import os
import pandas as pd
import arcpy
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.ttk import Progressbar, Scrollbar
import traceback
import sys
import re

# Enable overwrite for ArcPy outputs
arcpy.env.overwriteOutput = 1

def process_nav_file(nav_file):
    """Process a navigation text file and return the formatted data"""
    try:
        # Extract the dive number from the filename
        dive_num = os.path.basename(nav_file).split("_")[0]
        
        # Allow user to specify output location instead of assuming parent structure
        main_folder = os.path.dirname(nav_file)
        
        # Read the navigation file - use actual headers from file
        try:
            with open(nav_file, 'r') as f:
                lines = f.readlines()
                if len(lines) < 3:
                    raise ValueError(f"File {nav_file} has fewer than 3 lines")
                    
                # First line is column headers, second line is units, data starts at line 3
                header_line = lines[0].strip()
                column_names = [col.strip() for col in header_line.split(',')]
                
            # Read the file using actual headers and skip the units line
            all_data = pd.read_csv(nav_file, sep=",", header=0, skiprows=1, names=column_names)
            
        except Exception as e:
            raise ValueError(f"Error reading file: {str(e)}")
        
        # Print available columns for debugging
        print(f"Available columns: {list(all_data.columns)}")
        
        # Safety check for required columns - find actual column names
        time_col = None
        date_col = None
        lonlat_col = None
        
        # Find Time column (look for variations)
        for col in all_data.columns:
            if 'time' in col.lower():
                time_col = col
                break
        
        # Find Date column  
        for col in all_data.columns:
            if 'date' in col.lower():
                date_col = col
                break
                
        # Find LonLat column
        for col in all_data.columns:
            if 'lon' in col.lower() and 'lat' in col.lower():
                lonlat_col = col
                break
        
        if not time_col:
            raise ValueError("Could not find Time column in data")
        if not date_col:
            raise ValueError("Could not find Date column in data") 
        if not lonlat_col:
            raise ValueError("Could not find Lon/Lat column in data")
            
        print(f"Using columns - Time: '{time_col}', Date: '{date_col}', LonLat: '{lonlat_col}'")
        
        # Trim whitespace from columns
        all_data[time_col] = all_data[time_col].str.strip()
        all_data[date_col] = all_data[date_col].str.strip()
        
        # Convert Date to datetime format
        all_data["Date_mod"] = pd.to_datetime(all_data[date_col], format="%m/%d/%Y")
        
        # Pad Time with leading zero if needed
        all_data["time_mod"] = all_data[time_col].apply(lambda t: t if len(t.strip()) == 12 else f"0{t.strip()}")
        
        # Create combined timestamp column (assuming UTC timezone)
        all_data["Tmstamp"] = all_data["Date_mod"].astype(str) + " " + all_data["time_mod"]
        all_data["Tmstamp2"] = pd.to_datetime(all_data["Tmstamp"], format="%Y-%m-%d %H:%M:%S.%f", utc=True)
        
        # Convert to epoch time (Unix timestamp)
        all_data["mission_time"] = all_data["Tmstamp2"].astype('int64') // 10**9
        
        # Sort by timestamp
        all_data = all_data.sort_values(by="Tmstamp2")
        
        # Split LonLat into Latitude and Longitude with robust handling of leading whitespace
        try:
            # Print sample of LonLat data for debugging
            print(f"Sample LonLat format: '{all_data[lonlat_col].iloc[0]}'")
            
            # Strip leading and trailing whitespace first
            all_data[lonlat_col] = all_data[lonlat_col].str.strip()
            
            # Try different splitting methods
            # Method 1: Split by multiple spaces (2 or more)
            lat_lon_split = all_data[lonlat_col].str.split(r'\s{2,}', expand=True)
            
            if len(lat_lon_split.columns) >= 2:
                all_data["Latitude"] = lat_lon_split[0]
                all_data["Longitude"] = lat_lon_split[1]
            else:
                # Method 2: Use regex to find the specific coordinate patterns
                
                def extract_coords(lonlat_str):
                    if pd.isna(lonlat_str) or not lonlat_str.strip():
                        return None, None
                    
                    # Look for patterns like 28N05.66080 and 91W58.01316
                    coords = re.findall(r'(\d+[NS]\d+\.\d+)\s+(\d+[WE]\d+\.\d+)', lonlat_str)
                    if coords and len(coords[0]) == 2:
                        return coords[0][0], coords[0][1]
                    
                    # Try alternate pattern
                    matches = re.findall(r'\d+[NSWE]\d+\.\d+', lonlat_str)
                    if len(matches) >= 2:
                        lat = next((m for m in matches if 'N' in m or 'S' in m), None)
                        lon = next((m for m in matches if 'W' in m or 'E' in m), None)
                        return lat, lon
                    
                    return None, None
                
                # Apply extraction function to each row
                extracted = all_data[lonlat_col].apply(extract_coords)
                all_data["Latitude"] = extracted.str[0]
                all_data["Longitude"] = extracted.str[1]
            
            # Check if split worked
            valid_coordinates = all_data.dropna(subset=["Latitude", "Longitude"])
            print(f"Successfully split coordinates: {len(valid_coordinates)} of {len(all_data)} rows")
            
            # Print first few coordinates for debugging
            print("First 5 extracted coordinate pairs:")
            for i, (lat, lon) in enumerate(zip(valid_coordinates["Latitude"].head(5), 
                                              valid_coordinates["Longitude"].head(5))):
                print(f"  {i+1}: '{lat}' - '{lon}'")
            
            if len(valid_coordinates) < 2:
                raise ValueError(f"Not enough valid coordinate pairs found (minimum 2 required, found {len(valid_coordinates)})")
            
            # Process only rows with valid data
            all_data["Latitude_dd"] = None
            all_data["Longitude_dd"] = None
            
            # Process each row individually to avoid errors stopping the whole process
            conversion_count = 0
            for idx, row in valid_coordinates.iterrows():
                try:
                    lat_str = row["Latitude"]
                    lon_str = row["Longitude"]
                    
                    # Extract N/S hemisphere and degree/minute values
                    if 'N' in lat_str:
                        ns_idx = lat_str.find('N')
                        ns_mult = 1
                    elif 'S' in lat_str:
                        ns_idx = lat_str.find('S')
                        ns_mult = -1
                    else:
                        print(f"Warning: No N/S indicator in latitude: '{lat_str}'")
                        continue
                    
                    lat_deg = float(lat_str[:ns_idx])
                    lat_min = float(lat_str[ns_idx+1:])
                    lat_val = ns_mult * (lat_deg + lat_min / 60)
                    
                    # Extract W/E hemisphere and degree/minute values
                    if 'W' in lon_str:
                        we_idx = lon_str.find('W')
                        we_mult = -1
                    elif 'E' in lon_str:
                        we_idx = lon_str.find('E')
                        we_mult = 1
                    else:
                        print(f"Warning: No W/E indicator in longitude: '{lon_str}'")
                        continue
                    
                    lon_deg = float(lon_str[:we_idx])
                    lon_min = float(lon_str[we_idx+1:])
                    lon_val = we_mult * (lon_deg + lon_min / 60)
                    
                    # Store decimal degree values
                    all_data.at[idx, "Latitude_dd"] = lat_val
                    all_data.at[idx, "Longitude_dd"] = lon_val
                    conversion_count += 1
                    
                except Exception as e:
                    print(f"Warning: Could not parse coordinates at row {idx}: {str(e)}")
            
            print(f"Successfully converted {conversion_count} coordinate pairs to decimal degrees")
            
            # Remove rows with failed conversions
            all_data = all_data.dropna(subset=["Latitude_dd", "Longitude_dd"])
            
            if len(all_data) < 2:
                raise ValueError(f"Not enough valid coordinates after conversion (minimum 2 required, converted {len(all_data)})")
                
        except Exception as e:
            error_msg = f"Error processing lat/lon values: {str(e)}"
            print(error_msg)
            raise ValueError(error_msg)
        
        # Find actual column names in the data for MSN005 format
        # Required: mission_time, heading, latitude, longitude, depth, heading_rate, altitude
        
        # Find heading column
        heading_col = None
        for col in all_data.columns:
            if col.lower() == 'heading' and 'rate' not in col.lower():
                heading_col = col
                break
        
        # Find heading rate column  
        heading_rate_col = None
        for col in all_data.columns:
            if 'heading' in col.lower() and 'rate' in col.lower():
                heading_rate_col = col
                break
                
        # Find depth column (could be Depth of vehicle, Bathymetry, etc.)
        depth_col = None
        for col in all_data.columns:
            if ('depth' in col.lower() and 'vehicle' in col.lower()) or 'bathymetry' in col.lower():
                depth_col = col
                break
                
        # Find altitude column
        altitude_col = None
        for col in all_data.columns:
            if 'altitude' in col.lower():
                altitude_col = col
                break
        
        # Create the MSN005 format dataframe with required columns
        output_data = pd.DataFrame()
        
        # mission_time (epoch time in UTC) - already created
        output_data['mission_time'] = all_data['mission_time']
        
        # heading - use found heading column or set to 0 if not found
        if heading_col and heading_col in all_data.columns:
            output_data['heading'] = pd.to_numeric(all_data[heading_col], errors='coerce')
        else:
            print("Warning: Heading column not found, setting to 0")
            output_data['heading'] = 0.0
        
        # latitude and longitude - already converted to decimal degrees
        output_data['latitude'] = all_data['Latitude_dd']
        output_data['longitude'] = all_data['Longitude_dd']
        
        # depth - use found depth column or set to 0 if not found  
        if depth_col and depth_col in all_data.columns:
            output_data['depth'] = pd.to_numeric(all_data[depth_col], errors='coerce')
        else:
            print("Warning: Depth column not found, setting to 0")
            output_data['depth'] = 0.0
        
        # heading_rate - use found heading rate column or set to 0 if not found
        if heading_rate_col and heading_rate_col in all_data.columns:
            # Adjust heading_rate (multiply by -1 as in original code)
            output_data['heading_rate'] = pd.to_numeric(all_data[heading_rate_col], errors='coerce') * -1
        else:
            print("Warning: Heading rate column not found, setting to 0")
            output_data['heading_rate'] = 0.0
            
        # altitude - use found altitude column or set to 0 if not found
        if altitude_col and altitude_col in all_data.columns:
            output_data['altitude'] = pd.to_numeric(all_data[altitude_col], errors='coerce')
        else:
            print("Warning: Altitude column not found, setting to 0")
            output_data['altitude'] = 0.0
        
        # Remove rows with invalid coordinates
        output_data = output_data.dropna(subset=['latitude', 'longitude'])
        
        # Use the output_data for both CSV and shapefile creation
        all_data = output_data
        
        return all_data, dive_num, main_folder
        
    except Exception as e:
        # Add more context to the error message
        error_msg = f"Error processing file {os.path.basename(nav_file)}: {str(e)}"
        raise Exception(error_msg)

