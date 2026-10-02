"""
PHINS Standard v2 (NMEA-style) Navigation Data to Shapefile Converter
Author: Mike Bollinger
Date: 2026-09-30
Version: 1.0

Description:
    Converts PHINS Standard v2 navigation log files to CSV and ESRI shapefiles.
    Unlike the proprietary 'IX'-header binary format handled by
    Remus_PHINS_BinaryToSHP.py, real-world PHINS Standard v2 output from the
    iXBlue/Exail C7 INS is a sequence of NMEA-0183-style ASCII sentences
    (e.g. $HEHDT, $PIXSE,ATITUD, $PIXSE,POSITI) written to a ".bin" file with
    embedded null-byte padding between records.

    Sentence types parsed:
        $HEHDT               - Heading
        $PIXSE,ATITUD        - Roll, Pitch
        $PIXSE,POSITI        - Latitude, Longitude, Altitude
        $PIXSE,DEPIN_        - Depth
        $PIXSE,SPEED_        - East/North/Up speed
        $PIXSE,UTMWGS        - UTM zone, Easting, Northing, Altitude
        $PIXSE,LOGDVL        - Sound velocity, DVL distance to bottom
        $PIXSE,TIME__        - Time-of-day, used with the date encoded in the
                                filename to build an absolute UTC timestamp

USAGE:
    Run the script and use the Tkinter GUI to select the PHINS Standard v2
    log file(s) and an output folder:
        python Remus_PHINS_StdV2_ToSHP.py

INPUTS:
    - One or more PHINS Standard v2 log files, named like
      "<MISSION>_<DIVE>_<VEHICLE>_phins_std_YYYY-MM-DD_HH-MM.bin".

OUTPUTS:
    A tab-separated CSV of parsed navigation records and a dissolved
    polyline shapefile (track line) per input file, written to the chosen
    output folder. In addition, this script attempts to recreate two of the
    vehicle's native "EXPORTS" text products directly from the PHINS stream:
        BATHY.txt      - latitude, longitude, depth, altitude, heading,
                         pitch, roll (full fidelity)
        PHINS_INS.txt  - partial: lat/lon/depth/heave/velocity/heading/
                         pitch/roll are filled from the PHINS sentences; the
                         vehicle fault/status words, std-dev/QC fields, and
                         DVL calibration fields are NOT present in the PHINS
                         NMEA stream and are left blank.
    ADCP.txt, CTD.txt (conductivity/temperature/salinity), and GPSDATA.txt
    (GPS satellite constellation detail) are produced by separate
    instruments/receivers on the vehicle and are not recoverable from the
    PHINS file alone. Console output includes a tally of every sentence tag
    seen in the file so additional products can be added if more sentence
    types are discovered in a given log.
"""

import csv
import datetime as dt
import os
import re
import sys
import traceback

import arcpy
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.ttk import Progressbar

# Enable overwrite for ArcPy outputs
arcpy.env.overwriteOutput = True


def _verify_nmea_checksum(row_str):
    """Validate the trailing *HH checksum on an NMEA-style sentence."""
    if not row_str.startswith("$") or "*" not in row_str:
        return False
    data, checksum_str = row_str[1:].split("*", 1)
    calc = 0
    for ch in data:
        calc ^= ord(ch)
    try:
        expected = int(checksum_str[:2], 16)
    except ValueError:
        return False
    return calc == expected


def _parse_phins_date(filename):
    """Extract the YYYYMMDD collection date encoded in the filename."""
    base = os.path.basename(filename)
    match = re.search(r"phinsdata_(\d{8})", base)
    if match:
        return match.group(1)
    match = re.search(r"_(\d{4}-\d{2}-\d{2})_\d{2}-\d{2}\.bin", base)
    if match:
        return match.group(1).replace("-", "")
    raise ValueError(f"Could not extract date from PHINS filename: {filename}")


