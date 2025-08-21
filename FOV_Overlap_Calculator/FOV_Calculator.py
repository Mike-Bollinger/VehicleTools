#!/usr/bin/env python3
"""
AUV FOV Calculator - Standalone Python GUI Version
Converted from R script by Mike Bollinger
Original R version: 9/2020
Python GUI version: 2025

This is a standalone script that requires only standard Python libraries
and matplotlib for plotting.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import math
import sys

# Try to import matplotlib, provide fallback if not available
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.figure as mfig
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not available. Plots will be disabled.")

class FOVCalculatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AUV FOV Calculator")
        self.root.geometry("1400x700")
        
        # Camera configurations dictionary (extracted from R script)
        self.camera_configs = {
            "VOYIS Recon LS": {
                "HFOV": 56,
                "VFOV": 42,
                "ImageColumns": 4096,
                "ImageRows": 3008,
                "HorizontalOverlap": 80,
                "VerticalOverlap": 80,
                "ImageSize": 25  # MB
            },
            "Micro UUV 6.3MP": {
                "DFOV": 49,
                "HFOV": "x",
                "VFOV": "x",
                "ImageColumns": 3072,
                "ImageRows": 2048,
                "SensorWidth": 7.11,
                "SensorHeight": 5.33,
                "HorizontalOverlap": 75,
                "VerticalOverlap": 75,
                "ImageSize": 10  # MB estimate
            },
            "Micro UUV 12MP": {
                "DFOV": 51,
                "HFOV": "x",
                "VFOV": "x",
                "ImageColumns": 4096,
                "ImageRows": 3000,
                "SensorWidth": 14.10,
                "SensorHeight": 10.30,
                "HorizontalOverlap": 80,
                "VerticalOverlap": 80,
                "ImageSize": 15  # MB estimate
            },
            "Nikon D780": {
                "DFOV": 84.1,
                "HFOV": 73.7,
                "VFOV": 53.1,
                "ImageColumns": 6048,
                "ImageRows": 4024,
                "SensorWidth": 35.9,
                "SensorHeight": 23.9,
                "HorizontalOverlap": 80,
                "VerticalOverlap": 80,
                "ImageSize": 25  # MB
            },
            "GoPro Hero7 Black": {
                "DFOV": 149.2,
                "HFOV": 122.6,
                "VFOV": 94.4,
                "ImageColumns": 4000,
                "ImageRows": 3000,
                "SensorWidth": 6.17,
                "SensorHeight": 4.63,
                "HorizontalOverlap": 40,
                "VerticalOverlap": 90,
                "ImageSize": 8  # MB estimate
            },
            "SONY ILCE-6300": {
                "f": 24,
                "ImageColumns": 6048,
                "ImageRows": 4024,
                "SensorWidth": 23.5,
                "SensorHeight": 15.6,
                "HorizontalOverlap": 75,
                "VerticalOverlap": 75,
                "ImageSize": 20  # MB estimate
            },
            "UAV Onboard": {
                "DFOV": 84,
                "ImageColumns": 4864,
                "ImageRows": 3648,
                "HorizontalOverlap": 40,
                "VerticalOverlap": 90,
                "ImageSize": 12  # MB estimate
            }
        }
        
        self.setup_gui()
        
    def rad2deg(self, rad):
        """Convert radians to degrees"""
        return (rad * 180) / math.pi
    
    def deg2rad(self, deg):
        """Convert degrees to radians"""
        return (deg * math.pi) / 180
    
    def setup_gui(self):
        """Setup the GUI layout"""
        # Main frame with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="AUV Field of View Calculator", 
                               font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))
        
        # Input section - more compact layout
        input_frame = ttk.Frame(main_frame)
        input_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        input_frame.columnconfigure(1, weight=1)
        input_frame.columnconfigure(3, weight=1)
        input_frame.columnconfigure(5, weight=1)
        
        # Top row of inputs
        ttk.Label(input_frame, text="Camera:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.camera_var = tk.StringVar(value="VOYIS Recon LS")
        camera_combo = ttk.Combobox(input_frame, textvariable=self.camera_var, 
                                   values=list(self.camera_configs.keys()), 
                                   state="readonly", width=20)
        camera_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 15))
        camera_combo.bind('<<ComboboxSelected>>', self.on_camera_change)
        
        ttk.Label(input_frame, text="Frame Rate (fps):").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.frame_rate_var = tk.StringVar(value="5")
        frame_rate_entry = ttk.Entry(input_frame, textvariable=self.frame_rate_var, width=10)
        frame_rate_entry.grid(row=0, column=3, sticky=tk.W, padx=(0, 15))
        
        ttk.Label(input_frame, text="Altitude (m):").grid(row=0, column=4, sticky=tk.W, padx=(0, 5))
        self.altitude_var = tk.StringVar(value="5")
        altitude_entry = ttk.Entry(input_frame, textvariable=self.altitude_var, width=10)
        altitude_entry.grid(row=0, column=5, sticky=tk.W)
        
        # Control buttons section
        controls_frame = ttk.Frame(main_frame)
        controls_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        controls_frame.columnconfigure(0, weight=1)
        controls_frame.columnconfigure(1, weight=1)
        
        # Overlap settings group (left side)
        overlap_frame = ttk.LabelFrame(controls_frame, text="Overlap Settings", padding="5")
        overlap_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        overlap_frame.columnconfigure(1, weight=1)
        overlap_frame.columnconfigure(3, weight=1)
        
        # Overlap inputs
        ttk.Label(overlap_frame, text="Horizontal Overlap (%):").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.horizontal_overlap_var = tk.StringVar(value="80")
        h_overlap_entry = ttk.Entry(overlap_frame, textvariable=self.horizontal_overlap_var, width=8)
        h_overlap_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 15))
        
        ttk.Label(overlap_frame, text="Vertical Overlap (%):").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.vertical_overlap_var = tk.StringVar(value="80")
        v_overlap_entry = ttk.Entry(overlap_frame, textvariable=self.vertical_overlap_var, width=8)
        v_overlap_entry.grid(row=0, column=3, sticky=tk.W, padx=(0, 15))
        
        # Main calculate button
        calc_button = ttk.Button(overlap_frame, text="Calculate FOV", 
                                command=self.calculate, width=15)
        calc_button.grid(row=0, column=4, padx=(10, 0))
        
        # Speed-based calculation group (right side)
        speed_frame = ttk.LabelFrame(controls_frame, text="Speed-Based Planning", padding="5")
        speed_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        speed_frame.columnconfigure(1, weight=1)
        
        ttk.Label(speed_frame, text="Desired Speed (knots):").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.speed_var = tk.StringVar(value="")
        speed_entry = ttk.Entry(speed_frame, textvariable=self.speed_var, width=10)
        speed_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 15))
        
        calc_overlap_btn = ttk.Button(speed_frame, text="Calculate Resulting Overlap", 
                                     command=self.calculate_overlap_from_speed, width=22)
        calc_overlap_btn.grid(row=0, column=2, padx=(0, 0))
        
        
        # Bottom section with results on left and plots on right
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        bottom_frame.columnconfigure(0, weight=1)
        bottom_frame.columnconfigure(1, weight=1)
        bottom_frame.rowconfigure(0, weight=1)
        
        # Results section (left side)
        results_frame = ttk.LabelFrame(bottom_frame, text="Calculation Results", padding="5")
        results_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Results text widget with scrollbar
        text_frame = ttk.Frame(results_frame)
        text_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        self.results_text = tk.Text(text_frame, width=60, wrap=tk.WORD, 
                                   font=('Consolas', 9))
        scrollbar_v = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=scrollbar_v.set)
        
        self.results_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar_v.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Plot section (right side, only if matplotlib is available)
        if MATPLOTLIB_AVAILABLE:
            plot_frame = ttk.LabelFrame(bottom_frame, text="Graphical Analysis", padding="5")
            plot_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
            plot_frame.columnconfigure(0, weight=1)
            plot_frame.rowconfigure(0, weight=1)
            
            # Matplotlib figure
            self.figure = mfig.Figure(figsize=(8, 8), dpi=80)
            self.canvas = FigureCanvasTkAgg(self.figure, plot_frame)
            self.canvas.get_tk_widget().grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        else:
            # Placeholder if matplotlib not available
            no_plot_frame = ttk.LabelFrame(bottom_frame, text="Plots Not Available", padding="5")
            no_plot_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
            ttk.Label(no_plot_frame, text="Install matplotlib to enable plots:\npip install matplotlib").pack(expand=True)
        
        # Configure row weights for expanding
        main_frame.rowconfigure(3, weight=1)
        
    def on_camera_change(self, event=None):
        """Update default values when camera selection changes"""
        selected_camera = self.camera_var.get()
        config = self.camera_configs[selected_camera]
        
        # Set overlap values from camera config
        self.horizontal_overlap_var.set(str(config["HorizontalOverlap"]))
        self.vertical_overlap_var.set(str(config["VerticalOverlap"]))
        
        # Set sensible default altitude based on camera type
        if selected_camera == "UAV Onboard":
            self.altitude_var.set("54")
            self.frame_rate_var.set("2")
        elif selected_camera == "GoPro Hero7 Black":
            self.altitude_var.set("2")
            self.frame_rate_var.set("2")
        elif selected_camera in ["Nikon D780", "SONY ILCE-6300"]:
            self.altitude_var.set("2")
            self.frame_rate_var.set("5")
        elif "UUV" in selected_camera:
            self.altitude_var.set("3")
            self.frame_rate_var.set("5")
        else:  # VOYIS and others
            self.altitude_var.set("5")
            self.frame_rate_var.set("5")
    
    def calculate_overlap_from_speed(self):
        """Calculate resulting vertical overlap based on desired speed"""
        try:
            # Get input values
            camera_name = self.camera_var.get()
            frame_rate = float(self.frame_rate_var.get())
            distance_off_seafloor = float(self.altitude_var.get())
            desired_speed_knots = float(self.speed_var.get())
            
            if desired_speed_knots <= 0:
                raise ValueError("Speed must be positive")
            
            # Convert speed from knots to m/s
            desired_speed_ms = desired_speed_knots / 1.9438444924406
            
            # Get camera configuration
            config = self.camera_configs[camera_name]
            HFOV = config.get("HFOV")
            VFOV = config.get("VFOV")
            DFOV = config.get("DFOV")
            image_rows = config["ImageRows"]
            image_columns = config["ImageColumns"]
            
            # Calculate HFOV and VFOV if needed
            if HFOV == "x" and DFOV is not None:
                HFOV = self.rad2deg(2 * math.atan(math.tan(self.deg2rad(DFOV)/2) * 
                                                 math.cos(math.atan(image_rows/image_columns))))
            
            if VFOV == "x" and DFOV is not None:
                VFOV = self.rad2deg(2 * math.atan(math.tan(self.deg2rad(DFOV)/2) * 
                                                 math.sin(math.atan(image_rows/image_columns))))
            
            # Calculate vertical coverage
            dx = distance_off_seafloor
            hy = abs(dx / math.cos(self.deg2rad(VFOV/2)))
            cy = math.sqrt(hy**2 - dx**2)
            vsamp = cy * 2
            
            # Calculate resulting overlap
            vlap = desired_speed_ms / frame_rate
            overlap_fraction = 1 - (vlap / vsamp)
            resulting_overlap = overlap_fraction * 100
            
            # Update the vertical overlap field
            self.vertical_overlap_var.set(f"{resulting_overlap:.1f}")
            
            # Display results in the results text area
            speed_results = f"""╔═══════════════════════════════════════════════════════════╗
