import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import os
import threading
import builtins
from tkinter import scrolledtext
from typing import Optional
from models.metrics import Metrics
from models.altitude_map import GEOPANDAS_AVAILABLE, AltitudeMap
from src.models.footprint_map import FootprintMap
from src.models.visibility_analyzer import VisibilityAnalyzer
from src.models.highlight_selector import HighlightSelector
from datetime import datetime
import numpy as np
import time

class AppWindow:
    def __init__(self, root):
        self.root = root
        self.master = root  # For compatibility with some tkinter code
        
        # Create a custom style for the process button
        style = ttk.Style()
        style.configure("AccentButton.TButton", font=('', 10, 'bold'))
        
        # Initialize AltitudeMap
        self.altitude_map = AltitudeMap()
        
        # Make sure metrics object exists
        self.metrics = None  # Will be initialized later
        
        # Set default thresholds
        self.altitude_threshold = 8.0
        self.low_altitude_threshold = 4.0
        
        # Initialize variables
        self.all_var = tk.BooleanVar(value=True)
        self.basic_metrics_var = tk.BooleanVar(value=True)
        self.location_map_var = tk.BooleanVar(value=True)
        self.histogram_var = tk.BooleanVar(value=True)
        self.footprint_map_var = tk.BooleanVar(value=True)
        self.visibility_analyzer_var = tk.BooleanVar(value=True)  # Changed to True
        self.highlight_selector_var = tk.BooleanVar(value=True)  # Changed to True
        self.nav_path = tk.StringVar()
        self.threshold_var = tk.StringVar(value="8.0")  # String for text entry
        
        # Set all functions to True if all individual options are True
        if all([self.basic_metrics_var.get(), self.location_map_var.get(),
                self.histogram_var.get(), self.footprint_map_var.get()]):
            self.all_var.set(True)
        else:
            self.all_var.set(False)
        
        # Create GUI elements
        self.create_frames()
        
        # Initialize components
        self.metrics = Metrics(self.altitude_threshold)
        self.altitude_map = AltitudeMap()
        self.altitude_map.set_altitude_thresholds(self.altitude_threshold, 4.0)
        self.footprint_map = FootprintMap(self.altitude_threshold)
        
        # Initialize highlight selector
        self.highlight_selector = HighlightSelector()
        
        # Create metrics, altitude map and footprint map objects with the threshold
        self.metrics = Metrics(self.altitude_threshold)
        self.altitude_map.set_altitude_thresholds(self.altitude_threshold, 4.0)  # Set both thresholds
        self.footprint_map = FootprintMap()
        self.footprint_map.altitude_threshold = self.altitude_threshold
        
        # Add visibility analyzer
        self.visibility_analyzer = VisibilityAnalyzer()
        self.visibility_analyzer.altitude_threshold = self.altitude_threshold
        
        # Create the UI components in the correct order
        # First create the log section so log_message works
        self.create_log_section()
        
        # Then create the rest of the UI
        self.create_input_section()
        self.create_functions_section()
        
        # Make sure the navigation file selection is visible if footprint map is checked by default
        self.update_nav_file_visibility()

    def toggle_all_functions(self):
        """Toggle all function checkboxes based on 'All Functions' checkbox"""
        state = self.all_var.get()
        self.basic_metrics_var.set(state)
        self.location_map_var.set(state)
        self.histogram_var.set(state)
        self.footprint_map_var.set(state)
        self.visibility_analyzer_var.set(state)  # Added this line
        self.highlight_selector_var.set(state)   # Added this line
        
        # Update UI based on new state
        self.update_nav_file_visibility()
        
        # Show/hide visibility options based on checkbox state
        if state:
            self.toggle_visibility_options()  # Make sure visibility options appear if checked
        else:
            self.visibility_model_frame.grid_remove()  # Hide when unchecked

    def update_all_checkbox(self):
        """Update 'All Functions' checkbox based on individual checkboxes"""
        if all([self.basic_metrics_var.get(), 
                self.location_map_var.get(), 
                self.histogram_var.get(), 
                self.footprint_map_var.get(),
                self.visibility_analyzer_var.get(),  # Added this line
                self.highlight_selector_var.get()    # Added this line
               ]):
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

    def select_visibility_file(self, file_type):
        """Select model file or training data directory for visibility analyzer"""
        if file_type == "model":
            # Get the default models directory
            default_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                       "v_a_pre-trained_models")
            os.makedirs(default_dir, exist_ok=True)
            
            file_path = filedialog.askopenfilename(
                title="Select Pre-trained Visibility Model",
                initialdir=default_dir,
                filetypes=[("Model files", "*.h5"), ("All files", "*.*")]
            )
            if file_path:
                self.model_path.set(file_path)
                self.training_path.set("")  # Clear the other path
                self.model_type_var.set("model")
                self.log_message(f"Visibility model file set to: {file_path}")
        else:  # training data
            folder_path = filedialog.askdirectory(
                title="Select Visibility Training Data Directory"
            )
            if folder_path:
                self.training_path.set(folder_path)
                self.model_path.set("")  # Clear the other path
                self.model_type_var.set("training")
                self.log_message(f"Visibility training data directory set to: {folder_path}")

    def update_nav_file_visibility(self):
        """Show or hide navigation file selection based on footprint map checkbox"""
        if self.footprint_map_var.get():
            self.nav_file_frame.grid()
        else:
            self.nav_file_frame.grid_remove()

    def toggle_nav_options(self):
        """Show or hide nav file options based on checkbox state"""
        if self.footprint_map_var.get():
            self.nav_file_frame.grid()
            # Don't affect the visibility options by resizing
        else:
            self.nav_file_frame.grid_remove()
        
        self.update_all_checkbox()

    def log_message(self, message):
        """
        Add a message to the log text
        
        Args:
            message: Message to log
        """
        # Format with timestamp
        timestamp = time.strftime("[%H:%M:%S]")
        log_entry = f"{timestamp} {message}"
        
        # Add to text widget
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, log_entry + "\n")
        self.log_text.see(tk.END)  # Scroll to the end
        self.log_text.config(state=tk.DISABLED)
        
        # Also print to console
        print(log_entry)

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
        
        # Set both thresholds in the AltitudeMap object
        self.altitude_map.set_altitude_thresholds(self.altitude_threshold, self.low_altitude_threshold)
        
        # Start a thread for processing
        thread = threading.Thread(
            target=self.analyze_images,
            args=(input_path, output_path)
        )
        thread.daemon = True
        thread.start()

    def analyze_images(self, input_folder, output_folder):
        """Process images based on selected functions"""
        try:
            self.update_progress(0, "Starting processing...")
            
            # Update the threshold from the entry field
            try:
                altitude_threshold = float(self.threshold_var.get())
                self.altitude_threshold = altitude_threshold
                
                # Update threshold in all components
                self.metrics.altitude_threshold = altitude_threshold
                self.altitude_map.set_altitude_thresholds(altitude_threshold, 4.0)  # Keep low threshold at 4m
                
                self.log_message(f"Using altitude threshold: {altitude_threshold:.1f}m")
            except ValueError:
                self.log_message(f"Using default altitude threshold: {self.altitude_threshold:.1f}m")
            
            # Determine if we need to extract GPS data
            extract_gps = self.location_map_var.get() or self.histogram_var.get() or self.footprint_map_var.get() or self.visibility_analyzer_var.get()
            
            # STAGE 1: Basic Metrics (Always run this first to extract GPS data)
            self.log_message("STAGE 1: Processing basic metrics...")
            
            try:
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
            except Exception as e:
                self.log_message(f"Error processing basic metrics: {str(e)}")
                raise  # Re-raise to be caught by outer try-except
            
            # STAGE 2: Location Map and Altitude Histogram
            if self.location_map_var.get() or self.histogram_var.get():
                self.log_message("\nSTAGE 2: Creating location map and altitude histogram...")

                # Check if we have GPS data
                if not self.metrics.gps_data:
                    self.log_message("Warning: No GPS data found in images. Cannot create location map or altitude histogram.")
                else:
                    # Step 2A: Create location map if selected
                    if self.location_map_var.get():
                        self.log_message("Creating image location map...")
                        
                        try:
                            # Generate the location map
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
                                
                            # Create CSV and shapefile export using AltitudeMap's export_to_gis_formats method
                            self.log_message("Creating GPS data exports (CSV and shapefile)...")

                            try:
                                # Use the export_to_gis_formats method from AltitudeMap
                                result_files = self.altitude_map.export_to_gis_formats(
                                    self.metrics.gps_data,
                                    output_folder
                                )
                                
                                if 'csv' in result_files:
                                    self.log_message(f"CSV export saved to: {result_files['csv']}")
                                    
                                if 'shapefile' in result_files and GEOPANDAS_AVAILABLE:
                                    self.log_message(f"Shapefile export saved to: {result_files['shapefile']}")
                                    
                            except Exception as e:
                                # Fall back to the simple CSV export if the GIS export fails
                                self.log_message(f"Error creating GIS exports: {str(e)}")
                                
                                try:
                                    csv_path = os.path.join(output_folder, "image_locations.csv")
                                    import pandas as pd
                                    df = pd.DataFrame(self.metrics.gps_data)
                                    
                                    # Define column order before saving
                                    columns = ["filename", "DateTime", "latitude", "longitude", "altitude", 
                                              "SubjectDistance", "ExposureTime", "FNumber", "FocalLength",
                                              "width", "height"]
                                              
                                    # Only include columns that exist in the dataframe
                                    available_cols = [col for col in columns if col in df.columns]
                                    other_cols = [col for col in df.columns if col not in columns]
                                    
                                    # Reorder columns
                                    df = df[available_cols + other_cols]
                                    
                                    df.to_csv(csv_path, index=False)
                                    self.log_message(f"CSV export saved to: {csv_path}")
                                except Exception as csv_err:
                                    self.log_message(f"Error creating CSV export: {str(csv_err)}")
                        except Exception as e:
                            self.log_message(f"Error creating location map: {str(e)}")
                    
                    # Step 2B: Create altitude histogram if selected
                    if self.histogram_var.get():
                        self.log_message("Creating altitude histogram...")
                        
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
            
            # STAGE 3: Footprint and Overlap Analysis
            if self.footprint_map_var.get():
                self.log_message("\nSTAGE 3: Creating image footprint map and overlap analysis...")
                
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
                        
                        # SAFE way to capture print output without recursion error:
                        # Use StringIO instead of redefining print
                        import io
                        import contextlib
                        
                        # Create a StringIO object to capture print output
                        f = io.StringIO()
                        with contextlib.redirect_stdout(f):
                            # Generate the footprint map
                            map_file = self.footprint_map.create_footprint_map(
                                self.metrics.gps_data,
                                output_folder,
                                nav_file_path=nav_file
                            )
                        
                        # Log the captured output (split by lines)
                        for line in f.getvalue().splitlines():
                            if line.strip():  # Only log non-empty lines
                                self.log_message(line)
                        
                        # Transfer overlap stats
                        if hasattr(self.footprint_map, 'vertical_overlap_stats'):
                            self.metrics.vertical_overlap_stats = self.footprint_map.vertical_overlap_stats
                            
                        if hasattr(self.footprint_map, 'horizontal_overlap_stats'):
                            self.metrics.horizontal_overlap_stats = self.footprint_map.horizontal_overlap_stats
                            
                        if hasattr(self.footprint_map, 'overall_overlap_stats'):
                            self.metrics.overall_overlap_stats = self.footprint_map.overall_overlap_stats
                        
                        # Append updated metrics with overlap information to the metrics file
                        self.append_overlap_metrics_to_file(output_folder)
                        
                        # Log results
                        if map_file:
                            self.log_message(f"Footprint map saved to: {map_file}")
                            self.log_message("CSV and shapefile with footprint data also created in the same folder.")
                        else:
                            self.log_message("Error: Could not create footprint map.")
                            
                    except Exception as e:
                        self.log_message(f"Error creating footprint map: {str(e)}")
                        import traceback
                        self.log_message(traceback.format_exc())
            
            # STAGE 4: Visibility Analysis (last step)
            if self.visibility_analyzer_var.get():
                self.log_message("\nSTAGE 4: Running visibility analysis...")
                
                # Initialize visibility analyzer if needed
                if not hasattr(self, 'visibility_analyzer'):
                    from src.models.visibility_analyzer import VisibilityAnalyzer
                    self.visibility_analyzer = VisibilityAnalyzer(self.altitude_threshold)
                else:
                    # Update the altitude threshold in case it was changed
                    self.visibility_analyzer.altitude_threshold = self.altitude_threshold
                
                # Try to check TensorFlow without importing
                tf_available = self.visibility_analyzer._import_tensorflow()
                            
                if not tf_available:
                    self.log_message("WARNING: TensorFlow not available. Cannot perform visibility analysis.")
                    self.log_message("Please install TensorFlow with: pip install tensorflow")
                else:
                    try:
                        # Get the path based on radio button selection
                        if self.model_type_var.get() == "model":
                            model_path = self.model_path.get()
                            if not model_path or not os.path.exists(model_path):
                                self.log_message("Error: Please select a valid visibility model file.")
                                return
                        else:  # training
                            model_path = self.training_path.get()
                            if not model_path or not os.path.exists(model_path):
                                self.log_message("Error: Please select a valid training data directory.")
                                return
                        
                        # Load or train model
                        self.log_message(f"Loading or training visibility model from: {model_path}")
                        success = self.visibility_analyzer.load_or_train_model(
                            model_path, 
                            progress_callback=self.update_progress
                        )
                        
                        if not success:
                            self.log_message("Error: Could not load or train visibility model.")
                        else:
                            # If we trained a new model, save it
                            if os.path.isdir(model_path):  # model_path is a training data directory
                                # Create a models directory in the application root
                                app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
                                models_dir = os.path.join(app_root, "utils", "models")
                                os.makedirs(models_dir, exist_ok=True)
                                
                                # Create a timestamped filename for the model
                                import datetime
                                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                                model_filename = f"visibility_model_{timestamp}.h5"
                                model_save_path = os.path.join(models_dir, model_filename)
                                
                                # Save the model
                                saved_path = self.visibility_analyzer.save_model(model_save_path)
                                if saved_path:
                                    self.log_message(f"Trained model saved to: {saved_path}")
                                    
                                    # Also save a copy to the output folder for this specific run
                                    output_model_path = os.path.join(output_folder, "visibility_model.h5")
                                    self.visibility_analyzer.save_model(output_model_path)
                                    self.log_message(f"Model copy saved to output folder: {output_model_path}")
                                else:
                                    self.log_message("Warning: Could not save trained model")
                            
                            # Patch the log_message method for visibility analyzer
                            # Store original log_message if exists
                            if hasattr(self.visibility_analyzer, 'log_message'):
                                original_log_message = self.visibility_analyzer.log_message
                            
                            # Create a properly-scoped log message function
                            def log_message_adapter(msg, progress=None):
                                self.log_message(msg)
                                if progress is not None:
                                    self.update_progress(progress, msg)
                            
                            # Replace the log_message in visibility_analyzer
                            self.visibility_analyzer.log_message = log_message_adapter
                            
                            # The input folder contains the images to analyze
                            self.log_message(f"Starting visibility analysis with altitude threshold: {self.altitude_threshold}m")
                            self.log_message("This will process all images below the threshold (up to 5000)")
                            
                            # Let the analyzer find all images - don't pre-filter or limit here
                            success, stats = self.visibility_analyzer.analyze_images(
                                [],  # Empty list means it will scan the input folder
                                output_folder,
                                progress_callback=self.update_progress,
                                altitude_threshold=self.altitude_threshold
                            )
                            
                            # Restore original log_message if it existed
                            if hasattr(self.visibility_analyzer, 'original_log_message'):
                                self.visibility_analyzer.log_message = original_log_message
                            
                            if not success:
                                self.log_message("Error during visibility analysis.")
                            else:
                                # Show results
                                self.log_message(f"Visibility analysis complete. Results saved to {output_folder}")
                                
                                # Display summary in log
                                for line in self.visibility_analyzer.get_summary_report():
                                    self.log_message(line)
                                
                                # Append to metrics file
                                self.append_visibility_metrics_to_file(output_folder)
                    except Exception as e:
                        self.log_message(f"Error during visibility analysis: {str(e)}")
                        import traceback
                        self.log_message(traceback.format_exc())
            
            # STAGE 5: Highlight Image Selection
            if self.highlight_selector_var.get():
                self.log_message("\nSTAGE 5: Selecting highlight images...")
                
                success = self.select_highlight_images(input_folder, output_folder)
                
                if success:
                    self.log_message("Highlight image selection completed successfully")
                else:
                    self.log_message("Error during highlight image selection")
            
            self.log_message("\nAll selected processing tasks completed successfully.")
            
        except Exception as e:
            self.log_message(f"Error during processing: {str(e)}")
            import traceback
            self.log_message(f"Details: {traceback.format_exc()}")
        finally:
            # Re-enable the process button
            self.master.after(0, lambda: self.process_button.configure(state=tk.NORMAL))

    def append_overlap_metrics_to_file(self, output_folder: str):
        """
        Append overlap metrics to the existing metrics text file
        
        Args:
            output_folder: Directory where the metrics file is located
        """
        metrics_file = os.path.join(output_folder, "image_metrics.txt")
        
        if not os.path.exists(metrics_file):
            self.log_message("Warning: Metrics file not found. Creating new file with overlap metrics.")
            
        try:
            # Get only the overlap-related metrics
            overlap_metrics = []
            
            if hasattr(self.metrics, 'vertical_overlap_stats') and self.metrics.vertical_overlap_stats:
                overlap_metrics.append("\n\n--- OVERLAP METRICS ---\n")
                overlap_metrics.append("\nVertical Overlap Statistics (Sequential Images):")
                overlap_metrics.append("-" * 45)
                overlap_metrics.append(f"Average overlap: {self.metrics.vertical_overlap_stats['avg_overlap']:.1f}%")
                overlap_metrics.append(f"Median overlap: {self.metrics.vertical_overlap_stats['median_overlap']:.1f}%")
                overlap_metrics.append(f"Overlap range: {self.metrics.vertical_overlap_stats['min_overlap']:.1f}% to {self.metrics.vertical_overlap_stats['max_overlap']:.1f}%")
                overlap_metrics.append(f"Low overlap (<40%): {self.metrics.vertical_overlap_stats['low_overlap']} image pairs")
                overlap_metrics.append(f"Medium overlap (40-70%): {self.metrics.vertical_overlap_stats['medium_overlap']} image pairs")
                overlap_metrics.append(f"High overlap (>70%): {self.metrics.vertical_overlap_stats['high_overlap']} image pairs")
                overlap_metrics.append(f"Total image pairs analyzed: {self.metrics.vertical_overlap_stats['total_overlap_count']}")
            
            if hasattr(self.metrics, 'horizontal_overlap_stats') and self.metrics.horizontal_overlap_stats:
                overlap_metrics.append("\nHorizontal Overlap Statistics (Between Survey Lines):")
                overlap_metrics.append("-" * 50)
                overlap_metrics.append(f"Average overlap: {self.metrics.horizontal_overlap_stats['avg_overlap']:.1f}%")
                overlap_metrics.append(f"Median overlap: {self.metrics.horizontal_overlap_stats['median_overlap']:.1f}%")
                overlap_metrics.append(f"Overlap range: {self.metrics.horizontal_overlap_stats['min_overlap']:.1f}% to {self.metrics.horizontal_overlap_stats['max_overlap']:.1f}%")
                overlap_metrics.append(f"Low overlap (<10%): {self.metrics.horizontal_overlap_stats['low_overlap']} image pairs")
                overlap_metrics.append(f"Medium overlap (10-40%): {self.metrics.horizontal_overlap_stats['medium_overlap']} image pairs")
                overlap_metrics.append(f"High overlap (>40%): {self.metrics.horizontal_overlap_stats['high_overlap']} image pairs")
                overlap_metrics.append(f"Total image pairs with overlap: {self.metrics.horizontal_overlap_stats['total_overlap_count']} (of {self.metrics.horizontal_overlap_stats.get('total_checks', 'N/A')} possible pairs)")
            
            if hasattr(self.metrics, 'overall_overlap_stats') and self.metrics.overall_overlap_stats:
                overlap_metrics.append("\nOverall Overlap Statistics (All Overlapping Images):")
                overlap_metrics.append("-" * 49)
                overlap_metrics.append(f"Average overlapping images: {self.metrics.overall_overlap_stats['avg_count']:.1f} per footprint")
                overlap_metrics.append(f"Median overlapping images: {self.metrics.overall_overlap_stats['median_count']:.1f} per footprint")
                overlap_metrics.append(f"Range: {self.metrics.overall_overlap_stats['min_count']} to {self.metrics.overall_overlap_stats['max_count']} overlapping images")
                overlap_metrics.append(f"Total overlapping pairs: {self.metrics.overall_overlap_stats['total_overlaps']} (of {self.metrics.overall_overlap_stats.get('total_checks', 'N/A')} possible pairs)")
            
            # Only proceed if we have overlap metrics to append
            if overlap_metrics:
                with open(metrics_file, 'a') as f:
                    f.write("\n".join(overlap_metrics))
                self.log_message("Overlap metrics appended to image_metrics.txt")
            
        except Exception as e:
            self.log_message(f"Error appending overlap metrics to file: {str(e)}")
            import traceback
            self.log_message(traceback.format_exc())

    def append_visibility_metrics_to_file(self, output_folder: str):
        """
        Append visibility metrics to the existing metrics text file
        
        Args:
            output_folder: Directory where the metrics file is located
        """
        metrics_file = os.path.join(output_folder, "image_metrics.txt")
        
        if not os.path.exists(metrics_file):
            self.log_message("Warning: Metrics file not found. Creating new file with visibility metrics.")
            
        try:
            # Get visibility metrics
            visibility_metrics = self.visibility_analyzer.get_summary_report()
            
            # Only proceed if we have metrics to append
            if visibility_metrics:
                with open(metrics_file, 'a') as f:
                    f.write("\n\n--- VISIBILITY METRICS ---\n")
                    f.write("\n".join(visibility_metrics))
                self.log_message("Visibility metrics appended to image_metrics.txt")
            
        except Exception as e:
            self.log_message(f"Error appending visibility metrics to file: {str(e)}")
            import traceback
            self.log_message(traceback.format_exc())

    def threshold_changed(self, *args):
        """Update the altitude threshold when the slider is moved"""
        try:
            # Get the new threshold value
            new_threshold = float(self.threshold_var.get())
            
            # Update threshold value
            self.altitude_threshold = new_threshold
            
            # Update both map objects with the new threshold
            if hasattr(self.altitude_map, 'set_altitude_thresholds'):
                self.altitude_map.set_altitude_thresholds(new_threshold, 4.0)  # Keep low threshold at 4m
                
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
        
        # Removed action_frame - process button will be added later
        
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
        self.all_var = tk.BooleanVar(value=True)
        self.basic_metrics_var = tk.BooleanVar(value=True)
        self.location_map_var = tk.BooleanVar(value=True)
        self.histogram_var = tk.BooleanVar(value=True)
        self.footprint_map_var = tk.BooleanVar(value=True)
        self.visibility_analyzer_var = tk.BooleanVar(value=True)
        self.highlight_selector_var = tk.BooleanVar(value=True)

        # We'll use this to track the row for dynamic positioning
        self.current_row = 0
        
        # Analysis Functions section
        self.all_check = ttk.Checkbutton(
            self.functions_frame,
            text="All Functions",
            variable=self.all_var,
            command=self.toggle_all_functions
        )
        self.all_check.grid(row=self.current_row, column=0, sticky='w', pady=2)
        self.current_row += 1
        
        # Individual functions checkboxes
        self.basic_metrics_check = ttk.Checkbutton(
            self.functions_frame,
            text="Basic Metrics",
            variable=self.basic_metrics_var,
            command=self.update_all_checkbox
        )
        self.basic_metrics_check.grid(row=self.current_row, column=0, sticky='w', padx=25, pady=2)
        self.current_row += 1
        
        self.location_map_check = ttk.Checkbutton(
            self.functions_frame,
            text="Image Location Map",
            variable=self.location_map_var,
            command=self.update_all_checkbox
        )
        self.location_map_check.grid(row=self.current_row, column=0, sticky='w', padx=25, pady=2)
        self.current_row += 1
        
        self.histogram_check = ttk.Checkbutton(
            self.functions_frame,
            text="Image Altitude Histogram",
            variable=self.histogram_var,
            command=self.update_all_checkbox
        )
        self.histogram_check.grid(row=self.current_row, column=0, sticky='w', padx=25, pady=2)
        self.current_row += 1
        
        self.footprint_map_check = ttk.Checkbutton(
            self.functions_frame,
            text="Image Footprint and Overlap Maps (Requires Vehicle Navigation File)",
            variable=self.footprint_map_var,
            command=self.update_all_checkbox
        )
        self.footprint_map_check.grid(row=self.current_row, column=0, sticky='w', padx=25, pady=2)
        self.current_row += 1
        
        # Add a frame for nav file selection that appears when footprint map is selected
        self.nav_file_frame = ttk.Frame(self.functions_frame)
        self.nav_file_frame.grid(row=self.current_row, column=0, sticky='w', padx=45, pady=(0, 5))
        self.nav_file_frame.grid_remove()  # Hide it initially
        self.nav_file_row = self.current_row
        self.current_row += 1
        
        ttk.Label(self.nav_file_frame, text="Vehicle Navigation File:").grid(row=0, column=0, sticky='w', padx=(0, 5))
        self.nav_entry = ttk.Entry(self.nav_file_frame, textvariable=self.nav_path, width=40)
        self.nav_entry.grid(row=0, column=1, padx=(5, 5), sticky='ew')
        self.nav_button = ttk.Button(self.nav_file_frame, text="Browse...", command=self.select_nav_file)
        self.nav_button.grid(row=0, column=2)
        
        # Add visibility analyzer checkbox
        self.visibility_analyzer_check = ttk.Checkbutton(
            self.functions_frame,
            text="Analyze Image Visibility",
            variable=self.visibility_analyzer_var,
            command=self.toggle_visibility_options
        )
        self.visibility_analyzer_check.grid(row=self.current_row, column=0, sticky='w', padx=25, pady=2)
        self.current_row += 1

        # Add a note about computational intensity below the visibility checkbox
        self.vis_note_label = ttk.Label(
            self.functions_frame,
            text="(Visibility analysis is computationally intensive and may take a long time)",
            font=("", 8, "italic")
        )
        self.vis_note_label.grid(row=self.current_row, column=0, sticky='w', padx=45, pady=(0, 5))
        self.current_row += 1

        # Make the visibility frame wider to show all options
        # Use a LabelFrame for better visual separation and more space
        self.visibility_model_frame = ttk.LabelFrame(self.functions_frame, text="Visibility Analysis Options")
        # Note: We don't grid it here - it will be positioned by toggle_visibility_options
        self.visibility_model_row = self.current_row  # Store the correct position
        self.current_row += 1  # Still increment for spacing

        # Add highlight image selector checkbox
        self.highlight_selector_check = ttk.Checkbutton(
            self.functions_frame, 
            text="Select Highlight Images", 
            variable=self.highlight_selector_var
        )
        self.highlight_selector_check.grid(row=self.current_row, column=0, sticky='w', padx=25, pady=2)
        self.current_row += 1
        
        # Configure column weights to make the frame expand properly
        self.visibility_model_frame.columnconfigure(1, weight=1)
        
        # Model selection radio buttons
        self.model_type_var = tk.StringVar(value="model")
        
        # Model radio button
        self.model_radio = ttk.Radiobutton(
            self.visibility_model_frame,
            text="Pre-trained Model",
            variable=self.model_type_var,
            value="model",
            command=self.on_model_radio_select
        )
        self.model_radio.grid(row=0, column=0, sticky='w', padx=(10, 5), pady=(5, 2))
        
        # Model path - make entry wider
        self.model_path = tk.StringVar()
        self.model_entry = ttk.Entry(self.visibility_model_frame, textvariable=self.model_path, width=40)
        self.model_entry.grid(row=0, column=1, padx=(5, 5), pady=(5, 2), sticky='ew')
        self.model_button = ttk.Button(
            self.visibility_model_frame, 
            text="Browse...", 
            command=lambda: self.select_visibility_file("model")
        )
        self.model_button.grid(row=0, column=2, padx=(0, 10), pady=(5, 2))
        
        # Training data selection - increase padding for better spacing
        self.training_radio = ttk.Radiobutton(
            self.visibility_model_frame,
            text="Training Data",
            variable=self.model_type_var,
            value="training",
            command=self.on_training_radio_select
        )
        self.training_radio.grid(row=1, column=0, sticky='w', padx=(10, 5), pady=(2, 5))
        
        # Training path - make entry wider
        self.training_path = tk.StringVar()
        self.training_entry = ttk.Entry(self.visibility_model_frame, textvariable=self.training_path, width=40)
        self.training_entry.grid(row=1, column=1, padx=(5, 5), pady=(2, 5), sticky='ew')
        self.training_button = ttk.Button(
            self.visibility_model_frame, 
            text="Browse...", 
            command=lambda: self.select_visibility_file("training")
        )
        self.training_button.grid(row=1, column=2, padx=(0, 10), pady=(2, 5))
        
        # Add Training Guide button inside the visibility model frame - center it better
        self.help_button = ttk.Button(
            self.visibility_model_frame,
            text="Training Guide",
            command=self.show_training_guide
        )
        self.help_button.grid(row=2, column=0, columnspan=3, pady=(0, 10))
        
        # Create a separate LabelFrame for the altitude threshold - CLEARLY SEPARATED FROM FUNCTIONS
        # Create threshold frame after functions frame
        self.threshold_frame = ttk.LabelFrame(self.left_frame, text="Altitude Threshold")
        self.threshold_frame.pack(fill=tk.X, pady=(10, 10))
        
        # Create a frame inside the LabelFrame for better layout
        threshold_content = ttk.Frame(self.threshold_frame)
        threshold_content.pack(fill=tk.X, padx=10, pady=5)
        
        # Add altitude threshold controls
        ttk.Label(threshold_content, text="Altitude Threshold (m):").grid(row=0, column=0, sticky='w', padx=(0, 5))
        
        self.threshold_var = tk.StringVar(value=str(self.altitude_threshold))
        threshold_entry = ttk.Entry(threshold_content, textvariable=self.threshold_var, width=6)
        threshold_entry.grid(row=0, column=1, padx=5, sticky='w')
        
        apply_button = ttk.Button(threshold_content, text="Apply", command=self.update_threshold)
        apply_button.grid(row=0, column=2, padx=5, sticky='w')
        
        # Add explanation text for altitude threshold
        ttk.Label(
            threshold_content, 
            text="(Filters out images that are too high to see the seabed)",
            font=("", 8, "italic")
        ).grid(row=1, column=0, columnspan=3, sticky='w', pady=(5, 0))
        
        # Add process button as the last element in the left frame (below everything else)
        process_button_frame = ttk.Frame(self.left_frame)
        process_button_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.process_button = ttk.Button(
            process_button_frame,
            text="Process Images",
            command=self.process_images,
            style="AccentButton.TButton"  # Apply a custom style to make it stand out
        )
        self.process_button.pack(fill=tk.X, padx=10, pady=10, ipady=5)  # Make button taller with ipady

        # Since visibility analysis is checked by default, show the options immediately
        if self.visibility_analyzer_var.get():
            self.toggle_visibility_options()

        # Since footprint map is checked by default, show nav file selection immediately  
        if self.footprint_map_var.get():
            self.update_nav_file_visibility()

    def toggle_visibility_options(self):
        """Show or hide visibility analysis options based on checkbox state"""
        if self.visibility_analyzer_var.get():
            # Show the model frame - position it right after the visibility checkbox
            self.visibility_model_frame.grid_remove()  # Remove first to make sure it's properly positioned
            self.visibility_model_frame.grid(row=self.vis_note_label.grid_info()['row'] + 1, 
                                           column=0, sticky='ew', padx=25, pady=(0, 5))
            
            # Set default path in the model entry field instead of showing a dialog
            if not hasattr(self, 'model_path_initialized') or not self.model_path_initialized:
                self.model_path_initialized = True  # Mark as initialized
                
                if not self.model_path.get() and not self.training_path.get():
                    # Get the default models directory
                    default_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                           "v_a_pre-trained_models")
                    
                    # Look for existing .h5 files in that directory
                    if os.path.exists(default_dir):
                        model_files = [f for f in os.listdir(default_dir) if f.endswith('.h5')]
                        if model_files:
                            # Use the most recent model file based on filename (assuming timestamp in name)
                            model_files.sort(reverse=True)  # Sort in descending order
                            default_model = os.path.join(default_dir, model_files[0])
                            self.model_path.set(default_model)
                            # Only log if log_text exists
                            if hasattr(self, 'log_text'):
                                self.log_message(f"Default visibility model: {default_model}")
                        else:
                            # No model files found, just set the directory
                            self.model_path.set(default_dir)
                            if hasattr(self, 'log_text'):
                                self.log_message(f"No model files found in default directory. Please select a model.")
                    else:
                        # Default directory doesn't exist, create it and set the path
                        os.makedirs(default_dir, exist_ok=True)
                        self.model_path.set(default_dir)
                        if hasattr(self, 'log_text'):
                            self.log_message(f"Please select a visibility model file.")
                    
                    # Make sure model radio is selected by default
                    self.model_type_var.set("model")
                    self.on_model_radio_select()
        else:
            # Hide the model frame
            self.visibility_model_frame.grid_remove()
        
        self.update_all_checkbox()

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
        threshold_frame.grid(row=8, column=0, sticky='ew', pady=(10, 5))
        
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
        ).grid(row=9, column=0, sticky='w', pady=(0, 10), padx=25)

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
            self.altitude_map.set_altitude_thresholds(new_threshold, 4.0)  # Keep low threshold at 4m
            
            # Update the footprint map if it exists
            if hasattr(self, 'footprint_map'):
                self.footprint_map.altitude_threshold = new_threshold
                
            # Update the visibility analyzer if it exists
            if hasattr(self, 'visibility_analyzer'):
                self.visibility_analyzer.altitude_threshold = new_threshold
                
            # Log the change
            self.log_message(f"Altitude threshold set to {new_threshold:.1f}m")
            
        except ValueError:
            messagebox.showwarning("Invalid Input", "Please enter a valid number for the altitude threshold.")
        except Exception as e:
            self.log_message(f"Error updating threshold: {str(e)}")

    def _load_image(self, image_path: str, target_size=(224, 224)) -> Optional[np.ndarray]:
        """Load and preprocess an image for the model"""
        try:
            # Use TensorFlow's method to load the image
            img = self._load_img(image_path, target_size=target_size)
            img_array = self._img_to_array(img)
            # Apply VGG16 preprocessing (normalize for the model)
            img_array = self._preprocess_input(img_array)
            return img_array
        except Exception as e:
            print(f"Error loading image {image_path}: {str(e)}")
            return None

    def show_training_guide(self):
        """Display a guide for setting up training data"""
        # Lazy-load the visibility analyzer if needed
        if not hasattr(self, 'visibility_analyzer'):
            from src.models.visibility_analyzer import VisibilityAnalyzer
            self.visibility_analyzer = VisibilityAnalyzer(self.altitude_threshold)
        
        # Create a dialog window
        guide_window = tk.Toplevel(self.master)
        guide_window.title("Training Data Structure Guide")
        guide_window.geometry("650x450")
        
        # Add text widget for the guide content
        guide_text = tk.Text(guide_window, wrap=tk.WORD, padx=10, pady=10)
        guide_text.pack(fill=tk.BOTH, expand=True)
        
        # Create scrollbar
        scrollbar = ttk.Scrollbar(guide_text, command=guide_text.yview)
        guide_text.config(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add the guide content
        guide_content = """
TRAINING DATA DIRECTORY STRUCTURE GUIDE

Your training data folder should have this structure:

Training_Data/
  ├── zero_visibility/
  │   ├── image1.jpg
  │   ├── image2.jpg
  │   └── ...
  ├── low_visibility/
  │   ├── image1.jpg
  │   ├── image2.jpg
  │   └── ...
  ├── good_visibility/
  │   ├── image1.jpg
  │   ├── image2.jpg
  │   └── ...
  └── great_visibility/
      ├── image1.jpg
      ├── image2.jpg
      └── ...

IMPORTANT NOTES:

1. Each category subfolder MUST be named exactly as shown above
2. Each category should contain example images for that visibility level
3. Supported image formats: .jpg, .jpeg, .png, .tif, .tiff
4. For best results, include at least 20-30 images per category
5. Images should be representative of the category (clear examples)
6. Avoid using the same or very similar images across categories

HOW TO PREPARE YOUR DATA:

1. Create a main training folder (e.g., "Training_Data")
2. Inside it, create the four subfolders with exact names shown above
3. Sort your example images into the appropriate folders
4. Browse to the main folder (not the subfolders) when selecting training data

The visibility categories represent:
- zero_visibility: No visible features, complete turbidity
- low_visibility: Minimal features visible, heavy turbidity
- good_visibility: Clear features, moderate turbidity
- great_visibility: Very clear features, minimal turbidity
"""
        
        guide_text.insert(tk.END, guide_content)
        guide_text.config(state=tk.DISABLED)  # Make read-only
        
        # Add a close button
        close_button = ttk.Button(guide_window, text="Close", command=guide_window.destroy)
        close_button.pack(pady=10)
        
        # Make dialog modal
        guide_window.transient(self.master)
        guide_window.grab_set()
        self.master.wait_window(guide_window)

    def on_training_radio_select(self):
        """Called when training radio button is selected"""
        path = self.training_path.get()
        if path and os.path.isdir(path):
            # Check training directory structure
            if hasattr(self, 'visibility_analyzer'):
                message = self.visibility_analyzer.verify_and_provide_training_guidance(path)
                if "Error" in message or "Warning" in message:
                    self.log_message(message)
        
        # Update UI state
        self.training_entry.config(state=tk.NORMAL)
        self.training_button.config(state=tk.NORMAL)
        self.help_button.config(state=tk.NORMAL)
        self.model_entry.config(state=tk.DISABLED)
        self.model_button.config(state=tk.DISABLED)

    def on_model_radio_select(self):
        """Called when model radio button is selected"""
        # Update UI state
        self.model_entry.config(state=tk.NORMAL)
        self.model_button.config(state=tk.NORMAL)
        self.training_entry.config(state=tk.DISABLED)
        self.training_button.config(state=tk.DISABLED)
        self.help_button.config(state=tk.DISABLED)

    def select_highlight_images(self, input_folder, output_folder):
        """Select highlight images from the dataset"""
        self.log_message("Selecting highlight images from the dataset...")
        
        try:
            # Get visibility results if available from a previous analysis
            visibility_results = None
            if hasattr(self, 'visibility_analyzer') and hasattr(self.visibility_analyzer, 'visibility_stats'):
                visibility_results = self.visibility_analyzer.visibility_stats
            
            # Define min altitude threshold 
            min_altitude_threshold = 4.0
            
            # Call the highlight selector with our app's altitude threshold
            highlight_paths = self.highlight_selector.select_highlights(
                input_folder=input_folder,
                output_folder=output_folder,
                count=10,  # Select 10 highlight images
                progress_callback=self.update_progress,
                altitude_threshold=self.altitude_threshold,
                min_altitude_threshold=min_altitude_threshold,
                visibility_results=visibility_results
            )
            
            if highlight_paths:
                self.log_message(f"Successfully selected {len(highlight_paths)} highlight images")
                self.log_message(f"Highlight images saved to: {os.path.join(output_folder, 'highlight_images')}")
            else:
                self.log_message("No highlight images were selected")
                
            return True
                
        except Exception as e:
            self.log_message(f"Error during highlight image selection: {str(e)}")
            import traceback
            self.log_message(traceback.format_exc())
            return False