def extract_dive_num(filename):
    """Pull a 'DIVE###' identifier out of the filename, falling back to the first token."""
    base = os.path.basename(filename)
    match = re.search(r"(DIVE\d+)", base, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return base.split("_")[0]


def parse_phins_bytes(raw_bytes, filename):
    """Parse raw PHINS Standard v2 bytes into per-sentence-type DataFrames."""
    date = _parse_phins_date(filename)

    frames = {
        "DEPIN_": {"Depth": [], "Heave": [], "Time_REF": []},
        "ATITUD": {"Roll": [], "Pitch": [], "Time_REF": []},
        "HEHDT": {"Heading": [], "Time_REF": []},
        "UTMWGS": {"LatZone": [], "LonZone": [], "Easting": [], "Northing": [], "Altitude": [], "Time_REF": []},
        "SPEED_": {"EastSpeed": [], "NorthSpeed": [], "UpSpeed": [], "Velocity": [], "Time_REF": []},
        "POSITI": {"Latitude": [], "Longitude": [], "Altitude": [], "Time_REF": []},
        "LOGDVL": {"SoundVelocity": [], "Compensation": [], "DVL_Distance_2btm": [], "Time_REF": []},
    }

    current_time = ""
    time_last = 0.0
    decoded = raw_bytes.replace(b"\x00", b"").decode("latin-1")

    # Tally every sentence tag seen so unrecognized message types (e.g. GPS,
    # CTD, ADCP) can be discovered and reported even though they aren't parsed.
    sentence_tally = {}

    message_count = 0
    for row in csv.reader(decoded.splitlines()):
        row_str = ",".join(row)
        if not _verify_nmea_checksum(row_str):
            continue
        row = [col.split("*")[0] for col in row]
        if len(row) < 2:
            continue

        identifier = row[0]
        tag = f"{identifier},{row[1]}" if identifier == "$PIXSE" and len(row) >= 2 else identifier
        sentence_tally[tag] = sentence_tally.get(tag, 0) + 1

        if identifier == "$PIXSE":
            message = row[1]
            if message == "TIME__" and len(row) >= 3:
                try:
                    t = float(row[2])
                    if t == 0:
                        continue
                    if t < time_last and time_last > 235900:
                        day = dt.datetime.strptime(date, "%Y%m%d") + dt.timedelta(days=1)
                        date = day.strftime("%Y%m%d")
                    time_last = t
                    current_time = date + " " + row[2]
                except ValueError:
                    pass
            elif message == "DEPIN_" and len(row) >= 4:
                try:
                    frames["DEPIN_"]["Depth"].append(float(row[2]))
                    frames["DEPIN_"]["Heave"].append(float(row[3]))
                    frames["DEPIN_"]["Time_REF"].append(current_time)
                except ValueError:
                    pass
            elif message == "ATITUD" and len(row) >= 4:
                try:
                    frames["ATITUD"]["Roll"].append(float(row[2]))
                    frames["ATITUD"]["Pitch"].append(float(row[3]))
                    frames["ATITUD"]["Time_REF"].append(current_time)
                except ValueError:
                    pass
            elif message == "UTMWGS" and len(row) >= 7:
                try:
                    frames["UTMWGS"]["LatZone"].append(row[2])
                    frames["UTMWGS"]["LonZone"].append(int(row[3]))
                    frames["UTMWGS"]["Easting"].append(float(row[4]))
                    frames["UTMWGS"]["Northing"].append(float(row[5]))
                    frames["UTMWGS"]["Altitude"].append(float(row[6]))
                    frames["UTMWGS"]["Time_REF"].append(current_time)
                except ValueError:
                    pass
            elif message == "SPEED_" and len(row) >= 5:
                try:
                    east, north, up = float(row[2]), float(row[3]), float(row[4])
                    frames["SPEED_"]["EastSpeed"].append(east)
                    frames["SPEED_"]["NorthSpeed"].append(north)
                    frames["SPEED_"]["UpSpeed"].append(up)
                    frames["SPEED_"]["Velocity"].append((east**2 + north**2) ** 0.5)
                    frames["SPEED_"]["Time_REF"].append(current_time)
                except ValueError:
                    pass
            elif message == "POSITI" and len(row) >= 5:
                try:
                    frames["POSITI"]["Latitude"].append(float(row[2]))
                    frames["POSITI"]["Longitude"].append(float(row[3]))
                    frames["POSITI"]["Altitude"].append(float(row[4]))
                    frames["POSITI"]["Time_REF"].append(current_time)
                except ValueError:
                    pass
            elif message == "LOGDVL" and len(row) >= 5:
                try:
                    sound_velocity = float(row[2])
                    if sound_velocity > 0:
                        frames["LOGDVL"]["SoundVelocity"].append(sound_velocity)
                        frames["LOGDVL"]["Compensation"].append(float(row[3]))
                        frames["LOGDVL"]["DVL_Distance_2btm"].append(float(row[4]))
                        frames["LOGDVL"]["Time_REF"].append(current_time)
                except ValueError:
                    pass
        elif identifier == "$HEHDT" and len(row) >= 2:
            try:
                frames["HEHDT"]["Heading"].append(float(row[1]))
                frames["HEHDT"]["Time_REF"].append(current_time)
            except ValueError:
                pass

        message_count += 1
        if message_count % 200000 == 0:
            print(f"  Processed {message_count} sentences...")

    print(f"  Total valid sentences processed: {message_count}")

    result = {}
    for key, data in frames.items():
        df = pd.DataFrame(data)
        if "Time_REF" in df.columns:
            df["Date_Time"] = pd.to_datetime(
                df["Time_REF"], format="%Y%m%d %H%M%S.%f", errors="coerce", utc=True
            )
            df = df.drop(columns=["Time_REF"])
        result[key] = df
        print(f"  {key}: {len(df)} record(s)")

    print("  Sentence tag tally (top 20):")
    for tag, count in sorted(sentence_tally.items(), key=lambda kv: kv[1], reverse=True)[:20]:
        print(f"    {tag}: {count}")

    return result, sentence_tally


def _to_time_seconds(series):
    times = pd.to_datetime(series, utc=True, errors="coerce")
    valid = times.notna()
    return times[valid].astype("int64").to_numpy(dtype=np.float64) / 1e9


def _interp_from_frame(df, value_col, target_times):
    """Linearly interpolate a value column from a nav frame onto target epoch times."""
    if df.empty or value_col not in df.columns or "Date_Time" not in df.columns:
        return np.full(len(target_times), np.nan, dtype=np.float64)

    clean = df[["Date_Time", value_col]].dropna().copy()
    if clean.empty:
        return np.full(len(target_times), np.nan, dtype=np.float64)

    source_times = pd.to_datetime(clean["Date_Time"], utc=True, errors="coerce")
    clean = clean.loc[source_times.notna()].copy()
    if clean.empty:
        return np.full(len(target_times), np.nan, dtype=np.float64)

    source_times = pd.to_datetime(clean["Date_Time"], utc=True).astype("int64").to_numpy(dtype=np.float64) / 1e9
    source_values = pd.to_numeric(clean[value_col], errors="coerce").to_numpy(dtype=np.float64)
    valid = np.isfinite(source_times) & np.isfinite(source_values)
    if valid.sum() < 2:
        return np.full(len(target_times), np.nan, dtype=np.float64)

    source_times = source_times[valid]
    source_values = source_values[valid]
    order = np.argsort(source_times)
    source_times = source_times[order]
    source_values = source_values[order]
    return np.interp(target_times, source_times, source_values)


def build_bathy_dataframe(frames, positi, target_seconds):
    """Recreate BATHY.txt (latitude, longitude, depth, altitude, heading, pitch, roll) from the PHINS stream."""
    out = pd.DataFrame()
    out["latitude"] = positi["Latitude"].to_numpy()
    out["longitude"] = positi["Longitude"].to_numpy()
    out["depth"] = _interp_from_frame(frames["DEPIN_"], "Depth", target_seconds)
    out["altitude"] = _interp_from_frame(frames["LOGDVL"], "DVL_Distance_2btm", target_seconds)
    out["heading"] = _interp_from_frame(frames["HEHDT"], "Heading", target_seconds)
    out["pitch"] = _interp_from_frame(frames["ATITUD"], "Pitch", target_seconds)
    out["roll"] = _interp_from_frame(frames["ATITUD"], "Roll", target_seconds)
    return out.fillna({"depth": 0.0, "altitude": 0.0, "heading": 0.0, "pitch": 0.0, "roll": 0.0})


def build_phins_ins_dataframe(frames, positi, target_seconds):
    """
    Best-effort, partial recreation of PHINS_INS.txt.

    Vehicle fault/status words, std-dev/QC fields, range/distance estimates,
    and DVL calibration fields are produced by the vehicle's own data logger
    (not present in the PHINS NMEA stream) and are left blank (NaN). The
    SPEED_ sentence field order (mapped here to north/east/down) is a
    best-effort guess and has not been verified byte-for-byte against this format.
    """
    out = pd.DataFrame()
    out["latitude"] = positi["Latitude"].to_numpy()
    out["longitude"] = positi["Longitude"].to_numpy()
    # True vehicle "mission_msecs" is assigned by the vehicle data logger and
    # is not recoverable from the PHINS file alone.
    out["time"] = np.nan
    out["depth"] = _interp_from_frame(frames["DEPIN_"], "Depth", target_seconds)
    for col in ("faults", "Algorithm_Status_lo32", "Algorithm_Status_hi32",
                "System_Status_lo32", "Sensor_Status_lo32", "Sensor_Status_hi32"):
        out[col] = np.nan
    out["phins_time"] = target_seconds
    out["phins_lat"] = out["latitude"]
    out["phins_lon"] = out["longitude"]
    out["phins_depth"] = out["depth"]
    out["phins_heave"] = _interp_from_frame(frames["DEPIN_"], "Heave", target_seconds)
    out["phins_vel_north"] = _interp_from_frame(frames["SPEED_"], "NorthSpeed", target_seconds)
    out["phins_vel_east"] = _interp_from_frame(frames["SPEED_"], "EastSpeed", target_seconds)
    out["phins_vel_down"] = -_interp_from_frame(frames["SPEED_"], "UpSpeed", target_seconds)
    out["phins_heading"] = _interp_from_frame(frames["HEHDT"], "Heading", target_seconds)
    out["phins_pitch"] = _interp_from_frame(frames["ATITUD"], "Pitch", target_seconds)
    out["phins_roll"] = _interp_from_frame(frames["ATITUD"], "Roll", target_seconds)
    for col in ("phins_head_rate", "phins_pitch_rate", "phins_roll_rate",
                "phins_std_dev_lat", "phins_std_dev_lon", "phins_std_dev_north_vel",
                "phins_std_dev_east_vel", "phins_std_dev_down_vel", "phins_std_dev_roll",
                "phins_std_dev_pitch", "phins_std_dev_north_heading",
                "phins_est_range_err", "phins_est_dist_traveled",
                "dvl_cal_pitch", "dvl_cal_hdg_misalignment", "dvl_cal_scale_factor"):
        out[col] = np.nan
    # Reproduce the original export's columns exactly, including its duplicated
    # "Algorithm_Status_hi32" header.
    return out[[
        "latitude", "longitude", "time", "depth", "faults",
        "Algorithm_Status_lo32", "Algorithm_Status_hi32", "System_Status_lo32",
        "Algorithm_Status_hi32", "Sensor_Status_lo32", "Sensor_Status_hi32",
        "phins_time", "phins_lat", "phins_lon", "phins_depth", "phins_heave",
        "phins_vel_north", "phins_vel_east", "phins_vel_down", "phins_heading",
        "phins_pitch", "phins_roll", "phins_head_rate", "phins_pitch_rate",
        "phins_roll_rate", "phins_std_dev_lat", "phins_std_dev_lon",
        "phins_std_dev_north_vel", "phins_std_dev_east_vel", "phins_std_dev_down_vel",
        "phins_std_dev_roll", "phins_std_dev_pitch", "phins_std_dev_north_heading",
        "phins_est_range_err", "phins_est_dist_traveled", "dvl_cal_pitch",
        "dvl_cal_hdg_misalignment", "dvl_cal_scale_factor",
    ]]


def process_phins_file(phins_file):
    """
    Process a PHINS Standard v2 log file and return formatted navigation data.

    Args:
        phins_file (str): Path to PHINS Standard v2 log file

    Returns:
        tuple: (formatted_data, bathy_data, phins_ins_data, dive_num, main_folder)
    """
    print(f"Parsing PHINS Standard v2 file: {os.path.basename(phins_file)}")

    dive_num = extract_dive_num(phins_file)
    main_folder = os.path.dirname(phins_file)

    with open(phins_file, "rb") as f:
        raw_bytes = f.read()
    print(f"  File size: {len(raw_bytes)} bytes")

    frames, sentence_tally = parse_phins_bytes(raw_bytes, phins_file)

    positi = frames["POSITI"].dropna(subset=["Latitude", "Longitude", "Date_Time"]).copy()
    if positi.empty:
        raise ValueError("No $PIXSE,POSITI sentences with valid position/time found in file")

    # PHINS reports west longitudes as 0-360 azimuth; normalize back to -180..180
    positi["Longitude"] = positi["Longitude"].apply(lambda lon: lon - 360 if lon > 180 else lon)

    positi = positi.sort_values("Date_Time").drop_duplicates(subset=["Date_Time"]).reset_index(drop=True)
    target_seconds = _to_time_seconds(positi["Date_Time"])

    bathy_data = build_bathy_dataframe(frames, positi, target_seconds)
    phins_ins_data = build_phins_ins_dataframe(frames, positi, target_seconds)

    output_data = pd.DataFrame()
    output_data["mission_time"] = target_seconds.astype("int64")
    output_data["heading"] = _interp_from_frame(frames["HEHDT"], "Heading", target_seconds)
    output_data["pitch"] = _interp_from_frame(frames["ATITUD"], "Pitch", target_seconds)
    output_data["roll"] = _interp_from_frame(frames["ATITUD"], "Roll", target_seconds)
    output_data["latitude"] = positi["Latitude"].to_numpy()
    output_data["longitude"] = positi["Longitude"].to_numpy()
    # Depth convention: negative for underwater
    output_data["depth"] = -_interp_from_frame(frames["DEPIN_"], "Depth", target_seconds)
    output_data["heading_rate"] = 0.0
    output_data["altitude"] = _interp_from_frame(frames["LOGDVL"], "DVL_Distance_2btm", target_seconds)

    output_data = output_data.fillna({"heading": 0.0, "pitch": 0.0, "roll": 0.0, "depth": 0.0, "altitude": 0.0})

    # Remove any rows with NaN or invalid values in critical columns
    output_data = output_data.dropna(subset=["latitude", "longitude"])

    # Additional validation: remove rows with invalid coordinate ranges
    output_data = output_data[
        (output_data["latitude"] >= -90) & (output_data["latitude"] <= 90) &
        (output_data["longitude"] >= -180) & (output_data["longitude"] <= 180)
    ]

    # Remove duplicate consecutive points to clean up the track
    output_data = output_data.drop_duplicates(subset=["latitude", "longitude"], keep="first")

    if len(output_data) < 2:
        raise ValueError(f"Not enough valid navigation points (minimum 2 required, got {len(output_data)})")

    print(f"Formatted {len(output_data)} navigation points")

    return output_data, bathy_data, phins_ins_data, dive_num, main_folder


def create_shapefile(coord_data, dive_num, output_folder):
    """
    Create a shapefile from the provided coordinate data

    Args:
        coord_data (pd.DataFrame): Navigation data with latitude/longitude
        dive_num (str): Dive/mission identifier
        output_folder (str): Output directory path

    Returns:
        str: Path to created shapefile
    """
    try:
        print(f"Creating shapefile for {dive_num}...")

        # Create array to store points
        array = arcpy.Array()

        # Set output file names
        fc = f"{dive_num}.shp"
        shapefile_w_path = os.path.join(output_folder, fc)

        # Set spatial reference to WGS84
        spatRef = arcpy.SpatialReference(4326)

        # Create empty polyline feature class
        arcpy.CreateFeatureclass_management(
            out_path=output_folder,
            out_name=fc,
            geometry_type='POLYLINE',
            spatial_reference=spatRef
        )

        # Insert points into shapefile as polylines
        cursor = arcpy.da.InsertCursor(shapefile_w_path, ["SHAPE@"])

        # Make sure coord_data has at least 2 points
        if len(coord_data) < 2:
            raise ValueError("Not enough coordinate points to create a line (minimum 2 required)")

        for i in range(len(coord_data) - 1):
            try:
                x = float(coord_data.iloc[i]['longitude'])
                y = float(coord_data.iloc[i]['latitude'])
                point = arcpy.Point(x, y)
                array.add(point)

                x1 = float(coord_data.iloc[i+1]['longitude'])
                y1 = float(coord_data.iloc[i+1]['latitude'])
                point1 = arcpy.Point(x1, y1)
                array.add(point1)

                myline = arcpy.Polyline(array, spatRef)
                array.removeAll()
                cursor.insertRow([myline])
            except Exception as e:
                print(f"  Warning: Skipping point at index {i}: {str(e)}")
                continue

        del cursor

        # Repair geometry
        print(f"  Repairing geometry...")
        arcpy.management.RepairGeometry(shapefile_w_path, "DELETE_NULL", "ESRI")

        # Dissolve the shapefile
        print(f"  Dissolving polylines...")
        dissolved_shpfile = os.path.join(output_folder, f"Dissolved_{fc}")
        arcpy.management.Dissolve(
            shapefile_w_path,
            dissolved_shpfile,
            "",
            "",
            "MULTI_PART",
            "DISSOLVE_LINES"
        )

        # Delete the original shapefile
        arcpy.Delete_management(shapefile_w_path)

        # Repair dissolved geometry
        print(f"  Repairing dissolved geometry...")
        arcpy.management.RepairGeometry(dissolved_shpfile, "DELETE_NULL", "ESRI")

        # Add DIVE field and calculate
        print(f"  Adding DIVE field...")
        arcpy.management.AddField(dissolved_shpfile, "DIVE", "TEXT")
        arcpy.management.CalculateField(
            dissolved_shpfile,
            "DIVE",
            f"'{dive_num}'",
            "PYTHON3",
            '',
            "TEXT",
            "NO_ENFORCE_DOMAINS"
        )

        # Add Length_m field and calculate
        print(f"  Calculating track length...")
        arcpy.management.AddField(
            dissolved_shpfile,
            "Length_m",
            "DOUBLE",
            8,
            "",
            "",
            "Length_m",
            "NULLABLE",
            "NON_REQUIRED"
        )

        try:
            arcpy.CalculateGeometryAttributes_management(
                dissolved_shpfile,
                [["Length_m", "LENGTH_GEODESIC"]],
                "METERS"
            )
        except Exception as e:
            print(f"  Warning: Could not calculate geodesic length: {str(e)}")
            print(f"  Calculating length manually using geodesic distance...")
            try:
                # Calculate length manually by summing geodesic distances between vertices
                with arcpy.da.UpdateCursor(dissolved_shpfile, ["SHAPE@", "Length_m"]) as cursor:
                    for row in cursor:
                        geom = row[0]
                        if geom:
                            total_length = 0
                            for part in geom:
                                points = list(part)
                                for i in range(len(points) - 1):
                                    p1 = points[i]
                                    p2 = points[i + 1]
                                    if p1 and p2:
                                        # Create point geometries with spatial reference
                                        pt1 = arcpy.PointGeometry(arcpy.Point(p1.X, p1.Y), spatRef)
                                        pt2 = arcpy.PointGeometry(arcpy.Point(p2.X, p2.Y), spatRef)
                                        # Calculate geodesic distance
                                        segment_length = pt1.distanceTo(pt2)
                                        total_length += segment_length
                            row[1] = total_length
                            cursor.updateRow(row)
                print(f"  Manual length calculation successful")
            except Exception as e2:
                print(f"  Warning: Could not calculate length manually: {str(e2)}")
                # Leave Length_m as NULL rather than failing

        print(f"  Shapefile created: {dissolved_shpfile}")

        return dissolved_shpfile

    except Exception as e:
        error_msg = f"Error creating shapefile for {dive_num}: {str(e)}"
        raise Exception(error_msg)


def process_files(file_list, output_folder=None):
    """Process each PHINS file in the list and update the progress bar"""
    results = []
    progress_step = 100 / len(file_list) if file_list else 0

    for i, file_path in enumerate(file_list):
        try:
            # Update status text
            dive_name = extract_dive_num(file_path)
            status_var.set(f"Processing {dive_name}... ({i+1}/{len(file_list)})")
            root.update_idletasks()

            # Process the PHINS file
            formatted_data, bathy_data, phins_ins_data, dive_num, source_folder = process_phins_file(file_path)

            # Determine output folder
            if output_folder:
                destination_folder = output_folder
            else:
                destination_folder = os.path.join(source_folder, "NavProducts")

            # Create destination folder if it doesn't exist
            if not os.path.exists(destination_folder):
                os.makedirs(destination_folder)

            # Save CSV
            csv_filename = os.path.join(
                destination_folder,
                f"{dive_num}_PHINS_StdV2_Nav_Formatted.csv"
            )
            formatted_data.to_csv(csv_filename, index=False, sep="\t")
            print(f"CSV saved: {csv_filename}")

            # Recreate the vehicle's BATHY.txt and (partial) PHINS_INS.txt exports
            bathy_filename = os.path.join(destination_folder, f"{dive_num}_BATHY.txt")
            bathy_data.to_csv(bathy_filename, index=False)
            print(f"BATHY.txt recreated: {bathy_filename}")

            phins_ins_filename = os.path.join(destination_folder, f"{dive_num}_PHINS_INS.txt")
            phins_ins_data.to_csv(phins_ins_filename, index=False)
            print(f"PHINS_INS.txt recreated (partial): {phins_ins_filename}")

            # Update status
            status_var.set(f"Creating shapefile for {dive_num}...")
            root.update_idletasks()

            # Create shapefile
            shapefile_path = create_shapefile(formatted_data, dive_num, destination_folder)

            # Update results
            results.append({
                "dive_num": dive_num,
                "csv_file": csv_filename,
                "bathy_file": bathy_filename,
                "phins_ins_file": phins_ins_filename,
                "shapefile": shapefile_path,
                "status": "Success"
            })

            # Update progress bar
            progress["value"] = (i + 1) * progress_step
            root.update_idletasks()

        except Exception as e:
            # Get detailed error information
            exc_type, exc_value, exc_traceback = sys.exc_info()
            error_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
            error_message = ''.join(error_details)

            # Print detailed error to console for debugging
            print(f"Error processing {file_path}:")
            print(error_message)

            # Add to results with simplified error message
            results.append({
                "dive_num": extract_dive_num(file_path),
                "status": f"Error: {str(e)}"
            })

            # Update status
            status_var.set(f"Error processing {os.path.basename(file_path)}")
            root.update_idletasks()

    return results


# GUI Functions
def select_output_folder():
    """Allow user to select a common output folder for all processed files"""
    folder = filedialog.askdirectory(
        title="Select Output Folder for All Processed Files"
    )

    if not folder:
        return None

    output_folder_var.set(folder)
    return folder


def browse_file(file_var):
    """Open file dialog to select a file for a specific row"""
    file_path = filedialog.askopenfilename(
        title="Select PHINS Standard v2 File",
        filetypes=[("PHINS Log Files", "*.bin *.phins *.dat *.log"), ("All Files", "*.*")]
    )

    if file_path:
        file_var.set(file_path)
        update_buttons_state()


def remove_file_entry(row, file_var):
    """Remove a file entry row"""
    row.destroy()
    if file_var in file_vars:
        file_vars.remove(file_var)
    update_buttons_state()
    update_scroll_region()


def update_scroll_region():
    """Update the canvas scroll region after changes"""
    file_entries_frame.update_idletasks()
    canvas.configure(scrollregion=canvas.bbox("all"))


def update_buttons_state():
    """Update the state of buttons based on file selection"""
    valid_files = [v.get() for v in file_vars if v.get().strip()]
    file_count = len(valid_files)

    file_count_var.set(f"{file_count} file(s) selected")

    if file_count > 0:
        process_button.config(state="normal")
        select_output_button.config(state="normal")
    else:
        process_button.config(state="disabled")
        select_output_button.config(state="normal" if file_vars else "disabled")


def start_processing():
    """Start processing the selected files"""
    valid_files = [v.get() for v in file_vars if v.get().strip()]

    if not valid_files:
        messagebox.showerror("Error", "No files selected!")
        return

    output_folder = output_folder_var.get()
    if output_folder == "Default: NavProducts folder in source directory":
        output_folder = None

    add_file_button.config(state="disabled")
    select_output_button.config(state="disabled")
    process_button.config(state="disabled")

    progress["value"] = 0
    root.update_idletasks()

    try:
        results = process_files(valid_files, output_folder)
        status_var.set("Processing complete!")
        show_results(results)
    except Exception as e:
        messagebox.showerror("Processing Error", f"An unexpected error occurred: {str(e)}")
        status_var.set("Processing failed. See error message.")
    finally:
        add_file_button.config(state="normal")
        select_output_button.config(state="normal")
        process_button.config(state="normal")


def show_results(results):
    """Display the processing results in a new window"""
    result_window = tk.Toplevel(root)
    result_window.title("Processing Results")
    result_window.geometry("600x400")

    result_text = tk.Text(result_window, wrap=tk.WORD)
    result_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    scrollbar = tk.Scrollbar(result_window)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    result_text.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=result_text.yview)

    result_text.insert(tk.END, "Processing Results:\n\n")
    for result in results:
        if result["status"] == "Success":
            result_text.insert(tk.END, f"Dive: {result['dive_num']}\n")
            result_text.insert(tk.END, f"CSV File: {result['csv_file']}\n")
            result_text.insert(tk.END, f"BATHY.txt: {result['bathy_file']}\n")
            result_text.insert(tk.END, f"PHINS_INS.txt (partial): {result['phins_ins_file']}\n")
            result_text.insert(tk.END, f"Shapefile: {result['shapefile']}\n")
            result_text.insert(tk.END, f"Status: {result['status']}\n\n")
        else:
            result_text.insert(tk.END, f"Dive: {result['dive_num']}\n")
            result_text.insert(tk.END, f"Status: {result['status']}\n\n")

    result_text.config(state=tk.DISABLED)


