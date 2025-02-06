"""
Title: Sidecar to Exif tag from NemoSens UUV
Author: Mike Bollinger
Date: 2025-02-06
Version: 1.2
Description:
    This script processes images and embeds EXIF metadata extracted from a CSV sidecar file.
    - Supports JPEG, JPG, TIFF, and PNG images (PNG does not support EXIF, so only copied).
    - Uses a Tkinter GUI to select input and output directories.
    - Overwrites existing images in the output folder.
    - Handles truncated images and errors gracefully, ensuring uninterrupted execution.
    - Prints a summary of skipped images at the end.
"""

from PIL import Image, ImageFile
import piexif
import pandas as pd
import os
import tkinter as tk
from tkinter import filedialog

# Enable loading of truncated images to avoid stopping on partial files
ImageFile.LOAD_TRUNCATED_IMAGES = True


def select_directories():
    """
    Opens a GUI dialog for the user to select input (image) and output (processed) directories.

    Returns:
        tuple: (image_directory, output_directory) or (None, None) if selection is canceled.
    """
    root = tk.Tk()
    root.withdraw()  # Hide the Tkinter root window

    image_directory = filedialog.askdirectory(title="Select Input Directory with Images")
    if not image_directory:
        print("No input directory selected. Exiting.")
        return None, None

    output_directory = filedialog.askdirectory(title="Select Output Directory")
    if not output_directory:
        print("No output directory selected. Exiting.")
        return None, None

    return image_directory, output_directory


def convert_to_dms(value):
    """
    Converts a decimal degree value into degrees, minutes, and seconds (DMS) format for EXIF.

    Args:
        value (float): Decimal degrees.

    Returns:
        tuple: ((degrees, 1), (minutes, 1), (seconds, 1000))
    """
    degrees = int(value)
    minutes = int((value - degrees) * 60)
    seconds = round((value - degrees - minutes / 60) * 3600 * 1000)
    return ((degrees, 1), (minutes, 1), (seconds, 1000))


def process_image(image_file_path, csv_file_path, output_dir, skipped_files):
    """
    Reads metadata from a CSV file and embeds it into an image's EXIF data.

    Args:
        image_file_path (str): Path to the image file.
        csv_file_path (str): Path to the associated CSV file.
        output_dir (str): Directory where processed images will be saved.
        skipped_files (list): List to store paths of skipped images.
    """
    try:
        # Load CSV and extract the first row of metadata
        df = pd.read_csv(csv_file_path, header=None)
        first_row = df.iloc[0]

        # Extract necessary metadata fields
        date_time = first_row[0] + " " + first_row[1]  # Combine date and time
        latitude = first_row[2]
        longitude = first_row[3]
        altitude = first_row[5]
        heading = first_row[8]

        # Prepare EXIF metadata
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

        # Open the image and ensure it is in an editable state
        image = Image.open(image_file_path)
        image = image.convert("RGB")  # Converts to RGB for better compatibility

        # Determine output file path
        output_image_path = os.path.join(output_dir, os.path.basename(image_file_path))

        # Process based on file extension (not relying on PIL's format detection)
        file_ext = os.path.splitext(image_file_path)[1].lower()

        if file_ext in ['.jpg', '.jpeg']:
            image.save(output_image_path, "jpeg", exif=exif_bytes)
        elif file_ext in ['.tif', '.tiff']:
            image.save(output_image_path, "tiff")  # TIFF does not support EXIF in the same way
        elif file_ext == '.png':
            image.save(output_image_path, "png")  # PNG does not support EXIF
            print(f"Warning: Metadata cannot be added to PNG {image_file_path}. Copying file only.")
        else:
            print(f"Unsupported format for {image_file_path}. Skipping...")
            skipped_files.append(image_file_path)
            return

        print(f"Metadata added to {image_file_path}. Saved as {output_image_path}")

    except Exception as e:
        print(f"Error processing {image_file_path}: {e}")
        skipped_files.append(image_file_path)


def process_directory(image_dir, output_dir):
    """
    Iterates through all images in the directory, matching them with CSV sidecar files and tagging metadata.

    Args:
        image_dir (str): Directory containing images.
        output_dir (str): Directory where processed images will be saved.
    """
    skipped_files = []  # List to track skipped files

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Process each image in the directory
    for root, _, files in os.walk(image_dir):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.tif', '.tiff', '.png')):
                image_file_path = os.path.join(root, file)
                csv_file_path = os.path.join(root, os.path.splitext(file)[0] + ".csv")

                if os.path.exists(csv_file_path):
                    process_image(image_file_path, csv_file_path, output_dir, skipped_files)
                else:
                    print(f"No matching CSV for {image_file_path}. Skipping...")
                    skipped_files.append(image_file_path)

    # Print a summary of skipped files
    if skipped_files:
        print("\n--- Skipped Files ---")
        for file in skipped_files:
            print(file)
    else:
        print("\nAll images processed successfully!")


# Main execution
if __name__ == "__main__":
    image_directory, output_directory = select_directories()

    if image_directory and output_directory:
        process_directory(image_directory, output_directory)
