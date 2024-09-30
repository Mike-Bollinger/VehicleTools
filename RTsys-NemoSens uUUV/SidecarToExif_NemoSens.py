from PIL import Image
import piexif
import pandas as pd
import os
import tkinter as tk
from tkinter import filedialog


# Function to open a dialog box to select directories
def select_directories():
    root = tk.Tk()
    root.withdraw()  # Hide the root window

    # Ask for the input directory
    image_directory = filedialog.askdirectory(title="Select Input Directory with Images")
    if not image_directory:
        print("No input directory selected. Exiting.")
        return None, None

    # Ask for the output directory
    output_directory = filedialog.askdirectory(title="Select Output Directory")
    if not output_directory:
        print("No output directory selected. Exiting.")
        return None, None

    return image_directory, output_directory


# Function to process a single image
def process_image(image_file_path, csv_file_path, output_dir):
    # Load the CSV file and extract the first row of data
    df = pd.read_csv(csv_file_path, header=None)
    first_row = df.iloc[0]

    # Extracted data
    date_time = first_row[0] + " " + first_row[1]
    latitude = first_row[2]
    longitude = first_row[3]
    altitude = first_row[5]
    heading = first_row[8]

    # Convert latitude and longitude to the format used by EXIF
    def convert_to_dms(value):
        degrees = int(value)
        minutes = int((value - degrees) * 60)
        seconds = round((value - degrees - minutes / 60) * 3600 * 1000)
        return ((degrees, 1), (minutes, 1), (seconds, 1000))

    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: 'N' if latitude >= 0 else 'S',
        piexif.GPSIFD.GPSLatitude: convert_to_dms(abs(latitude)),
        piexif.GPSIFD.GPSLongitudeRef: 'E' if longitude >= 0 else 'W',
        piexif.GPSIFD.GPSLongitude: convert_to_dms(abs(longitude)),
        piexif.GPSIFD.GPSAltitude: (int(altitude), 1),
        piexif.GPSIFD.GPSAltitudeRef: 0 if altitude >= 0 else 1,
        piexif.GPSIFD.GPSImgDirection: (int(heading * 100), 100)
    }

    exif_dict = {"GPS": gps_ifd, "Exif": {piexif.ExifIFD.DateTimeOriginal: date_time.encode("utf-8")}}
    exif_bytes = piexif.dump(exif_dict)

    # Open the image and add the EXIF data
    image = Image.open(image_file_path)

    # Handle saving for JPEG and TIFF formats, preserving the original format
    output_image_path = os.path.join(output_dir, os.path.basename(image_file_path))
    if image.format == 'JPEG':
        image.save(output_image_path, "jpeg", exif=exif_bytes)
    elif image.format == 'TIFF':
        image.save(output_image_path, "tiff")
    else:
        print(f"Unsupported format for {image_file_path}. Skipping...")
        return

    print(f"Metadata added to {image_file_path}. Saved as {output_image_path}")


# Function to process all images in the directory
def process_directory(image_dir, output_dir):
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Iterate through all files in the directory
    for root, _, files in os.walk(image_dir):
        for file in files:
            if file.endswith(('.jpg', '.jpeg', '.tif', '.tiff')):
                image_file_path = os.path.join(root, file)
                csv_file_path = os.path.join(root, os.path.splitext(file)[0] + ".csv")

                if os.path.exists(csv_file_path):
                    process_image(image_file_path, csv_file_path, output_dir)
                else:
                    print(f"No matching CSV for {image_file_path}. Skipping...")


# Main execution
if __name__ == "__main__":
    image_directory, output_directory = select_directories()

    if image_directory and output_directory:
        process_directory(image_directory, output_directory)
