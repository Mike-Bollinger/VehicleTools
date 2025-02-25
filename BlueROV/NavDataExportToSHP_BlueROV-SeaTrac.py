import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString
import os
import tkinter as tk
from tkinter import filedialog, messagebox, Label, Button, Frame

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
    merged_df["Timestamp"] = merged_df["Timestamp"].astype(str)

    # Convert to GeoDataFrame
    gdf_points = gpd.GeoDataFrame(
        merged_df,
        geometry=[Point(xy) for xy in zip(merged_df["Longitude"], merged_df["Latitude"])],
        crs="EPSG:4326"
    )
    gdf_points.to_file(output_point_shapefile)

    # Create LineString geometry
    gdf_sorted = gdf_points.sort_values(by="Timestamp")
    if len(gdf_sorted) > 1:
        line_geometry = LineString([row.geometry for _, row in gdf_sorted.iterrows()])
        gdf_line = gpd.GeoDataFrame(pd.DataFrame([{ "Timestamp": base_name, "geometry": line_geometry }]), crs="EPSG:4326")
        gdf_line.to_file(output_line_shapefile)

    messagebox.showinfo("Success", f"Files saved:\n{output_csv}\n{output_point_shapefile}\n{output_line_shapefile}")

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