def create_shapefile(coord_data, dive_num, output_folder):
    """Create a shapefile from the provided coordinate data"""
    try:
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
                x = float(coord_data.iloc[i, coord_data.columns.get_loc("longitude")])
                y = float(coord_data.iloc[i, coord_data.columns.get_loc("latitude")])
                point = arcpy.Point(x, y)
                array.add(point)
                
                x1 = float(coord_data.iloc[i+1, coord_data.columns.get_loc("longitude")])
                y1 = float(coord_data.iloc[i+1, coord_data.columns.get_loc("latitude")])
                point1 = arcpy.Point(x1, y1)
                array.add(point1)
                
                myline = arcpy.Polyline(array, spatRef)
                array.removeAll()
                cursor.insertRow([myline])
            except Exception as e:
                print(f"Warning: Skipping point at index {i}: {str(e)}")
                continue
        
        del cursor
        
        # Repair geometry
        arcpy.management.RepairGeometry(shapefile_w_path, "DELETE_NULL", "ESRI")
        
        # Dissolve the shapefile
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
        
        # Add DIVE field and calculate
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
        arcpy.CalculateGeometryAttributes_management(
            dissolved_shpfile,
            [["Length_m", "LENGTH_GEODESIC"]],
            "METERS"
        )
        
        return dissolved_shpfile
    
    except Exception as e:
        error_msg = f"Error creating shapefile for {dive_num}: {str(e)}"
        raise Exception(error_msg)

