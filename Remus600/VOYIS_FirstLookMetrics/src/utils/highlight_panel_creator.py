"""
Highlight Panel Creator

A standalone utility that creates highlight panels with 2, 4, or 6 images.
This tool extracts EXIF data from images to display coordinates and altitude,
and arranges selected images in a grid with annotations.
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, ttk
from tkinter.font import Font
import traceback
import re
from typing import List, Dict, Optional, Union, Tuple
from PIL import Image, ExifTags
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

# Define the GPSTAGS dictionary for EXIF data extraction
GPSTAGS = {
    0: "GPSVersionID",
    1: "GPSLatitudeRef",
    2: "GPSLatitude",
    3: "GPSLongitudeRef",
    4: "GPSLongitude",
    5: "GPSAltitudeRef",
    6: "GPSAltitude"
}

class HighlightPanelCreator:
    def __init__(self, root):
        self.root = root
        self.root.title("Highlight Panel Creator")
        self.root.geometry("1000x800")
        
        self.setup_variables()
        self.create_widgets()
        self.layout_widgets()
        self.bind_events()
    
    def setup_variables(self):
        """Initialize variables needed by the application"""
        self.selected_images = []
        self.panel_layout = tk.IntVar(value=4)  # Default to 4 images (2x2 grid)
        self.output_folder = os.path.expanduser("~\\Documents")
        self.preview_figure = None
        self.preview_canvas = None
    
    def create_widgets(self):
        """Create the GUI widgets"""
        # Create a custom style
        style = ttk.Style()
        style.configure("TButton", padding=6, relief="flat")
        style.configure("Header.TLabel", font=('Helvetica', 12, 'bold'))
        
        # Main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        
        # Layout selection
        self.layout_frame = ttk.LabelFrame(self.main_frame, text="Panel Layout", padding="5")
        self.layout_2_radio = ttk.Radiobutton(self.layout_frame, text="2 Images (1×2)", variable=self.panel_layout, value=2)
        self.layout_4_radio = ttk.Radiobutton(self.layout_frame, text="4 Images (2×2)", variable=self.panel_layout, value=4)
        self.layout_6_radio = ttk.Radiobutton(self.layout_frame, text="6 Images (2×3)", variable=self.panel_layout, value=6)
        
        # Image selection
        self.images_frame = ttk.LabelFrame(self.main_frame, text="Selected Images", padding="5")
        self.images_listbox = tk.Listbox(self.images_frame, width=70, height=8, selectmode=tk.MULTIPLE)
        self.images_scrollbar = ttk.Scrollbar(self.images_frame, orient=tk.VERTICAL, command=self.images_listbox.yview)
        self.images_listbox.configure(yscrollcommand=self.images_scrollbar.set)
        
        # Buttons for image management
        self.button_frame = ttk.Frame(self.images_frame)
        self.add_button = ttk.Button(self.button_frame, text="Add Images", command=self.add_images)
        self.remove_button = ttk.Button(self.button_frame, text="Remove Selected", command=self.remove_images)
        self.clear_button = ttk.Button(self.button_frame, text="Clear All", command=self.clear_images)
        
        # Preview frame
        self.preview_frame = ttk.LabelFrame(self.main_frame, text="Preview", padding="5")
        
        # Create a frame that will contain the matplotlib canvas
        self.figure_frame = ttk.Frame(self.preview_frame)
        
        # Actions frame
        self.actions_frame = ttk.Frame(self.main_frame)
        self.output_label = ttk.Label(self.actions_frame, text="Output folder: " + self.output_folder, wraplength=600)
        self.change_output_button = ttk.Button(self.actions_frame, text="Change Output Folder", command=self.change_output_folder)
        self.save_button = ttk.Button(self.actions_frame, text="Save Panel", command=self.save_panel)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        self.statusbar = ttk.Label(self.main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
    
    def layout_widgets(self):
        """Arrange widgets in the layout"""
        # Configure grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E, tk.S))
        
        # Layout selection
        self.layout_frame.grid(column=0, row=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        self.layout_2_radio.grid(column=0, row=0, sticky=tk.W, padx=5, pady=2)
        self.layout_4_radio.grid(column=1, row=0, sticky=tk.W, padx=5, pady=2)
        self.layout_6_radio.grid(column=2, row=0, sticky=tk.W, padx=5, pady=2)
        
        # Image selection
        self.images_frame.grid(column=0, row=1, sticky=(tk.N, tk.W, tk.E, tk.S), padx=5, pady=5)
        self.images_listbox.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E, tk.S))
        self.images_scrollbar.grid(column=1, row=0, sticky=(tk.N, tk.S))
        
        # Buttons for image management
        self.button_frame.grid(column=0, row=1, columnspan=2, sticky=(tk.W, tk.E))
        self.add_button.pack(side=tk.LEFT, padx=5, pady=5)
        self.remove_button.pack(side=tk.LEFT, padx=5, pady=5)
        self.clear_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Preview Frame
        self.preview_frame.grid(column=0, row=2, sticky=(tk.N, tk.W, tk.E, tk.S), padx=5, pady=5)
        self.figure_frame.pack(fill=tk.BOTH, expand=True)
        
        # Actions frame
        self.actions_frame.grid(column=0, row=3, sticky=(tk.W, tk.E), padx=5, pady=5)
        self.output_label.grid(column=0, row=0, sticky=tk.W)
        self.change_output_button.grid(column=1, row=0, sticky=tk.E, padx=5)
        self.save_button.grid(column=2, row=0, sticky=tk.E, padx=5)
        
        # Status bar
        self.statusbar.grid(column=0, row=4, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # Configure weights
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(2, weight=1)  # Make preview expandable
        self.images_frame.columnconfigure(0, weight=1)
        self.images_frame.rowconfigure(0, weight=1)
    
    def bind_events(self):
        """Bind events to widgets"""
        self.panel_layout.trace_add("write", self.update_preview)
        self.images_listbox.bind("<Delete>", lambda e: self.remove_images())
        
        # Set up drag and drop
        self.images_listbox.drop_target_register("DND_Files")
        self.images_listbox.dnd_bind("<<Drop>>", self.handle_drop)
    
    def handle_drop(self, event):
        """Handle drag and drop of files"""
        try:
            # Get the dropped data
            data = event.data
            
            # Parse the data which will be in the format: {file1} {file2} ...
            files = re.findall(r'{([^}]+)}', data)
            
            # If no files matched the pattern, try without braces
            if not files:
                files = data.split()
            
            # Process each file
            valid_files = []
            for file in files:
                if os.path.isfile(file) and file.lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff')):
                    valid_files.append(file)
            
            # Add valid files
            if valid_files:
                self.add_images_to_list(valid_files)
                self.update_preview()
            
            return "break"  # Prevent default handling
        except Exception as e:
            self.status_var.set(f"Error handling dropped files: {str(e)}")
    
    def add_images(self):
        """Add images using file dialog"""
        files = filedialog.askopenfilenames(
            title="Select Images",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.tif *.tiff"),
                ("All files", "*.*")
            ]
        )
        
        if files:
            self.add_images_to_list(files)
            self.update_preview()
    
    def add_images_to_list(self, files):
        """Add images to the listbox and selected_images list"""
        for file in files:
            # Check if already added
            if file not in self.selected_images:
                self.selected_images.append(file)
                # Display only the filename, not the full path
                self.images_listbox.insert(tk.END, os.path.basename(file))
        
        # Update the status
        self.status_var.set(f"{len(self.selected_images)} images selected")
    
    def remove_images(self):
        """Remove selected images from the list"""
        selected_indices = self.images_listbox.curselection()
        
        # Remove in reverse order to avoid index shifting issues
        for i in sorted(selected_indices, reverse=True):
            del self.selected_images[i]
            self.images_listbox.delete(i)
        
        # Update the preview
        self.update_preview()
        
        # Update the status
        self.status_var.set(f"{len(self.selected_images)} images selected")
    
    def clear_images(self):
        """Clear all images from the list"""
        self.selected_images.clear()
        self.images_listbox.delete(0, tk.END)
        self.update_preview()
        self.status_var.set("All images cleared")
    
    def change_output_folder(self):
        """Change the output folder"""
        folder = filedialog.askdirectory(
            title="Select Output Folder",
            initialdir=self.output_folder
        )
        
        if folder:
            self.output_folder = folder
            self.output_label.config(text="Output folder: " + self.output_folder)
    
    def dms_to_dd(self, degrees, minutes, seconds, direction):
        """
        Convert coordinates from Degrees, Minutes, Seconds (DMS) to Decimal Degrees (DD)
        
        Args:
            degrees: Degrees value
            minutes: Minutes value
            seconds: Seconds value
            direction: Direction (N, S, E, W)
            
        Returns:
            Decimal degrees
        """
        dd = float(degrees) + float(minutes)/60 + float(seconds)/3600
        if direction in ['S', 'W', 's', 'w']:
            dd *= -1
        return dd
    
    def extract_gps_data(self, img_path):
        """
        Extract GPS data from image EXIF
        
        Args:
            img_path: Path to the image
            
        Returns:
            Dictionary with latitude, longitude, altitude or None if not available
        """
        try:
            with Image.open(img_path) as img:
                exif_data = img._getexif()
                if exif_data is None:
                    return None
                
                gps_info = {}
                for tag, value in exif_data.items():
                    tag_name = ExifTags.TAGS.get(tag, tag)
                    if tag_name == 'GPSInfo':
                        for gps_tag, gps_value in value.items():
                            gps_info[GPSTAGS.get(gps_tag, gps_tag)] = gps_value
                
                if not gps_info:
                    return None
                    
                result = {}
                
                # Handle Latitude
                if 'GPSLatitude' in gps_info and 'GPSLatitudeRef' in gps_info:
                    try:
                        lat_dms = gps_info['GPSLatitude']
                        lat_ref = gps_info['GPSLatitudeRef']
                        
                        # Check if we have a tuple/list of components (DMS format)
                        if isinstance(lat_dms, tuple) and len(lat_dms) == 3:
                            # Convert each component (which might be a fraction) to float
                            lat_d = float(lat_dms[0].numerator) / float(lat_dms[0].denominator) if hasattr(lat_dms[0], 'numerator') else float(lat_dms[0])
                            lat_m = float(lat_dms[1].numerator) / float(lat_dms[1].denominator) if hasattr(lat_dms[1], 'numerator') else float(lat_dms[1])
                            lat_s = float(lat_dms[2].numerator) / float(lat_dms[2].denominator) if hasattr(lat_dms[2], 'numerator') else float(lat_dms[2])
                            
                            # Convert to decimal degrees
                            latitude = self.dms_to_dd(lat_d, lat_m, lat_s, lat_ref)
                            result['latitude'] = latitude
                        else:
                            # Already in decimal degrees
                            result['latitude'] = float(lat_dms)
                    except (ValueError, TypeError, ZeroDivisionError) as e:
                        print(f"Error parsing latitude: {e}, value: {gps_info['GPSLatitude']}")
                
                # Handle Longitude
                if 'GPSLongitude' in gps_info and 'GPSLongitudeRef' in gps_info:
                    try:
                        lon_dms = gps_info['GPSLongitude']
                        lon_ref = gps_info['GPSLongitudeRef']
                        
                        # Check if we have a tuple/list of components (DMS format)
                        if isinstance(lon_dms, tuple) and len(lon_dms) == 3:
                            # Convert each component (which might be a fraction) to float
                            lon_d = float(lon_dms[0].numerator) / float(lon_dms[0].denominator) if hasattr(lon_dms[0], 'numerator') else float(lon_dms[0])
                            lon_m = float(lon_dms[1].numerator) / float(lon_dms[1].denominator) if hasattr(lon_dms[1], 'numerator') else float(lon_dms[1])
                            lon_s = float(lon_dms[2].numerator) / float(lon_dms[2].denominator) if hasattr(lon_dms[2], 'numerator') else float(lon_dms[2])
                            
                            # Convert to decimal degrees
                            longitude = self.dms_to_dd(lon_d, lon_m, lon_s, lon_ref)
                            result['longitude'] = longitude
                        else:
                            # Already in decimal degrees
                            result['longitude'] = float(lon_dms)
                    except (ValueError, TypeError, ZeroDivisionError) as e:
                        print(f"Error parsing longitude: {e}, value: {gps_info['GPSLongitude']}")
                
                # Handle Altitude
                if 'GPSAltitude' in gps_info:
                    try:
                        if hasattr(gps_info['GPSAltitude'], 'numerator'):
                            altitude = float(gps_info['GPSAltitude'].numerator) / float(gps_info['GPSAltitude'].denominator)
                        else:
                            altitude = float(gps_info['GPSAltitude'])
                            
                        if 'GPSAltitudeRef' in gps_info and gps_info['GPSAltitudeRef'] == 1:
                            altitude = -altitude
                        
                        result['altitude'] = altitude
                    except (ValueError, TypeError, ZeroDivisionError) as e:
                        print(f"Error parsing altitude: {e}, value: {gps_info['GPSAltitude']}")
                
                # If we found any GPS data, return it
                if result:
                    return result
                return None
                
        except Exception as e:
            print(f"Error extracting GPS data from {img_path}: {e}")
            return None
    
    def update_preview(self, *args):
        """Update the preview with the currently selected images"""
        # Clear existing figure
        for widget in self.figure_frame.winfo_children():
            widget.destroy()
        
        if not self.selected_images:
            self.status_var.set("No images selected for preview")
            return
        
        # Get the number of images to display based on layout
        layout = self.panel_layout.get()
        
        # Determine the grid configuration
        if layout == 2:
            rows, cols = 1, 2
        elif layout == 4:
            rows, cols = 2, 2
        elif layout == 6:
            rows, cols = 2, 3
        
        try:
            # Create figure with proper aspect ratio
            fig = plt.figure(figsize=(10, 8 if rows == 2 else 4))
            
            # Use tight layout and reduce spacing between subplots
            gs = gridspec.GridSpec(rows, cols, figure=fig, hspace=0.1, wspace=0.1)
            
            # Add each image to the grid
            for i, img_path in enumerate(self.selected_images):
                if i >= layout:
                    break
                    
                # Calculate grid position
                row_idx = i // cols
                col_idx = i % cols
                
                # Create subplot
                ax = fig.add_subplot(gs[row_idx, col_idx])
                
                try:
                    # Read and display image
                    img = plt.imread(img_path)
                    ax.imshow(img)
                    
                    # Use only filename without extension as title
                    filename = os.path.basename(img_path)
                    title = f"{os.path.splitext(filename)[0]}"
                    ax.set_title(title, fontsize=8, pad=2)  # Reduced padding
                    
                    # Get GPS data from image
                    gps_data = self.extract_gps_data(img_path)
                    
                    # Format text with coordinates and altitude
                    if gps_data and 'latitude' in gps_data and 'longitude' in gps_data:
                        text = f"Lat: {gps_data['latitude']:.6f}\nLon: {gps_data['longitude']:.6f}"
                        
                        if 'altitude' in gps_data:
                            text += f"\nAlt: {gps_data['altitude']:.2f}m"
                            
                        # Add text at bottom of the image
                        ax.text(0.03, 0.03, text,
                                transform=ax.transAxes,
                                fontsize=7,
                                color='white',
                                horizontalalignment='left',
                                verticalalignment='bottom', 
                                bbox=dict(boxstyle='round,pad=0.3', 
                                          facecolor='black', 
                                          alpha=0.7))
                        
                except Exception as e:
                    print(f"Error adding image to panel: {e}")
                    ax.text(0.5, 0.5, f"Error loading image:\n{filename}", 
                            ha='center', va='center')
                
                # Turn off axis labels
                ax.set_xticks([])
                ax.set_yticks([])
            
            # Create the canvas and add it to the frame
            canvas = FigureCanvasTkAgg(fig, master=self.figure_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Save references to figure and canvas
            self.preview_figure = fig
            self.preview_canvas = canvas
            
            self.status_var.set("Preview updated")
            
        except Exception as e:
            self.status_var.set(f"Error creating preview: {str(e)}")
            traceback.print_exc()
    
    def save_panel(self):
        """Save the current panel to a file"""
        if not self.selected_images:
            self.status_var.set("No images selected to save")
            return
        
        if not self.preview_figure:
            self.status_var.set("Preview not generated, cannot save")
            return
        
        try:
            # Create output filename
            output_filename = os.path.join(self.output_folder, "highlight_panel.png")
            
            # Let the user choose the filename
            save_path = filedialog.asksaveasfilename(
                initialdir=self.output_folder,
                initialfile="highlight_panel.png",
                defaultextension=".png",
                filetypes=[
                    ("PNG files", "*.png"),
                    ("JPEG files", "*.jpg"),
                    ("PDF files", "*.pdf"),
                    ("All files", "*.*")
                ]
            )
            
            if not save_path:
                return  # User canceled
            
            # Save the figure
            self.preview_figure.savefig(save_path, dpi=300, bbox_inches='tight')
            
            self.status_var.set(f"Panel saved to: {save_path}")
            
        except Exception as e:
            self.status_var.set(f"Error saving panel: {str(e)}")
            traceback.print_exc()

# Initialize drag and drop for the Tkinter interface
def add_drag_and_drop_support(tk):
    """Add drag and drop support for Tkinter"""
    # Define drag and drop functionality based on OS
    import sys
    if sys.platform == 'win32':
        # For Windows, use TkDND
        try:
            # Try to import and initialize TkDND
            from tkinterdnd2 import TkinterDnD, DND_FILES
            
            # Initialize for the tkinter module
            if not hasattr(tk, 'drop_target_register'):
                TkinterDnD.DnDWrapper.attach_tkinter_dnd(tk)
                
        except ImportError:
            print("TkinterDnD2 not installed. Drag and drop will be disabled.")
            
            # Create dummy methods
            def dummy(*args, **kwargs):
                pass
            
            tk.Listbox.drop_target_register = dummy
            tk.Listbox.dnd_bind = dummy
    else:
        # For other platforms, add dummy methods for now
        # Can be extended with platform-specific implementations
        def dummy(*args, **kwargs):
            pass
        
        tk.Listbox.drop_target_register = dummy
        tk.Listbox.dnd_bind = dummy

def main():
    # Set up exception handling
    def handle_exception(exc_type, exc_value, exc_traceback):
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        print(f"Unhandled exception: {error_msg}")
    
    # Set the exception handler
    sys.excepthook = handle_exception
    
    # Create the main window
    root = tk.Tk()
    
    try:
        # Add drag and drop support
        add_drag_and_drop_support(tk)
        
        # Create the application
        app = HighlightPanelCreator(root)
        
        # Start the main loop
        root.mainloop()
    except Exception as e:
        print(f"Error starting application: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main()