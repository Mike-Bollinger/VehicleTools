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
        
        # Extent layer group selection - MOVED UP TO HERE
        extent_frame = ttk.LabelFrame(main_frame, text="Extent Control", padding="10")
        extent_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(extent_frame, text="Select layer group to define map extent:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.extent_group_var = tk.StringVar()
        self.extent_group_dropdown = ttk.Combobox(extent_frame, textvariable=self.extent_group_var, state="readonly", width=40)
        self.extent_group_dropdown.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # Add a checkbox for fixed extent option
        self.use_fixed_extent = tk.BooleanVar(value=False)
        ttk.Checkbutton(extent_frame, text="Use fixed extent (don't zoom to features)", 
                        variable=self.use_fixed_extent).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)
    
        # Add layout element awareness option
        self.avoid_elements = tk.BooleanVar(value=True)
        ttk.Checkbutton(extent_frame, text="Smart extent: avoid legends, scale bars and inset maps", 
                        variable=self.avoid_elements).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Add extent buffer controls
        buffer_frame = ttk.Frame(extent_frame)
        buffer_frame.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5)

        ttk.Label(buffer_frame, text="Extent buffer (%):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.buffer_percentage = tk.IntVar(value=10)
        ttk.Entry(buffer_frame, textvariable=self.buffer_percentage, width=5).grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5,20))
        
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
            
        # Update the extent group dropdown
        self.update_extent_group_dropdown()
    
    # Add this new method to handle changes in layer group selection
    def on_layer_group_selection_changed(self):
        """Update the extent dropdown when layer group selection changes"""
        self.update_extent_group_dropdown()
    
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
        else:
            self.log_message("\nNo dive layers found in the selected groups")
        
        # Update the extent group dropdown with the selected layer groups
        self.update_extent_group_dropdown()
        
        # If there are selected groups but no extent group is selected, select the first one
        if all_dive_numbers and not self.extent_group_var.get():
            selected_groups = [key for key, var in self.layer_group_vars.items() if var.get()]
            if selected_groups:
                self.extent_group_var.set(selected_groups[0])
                self.log_message(f"Automatically selected {selected_groups[0]} as the extent group")
    
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
        """Zoom to the extent of active layers for the given dive using the selected extent group"""
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
        
        # Get the selected extent group
        extent_group_key = self.extent_group_var.get()
        if not extent_group_key:
            self.log_message("  No extent group selected, using all visible dive layers")
            # Use the old method with all visible layers
            visible_layers = []
            for layer in active_map_obj.listLayers():
                if hasattr(layer, 'visible') and layer.visible and dive_id.upper() in layer.name.upper():
                    if hasattr(layer, 'isFeatureLayer') and layer.isFeatureLayer:
                        visible_layers.append(layer)
        else:
            # Use the selected extent group
            self.log_message(f"  Using extent group: {extent_group_key}")
            map_name, group_name = extent_group_key.split(':', 1)
            
            # Get the map object
            map_obj = None
            for m in self.project.listMaps():
                if m.name == map_name:
                    map_obj = m
                    break
            
            if not map_obj:
                self.log_message(f"  Map not found for extent: {map_name}")
                return
            
            # Find the group layer
            group_layer = None
            for layer in map_obj.listLayers():
                if layer.name == group_name:
                    group_layer = layer
                    break
            
            if not group_layer:
                self.log_message(f"  Group layer not found for extent: {group_name}")
                return
            
            # Get visible layers for this dive from the selected group
            visible_layers = []
            for layer in group_layer.listLayers():
                if hasattr(layer, 'visible') and layer.visible and dive_id.upper() in layer.name.upper():
                    if hasattr(layer, 'isFeatureLayer') and layer.isFeatureLayer:
                        visible_layers.append(layer)
    
        if not visible_layers:
            self.log_message(f"  No visible feature layers found for {dive_id}")
            return
        
        # Get combined extent
        self.log_message(f"  Getting extent from {len(visible_layers)} layers")
        extent = None
        for layer in visible_layers:
            try:
                layer_extent = arcpy.Describe(layer).extent
                if extent is None:
                    extent = layer_extent
                else:
                    extent = extent.union(layer_extent)
            except Exception as e:
                self.log_message(f"  Error getting extent for {layer.name}: {str(e)}")
        
        if extent:
            # Get buffer percentage from control
            buffer_pct = self.buffer_percentage.get() / 100.0
            
            # Calculate basic buffer amounts
            buffer_x = extent.width * buffer_pct
            buffer_y = extent.height * buffer_pct
            
            # Create initial buffered extent
            buffered_extent = arcpy.Extent(
                extent.XMin - buffer_x,
                extent.YMin - buffer_y,
                extent.XMax + buffer_x,
                extent.YMax + buffer_y
            )
            
            # Apply smart element avoidance if enabled
            if self.avoid_elements.get():
                try:
                    self.log_message("  Applying smart element avoidance...")
                    
                    # Find map elements that might overlap data
                    elements_to_avoid = []
                    
                    # Get elements that could overlap: legends, north arrows, scale bars, inset maps
                    for elem_type in ["LEGEND_ELEMENT", "MAPSURROUND_ELEMENT", "MAPFRAME_ELEMENT"]:
                        elements = layout.listElements(elem_type)
                        
                        # Skip the main map frame
                        if elem_type == "MAPFRAME_ELEMENT":
                            elements = [e for e in elements if e != map_frame]
                            
                        elements_to_avoid.extend(elements)
                    
                    self.log_message(f"  Found {len(elements_to_avoid)} layout elements to avoid")
                    
                    # If we found elements to avoid
                    if elements_to_avoid:
                        # Apply the new extent first to get proper coordinates
                        try:
                            map_frame.camera.setExtent(buffered_extent)
                        except Exception as e:
                            self.log_message(f"  Warning: Initial extent setting failed: {str(e)}")
                            try:
                                map_frame.camera = buffered_extent
                            except:
                                self.log_message("  Could not set initial extent for element detection")
                                return
                        
                        # Get the new visible area
                        new_visible_extent = map_frame.camera.getExtent()
                        
                        # Convert layout elements to map coordinates
                        element_areas = []
                        for element in elements_to_avoid:
                            try:
                                # Get element position based on element type
                                if hasattr(element, 'elementPositionX') and hasattr(element, 'elementPositionY'):
                                    # Most elements have elementPosition properties
                                    elem_x = element.elementPositionX
                                    elem_y = element.elementPositionY
                                    elem_width = element.elementWidth
                                    elem_height = element.elementHeight
                                elif hasattr(element, 'getExtent'):
                                    # Some elements have a getExtent method
                                    elem_extent = element.getExtent()
                                    elem_x = elem_extent.XMin
                                    elem_y = elem_extent.YMin
                                    elem_width = elem_extent.XMax - elem_extent.XMin
                                    elem_height = elem_extent.YMax - elem_extent.YMin
                                else:
                                    # Fallback to alternative properties
                                    elem_properties = {prop: getattr(element, prop) for prop in dir(element) 
                                                     if not prop.startswith('_') and not callable(getattr(element, prop))}
                                    
                                    # Try to identify position properties
                                    position_props = [prop for prop in elem_properties.keys() 
                                                     if 'position' in prop.lower() or 'location' in prop.lower()]
                                    
                                    if position_props:
                                        self.log_message(f"  Found alternative position properties: {position_props}")
                                        # Try to use alternative position properties
                                        if 'X' in elem_properties and 'Y' in elem_properties:
                                            elem_x = elem_properties['X']
                                            elem_y = elem_properties['Y']
                                            elem_width = elem_properties.get('width', 20)  # Default width if not found
                                            elem_height = elem_properties.get('height', 20)  # Default height if not found
                                        else:
                                            # Skip this element if we can't determine position
                                            self.log_message(f"  Skipping element: Cannot determine position for {element.name}")
                                            continue
                                    else:
                                        # Skip this element if we can't determine position
                                        self.log_message(f"  Skipping element: Cannot determine position for {element.name}")
                                        continue
                                
                                # Convert to map coordinates (approximate)
                                map_width = new_visible_extent.XMax - new_visible_extent.XMin
                                map_height = new_visible_extent.YMax - new_visible_extent.YMin
                                page_width = layout.pageWidth
                                page_height = layout.pageHeight
                                
                                # Calculate the element extents in map coordinates
                                elem_map_min_x = new_visible_extent.XMin + (elem_x / page_width) * map_width
                                elem_map_min_y = new_visible_extent.YMin + (elem_y / page_height) * map_height
                                elem_map_max_x = elem_map_min_x + (elem_width / page_width) * map_width
                                elem_map_max_y = elem_map_min_y + (elem_height / page_height) * map_height
                                
                                element_areas.append((elem_map_min_x, elem_map_min_y, elem_map_max_x, elem_map_max_y))
                                self.log_message(f"  Detected element: {element.name} at position ({elem_x:.1f}, {elem_y:.1f})")
                            except Exception as e:
                                # More detailed error logging
                                self.log_message(f"  Error calculating element area for {type(element).__name__}: {str(e)}")
                                
                                # Debug: Output all available properties
                                try:
                                    properties = [prop for prop in dir(element) if not prop.startswith('_') and not callable(getattr(element, prop))]
                                    self.log_message(f"  Available properties for {type(element).__name__}: {', '.join(properties[:10])}...")
                                except:
                                    pass
                        
                        # Adjust the extent to avoid elements
                        if element_areas:
                            # Determine which sides have most elements
                            left_count = right_count = top_count = bottom_count = 0
                            
                            for e_min_x, e_min_y, e_max_x, e_max_y in element_areas:
                                # Check if element is predominantly on one side
                                map_center_x = (new_visible_extent.XMin + new_visible_extent.XMax) / 2
                                map_center_y = (new_visible_extent.YMin + new_visible_extent.YMax) / 2
                                
                                if (e_min_x + e_max_x) / 2 < map_center_x:
                                    left_count += 1
                                else:
                                    right_count += 1
                                    
                                if (e_min_y + e_max_y) / 2 < map_center_y:
                                    bottom_count += 1
                                else:
                                    top_count += 1
                            
                            self.log_message(f"  Element distribution - Left: {left_count}, Right: {right_count}, Top: {top_count}, Bottom: {bottom_count}")
                            
                            # Adjust buffer to avoid crowded sides
                            additional_buffer = max(buffer_x, buffer_y) * 2
                            new_buffered_extent = arcpy.Extent(
                                buffered_extent.XMin - (additional_buffer if right_count > left_count else 0),
                                buffered_extent.YMin - (additional_buffer if top_count > bottom_count else 0),
                                buffered_extent.XMax + (additional_buffer if left_count > right_count else 0),
                                buffered_extent.YMax + (additional_buffer if bottom_count > top_count else 0)
                            )
                            
                            # Apply the adjusted extent
                            buffered_extent = new_buffered_extent
                            self.log_message(f"  Adjusted extent to avoid {len(element_areas)} layout elements")
                except Exception as e:
                    self.log_message(f"  Error during smart element avoidance: {str(e)}")
            
            # Set the final extent
            try:
                map_frame.camera.setExtent(buffered_extent)
                self.log_message(f"  Zoomed to extent of {len(visible_layers)} layers for {dive_id}")
            except Exception as e:
                self.log_message(f"  Error setting extent: {str(e)}")
                # Try an alternative approach if the first one fails
                try:
                    self.log_message("  Trying alternative extent setting method...")
                    map_frame.camera = buffered_extent
                    self.log_message("  Alternative extent setting succeeded")
                except Exception as alt_e:
                    self.log_message(f"  Alternative extent setting also failed: {str(alt_e)}")
    
    def update_extent_group_dropdown(self):
        """Update the extent group dropdown with the selected layer groups"""
        selected_groups = [key for key, var in self.layer_group_vars.items() if var.get()]
        
        # Store current selection
        current_selection = self.extent_group_var.get()
        
        # Update dropdown values
        self.extent_group_dropdown['values'] = selected_groups
        
        # If there are selected groups
        if selected_groups:
            # If current selection is still valid, keep it
            if current_selection in selected_groups:
                self.extent_group_var.set(current_selection)
            else:
                # Otherwise select the first group
                self.extent_group_var.set(selected_groups[0])
        else:
            # Clear the selection if no groups are selected
            self.extent_group_var.set("")
        
        # Log the update
        if selected_groups:
            self.log_message(f"Updated extent control with {len(selected_groups)} selected layer groups")


def main():
    """Main function to run the application"""
    root = tk.Tk()
    app = LayoutAutomatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()