def select_output_folder():
    """Allow user to select a common output folder for all processed files"""
    folder = filedialog.askdirectory(
        title="Select Output Folder for All Processed Files"
    )
    
    if not folder:
        return None
    
    # Update output folder display
    output_folder_var.set(folder)
    return folder

def browse_file(file_var):
    """Open file dialog to select a file for a specific row"""
    file_path = filedialog.askopenfilename(
        title="Select Navigation File",
        filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
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
    # Count valid file paths
    valid_files = [v.get() for v in file_vars if v.get().strip()]
    file_count = len(valid_files)
    
    # Update file count label
    file_count_var.set(f"{file_count} file(s) selected")
    
    # Enable/disable buttons based on file count
    # Process button exists by this point since it's defined before calling this function
    if file_count > 0:
        process_button.config(state="normal")
        select_output_button.config(state="normal")
    else:
        process_button.config(state="disabled")
        select_output_button.config(state="normal" if file_vars else "disabled")

def process_files(file_list, output_folder=None):
    """Process each file in the list and update the progress bar"""
    results = []
    progress_step = 100 / len(file_list) if file_list else 0
    
    for i, file_path in enumerate(file_list):
        try:
            # Update status text
            dive_name = os.path.basename(file_path).split("_")[0]
            status_var.set(f"Processing {dive_name}... ({i+1}/{len(file_list)})")
            root.update_idletasks()
            
            # Process the navigation file
            formatted_data, dive_num, source_folder = process_nav_file(file_path)
            
            # Determine output folder
            if output_folder:
                # Use common output folder if specified
                destination_folder = output_folder
            else:
                # Create NavProducts folder in source directory
                destination_folder = os.path.join(source_folder, "NavProducts")
            
            # Create destination folder if it doesn't exist
            if not os.path.exists(destination_folder):
                os.makedirs(destination_folder)
            
            # Save CSV
            csv_filename = os.path.join(
                destination_folder,
                f"{dive_num}_Veh_Data_Formatted.csv"
            )
            formatted_data.to_csv(csv_filename, index=False, sep=",", quotechar='"')
            
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

def start_processing():
    """Start processing the selected files"""
    # Get valid file paths
    valid_files = [v.get() for v in file_vars if v.get().strip()]
    
    if not valid_files:
        messagebox.showerror("Error", "No files selected!")
        return
    
    # Get the output folder
    output_folder = output_folder_var.get() 
    if output_folder == "Default: NavProducts folder in source directory":
        output_folder = None
    
    # Disable the buttons during processing
    add_file_button.config(state="disabled")
    select_output_button.config(state="disabled")
    process_button.config(state="disabled")
    
    # Clear previous progress
    progress["value"] = 0
    root.update_idletasks()
    
    # Process the files
    try:
        results = process_files(valid_files, output_folder)
        
        # Show results
        status_var.set("Processing complete!")
        show_results(results)
    except Exception as e:
        messagebox.showerror("Processing Error", f"An unexpected error occurred: {str(e)}")
        status_var.set("Processing failed. See error message.")
    finally:
        # Enable the buttons after processing
        add_file_button.config(state="normal")
        select_output_button.config(state="normal")
        process_button.config(state="normal")

def show_results(results):
    """Display the processing results in a new window"""
    result_window = tk.Toplevel(root)
    result_window.title("Processing Results")
    result_window.geometry("600x400")
    
    # Create a text widget to display results
    result_text = tk.Text(result_window, wrap=tk.WORD)
    result_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Add a scrollbar
    scrollbar = tk.Scrollbar(result_window)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    result_text.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=result_text.yview)
    
    # Insert results
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
    
    # Make the text widget read-only
    result_text.config(state=tk.DISABLED)