║                SPEED-BASED OVERLAP CALCULATION           ║
╚═══════════════════════════════════════════════════════════╝

INPUT PARAMETERS:
═══════════════════════════════════════════════════════════
Camera: {camera_name}
Frame Rate: {frame_rate} fps
Altitude: {distance_off_seafloor} m
Desired Speed: {desired_speed_knots:.1f} knots ({desired_speed_ms:.2f} m/s)

CALCULATION RESULTS:
═══════════════════════════════════════════════════════════
Vertical Coverage: {vsamp:.2f} m
Distance per frame: {vlap:.2f} m
Resulting Vertical Overlap: {resulting_overlap:.1f}%

STATUS:
═══════════════════════════════════════════════════════════"""
            
            if resulting_overlap < 0:
                speed_results += f"""
❌ SPEED TOO HIGH: The desired speed of {desired_speed_knots:.1f} knots 
   results in negative overlap ({resulting_overlap:.1f}%).
   Maximum possible speed: {(frame_rate * vsamp * 1.9438444924406):.1f} knots with 0% overlap.
"""
            elif resulting_overlap > 95:
                speed_results += f"""
⚠️  HIGH OVERLAP: The desired speed of {desired_speed_knots:.1f} knots 
   results in very high overlap ({resulting_overlap:.1f}%).
   Consider using a higher speed or lower frame rate.
