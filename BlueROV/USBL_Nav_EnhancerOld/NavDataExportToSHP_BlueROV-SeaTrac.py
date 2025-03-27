import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter1d
from shapely.geometry import Point, LineString
import os
import tkinter as tk
from tkinter import filedialog, messagebox, Label, Button, Frame
from geopy.distance import geodesic
from scipy.interpolate import interp1d
import matplotlib.dates as mdates

# USBL Smoothing Configuration Parameters
SMOOTHING_WINDOW_SIZE = 7     # Size of the rolling window for weighted moving average
SMOOTHING_SIGMA = 1.5         # Sigma parameter for Gaussian filter
FIT_ERROR_THRESHOLD = 10      # Maximum acceptable Fit_Error value

# Function to browse and add multiple files
def browse_files(file_list, labels_frame, title):
    files = filedialog.askopenfilenames(title=title, filetypes=[("CSV Files", "*.csv")])
    for file in files:
        file_list.append(file)
        Label(labels_frame, text=os.path.basename(file), pady=2).pack()

# Function to browse for output directory
def browse_output():
    global output_dir
    output_dir = filedialog.askdirectory(title="Select Output Directory")
    output_label.config(text=output_dir)

# Function to reset selections
def reset_selections():
    global nav_files, diag_files, output_dir
    nav_files.clear()
    diag_files.clear()
    output_dir = ""
    for widget in nav_frame.winfo_children():
        widget.destroy()
    for widget in diag_frame.winfo_children():
        widget.destroy()
    output_label.config(text="No directory selected")

