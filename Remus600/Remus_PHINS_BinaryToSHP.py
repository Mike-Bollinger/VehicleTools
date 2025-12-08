"""
PHINS Binary Data to Shapefile Converter
Author: Mike Bollinger
Date: 2025-12-08
Version: 1.0

Description:
    This script converts PHINS Standard v2 binary navigation files to CSV and ESRI shapefiles.
    The PHINS (Photonics Inertial Navigation System) from iXBlue/Exail outputs navigation data
    in a binary format that needs to be parsed and converted for GIS analysis.
    
    PHINS Standard v2 Format:
    - Binary format with specific message structures
    - Contains INS (Inertial Navigation System) data
    - Includes position, attitude, velocity, and status information
    
References:
    - iXBlue/Exail PHINS C7 Inertial Navigation System
    - PHINS Standard Protocol v2
"""

import os
import struct
import pandas as pd
import arcpy
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.ttk import Progressbar
import traceback
import sys

# Enable overwrite for ArcPy outputs
arcpy.env.overwriteOutput = True


class PHINSParser:
    """Parser for iXBlue PHINS binary format"""
    
    # iXBlue PHINS message structure starts with 'IX' (0x49 0x58)
    PHINS_HEADER = b'IX'
    
    # Common PHINS message IDs (these vary by configuration)
    # We'll extract data fields regardless of specific message ID
    
    def __init__(self):
        self.data_records = []
        self.current_record = {}
        
    def parse_file(self, binary_file_path):
        """
        Parse a PHINS binary file and extract navigation data.
        
        Args:
            binary_file_path (str): Path to the PHINS binary file
            
        Returns:
            pd.DataFrame: Parsed navigation data
        """
        print(f"Parsing PHINS binary file: {os.path.basename(binary_file_path)}")
        
        try:
            with open(binary_file_path, 'rb') as f:
                file_data = f.read()
            
            print(f"  File size: {len(file_data)} bytes")
            
            # Check if file might be text-based (NMEA or ASCII)
            try:
                text_sample = file_data[:500].decode('ascii', errors='ignore')
                if '$' in text_sample or 'PHINS' in text_sample.upper():
                    print(f"  WARNING: File appears to contain ASCII/NMEA data!")
                    print(f"  First 200 chars: {text_sample[:200]}")
                    raise ValueError("File appears to be ASCII/NMEA format, not binary. Please use a different parser or convert to binary format.")
            except:
                pass
            
            # Print first 100 bytes for diagnostic purposes
            print(f"  First 100 bytes (hex): {file_data[:100].hex()}")
            print(f"  First 100 bytes (ASCII): {repr(file_data[:100])}")
            
            # Look for common start markers
            start_markers = {}
            for i in range(min(10000, len(file_data))):
                byte = file_data[i]
                if byte in [0x02, 0x24, 0x01, 0xFF, 0xFE]:  # Common markers: STX, $, SOH, etc.
                    start_markers[byte] = start_markers.get(byte, 0) + 1
            
            if start_markers:
                print(f"  Common start bytes found: {[(hex(k), v) for k, v in sorted(start_markers.items(), key=lambda x: x[1], reverse=True)]}")
                
            # Parse the binary data - iXBlue PHINS format
            offset = 0
            message_count = 0
            
            while offset < len(file_data) - 10:
                # Look for 'IX' header
                if file_data[offset:offset+2] != self.PHINS_HEADER:
                    offset += 1
                    continue
                    
                try:
                    # iXBlue PHINS message structure:
                    # 'IX' (2 bytes) + Protocol version (1 byte) + Message ID (1 byte) 
                    # + Navigation data descriptor (2 bytes) + Data size (2 bytes)
                    # + Payload (variable) + Checksum (2 bytes)
                    
                    protocol_version = struct.unpack('B', file_data[offset+2:offset+3])[0]
                    msg_id = struct.unpack('B', file_data[offset+3:offset+4])[0]
                    nav_descriptor = struct.unpack('<H', file_data[offset+4:offset+6])[0]
                    data_size = struct.unpack('<H', file_data[offset+6:offset+8])[0]
                    
                    # Validate message size
                    if offset + 8 + data_size + 2 > len(file_data):
                        offset += 1
                        continue
                    
                    # Check reasonable size (PHINS messages typically < 1000 bytes)
                    if data_size > 1000 or data_size == 0:
                        offset += 1
                        continue
                    
                    # Extract payload
                    payload = file_data[offset+8:offset+8+data_size]
                    
                    # Parse the message
                    self._parse_phins_message(msg_id, nav_descriptor, payload, message_count)
                    
                    message_count += 1
                    if message_count % 1000 == 0:
                        print(f"  Processed {message_count} messages...")
                    
                    # Move to next message
                    offset += 8 + data_size + 2
                    
                except struct.error:
                    offset += 1
                    continue
                except Exception as e:
                    if message_count < 10:  # Only show first few errors
                        print(f"  Warning at offset {offset}: {str(e)}")
                    offset += 1
                    continue
            
            print(f"  Total messages processed: {message_count}")
            print(f"  Navigation records extracted: {len(self.data_records)}")
            
            # Convert to DataFrame
            if self.data_records:
                df = pd.DataFrame(self.data_records)
                return df
            else:
                raise ValueError("No navigation data extracted from file")
                
        except Exception as e:
            raise Exception(f"Error parsing PHINS file: {str(e)}")
    
    def _parse_phins_message(self, msg_id, nav_descriptor, payload, msg_count):
        """Parse iXBlue PHINS message based on navigation descriptor"""
        try:
            # The nav_descriptor indicates which data fields are present
            # Common fields in PHINS messages (offset varies by descriptor):
            # - Timestamp (4 bytes, unsigned int, microseconds)
            # - Attitude (heading, roll, pitch - 3x4 bytes floats)
            # - Position (lat, lon, alt - 3x8 bytes doubles)
            # - Velocity (3x4 bytes floats)
            # - Status fields
            
            if len(payload) < 16:
                return
            
            offset = 0
            record = {}
            
            # Try to extract timestamp (usually first 4 bytes)
            if len(payload) >= 4:
                timestamp_us = struct.unpack('<I', payload[offset:offset+4])[0]
                # Convert microseconds to seconds (Unix epoch)
                record['timestamp'] = timestamp_us / 1000000.0
                offset += 4
            
            # Try to extract attitude data (heading, roll, pitch)
            # These are typically floats (4 bytes each) in radians or degrees
            if len(payload) >= offset + 12:
                try:
                    heading = struct.unpack('<f', payload[offset:offset+4])[0]
                    roll = struct.unpack('<f', payload[offset+4:offset+8])[0]
                    pitch = struct.unpack('<f', payload[offset+8:offset+12])[0]
                    
                    # Convert from radians to degrees if needed
                    if abs(heading) <= 6.3:  # Likely radians (max ~2*pi)
                        heading = heading * 180.0 / 3.14159265359
                    
                    # Validate reasonable values
                    if -360 <= heading <= 360 and -90 <= roll <= 90 and -90 <= pitch <= 90:
                        record['heading'] = heading % 360  # Normalize to 0-360
                        record['roll'] = roll
                        record['pitch'] = pitch
                    offset += 12
                except:
                    pass
            
            # Try to extract position data (lat, lon, altitude)
            # These are typically doubles (8 bytes each)
            if len(payload) >= offset + 24:
                try:
                    latitude = struct.unpack('<d', payload[offset:offset+8])[0]
                    longitude = struct.unpack('<d', payload[offset+8:offset+16])[0]
                    altitude = struct.unpack('<d', payload[offset+16:offset+24])[0]
                    
                    # Validate coordinates (reasonable Earth bounds)
                    if -90 <= latitude <= 90 and -180 <= longitude <= 180:
                        record['latitude'] = latitude
                        record['longitude'] = longitude
                        record['altitude'] = altitude
                        offset += 24
                except:
                    pass
            
            # Alternative: try position at different offset if not found
            if 'latitude' not in record and len(payload) >= 36:
                for test_offset in [16, 20, 28, 32]:
                    if len(payload) >= test_offset + 24:
                        try:
                            lat = struct.unpack('<d', payload[test_offset:test_offset+8])[0]
                            lon = struct.unpack('<d', payload[test_offset+8:test_offset+16])[0]
                            alt = struct.unpack('<d', payload[test_offset+16:test_offset+24])[0]
                            
                            if -90 <= lat <= 90 and -180 <= lon <= 180 and abs(alt) < 10000:
                                record['latitude'] = lat
                                record['longitude'] = lon
                                record['altitude'] = alt
                                break
                        except:
                            continue
            
            # Only save record if we have valid position data
            if 'latitude' in record and 'longitude' in record:
                # Merge with current record
                self.current_record.update(record)
                
                # Save complete record
                if 'timestamp' in self.current_record:
                    self.data_records.append(self.current_record.copy())
                    
        except Exception as e:
            # Silently skip parsing errors
            pass


