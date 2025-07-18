#!/usr/bin/env python3
"""
AUV Image Metadata Summary Analyzer
===================================

Author: Mike Bollinger (GitHub Copilot)
Date: 2025

DESCRIPTION:
This script analyzes AUV image metadata CSV files and provides comprehensive summary 
statistics for underwater vehicle missions. It processes all CSV files in a user-selected 
folder and calculates various metrics for each dive and overall mission statistics.

FEATURES:
- Image Counts: Total images per dive and overall mission
- Linear Distance: Calculates distance traveled using GPS coordinates and Haversine formula
- Depth Analysis: Min, max, and average depth per dive
- Altitude Analysis: Above-bottom altitude statistics (filters out -1 values)
- Time Analysis: Dive duration and imaging rates
- Position Tracking: Start/end coordinates for each dive
- Camera Settings: Exposure settings and light mode usage analysis
- Mission Overview: Combined statistics across all dives

USAGE:
1. Run the script: python ReportMetrics_fromImageMetadata_NemoSens.py
2. Select the folder containing your image metadata CSV files using the dialog
3. View the comprehensive analysis output in the console

INPUT FORMAT:
The script expects CSV files with the following columns (additional columns supported):
- Date, Time: For temporal analysis (e.g., '2024/09/25', '18:51:36.738')
- Latitude, Longitude: For distance calculations (decimal degrees)
- Depth: Water depth in meters
- Altitude: Above-bottom altitude in meters (-1 values filtered out)
- Exposure: Camera exposure settings
- Light Mode: Lighting configuration used
- Other columns: Processed but not required for core functionality

OUTPUT:
All results are printed to the console including:
- Overall mission summary (total images, distance, duration, etc.)
- Individual dive statistics with detailed metrics
- No files are created - all output displayed for immediate review

REQUIREMENTS:
- Python 3.6+
- pandas: pip install pandas
- numpy: pip install numpy  
- tkinter: Usually included with Python standard library

METRICS CALCULATED:
- Total images per dive and mission-wide
- Linear distance using Haversine formula for accurate GPS-based measurements
- Depth statistics (min/max/average) per dive
- Altitude above seafloor (excluding invalid -1 values)
- Dive duration and imaging rate (images per minute)
- Geographic coverage (start/end positions)
- Camera configuration analysis (exposure ranges, light modes)
- Mission timeline (start/end times across all dives)
"""

import pandas as pd
import numpy as np
import os
import math
from datetime import datetime
import tkinter as tk
from tkinter import filedialog
import glob