def add_file_entry():
    """Add a new file entry row to the file selection frame"""
    file_row = tk.Frame(file_entries_frame)
    file_row.pack(fill=tk.X, pady=2)
    
    # Create a variable to hold the file path
    file_var = tk.StringVar()
    file_vars.append(file_var)
    
    # Create an entry to display the file path
    entry = tk.Entry(file_row, textvariable=file_var, width=50)
    entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
    
    # Create a browse button for this row
    browse_btn = tk.Button(
        file_row, 
        text="Browse", 
        command=lambda v=file_var: browse_file(v)
    )
    browse_btn.pack(side=tk.LEFT, padx=5)
    
    # Create a remove button for this row
    remove_btn = tk.Button(
        file_row,
        text="Remove",
        command=lambda row=file_row, v=file_var: remove_file_entry(row, v)
    )
    remove_btn.pack(side=tk.LEFT, padx=5)
    
    # Update scrollregion
    update_scroll_region()
    
    return file_row, file_var

# Error handling for the entire application
def handle_exception(exc_type, exc_value, exc_traceback):
    """Handle uncaught exceptions"""
    if issubclass(exc_type, KeyboardInterrupt):
        # Don't capture keyboard interrupt (Ctrl+C)
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
        
    # Log the error
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(f"Uncaught exception: {error_msg}")
    
    # Show error message to user
    messagebox.showerror("Unexpected Error", f"An unexpected error occurred:\n{str(exc_value)}")

