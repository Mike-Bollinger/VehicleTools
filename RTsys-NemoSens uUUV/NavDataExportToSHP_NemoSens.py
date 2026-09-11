"""
Title: NemoSens Navigation CSV to Shapefile Converter
Author: Mike Bollinger
Last Updated: 2025

FUNCTION:
    Converts one or more semicolon-delimited NemoSens navigation CSV files
    into WGS84 point shapefiles, filtering out rows with zero/zero
    latitude-longitude and non-positive depth, and also produces a dissolved
    polyline (track line) shapefile per input file.

USAGE:
    Run the script directly to launch file/folder selection dialogs:
        python NavDataExportToSHP_NemoSens.py
    Select one or more navigation CSV files, then select an output folder.

INPUTS:
    - One or more semicolon-delimited CSV files selected via the GUI,
      containing at minimum "latitude deg", "Longitude deg", and "Depth m"
      columns.
    - An output directory selected via the GUI.

OUTPUTS:
    Per input CSV: a point shapefile (same base name, .shp extension) in
    EPSG:4326 retaining all original CSV columns, plus a dissolved polyline
    track-line shapefile ("Dissolved_<base name>.shp") with DIVE and
    Length_m (geodesic, meters) attributes, both written to the chosen
    output directory.
"""

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString
from pyproj import Geod
from tkinter import Tk, filedialog
import os


def convert_csv_to_shapefile(file_path, output_dir):
    # Load the semicolon-delimited CSV file
    df = pd.read_csv(file_path, sep=';')

    # Filter out rows where both Latitude and Longitude are 0, or Depth is 0 or less
    df_filtered = df[~((df['latitude deg'] == 0) & (df['Longitude deg'] == 0)) & (df['Depth m'] > 0)]

    # Check if there are any valid points after filtering
    if df_filtered.empty:
        print(f"No valid data in {file_path} after filtering. Skipping.")
        return

    # Sort by mission time so the track line follows the vehicle's actual path
    if 'timestamp s' in df_filtered.columns:
        df_filtered = df_filtered.sort_values('timestamp s')

    # Create geometry from latitude and longitude columns
    geometry = [Point(xy) for xy in zip(df_filtered['Longitude deg'], df_filtered['latitude deg'])]

    # Create a GeoDataFrame, keeping all columns
    gdf = gpd.GeoDataFrame(df_filtered, geometry=geometry)

    # Set the Coordinate Reference System to WGS84
    gdf.set_crs(epsg=4326, inplace=True)

    # Define the output shapefile path based on the input file name
    base_name = os.path.basename(file_path).replace('.csv', '')
    shapefile_path = os.path.join(output_dir, f"{base_name}.shp")

    # Export GeoDataFrame to ESRI Shapefile
    gdf.to_file(shapefile_path)

    print(f"Shapefile created at: {shapefile_path}")

    # Build a dissolved polyline (track line) from the same filtered points
    if len(geometry) < 2:
        print(f"Not enough points to create a track line for {file_path}. Skipping polyline output.")
        return

    track_line = LineString(geometry)
    length_m = Geod(ellps="WGS84").geometry_length(track_line)

    track_gdf = gpd.GeoDataFrame(
        {"DIVE": [base_name], "Length_m": [length_m]},
        geometry=[track_line],
        crs="EPSG:4326"
    )

    track_shapefile_path = os.path.join(output_dir, f"Dissolved_{base_name}.shp")
    track_gdf.to_file(track_shapefile_path)

    print(f"Dissolved polyline shapefile created at: {track_shapefile_path}")


def select_and_convert_files():
    # Initialize Tkinter and hide the root window
    root = Tk()
    root.withdraw()  # We don't need a full GUI, so keep the root window from appearing

    # Create a dialog to select multiple CSV files
    file_paths = filedialog.askopenfilenames(
        title="Select CSV files",
        filetypes=[("CSV files", "*.csv")]
    )

    if not file_paths:
        print("No files selected.")
        return

    # Ask for an output directory to save the shapefiles
    output_dir = filedialog.askdirectory(title="Select Output Directory")

    if not output_dir:
        print("No output directory selected.")
        return

    # Convert each selected CSV file to a shapefile
    for file_path in file_paths:
        convert_csv_to_shapefile(file_path, output_dir)


if __name__ == "__main__":
    select_and_convert_files()
