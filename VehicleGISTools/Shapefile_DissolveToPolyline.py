"""
Title: Point Data to Dissolved Polyline Converter
Author: Mike Bollinger
Last Updated: 2026-09-10

FUNCTION:
    Converts point navigation/image-metadata data into a single dissolved
    polyline (track line) shapefile per input file. Accepts any mix of:
      - Image metadata CSV (e.g. Date, Time, Latitude, Longitude columns)
      - Image metadata point shapefile
      - NavLog point shapefile
      - NavLog CSV (Latitude/Longitude style columns)
    Latitude/Longitude columns and row order (via Date/Time, timestamp, or
    mission_time columns when present) are auto-detected by column name.

USAGE:
    Run the script and use the GUI to select one or more input .shp/.csv
    files and a destination folder:
        python Shapefile_DissolveToPolyline.py

INPUTS:
    - One or more point shapefiles (.shp) and/or CSV files selected via
      the GUI, in any combination of the supported formats above.
    - Destination folder for the dissolved polyline outputs.

OUTPUTS:
    One dissolved polyline shapefile per input file
    ("Dissolved_<input base name>.shp"), in EPSG:4326, with DIVE and
    Length_m (geodesic, meters) attributes.

LIMITATIONS:
    Assumes latitude/longitude values are decimal degrees. Does not parse
    DMS-formatted coordinate strings (e.g. Remus "28N05.66080").
"""

import os
import re
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString
from pyproj import Geod
from tkinter import Tk, filedialog, messagebox


def _tokenize(col_name):
    return re.split(r'[^a-z0-9]+', col_name.strip().lower())


def find_column(columns, keywords):
    """Find the first column whose tokenized name matches one of keywords."""
    for col in columns:
        if any(kw in _tokenize(col) for kw in keywords):
            return col
    return None


def find_sort_series(df):
    """Return a Series usable to order rows chronologically, or None if unavailable."""
    date_col = find_column(df.columns, {'date'})
    time_col = find_column(df.columns, {'time'})
    if date_col and time_col and date_col != time_col:
        combined = pd.to_datetime(
            df[date_col].astype(str) + ' ' + df[time_col].astype(str), errors='coerce'
        )
        if combined.notna().sum() >= 2:
            return combined

    # Fall back to a single timestamp-like column (epoch seconds or parseable datetime)
    for keywords in ({'timestamp'}, {'mission'}, {'time'}):
        col = find_column(df.columns, keywords)
        if col:
            numeric = pd.to_numeric(df[col], errors='coerce')
            if numeric.notna().sum() >= 2:
                return numeric
            parsed = pd.to_datetime(df[col], errors='coerce')
            if parsed.notna().sum() >= 2:
                return parsed

    return None


def read_csv_flexible(file_path):
    """Read a CSV trying common delimiters until one yields multiple columns."""
    for sep in (',', ';', '\t'):
        try:
            df = pd.read_csv(file_path, sep=sep)
        except Exception:
            continue
        if df.shape[1] > 1:
            return df
    raise ValueError(f"Could not parse {os.path.basename(file_path)} as a delimited CSV file.")


def load_points_from_csv(file_path):
    """Load lat/lon points from a NavLog or image-metadata style CSV."""
    df = read_csv_flexible(file_path)

    lat_col = find_column(df.columns, {'latitude', 'lat'})
    lon_col = find_column(df.columns, {'longitude', 'lon', 'long'})
    if not lat_col or not lon_col:
        raise ValueError(f"Could not find latitude/longitude columns in {os.path.basename(file_path)}.")

    df[lat_col] = pd.to_numeric(df[lat_col], errors='coerce')
    df[lon_col] = pd.to_numeric(df[lon_col], errors='coerce')
    df = df.dropna(subset=[lat_col, lon_col])
    df = df[~((df[lat_col] == 0) & (df[lon_col] == 0))]

    sort_series = find_sort_series(df)
    if sort_series is not None:
        df = df.loc[sort_series.sort_values(kind='stable').index]

    points = [Point(xy) for xy in zip(df[lon_col], df[lat_col])]
    return points, "EPSG:4326"


def load_points_from_shapefile(file_path):
    """Load points (in file order, or sorted by a detected time column) from a point shapefile."""
    gdf = gpd.read_file(file_path)
    if gdf.empty:
        raise ValueError(f"{os.path.basename(file_path)} contains no features.")
    if not gdf.geometry.geom_type.isin(['Point', 'MultiPoint']).all():
        raise ValueError(f"{os.path.basename(file_path)} is not a point shapefile.")

    if gdf.crs is not None and gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)

    sort_series = find_sort_series(gdf.drop(columns='geometry'))
    if sort_series is not None:
        gdf = gdf.loc[sort_series.sort_values(kind='stable').index]

    return list(gdf.geometry), "EPSG:4326"


def create_dissolved_polyline(points, crs, base_name, output_dir):
    """Build and save a single-feature dissolved polyline from an ordered list of points."""
    if len(points) < 2:
        raise ValueError("Not enough points to build a track line (minimum 2 required).")

    line = LineString(points)
    length_m = Geod(ellps="WGS84").geometry_length(line)

    track_gdf = gpd.GeoDataFrame(
        {"DIVE": [base_name], "Length_m": [length_m]},
        geometry=[line],
        crs=crs
    )

    output_path = os.path.join(output_dir, f"Dissolved_{base_name}.shp")
    track_gdf.to_file(output_path)
    return output_path


def process_file(file_path, output_dir):
    """Dispatch to the appropriate loader based on file extension and dissolve to a polyline."""
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.shp':
        points, crs = load_points_from_shapefile(file_path)
    elif ext == '.csv':
        points, crs = load_points_from_csv(file_path)
    else:
        raise ValueError(f"Unsupported file type '{ext}'. Only .shp and .csv are supported.")

    return create_dissolved_polyline(points, crs, base_name, output_dir)


def select_and_convert_files():
    root = Tk()
    root.withdraw()  # No full GUI needed, just dialogs

    file_paths = filedialog.askopenfilenames(
        title="Select NavLog/Image Metadata shapefile(s) or CSV(s)",
        filetypes=[
            ("Shapefiles and CSVs", "*.shp *.csv"),
            ("Shapefiles", "*.shp"),
            ("CSV files", "*.csv"),
            ("All files", "*.*"),
        ]
    )
    if not file_paths:
        print("No files selected.")
        return

    output_dir = filedialog.askdirectory(title="Select Output Folder")
    if not output_dir:
        print("No output directory selected.")
        return

    results = []
    for file_path in file_paths:
        try:
            output_path = process_file(file_path, output_dir)
            print(f"Dissolved polyline shapefile created at: {output_path}")
            results.append(f"{os.path.basename(file_path)}: Success")
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            results.append(f"{os.path.basename(file_path)}: Error - {e}")

    messagebox.showinfo("Dissolve to Polyline - Results", "\n".join(results))


if __name__ == "__main__":
    select_and_convert_files()
