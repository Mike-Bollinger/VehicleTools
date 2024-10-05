import os
import pandas as pd
import geopandas as gpd
from tkinter import Tk, filedialog, Button, Label, Entry, StringVar, Frame, Text, Scrollbar, END
from glob import glob
import time
import gc  # Garbage collection
import threading  # Import threading module

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
        if row.isna().any():
            if temp_row is not None:
                temp_row.update(row)
                fixed_rows.append(temp_row)
                temp_row = None
        else:
            if temp_row is not None:
                fixed_rows.append(temp_row)
            temp_row = row.copy()

    if temp_row is not None:
        fixed_rows.append(temp_row)

    return pd.DataFrame(fixed_rows)

# Function to browse for a folder and update the corresponding Entry widget
def browse_folder(entry_widget):
    folder_path = filedialog.askdirectory(title="Select Folder")
    entry_widget.set(folder_path)

# Function to update progress in the GUI
def update_progress(text_widget, message):
    text_widget.insert(END, message + '\n')
    text_widget.see(END)
    text_widget.update_idletasks()

# Function to handle the concatenation and shapefile creation
def concatenate_csvs_to_csv_and_shapefile(input_folders, output_folder, progress_display=None):
    start_time = time.time()

    if not input_folders or not any(input_folders):
        update_progress(progress_display, "No input folders selected.") if progress_display else print("No input folders selected.")
        return

    if not output_folder:
        update_progress(progress_display, "No output folder selected.") if progress_display else print("No output folder selected.")
        return

    for input_folder in input_folders:
        if not input_folder:
            continue

        parent_folder_name = os.path.basename(os.path.dirname(os.path.normpath(input_folder)))

        output_csv = os.path.join(output_folder, f"{parent_folder_name}_imagemetadata.csv")
        output_shapefile = os.path.join(output_folder, f"{parent_folder_name}_imagemetadata.shp")

        csv_files = glob(os.path.join(input_folder, "*.csv"))

        if not csv_files:
            message = f"[{time.time() - start_time:.2f} seconds] No CSV files found in {input_folder}."
            update_progress(progress_display, message) if progress_display else print(message)
            continue

        message = f"[{time.time() - start_time:.2f} seconds] Found {len(csv_files)} CSV files in {input_folder}. Starting concatenation..."
        update_progress(progress_display, message) if progress_display else print(message)

        with open(output_csv, 'w') as f_out:
            header_written = False

            for file in csv_files:
                filename = os.path.splitext(os.path.basename(file))[0]

                img_extensions = ['.jpg', '.jpeg', '.tiff', '.tif']
                image_path = None
                for ext in img_extensions:
                    potential_img = os.path.join(input_folder, filename + ext)
                    if os.path.exists(potential_img):
                        image_path = potential_img
                        break

                if not image_path:
                    continue

                for chunk in pd.read_csv(file, chunksize=2000, header=None, names=CSV_HEADERS, low_memory=True):
                    chunk = fix_split_rows(chunk)

                    chunk['source_file'] = filename
                    chunk['image_path'] = image_path

                    if not header_written:
                        chunk.to_csv(f_out, index=False, header=True, mode='a', lineterminator='\n')
                        header_written = True
                    else:
                        chunk.to_csv(f_out, index=False, header=False, mode='a', lineterminator='\n')

                gc.collect()

                message = f"[{time.time() - start_time:.2f} seconds] Processed file: {file}"
                update_progress(progress_display, message) if progress_display else print(message)

        concatenated_df = pd.read_csv(output_csv, low_memory=True)

        if 'Latitude' not in concatenated_df.columns or 'Longitude' not in concatenated_df.columns:
            message = f"[{time.time() - start_time:.2f} seconds] Missing Latitude or Longitude for {input_folder}."
            update_progress(progress_display, message) if progress_display else print(message)
            continue

        message = f"[{time.time() - start_time:.2f} seconds] Latitude and Longitude found. Creating shapefile for {input_folder}..."
        update_progress(progress_display, message) if progress_display else print(message)

        concatenated_gdf = gpd.GeoDataFrame(
            concatenated_df,
            geometry=gpd.points_from_xy(concatenated_df['Longitude'], concatenated_df['Latitude']),
            crs="EPSG:4326"
        )

        shapefile_start_time = time.time()
        concatenated_gdf.to_file(output_shapefile, driver='ESRI Shapefile')

        message = f"[{time.time() - shapefile_start_time:.2f} seconds] Shapefile saved to: {output_shapefile}"
        update_progress(progress_display, message) if progress_display else print(message)

    total_time = f"[{time.time() - start_time:.2f} seconds] Total processing time."
    update_progress(progress_display, total_time) if progress_display else print(total_time)

# Function to dynamically add new input folder rows in the GUI
def add_folder_entry(frame, folder_vars):
    row = len(folder_vars)
    folder_var = StringVar()
    folder_vars.append(folder_var)

    Label(frame, text=f"Input Folder {row + 1}").grid(row=row, column=0, sticky='w')
    Entry(frame, textvariable=folder_var, width=50).grid(row=row, column=1, padx=(0, 5))
    Button(frame, text="Browse", command=lambda: browse_folder(folder_var)).grid(row=row, column=2)

# Function to run the concatenation in a separate thread
def run_concatenation(folder_vars, output_var, progress_display):
    concatenate_csvs_to_csv_and_shapefile(
        [folder_var.get() for folder_var in folder_vars], output_var.get(), progress_display
    )

# Function to create the GUI
def create_gui():
    root = Tk()
    root.title("CSV to Shapefile Tool")

    folder_vars = []

    # Create main frame
    main_frame = Frame(root)
    main_frame.grid(row=0, column=0, padx=10, pady=10)

    # Add first input folder
    add_folder_entry(main_frame, folder_vars)

    # Button to add more input folders
    Button(root, text="Add Input Folder", command=lambda: add_folder_entry(main_frame, folder_vars)).grid(row=1, column=0, pady=(5, 0))

    # Output folder
    output_var = StringVar()
    Label(root, text="Output Folder").grid(row=2, column=0, sticky='w', pady=(5, 0))
    Entry(root, textvariable=output_var, width=50).grid(row=2, column=0, columnspan=2, padx=(0, 5), pady=(5, 0))
    Button(root, text="Browse", command=lambda: browse_folder(output_var)).grid(row=2, column=1, pady=(5, 0))

    # Textbox for displaying progress
    progress_display = Text(root, height=20, width=80)
    progress_display.grid(row=4, column=0, columnspan=3, pady=(10, 0))

    # Scrollbar for the progress display
    scrollbar = Scrollbar(root, command=progress_display.yview)
    progress_display.config(yscrollcommand=scrollbar.set)
    scrollbar.grid(row=4, column=3, sticky='ns')

    # Run button
    Button(root, text="Run", command=lambda: threading.Thread(target=run_concatenation, args=(folder_vars, output_var, progress_display)).start()).grid(row=3, column=0, pady=(10, 0))

    root.mainloop()

if __name__ == "__main__":
    create_gui()
