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
        
        # Store selected layer groups (checkboxes)
        self.layer_group_vars = {}
        
        # Create GUI
        self.create_gui()
        
        # Try to open current project
        try:
            self.project = arcpy.mp.ArcGISProject("CURRENT")
            self.project_path.set(self.project.filePath)
            self.populate_layout_dropdown()
            self.populate_layer_groups()
        except:
            messagebox.showinfo("Note", "No ArcGIS Pro project currently open. Please open or select a project.")
    
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
        """Start the processing in a background thread with timeout monitoring"""
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
        processing_thread = threading.Thread(target=self.process_maps, args=(selected_groups,))
        processing_thread.daemon = True
        processing_thread.start()
    
    def _monitor_progress(self):
        """Monitor progress and detect if processing hangs"""
        warning_count = 0
        while self.processing_active:
            time.sleep(60)  # Check every minute instead of 30 seconds
            
            # If more than 10 minutes have passed without a log update, show a warning
            if time.time() - self.last_progress_time > 600:  # 10 minutes
                warning_count += 1
                self.log_message(f"WARNING: Processing appears to be slow or stuck... ({warning_count})")
                
                # Force an update to the GUI
                self.root.update()
                
                # After 3 warnings (30 minutes of inactivity), offer to abort
                if warning_count >= 3:
                    try:
                        self.root.after(0, lambda: self._show_abort_dialog())
                        # Reset counter after showing dialog
                        warning_count = 0
                    except:
                        pass
            
            # Reset the timer to avoid repeated warnings
            self.last_progress_time = time.time()
    
    def _show_abort_dialog(self):
        """Show a dialog asking if user wants to abort processing"""
        if messagebox.askyesno("Processing Stuck", 
                          "Processing appears to be stuck for several minutes. Would you like to abort?"):
            self.log_message("User requested abort of processing")
            self.processing_active = False
            self.status_var.set("Aborted by user")
    
    # 2. Add progress checkpoints in the process_maps method
    def process_maps(self, selected_groups):
        """Process the maps for each dive number with a workaround for layout access"""
        try:
            self.log_message("Starting process_maps function...")
            
            layout_name = self.layout_name.get()
            output_folder = self.output_folder.get()
            dpi = self.dpi.get()
            
            self.log_message(f"Parameters: Layout={layout_name}, Output={output_folder}, DPI={dpi}")
            
            # Create output folder if it doesn't exist
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)
                self.log_message(f"Created output folder: {output_folder}")
            
            # WORKAROUND: Skip direct layout lookup until needed
            self.log_message(f"Will use layout: {layout_name} (deferring actual layout access)")
            
            # Find all dive numbers across all selected groups
            self.log_message(f"Scanning {len(selected_groups)} layer groups to find all dive numbers...")
            all_dive_numbers = set()
            layer_count = 0
            
            # Process each group to find dive numbers
            for i, group_key in enumerate(selected_groups):
                self.log_message(f"Scanning group {i+1}/{len(selected_groups)}: {group_key}")
                map_name, group_name = group_key.split(':', 1)
                
                # Direct lookup for maps
                map_obj = None
                for m in self.project.listMaps():
                    if m.name == map_name:
                        map_obj = m
                        break
                
                if not map_obj:
                    self.log_message(f"  Map not found: {map_name}")
                    continue
                
                # Find the group layer
                group_layer = None
                for layer in map_obj.listLayers():
                    if layer.name == group_name:
                        group_layer = layer
                        break
                
                if not group_layer:
                    self.log_message(f"  Group layer not found: {group_name}")
                    continue
                
                # Find dive numbers in this group
                self.log_message(f"  Scanning layers in group: {group_name}")
                group_dive_numbers = set()
                group_layer_count = 0
                
                # Set a checkpoint for GUI updates
                last_update = time.time()
                
                for layer in group_layer.listLayers():
                    group_layer_count += 1
                    layer_count += 1
                    
                    # Update progress every 50 layers or 2 seconds
                    if group_layer_count % 50 == 0 or time.time() - last_update > 2:
                        self.log_message(f"  Scanned {group_layer_count} layers in current group, {layer_count} total...")
                        last_update = time.time()
                        
                    match = self.dive_pattern.search(layer.name)
                    if match:
                        dive_number = match.group(1)
                        group_dive_numbers.add(dive_number)
                
                self.log_message(f"  Finished scanning {group_layer_count} layers, found {len(group_dive_numbers)} dive numbers")
                all_dive_numbers.update(group_dive_numbers)
            
            if not all_dive_numbers:
                self.log_message("No dive layers found in the selected groups")
                self.status_var.set("No dive layers found")
                return
            
            # Sort dive numbers
            sorted_dives = sorted(all_dive_numbers, key=int)
            self.log_message(f"Found {len(sorted_dives)} total dive numbers: {', '.join(sorted_dives)}")
            self.log_message("Starting map generation process...")
            
            # Process each dive number
            total_dives = len(sorted_dives)
            self.log_message(f"Starting processing of {total_dives} dive maps...")
            
            for i, dive_number in enumerate(sorted_dives, 1):
                dive_id = f"DIVE{dive_number}"
                self.log_message(f"\n[{i}/{total_dives}] *** Starting {dive_id} ***")
                
                # Update the status bar with more detailed info
                progress_pct = int((i / total_dives) * 100)
                self.status_var.set(f"Processing {dive_id} ({i}/{total_dives}) - {progress_pct}% complete")
                
                # Force a GUI update
                self.root.update_idletasks()
                
                # Turn off all dive layers first
                self.log_message(f"Turning off all dive layers...")
                for group_key in selected_groups:
                    map_name, group_name = group_key.split(':', 1)
                    
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
                    
                    # Turn off all dive layers in this group
                    for layer in group_layer.listLayers():
                        if hasattr(layer, 'visible') and self.dive_pattern.search(layer.name):
                            layer.visible = False
                
                # Now turn on only the layers for this dive number
                self.log_message(f"Activating layers for {dive_id}...")
                active_layers = []
                active_map_obj = None  # Keep track of which map has the active layers
                
                for group_key in selected_groups:
                    map_name, group_name = group_key.split(':', 1)
                    
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
                    
                    # Turn on only the layers for this dive
                    for layer in group_layer.listLayers():
                        if hasattr(layer, 'visible') and dive_id.upper() in layer.name.upper():
                            layer.visible = True
                            active_layers.append(f"{layer.name} (in {group_name})")
                            active_map_obj = map_obj  # Track the map with active layers
                
                if not active_layers:
                    self.log_message(f"  No layers found for {dive_id}, skipping to next dive")
                    continue
                
                self.log_message(f"  Activated {len(active_layers)} layers for {dive_id}:")
                for layer_name in active_layers:
                    self.log_message(f"    - {layer_name}")
                
                # WORKAROUND: Access the layout right before we need to use it
                # This avoids keeping a reference to the layout object for extended periods
                self.log_message(f"Accessing layout {layout_name} for current dive...")
                layout = None
                
                try:
                    # Try to get the layout by name
                    layout = self.project.listLayouts(layout_name)[0]
                    self.log_message(f"Successfully accessed layout: {layout_name}")
                except Exception as e:
                    self.log_message(f"Error accessing layout: {str(e)}")
                    self.log_message("Attempting to access layout through alternative method...")
                    
                    # Fallback: Try to get layout by index if available
                    try:
                        layouts = list(self.project.listLayouts())
                        for l in layouts:
                            if l.name == layout_name:
                                layout = l
                                self.log_message(f"Found layout through manual search")
                                break
                    except Exception as alt_error:
                        self.log_message(f"Alternative layout access also failed: {str(alt_error)}")
                
                if not layout:
                    self.log_message(f"Could not access layout '{layout_name}' for export, skipping dive {dive_id}")
                    continue
                
                # Zoom to the dive layers extent
                self.log_message(f"Zooming to extent of {dive_id} layers...")
                try:
                    if active_map_obj:
                        self.zoom_to_active_layers(layout, active_map_obj, dive_id)
                    else:
                        self.log_message("No active map object found for zooming")
                except Exception as e:
                    self.log_message(f"  Error zooming to layers: {str(e)}")
                
                # Export the layout
                output_file = os.path.join(output_folder, f"{dive_id}.jpg")
                self.log_message(f"Exporting {dive_id} to JPEG...")
                try:
                    layout.exportToJPEG(output_file, resolution=dpi)
                    self.log_message(f"  Successfully exported {dive_id} to {output_file}")
                    
                    # Release the layout reference immediately after use
                    layout = None
                    
                    # Force garbage collection to free memory
                    import gc
                    gc.collect()
                    
                except Exception as e:
                    self.log_message(f"  Error exporting map: {str(e)}")
                
                # Update at the end of each dive processing
                self.log_message(f"*** Completed {dive_id} ({i}/{total_dives}) ***")
                self.root.update()  # Full update to process any pending events
            
            self.processing_active = False  # Stop the watchdog
            self.log_message("\nProcessing complete!")
            self.status_var.set("Processing complete")
            messagebox.showinfo("Success", f"Generated {len(sorted_dives)} maps in {output_folder}")
        
        except Exception as e:
            error_message = f"Error processing maps: {str(e)}"
            self.log_message(error_message)
            self.status_var.set("Error")
            messagebox.showerror("Error", error_message)
    
    def zoom_to_active_layers(self, layout, active_map_obj, dive_id):
        """Zoom to the extent of active layers with smart element avoidance"""
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
        
        # Collect all visible dive layers from all selected groups
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
            
            # Get ALL visible layers for this dive from this group
            group_layers = []
            for layer in group_layer.listLayers():
                if hasattr(layer, 'visible') and layer.visible and dive_id.upper() in layer.name.upper():
                    # Include any layer type that has a valid extent
                    try:
                        # FIXED: Proper extent validation
                        layer_extent = arcpy.Describe(layer).extent
                        
                        # Check if extent is valid by examining its dimensions
                        if (layer_extent and 
                            hasattr(layer_extent, 'XMin') and 
                            hasattr(layer_extent, 'XMax') and
                            hasattr(layer_extent, 'YMin') and 
                            hasattr(layer_extent, 'YMax') and
                            layer_extent.XMax > layer_extent.XMin and 
                            layer_extent.YMax > layer_extent.YMin):
                        
                            group_layers.append(layer)
                            self.log_message(f"    Including {layer.name} from {group_name}")
                            self.log_message(f"      Extent: ({layer_extent.XMin:.0f}, {layer_extent.YMin:.0f}) to ({layer_extent.XMax:.0f}, {layer_extent.YMax:.0f})")
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
                
                # FIXED: Proper extent validation and combination
                if (layer_extent and 
                    hasattr(layer_extent, 'XMin') and 
                    layer_extent.XMax > layer_extent.XMin and 
                    layer_extent.YMax > layer_extent.YMin):
                    
                    if extent is None:
                        extent = layer_extent
                        self.log_message(f"    Base extent from: {layer.name}")
                        self.log_message(f"      Extent: ({extent.XMin:.0f}, {extent.YMin:.0f}) to ({extent.XMax:.0f}, {extent.YMax:.0f})")
                    else:
                        # Expand the extent to include this layer
                        original_area = extent.width * extent.height
                        
                        # FIXED: Proper extent union
                        new_xmin = min(extent.XMin, layer_extent.XMin)
                        new_ymin = min(extent.YMin, layer_extent.YMin)
                        new_xmax = max(extent.XMax, layer_extent.XMax)
                        new_ymax = max(extent.YMax, layer_extent.YMax)
                        
                        extent = arcpy.Extent(new_xmin, new_ymin, new_xmax, new_ymax)
                        
                        new_area = extent.width * extent.height
                        if new_area > original_area * 1.1:  # Only log if significant expansion
                            self.log_message(f"    Expanded extent for: {layer.name}")
                            self.log_message(f"      New extent: ({extent.XMin:.0f}, {extent.YMin:.0f}) to ({extent.XMax:.0f}, {extent.YMax:.0f})")
                            
            except Exception as e:
                self.log_message(f"  Error getting extent for {layer.name}: {str(e)}")
        
        # FIXED: Better extent validation
        if not extent or extent.width <= 0 or extent.height <= 0:
            self.log_message(f"  Could not calculate valid extent for {dive_id}")
            return
        
        # Apply buffer percentage
        buffer_pct = self.buffer_percentage.get() / 100.0
        buffer_x = extent.width * buffer_pct
        buffer_y = extent.height * buffer_pct
        
        # Create initial buffered extent
        buffered_extent = arcpy.Extent(
            extent.XMin - buffer_x,
            extent.YMin - buffer_y,
            extent.XMax + buffer_x,
            extent.YMax + buffer_y
        )
        
        self.log_message(f"  Initial extent: {extent.width:.0f} x {extent.height:.0f} units")
        self.log_message(f"  Buffered extent: {buffered_extent.width:.0f} x {buffered_extent.height:.0f} units (+{buffer_pct*100:.0f}%)")
        
        # Apply smart element avoidance if enabled
        if self.avoid_elements.get():
            try:
                self.log_message("  Applying smart element avoidance...")
                
                # Get elements by type
                text_elements = list(layout.listElements("TEXT_ELEMENT"))
                graphic_elements = list(layout.listElements("GRAPHIC_ELEMENT"))
                legend_elements = list(layout.listElements("LEGEND_ELEMENT"))
                mapsurround_elements = list(layout.listElements("MAPSURROUND_ELEMENT"))
                mapframe_elements = [mf for mf in layout.listElements("MAPFRAME_ELEMENT") if mf != map_frame]
                picture_elements = list(layout.listElements("PICTURE_ELEMENT"))
                
                # Set initial centered extent
                try:
                    map_frame.camera.setExtent(buffered_extent)
                    self.log_message("  Set initial centered extent")
                except Exception as e:
                    self.log_message(f"  Warning: Initial extent setting failed: {str(e)}")
                    # Try fallback method
                    try:
                        map_frame.camera = buffered_extent
                        self.log_message("  Fallback extent setting succeeded")
                    except Exception as e2:
                        self.log_message(f"  Fallback extent setting also failed: {str(e2)}")
                        return
                
                # Get map frame boundaries
                map_x = map_frame.elementPositionX
                map_y = map_frame.elementPositionY
                map_width = map_frame.elementWidth
                map_height = map_frame.elementHeight
                map_center_x = map_x + map_width / 2
                map_center_y = map_y + map_height / 2
                
                self.log_message(f"  Map frame: ({map_x:.0f}, {map_y:.0f}) size: {map_width:.0f} x {map_height:.0f}")
                
                # Check which elements actually intersect with content area
                conflicting_elements = []
                all_elements = []
                all_elements.extend(text_elements)
                all_elements.extend(graphic_elements)
                all_elements.extend(legend_elements)
                all_elements.extend(mapsurround_elements)
                all_elements.extend(mapframe_elements)
                all_elements.extend(picture_elements)
                
                self.log_message(f"  Checking {len(all_elements)} layout elements for intersections...")
                
                for element in all_elements:
                    try:
                        if hasattr(element, 'elementPositionX') and hasattr(element, 'elementPositionY'):
                            elem_x = element.elementPositionX
                            elem_y = element.elementPositionY
                            elem_width = element.elementWidth
                            elem_height = element.elementHeight
                            
                            # Check if element actually overlaps the map frame
                            overlaps = not (
                                elem_x + elem_width <= map_x or        # Element completely to the left
                                elem_x >= map_x + map_width or         # Element completely to the right
                                elem_y + elem_height <= map_y or       # Element completely above
                                elem_y >= map_y + map_height           # Element completely below
                            )
                            
                            if overlaps:
                                elem_center_x = elem_x + elem_width / 2
                                elem_center_y = elem_y + elem_height / 2
                                
                                # Calculate actual intersection area
                                intersection_area = self._calculate_intersection_area(
                                    map_x, map_y, map_x + map_width, map_y + map_height,
                                    elem_x, elem_y, elem_x + elem_width, elem_y + elem_height
                                )
                                
                                # Only include elements with significant intersection
                                if intersection_area > 0:
                                    conflicting_elements.append({
                                        'element': element,
                                        'x': elem_x,
                                        'y': elem_y,
                                        'width': elem_width,
                                        'height': elem_height,
                                        'center_x': elem_center_x,
                                        'center_y': elem_center_y,
                                        'type': type(element).__name__,
                                        'intersection_area': intersection_area
                                    })
                                    
                                    self.log_message(f"  CONFLICT: {element.name} ({type(element).__name__}) overlaps map area")
                                    self.log_message(f"    Overlap area: {intersection_area:.0f} sq units")
                                    
                    except Exception as e:
                        self.log_message(f"  Error analyzing element: {str(e)}")
                        continue
                
                # Only adjust if there are actual conflicts
                if conflicting_elements:
                    self.log_message(f"  Found {len(conflicting_elements)} elements with actual overlaps")
                    
                    # Enhanced conflict calculation
                    left_conflict = 0
                    right_conflict = 0
                    up_conflict = 0
                    down_conflict = 0
                    
                    for elem in conflicting_elements:
                        elem_center_x = elem['center_x']
                        elem_center_y = elem['center_y']
                        conflict_weight = elem['intersection_area']
                        
                        # Enhanced element type weighting
                        type_multiplier = 1.0
                        elem_type = elem['type']
                        if "LegendElement" in elem_type:
                            type_multiplier = 4.0  # Highest priority for legends
                        elif "MapFrame" in elem_type:
                            type_multiplier = 3.5  # Very high priority for inset maps
                        elif "MapSurroundElement" in elem_type:
                            # Scale bars and north arrows - only high priority if significant overlap
                            if conflict_weight > (map_width * map_height * 0.1):  # More than 10% overlap
                                type_multiplier = 2.0
                            else:
                                type_multiplier = 1.2  # Light weight for small overlaps
                        elif "TextElement" in elem_type:
                            type_multiplier = 2.5  # High priority for text labels
                        elif "GraphicElement" in elem_type:
                            type_multiplier = 1.5
                        
                        weighted_conflict = conflict_weight * type_multiplier
                        
                        # Determine which direction this element pushes content
                        if elem_center_x < map_center_x:  # Element on left side
                            right_conflict += weighted_conflict  # Push content right
                        else:  # Element on right side
                            left_conflict += weighted_conflict   # Push content left
                        
                        if elem_center_y < map_center_y:  # Element on bottom
                            up_conflict += weighted_conflict     # Push content up
                        else:  # Element on top
                            down_conflict += weighted_conflict   # Push content down
                    
                    self.log_message(f"  Final conflict scores - Left: {left_conflict:.1f}, Right: {right_conflict:.1f}, "
                                   f"Up: {up_conflict:.1f}, Down: {down_conflict:.1f}")
                    
                    # Calculate shifts to avoid conflicts
                    base_shift_factor = 0.20
                    
                    # Calculate horizontal shift
                    horizontal_shift = 0
                    if left_conflict > right_conflict and left_conflict > 0:
                        horizontal_shift = -base_shift_factor * (left_conflict / (left_conflict + right_conflict))
                        self.log_message(f"  Shifting LEFT to avoid right-side elements")
                    elif right_conflict > left_conflict and right_conflict > 0:
                        horizontal_shift = base_shift_factor * (right_conflict / (left_conflict + right_conflict))
                        self.log_message(f"  Shifting RIGHT to avoid left-side elements")
                    
                    # Calculate vertical shift
                    vertical_shift = 0
                    if up_conflict > down_conflict and up_conflict > 0:
                        vertical_shift = base_shift_factor * (up_conflict / (up_conflict + down_conflict))
                        self.log_message(f"  Shifting UP to avoid bottom elements")
                    elif down_conflict > up_conflict and down_conflict > 0:
                        vertical_shift = -base_shift_factor * (down_conflict / (up_conflict + down_conflict))
                        self.log_message(f"  Shifting DOWN to avoid top elements")
                    
                    # Smart zoom out based on conflict severity
                    zoom_out_factor = 1.0 + (len(conflicting_elements) * 0.12)  # 12% per conflict
                    zoom_out_factor = min(zoom_out_factor, 1.6)  # Cap at 60% zoom out
                    
                    # Apply adjustments
                    current_width = buffered_extent.width
                    current_height = buffered_extent.height
                    current_center_x = (buffered_extent.XMin + buffered_extent.XMax) / 2
                    current_center_y = (buffered_extent.YMin + buffered_extent.YMax) / 2
                    
                    new_width = current_width * zoom_out_factor
                    new_height = current_height * zoom_out_factor
                    
                    shift_x = current_width * horizontal_shift
                    shift_y = current_height * vertical_shift
                    
                    new_center_x = current_center_x + shift_x
                    new_center_y = current_center_y + shift_y
                    
                    adjusted_extent = arcpy.Extent(
                        new_center_x - new_width / 2,
                        new_center_y - new_height / 2,
                        new_center_x + new_width / 2,
                        new_center_y + new_height / 2
                    )
                    
                    self.log_message(f"  Applied adjustments - H: {horizontal_shift:.3f}, V: {vertical_shift:.3f}")
                    self.log_message(f"  Zoom factor: {zoom_out_factor:.2f}, Final shifts: X={shift_x:.0f}, Y={shift_y:.0f}")
                    
                    buffered_extent = adjusted_extent
                    
                else:
                    self.log_message("  No actual overlaps detected - content is clear of all layout elements")
                
            except Exception as e:
                self.log_message(f"  Error during smart element avoidance: {str(e)}")
                import traceback
                self.log_message(f"  Traceback: {traceback.format_exc()}")
        
        # Set the final extent
        try:
            map_frame.camera.setExtent(buffered_extent)
            self.log_message(f"  Successfully set extent for {dive_id} using {len(visible_layers)} layers")
        except Exception as e:
            self.log_message(f"  Error setting extent: {str(e)}")
            # Try fallback method
            try:
                self.log_message("  Attempting fallback zoom to extent (no avoidance)")
                map_frame.camera = buffered_extent
                self.log_message("  Fallback zoom successful")
            except Exception as alt_e:
                self.log_message(f"  Fallback zoom also failed: {str(alt_e)}")

    def on_layer_group_selection_changed(self):
        """Handle changes in layer group selection"""
        # This method can be used for any future functionality when layer group selection changes
        # For now, it's just a placeholder to prevent the trace callback error
        pass

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

# Run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = LayoutAutomatorApp(root)
    root.mainloop()