# Add this new function for smoothing navigation data
def smooth_navigation(df):
    """
    Enhanced smoothing for navigation data with better handling of duplicates and outliers
    Uses global parameters: SMOOTHING_WINDOW_SIZE, SMOOTHING_SIGMA, FIT_ERROR_THRESHOLD
    """
    # Create a copy of the dataframe to hold smoothed data
    smoothed_df = df.copy()
    
    # First, remove duplicated timestamps keeping only the best quality point at each time
    if 'Fit_Error' in df.columns:
        # Sort by timestamp and Fit_Error (best quality first)
        deduped_df = df.sort_values(['Timestamp', 'Fit_Error']).drop_duplicates('Timestamp', keep='first')
        deduped_df = deduped_df.sort_values('Timestamp').reset_index(drop=True)
        
        # Convert Fit_Error to weights (inverse relationship) with adjusted scaling
        # Higher contrast between good and bad points
        deduped_df['Weight'] = 1 / (deduped_df['Fit_Error']**2 + 0.01)
        
        # Filter out extremely poor quality points
        quality_data = deduped_df[deduped_df['Fit_Error'] < FIT_ERROR_THRESHOLD].copy()
        
        if len(quality_data) > 10:  # Only smooth if we have enough quality points
            # First-pass weighted moving average to remove the worst jitter
            quality_data['Longitude'] = quality_data['Longitude'].rolling(
                window=SMOOTHING_WINDOW_SIZE, center=True, min_periods=1
            ).apply(lambda x: np.average(x, weights=quality_data.loc[x.index, 'Weight']))
            
            quality_data['Latitude'] = quality_data['Latitude'].rolling(
                window=SMOOTHING_WINDOW_SIZE, center=True, min_periods=1
            ).apply(lambda x: np.average(x, weights=quality_data.loc[x.index, 'Weight']))
            
            # Second pass with Gaussian filter for more gradual transitions
            quality_data['Longitude'] = gaussian_filter1d(quality_data['Longitude'], sigma=SMOOTHING_SIGMA)
            quality_data['Latitude'] = gaussian_filter1d(quality_data['Latitude'], sigma=SMOOTHING_SIGMA)
            
            # Create a time-based index for proper interpolation
            time_idx = pd.to_datetime(quality_data['Timestamp'])
            
            # Interpolate smoothed positions back to original timestamps 
            # to maintain same record count as original data
            lon_interpolator = interp1d(
                mdates.date2num(time_idx), 
                quality_data['Longitude'],
                bounds_error=False, 
                fill_value='extrapolate'
            )
            lat_interpolator = interp1d(
                mdates.date2num(time_idx), 
                quality_data['Latitude'],
                bounds_error=False, 
                fill_value='extrapolate'
            )
            
            # Apply interpolation to get smoothed values for all original timestamps
            smoothed_times = mdates.date2num(pd.to_datetime(df['Timestamp']))
            smoothed_df['Longitude'] = lon_interpolator(smoothed_times)
            smoothed_df['Latitude'] = lat_interpolator(smoothed_times)
            
            print(f"Smoothing applied based on {len(quality_data)} quality data points")
    
    else:
        # Handle data without Fit_Error by removing duplicates first
        deduped_df = df.drop_duplicates('Timestamp').sort_values('Timestamp').reset_index(drop=True)
        print("Diagnostic data not available. Using simple smoothing methods.")
        
        # First apply outlier removal (distance-based)
        coords = np.column_stack([deduped_df['Longitude'], deduped_df['Latitude']])
        if len(coords) > 10:
            # Calculate relative distances between consecutive points
            distances = np.sqrt(np.sum(np.diff(coords, axis=0)**2, axis=1))
            # Find points that are statistical outliers
            mean_dist = np.mean(distances)
            std_dist = np.std(distances)
            threshold = mean_dist + 2 * std_dist
            
            # Create mask for valid points
            good_point_mask = np.ones(len(coords), dtype=bool)
            for i in range(1, len(coords)):
                if i < len(distances) and distances[i-1] > threshold:
                    good_point_mask[i] = False
            
            # Apply simple moving average to filtered data
            filtered_df = deduped_df[good_point_mask]
            
            # Apply simple moving average
            filtered_df['Longitude'] = filtered_df['Longitude'].rolling(
                window=SMOOTHING_WINDOW_SIZE, center=True, min_periods=1
            ).mean()
            
            filtered_df['Latitude'] = filtered_df['Latitude'].rolling(
                window=SMOOTHING_WINDOW_SIZE, center=True, min_periods=1
            ).mean()
            
            # Apply Gaussian filter for additional smoothing
            filtered_df['Longitude'] = gaussian_filter1d(filtered_df['Longitude'], sigma=SMOOTHING_SIGMA)
            filtered_df['Latitude'] = gaussian_filter1d(filtered_df['Latitude'], sigma=SMOOTHING_SIGMA)
            
            # Interpolate back to original timestamps
            time_idx = pd.to_datetime(filtered_df['Timestamp'])
            
            lon_interpolator = interp1d(
                mdates.date2num(time_idx), 
                filtered_df['Longitude'],
                bounds_error=False, 
                fill_value='extrapolate'
            )
            lat_interpolator = interp1d(
                mdates.date2num(time_idx), 
                filtered_df['Latitude'],
                bounds_error=False, 
                fill_value='extrapolate'
            )
            
            smoothed_times = mdates.date2num(pd.to_datetime(df['Timestamp']))
            smoothed_df['Longitude'] = lon_interpolator(smoothed_times)
            smoothed_df['Latitude'] = lat_interpolator(smoothed_times)
    
    return smoothed_df

# Add this function to calculate distance
def calculate_track_distance(df):
    """
    Calculate the total distance traveled in the track in kilometers
    """
    total_distance = 0
    for i in range(1, len(df)):
        point1 = (df.iloc[i-1]['Latitude'], df.iloc[i-1]['Longitude'])
        point2 = (df.iloc[i]['Latitude'], df.iloc[i]['Longitude'])
        # Calculate distance between consecutive points in meters
        distance = geodesic(point1, point2).kilometers
        total_distance += distance
    return total_distance

