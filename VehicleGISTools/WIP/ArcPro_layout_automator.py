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
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.patches import Rectangle
import numpy as np


class InteractiveExtentController:
    """Interactive extent control window with embedded map display and mouse interaction"""
    
    def __init__(self, parent_app, layout, dive_list, selected_groups):
        self.parent_app = parent_app
        self.layout = layout
        self.dive_list = dive_list
        self.selected_groups = selected_groups
        self.current_dive_index = 0
        self.user_cancelled = False
        self.completed_dives = []
        
        # Map display variables
        self.current_extent = None
        self.original_extent = None
        self.visible_layers = []
        self.layout_elements = []
        
        # Mouse interaction variables
        self.mouse_pressed = False
        self.last_mouse_x = None
        self.last_mouse_y = None
        
        # Create the interactive window
        self.create_interactive_window()
        
    def create_interactive_window(self):
        """Create the interactive extent control window with embedded map"""
        self.window = tk.Toplevel(self.parent_app.root)
        self.window.title("Interactive Extent Control")
        self.window.geometry("1200x800")
        self.window.resizable(True, True)
        
        # Make it modal
        self.window.transient(self.parent_app.root)
        self.window.grab_set()
        
        # Create main container
        main_container = ttk.Frame(self.window)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left panel for controls
        left_panel = ttk.Frame(main_container, width=300)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        # Right panel for map
        right_panel = ttk.Frame(main_container)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # === LEFT PANEL CONTROLS ===
        
        # Title
        title_label = ttk.Label(left_panel, text="Interactive Extent Control", 
                               font=("TkDefaultFont", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Current dive info
        self.dive_info_frame = ttk.LabelFrame(left_panel, text="Current Dive", padding="10")
        self.dive_info_frame.pack(fill=tk.X, pady=5)
        
        self.current_dive_label = ttk.Label(self.dive_info_frame, text="", 
                                           font=("TkDefaultFont", 12, "bold"))
        self.current_dive_label.pack()
        
        self.progress_label = ttk.Label(self.dive_info_frame, text="")
        self.progress_label.pack()
        
        # Extent controls
        extent_control_frame = ttk.LabelFrame(left_panel, text="Extent Controls", padding="10")
        extent_control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(extent_control_frame, text="Zoom to Layer Extent", 
                  command=self.zoom_to_layers).pack(fill=tk.X, pady=2)
        ttk.Button(extent_control_frame, text="Reset to Original", 
                  command=self.reset_extent).pack(fill=tk.X, pady=2)
        
        # Zoom controls
        zoom_frame = ttk.Frame(extent_control_frame)
        zoom_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(zoom_frame, text="Zoom In", command=self.zoom_in, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="Zoom Out", command=self.zoom_out, width=10).pack(side=tk.LEFT, padx=2)
        
        # Pan controls
        pan_frame = ttk.LabelFrame(left_panel, text="Pan Controls", padding="10")
        pan_frame.pack(fill=tk.X, pady=5)
        
        # Pan buttons in grid
        pan_grid = ttk.Frame(pan_frame)
        pan_grid.pack()
        
        ttk.Button(pan_grid, text="↑", command=lambda: self.pan_map(0, 0.2), width=3).grid(row=0, column=1, padx=2, pady=2)
        ttk.Button(pan_grid, text="←", command=lambda: self.pan_map(-0.2, 0), width=3).grid(row=1, column=0, padx=2, pady=2)
        ttk.Button(pan_grid, text="●", command=self.center_on_features, width=3).grid(row=1, column=1, padx=2, pady=2)
        ttk.Button(pan_grid, text="→", command=lambda: self.pan_map(0.2, 0), width=3).grid(row=1, column=2, padx=2, pady=2)
        ttk.Button(pan_grid, text="↓", command=lambda: self.pan_map(0, -0.2), width=3).grid(row=2, column=1, padx=2, pady=2)
        
        # Instructions
        instructions_frame = ttk.LabelFrame(left_panel, text="Mouse Controls", padding="10")
        instructions_frame.pack(fill=tk.X, pady=5)
        
        instructions_text = "• Left-click and drag to pan\n• Mouse wheel to zoom\n• Use buttons for precise control"
        instructions_label = ttk.Label(instructions_frame, text=instructions_text, justify=tk.LEFT)
        instructions_label.pack(anchor=tk.W)
        
        # Layer info
        layer_info_frame = ttk.LabelFrame(left_panel, text="Current Layers", padding="10")
        layer_info_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create scrollable list for layers
        self.layer_listbox = tk.Listbox(layer_info_frame, height=6)
        layer_scrollbar = ttk.Scrollbar(layer_info_frame, orient="vertical", command=self.layer_listbox.yview)
        self.layer_listbox.configure(yscrollcommand=layer_scrollbar.set)
        
        self.layer_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        layer_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Status
        self.status_label = ttk.Label(left_panel, text="Ready to start...", 
                                     foreground="blue", wraplength=280)
        self.status_label.pack(pady=5)
        
        # Navigation buttons
        button_frame = ttk.Frame(left_panel)
        button_frame.pack(fill=tk.X, pady=10)
        
        self.next_button = ttk.Button(button_frame, text="NEXT DIVE", 
                                     command=self.next_dive)
        self.next_button.pack(side=tk.RIGHT, padx=5)
        
        self.cancel_button = ttk.Button(button_frame, text="CANCEL", 
                                       command=self.cancel_process)
        self.cancel_button.pack(side=tk.RIGHT, padx=5)
        
        # === RIGHT PANEL MAP ===
        
        # Create matplotlib figure with tight layout
        self.fig, self.ax = plt.subplots(figsize=(10, 8))
        self.fig.patch.set_facecolor('white')
        self.fig.tight_layout(pad=1.0)
        
        # Create canvas
        self.canvas = FigureCanvasTkAgg(self.fig, right_panel)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Connect mouse events for interaction
        self.canvas.mpl_connect('button_press_event', self.on_mouse_press)
        self.canvas.mpl_connect('button_release_event', self.on_mouse_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        self.canvas.mpl_connect('scroll_event', self.on_mouse_scroll)
        
        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self.cancel_process)
        
        # Start the process
        self.start_interactive_process()
    
    def on_mouse_press(self, event):
        """Handle mouse press events"""
        if event.inaxes != self.ax:
            return
        
        if event.button == 1:  # Left click
            self.mouse_pressed = True
            self.last_mouse_x = event.xdata
            self.last_mouse_y = event.ydata
    
    def on_mouse_release(self, event):
        """Handle mouse release events"""
        self.mouse_pressed = False
        self.last_mouse_x = None
        self.last_mouse_y = None
    
    def on_mouse_move(self, event):
        """Handle mouse move events for panning"""
        if not self.mouse_pressed or event.inaxes != self.ax:
            return
        
        if self.last_mouse_x is None or self.last_mouse_y is None:
            return
        
        if self.current_extent:
            # Calculate the pan distance in data coordinates
            dx = self.last_mouse_x - event.xdata
            dy = self.last_mouse_y - event.ydata
            
            # Update the extent
            self.current_extent = arcpy.Extent(
                self.current_extent.XMin + dx,
                self.current_extent.YMin + dy,
                self.current_extent.XMax + dx,
                self.current_extent.YMax + dy
            )
            
            # Update the display
            self.plot_layers()
            self.plot_layout_elements()
    
    def on_mouse_scroll(self, event):
        """Handle mouse scroll events for zooming"""
        if event.inaxes != self.ax:
            return
        
        if self.current_extent:
            # Get the mouse position in data coordinates
            mouse_x = event.xdata
            mouse_y = event.ydata
            
            if mouse_x is None or mouse_y is None:
                return
            
            # Zoom factor
            zoom_factor = 0.9 if event.step > 0 else 1.1
            
            # Calculate new size
            new_width = self.current_extent.width * zoom_factor
            new_height = self.current_extent.height * zoom_factor
            
            # Zoom towards mouse position
            x_ratio = (mouse_x - self.current_extent.XMin) / self.current_extent.width
            y_ratio = (mouse_y - self.current_extent.YMin) / self.current_extent.height
            
            new_x_min = mouse_x - (new_width * x_ratio)
            new_y_min = mouse_y - (new_height * y_ratio)
            
            self.current_extent = arcpy.Extent(
                new_x_min,
                new_y_min,
                new_x_min + new_width,
                new_y_min + new_height
            )
            
            # Update the display
            self.plot_layers()
            self.plot_layout_elements()
    
    def start_interactive_process(self):
        """Start the interactive extent control process"""
        try:
            self.parent_app.log_message("Starting interactive extent control with embedded map...")
            
            # Start with the first dive
            self.load_current_dive()
            
        except Exception as e:
            self.parent_app.log_message(f"Error starting interactive process: {str(e)}")
            messagebox.showerror("Error", f"Failed to start interactive process: {str(e)}")
            self.cancel_process()
    
    def load_current_dive(self):
        """Load the current dive and update the display"""
        if self.current_dive_index >= len(self.dive_list):
            self.complete_process()
            return
        
        current_dive = self.dive_list[self.current_dive_index]
        
        # Ensure current_dive is an integer for formatting
        if isinstance(current_dive, str):
            current_dive = int(current_dive)
        
        dive_id = f"DIVE{current_dive:03d}"
        
        # Update the GUI
        self.current_dive_label.config(text=f"Current: {dive_id}")
        self.progress_label.config(text=f"Dive {self.current_dive_index + 1} of {len(self.dive_list)}")
        
        progress_pct = int(((self.current_dive_index + 1) / len(self.dive_list)) * 100)
        self.status_label.config(text=f"Adjust extent for {dive_id} using the map and controls ({progress_pct}% complete)")
        
        self.parent_app.log_message(f"Interactive: Loading {dive_id} ({self.current_dive_index + 1}/{len(self.dive_list)})")
        
        try:
            # Set up the dive layers
            self.setup_dive_layers(dive_id)
            
            # Load and display the map
            self.load_map_display(dive_id)
            
            # Enable the NEXT button
            self.next_button.config(state=tk.NORMAL)
            
        except Exception as e:
            self.parent_app.log_message(f"Error loading {dive_id}: {str(e)}")
            messagebox.showerror("Error", f"Error loading {dive_id}: {str(e)}")
    
    def setup_dive_layers(self, dive_id):
        """Set up layer visibility for the current dive"""
        # Get all dive layers
        all_dive_layers = self.parent_app.pre_collect_dive_layers(self.selected_groups)
        
        # Prepare layer visibility changes
        layers_to_hide = []
        layers_to_show = []
        
        for layer_info in all_dive_layers:
            layer = layer_info['layer']
            if self.parent_app.dive_pattern.search(layer.name):
                if dive_id.upper() in layer.name.upper():
                    layers_to_show.append((layer, True))
                else:
                    layers_to_hide.append((layer, False))
        
        # Apply visibility changes
        if layers_to_hide:
            self.parent_app.batch_set_layer_visibility(layers_to_hide, dive_id)
        
        if layers_to_show:
            self.parent_app.batch_set_layer_visibility(layers_to_show, dive_id)
    
    def load_map_display(self, dive_id):
        """Load the map display with current dive layers"""
        try:
            # Clear the plot
            self.ax.clear()
            
            # Get visible layers for this dive
            self.visible_layers = self.parent_app.get_visible_layers_for_dive(self.selected_groups, dive_id)
            
            self.parent_app.log_message(f"Found {len(self.visible_layers)} visible layers for {dive_id}")
            
            if not self.visible_layers:
                self.ax.text(0.5, 0.5, f"No visible layers found for {dive_id}", 
                       ha='center', va='center', transform=self.ax.transAxes, fontsize=12)
                self.canvas.draw()
                return
            
            # Update layer list
            self.update_layer_list()
            
            # Calculate and set initial extent
            extent = self.parent_app.calculate_combined_extent(self.visible_layers)
            
            if extent:
                self.parent_app.log_message(f"Calculated extent: {extent.XMin:.6f}, {extent.YMin:.6f}, {extent.XMax:.6f}, {extent.YMax:.6f}")
                
                # Apply buffer for initial display
                base_buffer_pct = self.parent_app.buffer_percentage.get() / 100.0
                buffer_x = extent.width * base_buffer_pct
                buffer_y = extent.height * base_buffer_pct
                
                # Ensure minimum buffer
                min_buffer = 0.001
                buffer_x = max(buffer_x, min_buffer)
                buffer_y = max(buffer_y, min_buffer)
                
                self.original_extent = arcpy.Extent(
                    extent.XMin - buffer_x,
                    extent.YMin - buffer_y,
                    extent.XMax + buffer_x,
                    extent.YMax + buffer_y
                )
                
                self.current_extent = self.original_extent
                
                # Plot the layers
                self.plot_layers()
                
                # Add layout elements
                self.plot_layout_elements()
                
                self.parent_app.log_message(f"Loaded map display for {dive_id} with {len(self.visible_layers)} layers")
            else:
                self.ax.text(0.5, 0.5, f"Could not calculate extent for {dive_id}", 
                            ha='center', va='center', transform=self.ax.transAxes, fontsize=12, color='orange')
                self.canvas.draw()
                
        except Exception as e:
            self.parent_app.log_message(f"Error loading map display for {dive_id}: {str(e)}")
            self.ax.text(0.5, 0.5, f"Error loading map for {dive_id}\n{str(e)}", 
                        ha='center', va='center', transform=self.ax.transAxes, fontsize=10, color='red')
            self.canvas.draw()
    
    def extract_layer_geometries(self, layer):
        """Extract actual geometries from a layer"""
        geometries = []
        try:
            # Use arcpy to get feature geometries
            with arcpy.da.SearchCursor(layer, ["SHAPE@"]) as cursor:
                for row in cursor:
                    geom = row[0]
                    if geom:
                        # Convert geometry to coordinate lists
                        if geom.type == "polyline":
                            for part in geom:
                                coords = [(point.X, point.Y) for point in part if point]
                                if coords:
                                    geometries.append(('line', coords))
                        elif geom.type == "point":
                            geometries.append(('point', [(geom.centroid.X, geom.centroid.Y)]))
                        elif geom.type == "polygon":
                            for part in geom:
                                coords = [(point.X, point.Y) for point in part if point]
                                if coords:
                                    geometries.append(('polygon', coords))
        except Exception as e:
            self.parent_app.log_message(f"  Could not extract geometries from {layer.name}: {str(e)}")
            # Fallback to extent box
            try:
                layer_extent = arcpy.Describe(layer).extent
                coords = [
                    (layer_extent.XMin, layer_extent.YMin),
                    (layer_extent.XMax, layer_extent.YMin),
                    (layer_extent.XMax, layer_extent.YMax),
                    (layer_extent.XMin, layer_extent.YMax),
                    (layer_extent.XMin, layer_extent.YMin)
                ]
                geometries.append(('polygon', coords))
            except:
                pass
        
        return geometries
    
    def plot_layers(self):
        """Plot the visible layers on the map with actual geometries"""
        try:
            layer_colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray']
            
            self.parent_app.log_message(f"Plotting {len(self.visible_layers)} layers with geometries...")
            
            # Clear the axes but keep the extent
            self.ax.clear()
            
            for i, layer in enumerate(self.visible_layers):
                try:
                    color = layer_colors[i % len(layer_colors)]
                    
                    # Extract actual geometries
                    geometries = self.extract_layer_geometries(layer)
                    
                    self.parent_app.log_message(f"  Layer {layer.name}: {len(geometries)} geometries")
                    
                    # Plot each geometry
                    for geom_type, coords in geometries:
                        if geom_type == 'line':
                            x_coords = [coord[0] for coord in coords]
                            y_coords = [coord[1] for coord in coords]
                            self.ax.plot(x_coords, y_coords, color=color, linewidth=2, alpha=0.8, label=layer.name if i == 0 else "")
                        elif geom_type == 'point':
                            x_coords = [coord[0] for coord in coords]
                            y_coords = [coord[1] for coord in coords]
                            self.ax.scatter(x_coords, y_coords, c=color, s=50, alpha=0.8, label=layer.name if i == 0 else "")
                        elif geom_type == 'polygon':
                            x_coords = [coord[0] for coord in coords]
                            y_coords = [coord[1] for coord in coords]
                            self.ax.fill(x_coords, y_coords, color=color, alpha=0.3, edgecolor=color, linewidth=2, label=layer.name if i == 0 else "")
                    
                except Exception as e:
                    self.parent_app.log_message(f"Error plotting layer {layer.name}: {str(e)}")
    
            # Set the extent
            if self.current_extent:
                self.ax.set_xlim(self.current_extent.XMin, self.current_extent.XMax)
                self.ax.set_ylim(self.current_extent.YMin, self.current_extent.YMax)
            
            # Set labels and grid
            self.ax.set_xlabel('X Coordinate (Longitude)')
            self.ax.set_ylabel('Y Coordinate (Latitude)')
            self.ax.grid(True, alpha=0.3)
            self.ax.set_aspect('equal', adjustable='box')
            
            # Add title
            current_dive = self.dive_list[self.current_dive_index]
            if isinstance(current_dive, str):
                current_dive = int(current_dive)
            dive_title = f"DIVE{current_dive:03d}"
            
            self.ax.set_title(f'{dive_title} - Interactive Extent Control', fontsize=14, fontweight='bold')
            
            # Force the canvas to update
            self.canvas.draw()
            self.canvas.flush_events()
            
            self.parent_app.log_message("Map plotting with geometries completed")
        
        except Exception as e:
            self.parent_app.log_message(f"Error plotting layers: {str(e)}")
            # Show error on the plot
            self.ax.text(0.5, 0.5, f"Error plotting layers:\n{str(e)}", 
                        ha='center', va='center', transform=self.ax.transAxes, fontsize=10, color='red')
            self.canvas.draw()
    
    def plot_layout_elements(self):
        """Plot layout elements as static overlays relative to the plot area"""
        try:
            # Get the current plot limits
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()
            
            # Calculate layout element positions in axes coordinates (0-1 range)
            # These positions are fixed relative to the plot frame, not the data
            
            # Legend position (typically top-right of the plot area)
            legend_ax_x = 0.75  # 75% across the plot
            legend_ax_y = 0.85  # 85% up the plot
            legend_ax_w = 0.2   # 20% of plot width
            legend_ax_h = 0.1   # 10% of plot height
            
            # Convert to data coordinates for this specific extent
            plot_width = xlim[1] - xlim[0]
            plot_height = ylim[1] - ylim[0]
            
            legend_x = xlim[0] + (legend_ax_x * plot_width)
            legend_y = ylim[0] + (legend_ax_y * plot_height)
            legend_w = legend_ax_w * plot_width
            legend_h = legend_ax_h * plot_height
            
            legend_rect = Rectangle((legend_x, legend_y), legend_w, legend_h,
                                  linewidth=2, edgecolor='black', facecolor='lightgray',
                                  alpha=0.7, linestyle='--', zorder=1000)
            self.ax.add_patch(legend_rect)
            self.ax.text(legend_x + legend_w/2, legend_y + legend_h/2, 'LEGEND',
                        ha='center', va='center', fontsize=8, fontweight='bold', zorder=1001)
            
            # Scale bar position (typically bottom-left of the plot area)
            scale_ax_x = 0.05  # 5% across the plot
            scale_ax_y = 0.05  # 5% up the plot
            scale_ax_w = 0.15  # 15% of plot width
            scale_ax_h = 0.05  # 5% of plot height
            
            scale_x = xlim[0] + (scale_ax_x * plot_width)
            scale_y = ylim[0] + (scale_ax_y * plot_height)
            scale_w = scale_ax_w * plot_width
            scale_h = scale_ax_h * plot_height
            
            scale_rect = Rectangle((scale_x, scale_y), scale_w, scale_h,
                                 linewidth=2, edgecolor='black', facecolor='lightblue',
                                 alpha=0.7, linestyle='--', zorder=1000)
            self.ax.add_patch(scale_rect)
            self.ax.text(scale_x + scale_w/2, scale_y + scale_h/2, 'SCALE BAR',
                        ha='center', va='center', fontsize=8, fontweight='bold', zorder=1001)
            
            # North arrow (typically top-left)
            north_ax_x = 0.05
            north_ax_y = 0.85
            north_ax_w = 0.08
            north_ax_h = 0.1
            
            north_x = xlim[0] + (north_ax_x * plot_width)
            north_y = ylim[0] + (north_ax_y * plot_height)
            north_w = north_ax_w * plot_width
            north_h = north_ax_h * plot_height
            
            north_rect = Rectangle((north_x, north_y), north_w, north_h,
                                 linewidth=2, edgecolor='black', facecolor='lightyellow',
                                 alpha=0.7, linestyle='--', zorder=1000)
            self.ax.add_patch(north_rect)
            self.ax.text(north_x + north_w/2, north_y + north_h/2, 'N↑',
                        ha='center', va='center', fontsize=8, fontweight='bold', zorder=1001)
            
        except Exception as e:
            self.parent_app.log_message(f"Error plotting layout elements: {str(e)}")
    
    def update_layer_list(self):
        """Update the layer list display"""
        self.layer_listbox.delete(0, tk.END)
        for layer in self.visible_layers:
            self.layer_listbox.insert(tk.END, layer.name)
    
    def zoom_to_layers(self):
        """Zoom to the extent of all visible layers"""
        if self.visible_layers:
            extent = self.parent_app.calculate_combined_extent(self.visible_layers)
            if extent:
                # Apply buffer
                base_buffer_pct = self.parent_app.buffer_percentage.get() / 100.0
                buffer_x = extent.width * base_buffer_pct
                buffer_y = extent.height * base_buffer_pct
                
                self.current_extent = arcpy.Extent(
                    extent.XMin - buffer_x,
                    extent.YMin - buffer_y,
                    extent.XMax + buffer_x,
                    extent.YMax + buffer_y
                )
                
                self.plot_layers()
                self.plot_layout_elements()
    
    def reset_extent(self):
        """Reset to the original extent"""
        if self.original_extent:
            self.current_extent = self.original_extent
            self.plot_layers()
            self.plot_layout_elements()
    
    def zoom_in(self):
        """Zoom in by 25%"""
        if self.current_extent:
            center_x = (self.current_extent.XMin + self.current_extent.XMax) / 2
            center_y = (self.current_extent.YMin + self.current_extent.YMax) / 2
            
            new_width = self.current_extent.width * 0.75
            new_height = self.current_extent.height * 0.75
            
            self.current_extent = arcpy.Extent(
                center_x - new_width / 2,
                center_y - new_height / 2,
                center_x + new_width / 2,
                center_y + new_height / 2
            )
            
            self.plot_layers()
            self.plot_layout_elements()
    
    def zoom_out(self):
        """Zoom out by 25%"""
        if self.current_extent:
            center_x = (self.current_extent.XMin + self.current_extent.XMax) / 2
            center_y = (self.current_extent.YMin + self.current_extent.YMax) / 2
            
            new_width = self.current_extent.width * 1.25
            new_height = self.current_extent.height * 1.25
            
            self.current_extent = arcpy.Extent(
                center_x - new_width / 2,
                center_y - new_height / 2,
                center_x + new_width / 2,
                center_y + new_height / 2
            )
            
            self.plot_layers()
            self.plot_layout_elements()
    
    def pan_map(self, x_factor, y_factor):
        """Pan the map by the specified factors"""
        if self.current_extent:
            shift_x = self.current_extent.width * x_factor
            shift_y = self.current_extent.height * y_factor
            
            self.current_extent = arcpy.Extent(
                self.current_extent.XMin + shift_x,
                self.current_extent.YMin + shift_y,
                self.current_extent.XMax + shift_x,
                self.current_extent.YMax + shift_y
            )
            
            self.plot_layers()
            self.plot_layout_elements()
    
    def center_on_features(self):
        """Center the view on the feature centroid"""
        if self.visible_layers:
            extent = self.parent_app.calculate_combined_extent(self.visible_layers)
            if extent and self.current_extent:
                feature_center_x = (extent.XMin + extent.XMax) / 2
                feature_center_y = (extent.YMin + extent.YMax) / 2
                
                current_width = self.current_extent.width
                current_height = self.current_extent.height
                
                self.current_extent = arcpy.Extent(
                    feature_center_x - current_width / 2,
                    feature_center_y - current_height / 2,
                    feature_center_x + current_width / 2,
                    feature_center_y + current_height / 2
                )
                
                self.plot_layers()
                self.plot_layout_elements()
    
    def next_dive(self):
        """Process the next dive"""
        try:
            current_dive = self.dive_list[self.current_dive_index]
            
            # Ensure current_dive is an integer for formatting
            if isinstance(current_dive, str):
                current_dive = int(current_dive)
            
            dive_id = f"DIVE{current_dive:03d}"
            
            # Store the current extent for the layout
            self.store_current_extent(dive_id)
            
            # Mark this dive as completed
            self.completed_dives.append(current_dive)
            
            # Move to next dive
            self.current_dive_index += 1
            
            # Load the next dive or complete
            self.load_current_dive()
            
        except Exception as e:
            self.parent_app.log_message(f"Error proceeding to next dive: {str(e)}")
            messagebox.showerror("Error", f"Error proceeding to next dive: {str(e)}")

    def store_current_extent(self, dive_id):
        """Store the current extent in the actual layout"""
        try:
            # Find the map frame in the layout
            map_frame = None
            for mf in self.layout.listElements("MAPFRAME_ELEMENT"):
                map_frame = mf
                break
            
            if map_frame and self.current_extent:
                # Set the extent in the actual layout
                map_frame.camera.setExtent(self.current_extent)
                
                # Update the scale bar based on the new scale
                self.parent_app.adjust_scale_bar_units(self.layout, map_frame, dive_id)
                
                self.parent_app.log_message(f"Stored user-defined extent for {dive_id}")
                self.parent_app.log_message(f"  Extent: {self.current_extent.XMin:.6f}, {self.current_extent.YMin:.6f}, {self.current_extent.XMax:.6f}, {self.current_extent.YMax:.6f}")
            
        except Exception as e:
            self.parent_app.log_message(f"Error storing extent for {dive_id}: {str(e)}")
    
    def complete_process(self):
        """Complete the interactive process"""
        self.parent_app.log_message("Interactive extent control completed!")
        self.status_label.config(text="All dives completed! Close this window to continue.")
        
        # Disable next button
        self.next_button.config(state=tk.DISABLED)
        
        # Update button text
        self.cancel_button.config(text="CLOSE")
        
        # Show completion message
        messagebox.showinfo("Complete", 
                           f"Interactive extent control completed for {len(self.completed_dives)} dives.\n\n"
                           "Close this window to proceed with map generation.")
    
    def cancel_process(self):
        """Cancel the interactive process"""
        if self.completed_dives:
            if not messagebox.askyesno("Cancel", 
                                      f"You have completed {len(self.completed_dives)} dives.\n\n"
                                      "Do you want to cancel the entire process?"):
                return
        
        self.user_cancelled = True
        self.parent_app.log_message("Interactive extent control cancelled by user")
        self.window.destroy()
    
    def get_completed_dives(self):
        """Get the list of completed dives"""
        return self.completed_dives if not self.user_cancelled else []


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
        
        # Extent control with radio buttons - SIMPLIFIED VERSION
        extent_frame = ttk.LabelFrame(main_frame, text="Extent Control", padding="10")
        extent_frame.pack(fill=tk.X, pady=5)

        # Create a variable to track which extent method is selected
        self.extent_method = tk.StringVar(value="smart")  # Default to smart extent

        # Radio button for fixed extent
        ttk.Radiobutton(extent_frame, 
                        text="Simple zoom to layer extent (basic buffering only)", 
                        variable=self.extent_method, 
                        value="fixed").grid(row=0, column=0, sticky=tk.W, pady=5)

        # Radio button for smart extent
        ttk.Radiobutton(extent_frame, 
                        text="Smart extent with adaptive buffering and element avoidance", 
                        variable=self.extent_method, 
                        value="smart").grid(row=1, column=0, sticky=tk.W, pady=5)

        # Radio button for interactive extent
        ttk.Radiobutton(extent_frame, 
                        text="Interactive extent control (manual pan/zoom for each dive)", 
                        variable=self.extent_method, 
                        value="interactive").grid(row=2, column=0, sticky=tk.W, pady=5)

        # Add extent buffer controls
        buffer_frame = ttk.Frame(extent_frame)
        buffer_frame.grid(row=3, column=0, sticky=tk.W, pady=5)

        ttk.Label(buffer_frame, text="Extent buffer (%):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.buffer_percentage = tk.IntVar(value=10)
        ttk.Entry(buffer_frame, textvariable=self.buffer_percentage, width=5).grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5,20))

        # Updated note text
        ttk.Label(extent_frame, text="Note: Smart extent automatically avoids legends, scale bars and inset maps", 
                  foreground="blue", font=("TkDefaultFont", 8)).grid(row=4, column=0, sticky=tk.W, pady=(5,0))

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
        
        # Start processing
        self.status_var.set("Processing...")
        
        # Set up a watchdog timer to detect if processing hangs
        self.last_progress_time = time.time()
        self.processing_active = True
        
        # FIX: For interactive mode, don't use threading due to matplotlib GUI issues
        if self.extent_method.get() == "interactive":
            # Run interactive mode directly in main thread
            self.process_maps_enhanced(selected_groups)
        else:
            # Start the watchdog timer for non-interactive modes
            watchdog_thread = threading.Thread(target=self._monitor_progress)
            watchdog_thread.daemon = True
            watchdog_thread.start()
            
            # Start the actual processing in background thread
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
        """Enhanced processing with interactive mode support"""
        try:
            self.log_message("Starting enhanced map processing...")
            
            layout_name = self.layout_name.get()
            output_folder = self.output_folder.get()
            dpi = self.dpi.get()
            
            # Create output folder if it doesn't exist
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)
                self.log_message(f"Created output folder: {output_folder}")
            
            # Find all dive numbers
            all_dive_numbers = self.collect_dive_numbers(selected_groups)
            
            if not all_dive_numbers:
                self.log_message("No dive layers found in the selected groups")
                self.status_var.set("No dive layers found")
                return
            
            sorted_dives = sorted(all_dive_numbers, key=int)
            total_dives = len(sorted_dives)
            
            # Handle interactive mode differently
            if self.extent_method.get() == "interactive":
                self.log_message(f"Starting interactive extent control for {total_dives} dives...")
                
                # Get the layout
                layout = self.safe_get_layout(layout_name)
                if not layout:
                    self.log_message("Could not access layout for interactive mode")
                    self.status_var.set("Error accessing layout")
                    return
                
                # FIX: Create the interactive controller in the main thread using after_idle
                def create_interactive_controller():
                    try:
                        interactive_controller = InteractiveExtentController(
                            self, layout, sorted_dives, selected_groups
                        )
                        
                        # Wait for the interactive window to complete
                        self.root.wait_window(interactive_controller.window)
                        
                        # Check if user cancelled
                        completed_dives = interactive_controller.get_completed_dives()
                        if not completed_dives:
                            self.log_message("Interactive extent control was cancelled")
                            self.status_var.set("Cancelled")
                            return
                        
                        # Convert completed dive numbers to dive IDs for export
                        dive_ids_to_export = [f"DIVE{dive_num:03d}" if isinstance(dive_num, int) else f"DIVE{int(dive_num):03d}" for dive_num in completed_dives]
                        
                        # Continue with export process
                        self.export_completed_dives(dive_ids_to_export, selected_groups, layout_name, output_folder, dpi)
                        
                    except Exception as e:
                        self.log_message(f"Error in interactive controller: {str(e)}")
                        self.status_var.set("Error")
                
                # Schedule the controller creation in the main thread
                self.root.after_idle(create_interactive_controller)
                return
                
            else:
                # Regular processing for fixed and smart modes
                dive_ids_to_export = [f"DIVE{dive_num:03d}" if isinstance(dive_num, int) else f"DIVE{int(dive_num):03d}" for dive_num in sorted_dives]
                self.export_completed_dives(dive_ids_to_export, selected_groups, layout_name, output_folder, dpi)
            
        except Exception as e:
            error_message = f"Error processing maps: {str(e)}"
            self.log_message(error_message)
            self.status_var.set("Error")
            messagebox.showerror("Error", error_message)
            self.processing_active = False

    def export_completed_dives(self, dive_ids_to_export, selected_groups, layout_name, output_folder, dpi):
        """Export the completed dives"""
        try:
            # Now export all the completed dives
            self.log_message(f"Exporting {len(dive_ids_to_export)} completed dives...")
            
            # Pre-collect all layers to minimize repeated searches
            all_dive_layers = self.pre_collect_dive_layers(selected_groups)
            
            # Process each dive for export
            for i, dive_id in enumerate(dive_ids_to_export, 1):
                self.log_message(f"\n[{i}/{len(dive_ids_to_export)}] *** Exporting {dive_id} ***")
                
                progress_pct = int((i / len(dive_ids_to_export)) * 100)
                self.status_var.set(f"Exporting {dive_id} ({i}/{len(dive_ids_to_export)}) - {progress_pct}% complete")
                
                try:
                    # For interactive mode, we only need to export (extent is already set)
                    # For other modes, we need to do the full processing
                    if self.extent_method.get() == "interactive":
                        # Just export - extent was set during interactive phase
                        layout = self.safe_get_layout(layout_name)
                        if layout:
                            output_file = os.path.join(output_folder, f"{dive_id}.jpg")
                            success = self.safe_export_layout(layout, output_file, dpi, dive_id)
                            if success:
                                self.log_message(f"*** Exported {dive_id} successfully ***")
                            else:
                                self.log_message(f"*** Export failed for {dive_id} ***")
                    else:
                        # Regular processing
                        success = self.process_single_dive_enhanced(dive_id, all_dive_layers, layout_name, output_folder, dpi)
                        if success:
                            self.log_message(f"*** Completed {dive_id} successfully ***")
                        else:
                            self.log_message(f"*** {dive_id} completed with issues ***")
                        
                except Exception as e:
                    self.log_message(f"*** Error processing {dive_id}: {str(e)} ***")
            
                # Update GUI
                self.root.update()
            
            self.processing_active = False
            self.log_message("\nProcessing complete!")
            self.status_var.set("Processing complete")
            messagebox.showinfo("Success", f"Generated {len(dive_ids_to_export)} maps in {output_folder}")
            
        except Exception as e:
            error_message = f"Error exporting maps: {str(e)}"
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
        """Smart zoom to active layers with adaptive buffering and element avoidance"""
    
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
    
        self.log_message(f"  SMART EXTENT: Getting extent from all visible layers in {len(selected_groups)} selected groups")
        visible_layers = self.get_visible_layers_for_dive(selected_groups, dive_id)

        if not visible_layers:
            self.log_message(f"  No visible layers with valid extents found for {dive_id}")
            return
    
        # Calculate combined extent from ALL visible layers
        extent = self.calculate_combined_extent(visible_layers)
    
        if not extent or extent.width <= 0 or extent.height <= 0:
            self.log_message(f"  Could not calculate valid extent for {dive_id}")
            return

        # SMART EXTENT: Apply adaptive buffering and element avoidance
        self.log_message("  Using smart extent with adaptive buffering and automatic element avoidance")
    
        # Adaptive buffering based on feature size
        base_width = extent.width
        base_height = extent.height
    
        self.log_message(f"  Raw extent size: {base_width:.6f} x {base_height:.6f} units")
    
        # Calculate appropriate buffer based on feature dimensions
        buffer_multiplier, shift_reduction_factor = self.get_adaptive_buffer_params(base_width, base_height)
    
        # Apply the adaptive buffer
        base_buffer_pct = self.buffer_percentage.get() / 100.0
        adaptive_buffer_pct = base_buffer_pct * buffer_multiplier
    
        # Create initial buffered extent
        buffer_x = extent.width * adaptive_buffer_pct
        buffer_y = extent.height * adaptive_buffer_pct
    
        # Ensure minimum buffer size
        min_buffer = 0.002
        buffer_x = max(buffer_x, min_buffer)
        buffer_y = max(buffer_y, min_buffer)
    
        buffered_extent = arcpy.Extent(
            extent.XMin - buffer_x,
            extent.YMin - buffer_y,
            extent.XMax + buffer_x,
            extent.YMax + buffer_y
        )
    
        self.log_message(f"  Applied adaptive buffer: {buffer_x:.4f} x {buffer_y:.4f} units (multiplier: {buffer_multiplier:.1f})")
    
        # ALWAYS apply smart element avoidance for smart extent
        final_extent = self.apply_smart_element_avoidance(layout, map_frame, buffered_extent, shift_reduction_factor)
    
        # Set the final extent
        try:
            map_frame.camera.setExtent(final_extent)
        
            # Automatically adjust scale bar units based on new scale
            self.adjust_scale_bar_units(layout, map_frame, dive_id)
        
            self.log_message(f"  Successfully set smart adaptive extent for {dive_id} using {len(visible_layers)} layers")
        
        except Exception as e:
            self.log_message(f"  Error setting extent: {str(e)}")
            # Try fallback method
            try:
                self.log_message("  Attempting fallback zoom to extent")
                map_frame.camera = final_extent
            
                # Also try scale bar adjustment in fallback
                self.adjust_scale_bar_units(layout, map_frame, dive_id)
            
                self.log_message("  Fallback zoom successful")
            except Exception as alt_e:
                self.log_message(f"  Fallback zoom also failed: {str(alt_e)}")

    def zoom_to_fixed_extent(self, layout, active_map_obj, dive_id):
        """Simple fixed extent zoom with basic buffering"""
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
    
        self.log_message(f"  FIXED EXTENT: Getting extent from all visible layers in {len(selected_groups)} selected groups")
        visible_layers = self.get_visible_layers_for_dive(selected_groups, dive_id)

        if not visible_layers:
            self.log_message(f"  No visible layers with valid extents found for {dive_id}")
            return
    
        # Calculate combined extent from ALL visible layers
        extent = self.calculate_combined_extent(visible_layers)
    
        if not extent or extent.width <= 0 or extent.height <= 0:
            self.log_message(f"  Could not calculate valid extent for {dive_id}")
            return
        
        # Apply a basic buffer
        self.log_message("  Applying basic buffering to extent")
        base_buffer_pct = self.buffer_percentage.get() / 100.0
        buffer_x = extent.width * base_buffer_pct
        buffer_y = extent.height * base_buffer_pct
        
        # Ensure minimum buffer size
        min_buffer = 0.002
        buffer_x = max(buffer_x, min_buffer)
        buffer_y = max(buffer_y, min_buffer)
        
        buffered_extent = arcpy.Extent(
            extent.XMin - buffer_x,
            extent.YMin - buffer_y,
            extent.XMax + buffer_x,
            extent.YMax + buffer_y
        )
        
        # Set the extent
        try:
            map_frame.camera.setExtent(buffered_extent)
            
            # Automatically adjust scale bar units based on new scale
            self.adjust_scale_bar_units(layout, map_frame, dive_id)
            
            self.log_message(f"  Successfully set fixed extent for {dive_id}")
            
        except Exception as e:
            self.log_message(f"  Error setting extent: {str(e)}")
            # Try fallback method
            try:
                self.log_message("  Attempting fallback zoom to extent")
                map_frame.camera = buffered_extent
            
                # Also try scale bar adjustment in fallback
                self.adjust_scale_bar_units(layout, map_frame, dive_id)
            
                self.log_message("  Fallback zoom successful")
            except Exception as alt_e:
                self.log_message(f"  Fallback zoom also failed: {str(alt_e)}")
    
    def apply_smart_element_avoidance(self, layout, map_frame, extent, shift_reduction_factor):
        """Apply smart element avoidance to a given extent"""
        try:
            # Get all elements in the layout
            elements = layout.listElements()
            
            # Separate out the map frame for this specific map
            map_frames = [mf for mf in elements if mf.type == "MAPFRAME_ELEMENT" and mf.map.name == map_frame.map.name]
            other_elements = [el for el in elements if el not in map_frames]
            
            # Calculate the initial shift amounts
            x_shift = extent.width * 0.1  # 10% of width
            y_shift = extent.height * 0.1  # 10% of height
            
            # Reduce shifts if specified
            if shift_reduction_factor > 0:
                x_shift /= shift_reduction_factor
                y_shift /= shift_reduction_factor
            
            # Apply shifts to the extent
            new_x_min = extent.XMin + x_shift
            new_y_min = extent.YMin + y_shift
            new_x_max = extent.XMax - x_shift
            new_y_max = extent.YMax - y_shift
            
            avoided_extent = arcpy.Extent(new_x_min, new_y_min, new_x_max, new_y_max)
            
            self.log_message(f"  Avoided extent: {avoided_extent}")
            
            return avoided_extent
        
        except Exception as e:
            self.log_message(f"  Error applying smart element avoidance: {str(e)}")
            return extent  # Fallback to original extent

    def get_adaptive_buffer_params(self, width, height):
        """Determine adaptive buffer parameters based on feature size"""
        try:
            # Base buffer multiplier - this can be tuned
            base_multiplier = 1.5
            
            # Reduce the multiplier for very large features to avoid excessive buffering
            max_dimension = max(width, height)
            if max_dimension > 1000:
                reduction_factor = max_dimension / 1000
                buffer_multiplier = base_multiplier / reduction_factor
            else:
                buffer_multiplier = base_multiplier
            
            # Shift reduction factor - how much to reduce the shift for element avoidance
            shift_reduction_factor = 2.0  # Default to 2x reduction
            
            return buffer_multiplier, shift_reduction_factor
        
        except Exception as e:
            self.log_message(f"  Error determining adaptive buffer params: {str(e)}")
            return 1.5, 2.0  # Default values

    def manual_refresh_project(self):
        """Manually refresh the project - useful if processing gets stuck"""
        try:
            self.log_message("Manually refreshing project...")
            
            if self.refresh_project_connection():
                self.populate_layout_dropdown()
                self.populate_layer_groups()
                self.log_message("Project refreshed successfully")
                messagebox.showinfo("Success", "Project refreshed successfully")
            else:
                self.log_message("Project refresh failed")
                messagebox.showwarning("Warning", "Project refresh failed - see log for details")
                
        except Exception as e:
            error_msg = f"Error during manual refresh: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("Error", error_msg)

    def safe_get_layout(self, layout_name):
        """Safely get a layout with retry logic"""
        def get_layout():
            layouts = list(self.project.listLayouts())
            for layout in layouts:
                if layout.name == layout_name:
                    return layout
            return None
        
        try:
            return self.safe_layer_operation(get_layout)
        except Exception as e:
            self.log_message(f"Error getting layout {layout_name}: {str(e)}")
            return None

    def safe_export_layout(self, layout, output_file, dpi, dive_id):
        """Safely export a layout with retry logic"""
        def export_layout():
            layout.exportToJPEG(output_file, resolution=dpi, jpeg_quality=95)
            return True
        
        try:
            self.safe_layer_operation(export_layout)
            return True
        except Exception as e:
            self.log_message(f"Error exporting {dive_id}: {str(e)}")
            return False

    def adjust_scale_bar_units(self, layout, map_frame, dive_id):
        """Adjust scale bar units based on map scale"""
        try:
            scale_bars = layout.listElements("MAPSURROUND_ELEMENT", "Scale Bar*")
            
            if not scale_bars:
                return
            
            current_scale = map_frame.camera.scale
            
            for scale_bar in scale_bars:
                if hasattr(scale_bar, 'units'):
                    if current_scale > 50000:  # Large scale
                        scale_bar.units = "Kilometers"
                    else:  # Small scale
                        scale_bar.units = "Meters"
                        
        except Exception as e:
            self.log_message(f"  Could not adjust scale bar for {dive_id}: {str(e)}")

    def process_single_dive_enhanced(self, dive_id, all_dive_layers, layout_name, output_folder, dpi):
        """Process a single dive with enhanced error handling"""
        try:
            # Prepare layer visibility changes
            layers_to_hide = []
            layers_to_show = []
            
            for layer_info in all_dive_layers:
                layer = layer_info['layer']
                if dive_id.upper() in layer.name.upper():
                    layers_to_show.append((layer, True))
                else:
                    layers_to_hide.append((layer, False))
            
            # Hide other dive layers first
            if layers_to_hide:
                self.batch_set_layer_visibility(layers_to_hide, dive_id)
            
            # Show target dive layers
            if layers_to_show:
                self.batch_set_layer_visibility(layers_to_show, dive_id)
            
            # Get the layout
            layout = self.safe_get_layout(layout_name)
            if not layout:
                self.log_message(f"  Layout {layout_name} not found")
                return False
            
            # Find the main map
            maps = list(self.project.listMaps())
            if not maps:
                self.log_message("  No maps found in project")
                return False
            
            active_map_obj = maps[0]  # Use first map
            
            # Set the extent based on method
            if self.extent_method.get() == "smart":
                self.zoom_to_active_layers(layout, active_map_obj, dive_id)
            else:  # fixed
                self.zoom_to_fixed_extent(layout, active_map_obj, dive_id)
            
            # Export the layout
            output_file = os.path.join(output_folder, f"{dive_id}.jpg")
            success = self.safe_export_layout(layout, output_file, dpi, dive_id)
            
            return success
            
        except Exception as e:
            self.log_message(f"  Error processing {dive_id}: {str(e)}")
            return False

    def get_visible_layers_for_dive(self, selected_groups, dive_id):
        """Get all visible layers for a specific dive from selected groups"""
        visible_layers = []
        
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
            
            # Get all layers from this group that are currently visible
            for layer in group_layer.listLayers():
                try:
                    # Check if layer is visible and has valid data
                    if hasattr(layer, 'visible') and layer.visible:
                        # For dive-specific layers, check if it matches the current dive
                        if self.dive_pattern.search(layer.name):
                            if dive_id.upper() in layer.name.upper():
                                visible_layers.append(layer)
                        else:
                            # Non-dive layers that are visible should be included
                            visible_layers.append(layer)
                except Exception as e:
                    self.log_message(f"  Error checking layer {layer.name}: {str(e)}")
        
        return visible_layers

    def calculate_combined_extent(self, layers):
        """Calculate the combined extent of multiple layers"""
        try:
            if not layers:
                return None
            
            all_extents = []
            
            for layer in layers:
                try:
                    # Get layer extent
                    desc = arcpy.Describe(layer)
                    layer_extent = desc.extent;
                    
                    # Check if extent is valid
                    if (layer_extent.width > 0 and layer_extent.height > 0 and
                        layer_extent.XMin != layer_extent.XMax and 
                        layer_extent.YMin != layer_extent.YMax):
                        all_extents.append(layer_extent)
                        
                except Exception as e:
                    self.log_message(f"  Could not get extent for layer {layer.name}: {str(e)}")
            
            if not all_extents:
                self.log_message("  No valid extents found")
                return None
            
            # Calculate combined extent
            min_x = min(ext.XMin for ext in all_extents)
            min_y = min(ext.YMin for ext in all_extents)
            max_x = max(ext.XMax for ext in all_extents)
            max_y = max(ext.YMax for ext in all_extents)
            
            combined_extent = arcpy.Extent(min_x, min_y, max_x, max_y)
            
            self.log_message(f"  Combined extent from {len(all_extents)} layers: "
                            f"({min_x:.6f}, {min_y:.6f}) to ({max_x:.6f}, {max_y:.6f})")
            
            return combined_extent
            
        except Exception as e:
            self.log_message(f"Error calculating combined extent: {str(e)}")
            return None
# Main execution - THIS IS THE CRITICAL PART THAT KEEPS GETTING REMOVED:
if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = LayoutAutomatorApp(root)
        root.mainloop()
    except Exception as e:
        print(f"Error starting application: {str(e)}")
        import traceback
        traceback.print_exc()