def process_phins_file(phins_file):
    """
    Process a PHINS binary file and return formatted navigation data
    
    Args:
        phins_file (str): Path to PHINS binary file
        
    Returns:
        tuple: (formatted_data, dive_num, main_folder)
    """
    try:
        # Extract dive/mission number from filename
        dive_num = os.path.basename(phins_file).split("_")[0]
        main_folder = os.path.dirname(phins_file)
        
        # Parse the binary file
        parser = PHINSParser()
        nav_data = parser.parse_file(phins_file)
        
        if nav_data is None or len(nav_data) == 0:
            raise ValueError("No navigation data could be extracted from the file")
        
        print(f"Extracted {len(nav_data)} navigation records")
        
        # Convert timestamp to datetime
        if 'timestamp' in nav_data.columns:
            nav_data['datetime'] = pd.to_datetime(nav_data['timestamp'], unit='s', utc=True)
            nav_data['mission_time'] = nav_data['timestamp'].astype(int)
        else:
            # If no timestamp, create sequential time
            nav_data['mission_time'] = range(len(nav_data))
        
        # Ensure required columns exist
        required_cols = ['latitude', 'longitude']
        for col in required_cols:
            if col not in nav_data.columns:
                raise ValueError(f"Required column '{col}' not found in parsed data")
        
        # Create output dataframe with MSN005 format
        output_data = pd.DataFrame()
        
        # mission_time (epoch time in UTC)
        output_data['mission_time'] = nav_data.get('mission_time', range(len(nav_data)))
        
        # heading
        output_data['heading'] = nav_data.get('heading', 0.0)
        
        # latitude and longitude
        output_data['latitude'] = nav_data['latitude']
        output_data['longitude'] = nav_data['longitude']
        
        # depth (negative for underwater)
        output_data['depth'] = nav_data.get('depth', 0.0)
        
        # heading_rate (if available, otherwise 0)
        output_data['heading_rate'] = 0.0
        
        # altitude (altitude above seafloor)
        output_data['altitude'] = nav_data.get('altitude', 0.0)
        
        # Remove any rows with NaN or invalid values in critical columns
        output_data = output_data.dropna(subset=['latitude', 'longitude'])
        
        # Additional validation: remove rows with invalid coordinate ranges
        output_data = output_data[
            (output_data['latitude'] >= -90) & (output_data['latitude'] <= 90) &
            (output_data['longitude'] >= -180) & (output_data['longitude'] <= 180)
        ]
        
        # Remove duplicate consecutive points to clean up the track
        output_data = output_data.drop_duplicates(subset=['latitude', 'longitude'], keep='first')
        
        if len(output_data) < 2:
            raise ValueError(f"Not enough valid navigation points (minimum 2 required, got {len(output_data)})")
        
        print(f"Formatted {len(output_data)} navigation points")
        
        return output_data, dive_num, main_folder
        
    except Exception as e:
        error_msg = f"Error processing file {os.path.basename(phins_file)}: {str(e)}"
        raise Exception(error_msg)


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
            print(f"  Attempting planar length calculation instead...")
            try:
                # Try planar length as fallback
                arcpy.CalculateGeometryAttributes_management(
                    dissolved_shpfile,
                    [["Length_m", "LENGTH"]],
                    "METERS"
                )
            except Exception as e2:
                print(f"  Warning: Could not calculate length: {str(e2)}")
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
            dive_name = os.path.basename(file_path).split("_")[0]
            status_var.set(f"Processing {dive_name}... ({i+1}/{len(file_list)})")
            root.update_idletasks()
            
            # Process the PHINS file
            formatted_data, dive_num, source_folder = process_phins_file(file_path)
            
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
                f"{dive_num}_PHINS_Nav_Formatted.csv"
            )
            formatted_data.to_csv(csv_filename, index=False, sep="\t")
            print(f"CSV saved: {csv_filename}")
            
            # Update status
            status_var.set(f"Creating shapefile for {dive_num}...")
            root.update_idletasks()
            
            # Create shapefile
            shapefile_path = create_shapefile(formatted_data, dive_num, destination_folder)
            
            # Update results
            results.append({
                "dive_num": dive_num,
                "csv_file": csv_filename,
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
                "dive_num": os.path.basename(file_path).split("_")[0],
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
        title="Select PHINS Binary File",
        filetypes=[("Binary Files", "*.bin *.phins *.dat *.log"), ("All Files", "*.*")]
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
    root.title("PHINS Binary to Shapefile Converter")
    root.geometry("700x500")
    
    status_var = tk.StringVar()
    status_var.set("Add PHINS binary files to begin")
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
    file_entries_frame = tk.LabelFrame(canvas, text="PHINS Binary Files", padx=5, pady=5)
    
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
        text="Add PHINS Binary File", 
        command=add_file_entry,
        width=20
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
        text="This tool converts PHINS binary navigation files to CSV and shapefile formats.\n"
             "PHINS Standard v2 protocol from iXBlue/Exail C7 Inertial Navigation System.",
        justify=tk.LEFT,
        wraplength=680
    )
    note_label.pack(anchor="w", pady=5)
    
    # Add first file entry
    add_file_entry()
    
    root.mainloop()