"""
            else:
                speed_results += f"""
✅ SPEED FEASIBLE: The desired speed of {desired_speed_knots:.1f} knots 
   results in {resulting_overlap:.1f}% vertical overlap.
   Vertical overlap field has been updated.
"""
            
            speed_results += f"\n\n{'═'*59}\nSpeed analysis completed successfully."
            
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(1.0, speed_results)
            
            # Generate speed vs overlap plot if matplotlib is available
            if MATPLOTLIB_AVAILABLE:
                self.generate_speed_overlap_plot(camera_name, frame_rate, distance_off_seafloor, 
                                                HFOV, VFOV, DFOV, image_rows, image_columns, 
                                                desired_speed_knots, resulting_overlap)
            
        except ValueError as e:
            messagebox.showerror("Input Error", 
                               f"Please enter valid numeric values.\nError: {str(e)}")
        except Exception as e:
            messagebox.showerror("Calculation Error", 
                               f"An error occurred during calculation:\n{str(e)}")
            
    def calculate(self):
        """Main calculation function - converts R script logic to Python"""
        try:
            # Get input values
            camera_name = self.camera_var.get()
            frame_rate = float(self.frame_rate_var.get())
            distance_off_seafloor = float(self.altitude_var.get())
            horizontal_overlap = float(self.horizontal_overlap_var.get())
            vertical_overlap = float(self.vertical_overlap_var.get())
            
            # Validate inputs
            if frame_rate <= 0 or distance_off_seafloor <= 0:
                raise ValueError("Frame rate and altitude must be positive values")
            if horizontal_overlap < 0 or horizontal_overlap > 100:
                raise ValueError("Horizontal overlap must be between 0 and 100%")
            if vertical_overlap < 0 or vertical_overlap > 100:
                raise ValueError("Vertical overlap must be between 0 and 100%")
            
            # Get camera configuration
            config = self.camera_configs[camera_name]
            
            # Extract camera parameters
            HFOV = config.get("HFOV")
            VFOV = config.get("VFOV")
            DFOV = config.get("DFOV")
            image_columns = config["ImageColumns"]
            image_rows = config["ImageRows"]
            image_size = config.get("ImageSize", 10)  # Default 10MB if not specified
            sensor_width = config.get("SensorWidth")
            
            # Calculate HFOV and VFOV if not provided (from R script logic)
            if HFOV == "x" and DFOV is not None:
                HFOV = self.rad2deg(2 * math.atan(math.tan(self.deg2rad(DFOV)/2) * 
                                                 math.cos(math.atan(image_rows/image_columns))))
            
            if VFOV == "x" and DFOV is not None:
                VFOV = self.rad2deg(2 * math.atan(math.tan(self.deg2rad(DFOV)/2) * 
                                                 math.sin(math.atan(image_rows/image_columns))))
            
            # Main FOV calculations (from R script)
            dx = distance_off_seafloor
            hx = abs(dx / math.cos(self.deg2rad(HFOV/2)))
            cx = math.sqrt(hx**2 - dx**2)
            hsamp = cx * 2  # Horizontal coverage
            
            hy = abs(dx / math.cos(self.deg2rad(VFOV/2)))
            cy = math.sqrt(hy**2 - dx**2)
            vsamp = cy * 2  # Vertical coverage
            
            # Additional calculations
            ground_res = hsamp / image_columns  # Ground resolution
            
            # Focal length estimation (if sensor width available)
            focal_length = None
            if sensor_width is not None:
                focal_length = sensor_width * (1 / math.tan(self.deg2rad(HFOV/2)))
            
            # Line spacing calculation
            hlap = (cx * 2) * (1 - horizontal_overlap/100)
            
            # Speed calculations
            vlap = (cy * 2) * (1 - vertical_overlap/100)
            max_speed_ms = frame_rate * vlap  # m/s
            max_speed_knots = max_speed_ms * 1.9438444924406  # Convert to knots
            
            # Coverage analysis for 1000 m²
            eff_ah = hsamp * ((100 - horizontal_overlap) / 100)
            eff_av = vsamp * ((100 - vertical_overlap) / 100)
            eff_area = eff_ah * eff_av
            photos_1000m2 = 1000 / eff_area
            storage_mb = photos_1000m2 * image_size
            storage_gb = storage_mb / 1000
            
            # Format and display results
            results = self.format_results(
                camera_name, frame_rate, distance_off_seafloor, HFOV, VFOV,
                image_columns, image_rows, horizontal_overlap, vertical_overlap,
                hsamp, vsamp, ground_res, focal_length, hlap, max_speed_ms,
                max_speed_knots, photos_1000m2, storage_gb, image_size
            )
            
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(1.0, results)
            
            # Generate plots if matplotlib is available
            if MATPLOTLIB_AVAILABLE:
                self.generate_plots(camera_name, HFOV, image_columns, distance_off_seafloor, 
                                  vertical_overlap, cy)
            
        except ValueError as e:
            messagebox.showerror("Input Error", 
                               f"Please enter valid numeric values.\nError: {str(e)}")
        except Exception as e:
            messagebox.showerror("Calculation Error", 
                               f"An error occurred during calculation:\n{str(e)}")
    
    def format_results(self, camera_name, frame_rate, distance_off_seafloor, HFOV, VFOV,
                      image_columns, image_rows, horizontal_overlap, vertical_overlap,
                      hsamp, vsamp, ground_res, focal_length, hlap, max_speed_ms,
                      max_speed_knots, photos_1000m2, storage_gb, image_size):
        """Format calculation results for display"""
        
        results = f"""╔═══════════════════════════════════════════════════════════╗
