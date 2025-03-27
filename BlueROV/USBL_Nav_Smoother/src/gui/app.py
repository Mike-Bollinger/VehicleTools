import os
import tkinter as tk
from tkinter import filedialog, messagebox, Label, Button, Frame, ttk, IntVar, Checkbutton, StringVar
import platform
import subprocess
import pandas as pd

# Import our modules
from models.nccos_window_smoother import smooth_navigation, WINDOW_SIZE, GAUSSIAN_SIGMA
from models.tator_kalman_filter import smooth_with_kalman, KF_MEASUREMENT_NOISE, KF_PROCESS_NOISE, KF_TIME_GAP_THRESHOLD, KF_INIT_COVARIANCE
from models.oer_moving_average import smooth_with_oer_average, OER_WINDOW_SIZE, OER_TOLERANCE
from utils.file_handlers import read_navigation_files, read_diagnostic_files, save_output_files
from utils.visualization import create_plots, create_gif, create_comparative_analysis, create_variants_gif

# Define model configuration variants
MODEL_VARIANTS = {
    'window': [
        {
            'name': 'Default',
            'window_size': WINDOW_SIZE,
            'gaussian_sigma': GAUSSIAN_SIGMA
        },
        {
            'name': 'More Aggressive',
            'window_size': 11,  # Larger window for more smoothing
            'gaussian_sigma': 3.0  # Higher sigma for stronger smoothing
        },
        {
            'name': 'Less Aggressive',
            'window_size': 5,  # Smaller window for less smoothing
            'gaussian_sigma': 1.0  # Lower sigma for gentler smoothing
        }
    ],
    'kalman': [
        {
            'name': 'Default',
            'measurement_noise': KF_MEASUREMENT_NOISE,
            'process_noise': KF_PROCESS_NOISE,
            'time_gap_threshold': KF_TIME_GAP_THRESHOLD,
            'init_covariance': KF_INIT_COVARIANCE
        },
        {
            'name': 'More Aggressive',
            'measurement_noise': 50.0,  # Higher value trusts measurements less
            'process_noise': 0.01,  # Lower value assumes smoother motion
            'time_gap_threshold': 15.0,  # Higher value maintains longer segments
            'init_covariance': KF_INIT_COVARIANCE
        },
        {
            'name': 'Less Aggressive',
            'measurement_noise': 20.0,  # Lower value trusts measurements more
            'process_noise': 0.03,  # Higher value allows more natural motion
            'time_gap_threshold': 8.0,  # Lower value prevents over-smoothing across gaps
            'init_covariance': KF_INIT_COVARIANCE
        }
    ],
    'oer': [
        {
            'name': 'Default',
            'window_size': OER_WINDOW_SIZE,
            'tolerance': OER_TOLERANCE
        },
        {
            'name': 'More Aggressive',
            'window_size': 25,  # Larger window for more averaging
            'tolerance': 0.00005  # Higher tolerance for more simplification
        },
        {
            'name': 'Less Aggressive',
            'window_size': 9,  # Smaller window for less averaging
            'tolerance': 0.000005  # Lower tolerance for less simplification
        }
    ]
}

class NavSmootherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("USBL Navigation Smoothing")  # Changed from Enhancement to Smoothing
        self.root.geometry("650x750")
        self.root.configure(padx=20, pady=20)
        
        # Flag for shapefile support (set from run_app)
        self.shapefile_support = True
        
        # Initialize file lists
        self.nav_files = []
        self.diag_files = []
        self.output_dir = ""
        
        # Initialize model selection variables
        self.window_var = IntVar(value=1)
        self.kalman_var = IntVar(value=0)
        self.oer_var = IntVar(value=0)
        self.compare_mode_var = IntVar(value=0)
        
        # Initialize variant selection variables
        self.compare_variants_var = IntVar(value=0)
        
        # Create the GUI components
        self.create_gui()
    
    def create_gui(self):
        """Create all GUI components"""
        # Create file selection frame
        file_frame = ttk.LabelFrame(self.root, text="File Selection")
        file_frame.pack(fill="x", padx=10, pady=10)
        
        # Navigation files selection
        nav_frame = Frame(file_frame)
        nav_frame.pack(fill="x", pady=5)
        
        Label(nav_frame, text="Navigation Files:").pack(side=tk.LEFT, padx=5)
        self.nav_files_label = Label(nav_frame, text="No files selected", fg="gray", wraplength=300)
        self.nav_files_label.pack(side=tk.LEFT, padx=5, fill="x", expand=True)
        
        Button(nav_frame, text="Select Files", command=self.select_nav_files).pack(side=tk.RIGHT, padx=5)
        
        # Diagnostic files selection
        diag_frame = Frame(file_frame)
        diag_frame.pack(fill="x", pady=5)
        
        Label(diag_frame, text="Diagnostic Files:").pack(side=tk.LEFT, padx=5)
        self.diag_files_label = Label(diag_frame, text="No files selected (optional)", fg="gray", wraplength=300)
        self.diag_files_label.pack(side=tk.LEFT, padx=5, fill="x", expand=True)
        
        Button(diag_frame, text="Select Files", command=self.select_diag_files).pack(side=tk.RIGHT, padx=5)
        
        # Output directory selection
        output_frame = Frame(file_frame)
        output_frame.pack(fill="x", pady=5)
        
        Label(output_frame, text="Output Directory:").pack(side=tk.LEFT, padx=5)
        self.output_dir_label = Label(output_frame, text="No directory selected", fg="gray", wraplength=300)
        self.output_dir_label.pack(side=tk.LEFT, padx=5, fill="x", expand=True)
        
        Button(output_frame, text="Select Directory", command=self.select_output_dir).pack(side=tk.RIGHT, padx=5)
        
        # Model selection frame
        model_frame = ttk.LabelFrame(self.root, text="Smoothing Models")
        model_frame.pack(fill="x", padx=10, pady=10)
        
        # NCCOS Window
        self.window_checkbox = Checkbutton(
            model_frame, 
            text="NCCOS Moving Window and Gaussian Filter",
            variable=self.window_var
        )
        self.window_checkbox.grid(row=0, column=0, sticky="w", padx=20, pady=5)
        
        # TATOR Kalman
        self.kalman_checkbox = Checkbutton(
            model_frame, 
            text="TATOR Kalman Filter plus Fit",
            variable=self.kalman_var
        )
        self.kalman_checkbox.grid(row=1, column=0, sticky="w", padx=20, pady=5)
        
        # OER Moving Average
        self.oer_checkbox = Checkbutton(
            model_frame, 
            text="OER Moving Average",
            variable=self.oer_var
        )
        self.oer_checkbox.grid(row=2, column=0, sticky="w", padx=20, pady=5)
        
        # Compare mode
        self.compare_checkbox = Checkbutton(
            model_frame, 
            text="Compare All Models (selects all models)",
            variable=self.compare_mode_var,
            command=self.update_model_selection
        )
        self.compare_checkbox.grid(row=3, column=0, sticky="w", padx=20, pady=10)
        
        # Model comparison options
        self.variant_frame = ttk.LabelFrame(self.root, text="Model Comparison Options")
        self.variant_frame.pack(fill="x", padx=10, pady=10)
        
        self.compare_variants_checkbox = Checkbutton(
            self.variant_frame, 
            text="Compare configuration variants for each model",
            variable=self.compare_variants_var,
            command=self.update_variant_selection,
            state=tk.DISABLED
        )
        self.compare_variants_checkbox.grid(row=0, column=0, sticky="w", padx=20, pady=5)
        
        # Add note about variant comparison
        ttk.Label(
            self.variant_frame, 
            text="Note: This will compare different configuration settings for each selected model",
            font=("Arial", 8, "italic")
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 5))
        
        # Process button
        process_frame = Frame(self.root)
        process_frame.pack(fill="x", pady=20)
        
        self.process_button = Button(process_frame, text="Process Files", command=self.process_files, height=2, bg="#4CAF50", fg="white")
        self.process_button.pack(fill="x", padx=50)
        
        # Status display
        status_frame = Frame(self.root)
        status_frame.pack(fill="x", pady=10)
        
        self.status_label = Label(status_frame, text="Ready", fg="blue")
        self.status_label.pack()
        
        # Version info
        version_frame = Frame(self.root)
        version_frame.pack(fill="x", pady=10)
        
        Label(version_frame, text="USBL Navigation Smoothing Tool v1.0", font=("Arial", 8)).pack()  # Changed from Enhancement to Smoothing
        
        # Set focus to first button
        self.root.after(100, lambda: self.root.focus_force())
    
    def select_nav_files(self):
        """Open file dialog to select navigation files"""
        filetypes = [("CSV files", "*.csv"), ("Text files", "*.txt"), ("All files", "*.*")]
        files = filedialog.askopenfilenames(title="Select Navigation Files", filetypes=filetypes)
        
        if files:
            self.nav_files = list(files)
            if len(self.nav_files) == 1:
                self.nav_files_label.config(text=os.path.basename(self.nav_files[0]))
            else:
                self.nav_files_label.config(text=f"{len(self.nav_files)} files selected")
    
    def select_diag_files(self):
        """Open file dialog to select diagnostic files"""
        filetypes = [("CSV files", "*.csv"), ("Text files", "*.txt"), ("All files", "*.*")]
        files = filedialog.askopenfilenames(title="Select Diagnostic Files", filetypes=filetypes)
        
        if files:
            self.diag_files = list(files)
            if len(self.diag_files) == 1:
                self.diag_files_label.config(text=os.path.basename(self.diag_files[0]))
            else:
                self.diag_files_label.config(text=f"{len(self.diag_files)} files selected")
    
    def select_output_dir(self):
        """Open dialog to select output directory"""
        directory = filedialog.askdirectory(title="Select Output Directory")
        
        if directory:
            self.output_dir = directory
            self.output_dir_label.config(text=directory)
    
    def update_model_selection(self):
        """Update model checkboxes based on compare mode selection"""
        if self.compare_mode_var.get() == 1:
            # If compare mode is selected, enable all models
            self.window_var.set(1)
            self.kalman_var.set(1)
            self.oer_var.set(1)
            
            # Disable individual checkboxes in compare mode
            self.window_checkbox.config(state=tk.DISABLED)
            self.kalman_checkbox.config(state=tk.DISABLED)
            self.oer_checkbox.config(state=tk.DISABLED)
            
            # Enable variant comparison option
            self.compare_variants_checkbox.config(state=tk.NORMAL)
        else:
            # Enable individual checkboxes when compare mode is off
            self.window_checkbox.config(state=tk.NORMAL)
            self.kalman_checkbox.config(state=tk.NORMAL)
            self.oer_checkbox.config(state=tk.NORMAL)
            
            # Disable variant comparison option when not in compare mode
            self.compare_variants_checkbox.config(state=tk.DISABLED)
            self.compare_variants_var.set(0)
    
    def update_variant_selection(self):
        """Update UI based on variant comparison selection"""
        # This method is reserved for future enhancements
        # such as allowing selection of specific variants
        pass
    
    def process_files(self):
        """Process the selected files with the chosen models"""
        if not self.nav_files:
            messagebox.showerror("Error", "Please select at least one navigation file.")
            return
            
        if not self.output_dir:
            messagebox.showerror("Error", "Please select an output directory.")
            return
            
        # Check if at least one model is selected when not in compare mode
        if self.compare_mode_var.get() == 0 and not any([
            self.window_var.get(),
            self.kalman_var.get(),
            self.oer_var.get()
        ]):
            messagebox.showerror("Error", "Please select at least one smoothing model.")
            return
            
        try:
            # Update status
            self.status_label.config(text="Processing...", fg="blue")
            self.root.update()
            
            # Show warning if shapefile support is disabled
            if not getattr(self, 'shapefile_support', True):
                print("WARNING: Shapefile creation is disabled. Install geopandas and shapely to enable.")
                messagebox.showwarning("Shapefile Support Disabled", 
                                       "Shapefile creation is disabled because geopandas or shapely is not installed.\n\n"
                                       "To enable shapefile creation, install the required packages:\n"
                                       "pip install geopandas shapely")
            
            # Read navigation files
            nav_data = read_navigation_files(self.nav_files)
            
            # Read diagnostic files if provided
            diag_data = read_diagnostic_files(self.diag_files) if self.diag_files else None
            
            # Create a merged dataset from nav and diag data
            merged_data = self.create_merged_dataset(nav_data, diag_data)
            
            # Save the merged dataset as CSV
            basename = os.path.splitext(os.path.basename(self.nav_files[0]))[0]
            merged_file = os.path.join(self.output_dir, f"{basename}_Merged_Data.csv")
            merged_data.to_csv(merged_file, index=False)
            print(f"Saved merged navigation and diagnostic data to {merged_file}")
            
            # Always save original data shapefile
            original_shapefile_base = os.path.join(self.output_dir, f"{basename}_Original")
            self.save_as_shapefile(nav_data, original_shapefile_base)
            print(f"Saved original data shapefiles")
            
            # Process based on selected mode
            if self.compare_mode_var.get() == 1:
                # If variant comparison is enabled
                if self.compare_variants_var.get() == 1:
                    self.process_variant_comparison(nav_data, diag_data)
                else:
                    self.process_model_comparison(nav_data, diag_data)
            else:
                # Standard processing mode
                self.process_standard_mode(nav_data, diag_data)
                
            # Update status
            self.status_label.config(text="Processing completed successfully!", fg="green")
            
            messagebox.showinfo("Success", "Processing completed successfully. Results saved to the output directory.")
            
            # Open output directory
            self.open_output_directory()
            
        except Exception as e:
            self.status_label.config(text=f"Error: {str(e)}", fg="red")
            messagebox.showerror("Error", f"An error occurred during processing: {str(e)}")
            import traceback
            traceback.print_exc()

    def create_merged_dataset(self, nav_data, diag_data):
        """Create a merged dataset from navigation and diagnostic data"""
        # Start with a copy of navigation data
        merged_data = nav_data.copy()
        
        # If diagnostic data is available, merge it with navigation data
        if diag_data is not None and not diag_data.empty:
            # Add placeholder columns for diagnostic data
            for col in diag_data.columns:
                if col not in merged_data.columns and col != 'Timestamp':
                    merged_data[col] = None
            
            # Try to match timestamps between nav and diagnostic data
            for i, row in merged_data.iterrows():
                # Find matching diagnostic data by closest timestamp
                closest_diag = diag_data.iloc[
                    (diag_data['Timestamp'] - row['Timestamp']).abs().argsort()[:1]
                ]
                
                if not closest_diag.empty:
                    # Add all diagnostic columns (except Timestamp) to merged data
                    for col in diag_data.columns:
                        if col != 'Timestamp' and col in merged_data.columns:
                            merged_data.at[i, col] = closest_diag[col].values[0]
        
        return merged_data

    def save_as_shapefile(self, df, output_path):
        """
        Save dataframe with coordinate data as ESRI shapefile (both point and line)
        
        Args:
            df (pandas.DataFrame): DataFrame with Latitude and Longitude columns
            output_path (str): Base path for output shapefile (without extension)
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # First check if geopandas is installed
            try:
                import geopandas as gpd
                from shapely.geometry import Point, LineString
            except ImportError:
                print("WARNING: geopandas or shapely not installed. Cannot create shapefiles.")
                print("Please install with: pip install geopandas shapely")
                return False

            # Make sure we have latitude and longitude data
            if 'Latitude' not in df.columns or 'Longitude' not in df.columns:
                print("ERROR: DataFrame missing Latitude or Longitude columns")
                return False
                
            # Remove any NaN values to avoid shapefile errors
            valid_df = df.dropna(subset=['Latitude', 'Longitude']).copy()
            if len(valid_df) < 2:
                print("ERROR: Not enough valid coordinates to create shapefile")
                return False

            print(f"Creating shapefiles at {output_path} with {len(valid_df)} points")
            
            # Convert datetime columns to string format for shapefile compatibility
            for col in valid_df.columns:
                if pd.api.types.is_datetime64_any_dtype(valid_df[col]):
                    print(f"Converting datetime column '{col}' to string format for shapefile compatibility")
                    valid_df[col] = valid_df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(valid_df[col].iloc[0], pd.Timestamp):
                    print(f"Converting Timestamp column '{col}' to string format for shapefile compatibility")
                    valid_df[col] = valid_df[col].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(x) else None)
            
            # Create point shapefile - each row becomes a point feature
            geometry = [Point(lon, lat) for lon, lat in zip(valid_df['Longitude'], valid_df['Latitude'])]
            gdf_points = gpd.GeoDataFrame(valid_df, geometry=geometry)
            
            # Set the coordinate reference system to WGS84
            gdf_points.crs = "EPSG:4326"
            
            # Save point shapefile
            point_output = f"{output_path}_points"
            gdf_points.to_file(point_output + ".shp")
            print(f"Saved point shapefile to {point_output}.shp")
            
            # Create line shapefile - all points become a single line feature
            coords = [(lon, lat) for lon, lat in zip(valid_df['Longitude'], valid_df['Latitude'])]
            if len(coords) >= 2:  # Need at least 2 points to make a line
                line_geom = LineString(coords)
                
                # Create a new GeoDataFrame with just the line
                gdf_line = gpd.GeoDataFrame(geometry=[line_geom])
                
                # Add key attributes from original data to the line feature
                # Create a subset of non-datetime attributes
                attrs_to_copy = []
                for attr in valid_df.columns:
                    if attr not in ['Latitude', 'Longitude', 'geometry']:
                        # Sample the first value to check if it can be added to shapefile
                        sample_value = valid_df[attr].iloc[0] if not valid_df[attr].isna().all() else None
                        if sample_value is not None:
                            attrs_to_copy.append(attr)
                
                # Copy selected attributes
                for attr in attrs_to_copy:
                    try:
                        gdf_line[attr] = valid_df[attr].iloc[0]  # Take first value
                    except Exception as e:
                        print(f"Could not add attribute {attr} to line shapefile: {str(e)}")
                
                # Set the coordinate reference system
                gdf_line.crs = "EPSG:4326"
                
                # Save line shapefile
                line_output = f"{output_path}_line"
                gdf_line.to_file(line_output + ".shp")
                print(f"Saved line shapefile to {line_output}.shp")
            else:
                print("WARNING: Not enough valid points to create line shapefile")
            
            return True
        except Exception as e:
            print(f"ERROR creating shapefile: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def process_standard_mode(self, nav_data, diag_data):
        """Process files in standard mode (individual model mode)"""
        print("Processing in standard mode...")
        
        # For each selected model, apply smoothing and save
        basename = os.path.splitext(os.path.basename(self.nav_files[0]))[0]
        
        # Always save original data shapefile again here just to be safe
        original_shapefile_base = os.path.join(self.output_dir, f"{basename}_Original")
        print("Creating shapefile for original data...")
        shapefile_success = self.save_as_shapefile(nav_data, original_shapefile_base)
        if not shapefile_success:
            print("WARNING: Failed to create shapefile for original data")
        
        # Apply NCCOS Moving Window smoother
        if self.window_var.get() == 1:
            print("Processing NCCOS Moving Window smoother...")
            window_df = smooth_navigation(nav_data)
            
            # Save to CSV
            window_file = os.path.join(self.output_dir, f"{basename}_Window_Smoothed.csv")
            window_df.to_csv(window_file, index=False)
            print(f"Saved Window smoothed data to {window_file}")
            
            # Create visualization
            create_plots(window_df, os.path.join(self.output_dir, f"{basename}_Window"), 
                        original_df=nav_data)
            
            # Save shapefiles for window smoothed data
            window_shapefile_base = os.path.join(self.output_dir, f"{basename}_Window_Smoothed")
            print("Creating shapefile for Window smoothed data...")
            shapefile_success = self.save_as_shapefile(window_df, window_shapefile_base)
            if not shapefile_success:
                print("WARNING: Failed to create shapefile for Window smoothed data")
        
        # Apply TATOR Kalman filter
        if self.kalman_var.get() == 1:
            # Use merged data for Kalman filtering
            merged_data = self.create_merged_dataset(nav_data, diag_data)
            kalman_df = smooth_with_kalman(merged_data)
            
            kalman_file = os.path.join(self.output_dir, f"{basename}_Kalman_Smoothed.csv")
            kalman_df.to_csv(kalman_file, index=False)
            
            # Create visualization
            create_plots(kalman_df, os.path.join(self.output_dir, f"{basename}_Kalman"), 
                        original_df=nav_data)
            
            # Save shapefiles for Kalman smoothed data
            kalman_shapefile_base = os.path.join(self.output_dir, f"{basename}_Kalman_Smoothed")
            self.save_as_shapefile(kalman_df, kalman_shapefile_base)
        
        # Apply OER Moving Average
        if self.oer_var.get() == 1:
            oer_df = smooth_with_oer_average(nav_data)
            oer_file = os.path.join(self.output_dir, f"{basename}_OER_Smoothed.csv")
            oer_df.to_csv(oer_file, index=False)
            
            # Create visualization
            create_plots(oer_df, os.path.join(self.output_dir, f"{basename}_OER"), 
                        original_df=nav_data)
            
            # Save shapefiles for OER smoothed data
            oer_shapefile_base = os.path.join(self.output_dir, f"{basename}_OER_Smoothed")
            self.save_as_shapefile(oer_df, oer_shapefile_base)
        
        print(f"Standard processing completed. Results saved to {self.output_dir}")

    def process_model_comparison(self, nav_data, diag_data):
        """Process comparison of different models (standard compare mode)"""
        print("Processing model comparison...")
        basename = os.path.splitext(os.path.basename(self.nav_files[0]))[0]
        
        # Apply each model and store results
        window_df = None
        kalman_df = None
        oer_df = None
        
        # Apply NCCOS Moving Window smoother
        if self.window_var.get() == 1:
            window_df = smooth_navigation(nav_data)
        
        # Apply TATOR Kalman filter
        if self.kalman_var.get() == 1:
            # Use merged dataset
            merged_data = self.create_merged_dataset(nav_data, diag_data)
            kalman_df = smooth_with_kalman(merged_data)
        
        # Apply OER Moving Average
        if self.oer_var.get() == 1:
            oer_df = smooth_with_oer_average(nav_data)
        
        # Create comparison DataFrame
        comparison_columns = {
            'Timestamp': nav_data['Timestamp'],
            'Original_Latitude': nav_data['Latitude'],
            'Original_Longitude': nav_data['Longitude']
        }
        
        if window_df is not None:
            comparison_columns['Window_Latitude'] = window_df['Latitude']
            comparison_columns['Window_Longitude'] = window_df['Longitude']
            
        if kalman_df is not None:
            comparison_columns['Kalman_Latitude'] = kalman_df['Latitude']
            comparison_columns['Kalman_Longitude'] = kalman_df['Longitude']
            
        if oer_df is not None:
            comparison_columns['OER_Latitude'] = oer_df['Latitude']
            comparison_columns['OER_Longitude'] = oer_df['Longitude']
        
        comparison_df = pd.DataFrame(comparison_columns)
        
        # Save comparison file
        comparison_file = os.path.join(self.output_dir, f"{basename}_Smoothing_Comparison.csv")
        comparison_df.to_csv(comparison_file, index=False)
        
        # Create comparison plot
        output_file_base = os.path.join(self.output_dir, f"{basename}_Comparison")
        create_plots(comparison_df, output_file_base)
        
        # Create animated GIF if we have multiple points
        if len(comparison_df) > 5:
            # Create frames directory in parent output directory
            frames_dir = os.path.join(self.output_dir, f"{basename}_Animation_Frames")
            os.makedirs(frames_dir, exist_ok=True)
            
            # Save main GIF to parent directory, frames to subfolder
            output_gif = os.path.join(self.output_dir, f"{basename}_Animation.gif")
            
            try:
                # Check if file exists and is accessible before trying to write
                if os.path.exists(output_gif):
                    try:
                        # Try to open the file to check if it's accessible
                        with open(output_gif, 'a'):
                            pass
                    except PermissionError:
                        # File is open in another application, use an alternative name
                        print(f"Warning: Could not access {output_gif}. File may be open in another application.")
                        output_gif = os.path.join(self.output_dir, f"{basename}_Animation_new.gif")
                        print(f"Using alternative filename: {output_gif}")
                
                create_gif(comparison_df, output_gif, basename, frames_dir=frames_dir)
                print(f"Animation saved to {output_gif}")
            except Exception as e:
                print(f"Error creating animation: {str(e)}")
                import traceback
                traceback.print_exc()
                messagebox.showwarning("Animation Creation Error", 
                                      f"Could not create the animation GIF: {str(e)}\n\n"
                                      "This could be because the file is already open in another application "
                                      "or there are insufficient permissions.")
        
        print(f"Model comparison completed. Results saved to {comparison_file}")

    def process_variant_comparison(self, nav_data, diag_data):
        """Process comparison of different configuration variants for each model"""
        print("Processing variant comparison...")
        
        # Create list to store all model outputs
        all_variants = []
        
        # Start with original data
        all_variants.append({
            'name': 'Original',
            'data': nav_data
        })
        
        # Merged data for Kalman filter
        merged_data = self.create_merged_dataset(nav_data, diag_data)
        
        basename = os.path.splitext(os.path.basename(self.nav_files[0]))[0]
        
        # Process NCCOS Moving Window variants
        if self.window_var.get() == 1:
            for variant in MODEL_VARIANTS['window']:
                print(f"Processing NCCOS {variant['name']} variant...")
                smoothed = smooth_navigation(
                    nav_data, 
                    window_size=variant['window_size'], 
                    gaussian_sigma=variant['gaussian_sigma']
                )
                
                variant_name = f"NCCOS_{variant['name']}"
                all_variants.append({
                    'name': f"NCCOS {variant['name']}",
                    'data': smoothed
                })
                
                # Save shapefile for each variant
                variant_shapefile_base = os.path.join(self.output_dir, f"{basename}_{variant_name}")
                self.save_as_shapefile(smoothed, variant_shapefile_base)
        
        # Process Kalman filter variants
        if self.kalman_var.get() == 1:
            for variant in MODEL_VARIANTS['kalman']:
                print(f"Processing TATOR Kalman {variant['name']} variant...")
                
                smoothed = smooth_with_kalman(
                    merged_data,
                    measurement_noise=variant['measurement_noise'],
                    process_noise=variant['process_noise'],
                    time_gap_threshold=variant['time_gap_threshold'],
                    init_covariance=variant['init_covariance']
                )
                
                variant_name = f"TATOR_Kalman_{variant['name']}"
                all_variants.append({
                    'name': f"TATOR Kalman {variant['name']}",
                    'data': smoothed
                })
                
                # Save shapefile for each variant
                variant_shapefile_base = os.path.join(self.output_dir, f"{basename}_{variant_name}")
                self.save_as_shapefile(smoothed, variant_shapefile_base)
        
        # Process OER Moving Average variants
        if self.oer_var.get() == 1:
            for variant in MODEL_VARIANTS['oer']:
                print(f"Processing OER {variant['name']} variant...")
                smoothed = smooth_with_oer_average(
                    nav_data,
                    window_size=variant['window_size'],
                    tolerance=variant['tolerance']
                )
                
                variant_name = f"OER_{variant['name']}"
                all_variants.append({
                    'name': f"OER {variant['name']}",
                    'data': smoothed
                })
                
                # Save shapefile for each variant
                variant_shapefile_base = os.path.join(self.output_dir, f"{basename}_{variant_name}")
                self.save_as_shapefile(smoothed, variant_shapefile_base)
        
        # Create comparative visualization
        print("Creating comparative visualization...")
        output_filename = f"{basename}_Configuration_Variants_Comparison"
        
        create_comparative_analysis(
            all_variants,
            os.path.join(self.output_dir, output_filename)
        )
        
        # Save to CSV for further analysis
        comparison_df = pd.DataFrame()
        comparison_df['Timestamp'] = nav_data['Timestamp']
        comparison_df['Original_Latitude'] = nav_data['Latitude']
        comparison_df['Original_Longitude'] = nav_data['Longitude']
        
        for variant in all_variants[1:]:  # Skip original which is already added
            comparison_df[f"{variant['name'].replace(' ', '_')}_Latitude"] = variant['data']['Latitude']
            comparison_df[f"{variant['name'].replace(' ', '_')}_Longitude"] = variant['data']['Longitude']
        
        comparison_df.to_csv(
            os.path.join(self.output_dir, f"{output_filename}.csv"),
            index=False
        )
        
        # Create animated GIF with all variants
        if len(nav_data) > 5:
            print("Creating animated GIF of configuration variants...")
            create_variants_gif(all_variants, os.path.join(self.output_dir, f"{basename}_Variants_Animation.gif"))
        
        print(f"Variant comparison completed. Results saved to {self.output_dir}")
    
    def open_output_directory(self):
        """Open the output directory in file explorer"""
        if not self.output_dir or not os.path.exists(self.output_dir):
            return
            
        if platform.system() == "Windows":
            os.startfile(self.output_dir)
        elif platform.system() == "Darwin":  # macOS
            subprocess.call(["open", self.output_dir])
        else:  # Linux
            subprocess.call(["xdg-open", self.output_dir])

def run_app():
    """Run the main application"""
    
    # Check for required libraries
    try:
        import pandas as pd
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend for file saving
    except ImportError as e:
        print(f"Error: Missing required library - {str(e)}")
        print("Please install required libraries: pip install pandas numpy matplotlib")
        return
    
    # Check for optional libraries
    shapefile_support = True
    try:
        import geopandas
        import shapely
    except ImportError:
        shapefile_support = False
        print("WARNING: geopandas or shapely libraries not found. Shapefile creation will be disabled.")
        print("To enable shapefile creation, install: pip install geopandas shapely")
    
    # Create and run the main window
    root = tk.Tk()
    app = NavSmootherApp(root)
    app.shapefile_support = shapefile_support  # Add flag to app instance
    root.mainloop()

if __name__ == "__main__":
    run_app()