# Function to process the selected files
def process_files():
    if not nav_files or not output_dir:
        messagebox.showerror("Error", "Navigation files and output directory are required.")
        return

    # Generate output filenames based on first _Nav filename without extension
    base_name = os.path.splitext(os.path.basename(nav_files[0]))[0].replace("_Nav", "")
    output_csv = os.path.join(output_dir, f"{base_name}_Final.csv")
    output_point_shapefile = os.path.join(output_dir, f"{base_name}_Points.shp")
    output_line_shapefile = os.path.join(output_dir, f"{base_name}_Line.shp")
    output_smoothed_point_shapefile = os.path.join(output_dir, f"{base_name}_Points_Smoothed.shp")
    output_smoothed_line_shapefile = os.path.join(output_dir, f"{base_name}_Line_Smoothed.shp")
    output_plot = os.path.join(output_dir, f"{base_name}_Track_Comparison.png")

    # Define column names
    nav_columns = ["Timestamp", "ID", "Latitude", "Longitude", "Easting", "Northing", "Depth"]
    diag_columns = ["Timestamp", "ID", "Local_Yaw", "Local_Pitch", "Local_Roll", "Azimuth", "Elevation", "Range", "Fit_Error", "Blank"]

    # Read and combine _Nav CSV files
    df_nav = pd.concat([pd.read_csv(f, header=None, names=nav_columns) for f in nav_files], ignore_index=True)
    df_nav["Timestamp"] = pd.to_datetime(df_nav["Timestamp"]).dt.round('s')

    df_diag = None
    if diag_files:
        df_diag = pd.concat([pd.read_csv(f, header=None, names=diag_columns, skiprows=1) for f in diag_files], ignore_index=True)
        df_diag["Timestamp"] = pd.to_datetime(df_diag["Timestamp"], format='%a %b %d %H:%M:%S %Y', errors='coerce')
        df_diag["Timestamp"] = df_diag["Timestamp"].dt.round('s')

    # Merge the data
    merged_df = pd.merge(df_nav, df_diag, on="Timestamp", how="inner") if df_diag is not None else df_nav
    merged_df.to_csv(output_csv, index=False)
    
    # Create a copy with string timestamps for GeoDataFrame
    merged_df_geo = merged_df.copy()
    merged_df_geo["Timestamp"] = merged_df_geo["Timestamp"].astype(str)

    # Apply smoothing to navigation data
    smoothed_df = smooth_navigation(merged_df)
    smoothed_df_geo = smoothed_df.copy()
    smoothed_df_geo["Timestamp"] = smoothed_df_geo["Timestamp"].astype(str)

    # Calculate distance for the smoothed track
    track_distance = calculate_track_distance(smoothed_df)

    # Convert original data to GeoDataFrame
    gdf_points = gpd.GeoDataFrame(
        merged_df_geo,
        geometry=[Point(xy) for xy in zip(merged_df_geo["Longitude"], merged_df_geo["Latitude"])],
        crs="EPSG:4326"
    )
    gdf_points.to_file(output_point_shapefile)

    # Convert smoothed data to GeoDataFrame with distance attribute
    gdf_points_smoothed = gpd.GeoDataFrame(
        smoothed_df_geo,
        geometry=[Point(xy) for xy in zip(smoothed_df_geo["Longitude"], smoothed_df_geo["Latitude"])],
        crs="EPSG:4326"
    )
    gdf_points_smoothed.to_file(output_smoothed_point_shapefile)

    # Create LineString geometry for original data
    gdf_sorted = gdf_points.sort_values(by="Timestamp")
    if len(gdf_sorted) > 1:
        line_geometry = LineString([row.geometry for _, row in gdf_sorted.iterrows()])
        gdf_line = gpd.GeoDataFrame(pd.DataFrame([{"Timestamp": base_name, "geometry": line_geometry}]), crs="EPSG:4326")
        gdf_line.to_file(output_line_shapefile)

    # Create LineString geometry for smoothed data with distance attribute
    gdf_sorted_smoothed = gdf_points_smoothed.sort_values(by="Timestamp")
    if len(gdf_sorted_smoothed) > 1:
        smoothed_line_geometry = LineString([row.geometry for _, row in gdf_sorted_smoothed.iterrows()])
        gdf_line_smoothed = gpd.GeoDataFrame(
            pd.DataFrame([{
                "Timestamp": base_name, 
                "Distance_km": round(track_distance, 3),
                "geometry": smoothed_line_geometry
            }]), 
            crs="EPSG:4326"
        )
        gdf_line_smoothed.to_file(output_smoothed_line_shapefile)

    # Create a plot comparing raw and smoothed tracks and showing distance
    plt.figure(figsize=(12, 10))
    plt.plot(merged_df["Longitude"], merged_df["Latitude"], 'b.-', alpha=0.5, label='Raw USBL Data')
    plt.plot(smoothed_df["Longitude"], smoothed_df["Latitude"], 'r-', linewidth=2, label='Smoothed Track')
    
    # Add distance information as text on plot
    plt.annotate(f"Total Distance: {round(track_distance, 3)} km", 
                xy=(0.05, 0.95), xycoords='axes fraction',
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8),
                fontsize=12)
                
    plt.title(f"USBL Track Comparison - {base_name}", fontsize=14)
    plt.xlabel('Longitude', fontsize=12)
    plt.ylabel('Latitude', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=12)
    plt.tight_layout()
    plt.savefig(output_plot, dpi=300)
    
    # Display the plot if user wants to see it
    plt.show()

    messagebox.showinfo("Success", f"Files saved:\n"
                                 f"{output_csv}\n"
                                 f"{output_point_shapefile} & {output_smoothed_point_shapefile}\n"
                                 f"{output_line_shapefile} & {output_smoothed_line_shapefile}\n"
                                 f"{output_plot}")