║                   FOV CALCULATION RESULTS                ║
╚═══════════════════════════════════════════════════════════╝

INPUT PARAMETERS:
═══════════════════════════════════════════════════════════
Camera: {camera_name}
Frame Rate: {frame_rate} fps
Altitude: {distance_off_seafloor} m
Horizontal Overlap: {horizontal_overlap}%
Vertical Overlap: {vertical_overlap}%

CAMERA SPECS:
═══════════════════════════════════════════════════════════
HFOV: {HFOV:.1f}° | VFOV: {VFOV:.1f}°
Resolution: {image_columns} × {image_rows} pixels
Image Size: {image_size} MB

COVERAGE:
═══════════════════════════════════════════════════════════
Horizontal Coverage: {hsamp:.2f} m
Vertical Coverage: {vsamp:.2f} m
Ground Resolution: {ground_res*1000:.3f} mm/pixel

MISSION PLANNING:
═══════════════════════════════════════════════════════════
Line Spacing: {hlap:.2f} m
Max Speed: {max_speed_ms:.2f} m/s ({max_speed_knots:.2f} knots)

AREA COVERAGE (1000 m²):
═══════════════════════════════════════════════════════════
Photos needed: {math.ceil(photos_1000m2)}
Storage required: {math.ceil(storage_gb)} GB"""

        if focal_length is not None:
            results += f"\n\nESTIMATED FOCAL LENGTH: {focal_length:.2f} mm"
        
        results += f"\n\n{'═'*59}\nCalculation completed successfully."
        
        return results
    
    def generate_speed_overlap_plot(self, camera_name, frame_rate, distance_off_seafloor, 
                                   HFOV, VFOV, DFOV, image_rows, image_columns,
                                   current_speed_knots, current_overlap):
        """Generate speed vs overlap percentage plot"""
        try:
            self.figure.clear()
            
            # Calculate HFOV and VFOV if needed (same logic as main calculation)
            if HFOV == "x" and DFOV is not None:
                HFOV = self.rad2deg(2 * math.atan(math.tan(self.deg2rad(DFOV)/2) * 
                                                 math.cos(math.atan(image_rows/image_columns))))
            
            if VFOV == "x" and DFOV is not None:
                VFOV = self.rad2deg(2 * math.atan(math.tan(self.deg2rad(DFOV)/2) * 
                                                 math.sin(math.atan(image_rows/image_columns))))
            
            # Calculate vertical coverage
            dx = distance_off_seafloor
            hy = abs(dx / math.cos(self.deg2rad(VFOV/2)))
            cy = math.sqrt(hy**2 - dx**2)
            vsamp = cy * 2
            
            # Create speed range (0.5 to 8 knots)
            speed_range_knots = [s/10 for s in range(5, 81, 2)]  # 0.5 to 8.0 in 0.2 steps
            overlaps = []
            
            for speed_knots in speed_range_knots:
                speed_ms = speed_knots / 1.9438444924406
                vlap = speed_ms / frame_rate
                overlap_fraction = 1 - (vlap / vsamp)
                overlap_percent = overlap_fraction * 100
                overlaps.append(overlap_percent)
            
            # Create the plot
            ax = self.figure.add_subplot(1, 1, 1)
            ax.plot(speed_range_knots, overlaps, 'b-', linewidth=2, label='Speed vs Overlap')
            
            # Highlight current speed and overlap
            ax.plot(current_speed_knots, current_overlap, 'ro', markersize=8, 
                   label=f'Current: {current_speed_knots:.1f} knots, {current_overlap:.1f}% overlap')
            
            # Add reference lines
            ax.axhline(y=0, color='r', linestyle='--', alpha=0.5, label='0% Overlap (No overlap)')
            ax.axhline(y=80, color='g', linestyle='--', alpha=0.5, label='80% Overlap (Typical)')
            ax.axhline(y=90, color='orange', linestyle='--', alpha=0.5, label='90% Overlap (High)')
            
            # Formatting
            ax.set_xlabel('Speed (knots)')
            ax.set_ylabel('Vertical Overlap (%)')
            ax.set_title(f'{camera_name} - Speed vs Vertical Overlap\n'
                        f'@ {distance_off_seafloor}m altitude, {frame_rate} fps')
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # Set reasonable axis limits
            ax.set_xlim(0, max(8, current_speed_knots + 1))
            ax.set_ylim(-10, 100)
            
            # Add text box with key info
            info_text = f'Vertical Coverage: {vsamp:.1f}m\nFrame Rate: {frame_rate} fps'
            ax.text(0.02, 0.98, info_text, transform=ax.transAxes, 
                   verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            
            self.figure.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            print(f"Speed-overlap plot generation error: {e}")
    
    def generate_plots(self, camera_name, HFOV, image_columns, distance_off_seafloor, 
                      vertical_overlap, cy):
        """Generate matplotlib plots (equivalent to R script plots)"""
        try:
            self.figure.clear()
            
            # Create subplots
            ax1 = self.figure.add_subplot(2, 1, 1)
            ax2 = self.figure.add_subplot(2, 1, 2)
            
            # Plot 1: Height vs Resolution (equivalent to R script)
            heights = list(range(1, 16))  # 1 to 15 meters
            resolutions = []
            
            for h in heights:
                hh = abs(h / math.cos(self.deg2rad(HFOV/2)))
                hc = math.sqrt(hh**2 - h**2)
                hs = hc * 2 * 100  # Convert to cm scale
                res = hs / image_columns
                resolutions.append(res)
            
            ax1.plot(resolutions, heights, 'b-', linewidth=2, marker='o', markersize=4)
            ax1.set_xlabel('Resolution (cm/pixel)')
            ax1.set_ylabel('Vehicle Height (meters)')
            ax1.set_title(f'{camera_name} - Vehicle Height vs Resolution')
            ax1.grid(True, alpha=0.3)
            
            # Add linear fit equation (equivalent to R lm function)
            if len(resolutions) > 1:
                # Simple linear regression
                n = len(resolutions)
                sum_x = sum(resolutions)
                sum_y = sum(heights)
                sum_xy = sum(x*y for x, y in zip(resolutions, heights))
                sum_x2 = sum(x*x for x in resolutions)
                
                slope = (n*sum_xy - sum_x*sum_y) / (n*sum_x2 - sum_x*sum_x)
                intercept = (sum_y - slope*sum_x) / n
                
                ax1.text(0.05, 0.95, f'Height = {slope:.2f} × Resolution + {intercept:.2f}', 
                        transform=ax1.transAxes, verticalalignment='top', 
                        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            
            # Plot 2: Speed vs Frame Rate (equivalent to R script)
            fps_range = [f/2 for f in range(4, 21)]  # 2.0 to 10.0 in 0.5 steps
            speeds = []
            
            vlap = (cy * 2) * (1 - vertical_overlap/100)
            for f in fps_range:
                max_speed = f * vlap
                speed_knots = max_speed * 1.9438444924406
                speeds.append(speed_knots)
            
            ax2.plot(speeds, fps_range, 'r-', linewidth=2, marker='s', markersize=4)
            ax2.set_xlabel('Speed (knots)')
            ax2.set_ylabel('Frame Rate (fps)')
            ax2.set_title(f'{camera_name} - Speed vs Frame Rate\n'
                         f'@ {distance_off_seafloor}m height and {vertical_overlap}% Vertical Overlap')
            ax2.grid(True, alpha=0.3)
            
            self.figure.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            print(f"Plot generation error: {e}")

def main():
    """Main function to run the application"""
    try:
        root = tk.Tk()
        
        # Set up styling
        style = ttk.Style()
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        
        # Create and run the application
        app = FOVCalculatorGUI(root)
        
        # Center window on screen
        root.update_idletasks()
        x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
        y = (root.winfo_screenheight() // 2) - (root.winfo_height() // 2)
        root.geometry(f"+{x}+{y}")
        
        root.mainloop()
        
    except Exception as e:
        print(f"Application error: {e}")
        if messagebox:
            messagebox.showerror("Application Error", f"Failed to start application:\n{str(e)}")

if __name__ == "__main__":
    main()
