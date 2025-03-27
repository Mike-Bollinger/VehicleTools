import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import os
import threading
import builtins
from tkinter import scrolledtext
from models.metrics import Metrics
from models.altitude_map import GEOPANDAS_AVAILABLE, AltitudeMap
from src.models.footprint_map import FootprintMap
from datetime import datetime

class AppWindow:
    def __init__(self, root):
        self.root = root
        self.master = root  # For compatibility with some tkinter code
        
        # Set default altitude threshold
        self.altitude_threshold = 9.0
        
        # Initialize variables
        self.all_var = tk.BooleanVar(value=True)
        self.basic_metrics_var = tk.BooleanVar(value=True)
        self.location_map_var = tk.BooleanVar(value=True)
        self.histogram_var = tk.BooleanVar(value=True)
        self.footprint_map_var = tk.BooleanVar(value=True)
        self.nav_path = tk.StringVar()
        self.threshold_var = tk.StringVar(value="9.0")  # String for text entry
        
        # Set all functions to True if all individual options are True
        if all([self.basic_metrics_var.get(), self.location_map_var.get(),
                self.histogram_var.get(), self.footprint_map_var.get()]):
            self.all_var.set(True)
        else:
            self.all_var.set(False)
        
        # Create GUI elements
        self.create_frames()
        
        # Create metrics, altitude map and footprint map objects with the threshold
        self.metrics = Metrics(self.altitude_threshold)
        self.altitude_map = AltitudeMap()
        self.altitude_map.altitude_threshold = self.altitude_threshold
        self.footprint_map = FootprintMap()
        self.footprint_map.altitude_threshold = self.altitude_threshold
        
        # Create the rest of the UI components
        self.create_input_section()
        self.create_functions_section()
        self.create_log_section()
        
        # Make sure the navigation file selection is visible if footprint map is checked by default
        self.update_nav_file_visibility()

    def toggle_all_functions(self):
        """Toggle all function checkboxes based on 'All Functions' checkbox"""
        state = self.all_var.get()
        self.basic_metrics_var.set(state)
        self.location_map_var.set(state)
        self.histogram_var.set(state)
        self.footprint_map_var.set(state)
        self.update_nav_file_visibility()
    
    def update_all_checkbox(self):
        """Update 'All Functions' checkbox based on individual checkboxes"""
        if all([self.basic_metrics_var.get(), self.location_map_var.get(), 
                self.histogram_var.get(), self.footprint_map_var.get()]):
            self.all_var.set(True)
        else:
            self.all_var.set(False)
        # Show/hide nav file selection based on footprint map checkbox
        self.update_nav_file_visibility()

    def select_input_folder(self):
        folder_path = filedialog.askdirectory(title="Select Input Folder")
        if folder_path:
            self.input_path.set(folder_path)
            self.log_message(f"Input folder set to: {folder_path}")

    def select_output_folder(self):
        folder_path = filedialog.askdirectory(title="Select Output Folder")
        if folder_path:
            self.output_path.set(folder_path)
            self.log_message(f"Output folder set to: {folder_path}")

    def select_nav_file(self):
        """Select vehicle navigation file"""
        file_path = filedialog.askopenfilename(
            title="Select Vehicle Navigation File",
            filetypes=[("Text Files", "*.txt"), ("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if file_path:
            self.nav_path.set(file_path)
            self.log_message(f"Vehicle navigation file set to: {file_path}")

    def update_nav_file_visibility(self):
        """Show or hide navigation file selection based on footprint map checkbox"""
        if self.footprint_map_var.get():
            self.nav_file_frame.grid()
        else:
            self.nav_file_frame.grid_remove()

    def log_message(self, message):
        """Add a message to the log window"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, formatted_message)
        self.log_text.see(tk.END)  # Scroll to the end
        self.log_text.config(state=tk.DISABLED)
        
        # Update the UI
        self.root.update_idletasks()

    def update_progress(self, value, message="Processing..."):
        """Update the progress bar and message"""
        self.progress_var.set(value)
        self.progress_label.config(text=message)
        self.root.update_idletasks()
        
    def process_images(self):
        """Process images with selected functions"""
        input_path = self.input_path.get()
        output_path = self.output_path.get()
        
        if not input_path or not os.path.exists(input_path):
            messagebox.showerror("Error", "Please select a valid input folder.")
            return
            
        if not output_path:
            messagebox.showerror("Error", "Please select an output folder.")
            return
            
        # Disable the process button during processing
        self.process_button.configure(state=tk.DISABLED)
        
        # Start a thread for processing
        thread = threading.Thread(
            target=self.analyze_images,
            args=(input_path, output_path)
        )
        thread.daemon = True
        thread.start()

    def analyze_images(self, input_folder, output_folder):
        try:
            self.update_progress(0, "Starting processing...")
            
            # Update the threshold from the entry field
            try:
                altitude_threshold = float(self.threshold_var.get())
                self.altitude_threshold = altitude_threshold
                
                # Update threshold in all components
                self.metrics.altitude_threshold = altitude_threshold
                self.altitude_map.altitude_threshold = altitude_threshold
                self.footprint_map.altitude_threshold = altitude_threshold
                
                self.log_message(f"Using altitude threshold: {altitude_threshold:.1f}m")
            except ValueError:
                self.log_message(f"Using default altitude threshold: {self.altitude_threshold:.1f}m")
            
            # Determine if we need to extract GPS data
            extract_gps = self.location_map_var.get() or self.histogram_var.get() or self.footprint_map_var.get()
            
            # Step 1: Always run the basic metrics analysis first
            self.log_message("Processing basic metrics...")
            
            # Calculate metrics with progress updates
            _, results = self.metrics.analyze_directory(
                input_folder, 
                progress_callback=self.update_progress,
                extract_gps=extract_gps  # Extract GPS data if needed for later
            )
            
            # If basic metrics was selected, show the results
            if self.basic_metrics_var.get():
                # Log results to the GUI
                for line in results:
                    self.log_message(line)
                
                # Write results to output file
                output_file = os.path.join(output_folder, "image_metrics.txt")
                with open(output_file, "w") as f:
                    f.write("\n".join(results))
                
                self.log_message(f"Basic metrics saved to: {output_file}")
            else:
                self.log_message("Basic metrics processing completed (not displayed as not selected)")
            
            # Step 2: Create location map if selected
            if self.location_map_var.get():
                self.log_message("Creating image location map and GIS exports...")
                
                if not self.metrics.gps_data:
                    self.log_message("Warning: No GPS data found in images. Cannot create location map or GIS exports.")
                else:
                    try:
                        # 1. First create the location map
                        self.log_message(f"Generating map with {len(self.metrics.gps_data)} GPS points...")
                        
                        map_file = self.altitude_map.create_location_map(
                            self.metrics.gps_data,
                            output_folder,
                            metrics=self.metrics
                        )
                        
                        if map_file:
                            self.log_message(f"Location map saved to: {map_file}")
                        else:
                            self.log_message("Error: Could not create location map. No valid GPS coordinates found.")
                            
                        # 2. Then create GIS exports (CSV and Shapefile)
                        self.log_message("Creating GIS exports (CSV & Shapefile)...")
                        
                        try:
                            self.log_message(f"Exporting {len(self.metrics.gps_data)} GPS points to GIS formats...")
                            
                            gis_files = self.altitude_map.export_to_gis_formats(
                                self.metrics.gps_data,
                                output_folder
                            )
                            
                            if 'csv' in gis_files:
                                self.log_message(f"CSV file created: {os.path.basename(gis_files['csv'])}")
                            
                            if 'shapefile' in gis_files:
                                self.log_message(f"Shapefile created: {os.path.basename(gis_files['shapefile'])}")
                                self.log_message("The shapefile can be opened in GIS software such as ArcGIS or QGIS.")
                            elif GEOPANDAS_AVAILABLE:
                                self.log_message("Error: Could not create shapefile.")
                            else:
                                self.log_message("Note: Shapefile creation requires geopandas. Install using: pip install geopandas shapely")
                        except Exception as e:
                            self.log_message(f"Error creating GIS exports: {str(e)}")
                            
                    except Exception as e:
                        self.log_message(f"Error creating location map: {str(e)}")
            
            # Step 3: Create altitude histogram if selected
            if self.histogram_var.get():
                self.log_message("Creating altitude histogram...")
                
                if not self.metrics.gps_data:
                    self.log_message("Warning: No GPS data found in images. Cannot create altitude histogram.")
                else:
                    try:
                        self.log_message(f"Generating histogram with {len(self.metrics.gps_data)} altitude points...")
                        
                        histogram_file = self.altitude_map.create_altitude_histogram(
                            self.metrics.gps_data,
                            output_folder
                        )
                        
                        if histogram_file:
                            self.log_message(f"Altitude histogram saved to: {histogram_file}")
                        else:
                            self.log_message("Error: Could not create altitude histogram. No valid altitude data found.")
                    except Exception as e:
                        self.log_message(f"Error creating altitude histogram: {str(e)}")
            
            # Step 4: Create footprint map if selected
            if self.footprint_map_var.get():
                self.log_message("Creating image footprint map...")
                
                if not self.metrics.gps_data:
                    self.log_message("Warning: No GPS data found in images. Cannot create footprint map.")
                else:
                    try:
                        nav_file = self.nav_path.get() if self.nav_path.get() and os.path.exists(self.nav_path.get()) else None
                        
                        if not nav_file:
                            self.log_message("Warning: No navigation file selected or file not found. Using default heading.")
                        else:
                            self.log_message(f"Using navigation data from: {nav_file}")
                        
                        self.log_message(f"Generating footprint map with {len(self.metrics.gps_data)} images (altitude threshold: {self.altitude_threshold:.1f}m)...")
                        
                        # Redirect print statements to also go to the log
                        # Store the original print function
                        original_print = print
                        
                        # Define a new print function that logs to our GUI
                        def logging_print(*args, **kwargs):
                            # Call the original print function
                            original_print(*args, **kwargs)
                            # Also log to our GUI
                            message = " ".join(str(arg) for arg in args)
                            self.log_message(message)
                        
                        # Replace the built-in print function temporarily
                        builtins.print = logging_print
                        
                        try:
                            # Generate the footprint map
                            map_file = self.footprint_map.create_footprint_map(
                                self.metrics.gps_data,
                                output_folder,
                                nav_file_path=nav_file
                            )
                            
                            # Transfer overlap stats
                            if hasattr(self.footprint_map, 'vertical_overlap_stats'):
                                self.metrics.vertical_overlap_stats = self.footprint_map.vertical_overlap_stats
                                
                            if hasattr(self.footprint_map, 'horizontal_overlap_stats'):
                                self.metrics.horizontal_overlap_stats = self.footprint_map.horizontal_overlap_stats
                                
                            if hasattr(self.footprint_map, 'overall_overlap_stats'):
                                self.metrics.overall_overlap_stats = self.footprint_map.overall_overlap_stats
                            
                            # Log results
                            if map_file:
                                self.log_message(f"Footprint map saved to: {map_file}")
                                self.log_message("CSV and shapefile with footprint data also created in the same folder.")
                            else:
                                self.log_message("Error: Could not create footprint map.")
                                
                        finally:
                            # Restore the original print function
                            builtins.print = original_print
                            
                    except Exception as e:
                        self.log_message(f"Error creating footprint map: {str(e)}")
                        import traceback
                        self.log_message(traceback.format_exc())
            
            self.log_message("All selected processing tasks completed successfully.")
            
        except Exception as e:
            self.log_message(f"Error during processing: {str(e)}")
            import traceback
            self.log_message(f"Details: {traceback.format_exc()}")
        finally:
            # Re-enable the process button
            self.master.after(0, lambda: self.process_button.configure(state=tk.NORMAL))

    def threshold_changed(self, *args):
        """Update the altitude threshold when the slider is moved"""
        try:
            # Get the new threshold value
            new_threshold = float(self.threshold_var.get())
            
            # Update threshold value
            self.altitude_threshold = new_threshold
            
            # Update both map objects with the new threshold
            if hasattr(self.altitude_map, 'altitude_threshold'):
                self.altitude_map.altitude_threshold = new_threshold
                
            if hasattr(self.footprint_map, 'altitude_threshold'):
                self.footprint_map.altitude_threshold = new_threshold
            
            # Update the threshold label
            self.threshold_label.config(text=f"Altitude Threshold: {new_threshold:.1f}m")
        except Exception as e:
            print(f"Error updating threshold: {e}")

    def create_frames(self):
        """Create the main frames for the application"""
        # Main container frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left frame for options
        self.left_frame = ttk.Frame(self.main_frame, padding="5")
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))
        
        # Right frame for log output and progress
        self.right_frame = ttk.Frame(self.main_frame, padding="5")
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Create sub-frames in left frame
        self.input_frame = ttk.LabelFrame(self.left_frame, text="Input/Output", padding="5")
        self.input_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.functions_frame = ttk.LabelFrame(self.left_frame, text="Analysis Functions", padding="5")
        self.functions_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.action_frame = ttk.Frame(self.left_frame, padding="5")
        self.action_frame.pack(fill=tk.X)
        
        # Create log frame in right frame
        self.log_frame = ttk.LabelFrame(self.right_frame, text="Processing Log", padding="5")
        self.log_frame.pack(fill=tk.BOTH, expand=True)

    def create_input_section(self):
        """Create the input/output file selection widgets"""
        # Input folder selection
        self.input_path = tk.StringVar()
        input_frame = ttk.Frame(self.input_frame)
        input_frame.grid(row=0, column=0, sticky='ew', pady=2)
        
        ttk.Label(input_frame, text="Input Folder:").grid(row=0, column=0, sticky='w')
        self.input_entry = ttk.Entry(input_frame, textvariable=self.input_path, width=40)
        self.input_entry.grid(row=0, column=1, padx=5, sticky='ew')
        self.input_button = ttk.Button(input_frame, text="Browse...", command=self.select_input_folder)
        self.input_button.grid(row=0, column=2)
        
        # Output folder selection
        self.output_path = tk.StringVar()
        output_frame = ttk.Frame(self.input_frame)
        output_frame.grid(row=1, column=0, sticky='ew', pady=2)
        
        ttk.Label(output_frame, text="Output Folder:").grid(row=0, column=0, sticky='w')
        self.output_entry = ttk.Entry(output_frame, textvariable=self.output_path, width=40)
        self.output_entry.grid(row=0, column=1, padx=5, sticky='ew')
        self.output_button = ttk.Button(output_frame, text="Browse...", command=self.select_output_folder)
        self.output_button.grid(row=0, column=2)

    def create_functions_section(self):
        """Create the functions selection checkbox widgets"""
        # "All Functions" checkbox
        self.all_check = ttk.Checkbutton(
            self.functions_frame,
            text="All Functions",
            variable=self.all_var,
            command=self.toggle_all_functions
        )
        self.all_check.grid(row=0, column=0, sticky='w', pady=2)
        
        # Individual functions checkboxes
        self.basic_metrics_check = ttk.Checkbutton(
            self.functions_frame,
            text="Basic Metrics",
            variable=self.basic_metrics_var,
            command=self.update_all_checkbox
        )
        self.basic_metrics_check.grid(row=1, column=0, sticky='w', padx=25, pady=2)
        
        self.location_map_check = ttk.Checkbutton(
            self.functions_frame,
            text="Image Location Map",
            variable=self.location_map_var,
            command=self.update_all_checkbox
        )
        self.location_map_check.grid(row=2, column=0, sticky='w', padx=25, pady=2)
        
        self.histogram_check = ttk.Checkbutton(
            self.functions_frame,
            text="Image Altitude Histogram",
            variable=self.histogram_var,
            command=self.update_all_checkbox
        )
        self.histogram_check.grid(row=3, column=0, sticky='w', padx=25, pady=2)
        
        self.footprint_map_check = ttk.Checkbutton(
            self.functions_frame,
            text="Image Footprint and Overlap Maps (Requires Vehicle Navigation File)",
            variable=self.footprint_map_var,
            command=self.update_all_checkbox
        )
        self.footprint_map_check.grid(row=4, column=0, sticky='w', padx=25, pady=2)
        
        # Add a frame for nav file selection that appears when footprint map is selected
        self.nav_file_frame = ttk.Frame(self.functions_frame)
        self.nav_file_frame.grid(row=5, column=0, sticky='w', padx=45, pady=(0, 5))
        self.nav_file_frame.grid_remove()  # Hide it initially
        
        ttk.Label(self.nav_file_frame, text="Vehicle Navigation File:").grid(row=0, column=0, sticky='w', padx=(0, 5))
        self.nav_entry = ttk.Entry(self.nav_file_frame, textvariable=self.nav_path, width=40)
        self.nav_entry.grid(row=0, column=1, padx=(5, 5), sticky='ew')
        self.nav_button = ttk.Button(self.nav_file_frame, text="Browse...", command=self.select_nav_file)
        self.nav_button.grid(row=0, column=2)
        
        # Add the method for creating the altitude threshold control
        self.create_threshold_control()
        
        # Add process button
        self.process_button = ttk.Button(
            self.action_frame,
            text="Process Images",
            command=self.process_images
        )
        self.process_button.pack(pady=10)

    def create_log_section(self):
        """Create the log output and progress widgets"""
        # Create log text widget
        self.log_text = scrolledtext.ScrolledText(self.log_frame, height=20, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_text.config(state=tk.DISABLED)  # Make read-only
        
        # Create progress bar
        self.progress_frame = ttk.Frame(self.right_frame, padding="5")
        self.progress_frame.pack(fill=tk.X, pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            orient=tk.HORIZONTAL,
            length=300,
            mode='determinate',
            variable=self.progress_var
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.progress_label = ttk.Label(self.progress_frame, text="Ready")
        self.progress_label.pack(side=tk.RIGHT, padx=5)
        
        # Add initial log message
        self.log_message("Welcome to VOYIS First Look Metrics")
        self.log_message("Select an input folder with VOYIS images and an output folder for results")
        self.log_message("Then check the desired functions and click 'Process Images'")

    def create_threshold_control(self):
        """Create the altitude threshold entry box and label"""
        threshold_frame = ttk.Frame(self.functions_frame)
        threshold_frame.grid(row=6, column=0, sticky='ew', pady=(10, 5))
        
        ttk.Label(threshold_frame, text="Altitude Threshold (m):").grid(row=0, column=0, sticky='w')
        
        threshold_entry = ttk.Entry(threshold_frame, textvariable=self.threshold_var, width=6)
        threshold_entry.grid(row=0, column=1, padx=5, sticky='w')
        
        # Add a button to apply the threshold
        apply_button = ttk.Button(threshold_frame, text="Apply", command=self.update_threshold)
        apply_button.grid(row=0, column=2, padx=5, sticky='w')
        
        # Add explanation text
        ttk.Label(
            self.functions_frame, 
            text="(Altitude threshold filters out images that are too high to see the seabed)",
            font=("", 8, "italic")
        ).grid(row=7, column=0, sticky='w', pady=(0, 10), padx=25)

    def update_threshold(self):
        """Update altitude threshold when Apply button is clicked"""
        try:
            new_threshold = float(self.threshold_var.get())
            
            if new_threshold <= 0:
                messagebox.showwarning("Invalid Threshold", "Altitude threshold must be a positive number.")
                return
                
            # Update the threshold value
            self.altitude_threshold = new_threshold
            
            # Update all components
            self.metrics.altitude_threshold = new_threshold
            self.altitude_map.altitude_threshold = new_threshold
            self.footprint_map.altitude_threshold = new_threshold
            
            # Log the change
            self.log_message(f"Altitude threshold set to {new_threshold:.1f}m")
            
        except ValueError:
            messagebox.showwarning("Invalid Input", "Please enter a valid number for the altitude threshold.")
        except Exception as e:
            self.log_message(f"Error updating threshold: {str(e)}")