"""
# ArcGIS Pro Layout Automator

## Description
A tool for batch exporting ArcGIS Pro layouts with different visible layers.
Specifically designed for creating map series from dive data where each dive
has its own layer that needs to be turned on/off.

## Features
- Automatically detects dive layers in group layers
- Allows selection of which layer groups to process
- Controls map extent through smart element avoidance
- Exports high-quality JPEGs with customizable DPI
- Provides detailed logging and progress tracking
- Works with any ArcGIS Pro project structure

## Usage
1. Select an ArcGIS Pro project
2. Choose a layout template
3. Select which layer groups contain dive layers
4. Set the output folder and DPI
5. Run the analysis to see what dive numbers will be processed
6. Generate maps for all detected dives

## Requirements
- ArcGIS Pro 2.5 or higher
- Python 3.6+
- arcpy module

## Version
1.0.0 (June 2025)

## Author
Mike Bollinger
CSS Inc./NOAA National Center for Coastal Ocean Science (NCCOS)

## License
For internal use only

"""
import os
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import arcpy
import threading
import time
import traceback

class LayoutAutomatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ArcGIS Pro Layout Automator")
        self.root.geometry("800x700")
        self.root.minsize(800, 700)
        
        # Variables
        self.project_path = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.layout_name = tk.StringVar()
        self.dpi = tk.IntVar(value=300)
        self.project = None
        self.dive_pattern = re.compile(r'DIVE(\d+)', re.IGNORECASE)
        self.running_in_arcpro = False
        
        # Store selected layer groups (checkboxes)
        self.layer_group_vars = {}
        
        # Detect if running in ArcPro
        self.detect_arcpro_environment()
        
        # Create GUI
        self.create_gui()
        
        # Try to open current project
        self.initialize_project()
        
        # Add these lines to your __init__ method:
        self.last_progress_time = time.time()
        self.processing_active = False
    
    def detect_arcpro_environment(self):
        """Detect if we're running inside ArcPro"""
        try:
            # Check if we can access the current project without specifying a path
            current_proj = arcpy.mp.ArcGISProject("CURRENT")
            if current_proj and current_proj.filePath:
                self.running_in_arcpro = True
                self.log_message("Detected running inside ArcGIS Pro environment")
                return True
        except:
            pass
        
        self.running_in_arcpro = False
        self.log_message("Running in standalone mode")
        return False
    
    def initialize_project(self):
        """Initialize project based on environment"""
        try:
            if self.running_in_arcpro:
                # Running in ArcPro - use current project
                self.project = arcpy.mp.ArcGISProject("CURRENT")
                self.project_path.set(self.project.filePath)
                self.log_message(f"Using current ArcPro project: {self.project.filePath}")
                
                # Add warning about ArcPro locks
                self.show_arcpro_warning()
                
            else:
                # Standalone mode - try to find a recent project or prompt user
                self.project = None
                self.log_message("Standalone mode - please select or load a project")
            
            if self.project:
                self.populate_layout_dropdown()
                self.populate_layer_groups()
                
        except Exception as e:
            self.log_message(f"Error initializing project: {str(e)}")
            if not self.running_in_arcpro:
                messagebox.showinfo("Note", "No ArcGIS Pro project currently open. Please open or select a project.")
    
    def show_arcpro_warning(self):
        """Show warning about ArcPro usage with tips"""
        warning_msg = """RUNNING IN ARCGIS PRO - IMPORTANT TIPS:

To avoid layer locking issues:
• Close any layout views before running
• Close any map views showing dive layers  
• Minimize ArcPro interaction during processing
• Consider using 'Refresh Project' if script stalls

The script will attempt to handle locks automatically."""
        
        # Show in both messagebox and log
        messagebox.showwarning("ArcPro Mode", warning_msg)
        self.log_message("=== ARCGIS PRO MODE ACTIVATED ===")
        for line in warning_msg.split('\n')[2:]:  # Skip the header
            if line.strip():
                self.log_message(f"  {line.strip()}")
    
    def create_gui(self):
        """Create the GUI elements"""
        # Create a frame that will contain everything
        self.outer_frame = ttk.Frame(self.root)
        self.outer_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create a canvas with scrollbar for the entire interface
        self.main_canvas = tk.Canvas(self.outer_frame, borderwidth=0, highlightthickness=0)
        main_scrollbar = ttk.Scrollbar(self.outer_frame, orient="vertical", command=self.main_canvas.yview)
        
        # Configure the canvas
        self.main_canvas.configure(yscrollcommand=main_scrollbar.set)
        
        # Pack the scrollbar first, then the canvas
        main_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Create the main frame inside the canvas
        main_frame = ttk.Frame(self.main_canvas)
        self.main_frame_window = self.main_canvas.create_window((0, 0), window=main_frame, anchor="nw", tags="main_frame")
        
        # Configure scrolling behavior
        main_frame.bind("<Configure>", lambda e: self._configure_main_frame_scroll(e))
        self.main_canvas.bind("<Configure>", lambda e: self._configure_main_canvas(e))
        
        # Add mousewheel scrolling
        self.root.bind("<MouseWheel>", self._on_mousewheel)  # Windows
        self.root.bind("<Button-4>", self._on_mousewheel)    # Linux up
        self.root.bind("<Button-5>", self._on_mousewheel)    # Linux down
        
        # Project selection
        project_frame = ttk.LabelFrame(main_frame, text="ArcGIS Pro Project", padding="10")
        project_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(project_frame, text="Project Path:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(project_frame, textvariable=self.project_path, width=50).grid(row=0, column=1, sticky=tk.W+tk.E, pady=5)
        ttk.Button(project_frame, text="Browse...", command=self.browse_project).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(project_frame, text="Load Project", command=self.load_project).grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(project_frame, text="Refresh Project", command=self.manual_refresh_project).grid(row=0, column=4, padx=5, pady=5)
        
        # Layout selection
        layout_frame = ttk.LabelFrame(main_frame, text="Layout Selection", padding="10")
        layout_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(layout_frame, text="Layout:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.layout_dropdown = ttk.Combobox(layout_frame, textvariable=self.layout_name, state="readonly", width=40)
        self.layout_dropdown.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # Extent layer group selection with multiple checkboxes - ENHANCED VERSION
        extent_frame = ttk.LabelFrame(main_frame, text="Extent Control", padding="10")
        extent_frame.pack(fill=tk.X, pady=5)

        # Add a checkbox for fixed extent option
        self.use_fixed_extent = tk.BooleanVar(value=False)
        ttk.Checkbutton(extent_frame, text="Use fixed extent (don't zoom to features)", 
                        variable=self.use_fixed_extent).grid(row=0, column=0, sticky=tk.W, pady=5)

        # Add layout element awareness option
        self.avoid_elements = tk.BooleanVar(value=True)
        ttk.Checkbutton(extent_frame, text="Smart extent: avoid legends, scale bars and inset maps", 
                        variable=self.avoid_elements).grid(row=1, column=0, sticky=tk.W, pady=5)

        # Add extent buffer controls
        buffer_frame = ttk.Frame(extent_frame)
        buffer_frame.grid(row=2, column=0, sticky=tk.W, pady=5)

        ttk.Label(buffer_frame, text="Extent buffer (%):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.buffer_percentage = tk.IntVar(value=10)
        ttk.Entry(buffer_frame, textvariable=self.buffer_percentage, width=5).grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5,20))

        ttk.Label(extent_frame, text="Note: Extent will include all visible layers from selected layer groups", 
                  foreground="blue", font=("TkDefaultFont", 8)).grid(row=3, column=0, sticky=tk.W, pady=(5,0))

        # Layer group selection
        self.layer_groups_frame = ttk.LabelFrame(main_frame, text="Layer Groups (Select groups containing dive layers)", padding="10")
        self.layer_groups_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create a canvas with scrollbar for layer groups
        self.canvas = tk.Canvas(self.layer_groups_frame)
        scrollbar = ttk.Scrollbar(self.layer_groups_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Output settings
        output_frame = ttk.LabelFrame(main_frame, text="Output Settings", padding="10")
        output_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(output_frame, text="Output Folder:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(output_frame, textvariable=self.output_folder, width=50).grid(row=0, column=1, sticky=tk.W+tk.E, pady=5)
        ttk.Button(output_frame, text="Browse...", command=self.browse_output_folder).grid(row=0, column=2, padx=5, pady=5)
        
        ttk.Label(output_frame, text="Export DPI:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(output_frame, textvariable=self.dpi, width=10).grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # Action buttons
        button_frame = ttk.Frame(main_frame, padding="10")
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Generate Maps", command=self.start_processing, style="Accent.TButton").pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Analyze Selected Groups", command=self.analyze_selected_groups).pack(side=tk.RIGHT, padx=5)
        
        # Log area with both vertical and horizontal scrollbars
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Create a frame to hold the text and scrollbars
        log_container = ttk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True)

        # Create the text widget with NONE wrap to allow horizontal scrolling
        self.log_text = tk.Text(log_container, height=10, wrap=tk.NONE)

        # Create both scrollbars
        log_v_scrollbar = ttk.Scrollbar(log_container, orient="vertical", command=self.log_text.yview)
        log_h_scrollbar = ttk.Scrollbar(log_container, orient="horizontal", command=self.log_text.xview)

        # Configure the text widget to work with both scrollbars
        self.log_text.configure(
            yscrollcommand=log_v_scrollbar.set,
            xscrollcommand=log_h_scrollbar.set
        )

        # Grid layout for better control
        self.log_text.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        log_v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        log_h_scrollbar.grid(row=1, column=0, sticky=(tk.E, tk.W))

        # Configure the grid to expand properly
        log_container.columnconfigure(0, weight=1)
        log_container.rowconfigure(0, weight=1)
        
        # Status bar - move this outside the canvas to the root
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _configure_main_frame_scroll(self, event):
        """Configure the scroll region when the main frame changes size"""
        self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
    
    def _configure_main_canvas(self, event):
        """Adjust the width of the main frame window when canvas changes size"""
        self.main_canvas.itemconfig(self.main_frame_window, width=event.width)
    
    def _on_mousewheel(self, event):
        """Handle mousewheel scrolling"""
        if event.num == 4 or event.delta > 0:  # Scroll up
            self.main_canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:  # Scroll down
            self.main_canvas.yview_scroll(1, "units")
    
    # 1. Improve the log_message function to ensure updates are visible
    def log_message(self, message):
        """Add a message to the log text area with proper updating"""
        try:
            # Reset the progress timer since we're making progress
            self.last_progress_time = time.time()
            
            timestamp = time.strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}\n"
            
            # Print to console as well for debugging
            print(formatted_message.strip())
            
            # Insert the message at the end of the log
            self.log_text.insert(tk.END, formatted_message)
            
            # Scroll to the end to show the latest message
            self.log_text.see(tk.END)
            
            # Force the GUI to update - this is important for real-time updates
            self.root.update_idletasks()
            
            # For longer operations, occasionally give time to process events
            # This helps keep the GUI responsive during long operations
            if message.startswith("***") or "Starting" in message or "Completed" in message:
                self.root.update()
        except Exception as e:
            # Fallback to print if the GUI update fails
            print(f"[{timestamp}] {message} (Error updating log: {str(e)})")
    
    def browse_project(self):
        """Browse for an ArcGIS Pro project file"""
        file_path = filedialog.askopenfilename(
            title="Select ArcGIS Pro Project",
            filetypes=[("ArcGIS Pro Project", "*.aprx")]
        )
        if file_path:
            self.project_path.set(file_path)
    
    def browse_output_folder(self):
        """Browse for output folder"""
        folder_path = filedialog.askdirectory(title="Select Output Folder")
        if folder_path:
            self.output_folder.set(folder_path)
    
    def load_project(self):
        """Load the selected ArcGIS Pro project"""
        try:
            project_path = self.project_path.get()
            if not project_path:
                messagebox.showerror("Error", "Please select a project file")
                return
            
            self.status_var.set("Loading project...")
            self.root.update_idletasks()
            
            self.project = arcpy.mp.ArcGISProject(project_path)
            self.log_message(f"Loaded project: {project_path}")
            
            # Populate layout dropdown and layer groups
            self.populate_layout_dropdown()
            self.populate_layer_groups()
            
            self.status_var.set("Project loaded successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load project: {str(e)}")
            self.status_var.set("Error loading project")
    
    def populate_layout_dropdown(self):
        """Populate the layout dropdown with available layouts"""
        if not self.project:
            return
        
        layouts = [layout.name for layout in self.project.listLayouts()]
        self.layout_dropdown['values'] = layouts
        
        if layouts:
            self.layout_dropdown.current(0)
            self.log_message(f"Found {len(layouts)} layouts in project")
    
    def populate_layer_groups(self):
        """Populate the layer groups frame with checkboxes"""
        if not self.project:
            return
        
        # Clear existing checkboxes
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        self.layer_group_vars = {}
        
        # Add maps and their layer groups
        row = 0
        maps = self.project.listMaps()
        
        self.log_message(f"Scanning {len(maps)} maps for layer groups...")
        
        for map_obj in maps:
            # Add map heading
            map_label = ttk.Label(self.scrollable_frame, text=f"Map: {map_obj.name}", font=("TkDefaultFont", 10, "bold"))
            map_label.grid(row=row, column=0, sticky=tk.W, pady=(10, 5))
            row += 1
            
            # Get all layers in the map
            all_layers = list(map_obj.listLayers())
            self.log_message(f"Found {len(all_layers)} total layers in map '{map_obj.name}'")
            
            # Find group layers (more robust method)
            group_layers = []
            for layer in all_layers:
                try:
                    # Check if it's a group layer directly
                    if hasattr(layer, 'isGroupLayer') and layer.isGroupLayer:
                        group_layers.append(layer)
                    # Alternative check for group layers
                    elif hasattr(layer, 'dataSource') and layer.dataSource is None and hasattr(layer, 'listLayers'):
                        group_layers.append(layer)
                except Exception as e:
                    self.log_message(f"Error checking layer {layer.name}: {str(e)}")
        
            self.log_message(f"Found {len(group_layers)} group layers in map '{map_obj.name}'")
            
            # Add each group layer to the UI
            for group_layer in group_layers:
                try:
                    # Create a checkbox for this group layer
                    var = tk.BooleanVar()
                    
                    # Add trace to update extent dropdown when checkbox changes
                    var.trace_add("write", lambda *args: self.on_layer_group_selection_changed())
                    
                    group_key = f"{map_obj.name}:{group_layer.name}"
                    self.layer_group_vars[group_key] = var
                    
                    chk = ttk.Checkbutton(self.scrollable_frame, text=group_layer.name, variable=var)
                    chk.grid(row=row, column=0, sticky=tk.W, padx=20)
                    row += 1
                    
                    # Check if this group contains dive layers
                    has_dive_layers = False
                    try:
                        sub_layers = list(group_layer.listLayers())
                        for sublayer in sub_layers:
                            if self.dive_pattern.search(sublayer.name):
                                has_dive_layers = True
                                break
                    except Exception as e:
                        self.log_message(f"Error checking sublayers of {group_layer.name}: {str(e)}")
                    
                    if has_dive_layers:
                        info_label = ttk.Label(self.scrollable_frame, text="(Contains dive layers)", foreground="blue")
                        info_label.grid(row=row-1, column=1, sticky=tk.W)
                except Exception as e:
                    self.log_message(f"Error adding group layer {group_layer.name}: {str(e)}")
        
        if not self.layer_group_vars:
            self.log_message("WARNING: No layer groups were found in the project.")
            empty_label = ttk.Label(self.scrollable_frame, 
                                  text="No layer groups found. Please make sure your ArcGIS Pro project contains group layers.",
                                  foreground="red")
            empty_label.grid(row=row, column=0, sticky=tk.W, pady=10)
        else:
            self.log_message(f"Found {len(self.layer_group_vars)} layer groups across {len(maps)} maps")
            
    def on_layer_group_selection_changed(self):
        """Handle changes in layer group selection"""
        # This method can be used for any future functionality when layer group selection changes
        # For now, it's just a placeholder to prevent the trace callback error
        pass
    
    def analyze_selected_groups(self):
        """Analyze the selected layer groups to find dive numbers"""
        if not self.project:
            messagebox.showerror("Error", "No project loaded")
            return
        
        selected_groups = [key for key, var in self.layer_group_vars.items() if var.get()]
        
        if not selected_groups:
            messagebox.showinfo("Info", "No layer groups selected")
            return
        
        self.log_message("\n--- Layer Group Analysis ---")
        self.log_message(f"Analyzing {len(selected_groups)} selected layer groups")
        
        all_dive_numbers = set()
        
        for group_key in selected_groups:
            map_name, group_name = group_key.split(':', 1)
            
            map_obj = None
            for m in self.project.listMaps():
                if m.name == map_name:
                    map_obj = m
                    break
            
            if not map_obj:
                self.log_message(f"Map not found: {map_name}")
                continue
            
            # Find the group layer
            group_layer = None
            for layer in map_obj.listLayers():
                if layer.name == group_name:
                    group_layer = layer
                    break
            
            if not group_layer:
                self.log_message(f"Group layer not found: {group_name}")
                continue
            
            # Find dive layers in this group
            dive_layers = []
            dive_numbers = set()
            
            for layer in group_layer.listLayers():
                match = self.dive_pattern.search(layer.name)
                if match:
                    dive_number = match.group(1)
                    dive_layers.append(layer.name)
                    dive_numbers.add(dive_number)
            
            all_dive_numbers.update(dive_numbers)
            
            self.log_message(f"\nGroup: {group_name} (in map {map_name})")
            self.log_message(f"Found {len(dive_layers)} dive layers")
            self.log_message(f"Dive numbers: {', '.join(sorted(dive_numbers, key=int))}")
        
        if all_dive_numbers:
            sorted_dives = sorted(all_dive_numbers, key=int)
            self.log_message(f"\nAll dive numbers across selected groups: {', '.join(sorted_dives)}")
            self.log_message(f"Total unique dive numbers: {len(all_dive_numbers)}")
            self.log_message(f"Extent will include ALL visible layers from selected groups for each dive")
        else:
            self.log_message("\nNo dive layers found in the selected groups")
        
    
    def start_processing(self):
        """Enhanced start processing with ArcPro awareness"""
        if not self.project:
            messagebox.showerror("Error", "No project loaded")
            return
        
        if not self.layout_name.get():
            messagebox.showerror("Error", "Please select a layout")
            return
        
        if not self.output_folder.get():
            messagebox.showerror("Error", "Please select an output folder")
            return
        
        selected_groups = [key for key, var in self.layer_group_vars.items() if var.get()]
        
        if not selected_groups:
            messagebox.showerror("Error", "Please select at least one layer group")
            return
        
        # ArcPro-specific checks
        if self.running_in_arcpro:
            if not self.check_for_open_views():
                return
            
            # Additional ArcPro warning
            if not messagebox.askyesno("ArcPro Processing", 
                "Processing will modify layer visibility in your current project.\n\n"
                "This may affect your current ArcPro session.\n"
                "Make sure to save your project first if needed.\n\n"
                "Continue?"):
                return
        
        # Start processing in a background thread
        self.status_var.set("Processing...")
        
        # Set up a watchdog timer to detect if processing hangs
        self.last_progress_time = time.time()
        self.processing_active = True
        
        # Start the watchdog timer
        watchdog_thread = threading.Thread(target=self._monitor_progress)
        watchdog_thread.daemon = True
        watchdog_thread.start()
        
        # Start the actual processing
        processing_thread = threading.Thread(target=self.process_maps_enhanced, args=(selected_groups,))
        processing_thread.daemon = True
        processing_thread.start()

    def _monitor_progress(self):
        """Monitor processing progress and detect hangs"""
        while self.processing_active:
            time.sleep(30)  # Check every 30 seconds
            
            current_time = time.time()
            time_since_progress = current_time - self.last_progress_time
            
            if time_since_progress > 300: # 5 minutes without progress
                self.log_message("WARNING: No progress detected for 5 minutes - processing may be stuck")
                self.log_message("Consider using 'Refresh Project' button if processing appears hung")
                
                # Reset the timer to avoid spam
                self.last_progress_time = current_time

    def process_maps_enhanced(self, selected_groups):
        """Enhanced processing with ArcPro lock handling"""
        try:
            self.log_message("Starting enhanced map processing...")
            
            if self.running_in_arcpro:
                self.log_message("Using ArcPro-aware processing mode")
            
            layout_name = self.layout_name.get()
            output_folder = self.output_folder.get()
            dpi = self.dpi.get()
            
            # Create output folder if it doesn't exist
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)
                self.log_message(f"Created output folder: {output_folder}")
            
            # Find all dive numbers (same as before)
            all_dive_numbers = self.collect_dive_numbers(selected_groups)
            
            if not all_dive_numbers:
                self.log_message("No dive layers found in the selected groups")
                self.status_var.set("No dive layers found")
                return
            
            sorted_dives = sorted(all_dive_numbers, key=int)
            total_dives = len(sorted_dives)
            self.log_message(f"Processing {total_dives} dive maps...")
            
            # Pre-collect all layers to minimize repeated searches
            all_dive_layers = self.pre_collect_dive_layers(selected_groups)
            
            # Process each dive
            for i, dive_number in enumerate(sorted_dives, 1):
                dive_id = f"DIVE{dive_number}"
                self.log_message(f"\n[{i}/{total_dives}] *** Starting {dive_id} ***")
                
                progress_pct = int((i / total_dives) * 100)
                self.status_var.set(f"Processing {dive_id} ({i}/{total_dives}) - {progress_pct}% complete")
                
                try:
                    # Process this dive with enhanced error handling
                    success = self.process_single_dive_enhanced(dive_id, all_dive_layers, layout_name, output_folder, dpi)
                    
                    if success:
                        self.log_message(f"*** Completed {dive_id} successfully ***")
                    else:
                        self.log_message(f"*** {dive_id} completed with issues ***")
                        
                except Exception as e:
                    self.log_message(f"*** Error processing {dive_id}: {str(e)} ***")
                    
                    # In ArcPro mode, try to recover from errors
                    if self.running_in_arcpro:
                        self.log_message("Attempting error recovery...")
                        try:
                            self.refresh_project_connection()
                        except:
                            pass
                
                # Update GUI
                self.root.update()
            
            self.processing_active = False
            self.log_message("\nProcessing complete!")
            self.status_var.set("Processing complete")
            messagebox.showinfo("Success", f"Generated {len(sorted_dives)} maps in {output_folder}")
            
        except Exception as e:
            error_message = f"Error processing maps: {str(e)}"
            self.log_message(error_message)
            self.status_var.set("Error")
            messagebox.showerror("Error", error_message)
            self.processing_active = False

    def collect_dive_numbers(self, selected_groups):
        """Collect all unique dive numbers from selected groups"""
        all_dive_numbers = set()
        
        for group_key in selected_groups:
            map_name, group_name = group_key.split(':', 1)
            
            # Get the map object
            map_obj = None
            for m in self.project.listMaps():
                if m.name == map_name:
                    map_obj = m
                    break
            
            if not map_obj:
                continue
            
            # Find the group layer
            group_layer = None
            for layer in map_obj.listLayers():
                if layer.name == group_name:
                    group_layer = layer
                    break
            
            if not group_layer:
                continue
            
            # Find dive numbers in this group
            for layer in group_layer.listLayers():
                match = self.dive_pattern.search(layer.name)
                if match:
                    dive_number = match.group(1)
                    all_dive_numbers.add(dive_number)
        
        return all_dive_numbers

    def pre_collect_dive_layers(self, selected_groups):
        """Pre-collect all dive layers to minimize repeated searches"""
        all_dive_layers = []
        
        for group_key in selected_groups:
            map_name, group_name = group_key.split(':', 1)
            
            # Get the map object
            map_obj = None
            for m in self.project.listMaps():
                if m.name == map_name:
                    map_obj = m
                    break
            
            if not map_obj:
                continue
            
            # Find the group layer
            group_layer = None
            for layer in map_obj.listLayers():
                if layer.name == group_name:
                    group_layer = layer
                    break
            
            if not group_layer:
                continue
            
            # Collect all layers from this group
            for layer in group_layer.listLayers():
                if self.dive_pattern.search(layer.name):
                    all_dive_layers.append({
                        'layer': layer,
                        'map_obj': map_obj,
                        'group_name': group_name
                    })
        
        return all_dive_layers

    def refresh_project_connection(self):
        """Refresh the project connection to clear locks"""
        try:
            if self.running_in_arcpro:
                self.log_message("Refreshing project connection to clear potential locks...")
                
                # Force garbage collection first
                import gc
                gc.collect()
                
                # Try to refresh the project reference
                old_project_path = self.project.filePath if self.project else None
                
                # Clear the current reference
                self.project = None
                gc.collect()
                
                # Small delay to allow ArcPro to release locks
                time.sleep(0.5)
                
                # Reconnect to current project
                self.project = arcpy.mp.ArcGISProject("CURRENT")
                
                if old_project_path and self.project.filePath == old_project_path:
                    self.log_message("  Project connection refreshed successfully")
                    return True
                else:
                    self.log_message("  Warning: Project path changed during refresh")
                    return False
            
            return True
            
        except Exception as e:
            self.log_message(f"  Error refreshing project connection: {str(e)}")
            return False

    def safe_layer_operation(self, operation_func, *args, max_retries=3, **kwargs):
        """Safely perform layer operations with retry logic"""
        for attempt in range(max_retries):
            try:
                return operation_func(*args, **kwargs)
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check if it's a lock-related error
                if any(lock_indicator in error_msg for lock_indicator in 
                       ['lock', 'locked', 'in use', 'cannot access', 'permission denied']):
                    
                    self.log_message(f"  Lock detected on attempt {attempt + 1}: {str(e)}")
                    
                    if attempt < max_retries - 1:  # Don't refresh on last attempt
                        self.log_message(f"  Attempting to clear locks and retry...")
                        
                        # Try to refresh project connection
                        if not self.refresh_project_connection():
                            self.log_message(f"  Failed to refresh connection, continuing anyway...")
                        
                        # Progressive delay
                        delay = (attempt + 1) * 2
                        self.log_message(f"  Waiting {delay} seconds before retry...")
                        time.sleep(delay)
                    else:
                        self.log_message(f"  All retry attempts failed for lock issue")
                        raise
                else:
                    # Non-lock related error, don't retry
                    raise
        
        # If we get here, all retries failed
        raise Exception(f"Operation failed after {max_retries} attempts")

    def check_for_open_views(self):
        """Check for open views that might cause locks and warn user"""
        try:
            if not self.running_in_arcpro:
                return True
            
            # Check for open layout views
            layouts = list(self.project.listLayouts())
            
            # This is tricky - we can't directly detect if views are open in ArcPro
            # But we can warn the user and provide guidance
            
            self.log_message("Checking for potential view conflicts...")
            
            # Look for the target layout
            target_layout_name = self.layout_name.get()
            if target_layout_name:
                target_layout = None
                for layout in layouts:
                    if layout.name == target_layout_name:
                        target_layout = layout
                        break
                
                if target_layout:
                    self.log_message(f"Target layout '{target_layout_name}' found")
                    
                    # Warn user about potential conflicts
                    if messagebox.askyesno("View Check", 
                        f"About to process layout '{target_layout_name}'.\n\n"
                        "For best results:\n"
                        "• Close any open layout views\n"
                        "• Close any map views showing dive layers\n"
                        "• Minimize other ArcPro interactions\n\n"
                        "Continue with processing?"):
                        return True
                    else:
                        return False
            
            return True
            
        except Exception as e:
            self.log_message(f"Error checking for open views: {str(e)}")
            return True  # Proceed anyway

    def safe_set_layer_visibility(self, layer, visible, dive_id=None):
        """Safely set layer visibility with lock handling"""
        def set_visibility():
            if hasattr(layer, 'visible'):
                layer.visible = visible
                return True
            return False
        
        try:
            # Use the safe operation wrapper
            result = self.safe_layer_operation(set_visibility)
            
            if result:
                status = "visible" if visible else "hidden"
                layer_info = f"{layer.name}"
                if dive_id:
                    layer_info += f" (for {dive_id})"
                # Only log successful visibility changes for important operations
                if visible:  # Only log when making layers visible to reduce noise
                    self.log_message(f"    Set {layer_info} to {status}")
            
            return result
            
        except Exception as e:
            self.log_message(f"    Failed to set visibility for {layer.name}: {str(e)}")
            return False

    def batch_set_layer_visibility(self, layers_and_states, dive_id=None):
        """Set visibility for multiple layers in batch with progress tracking"""
        total_layers = len(layers_and_states)
        successful = 0
        failed = 0
        
        self.log_message(f"Setting visibility for {total_layers} layers...")
        
        for i, (layer, visible) in enumerate(layers_and_states):
            try:
                if self.safe_set_layer_visibility(layer, visible, dive_id):
                    successful += 1
                else:
                    failed += 1
                    
                # Progress update every 50 layers or at the end
                if (i + 1) % 50 == 0 or (i + 1) == total_layers:
                    self.log_message(f"  Progress: {i + 1}/{total_layers} layers processed")
                    
                    # Force a brief pause every 100 layers to allow ArcPro to catch up
                    if (i + 1) % 100 == 0:
                        time.sleep(0.1)
                        
            except Exception as e:
                failed += 1
                self.log_message(f"  Error with layer {layer.name}: {str(e)}")
        
        self.log_message(f"  Visibility update complete: {successful} successful, {failed} failed")
        return successful, failed

    def zoom_to_active_layers(self, layout, active_map_obj, dive_id):
        """Zoom to the extent of active layers with improved scaling and positioning"""
        # Check if we should use fixed extent
        if self.use_fixed_extent.get():
            self.log_message("  Using fixed extent (not zooming to features)")
            return
        
        # Find the map frame in the layout that uses this map
        map_frame = None
        for mf in layout.listElements("MAPFRAME_ELEMENT"):
            if mf.map.name == active_map_obj.name:
                map_frame = mf
                break
        
        if not map_frame:
            self.log_message(f"  Map frame for {active_map_obj.name} not found in layout")
            return
        
        # Get ALL visible layers from ALL selected layer groups for this dive
        selected_groups = [key for key, var in self.layer_group_vars.items() if var.get()]
        
        if not selected_groups:
            self.log_message("  No layer groups selected")
            return
        
        self.log_message(f"  Getting extent from all visible layers in {len(selected_groups)} selected groups")
        visible_layers = []
        
        # Collect layers from each selected group
        for group_key in selected_groups:
            map_name, group_name = group_key.split(':', 1)
            
            # Get the map object
            map_obj = None
            for m in self.project.listMaps():
                if m.name == map_name:
                    map_obj = m
                    break
            
            if not map_obj:
                continue
            
            # Find the group layer
            group_layer = None
            for layer in map_obj.listLayers():
                if layer.name == group_name:
                    group_layer = layer
                    break
            
            if not group_layer:
                self.log_message(f"Group layer not found: {group_name}")
                continue
            
            # Get ALL visible layers for this dive from this group
            group_layers = []
            for layer in group_layer.listLayers():
                if hasattr(layer, 'visible') and layer.visible and dive_id.upper() in layer.name.upper():
                    try:
                        layer_extent = arcpy.Describe(layer).extent
                        
                        if (layer_extent and 
                            hasattr(layer_extent, 'XMin') and 
                            hasattr(layer_extent, 'XMax') and
                            hasattr(layer_extent, 'YMin') and 
                            hasattr(layer_extent, 'YMax') and
                            layer_extent.XMax > layer_extent.XMin and 
                            layer_extent.YMax > layer_extent.YMin):
                
                            group_layers.append(layer)
                            self.log_message(f"    Including {layer.name} from {group_name}")
                        else:
                            self.log_message(f"    Skipping {layer.name} (invalid extent dimensions)")
                        
                    except Exception as e:
                        self.log_message(f"    Skipping {layer.name} (extent error): {str(e)}")
        
        visible_layers.extend(group_layers)
        self.log_message(f"    {group_name}: {len(group_layers)} layers with valid extents")

        if not visible_layers:
            self.log_message(f"  No visible layers with valid extents found for {dive_id}")
            return
        
        # Calculate combined extent from ALL visible layers
        self.log_message(f"  Calculating combined extent from {len(visible_layers)} layers")
        extent = None
        for layer in visible_layers:
            try:
                layer_extent = arcpy.Describe(layer).extent
                
                if (layer_extent and 
                    hasattr(layer_extent, 'XMin') and 
                    layer_extent.XMax > layer_extent.XMin and 
                    layer_extent.YMax > layer_extent.YMin):
                    
                    if extent is None:
                        extent = layer_extent
                        self.log_message(f"    Base extent from: {layer.name}")
                    else:
                        # Expand the extent to include this layer
                        new_xmin = min(extent.XMin, layer_extent.XMin)
                        new_ymin = min(extent.YMin, layer_extent.YMin)
                        new_xmax = max(extent.XMax, layer_extent.XMax)
                        new_ymax = max(extent.YMax, layer_extent.YMax)
                        
                        extent = arcpy.Extent(new_xmin, new_ymin, new_xmax, new_ymax)
                
            except Exception as e:
                self.log_message(f"  Error getting extent for {layer.name}: {str(e)}")
        
        if not extent or extent.width <= 0 or extent.height <= 0:
            self.log_message(f"  Could not calculate valid extent for {dive_id}")
            return
        
        # Add minimum extent size to prevent tiny extents
        min_extent_size = 0.01  # Minimum size in map units
        if extent.width < min_extent_size:
            center_x = (extent.XMin + extent.XMax) / 2
            extent = arcpy.Extent(
                center_x - min_extent_size/2,
                extent.YMin,
                center_x + min_extent_size/2,
                extent.YMax
            )
            self.log_message(f"  Adjusted width to minimum size: {min_extent_size}")

        if extent.height < min_extent_size:
            center_y = (extent.YMin + extent.YMax) / 2
            extent = arcpy.Extent(
                extent.XMin,
                center_y - min_extent_size/2,
                extent.XMax,
                center_y + min_extent_size/2
            )
            self.log_message(f"  Adjusted height to minimum size: {min_extent_size}")
        
        # Get map frame boundaries for element analysis
        map_x = 0
        map_y = 0
        map_width = 100
        map_height = 100
        
        try:
            map_x = map_frame.elementPositionX
            map_y = map_frame.elementPositionY
            map_width = map_frame.elementWidth
            map_height = map_frame.elementHeight
            self.log_message(f"  Main map frame: {map_width:.1f} x {map_height:.1f} at ({map_x:.1f}, {map_y:.1f})")
        except Exception as e:
            self.log_message(f"  Warning: Could not get map frame dimensions: {str(e)}")
        
        # CRITICAL FIX: Apply buffer to create buffered_extent BEFORE element analysis
        base_buffer_pct = self.buffer_percentage.get() / 100.0
        
        # Create initial buffered extent with buffer percentage
        buffer_x = extent.width * base_buffer_pct
        buffer_y = extent.height * base_buffer_pct
        
        # Create the buffered extent - THIS WAS MISSING BEFORE
        buffered_extent = arcpy.Extent(
            extent.XMin - buffer_x,
            extent.YMin - buffer_y,
            extent.XMax + buffer_x,
            extent.YMax + buffer_y
        )
        
        self.log_message(f"  Initial extent: {extent.width:.1f} x {extent.height:.1f} units")
        self.log_message(f"  Applied {base_buffer_pct*100:.0f}% buffer: {buffer_x:.1f} x {buffer_y:.1f} units")
        
        # Apply smart element avoidance if enabled
        if self.avoid_elements.get():
            try:
                self.log_message("  Analyzing layout elements - focusing on Legend, Inset Map, and Rectangle only")
        
                # Get ONLY the critical elements we want to avoid
                legend_elements = list(layout.listElements("LEGEND_ELEMENT"))
                inset_mapframes = [mf for mf in layout.listElements("MAPFRAME_ELEMENT") if mf != map_frame]
        
                # Find the Rectangle element by name or type
                rectangle_element = []
                for element in layout.listElements("GRAPHIC_ELEMENT"):
                    if element.name.lower() == "rectangle" or "rectangle" in element.name.lower():
                        rectangle_element = [element]
                        break
            
                # ONLY focus on these three critical elements
                critical_elements = []
                critical_elements.extend(legend_elements)
                critical_elements.extend(inset_mapframes)
                critical_elements.extend(rectangle_element)
        
                self.log_message(f"  Found {len(critical_elements)} critical elements to avoid")
        
                # Track element positions
                legend_pos = None
                inset_pos = None
                rectangle_pos = None
        
                # Analyze elements for positioning
                for element in critical_elements:
                    try:
                        if hasattr(element, 'elementPositionX') and hasattr(element, 'elementPositionY'):
                            elem_x = element.elementPositionX
                            elem_y = element.elementPositionY
                            elem_width = element.elementWidth
                            elem_height = element.elementHeight
                            elem_center_x = elem_x + elem_width/2
                            elem_center_y = elem_y + elem_height/2
                            elem_type = type(element).__name__
                    
                            # Store positions of key elements
                            if "LegendElement" in elem_type:
                                legend_pos = (elem_center_x, elem_center_y)
                                self.log_message(f"    LEGEND at ({elem_center_x:.1f}, {elem_center_y:.1f})")
                            elif "MapFrame" in elem_type and element != map_frame:
                                inset_pos = (elem_center_x, elem_center_y)
                                self.log_message(f"    INSET MAP at ({elem_center_x:.1f}, {elem_center_y:.1f})")
                            elif "GraphicElement" in elem_type and "rectangle" in element.name.lower():
                                rectangle_pos = (elem_center_x, elem_center_y)
                                self.log_message(f"    RECTANGLE at ({elem_center_x:.1f}, {elem_center_y:.1f})")
                    except Exception as e:
                        self.log_message(f"  Error analyzing element: {str(e)}")
        
                # Calculate the optimal position away from all critical elements
                map_center_x = map_x + map_width / 2
                map_center_y = map_y + map_height / 2
        
                # Analyze map quadrants manually based on critical element positions
                quad_weights = {'top_left': 0, 'top_right': 0, 'bottom_left': 0, 'bottom_right': 0}
        
                # Add weighting to quadrants based on where critical elements are located
                if legend_pos:
                    lx, ly = legend_pos
                    if lx < map_center_x and ly > map_center_y:
                        quad_weights['top_left'] += 10  # Top-left quadrant
                    elif lx > map_center_x and ly > map_center_y:
                        quad_weights['top_right'] += 10  # Top-right quadrant
                    elif lx < map_center_x and ly < map_center_y:
                        quad_weights['bottom_left'] += 10  # Bottom-left quadrant
                    elif lx > map_center_x and ly < map_center_y:
                        quad_weights['bottom_right'] += 10  # Bottom-right quadrant

                if inset_pos:
                    ix, iy = inset_pos
                    if ix < map_center_x and iy > map_center_y:
                        quad_weights['top_left'] += 8  # Top-left quadrant
                    elif ix > map_center_x and iy > map_center_y:
                        quad_weights['top_right'] += 8  # Top-right quadrant
                    elif ix < map_center_x and iy < map_center_y:
                        quad_weights['bottom_left'] += 8  # Bottom-left quadrant
                    elif ix > map_center_x and iy < map_center_y:
                        quad_weights['bottom_right'] += 8  # Bottom-right quadrant

                if rectangle_pos:
                    rx, ry = rectangle_pos
                    if rx < map_center_x and ry > map_center_y:
                        quad_weights['top_left'] += 5  # Top-left quadrant
                    elif rx > map_center_x and ry > map_center_y:
                        quad_weights['top_right'] += 5  # Top-right quadrant
                    elif rx < map_center_x and ry < map_center_y:
                        quad_weights['bottom_left'] += 5  # Bottom-left quadrant
                    elif rx > map_center_x and ry < map_center_y:
                        quad_weights['bottom_right'] += 5  # Bottom-right quadrant
        
                # Log the calculated weights
                self.log_message(f"  Critical element avoid weights: {quad_weights}")
        
                # Find the quadrant with minimum conflict weight
                min_quad = min(quad_weights.items(), key=lambda x: x[1])[0]
                self.log_message(f"  Best placement quadrant: {min_quad}")
        
                # IMPROVED: Apply a more conservative shift to avoid over-correction
                shift_multiplier = 0.4  # More conservative than 0.8
                horizontal_shift = 0
                vertical_shift = 0
        
                # CRITICAL FIX: CORRECT SHIFT DIRECTIONS FOR ALL QUADRANTS
                if min_quad == "top_left":
                    horizontal_shift = shift_multiplier  # Move RIGHT to shift content LEFT
                    vertical_shift = -shift_multiplier   # CORRECT: Move UP to shift content DOWN
                    self.log_message(f"  SMART SHIFT: Moving map UP and RIGHT to position content in {min_quad}")
                elif min_quad == "top_right":
                    horizontal_shift = -shift_multiplier  # Move LEFT to shift content RIGHT
                    vertical_shift = -shift_multiplier    # CORRECT: Move UP to shift content DOWN  
                    self.log_message(f"  SMART SHIFT: Moving map UP and LEFT to position content in {min_quad}")
                elif min_quad == "bottom_left":
                    horizontal_shift = shift_multiplier   # Move RIGHT to shift content LEFT
                    vertical_shift = shift_multiplier     # CORRECT: Move DOWN to shift content UP
                    self.log_message(f"  SMART SHIFT: Moving map DOWN and RIGHT to position content in {min_quad}")
                elif min_quad == "bottom_right":
                    horizontal_shift = -shift_multiplier  # Move LEFT to shift content RIGHT
                    vertical_shift = shift_multiplier     # CORRECT: Move DOWN to shift content UP
                    self.log_message(f"  SMART SHIFT: Moving map DOWN and LEFT to position content in {min_quad}")
        
                # Apply the shifts with guaranteed non-zero effect
                current_width = max(buffered_extent.width, 0.1)  # Ensure non-zero width
                current_height = max(buffered_extent.height, 0.1)  # Ensure non-zero height
        
                current_center_x = (buffered_extent.XMin + buffered_extent.XMax) / 2
                current_center_y = (buffered_extent.YMin + buffered_extent.YMax) / 2
        
                # Calculate more conservative shifts
                max_dimension = max(current_width, current_height)
                shift_x = max_dimension * horizontal_shift * 0.08  # Much more conservative
                shift_y = max_dimension * vertical_shift * 0.08    # Much more conservative
        
                new_center_x = current_center_x + shift_x
                new_center_y = current_center_y + shift_y
        
                self.log_message(f"  Shifting extent center from ({current_center_x:.4f}, {current_center_y:.4f}) to ({new_center_x:.4f}, {new_center_y:.4f})")
                self.log_message(f"  Absolute shift: X={shift_x:.4f}, Y={shift_y:.4f} map units")
        
                # Create the shifted extent
                current_width = buffered_extent.XMax - buffered_extent.XMin
                current_height = buffered_extent.YMax - buffered_extent.YMin
        
                buffered_extent = arcpy.Extent(
                    new_center_x - current_width / 2,
                    new_center_y - current_height / 2,
                    new_center_x + current_width / 2,
                    new_center_y + current_height / 2
                )
        
                self.log_message(f"  Final adjusted extent: {buffered_extent.XMin:.3f}, {buffered_extent.YMin:.3f}, {buffered_extent.XMax:.3f}, {buffered_extent.YMax:.3f}")

            except Exception as e:
                self.log_message(f"  Error during element analysis: {str(e)}")
        
        # Set the final extent
        try:
            map_frame.camera.setExtent(buffered_extent)
            
            # Automatically adjust scale bar units based on new scale
            self.adjust_scale_bar_units(layout, map_frame, dive_id)
            
            self.log_message(f"  Successfully set optimized extent for {dive_id} using {len(visible_layers)} layers")
        except Exception as e:
            self.log_message(f"  Error setting extent: {str(e)}")
            # Try fallback method
            try:
                self.log_message("  Attempting fallback zoom to extent")
                map_frame.camera = buffered_extent;
                
                # Also try scale bar adjustment in fallback
                self.adjust_scale_bar_units(layout, map_frame, dive_id)
                
                self.log_message("  Fallback zoom successful")
            except Exception as alt_e:
                self.log_message(f"  Fallback zoom also failed: {str(alt_e)}")
    
    def manual_refresh_project(self):
        """Manual project refresh for when things get stuck"""
        self.log_message("Manual project refresh requested...")
        
        if self.refresh_project_connection():
            # Repopulate the interface
            self.populate_layout_dropdown()
            self.populate_layer_groups()
            self.log_message("Project refreshed successfully")
            messagebox.showinfo("Success", "Project connection refreshed")
        else:
            messagebox.showerror("Error", "Failed to refresh project connection")

    def process_single_dive_enhanced(self, dive_id, all_dive_layers, layout_name, output_folder, dpi):
        """Process a single dive with enhanced error handling"""
        try:
            # Prepare layer visibility changes
            layers_to_hide = []
            layers_to_show = []
            active_map_obj = None
            
            for layer_info in all_dive_layers:
                layer = layer_info['layer']
                if self.dive_pattern.search(layer.name):
                    if dive_id.upper() in layer.name.upper():
                        layers_to_show.append((layer, True))
                        active_map_obj = layer_info['map_obj']
                    else:
                        layers_to_hide.append((layer, False))
            
            # Apply visibility changes in batches
            if layers_to_hide:
                self.batch_set_layer_visibility(layers_to_hide, dive_id)
            
            if layers_to_show:
                self.batch_set_layer_visibility(layers_to_show, dive_id)
            
            if not layers_to_show:
                self.log_message(f"  No layers found for {dive_id}")
                return False
            
            # Access layout with retry logic
            layout = self.safe_get_layout(layout_name)
            
            if not layout:
                self.log_message(f"  Could not access layout for {dive_id}")
                return False
            
            # Zoom to extent
            if active_map_obj:
                try:
                    self.zoom_to_active_layers(layout, active_map_obj, dive_id)
                except Exception as e:
                    self.log_message(f"  Error zooming: {str(e)}")
            
            # Export with retry
            output_file = os.path.join(output_folder, f"{dive_id}.jpg")
            return self.safe_export_layout(layout, output_file, dpi, dive_id)
            
        except Exception as e:
            self.log_message(f"  Error in single dive processing: {str(e)}")
            return False

    def safe_get_layout(self, layout_name, max_retries=3):
        """Safely get layout with retry logic"""
        def get_layout():
            layouts = list(self.project.listLayouts(layout_name))
            if layouts:
                return layouts[0]
            return None
        
        return self.safe_layer_operation(get_layout, max_retries=max_retries)

    def safe_export_layout(self, layout, output_file, dpi, dive_id, max_retries=2):
        """Safely export layout with retry logic"""
        def export_layout():
            layout.exportToJPEG(output_file, resolution=dpi)
            return True
        
        try:
            result = self.safe_layer_operation(export_layout, max_retries=max_retries)
            if result:
                self.log_message(f"  Successfully exported {dive_id}")
            return result
        except Exception as e:
            self.log_message(f"  Export failed for {dive_id}: {str(e)}")
            return False

    def _calculate_intersection_area(self, x1_min, y1_min, x1_max, y1_max, x2_min, y2_min, x2_max, y2_max):
        """Calculate the intersection area between two rectangles"""
        # Calculate intersection bounds
        intersection_x_min = max(x1_min, x2_min)
        intersection_y_min = max(y1_min, y2_min)
        intersection_x_max = min(x1_max, x2_max)
        intersection_y_max = min(y1_max, y2_max)
        
        # Check if there's actually an intersection
        if intersection_x_min >= intersection_x_max or intersection_y_min >= intersection_y_max:
            return 0
        
        # Calculate area
        width = intersection_x_max - intersection_x_min
        height = intersection_y_max - intersection_y_min
        return width * height

    # Enhanced scale bar approach with additional settings
    def adjust_scale_bar_units(self, layout, map_frame, dive_id):
        """Update ONLY the scale bar unit labels - let ArcGIS handle the scale"""
        try:
            # Get the current map scale
            current_scale = map_frame.camera.scale
            self.log_message(f"  Current map scale: 1:{current_scale:,.0f}")
            
            # Determine appropriate units based on scale
            scale_threshold = 90000
            use_kilometers = current_scale > scale_threshold
            target_label = "Kilometers" if use_kilometers else "Meters"
            
            self.log_message(f"  Scale threshold check: {current_scale:,.0f} {'>' if use_kilometers else '<='} {scale_threshold:,}")
            self.log_message(f"  Target scale bar label: {target_label}")
            
            # Find scale bar elements
            scale_bars = []
            for element in layout.listElements("MAPSURROUND_ELEMENT"):
                if hasattr(element, 'name') and ("scale" in element.name.lower() or "bar" in element.name.lower()):
                    scale_bars.append(element)
                    self.log_message(f"    Found scale bar: {element.name}")
            
            if not scale_bars:
                self.log_message("    No scale bar elements found")
                return False
            
            success_count = 0
            
            # CIM APPROACH: Only change the unit label
            try:
                layout_cim = layout.getDefinition("V3")
                
                # Use the appropriate UWKID for units
                import json
                unit_wkid = 9093 if use_kilometers else 9036  # 9036=Meters, 9093=Kilometers
                scalebar_unit = json.loads(f'{{"uwkid":{unit_wkid}}}')
                
                for scale_bar in scale_bars:
                    scale_bar_name = scale_bar.name
                    for elm in layout_cim.elements:
                        if hasattr(elm, 'name') and elm.name == scale_bar_name:
                            try:
                                # ONLY change the unit label and units - let ArcGIS handle the scale
                                elm.unitLabel = target_label
                                elm.units = scalebar_unit
                                
                                # DON'T change divisions, number format, or other scale properties
                                # Let ArcGIS auto-calculate the appropriate scale
                                
                                success_count += 1
                                self.log_message(f"      Updated scale bar label: {scale_bar_name}")
                                break
                            except Exception as e:
                                self.log_message(f"      Error updating scale bar {scale_bar_name}: {str(e)}")
        
                # Apply the CIM changes
                if success_count > 0:
                    layout.setDefinition(layout_cim)
                    self.log_message(f"    Successfully updated {success_count} scale bar labels")
                    return True
                    
            except Exception as e:
                self.log_message(f"    CIM approach failed: {str(e)}")
    
            # Fallback: Only change unit label - THIS NEEDS TO BE INSIDE THE MAIN TRY BLOCK
            if success_count == 0:
                self.log_message(f"    Attempting direct label update only")
                
                for scale_bar in scale_bars:
                    try:
                        if hasattr(scale_bar, 'mapSurround'):
                            ms = scale_bar.mapSurround
                            
                            # ONLY change the unit label - don't touch other properties
                            if hasattr(ms, 'unitLabel'):
                                ms.unitLabel = target_label
                                success_count += 1
                                self.log_message(f"      Updated {scale_bar.name} label only")
                    except Exception as e:
                        self.log_message(f"      Error in direct label update: {str(e)}")
        
            # Final success check - ALSO INSIDE THE MAIN TRY BLOCK
            if success_count > 0:
                self.log_message(f"    Successfully updated {success_count} scale bar labels")
                return True
            else:
                self.log_message("    Could not update scale bar labels")
                return False
                
        except Exception as e:
            self.log_message(f"  Error in scale bar label adjustment: {str(e)}")
            return False


def run_app():
    """Run the main application"""
    
    # Check for required libraries
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
        import arcpy
    except ImportError as e:
        print(f"Error: Missing required library - {str(e)}")
        print("Please ensure ArcGIS Pro Python environment is activated")
        return
    
    # Create and run the main window
    root = tk.Tk()
    app = LayoutAutomatorApp(root)
    root.mainloop()

if __name__ == "__main__":
    run_app()