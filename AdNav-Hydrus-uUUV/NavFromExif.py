import os
from tkinter import Tk, filedialog, Label, Button, Entry
from PIL import Image, ExifTags
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point


# Function to convert GPS coordinates from EXIF format to degrees
def convert_to_degrees(value):
    d = float(value[0])
    m = float(value[1])
    s = float(value[2])
    return d + (m / 60.0) + (s / 3600.0)


# Function to safely convert EXIF rational values to float
def convert_exif_value(value):
    if isinstance(value, (tuple, list)):
        return float(value[0]) / float(value[1])
    elif isinstance(value, int) or isinstance(value, float):
        return float(value)
    else:
        return None


# Function to extract EXIF data including Altitude (used as Depth)
def extract_exif(image_path):
    img = Image.open(image_path)
    exif_data = img._getexif() or {}

    # Make EXIF data more readable
    exif = {ExifTags.TAGS.get(tag): value for tag, value in exif_data.items() if tag in ExifTags.TAGS}
    gps_info = exif.get('GPSInfo', {})

    # Extracting date, time, latitude, longitude, and altitude from EXIF
    date_time = exif.get('DateTime', 'Unknown')

    if gps_info:
        gps_latitude = convert_to_degrees(gps_info[2]) if 2 in gps_info else 'Unknown'
        gps_longitude = convert_to_degrees(gps_info[4]) if 4 in gps_info else 'Unknown'
        gps_altitude = convert_exif_value(gps_info.get(6, 'Unknown'))  # Convert altitude EXIF value
        if gps_info[1] == 'S': gps_latitude = -gps_latitude
        if gps_info[3] == 'W': gps_longitude = -gps_longitude
    else:
        gps_latitude = 'Unknown'
        gps_longitude = 'Unknown'
        gps_altitude = 'Unknown'

    # Split date and time if available
    date, time = date_time.split(" ") if date_time != 'Unknown' else ('Unknown', 'Unknown')

    return date, time, gps_latitude, gps_longitude, gps_altitude


# Function to process images and extract metadata including Depth
def process_images(input_folder, output_folder):
    image_paths = [os.path.join(input_folder, f) for f in os.listdir(input_folder) if
                   f.lower().endswith(('jpg', 'jpeg', 'tiff'))]

    if not image_paths:
        print("No images found in the selected folder.")
        return

    # Initialize empty list for metadata
    metadata_list = []

    # Loop through images and extract metadata
    for image_path in image_paths:
        date, time, lat, lon, depth = extract_exif(image_path)
        filename = os.path.basename(image_path)
        file_path = os.path.abspath(image_path)  # Use file path for linking in ArcPro
        print(
            f"Processing {filename}: Date={date}, Time={time}, Latitude={lat}, Longitude={lon}, Depth={depth}, Path={file_path}")
        metadata_list.append(
            {'Image': filename, 'Date': date, 'Time': time, 'Latitude': lat, 'Longitude': lon, 'Depth': depth,
             'FilePath': file_path})

    # Convert to pandas DataFrame
    df = pd.DataFrame(metadata_list)

    # Filter out images without valid GPS coordinates
    df = df[(df['Latitude'] != 'Unknown') & (df['Longitude'] != 'Unknown')]

    if df.empty:
        print("No valid GPS data found in the images.")
        return

    # Convert DataFrame to GeoDataFrame with geometry column for shapefile export
    gdf = gpd.GeoDataFrame(df, geometry=[Point(float(lon), float(lat)) for lon, lat in
                                         zip(df['Longitude'], df['Latitude'])])
    gdf['Depth'] = df['Depth']  # Add the Depth column as plain text/number
    gdf.crs = "EPSG:4326"  # Set coordinate reference system

    # Get the input folder name for naming the output shapefile
    folder_name = os.path.basename(input_folder.rstrip("/\\"))
    shapefile_name = f"{folder_name}_ImageMetadata.shp"
    output_path = os.path.join(output_folder, shapefile_name)

    # Save the GeoDataFrame to a shapefile
    gdf.to_file(output_path, driver='ESRI Shapefile')
    print(f"Shapefile saved at: {output_path}")


# Function to browse for input folder
def browse_input_folder():
    input_folder = filedialog.askdirectory(title="Select Image Folder")
    input_entry.delete(0, 'end')
    input_entry.insert(0, input_folder)


# Function to browse for output folder
def browse_output_folder():
    output_folder = filedialog.askdirectory(title="Select Output Folder")
    output_entry.delete(0, 'end')
    output_entry.insert(0, output_folder)


# Function to run the process after selecting folders
def run_process():
    input_folder = input_entry.get()
    output_folder = output_entry.get()

    if not input_folder or not output_folder:
        print("Please select both input and output folders.")
        return

    # Process images and export the shapefile
    process_images(input_folder, output_folder)


# Create a simple GUI with folder selection and a Start button
def create_gui():
    global input_entry, output_entry

    root = Tk()
    root.title("Image Metadata to Shapefile")

    # Input folder selection
    Label(root, text="Input Folder:").grid(row=0, column=0, padx=10, pady=5)
    input_entry = Entry(root, width=50)
    input_entry.grid(row=0, column=1, padx=10, pady=5)
    Button(root, text="Browse", command=browse_input_folder).grid(row=0, column=2, padx=10, pady=5)

    # Output folder selection
    Label(root, text="Output Folder:").grid(row=1, column=0, padx=10, pady=5)
    output_entry = Entry(root, width=50)
    output_entry.grid(row=1, column=1, padx=10, pady=5)
    Button(root, text="Browse", command=browse_output_folder).grid(row=1, column=2, padx=10, pady=5)

    # Start button to initiate the process
    Button(root, text="Start", command=run_process).grid(row=2, column=1, pady=20)

    # Run the Tkinter main loop
    root.mainloop()


# Run the GUI function to start the app
if __name__ == "__main__":
    create_gui()
