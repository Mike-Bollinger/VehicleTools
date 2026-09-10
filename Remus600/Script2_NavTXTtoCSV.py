"""
Title: Remus Navigation TXT to CSV Converter (Script2, Python version)
Author: Mike Bollinger
Last Updated: 2025-03-04

FUNCTION:
    Companion Python port of Script2_CompleteNav_OR2401.R. Reads a single
    Remus navigation .txt log, converts DMS Lon/Lat to decimal degrees, and
    writes a formatted CSV ready for Script3_CreateAUVTrackLines_MB.py.

USAGE:
    Run the script and select the navigation file via the file dialog:
        python Script2_NavTXTtoCSV.py

INPUTS:
    - A Remus navigation .txt log file (comma-delimited, header + units +
      data rows) selected via the GUI file dialog.

OUTPUTS:
    A formatted navigation CSV ("<dive>_Veh_Data_Formatted.csv") written
    alongside/relative to the input file, with decimal-degree coordinates.
"""

import os
import pandas as pd
from datetime import datetime
from tkinter import Tk
from tkinter.filedialog import askopenfilename

# Open a dialog to select the navigation file
Tk().withdraw()  # Hide the root Tkinter window
nav_file = askopenfilename(
    title="Select the Navigation File",
    filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
)

# Check if a file was selected
if not nav_file:
    print("No file selected. Exiting...")
    exit()

# Extract the main folder and dive number from the selected file path
main_folder = os.path.dirname(os.path.dirname(os.path.dirname(nav_file)))
dive_num = os.path.basename(nav_file).split("_")[0]

# Read the navigation file
all_data = pd.read_csv(nav_file, sep=",", header=0, skiprows=1)

# Set column names
all_data.columns = [
    "Time", "Date", "LonLat", "Altitude", "Bathymetry", "Depth_vehicle",
    "Heading", "Headingrate", "NeilBrownSoundSpeed", "Pitch", "Pitchrate",
    "Roll", "Rollrate", "Velocity", "x"
]

# Trim whitespace from the Time column
all_data["Time"] = all_data["Time"].str.strip()

# Trim whitespace from the Date column
all_data["Date"] = all_data["Date"].str.strip()

# Convert Date to datetime format
all_data["Date_mod"] = pd.to_datetime(all_data["Date"], format="%m/%d/%Y")


# Pad Time with leading zero if needed
all_data["time_mod"] = all_data["Time"].apply(lambda t: t if len(t) == 12 else f"0{t}")

# Create combined timestamp column
all_data["Tmstamp"] = all_data["Date_mod"].astype(str) + " " + all_data["time_mod"]
all_data["Tmstamp2"] = pd.to_datetime(all_data["Tmstamp"], format="%Y-%m-%d %H:%M:%S.%f")

# Sort by timestamp
all_data = all_data.sort_values(by="Tmstamp2")

# Split LonLat into Latitude and Longitude
all_data["Latitude"] = all_data["LonLat"].str.split(" ").str[1]
all_data["Longitude"] = all_data["LonLat"].str.split(" ").str[3]

# Convert Latitude and Longitude to decimal degrees
all_data["Latitude_dd"] = (
    all_data["Latitude"].str.split("N").str[0].astype(float) +
    all_data["Latitude"].str.split("N").str[1].astype(float) / 60
)
all_data["Longitude_dd"] = (
    -1 * (
        all_data["Longitude"].str.split("W").str[0].astype(float) +
        all_data["Longitude"].str.split("W").str[1].astype(float) / 60
    )
)

# Select relevant columns
all_data = all_data[[
    "Date_mod", "time_mod", "Tmstamp2", "Latitude_dd", "Longitude_dd",
    "Altitude", "Bathymetry", "Depth_vehicle", "Heading", "Headingrate",
    "Pitch", "Pitchrate", "Roll", "Rollrate", "Velocity"
]]

# Rename columns
all_data.columns = [
    "date", "time", "timestamp", "latitude", "longitude",
    "altitude", "bathymetry", "depth", "heading", "heading_rate",
    "pitch", "pitch_rate", "roll", "roll_rate", "velocity"
]

# Adjust heading_rate
all_data["heading_rate"] *= -1

# Create destination folder
destination_folder = os.path.join(main_folder, "NavProducts")
if not os.path.exists(destination_folder):
    os.makedirs(destination_folder)
    print(f"Created Directory: {destination_folder}")
else:
    print("Directory Exists")

# Save the formatted data
filename = os.path.join(
    destination_folder,
    os.path.splitext(os.path.basename(nav_file))[0] + "_Formatted.csv"
)
all_data.to_csv(filename, index=False, sep=",", quotechar='"')
print(f"Completed {dive_num}")
