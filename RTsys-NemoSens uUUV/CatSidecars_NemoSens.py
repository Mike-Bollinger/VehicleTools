import os
import pandas as pd
import geopandas as gpd
from tkinter import Tk, filedialog
from glob import glob
import time
import gc  # Garbage collection

# Define the headers for the CSVs
CSV_HEADERS = [
    "Date", "Time", "Latitude", "Longitude", "Depth", "Altitude", "Pitch",
    "Roll", "Heading", "Timestamp Source", "Light Mode", "Exposure",
    "Gain", "Focal Length", "Aperture"
]


# Function to merge rows when a split across multiple lines is detected
def fix_split_rows(df):
    fixed_rows = []
    temp_row = None

    for _, row in df.iterrows():
        # If the row contains NaN values, it likely belongs to the previous row
        if row.isna().any():
            if temp_row is not None:
                # Merge the current row with the previous incomplete row
                temp_row.update(row)
                fixed_rows.append(temp_row)
                temp_row = None
        else:
            # If we encounter a normal row, we check if temp_row is set from a previous split
            if temp_row is not None:
                fixed_rows.append(temp_row)
            temp_row = row.copy()

    # Append any remaining row that wasn't merged
    if temp_row is not None:
        fixed_rows.append(temp_row)

    # Convert back to a DataFrame
    return pd.DataFrame(fixed_rows)


def concatenate_csvs_to_csv_and_shapefile():
    start_time = time.time()  # Start the timer

    # Hide Tkinter root window
    root = Tk()
    root.withdraw()

    # Open dialog to select input folder
    input_folder = filedialog.askdirectory(title="Select Input Folder Containing CSVs")
    if not input_folder:
        print("No folder selected.")
        return

    print(f"[{time.time() - start_time:.2f} seconds] Selected input folder: {input_folder}")

    # Open dialog to select output folder
    output_folder = filedialog.askdirectory(title="Select Output Folder")
    if not output_folder:
        print("No folder selected.")
        return

    print(f"[{time.time() - start_time:.2f} seconds] Selected output folder: {output_folder}")

    # Create the output filenames based on the input folder name
    folder_name = os.path.basename(os.path.dirname(os.path.normpath(input_folder)))

    output_csv = os.path.join(output_folder, f"{folder_name}_imagemetadata.csv")
    output_shapefile = os.path.join(output_folder, f"{folder_name}_imagemetadata.shp")

    # Find all CSV files in the input folder
    csv_files = glob(os.path.join(input_folder, "*.csv"))

    if not csv_files:
        print(f"[{time.time() - start_time:.2f} seconds] No CSV files found in the selected folder.")
        return

    print(f"[{time.time() - start_time:.2f} seconds] Found {len(csv_files)} CSV files. Starting concatenation...")

    # Create a temporary file for storing intermediate results
    with open(output_csv, 'w') as f_out:
        header_written = False

        for file in csv_files:
            # Extract filename without extension
            filename = os.path.splitext(os.path.basename(file))[0]
            print(f"[{time.time() - start_time:.2f} seconds] Processing file: {file}")

            # Read CSV in chunks, apply header and handle two-line cases
            for chunk in pd.read_csv(file, chunksize=10000, header=None, names=CSV_HEADERS, low_memory=True):
                # Detect and merge split rows
                chunk = fix_split_rows(chunk)

                # Add the filename as a new column
                chunk['source_file'] = filename

                # Write the header only once
                if not header_written:
                    chunk.to_csv(f_out, index=False, header=True, mode='a', lineterminator='\n')

                    header_written = True
                else:
                    chunk.to_csv(f_out, index=False, header=False, mode='a', lineterminator='\n')


            # Free up memory after each file
            gc.collect()

    print(f"[{time.time() - start_time:.2f} seconds] CSV concatenation completed.")

    # Read the concatenated CSV for creating the shapefile
    concatenated_df = pd.read_csv(output_csv, low_memory=True)

    # Check for necessary columns for spatial data (e.g., 'Latitude' and 'Longitude')
    if 'Latitude' not in concatenated_df.columns or 'Longitude' not in concatenated_df.columns:
        print(
            f"[{time.time() - start_time:.2f} seconds] Missing Latitude or Longitude columns for shapefile creation. Shapefile will not be created.")
        return

    print(f"[{time.time() - start_time:.2f} seconds] Latitude and Longitude columns found. Creating shapefile...")

    # Convert the DataFrame to a GeoDataFrame with geometry
    shapefile_start_time = time.time()
    concatenated_gdf = gpd.GeoDataFrame(
        concatenated_df,
        geometry=gpd.points_from_xy(concatenated_df['Longitude'], concatenated_df['Latitude']),
        crs="EPSG:4326"  # Set the coordinate system
    )

    # Save GeoDataFrame as a shapefile
    concatenated_gdf.to_file(output_shapefile, driver='ESRI Shapefile')
    print(f"[{time.time() - shapefile_start_time:.2f} seconds] Shapefile saved to: {output_shapefile}")

    # Final processing time
    print(f"[{time.time() - start_time:.2f} seconds] Total processing time.")


if __name__ == "__main__":
    concatenate_csvs_to_csv_and_shapefile()

