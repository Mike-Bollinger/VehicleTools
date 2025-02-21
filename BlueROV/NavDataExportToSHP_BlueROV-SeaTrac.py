import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString
import os
import tkinter as tk
from tkinter import filedialog

# Create a GUI for file selection
root = tk.Tk()
root.withdraw()

# Select the _Nav file
nav_file = filedialog.askopenfilename(title="Select Navigation (_Nav) File", filetypes=[("CSV Files", "*.csv")])
if not nav_file:
    print("No Navigation file selected. Exiting.")
    exit()

# Select the _Diag file (optional)
diag_file = filedialog.askopenfilename(title="Select Diagnostic (_Diag) File", filetypes=[("CSV Files", "*.csv")])

# Select output directory
output_dir = filedialog.askdirectory(title="Select Output Directory")
if not output_dir:
    print("No output directory selected. Exiting.")
    exit()

# Generate output filenames based on _Nav filename without extension
base_name = os.path.splitext(os.path.basename(nav_file))[0].replace("_Nav", "")
output_csv = os.path.join(output_dir, f"{base_name}_Final.csv")
output_point_shapefile = os.path.join(output_dir, f"{base_name}_Points.shp")
output_line_shapefile = os.path.join(output_dir, f"{base_name}_Line.shp")

# Define column names for the _Nav and _Diag files
nav_columns = ["Timestamp", "ID", "Latitude", "Longitude", "Easting", "Northing", "Depth"]
diag_columns = ["Timestamp", "ID", "Local_Yaw", "Local_Pitch", "Local_Roll", "Azimuth", "Elevation", "Range", "Fit_Error","Blank"]

# Read the _Nav CSV (no headers in file, so assign column names)
df_nav = pd.read_csv(nav_file, header=None, names=nav_columns)

# Convert _Nav Timestamp to datetime and round to nearest second
df_nav["Timestamp"] = pd.to_datetime(df_nav["Timestamp"]).dt.round('s')  # Changed 'S' to 's'

# Read and clean the _Diag CSV if provided
df_diag = None
if diag_file:
    df_diag = pd.read_csv(diag_file, header=None, names=diag_columns, skiprows=1)

    # Convert the _Diag Timestamp to datetime format, handling the specific format
    df_diag["Timestamp"] = pd.to_datetime(df_diag["Timestamp"], format='%a %b %d %H:%M:%S %Y', errors='coerce')

    # Round the _Diag timestamps to the nearest second to help with merging
    df_diag["Timestamp"] = df_diag["Timestamp"].dt.round('s')  # Changed 'S' to 's'

# Merge the data on the Timestamp column
if df_diag is not None:
    merged_df = pd.merge(df_nav, df_diag, on="Timestamp", how="inner")
else:
    merged_df = df_nav

# Save merged data to CSV
merged_df.to_csv(output_csv, index=False)

#Convert DateTime to String
merged_df["Timestamp"] = merged_df["Timestamp"].astype(str)

# Convert to GeoDataFrame for Shapefile export
geometry = [Point(xy) for xy in zip(merged_df["Longitude"], merged_df["Latitude"])]
gdf_points = gpd.GeoDataFrame(merged_df, geometry=geometry, crs="EPSG:4326")
gdf_points.to_file(output_point_shapefile)

# Create LineString geometry from ordered points if more than 1 point exists
gdf_sorted = gdf_points.sort_values(by="Timestamp")  # Sorting by ID as Timestamp is removed
if len(gdf_sorted) > 1:
    array = [row.geometry for _, row in gdf_sorted.iterrows()]
    line_geometry = LineString(array)
    gdf_line = gpd.GeoDataFrame(pd.DataFrame([{"Timestamp": base_name, "geometry": line_geometry}]), crs="EPSG:4326")
    gdf_line.to_file(output_line_shapefile)

print(f"Combined CSV saved as {output_csv}")
print(f"Point Shapefile saved as {output_point_shapefile}")
print(f"Line Shapefile saved as {output_line_shapefile}")
