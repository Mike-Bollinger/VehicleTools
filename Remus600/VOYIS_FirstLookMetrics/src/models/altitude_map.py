import matplotlib.pyplot as plt
import os
import pandas as pd
from typing import List, Dict, Optional
import warnings

# Try importing geopandas, but handle the case where it might not be installed
try:
    import geopandas as gpd
    from shapely.geometry import Point
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False
    warnings.warn("geopandas or shapely not available. Shapefile export will be disabled.")

class AltitudeMap:
    def __init__(self):
        """Initialize the altitude map generator"""
        self.altitude_threshold = 9.0  # Default threshold in meters
    
    def set_altitude_threshold(self, threshold: float) -> None:
        """
        Set the threshold for altitude coloring
        
        Args:
            threshold: Altitude threshold in meters
        """
        self.altitude_threshold = threshold
    
    def create_location_map(self, gps_data: List[Dict], output_path: str, filename: str = "image_locations_map.png", metrics=None) -> Optional[str]:
        """
        Create a scatter plot of image locations colored by altitude
        
        Args:
            gps_data: List of dictionaries with latitude, longitude, altitude, and file_type
            output_path: Directory to save the plot
            filename: Filename for the generated map
            metrics: Optional Metrics object to use for statistics
            
        Returns:
            Path to the saved plot file, or None if no data or error
        """
        if not gps_data:
            return None
        
        # Extract data for plotting, ensuring all required fields exist
        valid_points = []
        for point in gps_data:
            if all(key in point for key in ['latitude', 'longitude', 'altitude']):
                valid_points.append(point)
                
        if not valid_points:
            print("No valid GPS points with latitude, longitude, and altitude found")
            return None
        
        # Extract values for plotting
        latitudes = [point['latitude'] for point in valid_points]
        longitudes = [point['longitude'] for point in valid_points]
        altitudes = [point['altitude'] for point in valid_points]
        
        # Check if we actually have coordinate data
        if not latitudes or not longitudes:
            print("No valid latitude/longitude data found")
            return None
        
        # Print some diagnostic info
        print(f"Found {len(valid_points)} valid GPS points from {len(gps_data)} total")
        if valid_points:
            print(f"Sample point: {valid_points[0]}")
        
        # Create figure
        fig = plt.figure(figsize=(12, 8))
        ax = plt.axes()
        
        # Create colors based on altitude threshold
        colors = ['green' if alt < self.altitude_threshold else 'red' for alt in altitudes]
        
        # Create scatter plot
        scatter = plt.scatter(
            longitudes,
            latitudes,
            c=colors,
            alpha=0.8,
            s=30,  # Size of markers
            edgecolors='none',  # Remove the border entirely
        )
        
        # Add labels and title - note the updated title
        ax.set_xlabel('Longitude (Decimal Degrees)')
        ax.set_ylabel('Latitude (Decimal Degrees)')
        ax.set_title(f'Processed Image Locations by GPS Altitude (Threshold: {self.altitude_threshold}m)')
        
        # Create custom legend
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], marker='o', color='w', markerfacecolor='green', markersize=10, 
                  label=f'Altitude < {self.altitude_threshold}m'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='red', markersize=10, 
                  label=f'Altitude ≥ {self.altitude_threshold}m')
        ]
        ax.legend(handles=legend_elements)
        
        # Add grid lines
        ax.grid(True, linestyle='--', alpha=0.7)
        
        # Add data points count in the corner
        ax.text(0.02, 0.98, f'Total Points: {len(valid_points)}', 
                transform=ax.transAxes, fontsize=9, 
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Generate statistics text - use metrics if provided
        if metrics:
            stats = metrics.get_altitude_statistics(self.altitude_threshold)
            below_threshold = stats['below_threshold']
            above_threshold = stats['above_threshold']
            below_percent = stats['below_percent']
            above_percent = stats['above_percent']
        else:
            below_threshold = sum(1 for alt in altitudes if alt < self.altitude_threshold)
            above_threshold = len(altitudes) - below_threshold
            below_percent = (below_threshold/len(altitudes)*100) if altitudes else 0
            above_percent = (above_threshold/len(altitudes)*100) if altitudes else 0
        
        stats_text = (
            f'Below {self.altitude_threshold}m: {below_threshold} points ({below_percent:.1f}%)\n'
            f'Above {self.altitude_threshold}m: {above_threshold} points ({above_percent:.1f}%)'
        )
        
        # Add statistics text box
        ax.text(0.02, 0.92, stats_text, 
                transform=ax.transAxes, fontsize=9, 
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Configure axis formatting to show full coordinate values
        plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:.6f}"))
        plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:.6f}"))
        
        # Rotate x-axis labels for better readability
        plt.xticks(rotation=45, ha='right')
        
        # Adjust layout to accommodate the longer tick labels
        plt.tight_layout()
        
        # Save plot
        output_file = os.path.join(output_path, filename)
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        return output_file
    
    def create_altitude_histogram(self, gps_data: List[Dict], output_path: str, filename: str = "altitude_histogram.png") -> Optional[str]:
        """
        Create a histogram of image altitudes
        
        Args:
            gps_data: List of dictionaries with altitude data
            output_path: Directory to save the plot
            filename: Filename for the generated histogram
            
        Returns:
            Path to the saved plot file, or None if no data or error
        """
        if not gps_data:
            return None
        
        # Extract altitude data, ensuring the field exists
        altitudes = [point['altitude'] for point in gps_data if 'altitude' in point]
        
        if not altitudes:
            print("No valid altitude data found in GPS data")
            return None
        
        # Print some diagnostic info
        print(f"Found {len(altitudes)} valid altitude values from {len(gps_data)} total points")
        
        # Create figure
        plt.figure(figsize=(10, 6))
        
        # Create histogram with custom bin boundaries to highlight the threshold
        bins = plt.hist(altitudes, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
        
        # Add a vertical line at the threshold
        plt.axvline(x=self.altitude_threshold, color='red', linestyle='--', 
                   label=f'Threshold: {self.altitude_threshold}m')
        
        # Add labels and title - note the updated title
        plt.xlabel('Altitude (meters)')
        plt.ylabel('Number of Processed Images')
        plt.title('Distribution of Processed Image Altitudes')
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.legend()
        
        # Calculate statistics
        below_threshold = sum(1 for alt in altitudes if alt < self.altitude_threshold)
        above_threshold = len(altitudes) - below_threshold
        
        # Add statistics text
        stats_text = (
            f'Total: {len(altitudes)} images\n'
            f'Below {self.altitude_threshold}m: {below_threshold} ({below_threshold/len(altitudes)*100:.1f}%)\n'
            f'Above {self.altitude_threshold}m: {above_threshold} ({above_threshold/len(altitudes)*100:.1f}%)\n'
            f'Min: {min(altitudes):.2f}m, Max: {max(altitudes):.2f}m, Avg: {sum(altitudes)/len(altitudes):.2f}m'
        )
        
        plt.annotate(stats_text, xy=(0.02, 0.95), xycoords='axes fraction',
                    fontsize=9, bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Adjust layout
        plt.tight_layout()
        
        # Save plot
        output_file = os.path.join(output_path, filename)
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        return output_file
    
    def export_to_gis_formats(self, gps_data: List[Dict], output_path: str, 
                             csv_filename: str = "image_locations.csv",
                             shapefile_filename: str = "image_locations.shp") -> Dict[str, str]:
        """
        Export GPS data to CSV and shapefile formats for GIS analysis
        
        Args:
            gps_data: List of dictionaries with GPS and EXIF data
            output_path: Directory to save the output files
            csv_filename: Name for the CSV file
            shapefile_filename: Name for the shapefile
            
        Returns:
            Dictionary with paths to created files
        """
        if not gps_data:
            print("No GPS data to export")
            return {}
        
        result_files = {}
        
        # Extract valid points (those with latitude and longitude)
        valid_points = []
        for point in gps_data:
            if all(key in point for key in ['latitude', 'longitude']):
                valid_points.append(point)
        
        if not valid_points:
            print("No valid GPS points found for export")
            return {}
        
        # Create a pandas DataFrame from the GPS data
        df = pd.DataFrame(valid_points)
        
        # Add missing columns if they don't exist
        for column in ["DateTime", "ExposureTime", "FNumber", "FocalLength", 
                       "SubjectDistance", "ImageWidth", "ImageHeight"]:
            if column not in df.columns:
                df[column] = "N/A"
        
        # Add a field to indicate whether altitude is below threshold
        df['below_threshold'] = df['altitude'].apply(lambda alt: 'Yes' if alt < self.altitude_threshold else 'No')
        
        # Parse datetime from filename if not available in EXIF
        if 'DateTime' not in df.columns or (df['DateTime'] == "N/A").all():
            def extract_datetime(filename):
                # Example filename format: ESC_stills_processed_PPS_2024-06-27T060004.978700_789.jpg
                try:
                    # Extract datetime part from filename
                    parts = filename.split('_')
                    if len(parts) >= 5:
                        datetime_part = parts[4].split('.')[0]
                        return datetime_part.replace('T', ' ')
                    return "N/A"
                except:
                    return "N/A"
                    
            if 'filename' in df.columns:
                df['DateTime'] = df['filename'].apply(extract_datetime)
        
        # Replace any NaN values with "N/A" for better CSV output
        df = df.fillna("N/A")
        
        # Export to CSV
        csv_path = os.path.join(output_path, csv_filename)
        df.to_csv(csv_path, index=False)
        result_files['csv'] = csv_path
        print(f"GPS data exported to CSV: {csv_path}")
        
        # Export to shapefile if geopandas is available
        if GEOPANDAS_AVAILABLE:
            try:
                # Create geometry column (Point objects) from latitude and longitude
                geometry = [Point(x, y) for x, y in zip(df['longitude'], df['latitude'])]
                
                # Create GeoDataFrame
                gdf = gpd.GeoDataFrame(df, geometry=geometry)
                
                # Set coordinate reference system (CRS) to WGS84
                gdf.crs = "EPSG:4326"  # WGS84 - standard GPS coordinate system
                
                # Export to shapefile
                shapefile_path = os.path.join(output_path, shapefile_filename)
                gdf.to_file(shapefile_path)
                result_files['shapefile'] = shapefile_path
                print(f"GPS data exported to shapefile: {shapefile_path}")
                
            except Exception as e:
                print(f"Error creating shapefile: {e}")
        else:
            print("Geopandas not available. Skipping shapefile creation.")
        
        return result_files