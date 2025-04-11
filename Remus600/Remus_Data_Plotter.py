#!/usr/bin/env python3
"""
Author: Adapted from Noah Hunt's R script
Created: 2025-04-10
Organization: NOAA National Ocean Service (NOS) National Centers for Coastal
              Ocean Science (NCCOS) Marine Spatial Ecology Division (MSE)
              Seascape Ecology and Analytics Branch
Project: Developed for the Mesophotic Deep Benthic Communities Project
Description: Plots Remus vehicle motion and bathymetry data from NAV files
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as colors
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import geopandas as gpd
from shapely.geometry import Point
import tkinter as tk
from tkinter import filedialog, simpledialog
import re
from datetime import datetime
import seaborn as sns
from pathlib import Path

def parse_nav_file(file_path):
    """Parse the NAV file into DataFrames for motion and bathymetry data."""
    try:
        # Read the file, with the first line as comment and the second line as header
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # Extract the header line (second line) which contains the column names
        header_line = lines[0].strip()
        # Extract units line (third line)
        units_line = lines[1].strip()
        
        # Clean header to get column names
        columns = [col.strip() for col in header_line.split(',')]
        
        # Read the data, skipping the first 2 lines (header and units)
        df = pd.read_csv(file_path, skiprows=2, names=columns)
        
        # Convert time to datetime format if exists
        if 'Time' in df.columns:
            # Strip any leading or trailing whitespace from the time values
            df['Time'] = df['Time'].str.strip()
            # Now convert to datetime
            df['time'] = pd.to_datetime(df['Time'], format='%H:%M:%S.%f').dt.time
        
        # Extract longitude and latitude from the Lon/Lat column
        if 'Lon/Lat' in df.columns:
            # Define a function to extract coordinates
            def extract_coordinates(coord_str):
                # DIVE017_NAV format has patterns like "28N05.66080  91W58.01316"
                # Extract latitude components
                lat_parts = re.search(r'(\d+)([NS])(\d+\.\d+)', coord_str)
                lon_parts = re.search(r'(\d+)([EW])(\d+\.\d+)', coord_str)
                
                if lat_parts and lon_parts:
                    lat_deg = int(lat_parts.group(1))
                    lat_dir = lat_parts.group(2)
                    lat_min = float(lat_parts.group(3))
                    
                    lon_deg = int(lon_parts.group(1))
                    lon_dir = lon_parts.group(2)
                    lon_min = float(lon_parts.group(3))
                    
                    # Convert to decimal degrees
                    latitude = lat_deg + lat_min/60
                    longitude = lon_deg + lon_min/60
                    
                    # Apply direction
                    if lat_dir == 'S':
                        latitude = -latitude
                    if lon_dir == 'W':
                        longitude = -longitude
                        
                    return pd.Series([longitude, latitude])
                return pd.Series([None, None])
            
            # Extract coordinates
            coords = df['Lon/Lat'].apply(extract_coordinates)
            df['longitude'] = coords[0]
            df['latitude'] = coords[1]
        
        # Get vehicle depth column
        depth_col = None
        for col in df.columns:
            if 'Depth of vehicle' in col:
                depth_col = col
                break
        
        if depth_col is None:
            # Try alternative names
            for col in df.columns:
                if 'Depth' in col:
                    depth_col = col
                    break
        
        if depth_col:
            # Rename for consistency
            df.rename(columns={depth_col: 'Depth'}, inplace=True)
        else:
            print("Warning: No depth column found in NAV file.")
            df['Depth'] = 0
        
        # Create motion dataframe with mandatory columns
        motion_cols = ['time', 'longitude', 'latitude', 'Depth']
        
        # Add columns if they exist
        for col_name in ['Pitch', 'Roll', 'Altitude', 'Heading']:
            found = False
            for df_col in df.columns:
                if col_name in df_col:
                    if df_col != col_name:
                        # Rename to standardize
                        df.rename(columns={df_col: col_name}, inplace=True)
                    motion_cols.append(col_name)
                    found = True
                    break
            
            if not found:
                print(f"Warning: {col_name} data not found in NAV file.")
                df[col_name] = 0  # Use zeros as placeholder
        
        # Create motion dataframe
        motion_df = df[motion_cols].copy()
        
        # If we don't have Heave, use Altitude as a proxy if available
        if 'Altitude' in motion_cols:
            motion_df['Heave'] = motion_df['Altitude']
        else:
            motion_df['Heave'] = 0
            
        # Create a bathymetry dataframe
        bathy_df = df[['longitude', 'latitude', 'Depth']].copy()
        
        # Remove duplicates
        bathy_df = bathy_df.drop_duplicates()
        
        return motion_df, bathy_df
        
    except Exception as e:
        print(f"Error parsing NAV file: {e}")
        import traceback
        traceback.print_exc()
        raise

def create_geopandas_df(df):
    """Convert pandas DataFrame to GeoPandas DataFrame."""
    # Create a GeoDataFrame
    geometry = [Point(xy) for xy in zip(df['longitude'], df['latitude'])]
    geo_df = gpd.GeoDataFrame(df, geometry=geometry)
    geo_df.crs = "EPSG:4326"  # Set coordinate reference system to WGS84
    return geo_df

def plot_motion_map(data, plot_var, color_map, bbox, ax, remove_x_axis_title=False, remove_y_axis_title=False):
    """Plot motion data on a map."""
    data.plot(column=plot_var, cmap=color_map, markersize=3, ax=ax)
    
    # Set plot limits
    ax.set_xlim(bbox[0], bbox[1])
    ax.set_ylim(bbox[2], bbox[3])
    
    # Add labels and styling
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(f"{plot_var}")
    
    # Style the plot
    ax.grid(True, alpha=0.3)
    ax.set_facecolor('#121212')  # Dark background
    
    # Remove axis titles if requested
    if remove_x_axis_title:
        ax.set_xlabel("")
    if remove_y_axis_title:
        ax.set_ylabel("")
    
    return ax

def plot_bathy_map(data, plot_var, bbox, ax, remove_x_axis_title=False, remove_y_axis_title=False):
    """Plot bathymetry data on a map."""
    # Plot with a red to green color scheme
    data.plot(column=plot_var, cmap='RdYlGn', markersize=3, ax=ax)
    
    # Set plot limits
    ax.set_xlim(bbox[0], bbox[1])
    ax.set_ylim(bbox[2], bbox[3])
    
    # Add labels and styling
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(f"{plot_var} (m)")
    
    # Style the plot
    ax.grid(True, alpha=0.3)
    ax.set_facecolor('#121212')  # Dark background
    
    # Remove axis titles if requested
    if remove_x_axis_title:
        ax.set_xlabel("")
    if remove_y_axis_title:
        ax.set_ylabel("")
    
    return ax

def plot_motion_timeseries(data, plot_var, time_var, depth_var, ax, remove_x_axis_title=False, remove_y_axis_title=False):
    """Plot motion data as a time series."""
    # Convert time to seconds for plotting
    time_in_seconds = [(t.hour * 3600 + t.minute * 60 + t.second) for t in data[time_var]]
    
    # Create scatter plot colored by depth
    scatter = ax.scatter(time_in_seconds, data[plot_var], c=data[depth_var], cmap='RdYlGn')
    
    # Add colorbar
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label("Depth (m)")
    
    # Add labels and styling
    ax.set_xlabel("Time (s)")
    ax.set_ylabel(f"{plot_var} (°)")
    ax.set_title(f"{plot_var} over Time")
    
    # Style the plot
    ax.grid(True, alpha=0.3)
    ax.set_facecolor('#121212')  # Dark background
    ax.tick_params(axis='both', colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    ax.title.set_color('white')
    
    # Remove axis titles if requested
    if remove_x_axis_title:
        ax.set_xlabel("")
    if remove_y_axis_title:
        ax.set_ylabel("")
    
    return ax

def plot_motion_histogram(data, plot_var, plot_color, ax, remove_x_axis_title=False, remove_y_axis_title=False):
    """Plot motion data as a histogram."""
    # Calculate statistics
    min_value = data[plot_var].min()
    max_value = data[plot_var].max()
    mean_value = data[plot_var].mean()
    sd_value = data[plot_var].std()
    
    # Create histogram
    ax.hist(data[plot_var], bins=100, color=plot_color)
    
    # Add statistics text
    stats_text = f"Min: {min_value:.2f}\nMax: {max_value:.2f}\nMean: {mean_value:.2f}\nSD: {sd_value:.2f}"
    ax.text(0.95, 0.95, stats_text, transform=ax.transAxes, 
            verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='black', alpha=0.7))
    
    # Add labels and styling
    ax.set_xlabel(f"{plot_var} (°)")
    ax.set_ylabel("Count")
    ax.set_title(f"{plot_var} Distribution")
    
    # Style the plot
    ax.grid(True, alpha=0.3)
    ax.set_facecolor('#121212')  # Dark background
    ax.tick_params(axis='both', colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    ax.title.set_color('white')
    
    # Remove axis titles if requested
    if remove_x_axis_title:
        ax.set_xlabel("")
    if remove_y_axis_title:
        ax.set_ylabel("")
    
    return ax

def create_and_save_plots(motion_df, bathy_df, dive_name, output_dir):
    """Create and save all plots."""
    # Convert to GeoDataFrames
    motion_geo_df = create_geopandas_df(motion_df)
    bathy_geo_df = create_geopandas_df(bathy_df)
    
    # Calculate bounding boxes
    motion_bbox = (
        motion_geo_df.geometry.x.min() - 0.0001,
        motion_geo_df.geometry.x.max() + 0.0001,
        motion_geo_df.geometry.y.min() - 0.0001,
        motion_geo_df.geometry.y.max() + 0.0001
    )
    
    bathy_bbox = (
        bathy_geo_df.geometry.x.min() - 0.0001,
        bathy_geo_df.geometry.x.max() + 0.0001,
        bathy_geo_df.geometry.y.min() - 0.0001,
        bathy_geo_df.geometry.y.max() + 0.0001
    )
    
    # Set up style
    plt.style.use('dark_background')
    
    # 1. Create motion maps figure
    fig_maps, axes_maps = plt.subplots(1, 3, figsize=(15, 5))
    
    plot_motion_map(motion_geo_df, 'Heave', 'mako', motion_bbox, axes_maps[0], remove_x_axis_title=True)
    plot_motion_map(motion_geo_df, 'Pitch', 'magma', motion_bbox, axes_maps[1], remove_x_axis_title=True, remove_y_axis_title=True)
    plot_motion_map(motion_geo_df, 'Roll', 'viridis', motion_bbox, axes_maps[2], remove_x_axis_title=True, remove_y_axis_title=True)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"{dive_name}_motion_maps.png"), dpi=300)
    plt.close(fig_maps)
    
    # 2. Create histograms figure
    fig_hist, axes_hist = plt.subplots(1, 3, figsize=(15, 5))
    
    plot_motion_histogram(motion_df, 'Heave', '#a9e1fb', axes_hist[0])
    plot_motion_histogram(motion_df, 'Pitch', '#f7705c', axes_hist[1], remove_y_axis_title=True)
    plot_motion_histogram(motion_df, 'Roll', '#44bf70', axes_hist[2], remove_y_axis_title=True)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"{dive_name}_motion_histograms.png"), dpi=300)
    plt.close(fig_hist)
    
    # 3. Create time series figure
    fig_ts, axes_ts = plt.subplots(1, 3, figsize=(15, 5))
    
    plot_motion_timeseries(motion_df, 'Heave', 'time', 'Depth', axes_ts[0], remove_x_axis_title=True)
    plot_motion_timeseries(motion_df, 'Pitch', 'time', 'Depth', axes_ts[1], remove_y_axis_title=True)
    plot_motion_timeseries(motion_df, 'Roll', 'time', 'Depth', axes_ts[2], remove_x_axis_title=True, remove_y_axis_title=True)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"{dive_name}_motion_timeseries.png"), dpi=300)
    plt.close(fig_ts)
    
    # 4. Create bathymetry map
    fig_bathy, ax_bathy = plt.subplots(figsize=(8, 8))
    
    plot_bathy_map(bathy_geo_df, 'Depth', bathy_bbox, ax_bathy)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"{dive_name}_bathy_map.png"), dpi=300)
    plt.close(fig_bathy)
    
    print(f"All plots saved to {output_dir}")

def main():
    """Main function to run the program."""
    # Initialize tkinter
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    # Ask user for input file
    input_file = filedialog.askopenfilename(
        title="Select NAV file",
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
    )
    
    if not input_file:
        print("No input file selected. Exiting.")
        return
    
    # Ask user for output directory
    output_dir = filedialog.askdirectory(
        title="Select output directory for plots"
    )
    
    if not output_dir:
        print("No output directory selected. Exiting.")
        return
    
    # Ask user for dive name
    dive_name = simpledialog.askstring(
        "Dive Name", 
        "Enter the name of the dive (e.g., DIVE017):",
        parent=root
    )
    
    if not dive_name:
        # Extract dive name from filename if not provided
        dive_match = re.search(r'(DIVE\d+)', os.path.basename(input_file))
        if dive_match:
            dive_name = dive_match.group(1)
        else:
            dive_name = "DIVE_UNKNOWN"
    
    # Parse NAV file
    try:
        motion_df, bathy_df = parse_nav_file(input_file)
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Create and save plots
        create_and_save_plots(motion_df, bathy_df, dive_name, output_dir)
        
        print(f"Processing complete for {dive_name}")
        
    except Exception as e:
        print(f"Error processing file: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()