class ImageMetadataSummaryAnalyzer:
    """Analyzes AUV image metadata CSV files and provides comprehensive summary statistics."""
    
    def __init__(self):
        """Initialize the analyzer."""
        self.csv_files = []
        self.dive_summaries = {}
        self.total_summary = {}
        
    def haversine_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculate the great circle distance between two points on Earth in meters.
        
        Args:
            lat1, lon1: Latitude and longitude of first point in decimal degrees
            lat2, lon2: Latitude and longitude of second point in decimal degrees
            
        Returns:
            Distance in meters
        """
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Radius of earth in meters
        r = 6371000
        return c * r
    
    def calculate_total_distance(self, df):
        """
        Calculate total distance traveled based on GPS coordinates.
        
        Args:
            df: DataFrame with Latitude and Longitude columns
            
        Returns:
            Total distance in meters
        """
        if len(df) < 2:
            return 0.0
            
        total_distance = 0.0
        
        # Remove any rows with missing coordinates
        df_clean = df.dropna(subset=['Latitude', 'Longitude'])
        
        if len(df_clean) < 2:
            return 0.0
        
        # Calculate distance between consecutive points
        for i in range(1, len(df_clean)):
            lat1, lon1 = df_clean.iloc[i-1][['Latitude', 'Longitude']]
            lat2, lon2 = df_clean.iloc[i][['Latitude', 'Longitude']]
            
            distance = self.haversine_distance(lat1, lon1, lat2, lon2)
            total_distance += distance
            
        return total_distance
    
    def parse_datetime(self, date_str, time_str):
        """
        Parse date and time strings into datetime object.
        
        Args:
            date_str: Date string (e.g., '2024/09/25')
            time_str: Time string (e.g., '18:51:36.738')
            
        Returns:
            datetime object or None if parsing fails
        """
        try:
            datetime_str = f"{date_str} {time_str}"
            return pd.to_datetime(datetime_str)
        except:
            return None
    
    def analyze_csv_file(self, filepath):
        """
        Analyze a single CSV file and extract summary statistics.
        
        Args:
            filepath: Path to the CSV file
            
        Returns:
            Dictionary with summary statistics
        """
        try:
            # Read CSV file
            df = pd.read_csv(filepath)
            
            # Extract dive name from filename
            filename = os.path.basename(filepath)
            dive_name = filename.replace('_imagemetadata.csv', '').replace('.csv', '')
            
            # Initialize summary dictionary
            summary = {
                'dive_name': dive_name,
                'filename': filename,
                'total_images': len(df),
                'distance_meters': 0.0,
                'distance_km': 0.0,
                'min_depth': None,
                'max_depth': None,
                'avg_depth': None,
                'min_altitude': None,
                'max_altitude': None,
                'avg_altitude': None,
                'start_time': None,
                'end_time': None,
                'duration_minutes': None,
                'start_lat': None,
                'start_lon': None,
                'end_lat': None,
                'end_lon': None,
                'unique_light_modes': [],
                'avg_exposure': None,
                'exposure_range': None,
                'images_per_minute': None
            }
            
            if len(df) == 0:
                print(f"Warning: {filename} is empty")
                return summary
            
            # Calculate distance
            summary['distance_meters'] = self.calculate_total_distance(df)
            summary['distance_km'] = summary['distance_meters'] / 1000.0
            
            # Depth statistics
            if 'Depth' in df.columns:
                depth_clean = df['Depth'].dropna()
                if len(depth_clean) > 0:
                    summary['min_depth'] = depth_clean.min()
                    summary['max_depth'] = depth_clean.max()
                    summary['avg_depth'] = depth_clean.mean()
            
            # Altitude statistics
            if 'Altitude' in df.columns:
                altitude_clean = df['Altitude'].dropna()
                # Filter out -1 values which seem to indicate no data
                altitude_valid = altitude_clean[altitude_clean > -1]
                if len(altitude_valid) > 0:
                    summary['min_altitude'] = altitude_valid.min()
                    summary['max_altitude'] = altitude_valid.max()
                    summary['avg_altitude'] = altitude_valid.mean()
            
            # Time analysis
            if 'Date' in df.columns and 'Time' in df.columns:
                df['datetime'] = df.apply(lambda row: self.parse_datetime(row['Date'], row['Time']), axis=1)
                valid_times = df['datetime'].dropna()
                
                if len(valid_times) > 0:
                    summary['start_time'] = valid_times.min()
                    summary['end_time'] = valid_times.max()
                    
                    duration = summary['end_time'] - summary['start_time']
                    summary['duration_minutes'] = duration.total_seconds() / 60.0
                    
                    if summary['duration_minutes'] > 0:
                        summary['images_per_minute'] = summary['total_images'] / summary['duration_minutes']
            
            # Position information
            if 'Latitude' in df.columns and 'Longitude' in df.columns:
                lat_clean = df['Latitude'].dropna()
                lon_clean = df['Longitude'].dropna()
                
                if len(lat_clean) > 0 and len(lon_clean) > 0:
                    summary['start_lat'] = lat_clean.iloc[0]
                    summary['start_lon'] = lon_clean.iloc[0]
                    summary['end_lat'] = lat_clean.iloc[-1]
                    summary['end_lon'] = lon_clean.iloc[-1]
            
            # Light mode analysis
            if 'Light Mode' in df.columns:
                summary['unique_light_modes'] = df['Light Mode'].dropna().unique().tolist()
            
            # Exposure analysis
            if 'Exposure' in df.columns:
                exposure_clean = df['Exposure'].dropna()
                if len(exposure_clean) > 0:
                    summary['avg_exposure'] = exposure_clean.mean()
                    summary['exposure_range'] = (exposure_clean.min(), exposure_clean.max())
            
            return summary
            
        except Exception as e:
            print(f"Error analyzing {filepath}: {str(e)}")
            return None
    
    def select_folder(self):
        """Open dialog to select folder containing CSV files."""
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        
        folder_path = filedialog.askdirectory(
            title="Select folder containing image metadata CSV files"
        )
        
        root.destroy()
        return folder_path
    
    def find_csv_files(self, folder_path):
        """
        Find all CSV files in the selected folder.
        
        Args:
            folder_path: Path to folder to search
            
        Returns:
            List of CSV file paths
        """
        # Look for files with 'metadata' in the name or ending with .csv
        patterns = [
            os.path.join(folder_path, "*metadata*.csv"),
            os.path.join(folder_path, "*imagemetadata*.csv"),
            os.path.join(folder_path, "*.csv")
        ]
        
        csv_files = []
        for pattern in patterns:
            csv_files.extend(glob.glob(pattern))
        
        # Remove duplicates while preserving order
        seen = set()
        unique_files = []
        for file in csv_files:
            if file not in seen:
                seen.add(file)
                unique_files.append(file)
        
        return unique_files
    
    def calculate_total_summary(self):
        """Calculate overall summary statistics across all dives."""
        if not self.dive_summaries:
            return
        
        # Initialize totals
        total_images = 0
        total_distance_m = 0.0
        total_duration = 0.0
        all_depths = []
        all_altitudes = []
        all_exposures = []
        earliest_time = None
        latest_time = None
        
        for dive_id, summary in self.dive_summaries.items():
            total_images += summary['total_images']
            total_distance_m += summary['distance_meters']
            
            if summary['duration_minutes']:
                total_duration += summary['duration_minutes']
            
            if summary['min_depth'] is not None:
                all_depths.extend([summary['min_depth'], summary['max_depth']])
            
            if summary['min_altitude'] is not None:
                all_altitudes.extend([summary['min_altitude'], summary['max_altitude']])
            
            if summary['avg_exposure'] is not None:
                all_exposures.append(summary['avg_exposure'])
            
            if summary['start_time']:
                if earliest_time is None or summary['start_time'] < earliest_time:
                    earliest_time = summary['start_time']
            
            if summary['end_time']:
                if latest_time is None or summary['end_time'] > latest_time:
                    latest_time = summary['end_time']
        
        self.total_summary = {
            'total_dives': len(self.dive_summaries),
            'total_images': total_images,
            'total_distance_meters': total_distance_m,
            'total_distance_km': total_distance_m / 1000.0,
            'total_duration_minutes': total_duration,
            'total_duration_hours': total_duration / 60.0,
            'avg_images_per_dive': total_images / len(self.dive_summaries) if self.dive_summaries else 0,
            'avg_distance_per_dive_km': (total_distance_m / 1000.0) / len(self.dive_summaries) if self.dive_summaries else 0,
            'overall_depth_range': (min(all_depths), max(all_depths)) if all_depths else None,
            'overall_altitude_range': (min(all_altitudes), max(all_altitudes)) if all_altitudes else None,
            'avg_exposure_all_dives': np.mean(all_exposures) if all_exposures else None,
            'mission_start_time': earliest_time,
            'mission_end_time': latest_time
        }
    
    def print_summary_report(self):
        """Print comprehensive summary report to console."""
        print("\n" + "="*80)
        print("AUV IMAGE METADATA SUMMARY ANALYSIS")
        print("="*80)
        
        if not self.dive_summaries:
            print("No CSV files were successfully analyzed.")
            return
        
        # Overall summary
        print(f"\nOVERALL MISSION SUMMARY:")
        print(f"  Total Dives Analyzed: {self.total_summary['total_dives']}")
        print(f"  Total Images: {self.total_summary['total_images']:,}")
        print(f"  Total Distance: {self.total_summary['total_distance_km']:.2f} km ({self.total_summary['total_distance_meters']:.0f} m)")
        print(f"  Total Duration: {self.total_summary['total_duration_hours']:.2f} hours ({self.total_summary['total_duration_minutes']:.1f} minutes)")
        print(f"  Average Images per Dive: {self.total_summary['avg_images_per_dive']:.0f}")
        print(f"  Average Distance per Dive: {self.total_summary['avg_distance_per_dive_km']:.2f} km")
        
        if self.total_summary['overall_depth_range']:
            min_depth, max_depth = self.total_summary['overall_depth_range']
            print(f"  Overall Depth Range: {min_depth:.2f} to {max_depth:.2f} m")
        
        if self.total_summary['overall_altitude_range']:
            min_alt, max_alt = self.total_summary['overall_altitude_range']
            print(f"  Overall Altitude Range: {min_alt:.2f} to {max_alt:.2f} m")
        
        if self.total_summary['mission_start_time'] and self.total_summary['mission_end_time']:
            print(f"  Mission Period: {self.total_summary['mission_start_time'].strftime('%Y-%m-%d %H:%M')} to {self.total_summary['mission_end_time'].strftime('%Y-%m-%d %H:%M')}")
        
        # Individual dive summaries
        print(f"\nINDIVIDUAL DIVE SUMMARIES:")
        print("-" * 80)
        
        for dive_id, summary in self.dive_summaries.items():
            print(f"\nDive: {summary['dive_name']}")
            print(f"  File: {summary['filename']}")
            print(f"  Images: {summary['total_images']:,}")
            print(f"  Distance: {summary['distance_km']:.2f} km ({summary['distance_meters']:.0f} m)")
            
            if summary['duration_minutes']:
                print(f"  Duration: {summary['duration_minutes']:.1f} minutes ({summary['duration_minutes']/60:.2f} hours)")
            
            if summary['images_per_minute']:
                print(f"  Imaging Rate: {summary['images_per_minute']:.1f} images/minute")
            
            if summary['min_depth'] is not None:
                print(f"  Depth Range: {summary['min_depth']:.2f} to {summary['max_depth']:.2f} m (avg: {summary['avg_depth']:.2f} m)")
            
            if summary['min_altitude'] is not None:
                print(f"  Altitude Range: {summary['min_altitude']:.2f} to {summary['max_altitude']:.2f} m (avg: {summary['avg_altitude']:.2f} m)")
            
            if summary['start_time'] and summary['end_time']:
                print(f"  Time Period: {summary['start_time'].strftime('%Y-%m-%d %H:%M:%S')} to {summary['end_time'].strftime('%H:%M:%S')}")
            
            if summary['start_lat'] is not None:
                print(f"  Start Position: {summary['start_lat']:.6f}, {summary['start_lon']:.6f}")
                print(f"  End Position: {summary['end_lat']:.6f}, {summary['end_lon']:.6f}")
            
            if summary['unique_light_modes']:
                print(f"  Light Modes Used: {', '.join(map(str, summary['unique_light_modes']))}")
            
            if summary['avg_exposure'] is not None:
                min_exp, max_exp = summary['exposure_range']
                print(f"  Exposure: {summary['avg_exposure']:.1f} avg (range: {min_exp:.1f} - {max_exp:.1f})")
        
        print("\n" + "="*80)
        print("Analysis Complete!")
        print("="*80)
    
    def run_analysis(self):
        """Main method to run the complete analysis."""
        print("AUV Image Metadata Summary Analyzer")
        print("===================================")
        
        # Select folder
        folder_path = self.select_folder()
        if not folder_path:
            print("No folder selected. Exiting.")
            return
        
        print(f"\nAnalyzing CSV files in: {folder_path}")
        
        # Find CSV files
        csv_files = self.find_csv_files(folder_path)
        
        if not csv_files:
            print("No CSV files found in the selected folder.")
            return
        
        print(f"Found {len(csv_files)} CSV files:")
        for file in csv_files:
            print(f"  - {os.path.basename(file)}")
        
        print("\nAnalyzing files...")
        
        # Analyze each CSV file
        successful_analyses = 0
        for i, csv_file in enumerate(csv_files, 1):
            print(f"Processing {i}/{len(csv_files)}: {os.path.basename(csv_file)}...")
            
            summary = self.analyze_csv_file(csv_file)
            if summary:
                self.dive_summaries[summary['dive_name']] = summary
                successful_analyses += 1
            else:
                print(f"  Failed to analyze {os.path.basename(csv_file)}")
        
        print(f"\nSuccessfully analyzed {successful_analyses}/{len(csv_files)} files.")
        
        if successful_analyses > 0:
            # Calculate totals
            self.calculate_total_summary()
            
            # Print summary report
            self.print_summary_report()
        else:
            print("No files were successfully analyzed.")


def main():
    """Main function to run the analyzer."""
    analyzer = ImageMetadataSummaryAnalyzer()
    analyzer.run_analysis()


if __name__ == "__main__":
    main()