def add_file_entry():
    """Add a new file entry row to the file selection frame"""
    file_row = tk.Frame(file_entries_frame)
    file_row.pack(fill=tk.X, pady=2)

    file_var = tk.StringVar()
    file_vars.append(file_var)

    entry = tk.Entry(file_row, textvariable=file_var, width=50)
    entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

    browse_btn = tk.Button(
        file_row,
        text="Browse",
        command=lambda v=file_var: browse_file(v)
    )
    browse_btn.pack(side=tk.LEFT, padx=5)

    remove_btn = tk.Button(
        file_row,
        text="Remove",
        command=lambda row=file_row, v=file_var: remove_file_entry(row, v)
    )
    remove_btn.pack(side=tk.LEFT, padx=5)

    update_scroll_region()

    return file_row, file_var


# Main GUI setup
if __name__ == "__main__":
    root = tk.Tk()
    root.title("PHINS Standard v2 (NMEA) to Shapefile Converter")
    root.geometry("700x500")

    status_var = tk.StringVar()
    status_var.set("Add PHINS Standard v2 log files to begin")
    file_count_var = tk.StringVar()
    file_count_var.set("No files selected")
    output_folder_var = tk.StringVar()
    output_folder_var.set("Default: NavProducts folder in source directory")
    file_vars = []

    # Create frames
    top_frame = tk.Frame(root, padx=10, pady=10)
    top_frame.pack(fill=tk.X)

    middle_frame = tk.Frame(root, padx=10, pady=5)
    middle_frame.pack(fill=tk.BOTH, expand=True)

    bottom_frame = tk.Frame(root, padx=10, pady=10)
    bottom_frame.pack(fill=tk.X)

    # File entries container with scrollbar
    file_entries_container = tk.Frame(middle_frame)
    file_entries_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    canvas = tk.Canvas(file_entries_container, height=200)
    scrollbar = tk.Scrollbar(file_entries_container, orient="vertical", command=canvas.yview)
    file_entries_frame = tk.LabelFrame(canvas, text="PHINS Standard v2 Files", padx=5, pady=5)

    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    canvas_frame = canvas.create_window((0, 0), window=file_entries_frame, anchor="nw",
                                       width=canvas.winfo_reqwidth())

    def on_frame_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfig(canvas_frame, width=canvas.winfo_width())

    file_entries_frame.bind("<Configure>", on_frame_configure)

    def on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    canvas.bind_all("<MouseWheel>", on_mousewheel)

    # Output folder selection
    output_frame = tk.Frame(middle_frame, padx=5, pady=5)
    output_frame.pack(fill=tk.X, padx=5, pady=5)

    output_label = tk.Label(output_frame, text="Output Folder:")
    output_label.pack(side=tk.LEFT, padx=5)

    output_path_label = tk.Label(output_frame, textvariable=output_folder_var, wraplength=450)
    output_path_label.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

    # Top frame widgets
    add_file_button = tk.Button(
        top_frame,
        text="Add PHINS Standard v2 File",
        command=add_file_entry,
        width=22
    )
    add_file_button.pack(side=tk.LEFT, padx=5)

    file_count_label = tk.Label(top_frame, textvariable=file_count_var)
    file_count_label.pack(side=tk.LEFT, padx=10)

    # Bottom frame widgets
    control_frame = tk.Frame(bottom_frame)
    control_frame.pack(fill=tk.X)

    process_button = tk.Button(
        control_frame,
        text="Process Files",
        command=start_processing,
        width=20,
        state="disabled"
    )
    process_button.pack(side=tk.LEFT, padx=5)

    select_output_button = tk.Button(
        output_frame,
        text="Change",
        command=lambda: output_folder_var.set(select_output_folder() or output_folder_var.get()),
        state="disabled",
        width=10
    )
    select_output_button.pack(side=tk.RIGHT, padx=5)

    status_label = tk.Label(bottom_frame, textvariable=status_var)
    status_label.pack(anchor="w", pady=5)

    progress = Progressbar(bottom_frame, orient="horizontal", length=680, mode="determinate")
    progress.pack(fill=tk.X, pady=5)

    note_label = tk.Label(
        bottom_frame,
        text="This tool converts PHINS Standard v2 NMEA-style log files to CSV and shapefile formats.\n"
             "For the proprietary 'IX'-header binary format, use Remus_PHINS_BinaryToSHP.py instead.",
        justify=tk.LEFT,
        wraplength=680
    )
    note_label.pack(anchor="w", pady=5)

    # Add first file entry
    add_file_entry()

    root.mainloop()