# Set up global exception handler
sys.excepthook = handle_exception

def set_map_icon(window):
    """Set a map emoji as the window icon"""
    try:
        # Import PIL components
        from PIL import Image, ImageDraw, ImageTk
        
        # Create a 32x32 icon
        icon_size = 32
        icon_image = Image.new('RGBA', (icon_size, icon_size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(icon_image)
        
        # Draw a simple map shape
        # Map background (rectangle with rounded corners effect)
        draw.rectangle([2, 4, 30, 28], fill='lightblue', outline='darkblue', width=2)
        
        # Draw landmasses (irregular shapes to represent continents)
        # First landmass (upper left)
        draw.polygon([(4, 8), (12, 6), (14, 12), (8, 14), (4, 10)], fill='green', outline='darkgreen')
        
        # Second landmass (center right)
        draw.polygon([(18, 10), (28, 8), (26, 18), (20, 20), (16, 16)], fill='brown', outline='darkred')
        
        # Third landmass (bottom)
        draw.polygon([(6, 20), (16, 22), (14, 26), (8, 24)], fill='green', outline='darkgreen')
        
        # Add grid lines to make it look more map-like
        for i in range(6, 28, 6):
            draw.line([(2, i), (30, i)], fill='blue', width=1)  # Horizontal lines
            draw.line([(i, 4), (i, 28)], fill='blue', width=1)  # Vertical lines
        
        # Convert to PhotoImage for tkinter
        icon_photo = ImageTk.PhotoImage(icon_image)
        
        # Set the icon
        window.iconphoto(True, icon_photo)
        
        # Keep a reference to prevent garbage collection
        window.icon_photo = icon_photo
        
    except Exception as e:
        # Fallback: try to use a Unicode map emoji in the title
        print(f"Could not set custom icon: {e}")
        current_title = window.title()
        window.title(f"🗺️ {current_title}")

# Create the main GUI window
root = tk.Tk()
root.title("Remus Navigation Processor")
root.geometry("700x500")

# Set window icon to map emoji
set_map_icon(root)

# Set up variables
status_var = tk.StringVar()
status_var.set("Add navigation files to begin")
file_count_var = tk.StringVar()
file_count_var.set("No files selected")
output_folder_var = tk.StringVar()
output_folder_var.set("Default: NavProducts folder in source directory")
file_vars = []  # List to store file path variables

# Create frames
top_frame = tk.Frame(root, padx=10, pady=10)
top_frame.pack(fill=tk.X)

middle_frame = tk.Frame(root, padx=10, pady=5)
middle_frame.pack(fill=tk.BOTH, expand=True)

bottom_frame = tk.Frame(root, padx=10, pady=10)
bottom_frame.pack(fill=tk.X)

# Add a scrollable frame for file entries with fixed canvas size
file_entries_container = tk.Frame(middle_frame)
file_entries_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

# Create a canvas with scrollbar for the file entries
canvas = tk.Canvas(file_entries_container, height=200)
scrollbar = Scrollbar(file_entries_container, orient="vertical", command=canvas.yview)
file_entries_frame = tk.LabelFrame(canvas, text="Navigation Files", padx=5, pady=5)

# Configure the canvas
canvas.configure(yscrollcommand=scrollbar.set)
canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

# Add the frame to the canvas
canvas_frame = canvas.create_window((0, 0), window=file_entries_frame, anchor="nw", 
                                   width=canvas.winfo_reqwidth())

# Update scroll region when frame size changes
def on_frame_configure(event):
    canvas.configure(scrollregion=canvas.bbox("all"))
    # Update the width of the canvas window
    canvas.itemconfig(canvas_frame, width=canvas.winfo_width())

file_entries_frame.bind("<Configure>", on_frame_configure)

# Allow mouse wheel scrolling
def on_mousewheel(event):
    canvas.yview_scroll(int(-1*(event.delta/120)), "units")

canvas.bind_all("<MouseWheel>", on_mousewheel)

# Add output folder selection to middle frame
output_frame = tk.Frame(middle_frame, padx=5, pady=5)
output_frame.pack(fill=tk.X, padx=5, pady=5)

output_label = tk.Label(output_frame, text="Output Folder:")
output_label.pack(side=tk.LEFT, padx=5)

output_path_label = tk.Label(output_frame, textvariable=output_folder_var, wraplength=450)
output_path_label.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

# Add widgets to top frame
add_file_button = tk.Button(
    top_frame, 
    text="Add Navigation File", 
    command=add_file_entry,
    width=20
)
add_file_button.pack(side=tk.LEFT, padx=5)

file_count_label = tk.Label(top_frame, textvariable=file_count_var)
file_count_label.pack(side=tk.LEFT, padx=10)

# Add process button to bottom frame
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

# Define select_output_button after process_button
select_output_button = tk.Button(
    output_frame,
    text="Change",
    command=lambda: output_folder_var.set(select_output_folder() or output_folder_var.get()),
    state="disabled",
    width=10
)
select_output_button.pack(side=tk.RIGHT, padx=5)

# Add status label and progress bar
status_label = tk.Label(bottom_frame, textvariable=status_var)
status_label.pack(anchor="w", pady=5)

progress = Progressbar(bottom_frame, orient="horizontal", length=680, mode="determinate")
progress.pack(fill=tk.X, pady=5)

# Add a note about the script
note_label = tk.Label(
    bottom_frame, 
    text="This tool converts Remus navigation files to CSV and shapefile formats.\n"
         "Add multiple files from different folders and process them in batch.",
    justify=tk.LEFT,
    wraplength=680
)
note_label.pack(anchor="w", pady=5)

# NOW add the first file entry, after all widgets are defined
add_file_entry = add_file_entry  # This ensures the function has a reference to itself

# Start the main loop
if __name__ == "__main__":
    try:
        # First call to add_file_entry
        add_file_entry()
        
        root.mainloop()
    except Exception as e:
        print(f"Unhandled exception in main loop: {str(e)}")
        traceback.print_exc()