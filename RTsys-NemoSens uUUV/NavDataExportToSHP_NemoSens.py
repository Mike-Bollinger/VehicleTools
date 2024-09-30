import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
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

    # Create geometry from latitude and longitude columns
    geometry = [Point(xy) for xy in zip(df_filtered['Longitude deg'], df_filtered['latitude deg'])]

    # Create a GeoDataFrame, keeping all columns
    gdf = gpd.GeoDataFrame(df_filtered, geometry=geometry)

    # Set the Coordinate Reference System to WGS84
    gdf.set_crs(epsg=4326, inplace=True)

    # Define the output shapefile path based on the input file name
    base_name = os.path.basename(file_path).replace('.csv', '.shp')
    shapefile_path = os.path.join(output_dir, base_name)

    # Export GeoDataFrame to ESRI Shapefile
    gdf.to_file(shapefile_path)

    print(f"Shapefile created at: {shapefile_path}")


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
