#!/usr/bin/env python3
"""
AUV Attitude EXIF Writer
Author: Mike Bollinger with GitHub Copilot assistance
Date: September 16, 2025
Updated: September 24, 2025

Description:
This script applies attitude parameters (pitch, roll, heading) from AUV navigation data
to JPEG images with full Agisoft Metashape compatibility. It matches navigation data
to images based on timestamps and writes attitude information using multiple EXIF/XMP
formats to ensure maximum photogrammetry software compatibility.

Technical Implementation:
- Multi-namespace XMP packets (SenseFly Camera, DJI drone-dji, generic Camera)
- DJI-compatible EXIF MakerNote format with precise attitude encoding
- GPS EXIF tags for heading information with proper rational number formatting
- EXIF SubjectDistance tag for capture distance (uses altitude from navigation data)
- Enhanced UserComment fields for debugging and verification
- Direct pitch/roll/heading values (0° pitch = oblique viewing as expected by Agisoft)
- Capture distance support for improved Agisoft Metashape photogrammetry processing

Navigation File Support:
- PHINS INS format with automatic depth/altitude mapping
- NAV_STATE format with enhanced column recognition
- DIVE format with complex header structure parsing
- Flexible auto-detection for unknown formats
- Robust column name handling (strips whitespace, handles "Depth of vehicle" variants)

Features:
- GUI interface for selecting image folder and navigation file
- Timestamp-based matching between images and navigation data (configurable tolerance)
- Parallel processing support for large datasets (configurable CPU cores)
- Safe mode (backup copies) or overwrite mode options
- Progress tracking and comprehensive logging
- CSV export for Agisoft reference with depth/altitude/attitude data
- Agisoft-verified compatibility with proper pitch/roll/heading import
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
from datetime import datetime, timedelta
import glob
from PIL import Image
from PIL.ExifTags import TAGS
import json
import threading
import time
import traceback
import multiprocessing as mp
import csv
import shutil
import re
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed

# Try to import piexif, but continue without it if not available
try:
    import piexif
    import piexif.helper
    PIEXIF_AVAILABLE = True
except ImportError:
    PIEXIF_AVAILABLE = False
    print("Warning: piexif not available. EXIF writing capabilities will be limited.")

# ---- EXIF helpers (preserve everything, add only attitude) ----
def _build_attitude_string(nav_data):
    """Return DJI-compatible attitude string using tenths of degrees (ints)."""
    gimbal_y = int((nav_data.get('heading') or 0) * 10)
    gimbal_p = int((nav_data.get('pitch') or 0) * 10)
    gimbal_r = int((nav_data.get('roll') or 0) * 10)
    
    # DJI-compatible format (exact match to working DJI images)
    gimbal_string = f"[GimbalDegree(Y,P,R):{gimbal_y},{gimbal_p},{gimbal_r}]"
    flight_string = f"[FlightDegree(Y,P,R):{gimbal_y},{gimbal_p},{gimbal_r}]"
    sensor_id = "[sensor_id:AUV_ATTITUDE_APPLIED]"
    
    return gimbal_string + flight_string + sensor_id

def _safe_piexif_dump(exif_dict):
    """Safely dump EXIF by filtering problematic tags piexif can't serialize.
    Strategy: try dump; if it fails, incrementally build a new dict and keep GPS intact.
    """
    try:
        return piexif.dump(exif_dict)
    except Exception:
        pass

    safe = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
    # Preserve GPS as much as possible (common requirement: don't lose geotags)
    try:
        safe["GPS"] = exif_dict.get("GPS", {}) or {}
    except Exception:
        safe["GPS"] = {}

    def try_add(ifd_name, tag, value):
        try:
            test = {"0th": {}, "Exif": {}, "GPS": safe["GPS"], "1st": {}, "thumbnail": exif_dict.get("thumbnail")}
            test[ifd_name][tag] = value
            piexif.dump(test)
            safe[ifd_name][tag] = value
            return True
        except Exception:
            return False

    # Whitelist-copy common, safe tags first to reduce dump exceptions
    safe_0th_tags = [
        getattr(piexif.ImageIFD, n) for n in (
            "Make", "Model", "Orientation", "XResolution", "YResolution", "ResolutionUnit",
            "Software", "DateTime", "Artist", "Copyright", "ImageDescription",
            "ExifTag", "GPSInfoTag", "ExifImageWidth", "ExifImageHeight"
        ) if hasattr(piexif.ImageIFD, n)
    ]
    for tag, val in (exif_dict.get("0th", {}) or {}).items():
        if (tag in safe_0th_tags) or True:  # attempt all; filter by try_add
            try_add("0th", tag, val)

    safe_exif_pref = [
        "DateTimeOriginal", "DateTimeDigitized", "SubSecTimeOriginal", "SubSecTimeDigitized",
        "ExposureTime", "FNumber", "ExposureProgram", "PhotographicSensitivity", "ISOSpeedRatings",
        "ShutterSpeedValue", "ApertureValue", "BrightnessValue", "MeteringMode", "Flash",
        "FocalLength", "ColorSpace", "ExifVersion", "ComponentsConfiguration", "SceneType",
        "UserComment", "PixelXDimension", "PixelYDimension"
    ]
    safe_exif_tags = [getattr(piexif.ExifIFD, n) for n in safe_exif_pref if hasattr(piexif.ExifIFD, n)]
    for tag, val in (exif_dict.get("Exif", {}) or {}).items():
        if (tag in safe_exif_tags) or True:
            try_add("Exif", tag, val)

    # 1st IFD often mirrors 0th; keep minimal safe subset
    for tag, val in (exif_dict.get("1st", {}) or {}).items():
        try_add("1st", tag, val)

    try:
        return piexif.dump(safe)
    except Exception as e:
        raise e

def process_single_image_worker(task):
    """
    Worker function for parallel processing of individual images.
    This function must be at module level to be pickable by multiprocessing.
    """
    try:
        image_path = task['image_path']
        filename = task['filename']
        nav_data = task['nav_data']
        output_path = task['output_path']
        overwrite_original = task['overwrite_original']
        
        # If not overwriting, copy to output directory first
        if not overwrite_original:
            # Create output directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            # Copy original to output location
            shutil.copy2(image_path, output_path)
            # Process the output copy
            process_path = output_path
        else:
            # Process the original file directly
            process_path = image_path
        
        # Apply attitude data
        success = write_attitude_to_image_worker(process_path, nav_data)
        
        if success:
            result_path = output_path if not overwrite_original else image_path
            pitch_val = nav_data['pitch']
            return {
                'filename': filename,
                'success': True,
                'message': f"Y={nav_data['heading']:.1f}°, P={pitch_val:.1f}°, R={nav_data['roll']:.1f}°",
                'output_path': result_path
            }
        else:
            return {
                'filename': filename,
                'success': False,
                'message': "Failed to write attitude data",
                'output_path': None
            }
            
    except Exception as e:
        return {
            'filename': task.get('filename', 'unknown'),
            'success': False,
            'message': f"Error: {str(e)}",
            'output_path': None
        }

def write_attitude_to_image_worker(image_path, nav_data):
    """
    Worker function to write attitude data to an image.
    This version PRESERVES all existing EXIF data and writes attitude to MakerNote in DJI format.
    
    Args:
        image_path: Path to the image file
        nav_data: Navigation data dictionary with attitude values
    """
    try:
        if not PIEXIF_AVAILABLE:
            print("piexif not available; cannot safely modify EXIF without risking data loss.")
            return False

        # Load original EXIF bytes to preserve exactly what's already there
        with Image.open(image_path) as im:
            orig_exif_bytes = im.info.get("exif")

        # Prefer loading from bytes (safer than reading file structure)
        exif_dict = piexif.load(orig_exif_bytes) if orig_exif_bytes else piexif.load(image_path)

        # Ensure IFDs exist
        exif_dict.setdefault("0th", {})
        exif_dict.setdefault("Exif", {})
        exif_dict.setdefault("GPS", exif_dict.get("GPS", {}))
        exif_dict.setdefault("1st", exif_dict.get("1st", {}))
        exif_dict.setdefault("thumbnail", exif_dict.get("thumbnail", None))

        # Create DJI-compatible attitude strings for MakerNote
        # Truncate to 3 decimal places as requested (Agisoft displays 3 decimal places)
        # Use precise decimal values instead of integers to preserve small attitude values
        
        # Ensure all navigation values are properly converted to float (defensive programming)
        try:
            heading_raw = nav_data.get('heading', 0)
            heading_val = round(float(heading_raw) if heading_raw is not None else 0.0, 3)
        except (ValueError, TypeError):
            heading_val = 0.0
            print(f"Warning: Invalid heading value '{nav_data.get('heading')}', using 0.0")
        
        # Handle pitch value
        try:
            raw_pitch = nav_data.get('pitch', 0)
            raw_pitch_float = float(raw_pitch) if raw_pitch is not None else 0.0
            # Use navigation pitch directly
            pitch_val = round(raw_pitch_float, 3)
        except (ValueError, TypeError):
            pitch_val = 0.0
            print(f"Warning: Invalid pitch value '{nav_data.get('pitch')}', using 0.0")
        
        try:
            roll_raw = nav_data.get('roll', 0)
            roll_val = round(float(roll_raw) if roll_raw is not None else 0.0, 3)
        except (ValueError, TypeError):
            roll_val = 0.0
            print(f"Warning: Invalid roll value '{nav_data.get('roll')}', using 0.0")
        
        # DJI format uses integers representing tenths of degrees
        # Convert to tenths of degrees as integers for MakerNote compatibility
        gimbal_y = int(heading_val * 10)  # Yaw (heading) in tenths of degrees
        gimbal_p = int(pitch_val * 10)    # Pitch in tenths of degrees (with -90° compensation)
        gimbal_r = int(roll_val * 10)     # Roll in tenths of degrees
        
        # Use same values for flight attitude (AUV doesn't have separate gimbal)
        flight_y = gimbal_y
        flight_p = gimbal_p  
        flight_r = gimbal_r

        # Write attitude data using Agisoft-compatible GPS EXIF tags
        # Based on Agisoft forum: https://www.agisoft.com/forum/index.php?topic=5597.0
        
        # Ensure GPS IFD exists
        exif_dict.setdefault("GPS", {})
        
        # Convert attitude values to proper format for GPS tags
        # GPS tags typically use rational numbers (fractions)
        def degrees_to_rational(degrees):
            """Convert degrees to rational format (numerator, denominator)"""
            # Use 1000 as denominator for precision to 0.001 degrees (3 decimal places)
            numerator = int(abs(degrees) * 1000)
            denominator = 1000
            return (numerator, denominator)
        
        # Set GPS attitude tags - only use standard tags that piexif supports
        # GPSImgDirection (0x0011) for Yaw/Heading
        try:
            heading_rational = degrees_to_rational(heading_val)  # Use truncated value
            exif_dict["GPS"][piexif.GPSIFD.GPSImgDirection] = heading_rational
            exif_dict["GPS"][piexif.GPSIFD.GPSImgDirectionRef] = b"T"  # True North - use bytes
            
            # Note: Custom GPS tags 0xd000 (pitch) and 0xd001 (roll) are not supported by piexif
            # Agisoft will need to rely on the MakerNote approach for pitch/roll data
            
        except Exception as gps_error:
            print(f"Warning: Could not set GPS attitude tags: {gps_error}")
        
        # Add capture distance using EXIF SubjectDistance tag
        # This helps Agisoft Metashape with photogrammetry processing
        try:
            altitude_raw = nav_data.get('altitude', 0)
            altitude_val = float(altitude_raw) if altitude_raw is not None else 0.0
            if altitude_val > 0:
                # SubjectDistance is stored as a rational (numerator, denominator) in meters
                # Use altitude as capture distance - distance from camera to subject (seafloor/ground)
                distance_rational = (int(altitude_val * 1000), 1000)  # Store with 3 decimal precision
                exif_dict["Exif"][piexif.ExifIFD.SubjectDistance] = distance_rational
            else:
                print("Warning: No valid altitude data for capture distance")
                
        except Exception as distance_error:
            print(f"Warning: Could not set capture distance: {distance_error}")
        
        # Enhanced MakerNote approach - use exact DJI format structure
        # Based on analysis of working DJI images, use precise format matching
        gimbal_string = f"[GimbalDegree(Y,P,R):{gimbal_y},{gimbal_p},{gimbal_r}]"
        flight_string = f"[FlightDegree(Y,P,R):{flight_y},{flight_p},{flight_r}]"
        sensor_id = "[sensor_id:AUV_ATTITUDE_APPLIED]"
        
        # Create complete DJI-style MakerNote (overwrite existing to ensure format)
        dji_maker_note = gimbal_string + flight_string + sensor_id
        exif_dict["Exif"][piexif.ExifIFD.MakerNote] = dji_maker_note.encode('utf-8')
        
        # Also add attitude to UserComment for additional compatibility
        try:
            altitude_raw = nav_data.get('altitude', 0)
            depth_raw = nav_data.get('depth', 0)
            altitude_val = float(altitude_raw) if altitude_raw is not None else 0.0
            depth_val = float(depth_raw) if depth_raw is not None else 0.0
            attitude_comment = f"AUV Attitude: H={heading_val:.3f}°,P={pitch_val:.3f}°,R={roll_val:.3f}°,D={depth_val:.3f}m,A={altitude_val:.3f}m,CD={altitude_val:.3f}m"
            user_comment = piexif.helper.UserComment.dump(attitude_comment, encoding="unicode")
            exif_dict["Exif"][piexif.ExifIFD.UserComment] = user_comment
        except Exception as uc_error:
            print(f"Warning: Could not set UserComment: {uc_error}")
        
        # Don't modify ImageDescription - leave title and subject unchanged as requested
        try:
            # Keep existing ImageDescription unchanged
            pass
        except Exception as desc_error:
            print(f"Warning: Could not set ImageDescription: {desc_error}")

        # Create bytes safely
        try:
            exif_bytes = _safe_piexif_dump(exif_dict)
        except Exception as dump_err:
            print(f"piexif dump failed after sanitize: {dump_err}")
            return False

        # Save image with EXIF data first
        with Image.open(image_path) as im:
            im.save(image_path, "JPEG", exif=exif_bytes)

        # Now add XMP GPS attitude data for maximum Agisoft compatibility
        # Based on analysis: DJI uses drone-dji namespace, FreeFly uses Camera namespace
        try:
            # Convert to rational format (value/1000) like FreeFly
            heading_rational = int(heading_val * 1000)
            pitch_rational = int(pitch_val * 1000)
            roll_rational = int(roll_val * 1000)
            
            # Create XMP packet with MULTIPLE attitude namespaces for maximum Agisoft compatibility
            # Based on Agisoft PDF documentation, try multiple supported namespaces
            altitude_raw = nav_data.get('altitude', 0)
            depth_raw = nav_data.get('depth', 0)
            altitude_val = float(altitude_raw) if altitude_raw is not None else 0.0
            depth_val = float(depth_raw) if depth_raw is not None else 0.0
            
            xmp_packet = f'''<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
        xmlns:sensefly-camera="http://ns.sensefly.com/Camera/1.0/"
        xmlns:drone-dji="http://www.dji.com/drone-dji/1.0/"
        xmlns:auv="http://auv.attitude/1.0/"
        sensefly-camera:Pitch="{pitch_val:.3f}"
        sensefly-camera:Roll="{roll_val:.3f}"
        sensefly-camera:Yaw="{heading_val:.3f}"
        sensefly-camera:GPSXYAccuracy="1.0"
        sensefly-camera:GPSZAccuracy="1.0"
        sensefly-camera:AboveGroundAltitude="{altitude_val:.3f}"
        sensefly-camera:CaptureDistance="{altitude_val:.3f}"
        drone-dji:FlightPitchDegree="{pitch_val:+.2f}"
        drone-dji:FlightRollDegree="{roll_val:+.2f}"
        drone-dji:FlightYawDegree="{heading_val:+.2f}"
        drone-dji:RelativeAltitude="{altitude_val:.3f}">
      
      <auv:Heading>{heading_val:.3f}</auv:Heading>
      <auv:Pitch>{pitch_val:.3f}</auv:Pitch>
      <auv:Roll>{roll_val:.3f}</auv:Roll>
      <auv:Depth>{depth_val:.3f}</auv:Depth>
      <auv:Altitude>{altitude_val:.3f}</auv:Altitude>
      <auv:CaptureDistance>{altitude_val:.3f}</auv:CaptureDistance>
      <auv:HeadingReference>TrueNorth</auv:HeadingReference>
      <auv:AttitudeSource>AUV_Navigation_Data</auv:AttitudeSource>
      
      <sensefly-camera:CameraPitch>{pitch_val:.3f}</sensefly-camera:CameraPitch>
      <sensefly-camera:CameraRoll>{roll_val:.3f}</sensefly-camera:CameraRoll>
      <sensefly-camera:CameraYaw>{heading_val:.3f}</sensefly-camera:CameraYaw>
      <sensefly-camera:CameraAltitude>{altitude_val:.3f}</sensefly-camera:CameraAltitude>
      
      <drone-dji:GimbalReverse>0</drone-dji:GimbalReverse>
      <drone-dji:AbsoluteAltitude>{altitude_val:.3f}</drone-dji:AbsoluteAltitude>
      
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''
            
            # Write XMP data to image
            with Image.open(image_path) as im:
                new_info = im.info.copy()
                new_info['xmp'] = xmp_packet.encode('utf-8')
                im.save(image_path, format='JPEG', **new_info)
        except Exception as xmp_error:
            print(f"Warning: Could not add XMP GPS attitude data: {xmp_error}")
            # Continue anyway - EXIF data was written successfully
        
        print("Image:", image_path, "altitude:", altitude_val, "depth:", depth_val, "pitch:", f"{pitch_val}", "roll:", roll_val, "heading:", heading_val)

        return True

    except Exception as e:
        print(f"Overall error in write_attitude_to_image_worker: {e}")
        return False

def safe_float_convert(value, default=0.0, field_name=""):
    """Safely convert a value to float, handling None and string values"""
    if value is None:
        return default
    try:
        # Handle pandas NA/NaN values
        if pd.isna(value):
            return default
        return float(value)
    except (ValueError, TypeError) as e:
        if field_name:
            print(f"Warning: Could not convert {field_name} value '{value}' to float, using {default}: {e}")
        return default

class AttitudeEXIFWriter:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AUV Attitude EXIF Writer")
        self.root.geometry("800x600")
        
        self.image_folder = ""
        self.nav_file = ""
        self.output_folder = ""
        self.nav_data = []
        self.images = []
        
        self.setup_gui()
    
    def setup_gui(self):
        """Setup the GUI interface"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="AUV Attitude EXIF Writer", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Image folder selection
        ttk.Label(main_frame, text="Image Folder:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.image_folder_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.image_folder_var, width=60).grid(row=1, column=1, padx=5)
        ttk.Button(main_frame, text="Browse", 
                  command=self.select_image_folder).grid(row=1, column=2, padx=5)
        
        # Navigation file selection
        ttk.Label(main_frame, text="Navigation File:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.nav_file_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.nav_file_var, width=60).grid(row=2, column=1, padx=5)
        ttk.Button(main_frame, text="Browse", 
                  command=self.select_nav_file).grid(row=2, column=2, padx=5)
        
        # Output directory selection
        ttk.Label(main_frame, text="Output Directory:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.output_folder_var = tk.StringVar()
        self.output_entry = ttk.Entry(main_frame, textvariable=self.output_folder_var, width=60)
        self.output_entry.grid(row=3, column=1, padx=5)
        self.output_button = ttk.Button(main_frame, text="Browse", 
                  command=self.select_output_folder)
        self.output_button.grid(row=3, column=2, padx=5)
        
        # Options frame
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding="10")
        options_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # Time tolerance
        ttk.Label(options_frame, text="Nav Matching Time Tolerance (seconds):").grid(row=0, column=0, sticky=tk.W)
        self.time_tolerance_var = tk.IntVar(value=3)
        ttk.Spinbox(options_frame, from_=1, to=300, textvariable=self.time_tolerance_var, 
                   width=10).grid(row=0, column=1, padx=5, sticky=tk.W)
        
        # Parallel processing options
        ttk.Label(options_frame, text="CPU Cores for Processing:").grid(row=1, column=0, sticky=tk.W)
        self.cpu_cores_var = tk.IntVar(value=mp.cpu_count())  # Default to max CPU cores
        max_cores = mp.cpu_count()
        ttk.Spinbox(options_frame, from_=1, to=max_cores, textvariable=self.cpu_cores_var, 
                   width=10).grid(row=1, column=1, padx=5, sticky=tk.W)
        ttk.Label(options_frame, text=f"(Max: {max_cores})").grid(row=1, column=2, sticky=tk.W, padx=5)
        
        # Batch size option
        ttk.Label(options_frame, text="Images per Batch:").grid(row=2, column=0, sticky=tk.W)
        self.batch_size_var = tk.IntVar(value=100)  # Default to 100 images per batch
        ttk.Spinbox(options_frame, from_=10, to=1000, textvariable=self.batch_size_var, 
                   width=10).grid(row=2, column=1, padx=5, sticky=tk.W)
        
        # Performance optimization options
        self.fast_io_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Fast I/O mode (use memory buffers)", 
                       variable=self.fast_io_var).grid(row=3, column=0, columnspan=2, sticky=tk.W)
        
        # Overwrite original files option
        self.overwrite_var = tk.BooleanVar(value=False)
        self.overwrite_checkbox = ttk.Checkbutton(options_frame, text="Overwrite original files (WARNING: No backup!)", 
                       variable=self.overwrite_var, command=self.toggle_output_controls)
        self.overwrite_checkbox.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=5)
        

        
        # Preview frame
        preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding="10")
        preview_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # Text widget for preview
        self.preview_text = tk.Text(preview_frame, height=15, width=80)
        preview_scrollbar = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=preview_scrollbar.set)
        self.preview_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        preview_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Progress bar and status
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # Status label for showing current operation
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, font=("Arial", 9))
        self.status_label.grid(row=6, column=2, sticky=tk.E, padx=(5, 0))
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=7, column=0, columnspan=3, pady=10)
        
        ttk.Button(buttons_frame, text="Load & Preview", 
                  command=self.load_and_preview).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Process Images", 
                  command=self.process_images).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Load & Process All", 
                  command=self.load_and_process_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Clear", 
                  command=self.clear_preview).pack(side=tk.LEFT, padx=5)
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(5, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
    
    def select_image_folder(self):
        """Select folder containing JPEG images"""
        folder = filedialog.askdirectory(title="Select Image Folder")
        if folder:
            self.image_folder = folder
            self.image_folder_var.set(folder)
            self.log(f"Selected image folder: {folder}")
    
    def select_nav_file(self):
        """Select navigation file"""
        file = filedialog.askopenfilename(
            title="Select Navigation File", 
            filetypes=[("All files", "*.*"), ("Text files", "*.txt"), ("CSV files", "*.csv")]
        )
        if file:
            self.nav_file = file
            self.nav_file_var.set(file)
            self.log(f"Selected navigation file: {file}")
    
    def select_output_folder(self):
        """Select output folder for processed images"""
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_folder = folder
            self.output_folder_var.set(folder)
            self.log(f"Selected output folder: {folder}")
    
    def toggle_output_controls(self):
        """Toggle output directory controls based on overwrite option"""
        if self.overwrite_var.get():
            # Disable output directory when overwriting
            self.output_entry.config(state='disabled')
            self.output_button.config(state='disabled')
            self.log("Overwrite mode enabled - original files will be modified")
        else:
            # Enable output directory when not overwriting
            self.output_entry.config(state='normal')
            self.output_button.config(state='normal')
            self.log("Safe mode enabled - processed images will be saved to output directory")
    
    def log(self, message):
        """Add message to preview text widget"""
        self.preview_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')}: {message}\n")
        self.preview_text.see(tk.END)
        self.root.update_idletasks()
    
    def clear_preview(self):
        """Clear the preview text"""
        self.preview_text.delete(1.0, tk.END)
        self.progress_var.set(0)
        self.status_var.set("Ready")
    
    def load_navigation_data(self):
        """Load and parse navigation data"""
        if not os.path.exists(self.nav_file):
            raise FileNotFoundError(f"Navigation file not found: {self.nav_file}")
        
        self.log("Loading navigation data...")
        
        # Debug: Show file info and estimate progress
        try:
            file_size = os.path.getsize(self.nav_file)
            self.log(f"Navigation file size: {file_size} bytes")
            
            # Count total lines for progress tracking
            with open(self.nav_file, 'r') as f:
                total_lines = sum(1 for _ in f)
            self.log(f"Navigation file has {total_lines} lines")
            self.total_nav_lines = total_lines
        except:
            self.total_nav_lines = 0
        
        # Try to read as CSV first
        try:
            # Read the file to determine format and show first few lines for debugging
            with open(self.nav_file, 'r') as f:
                lines = f.readlines()
            
            self.log(f"File has {len(lines)} lines")
            self.log("First 5 lines of navigation file:")
            for i, line in enumerate(lines[:5]):
                self.log(f"  Line {i+1}: {repr(line.strip())}")
            
            first_line = lines[0].strip() if lines else ""
            self.log(f"Header line: {first_line}")
            
            # Try to read as pandas DataFrame with different separators and options
            df = None
            separators_to_try = [
                (',', 'comma'),
                ('\t', 'tab'), 
                (';', 'semicolon'),
                ('|', 'pipe'),
                (' ', 'space'),
                (None, 'auto-detect')  # Let pandas figure it out
            ]
            
            for sep, sep_name in separators_to_try:
                try:
                    # Try different read options
                    read_options = [
                        {'sep': sep, 'skipinitialspace': True},
                        {'sep': sep, 'header': 0, 'skipinitialspace': True},
                        {'sep': sep, 'header': None, 'skipinitialspace': True},
                        {'sep': sep, 'delim_whitespace': True} if sep == ' ' else {'sep': sep, 'skipinitialspace': True}
                    ]
                    
                    for options in read_options:
                        try:
                            if sep is None:  # Auto-detect case
                                options = {'sep': None, 'engine': 'python', 'low_memory': False, 'skipinitialspace': True}
                            else:
                                options['low_memory'] = False
                            
                            df = pd.read_csv(self.nav_file, **options)
                            
                            # Validate that we got reasonable data
                            if df.shape[1] >= 3 and df.shape[0] > 0:  # At least 3 columns and some data
                                self.log(f"Successfully read CSV with {sep_name} separator")
                                self.log(f"DataFrame shape: {df.shape}")
                                self.log(f"Column names: {list(df.columns)}")
                                
                                # Check if columns have reasonable names or if we need to set them
                                if df.columns[0].startswith('Unnamed') or not any(isinstance(col, str) for col in df.columns):
                                    self.log("Columns appear to be auto-generated, trying without header...")
                                    options_no_header = {k:v for k,v in options.items() if k != 'header'}
                                    options_no_header['low_memory'] = False
                                    df = pd.read_csv(self.nav_file, header=None, **options_no_header)
                                    self.log(f"Re-read without header: {df.shape}")
                                
                                break
                        except Exception as e:
                            continue
                    
                    if df is not None and df.shape[1] >= 3:
                        break
                        
                except Exception as e:
                    self.log(f"Failed with {sep_name}: {e}")
                    continue
            
            if df is None or df.shape[1] < 3:
                self.log("ERROR: Could not read file with any common separator or insufficient columns")
                self.log("Expected at least 3 columns (time, latitude, longitude)")
                return False
            
            # Show first few rows for debugging
            self.log("First 3 rows of data:")
            for i in range(min(3, len(df))):
                self.log(f"  Row {i}: {dict(df.iloc[i])}")
            
            # Detect specific format based on filename and content
            filename = os.path.basename(self.nav_file).lower()
            
            if "dive009" in filename or filename.startswith("dive") or "dive" in filename:
                self.log("Detected DIVE format navigation file")
                self.nav_data = self.parse_dive_format(self.nav_file)
            elif "phins" in filename:
                self.log("Detected PHINS INS format navigation file")
                self.nav_data = self.parse_phins_format(self.nav_file)
            elif "nav_state" in filename:
                self.log("Detected NAV_STATE format navigation file")
                self.nav_data = self.parse_nav_state_format(self.nav_file)
            else:
                # Auto-detect the format based on column names and data patterns
                format_detected = self.detect_navigation_format(df, first_line)
                
                if format_detected == 'vehicle':
                    self.log("Detected vehicle format - parsing...")
                    self.nav_data = self.parse_vehicle_format(df)
                elif format_detected == 'standard':
                    self.log("Detected standard format - parsing...")
                    self.nav_data = self.parse_standard_format(df)
                elif format_detected == 'numeric':
                    self.log("Detected numeric format (no headers) - parsing...")
                    self.nav_data = self.parse_numeric_format(df)
                else:
                    self.log("Unknown format - trying flexible parsing...")
                    self.nav_data = self.parse_flexible_format(df)
            
            self.log(f"Successfully parsed {len(self.nav_data)} navigation records")
            
            # Show first parsed record for debugging
            if self.nav_data:
                first_record = self.nav_data[0]
                self.log(f"First parsed record: {first_record}")
            
            return True
            
        except Exception as e:
            self.log(f"Error loading navigation data: {e}")
            import traceback
            self.log(f"Full error: {traceback.format_exc()}")
            return False
    
    def parse_vehicle_format(self, df):
        """Parse the specific vehicle navigation format"""
        nav_data = []
        total_rows = len(df)
        self.log(f"Parsing {total_rows} rows in vehicle format...")
        
        # Initialize progress for navigation parsing
        progress_step = max(1, total_rows // 100)  # Update every 1% or at least every row
        
        for idx, row in df.iterrows():
            # Update progress every progress_step rows
            if idx % progress_step == 0 or idx == total_rows - 1:
                progress = (idx + 1) / total_rows * 50  # Use first 50% of progress bar for nav parsing
                self.progress_var.set(progress)
                self.root.update_idletasks()
            try:
                # Check if required columns exist
                if 'Time' not in row or 'Date' not in row or 'Lon/Lat' not in row:
                    self.log(f"Row {idx}: Missing required columns")
                    continue
                
                # Parse time and date
                time_str = str(row['Time']).strip()
                date_str = str(row['Date']).strip()
                
                if idx < 3:  # Debug first few rows
                    self.log(f"Row {idx}: time='{time_str}', date='{date_str}'")
                
                # Combine date and time
                datetime_str = f"{date_str} {time_str}"
                dt = None
                
                # Try different datetime formats
                formats_to_try = [
                    '%m/%d/%Y %H:%M:%S.%f', '%m/%d/%Y %H:%M:%S', 
                    '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S',
                    '%d/%m/%Y %H:%M:%S.%f', '%d/%m/%Y %H:%M:%S',
                    '%Y/%m/%d %H:%M:%S.%f', '%Y/%m/%d %H:%M:%S'
                ]
                
                for fmt in formats_to_try:
                    try:
                        dt = datetime.strptime(datetime_str, fmt)
                        if idx < 3:
                            self.log(f"Row {idx}: Successfully parsed datetime with format '{fmt}'")
                        break
                    except:
                        continue
                
                if dt is None:
                    if idx < 3:
                        self.log(f"Row {idx}: Failed to parse datetime '{datetime_str}'")
                    continue
                
                # Parse coordinates from format like "30N00.99305  87W00.66822"
                lonlat_str = str(row['Lon/Lat']).strip()
                if idx < 3:
                    self.log(f"Row {idx}: coordinates='{lonlat_str}'")
                
                lat, lon = self.parse_lonlat_string(lonlat_str)
                
                if lat is None or lon is None:
                    if idx < 3:
                        self.log(f"Row {idx}: Failed to parse coordinates")
                    continue
                
                # Get altitude and heading
                altitude = None
                if 'Altitude' in row:
                    try:
                        altitude = float(row['Altitude'])
                    except:
                        pass
                
                heading = None
                if 'Heading' in row:
                    try:
                        heading = float(row['Heading'])
                    except:
                        pass
                
                # Look for pitch and roll columns
                pitch = None
                if 'Pitch' in row:
                    try:
                        pitch = float(row['Pitch'])
                    except:
                        pass
                
                roll = None
                if 'Roll' in row:
                    try:
                        roll = float(row['Roll'])
                    except:
                        pass
                
                nav_record = {
                    'datetime': dt,
                    'latitude': lat,
                    'longitude': lon,
                    'altitude': altitude,
                    'heading': heading,
                    'pitch': pitch,
                    'roll': roll
                }
                
                nav_data.append(nav_record)
                
                if idx < 3:
                    self.log(f"Row {idx}: Successfully parsed record: {nav_record}")
                
            except Exception as e:
                self.log(f"Error parsing navigation row {idx}: {e}")
                if idx < 3:
                    import traceback
                    self.log(f"Row {idx} traceback: {traceback.format_exc()}")
                continue
        
        self.log(f"Vehicle format parsing complete: {len(nav_data)}/{total_rows} records parsed")
        return nav_data
    
    def parse_standard_format(self, df):
        """Parse standard CSV format"""
        # Clean column names heavily to handle whitespace formatting issues
        if hasattr(df.columns, 'str'):
            df.columns = df.columns.astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
        
        nav_data = []
        total_rows = len(df)
        self.log(f"Parsing {total_rows} rows in standard format...")
        
        # Initialize progress for navigation parsing
        progress_step = max(1, total_rows // 100)  # Update every 1% or at least every row
        
        # Common column name variations
        time_cols = ['Time', 'DateTime', 'Timestamp', 'time', 'datetime', 'timestamp']
        lat_cols = ['Latitude', 'Lat', 'latitude', 'lat']
        lon_cols = ['Longitude', 'Lon', 'longitude', 'lon']
        heading_cols = ['Heading', 'Yaw', 'heading', 'yaw']
        pitch_cols = ['Pitch', 'pitch']
        roll_cols = ['Roll', 'roll']
        alt_cols = ['Altitude', 'Alt', 'altitude', 'alt', 'Height', 'height']
        depth_cols = ['Depth', 'depth', 'Depth_m', 'depth_m', 'Depth of vehicle']
        
        # Find the correct column names
        time_col = next((col for col in time_cols if col in df.columns), None)
        lat_col = next((col for col in lat_cols if col in df.columns), None)
        lon_col = next((col for col in lon_cols if col in df.columns), None)
        heading_col = next((col for col in heading_cols if col in df.columns), None)
        pitch_col = next((col for col in pitch_cols if col in df.columns), None)
        roll_col = next((col for col in roll_cols if col in df.columns), None)
        alt_col = next((col for col in alt_cols if col in df.columns), None)
        depth_col = next((col for col in depth_cols if col in df.columns), None)
        
        self.log(f"Column mapping:")
        self.log(f"  Time: {time_col}")
        self.log(f"  Latitude: {lat_col}")
        self.log(f"  Longitude: {lon_col}")
        self.log(f"  Heading: {heading_col}")
        self.log(f"  Pitch: {pitch_col}")
        self.log(f"  Roll: {roll_col}")
        self.log(f"  Altitude: {alt_col}")
        self.log(f"  Depth: {depth_col}")
        
        if not all([time_col, lat_col, lon_col]):
            missing = []
            if not time_col:
                missing.append("Time/DateTime")
            if not lat_col:
                missing.append("Latitude")
            if not lon_col:
                missing.append("Longitude")
            raise ValueError(f"Required columns not found: {missing}")
        
        for idx, row in df.iterrows():
            # Update progress every progress_step rows
            if idx % progress_step == 0 or idx == total_rows - 1:
                progress = (idx + 1) / total_rows * 50  # Use first 50% of progress bar for nav parsing
                self.progress_var.set(progress)
                self.root.update_idletasks()
                
            try:
                # Parse datetime
                dt_str = str(row[time_col])
                if idx < 3:
                    self.log(f"Row {idx}: datetime string = '{dt_str}'")
                
                dt = self.parse_flexible_datetime(dt_str)
                
                if dt is None:
                    if idx < 3:
                        self.log(f"Row {idx}: Failed to parse datetime")
                    continue
                
                # Parse coordinates
                try:
                    lat = float(row[lat_col])
                    lon = float(row[lon_col])
                except:
                    if idx < 3:
                        self.log(f"Row {idx}: Failed to parse coordinates")
                    continue
                
                nav_record = {
                    'datetime': dt,
                    'latitude': lat,
                    'longitude': lon,
                    'altitude': float(row[alt_col]) if alt_col and pd.notna(row[alt_col]) else 0.0,
                    'depth': float(row[depth_col]) if depth_col and pd.notna(row[depth_col]) else 0.0,
                    'heading': float(row[heading_col]) if heading_col and pd.notna(row[heading_col]) else 0.0,
                    'pitch': float(row[pitch_col]) if pitch_col and pd.notna(row[pitch_col]) else 0.0,
                    'roll': float(row[roll_col]) if roll_col and pd.notna(row[roll_col]) else 0.0
                }
                
                nav_data.append(nav_record)
                
                if idx < 3:
                    self.log(f"Row {idx}: Successfully parsed: {nav_record}")
                
            except Exception as e:
                self.log(f"Error parsing navigation row {idx}: {e}")
                if idx < 3:
                    import traceback
                    self.log(f"Row {idx} traceback: {traceback.format_exc()}")
                continue
        
        self.log(f"Standard format parsing complete: {len(nav_data)}/{total_rows} records parsed")
        return nav_data
    
    def detect_navigation_format(self, df, first_line):
        """Auto-detect the navigation file format"""
        self.log("Auto-detecting navigation format...")
        
        # Check for vehicle format (Field Photogrammetry format)
        if ('Time' in first_line and 'Date' in first_line and 'Lon/Lat' in first_line) or \
           (hasattr(df, 'columns') and 'Time' in df.columns and 'Date' in df.columns and 'Lon/Lat' in df.columns):
            return 'vehicle'
        
        # Check for standard format with recognizable column names
        if hasattr(df, 'columns'):
            cols_lower = [str(col).lower() for col in df.columns]
            has_time = any(t in ' '.join(cols_lower) for t in ['time', 'date', 'timestamp'])
            has_coords = any(c in ' '.join(cols_lower) for c in ['lat', 'lon', 'latitude', 'longitude'])
            
            if has_time and has_coords:
                return 'standard'
        
        # Check if it's numeric data without headers
        if not hasattr(df, 'columns') or df.columns[0] == 0 or str(df.columns[0]).startswith('Unnamed'):
            return 'numeric'
        
        return 'flexible'
    
    def parse_numeric_format(self, df):
        """Parse numeric format without column headers"""
        nav_data = []
        total_rows = len(df)
        self.log(f"Parsing {total_rows} rows in numeric format...")
        self.log("Assuming column order: [Time/DateTime, Latitude, Longitude, ...]")
        
        if df.shape[1] < 3:
            self.log("ERROR: Need at least 3 columns for numeric format")
            return nav_data
        
        # Initialize progress for navigation parsing
        progress_step = max(1, total_rows // 100)  # Update every 1% or at least every row
        
        for idx, row in df.iterrows():
            # Update progress every progress_step rows
            if idx % progress_step == 0 or idx == total_rows - 1:
                progress = (idx + 1) / total_rows * 50  # Use first 50% of progress bar for nav parsing
                self.progress_var.set(progress)
                self.root.update_idletasks()
            try:
                # Assume first column is time/datetime
                time_val = row.iloc[0]
                lat_val = row.iloc[1] 
                lon_val = row.iloc[2]
                
                if idx < 3:
                    self.log(f"Row {idx}: time='{time_val}', lat='{lat_val}', lon='{lon_val}'")
                
                # Try to parse datetime
                dt = self.parse_flexible_datetime(str(time_val))
                if dt is None:
                    if idx < 3:
                        self.log(f"Row {idx}: Failed to parse datetime")
                    continue
                
                # Parse coordinates
                try:
                    lat = float(lat_val)
                    lon = float(lon_val)
                except:
                    if idx < 3:
                        self.log(f"Row {idx}: Failed to parse coordinates")
                    continue
                
                # Get additional columns if available
                altitude = None
                heading = None
                pitch = None  
                roll = None
                
                if df.shape[1] > 3:
                    try:
                        altitude = float(row.iloc[3])
                    except:
                        pass
                
                if df.shape[1] > 4:
                    try:
                        heading = float(row.iloc[4])
                    except:
                        pass
                
                if df.shape[1] > 5:
                    try:
                        pitch = float(row.iloc[5])
                    except:
                        pass
                
                if df.shape[1] > 6:
                    try:
                        roll = float(row.iloc[6])
                    except:
                        pass
                
                nav_record = {
                    'datetime': dt,
                    'latitude': lat,
                    'longitude': lon,
                    'altitude': altitude,
                    'heading': heading,
                    'pitch': pitch,
                    'roll': roll
                }
                
                nav_data.append(nav_record)
                
                if idx < 3:
                    self.log(f"Row {idx}: Successfully parsed: {nav_record}")
                
            except Exception as e:
                self.log(f"Error parsing numeric row {idx}: {e}")
                if idx < 3:
                    self.log(f"Row {idx} traceback: {traceback.format_exc()}")
                continue
        
        self.log(f"Numeric format parsing complete: {len(nav_data)}/{total_rows} records parsed")
        return nav_data
    
    def parse_flexible_format(self, df):
        """Parse unknown format by analyzing data patterns"""
        nav_data = []
        total_rows = len(df)
        self.log(f"Parsing {total_rows} rows in flexible format...")
        
        # Analyze columns to guess their purpose
        column_analysis = self.analyze_columns(df)
        self.log(f"Column analysis: {column_analysis}")
        
        if not column_analysis.get('time_col') or not column_analysis.get('lat_col') or not column_analysis.get('lon_col'):
            self.log("ERROR: Could not identify time, latitude, and longitude columns")
            return nav_data
        
        time_col = column_analysis['time_col']
        lat_col = column_analysis['lat_col']
        lon_col = column_analysis['lon_col']
        alt_col = column_analysis.get('alt_col')
        heading_col = column_analysis.get('heading_col')
        pitch_col = column_analysis.get('pitch_col')
        roll_col = column_analysis.get('roll_col')
        
        # Initialize progress for navigation parsing
        progress_step = max(1, total_rows // 100)  # Update every 1% or at least every row
        
        for idx, row in df.iterrows():
            # Update progress every progress_step rows
            if idx % progress_step == 0 or idx == total_rows - 1:
                progress = (idx + 1) / total_rows * 50  # Use first 50% of progress bar for nav parsing
                self.progress_var.set(progress)
                self.root.update_idletasks()
            try:
                # Parse datetime
                time_val = row[time_col] if time_col in row else row.iloc[time_col]
                dt = self.parse_flexible_datetime(str(time_val))
                
                if dt is None:
                    if idx < 3:
                        self.log(f"Row {idx}: Failed to parse datetime '{time_val}'")
                    continue
                
                # Parse coordinates
                try:
                    lat = float(row[lat_col] if lat_col in row else row.iloc[lat_col])
                    lon = float(row[lon_col] if lon_col in row else row.iloc[lon_col])
                except:
                    if idx < 3:
                        self.log(f"Row {idx}: Failed to parse coordinates")
                    continue
                
                # Parse additional fields
                altitude = None
                if alt_col is not None:
                    try:
                        alt_val = row[alt_col] if alt_col in row else row.iloc[alt_col]
                        altitude = float(alt_val)
                    except:
                        pass
                
                heading = None
                if heading_col is not None:
                    try:
                        head_val = row[heading_col] if heading_col in row else row.iloc[heading_col]
                        heading = float(head_val)
                    except:
                        pass
                
                pitch = None
                if pitch_col is not None:
                    try:
                        pitch_val = row[pitch_col] if pitch_col in row else row.iloc[pitch_col]
                        pitch = float(pitch_val)
                    except:
                        pass
                
                roll = None
                if roll_col is not None:
                    try:
                        roll_val = row[roll_col] if roll_col in row else row.iloc[roll_col]
                        roll = float(roll_val)
                    except:
                        pass
                
                nav_record = {
                    'datetime': dt,
                    'latitude': lat,
                    'longitude': lon,
                    'altitude': altitude,
                    'heading': heading,
                    'pitch': pitch,
                    'roll': roll
                }
                
                nav_data.append(nav_record)
                
                if idx < 3:
                    self.log(f"Row {idx}: Successfully parsed: {nav_record}")
                
            except Exception as e:
                self.log(f"Error parsing flexible row {idx}: {e}")
                if idx < 3:
                    self.log(f"Row {idx} traceback: {traceback.format_exc()}")
                continue
        
        self.log(f"Flexible format parsing complete: {len(nav_data)}/{total_rows} records parsed")
        return nav_data
    
    def analyze_columns(self, df):
        """Analyze DataFrame columns to identify their purpose"""
        analysis = {
            'time_col': None,
            'lat_col': None, 
            'lon_col': None,
            'alt_col': None,
            'heading_col': None,
            'pitch_col': None,
            'roll_col': None
        }
        
        # Check if we have named columns
        if hasattr(df, 'columns'):
            cols = df.columns
            cols_lower = [str(col).lower() for col in cols]
            
            # Time column patterns
            time_patterns = ['time', 'date', 'timestamp', 'datetime']
            for i, col in enumerate(cols_lower):
                if any(pattern in col for pattern in time_patterns):
                    analysis['time_col'] = cols[i]
                    break
            
            # Coordinate patterns
            lat_patterns = ['lat', 'latitude', 'y']
            lon_patterns = ['lon', 'long', 'longitude', 'x']
            
            for i, col in enumerate(cols_lower):
                if any(pattern in col for pattern in lat_patterns) and 'lon' not in col:
                    analysis['lat_col'] = cols[i]
                elif any(pattern in col for pattern in lon_patterns):
                    analysis['lon_col'] = cols[i]
            
            # Attitude patterns
            alt_patterns = ['alt', 'altitude', 'depth', 'z']
            heading_patterns = ['head', 'yaw', 'bearing', 'azimuth']
            pitch_patterns = ['pitch']
            roll_patterns = ['roll']
            
            for i, col in enumerate(cols_lower):
                if any(pattern in col for pattern in alt_patterns):
                    analysis['alt_col'] = cols[i]
                elif any(pattern in col for pattern in heading_patterns):
                    analysis['heading_col'] = cols[i]
                elif any(pattern in col for pattern in pitch_patterns):
                    analysis['pitch_col'] = cols[i]
                elif any(pattern in col for pattern in roll_patterns):
                    analysis['roll_col'] = cols[i]
        
        else:
            # Use column indices for unnamed columns
            if df.shape[1] >= 3:
                analysis['time_col'] = 0
                analysis['lat_col'] = 1
                analysis['lon_col'] = 2
                
                if df.shape[1] > 3:
                    analysis['alt_col'] = 3
                if df.shape[1] > 4:
                    analysis['heading_col'] = 4
                if df.shape[1] > 5:
                    analysis['pitch_col'] = 5
                if df.shape[1] > 6:
                    analysis['roll_col'] = 6
        
        return analysis
    
    def parse_flexible_datetime(self, dt_str):
        """Parse datetime with multiple format attempts"""
        if not dt_str or str(dt_str).lower() in ['nan', 'none', 'null', '']:
            return None
        
        dt_str = str(dt_str).strip()
        
        # Common datetime formats
        formats_to_try = [
            # ISO formats
            '%Y-%m-%dT%H%M%S.%f',  # ISO-like format without colons used by specific AUV systems
            '%Y-%m-%d %H:%M:%S.%f',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%dT%H:%M:%S',
            # US formats
            '%m/%d/%Y %H:%M:%S.%f',
            '%m/%d/%Y %H:%M:%S',
            # European formats
            '%d/%m/%Y %H:%M:%S.%f',
            '%d/%m/%Y %H:%M:%S',
            # Alternative formats
            '%Y/%m/%d %H:%M:%S.%f',
            '%Y/%m/%d %H:%M:%S',
            # Date only (assume midnight)
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%Y/%m/%d',
            # Time formats (Unix timestamp)
            # Will handle separately
        ]
        
        # Try timestamp formats first
        for fmt in formats_to_try:
            try:
                return datetime.strptime(dt_str, fmt)
            except:
                continue
        
        # Try Unix timestamp
        try:
            timestamp = float(dt_str)
            if timestamp > 1e9:  # Reasonable Unix timestamp range
                return datetime.fromtimestamp(timestamp)
        except:
            pass
        
        return None
    
    def parse_lonlat_string(self, lonlat_str):
        """Parse coordinate string like '30N00.99305  87W00.66822'"""
        try:
            parts = lonlat_str.split()
            if len(parts) != 2:
                return None, None
            
            lat_str, lon_str = parts
            
            # Parse latitude (e.g., '30N00.99305')
            if 'N' in lat_str or 'S' in lat_str:
                lat_ref = 'N' if 'N' in lat_str else 'S'
                lat_str = lat_str.replace('N', '').replace('S', '')
                lat_deg = int(lat_str[:2])
                lat_min = float(lat_str[2:])
                lat = lat_deg + lat_min / 60.0
                if lat_ref == 'S':
                    lat = -lat
            else:
                return None, None
            
            # Parse longitude (e.g., '87W00.66822')
            if 'E' in lon_str or 'W' in lon_str:
                lon_ref = 'E' if 'E' in lon_str else 'W'
                lon_str = lon_str.replace('E', '').replace('W', '')
                lon_deg = int(lon_str[:2])
                lon_min = float(lon_str[2:])
                lon = lon_deg + lon_min / 60.0
                if lon_ref == 'W':
                    lon = -lon
            else:
                return None, None
            
            return lat, lon
            
        except Exception as e:
            self.log(f"Error parsing coordinates '{lonlat_str}': {e}")
            return None, None
    
    def load_images(self):
        """Load JPEG images from the selected folder"""
        if not os.path.exists(self.image_folder):
            raise FileNotFoundError(f"Image folder not found: {self.image_folder}")
        
        self.log("Loading images...")
        
        # Find all JPEG files
        jpeg_patterns = ['*.jpg', '*.jpeg', '*.JPG', '*.JPEG']
        self.images = []
        
        for pattern in jpeg_patterns:
            self.images.extend(glob.glob(os.path.join(self.image_folder, pattern)))
        
        self.log(f"Found {len(self.images)} JPEG files")
        
        # Extract datetime from each image
        processed_images = []
        total_images = len(self.images)
        progress_step = max(1, total_images // 100)  # Update every 1% or at least every image
        
        for idx, img_path in enumerate(self.images):
            # Update progress every progress_step images OR every 5th image for responsiveness
            if idx % min(progress_step, 5) == 0 or idx == total_images - 1:
                progress = 50 + (idx + 1) / total_images * 30  # Use 50-80% of progress bar for image loading
                self.progress_var.set(progress)
                self.root.update_idletasks()
            try:
                img_datetime = self.extract_image_datetime(img_path)
                if img_datetime:
                    processed_images.append({
                        'path': img_path,
                        'filename': os.path.basename(img_path),
                        'datetime': img_datetime
                    })
            except Exception as e:
                self.log(f"Error processing {os.path.basename(img_path)}: {e}")
        
        self.images = processed_images
        self.log(f"Loaded {len(self.images)} images with datetime information")
        return len(self.images) > 0
    
    def extract_image_datetime(self, image_path):
        """Extract datetime from image EXIF or filename"""
        try:
            # Try EXIF first
            image = Image.open(image_path)
            exif_data = image._getexif()
            
            if exif_data:
                # Look for datetime tags
                datetime_tags = [36867, 36868, 306]  # DateTimeOriginal, DateTimeDigitized, DateTime
                for tag in datetime_tags:
                    if tag in exif_data:
                        try:
                            dt_str = exif_data[tag]
                            return datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
                        except:
                            continue
            
            # Try to parse from filename if EXIF fails
            filename = os.path.basename(image_path)
            
            # Common timestamp patterns in filenames (Added AUV-specific ISO variant)
            patterns = [
                r'(\d{4}-\d{2}-\d{2}T\d{6}\.\d+)',
                r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})',
                r'(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})',
                r'(\d{8}_\d{6})',
                r'(\d{4}\d{2}\d{2}_\d{6})'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, filename)
                if match:
                    dt_str = match.group(1)
                    for fmt in ['%Y-%m-%dT%H%M%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d_%H-%M-%S', '%Y%m%d_%H%M%S']:
                        try:
                            return datetime.strptime(dt_str, fmt)
                        except:
                            continue
            
            return None
            
        except Exception as e:
            self.log(f"Error extracting datetime from {image_path}: {e}")
            return None
    
    def parse_dive_format(self, file_path):
        """Parse DIVE format navigation file using pandas for robust column handling"""
        try:
            self.log("Parsing DIVE format navigation file...")
            
            # Read as CSV with skipinitialspace and clean column names heavily
            df = pd.read_csv(file_path, low_memory=False, skipinitialspace=True)
            if hasattr(df.columns, 'str'):
                df.columns = df.columns.astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
            
            # Remove the units row (second row) - it contains 'HH:MM:SS.SSS', 'MM/DD/YYYY', etc.
            if len(df) > 0 and str(df.iloc[0].get(df.columns[0], '')).strip() in ['HH:MM:SS.SSS', 'MM/DD/YYYY']:
                df = df.drop(df.index[0]).reset_index(drop=True)
            
            self.log(f"DIVE file columns: {list(df.columns)}")
            self.log(f"DIVE file shape: {df.shape}")
            
            # Show sample of actual data for debugging
            if len(df) > 0:
                self.log("Sample DIVE data (first row):")
                sample_row = df.iloc[0].to_dict()
                for key, value in list(sample_row.items())[:10]:  # Show first 10 columns
                    self.log(f"  {key}: {value}")
            
            nav_data = []
            total_rows = len(df)
            # Initialize progress for navigation parsing
            progress_step = max(1, total_rows // 100)  # Update every 1% or at least every row
            
            for idx, row in df.iterrows():
                # Update progress every progress_step rows
                if idx % progress_step == 0 or idx == total_rows - 1:
                    progress = (idx + 1) / total_rows * 50  # Use first 50% of progress bar for nav parsing
                    self.progress_var.set(progress)
                    self.root.update_idletasks()
                    
                try:
                    # Parse time - handle format like " 1:54:56.900"
                    time_str = str(row.get('Time', '')).strip()
                    date_str = str(row.get('Date', '')).strip()
                    
                    # Skip header/units rows
                    if not time_str or time_str in ['nan', 'HH:MM:SS.SSS', 'Time']:
                        continue
                    
                    # Combine date and time or fall back gracefully
                    if date_str and date_str not in ['nan', 'MM/DD/YYYY', 'Date', '']:
                        datetime_str = f"{date_str} {time_str}"
                    else:
                        datetime_str = time_str
                    
                    dt = self.parse_flexible_datetime(datetime_str)
                    if not dt:
                        continue
                    
                    # Parse coordinates from "Lon/Lat" format like "30N00.99305  87W00.66822"
                    lonlat_str = str(row.get('Lon/Lat', '')).strip()
                    coordinates = self.parse_lonlat_string(lonlat_str)
                    if not coordinates:
                        continue
                    
                    latitude, longitude = coordinates
                    
                    # Extract attitude data using column names directly
                    heading = None
                    pitch = None  
                    roll = None
                    
                    # Extract heading - use the primary Heading column
                    if 'Heading' in df.columns and pd.notna(row.get('Heading')):
                        try:
                            heading = float(row['Heading'])
                        except:
                            pass
                    
                    # Extract pitch - use the primary Pitch column
                    if 'Pitch' in df.columns and pd.notna(row.get('Pitch')):
                        try:
                            pitch = float(row['Pitch'])
                        except:
                            pass
                    
                    # Extract roll - use the primary Roll column
                    if 'Roll' in df.columns and pd.notna(row.get('Roll')):
                        try:
                            roll = float(row['Roll'])
                        except:
                            pass
                    
                    # Extract depth/altitude using column names
                    depth = None
                    altitude = None
                    
                    # Try "Depth of vehicle" first (primary depth column for DIVE format)
                    if 'Depth of vehicle' in df.columns and pd.notna(row.get('Depth of vehicle')):
                        try:
                            depth_val = float(row['Depth of vehicle'])
                            depth = abs(depth_val)  # Make depth positive
                        except:
                            pass
                    elif 'Depth' in df.columns and pd.notna(row.get('Depth')):
                        try:
                            depth_val = float(row['Depth'])  
                            depth = abs(depth_val)  # Make depth positive
                        except:
                            pass
                    
                    # Extract altitude if available
                    if 'Altitude' in df.columns and pd.notna(row.get('Altitude')):
                        try:
                            altitude = float(row['Altitude'])
                        except:
                            pass
                    elif depth is not None:
                        # For underwater vehicles, altitude above seafloor is often related to depth
                        # Use a reasonable default if altitude not available
                        altitude = max(0, depth - 60)  # Assume ~60m depth, so altitude = depth - 60
                    
                    # Create navigation record
                    nav_record = {
                        'datetime': dt,
                        'latitude': latitude,
                        'longitude': longitude,
                        'heading': heading if heading is not None else 0.0,
                        'pitch': pitch if pitch is not None else 0.0,
                        'roll': roll if roll is not None else 0.0,
                        'depth': depth if depth is not None else 0.0,
                        'altitude': altitude if altitude is not None else 0.0
                    }
                    
                    nav_data.append(nav_record)
                    
                except Exception as e:
                    if idx < 5:  # Log first few errors for debugging
                        self.log(f"Error parsing DIVE row {idx}: {e}")
                    continue
            
            self.log(f"Successfully parsed {len(nav_data)} DIVE navigation records")
            
            # Show first parsed record for debugging
            if nav_data:
                first_record = nav_data[0]
                self.log(f"First DIVE record: Time={first_record['datetime']}, Lat={first_record['latitude']:.6f}, Lon={first_record['longitude']:.6f}")
                self.log(f"  Attitude: H={first_record['heading']:.3f}°, P={first_record['pitch']:.3f}°, R={first_record['roll']:.3f}°")
                self.log(f"  Position: Depth={first_record['depth']:.3f}m, Alt={first_record['altitude']:.3f}m")
            
            return nav_data
            
        except Exception as e:
            self.log(f"Error parsing DIVE format: {e}")
            self.log(f"Full error: {traceback.format_exc()}")
            return []
    
    def parse_dive_header(self, header_lines):
        """Parse DIVE format header to find column positions"""
        column_map = {}
        
        try:
            # The first header line contains the column names
            if len(header_lines) > 0:
                first_line = header_lines[0]
                column_names = [name.strip() for name in first_line.split(',')]
                
                # Map column names to their positions
                for i, name in enumerate(column_names):
                    if name:  # Skip empty column names
                        column_map[name] = i
                        
                    # Map specific column names (exact matches to avoid conflicts)
                    if name == 'Heading':
                        column_map['Heading'] = i
                    elif name == 'Pitch':
                        column_map['Pitch'] = i
                    elif name == 'Roll':
                        column_map['Roll'] = i
                    elif name == 'Depth of vehicle':
                        column_map['Depth of vehicle'] = i
                    elif name == 'Depth' and 'Depth of vehicle' not in column_map:
                        column_map['Depth'] = i
                    elif name == 'Altitude':
                        column_map['Altitude'] = i
                
                self.log(f"Found columns: {list(column_map.keys())}")
                
                # Log attitude column positions if found
                attitude_cols = []
                for col_name in ['Heading', 'Pitch', 'Roll']:
                    if col_name in column_map:
                        attitude_cols.append(f"{col_name}: col {column_map[col_name]}")
                
                if attitude_cols:
                    self.log(f"Attitude columns: {', '.join(attitude_cols)}")
                else:
                    self.log("WARNING: No attitude columns found in header")
                
                # Log depth-related columns if found
                depth_cols = []
                for col_name in ['Depth of vehicle', 'Depth', 'depth']:
                    if col_name in column_map:
                        depth_cols.append(f"{col_name}: col {column_map[col_name]}")
                
                if depth_cols:
                    self.log(f"Depth columns: {', '.join(depth_cols)}")
                else:
                    self.log("WARNING: No depth columns found in header")
                    
        except Exception as e:
            self.log(f"Error parsing DIVE header: {e}")
        
        return column_map
    
    def parse_phins_format(self, file_path):
        """Parse PHINS INS format navigation file"""
        try:
            self.log("Parsing PHINS INS format navigation file...")
            
            # Read as CSV and clean column names
            df = pd.read_csv(file_path, low_memory=False, skipinitialspace=True)
            if hasattr(df.columns, 'str'):
                df.columns = df.columns.astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
            
            self.log(f"PHINS file columns: {list(df.columns)}")
            self.log(f"PHINS file shape: {df.shape}")
            
            nav_data = []
            total_rows = len(df)
            # Initialize progress for navigation parsing
            progress_step = max(1, total_rows // 100)  # Update every 1% or at least every row
            
            for idx, row in df.iterrows():
                # Update progress every progress_step rows
                if idx % progress_step == 0 or idx == total_rows - 1:
                    progress = (idx + 1) / total_rows * 50  # Use first 50% of progress bar for nav parsing
                    self.progress_var.set(progress)
                    self.root.update_idletasks()
                    
                try:
                    # Parse time - it's in HH:MM:SS.S format
                    time_str = str(row['time']).strip()
                    
                    # Use first row's date as a base (we might need to handle date differently)
                    # For now, use a default date - this might need adjustment
                    base_date = datetime.now().date()
                    
                    # Parse time
                    dt = None
                    try:
                        time_part = datetime.strptime(time_str, '%H:%M:%S.%f').time()
                        dt = datetime.combine(base_date, time_part)
                    except:
                        try:
                            time_part = datetime.strptime(time_str, '%H:%M:%S').time()
                            dt = datetime.combine(base_date, time_part)
                        except:
                            continue
                    
                    # Extract coordinates and attitude
                    lat = float(row['latitude'])
                    lon = float(row['longitude'])
                    heading = float(row['heading'])
                    pitch = float(row['pitch'])
                    roll = float(row['roll'])
                    
                    # Extract depth and altitude if available
                    depth = None
                    altitude = None
                    
                    # Try to get depth from available columns
                    if 'depth' in row and pd.notna(row['depth']):
                        depth = float(row['depth'])
                    elif 'phins_depth' in row and pd.notna(row['phins_depth']):
                        depth = float(row['phins_depth'])
                    
                    # For underwater vehicles, altitude might be calculated as negative depth
                    # or might be available as a separate field
                    if 'altitude' in row and pd.notna(row['altitude']):
                        altitude = float(row['altitude'])
                    elif depth is not None:
                        # For AUV, altitude above seafloor might be calculated differently
                        # For now, we'll use depth as the primary measurement
                        altitude = depth  # This might need adjustment based on your specific needs
                    
                    nav_data.append({
                        'datetime': dt,
                        'latitude': lat,
                        'longitude': lon,
                        'heading': heading,
                        'pitch': pitch,
                        'roll': roll,
                        'depth': depth if depth is not None else 0.0,
                        'altitude': altitude if altitude is not None else 0.0
                    })
                    
                except Exception as e:
                    if idx < 5:  # Log first few errors
                        self.log(f"Error parsing PHINS row {idx}: {e}")
                    continue
            
            self.log(f"Successfully parsed {len(nav_data)} PHINS navigation records")
            return nav_data
            
        except Exception as e:
            self.log(f"Error parsing PHINS format: {e}")
            return []
    
    def parse_nav_state_format(self, file_path):
        """Parse NAV_STATE format navigation file"""
        try:
            self.log("Parsing NAV_STATE format navigation file...")
            
            # Read as CSV and clean column names
            df = pd.read_csv(file_path, low_memory=False, skipinitialspace=True)
            if hasattr(df.columns, 'str'):
                df.columns = df.columns.astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
            
            self.log(f"NAV_STATE file columns: {list(df.columns)}")
            self.log(f"NAV_STATE file shape: {df.shape}")
            
            nav_data = []
            total_rows = len(df)
            # Initialize progress for navigation parsing
            progress_step = max(1, total_rows // 100)  # Update every 1% or at least every row
            
            for idx, row in df.iterrows():
                # Update progress every progress_step rows
                if idx % progress_step == 0 or idx == total_rows - 1:
                    progress = (idx + 1) / total_rows * 50  # Use first 50% of progress bar for nav parsing
                    self.progress_var.set(progress)
                    self.root.update_idletasks()
                    
                try:
                    # Parse Unix timestamp
                    timestamp = float(row['secs_since_1970'])
                    dt = datetime.fromtimestamp(timestamp)
                    
                    # Extract coordinates and attitude
                    lat = float(row['latitude'])
                    lon = float(row['longitude'])
                    heading = float(row['heading_degs'])
                    pitch = float(row['pitch_degs'])
                    roll = float(row['roll_degs'])
                    
                    # Extract depth and altitude if available
                    depth = None
                    altitude = None
                    
                    # Try to get depth and altitude from available columns
                    if 'depth' in row and pd.notna(row['depth']):
                        depth = float(row['depth'])
                    elif 'depth_m' in row and pd.notna(row['depth_m']):
                        depth = float(row['depth_m'])
                    
                    if 'altitude' in row and pd.notna(row['altitude']):
                        altitude = float(row['altitude'])
                    elif 'altitude_m' in row and pd.notna(row['altitude_m']):
                        altitude = float(row['altitude_m'])
                    elif 'height' in row and pd.notna(row['height']):
                        altitude = float(row['height'])
                    
                    nav_data.append({
                        'datetime': dt,
                        'latitude': lat,
                        'longitude': lon,
                        'heading': heading,
                        'pitch': pitch,
                        'roll': roll,
                        'depth': depth if depth is not None else 0.0,
                        'altitude': altitude if altitude is not None else 0.0
                    })
                    
                except Exception as e:
                    if idx < 5:  # Log first few errors
                        self.log(f"Error parsing NAV_STATE row {idx}: {e}")
                    continue
            
            self.log(f"Successfully parsed {len(nav_data)} NAV_STATE navigation records")
            return nav_data
            
        except Exception as e:
            self.log(f"Error parsing NAV_STATE format: {e}")
            return []
    
    def match_navigation_to_images(self):
        """Match navigation data to images based on timestamp"""
        self.log("Matching navigation data to images...")
        
        matched_pairs = []
        tolerance = timedelta(seconds=self.time_tolerance_var.get())
        
        total_images = len(self.images)
        progress_step = max(1, total_images // 100)  # Update every 1% or at least every image
        
        for idx, img in enumerate(self.images):
            # Update progress every progress_step images OR every 10th image to maintain responsiveness
            if idx % min(progress_step, 10) == 0 or idx == total_images - 1:
                progress = 80 + (idx + 1) / total_images * 20  # Use 80-100% of progress bar for matching
                self.progress_var.set(progress)
                self.root.update_idletasks()
                
            best_match = None
            best_diff = None
            
            for nav in self.nav_data:
                time_diff = abs(img['datetime'] - nav['datetime'])
                if time_diff <= tolerance:
                    if best_match is None or time_diff < best_diff:
                        best_match = nav
                        best_diff = time_diff
            
            if best_match:
                matched_pairs.append({
                    'image': img,
                    'navigation': best_match,
                    'time_diff': best_diff
                })
        
        return matched_pairs

    def export_csv_reference(self, matched_pairs):
        """Export CSV file with image/navigation pairing for Agisoft reference"""
        try:
            # Determine output directory
            if self.overwrite_var.get():
                # If overwriting, save CSV to image folder
                csv_output_dir = self.image_folder
            else:
                # Save to output folder
                csv_output_dir = self.output_folder
                # Create output directory if it doesn't exist
                os.makedirs(csv_output_dir, exist_ok=True)
            
            csv_path = os.path.join(csv_output_dir, "Agisoft_Reference_Information.csv")
            
            self.log(f"Exporting CSV reference file to: {csv_path}")
            
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['image_name', 'latitude', 'longitude', 'depth', 'altitude', 'heading', 'pitch', 'roll', 'timestamp', 'time_diff_seconds']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write header
                writer.writeheader()
                
                # Write data rows
                for pair in matched_pairs:
                    nav = pair['navigation']
                    img = pair['image']
                    
                   
                    row = {
                        'image_name': os.path.basename(img['path']),
                        'latitude': nav.get('latitude', ''),
                        'longitude': nav.get('longitude', ''),
                        'depth': nav.get('depth', ''),
                        'altitude': nav.get('altitude', ''),
                        'heading': nav.get('heading', ''),
                        'pitch': nav.get('pitch', ''),
                        'roll': nav.get('roll', ''),
                        'timestamp': nav['datetime'].strftime('%Y-%m-%d %H:%M:%S.%f') if nav['datetime'] else '',
                        'time_diff_seconds': f"{pair['time_diff'].total_seconds():.3f}"
                    }
                    
                    writer.writerow(row)
            
            self.log(f"Successfully exported {len(matched_pairs)} image/navigation pairs to CSV")
            return csv_path
            
        except Exception as e:
            self.log(f"Error exporting CSV reference file: {e}")
            return None
    
    def load_and_preview(self):
        """Load data and show preview"""
        if not self.image_folder or not self.nav_file:
            messagebox.showerror("Error", "Please select both image folder and navigation file")
            return
        
        # Check output directory if not overwriting
        if not self.overwrite_var.get() and not self.output_folder:
            messagebox.showerror("Error", "Please select an output directory or enable overwrite mode")
            return
        
        # Run loading in background thread to prevent GUI freezing
        thread = threading.Thread(target=self._load_and_preview_thread)
        thread.daemon = True
        thread.start()
    
    def _load_and_preview_thread(self):
        """Background thread for loading and preview to prevent GUI freezing"""
        try:
            self.clear_preview()
            
            # Initialize progress bar
            self.progress_var.set(0)
            self.root.update_idletasks()
            
            # Load navigation data (0-50% progress)
            self.log("Step 1/3: Loading navigation data...")
            self.status_var.set("Loading navigation data...")
            if not self.load_navigation_data():
                self.progress_var.set(0)  # Reset on failure
                return
            
            # Load images (50-80% progress)
            self.log("Step 2/3: Loading and processing images...")
            self.status_var.set("Loading images...")
            if not self.load_images():
                messagebox.showerror("Error", "No images with datetime information found")
                self.progress_var.set(0)  # Reset on failure
                return
            
            # Match navigation to images (80-100% progress)
            self.log("Step 3/3: Matching navigation data to images...")
            self.status_var.set("Matching navigation to images...")
            matched_pairs = self.match_navigation_to_images()
            
            # Show preview
            self.log("\n" + "="*60)
            self.log("PREVIEW OF MATCHED DATA")
            self.log("="*60)
            self.log(f"Total images: {len(self.images)}")
            self.log(f"Navigation records: {len(self.nav_data)}")
            self.log(f"Matched pairs: {len(matched_pairs)}")
            
            if len(matched_pairs) == 0:
                self.log("\nWARNING: No images matched with navigation data!")
                self.log("Check your time tolerance setting or verify timestamps.")
                return
            
            # Show 25 matches from the middle of the dataset
            total_matches = len(matched_pairs)
            start_idx = max(0, (total_matches - 25) // 2)
            end_idx = min(total_matches, start_idx + 25)
            
            self.log(f"\nShowing 25 matches from middle of dataset (matches {start_idx+1}-{end_idx}):")
            for i, pair in enumerate(matched_pairs[start_idx:end_idx]):
                img = pair['image']
                nav = pair['navigation']
                time_diff = pair['time_diff']
                
                self.log(f"\n{start_idx + i + 1}. {img['filename']}")
                self.log(f"   Image time: {img['datetime']}")
                self.log(f"   Nav time:   {nav['datetime']}")
                self.log(f"   Time diff:  {time_diff.total_seconds():.1f}s")
                
                attitude_info = []
                if nav['pitch'] is not None:
                    attitude_info.append(f"Pitch: {nav['pitch']:.1f}°")
                if nav['roll'] is not None:
                    attitude_info.append(f"Roll: {nav['roll']:.1f}°")
                if nav['heading'] is not None:
                    attitude_info.append(f"Heading: {nav['heading']:.1f}°")
                
                if attitude_info:
                    self.log(f"   Attitude:   {', '.join(attitude_info)}")
                else:
                    self.log(f"   Attitude:   No attitude data available")
            
            # Export CSV reference file
            self.log("\n" + "="*60)
            self.log("EXPORTING CSV REFERENCE FILE")
            self.log("="*60)
            csv_path = self.export_csv_reference(matched_pairs)
            if csv_path:
                self.log(f"CSV reference file saved: {csv_path}")
                self.log("This file contains image/navigation pairing data for Agisoft Metashape reference.")
            else:
                self.log("Failed to export CSV reference file")
            
            self.matched_pairs = matched_pairs
            
            # Set progress to 100% and log completion
            self.progress_var.set(100)
            self.log("\n" + "="*60)
            self.log("LOAD AND PREVIEW COMPLETE")
            self.log("="*60)
            self.status_var.set("Preview complete")
            self.root.update_idletasks()
            
        except Exception as e:
            self.progress_var.set(0)  # Reset progress on error
            self.status_var.set("Error occurred")
            messagebox.showerror("Error", f"Error during preview: {e}")
            self.log(f"Error: {e}")
    
    def load_and_process_all(self):
        """All-in-one function: Load navigation data, match to images, and process all in one step"""
        if not self.image_folder or not self.nav_file:
            messagebox.showerror("Error", "Please select both image folder and navigation file")
            return
        
        # Check output directory if not overwriting
        if not self.overwrite_var.get() and not self.output_folder:
            messagebox.showerror("Error", "Please select an output directory or enable overwrite mode")
            return
        
        # Ask for confirmation with processing details
        total_cores = mp.cpu_count()
        selected_cores = self.cpu_cores_var.get()
        mode = "OVERWRITE MODE" if self.overwrite_var.get() else "SAFE MODE (copying to output)"
        
        confirm_msg = (f"Load navigation data, match to images, and process all?\n\n"
                      f"Processing Mode: {mode}\n"
                      f"CPU Cores: {selected_cores}/{total_cores}\n"
                      f"Batch Size: {self.batch_size_var.get()} images\n\n"
                      f"This will combine Load & Preview + Process Images into one operation.")
        
        if not messagebox.askyesno("Confirm All-in-One Processing", confirm_msg):
            return
        
        # Run all-in-one processing in background thread
        thread = threading.Thread(target=self._load_and_process_all_thread)
        thread.daemon = True
        thread.start()
    
    def _load_and_process_all_thread(self):
        """Background thread for all-in-one processing"""
        try:
            self.clear_preview()
            
            # Initialize progress bar
            self.progress_var.set(0)
            self.root.update_idletasks()
            
            self.log("="*60)
            self.log("ALL-IN-ONE PROCESSING STARTED")
            self.log("="*60)
            
            # Phase 1: Load navigation data (0-25% progress)
            self.log("Phase 1/4: Loading navigation data...")
            self.status_var.set("Phase 1/4: Loading navigation...")
            if not self.load_navigation_data_for_processing():
                self.progress_var.set(0)
                return
            
            # Phase 2: Load images (25-50% progress)  
            self.log("Phase 2/4: Loading and processing images...")
            self.status_var.set("Phase 2/4: Loading images...")
            if not self.load_images_for_processing():
                messagebox.showerror("Error", "No images with datetime information found")
                self.progress_var.set(0)
                return
            
            # Phase 3: Match navigation to images (50-60% progress)
            self.log("Phase 3/4: Matching navigation data to images...")
            self.status_var.set("Phase 3/4: Matching data...")
            matched_pairs = self.match_navigation_to_images_for_processing()
            
            if len(matched_pairs) == 0:
                self.log("ERROR: No images matched with navigation data!")
                self.log("Check your time tolerance setting or verify timestamps.")
                messagebox.showerror("Error", "No images matched with navigation data!")
                self.progress_var.set(0)
                return
            
            self.log(f"Successfully matched {len(matched_pairs)} image/navigation pairs")
            self.matched_pairs = matched_pairs
            
            # Phase 4: Process all images (60-100% progress)
            self.log("Phase 4/4: Processing all images with attitude data...")
            self.status_var.set("Phase 4/4: Processing images...")
            self._process_all_images_with_progress()
            
        except Exception as e:
            self.progress_var.set(0)
            self.status_var.set("Error occurred")
            messagebox.showerror("Error", f"Error during all-in-one processing: {e}")
            self.log(f"Fatal error: {e}")
    
    def load_navigation_data_for_processing(self):
        """Load navigation data with progress 0-25% for all-in-one processing"""
        # Temporarily modify progress calculation for this phase
        original_load_nav = self.load_navigation_data
        
        def modified_progress_update(idx, total_rows, base_progress=0, max_progress=25):
            if idx % max(1, total_rows // 100) == 0 or idx == total_rows - 1:
                progress = base_progress + (idx + 1) / total_rows * max_progress
                self.progress_var.set(progress)
                self.root.update_idletasks()
        
        # Override progress updates in parsing functions temporarily
        self._current_progress_updater = modified_progress_update
        result = self.load_navigation_data()
        self._current_progress_updater = None
        return result
    
    def load_images_for_processing(self):
        """Load images with progress 25-50% for all-in-one processing"""
        # Use existing load_images but adjust progress range
        if not os.path.exists(self.image_folder):
            raise FileNotFoundError(f"Image folder not found: {self.image_folder}")
        
        self.log("Loading images...")
        
        # Find all JPEG files
        jpeg_patterns = ['*.jpg', '*.jpeg', '*.JPG', '*.JPEG']
        self.images = []
        
        for pattern in jpeg_patterns:
            self.images.extend(glob.glob(os.path.join(self.image_folder, pattern)))
        
        self.log(f"Found {len(self.images)} JPEG files")
        
        # Extract datetime from each image with 25-50% progress
        processed_images = []
        total_images = len(self.images)
        progress_step = max(1, total_images // 100)
        
        for idx, img_path in enumerate(self.images):
            if idx % progress_step == 0 or idx == total_images - 1:
                progress = 25 + (idx + 1) / total_images * 25  # 25-50% range
                self.progress_var.set(progress)
                self.root.update_idletasks()
                
            try:
                img_datetime = self.extract_image_datetime(img_path)
                if img_datetime:
                    processed_images.append({
                        'path': img_path,
                        'filename': os.path.basename(img_path),
                        'datetime': img_datetime
                    })
            except Exception as e:
                self.log(f"Error processing {img_path}: {e}")
                continue
        
        self.images = processed_images
        self.log(f"Loaded {len(self.images)} images with datetime information")
        return len(self.images) > 0
    
    def match_navigation_to_images_for_processing(self):
        """Match navigation to images with progress 50-60% for all-in-one processing"""
        self.log("Matching navigation data to images...")
        
        matched_pairs = []
        tolerance = timedelta(seconds=self.time_tolerance_var.get())
        
        total_images = len(self.images)
        progress_step = max(1, total_images // 100)
        
        for idx, img in enumerate(self.images):
            # Update progress more frequently for responsiveness (every 5th image minimum)
            if idx % min(progress_step, 5) == 0 or idx == total_images - 1:
                progress = 50 + (idx + 1) / total_images * 10  # 50-60% range
                self.progress_var.set(progress)
                self.root.update_idletasks()
                
            best_match = None
            best_diff = None
            
            for nav in self.nav_data:
                time_diff = abs(img['datetime'] - nav['datetime'])
                if time_diff <= tolerance:
                    if best_match is None or time_diff < best_diff:
                        best_match = nav
                        best_diff = time_diff
            
            if best_match:
                matched_pairs.append({
                    'image': img,
                    'navigation': best_match,
                    'time_diff': best_diff
                })
        
        return matched_pairs
    
    def _process_all_images_with_progress(self):
        """Process all matched images with progress 60-100%"""
        total_pairs = len(self.matched_pairs)
        cpu_cores = self.cpu_cores_var.get()
        
        mode_text = "OVERWRITE MODE" if self.overwrite_var.get() else "SAFE MODE (COPYING TO OUTPUT)"
        
        self.log(f"Processing {total_pairs} images - {mode_text}")
        self.log(f"Using {cpu_cores} CPU cores")
        
        if not self.overwrite_var.get():
            os.makedirs(self.output_folder, exist_ok=True)
        
        success_count = 0
        error_count = 0
        
        # Use parallel processing if more than 10 images, otherwise sequential
        if total_pairs > 10:
            # Parallel processing with progress 60-100%
            batch_size = self.batch_size_var.get()
            processed_count = 0
            
            for batch_start in range(0, total_pairs, batch_size):
                batch_end = min(batch_start + batch_size, total_pairs)
                batch_pairs = self.matched_pairs[batch_start:batch_end]
                
                # Create tasks for this batch
                tasks = []
                for pair in batch_pairs:
                    img = pair['image']
                    nav = pair['navigation']
                    
                    if self.overwrite_var.get():
                        output_path = img['path']
                    else:
                        rel_path = os.path.relpath(img['path'], self.image_folder)
                        output_path = os.path.join(self.output_folder, rel_path)
                    
                    tasks.append({
                        'image_path': img['path'],
                        'filename': img['filename'],
                        'nav_data': nav,
                        'output_path': output_path,
                        'overwrite_original': self.overwrite_var.get()
                    })
                
                # Process batch
                batch_results = self.process_batch_parallel(tasks, cpu_cores)
                
                # Update counters and progress
                for result in batch_results:
                    if result['success']:
                        success_count += 1
                    else:
                        error_count += 1
                    processed_count += 1
                
                # Update progress (60-100% range)
                progress = 60 + (processed_count / total_pairs) * 40
                self.progress_var.set(progress)
                self.root.update_idletasks()
                
                self.log(f"Processed batch: {batch_start+1}-{batch_end} ({processed_count}/{total_pairs} total)")
        
        else:
            # Sequential processing for small datasets
            for i, pair in enumerate(self.matched_pairs):
                img = pair['image']
                nav = pair['navigation']
                
                try:
                    if self.apply_attitude_to_image(img['path'], nav):
                        success_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    self.log(f"Error processing {img['filename']}: {e}")
                    error_count += 1
                
                # Update progress (60-100% range)
                progress = 60 + ((i + 1) / total_pairs) * 40
                self.progress_var.set(progress)
                self.root.update_idletasks()
        
        # Final results
        self.progress_var.set(100)
        self.log("\n" + "="*60)
        self.log("ALL-IN-ONE PROCESSING COMPLETE")
        self.log(f"Successfully processed: {success_count}")
        self.log(f"Errors: {error_count}")
        if not self.overwrite_var.get():
            self.log(f"Processed images saved to: {self.output_folder}")
        self.log("="*60)
        self.status_var.set("Processing complete")
        
        # Show completion message
        completion_msg = (f"All-in-one processing complete!\n"
                         f"Successfully processed: {success_count}\n"
                         f"Errors: {error_count}")
        if not self.overwrite_var.get():
            completion_msg += f"\n\nProcessed images saved to:\n{self.output_folder}"
        
        messagebox.showinfo("All-in-One Processing Complete", completion_msg)
    
    def process_images(self):
        """Process images and apply attitude parameters"""
        if not hasattr(self, 'matched_pairs') or not self.matched_pairs:
            messagebox.showerror("Error", "Please load and preview data first")
            return
        
        # Check output directory if not overwriting
        if not self.overwrite_var.get() and not self.output_folder:
            messagebox.showerror("Error", "Please select an output directory or enable overwrite mode")
            return
        
        total_images = len(self.matched_pairs)
        cpu_cores = self.cpu_cores_var.get()
        
        # Ask user to confirm and choose processing method
        if total_images > 50:
            # For large datasets, recommend parallel processing
            choice = messagebox.askyesnocancel(
                "Processing Method", 
                f"Process {total_images} images?\n\n"
                f"• YES: Use parallel processing ({cpu_cores} cores) - FASTER\n"
                f"• NO: Use sequential processing - SAFER\n"
                f"• CANCEL: Abort"
            )
            if choice is None:  # Cancel
                return
            use_parallel = choice
        else:
            # For small datasets, just confirm
            if self.overwrite_var.get():
                confirm_msg = f"This will OVERWRITE {total_images} original images. Continue?"
            else:
                confirm_msg = f"This will process {total_images} images and save copies to:\n{self.output_folder}\n\nContinue?"
            
            if not messagebox.askyesno("Confirm", confirm_msg):
                return
            use_parallel = total_images > 10  # Use parallel for more than 10 images
        
        # Run processing in separate thread to avoid freezing GUI
        if use_parallel:
            thread = threading.Thread(target=self._process_images_parallel_thread)
        else:
            thread = threading.Thread(target=self._process_images_thread)
        
        thread.daemon = True
        thread.start()
    
    def _process_images_thread(self):
        """Process images in background thread (original sequential version)"""
        try:
            self.log("\n" + "="*60)
            mode_text = "OVERWRITE MODE" if self.overwrite_var.get() else "SAFE MODE (COPYING TO OUTPUT)"
            self.log(f"PROCESSING IMAGES (SEQUENTIAL) - {mode_text}")
            self.log("="*60)
            
            if not self.overwrite_var.get():
                self.log(f"Output directory: {self.output_folder}")
                # Create output directory if it doesn't exist
                os.makedirs(self.output_folder, exist_ok=True)
            
            total_pairs = len(self.matched_pairs)
            success_count = 0
            error_count = 0
            
            for i, pair in enumerate(self.matched_pairs):
                try:
                    img = pair['image']
                    nav = pair['navigation']
                    
                    self.log(f"\nProcessing {i+1}/{total_pairs}: {img['filename']}")
                    
                    # Determine output path
                    if self.overwrite_var.get():
                        output_path = None
                        self.log(f"  Modifying original: {img['path']}")
                    else:
                        output_path = os.path.join(self.output_folder, img['filename'])
                        self.log(f"  Copying to: {output_path}")
                    
                    if self.apply_attitude_to_image(img['path'], nav, output_path):
                        success_count += 1
                        self.log(f"  ✓ Successfully updated - H:{nav.get('heading', 0):.1f}° P:{nav.get('pitch', 0):.1f}° R:{nav.get('roll', 0):.1f}°")
                    else:
                        error_count += 1
                        self.log(f"  ✗ Failed to update")
                    
                    # Update progress
                    progress = (i + 1) / total_pairs * 100
                    self.progress_var.set(progress)
                    
                except Exception as e:
                    error_count += 1
                    self.log(f"  ✗ Error: {e}")
            
            self.log(f"\n" + "="*60)
            self.log("SEQUENTIAL PROCESSING COMPLETE")
            self.log(f"Successfully updated: {success_count}")
            self.log(f"Errors: {error_count}")
            if not self.overwrite_var.get():
                self.log(f"Processed images saved to: {self.output_folder}")
            self.log("="*60)
            
            # Show completion message
            completion_msg = f"Processing complete!\nSuccess: {success_count}\nErrors: {error_count}"
            if not self.overwrite_var.get():
                completion_msg += f"\n\nProcessed images saved to:\n{self.output_folder}"
            messagebox.showinfo("Complete", completion_msg)
            
        except Exception as e:
            self.log(f"Fatal error during processing: {e}")
            messagebox.showerror("Error", f"Fatal error: {e}")
    
    def apply_attitude_to_image(self, image_path, nav_data, output_path=None):
        """Apply attitude parameters to image EXIF"""
        try:
            # Determine the target path
            if output_path and not self.overwrite_var.get():
                # Copy to output directory first
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                shutil.copy2(image_path, output_path)
                target_path = output_path
            else:
                # Process original file directly
                target_path = image_path
            
            # Apply attitude data to the target file using XMP implementation
            return write_attitude_to_image_worker(target_path, nav_data)
            
        except Exception as e:
            self.log(f"Error applying attitude to {image_path}: {e}")
            return False
    
    
    def _process_images_parallel_thread(self):
        """Process images in background thread with parallel processing"""
        try:
            self.log("\n" + "="*60)
            mode_text = "OVERWRITE MODE" if self.overwrite_var.get() else "SAFE MODE (COPYING TO OUTPUT)"
            self.log(f"PROCESSING IMAGES WITH PARALLEL PROCESSING - {mode_text}")
            self.log("="*60)
            
            if not self.overwrite_var.get():
                self.log(f"Output directory: {self.output_folder}")
                # Create output directory if it doesn't exist
                os.makedirs(self.output_folder, exist_ok=True)
            
            total_pairs = len(self.matched_pairs)
            cpu_cores = self.cpu_cores_var.get()
            batch_size = self.batch_size_var.get()
            
            self.log(f"System info: {mp.cpu_count()} CPU cores available")
            self.log(f"Using {cpu_cores} CPU cores for parallel processing")
            self.log(f"Processing in batches of {batch_size} images")
            self.log(f"Fast I/O mode: {'enabled' if self.fast_io_var.get() else 'disabled'}")
            
            success_count = 0
            error_count = 0
            processed_count = 0
            
            start_time = time.time()
            
            # Process in batches to manage memory and provide progress updates
            for batch_start in range(0, total_pairs, batch_size):
                batch_end = min(batch_start + batch_size, total_pairs)
                batch_pairs = self.matched_pairs[batch_start:batch_end]
                
                self.log(f"\nProcessing batch {batch_start//batch_size + 1}: images {batch_start+1}-{batch_end}")
                
                # Prepare data for parallel processing
                tasks = []
                for pair in batch_pairs:
                    # Determine output path for each image
                    if self.overwrite_var.get():
                        output_path = pair['image']['path']  # Same as input when overwriting
                    else:
                        output_path = os.path.join(self.output_folder, pair['image']['filename'])
                    
                    tasks.append({
                        'image_path': pair['image']['path'],
                        'filename': pair['image']['filename'],
                        'nav_data': pair['navigation'],
                        'output_path': output_path,
                        'overwrite_original': self.overwrite_var.get()
                    })
                
                # Process batch in parallel
                batch_results = self.process_batch_parallel(tasks, cpu_cores)
                
                # Update counters and progress
                for result in batch_results:
                    processed_count += 1
                    if result['success']:
                        success_count += 1
                        self.log(f"  ✓ {result['filename']}: {result['message']}")
                    else:
                        error_count += 1
                        self.log(f"  ✗ {result['filename']}: {result['message']}")
                    
                    # Update progress bar
                    progress = processed_count / total_pairs * 100
                    self.progress_var.set(progress)
                    self.root.update_idletasks()
                
                # Show batch completion with performance metrics
                elapsed = time.time() - start_time
                avg_time = elapsed / processed_count if processed_count > 0 else 0
                remaining = (total_pairs - processed_count) * avg_time
                images_per_sec = processed_count / elapsed if elapsed > 0 else 0
                
                self.log(f"Batch complete. Progress: {processed_count}/{total_pairs} "
                        f"({progress:.1f}%) - Rate: {images_per_sec:.1f} img/sec - "
                        f"Est. remaining: {remaining/60:.1f} min")
            
            total_time = time.time() - start_time
            
            self.log(f"\n" + "="*60)
            self.log("PARALLEL PROCESSING COMPLETE")
            self.log(f"Total time: {total_time/60:.1f} minutes")
            self.log(f"Average time per image: {total_time/total_pairs:.2f} seconds")
            self.log(f"Successfully updated: {success_count}")
            self.log(f"Errors: {error_count}")
            if not self.overwrite_var.get():
                self.log(f"Processed images saved to: {self.output_folder}")
            self.log("="*60)
            
            # Show completion message
            completion_msg = (f"Parallel processing complete!\n"
                              f"Time: {total_time/60:.1f} minutes\n"
                              f"Success: {success_count}\nErrors: {error_count}")
            if not self.overwrite_var.get():
                completion_msg += f"\n\nProcessed images saved to:\n{self.output_folder}"
            
            messagebox.showinfo("Complete", completion_msg)
            
        except Exception as e:
            self.log(f"Fatal error during parallel processing: {e}")
            self.log(f"Full error: {traceback.format_exc()}")
            messagebox.showerror("Error", f"Fatal error: {e}")
    
    def process_batch_parallel(self, tasks, cpu_cores):
        """Process a batch of images in parallel"""
        results = []
        
        try:
            # Use ProcessPoolExecutor for CPU-intensive tasks
            with ProcessPoolExecutor(max_workers=cpu_cores) as executor:
                # Submit all tasks
                future_to_task = {
                    executor.submit(process_single_image_worker, task): task 
                    for task in tasks
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    try:
                        result = future.result(timeout=30)  # 30 second timeout per image
                        results.append(result)
                    except Exception as e:
                        results.append({
                            'filename': task['filename'],
                            'success': False,
                            'message': f"Processing error: {str(e)}"
                        })
                        
        except Exception as e:
            # Fallback to sequential processing if parallel fails
            self.log(f"Parallel processing failed, falling back to sequential: {e}")
            for task in tasks:
                try:
                    result = process_single_image_worker(task)
                    results.append(result)
                except Exception as ex:
                    results.append({
                        'filename': task['filename'],
                        'success': False,
                        'message': f"Sequential fallback error: {str(ex)}"
                    })
        
        return results
    
    def run(self):
        """Run the application"""
        self.root.mainloop()

def main():
    """Main function"""
    app = AttitudeEXIFWriter()
    app.run()

if __name__ == "__main__":
    main()