# Initialize GUI
root = tk.Tk()
root.title("ROV-SeaTrac USBL Navigation File Selection")
root.geometry("500x450")
root.configure(padx=20, pady=20)

nav_files, diag_files = [], []

# Navigation File Selection
Label(root, text="Select Navigation (_Nav) Files:", pady=5, font=("Arial", 10, "bold")).pack()
nav_frame = Frame(root)
nav_frame.pack()
Button(root, text="Add More Nav Files", command=lambda: browse_files(nav_files, nav_frame, "Select Navigation (_Nav) Files"), pady=5).pack()

# Horizontal Line Separator
Frame(root, height=2, width=450, bg="#CCCCCC").pack(pady=10)

# Diagnostic File Selection
Label(root, text="Select Diagnostic (_Diag) Files:", pady=5, font=("Arial", 10, "bold")).pack()
diag_frame = Frame(root)
diag_frame.pack()
Button(root, text="Add More Diag Files", command=lambda: browse_files(diag_files, diag_frame, "Select Diagnostic (_Diag) Files"), pady=5).pack()

# Horizontal Line Separator
Frame(root, height=2, width=450, bg="#CCCCCC").pack(pady=10)

# Output Directory Selection
Label(root, text="Select Output Directory:", pady=5, font=("Arial", 10, "bold")).pack()
output_label = Label(root, text="No directory selected", width=50, pady=5)
output_label.pack()
Button(root, text="Browse", command=browse_output, pady=5).pack()

# Horizontal Line Separator
Frame(root, height=2, width=450, bg="#CCCCCC").pack(pady=10)

# Buttons for Processing & Reset
Button(root, text="Process", command=process_files, pady=10, font=("Arial", 10, "bold"), bg="#4CAF50", fg="white").pack(pady=(10, 5))
Button(root, text="Reset", command=reset_selections, pady=10, font=("Arial", 10, "bold"), bg="#f44336", fg="white").pack()

root.mainloop()
