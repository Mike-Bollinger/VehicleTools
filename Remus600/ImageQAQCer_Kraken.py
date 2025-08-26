"""
Title: Synthetic Aperture Sonar Image QAQC Application with GeoTIFF Metadata Display
Author: Mike Bollinger with contributions from CoPilot
Date: 2025-08-26
Version: 2.0

Description:
This is a synthetic aperture sonar image QAQC application for reviewing SAS 
GeoTIFF images from a selected folder, extracts geospatial metadata, and displays relevant 
fields in a sidebar along with a plot of image bounding boxes (latitude/longitude).
The sidebar includes fields such as coordinate system, bounds, pixel size, and creation date.
Users can navigate through the images with play, pause, forward, and backward controls.

The application includes a slider to manually navigate between images, and it plots the GPS 
bounding boxes on a matplotlib plot.
"""
import os
import tkinter as tk
import math
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Rectangle
import gc

try:
    import rasterio
    from rasterio.crs import CRS
    from rasterio.warp import transform_bounds
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False
    print("Warning: rasterio not available. GeoTIFF functionality will be limited.")

try:
    from osgeo import gdal
    GDAL_AVAILABLE = True
except ImportError:
    GDAL_AVAILABLE = False
    print("Warning: GDAL not available. Using fallback methods for GeoTIFF reading.")

ImageX = 900  # Monitor = 1100, Laptop = 900
ImageY = 750  # Monitor = 750


class SASImageSlideshow(tk.Tk):
    def __init__(self, slideshow_interval=0.1):
        super().__init__()
        self.title("SAS Image QAQCer")
        
        # Set window icon to camera emoji
        self.set_camera_icon()
        
        self.slideshow_interval = slideshow_interval
        self.base_thumbnail_size = (ImageX, ImageY)  # Base size for reference
        self.thumbnail_size = (ImageX, ImageY)  # Current size (will be dynamic)

        self.image_files = []
        self.current_index = 0
        self.is_playing = False
        self.slideshow_id = None
        self.bounding_boxes = []  # Store bounding boxes instead of point locations
        
        # Performance optimizations
        self.image_cache = {}  # Cache for thumbnails
        self.metadata_cache = {}   # Cache for GeoTIFF metadata
        self.cache_size_limit = 50  # Limit cache to prevent memory issues
        self.fig = None  # Reuse single figure
        self.ax = None
        self.canvas = None
        
        # Track the original image for resizing
        self.current_image_path = None
        self.current_original_image = None
        
        # Store current image transform for coordinate calculations
        self.current_transform = None
        self.current_crs = None

        # Create a frame for the image and the side panel (text + plot)
        self.display_frame = tk.Frame(self)
        self.display_frame.pack(fill=tk.BOTH, expand=True)

        # Create the image label (left side)
        self.image_label = tk.Label(self.display_frame)
        self.image_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Bind mouse motion to image label for coordinate display
        self.image_label.bind('<Motion>', self.on_mouse_motion)

        # Coordinate display label (shows lat/lon when hovering)
        self.coord_label = tk.Label(self, text="", font=("Arial", 10), fg="blue")
        self.coord_label.pack()

        # Create the side panel for text and plot (right side)
        self.side_panel = tk.Frame(self.display_frame)
        self.side_panel.pack(side=tk.RIGHT, fill=tk.Y)

        # Create the text sidebar
        self.text_sidebar = tk.Text(self.side_panel, width=20, height=10, font=("Arial", 14), state=tk.DISABLED)
        self.text_sidebar.pack(fill=tk.X)

        # Add a frame for the plot below the text sidebar
        self.plot_frame = tk.Frame(self.side_panel)
        self.plot_frame.pack()
        
        # Initialize the plot once
        self.init_plot()

        # Filename label below the image
        self.filename_label = tk.Label(self, text="")
        self.filename_label.pack()

        # Control buttons
        self.controls_frame = tk.Frame(self)
        self.controls_frame.pack(fill=tk.X)

        self.pause_button = tk.Button(self.controls_frame, text="Pause", command=self.pause_slideshow)
        self.pause_button.pack(side=tk.LEFT)
        self.play_button = tk.Button(self.controls_frame, text="Play", command=self.play_slideshow)
        self.play_button.pack(side=tk.LEFT)
        self.forward_button = tk.Button(self.controls_frame, text="Forward", command=self.forward_image)
        self.forward_button.pack(side=tk.LEFT)
        self.backward_button = tk.Button(self.controls_frame, text="Backward", command=self.backward_image)
        self.backward_button.pack(side=tk.LEFT)
        
        # Add index seek functionality
        tk.Label(self.controls_frame, text="Go to index:").pack(side=tk.LEFT, padx=(10, 5))
        self.index_entry = tk.Entry(self.controls_frame, width=8)
        self.index_entry.pack(side=tk.LEFT)
        self.index_entry.bind('<Return>', self.on_index_entry)
        self.go_button = tk.Button(self.controls_frame, text="Go", command=self.go_to_index)
        self.go_button.pack(side=tk.LEFT, padx=(2, 0))

        # Slider for image navigation
        self.slider = tk.Scale(self, from_=0, to=0, orient=tk.HORIZONTAL, command=self.slider_changed)
        self.slider.pack(fill=tk.X)

        self.update_idletasks()  # Ensure the widget size is updated
        self.minsize(self.winfo_width(), self.winfo_height())
        
        # Bind window resize event
        self.bind('<Configure>', self.on_window_resize)
        
        # Bind keyboard hotkeys
        self.bind('<Key>', self.on_key_press)
        self.focus_set()  # Ensure the window can receive keyboard events

        self.select_image_folder()

    def set_camera_icon(self):
        """Set a camera emoji as the window icon"""
        try:
            # Create a simple camera icon using PIL
            from PIL import Image, ImageDraw, ImageFont
            
            # Create a 32x32 icon
            icon_size = 32
            icon_image = Image.new('RGBA', (icon_size, icon_size), (255, 255, 255, 0))
            draw = ImageDraw.Draw(icon_image)
            
            # Draw a simple camera shape
            # Camera body (rectangle)
            draw.rectangle([4, 10, 28, 26], fill='black', outline='gray')
            
            # Camera lens (circle)
            draw.ellipse([10, 12, 22, 24], fill='gray', outline='black')
            draw.ellipse([12, 14, 20, 22], fill='black')
            
            # Camera viewfinder (small rectangle on top)
            draw.rectangle([12, 6, 20, 10], fill='black', outline='gray')
            
            # Convert to PhotoImage for tkinter
            icon_photo = ImageTk.PhotoImage(icon_image)
            
            # Set the icon
            self.iconphoto(True, icon_photo)
            
            # Keep a reference to prevent garbage collection
            self.icon_photo = icon_photo
            
        except Exception as e:
            # Fallback: try to use a Unicode camera emoji in the title
            print(f"Could not set custom icon: {e}")
            self.title("📷 Image QAQCer")

    def init_plot(self):
        """Initialize the plot once and reuse it"""
        self.fig, self.ax = plt.subplots(figsize=(4, 3))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack()

    def cleanup_cache(self):
        """Clean up caches when they get too large"""
        if len(self.image_cache) > self.cache_size_limit:
            # Remove oldest half of cache
            items_to_remove = len(self.image_cache) // 2
            for _ in range(items_to_remove):
                self.image_cache.popitem()
        
        if len(self.metadata_cache) > self.cache_size_limit:
            items_to_remove = len(self.metadata_cache) // 2
            for _ in range(items_to_remove):
                self.metadata_cache.popitem()
        
        # Force garbage collection
        gc.collect()

    def on_window_resize(self, event):
        """Handle window resize events to adjust image size"""
        # Only respond to resize events from the main window
        if event.widget == self:
            # Calculate available space for the image
            window_width = self.winfo_width()
            window_height = self.winfo_height()
            
            # Account for side panel and controls (approximately)
            side_panel_width = 300  # Approximate width of side panel
            controls_height = 100   # Approximate height of controls and slider
            
            available_width = max(400, window_width - side_panel_width - 20)  # Minimum 400px
            available_height = max(300, window_height - controls_height - 20)  # Minimum 300px
            
            # Update thumbnail size if it changed significantly
            new_size = (available_width, available_height)
            if abs(new_size[0] - self.thumbnail_size[0]) > 50 or abs(new_size[1] - self.thumbnail_size[1]) > 50:
                self.thumbnail_size = new_size
                # Clear image cache since we're changing sizes
                self.image_cache.clear()
                # Refresh current image with new size
                if self.current_index < len(self.image_files):
                    self.show_image(self.current_index)

    def resize_current_image(self):
        """Resize the current image to fit the new thumbnail size"""
        if self.current_original_image and self.current_image_path:
            # Create a copy and resize it
            image_copy = self.current_original_image.copy()
            image_copy.thumbnail(self.thumbnail_size)
            photo = ImageTk.PhotoImage(image_copy)
            
            # Update the display
            self.image_label.config(image=photo)
            self.image_label.image = photo
            
            # Update cache with new size
            self.image_cache[self.current_image_path] = photo

    def on_key_press(self, event):
        """Handle keyboard events for navigation"""
        if event.keysym == 'Right':
            self.forward_image()
        elif event.keysym == 'Left':
            self.backward_image()
        elif event.keysym == 'space':
            # Space bar toggles play/pause
            if self.is_playing:
                self.pause_slideshow()
            else:
                self.play_slideshow()
        elif event.keysym == 'Escape':
            # Escape key pauses slideshow
            self.pause_slideshow()

    def on_mouse_motion(self, event):
        """Handle mouse motion over image to display coordinates"""
        if (self.current_transform and self.current_original_image and 
            hasattr(self.image_label, 'image') and self.image_label.image):
            
            try:
                # Get the displayed image dimensions
                displayed_width = self.image_label.winfo_width()
                displayed_height = self.image_label.winfo_height()
                
                # Get original image dimensions
                orig_width, orig_height = self.current_original_image.size
                
                # Calculate scaling factors
                scale_x = orig_width / displayed_width if displayed_width > 0 else 1
                scale_y = orig_height / displayed_height if displayed_height > 0 else 1
                
                # Convert mouse coordinates to original image pixel coordinates
                orig_x = event.x * scale_x
                orig_y = event.y * scale_y
                
                # Ensure coordinates are within image bounds
                if 0 <= orig_x < orig_width and 0 <= orig_y < orig_height:
                    # Apply the geotransform to get real-world coordinates
                    # For rasterio transform: transform.a = pixel_width, transform.e = pixel_height
                    # For GDAL transform: [0]=pixel_width, [1]=rotation, [2]=x_origin, [3]=rotation, [4]=pixel_height, [5]=y_origin
                    transform = self.current_transform
                    
                    if hasattr(transform, 'a'):  # Rasterio transform object
                        # Rasterio transform format
                        geo_x = transform.c + orig_x * transform.a + orig_y * transform.b
                        geo_y = transform.f + orig_x * transform.d + orig_y * transform.e
                    else:  # GDAL transform tuple
                        # GDAL transform format: [x_origin, pixel_width, rotation, y_origin, rotation, pixel_height]
                        geo_x = transform[0] + orig_x * transform[1] + orig_y * transform[2]
                        geo_y = transform[3] + orig_x * transform[4] + orig_y * transform[5]
                    
                    # Format coordinate display
                    coord_text = f"Pixel: ({orig_x:.0f}, {orig_y:.0f}) | Lat: {geo_y:.6f}° | Lon: {geo_x:.6f}°"
                    self.coord_label.config(text=coord_text)
                else:
                    self.coord_label.config(text="")
                    
            except Exception as e:
                self.coord_label.config(text=f"Coordinate error: {str(e)}")
        else:
            self.coord_label.config(text="")

    def calculate_ground_resolution(self, transform, crs):
        """Calculate ground resolution in meters per pixel"""
        try:
            if not transform:
                return "Unknown"
            
            # Get pixel sizes from transform
            if hasattr(transform, 'a'):  # Rasterio transform object
                pixel_size_x = abs(transform.a)  # degrees per pixel in X
                pixel_size_y = abs(transform.e)  # degrees per pixel in Y
            else:  # GDAL transform tuple
                pixel_size_x = abs(transform[1])  # degrees per pixel in X
                pixel_size_y = abs(transform[5])  # degrees per pixel in Y
            
            # If CRS is geographic (degrees), convert to meters
            if crs and ('4326' in str(crs) or 'WGS84' in str(crs).upper() or 'GEOGCS' in str(crs)):
                # More accurate conversion using latitude for your area (Gulf of Mexico ~29°N)
                # At 29°N latitude: 1 degree longitude ≈ 97,458 meters, 1 degree latitude ≈ 111,320 meters
                import math
                avg_lat = 29.0  # Approximate latitude for your area
                lat_rad = math.radians(avg_lat)
                meters_per_deg_lon = 111320 * math.cos(lat_rad)  # Longitude varies with latitude
                meters_per_deg_lat = 111320  # Latitude is constant
                
                ground_res_x = pixel_size_x * meters_per_deg_lon  # meters per pixel
                ground_res_y = pixel_size_y * meters_per_deg_lat  # meters per pixel
                
                avg_resolution = (ground_res_x + ground_res_y) / 2
                
                # Convert to appropriate units
                if avg_resolution < 1.0:
                    return f"{avg_resolution * 100:.1f} cm/pixel"
                elif avg_resolution < 1000:
                    return f"{avg_resolution:.2f} m/pixel"
                else:
                    return f"{avg_resolution / 1000:.2f} km/pixel"
            else:
                # For projected coordinate systems, pixel size is already in map units
                avg_resolution = (pixel_size_x + pixel_size_y) / 2
                return f"{avg_resolution:.2f} units/pixel"
                
        except Exception as e:
            return f"Error: {str(e)}"

    def load_image_files(self, folder_path):
        """Recursively load SAS .tif files, excluding .bathy.tif and .bmp files"""
        self.image_files = []
        self.parent_folder = folder_path  # Store parent folder for relative path display
        
        # Walk through all subdirectories recursively
        for root, dirs, files in os.walk(folder_path):
            for f in files:
                if f.lower().endswith('.tif'):
                    # Skip bathymetry files and other non- SAS files
                    if not f.lower().endswith('.bathy.tif') and '.bathy.' not in f.lower():
                        full_path = os.path.join(root, f)
                        self.image_files.append(full_path)
        
        # Sort files for consistent ordering
        self.image_files.sort()
        
        # Print summary for user feedback
        print(f"Found {len(self.image_files)} .tif image files in {folder_path} and subdirectories")

    def read_geotiff_metadata(self, image_path):
        """Read GeoTIFF metadata and return formatted information"""
        metadata = {
            'bounds': None,
            'crs': 'Unknown',
            'pixel_size': 'Unknown',
            'creation_date': 'Unknown',
            'transform': None,
            'ground_resolution': 'Unknown',
            'image_text': ''
        }
        
        try:
            if RASTERIO_AVAILABLE:
                # Use rasterio (preferred method)
                with rasterio.open(image_path) as src:
                    # Get bounds in the image's CRS
                    bounds = src.bounds
                    crs = src.crs
                    transform = src.transform
                    
                    # Store transform and CRS for coordinate calculations
                    metadata['transform'] = transform
                    metadata['crs_obj'] = crs
                    
                    # Transform bounds to WGS84 for plotting
                    if crs and crs != CRS.from_epsg(4326):
                        wgs84_bounds = transform_bounds(crs, CRS.from_epsg(4326), 
                                                      bounds.left, bounds.bottom, 
                                                      bounds.right, bounds.top)
                    else:
                        wgs84_bounds = (bounds.left, bounds.bottom, bounds.right, bounds.top)
                    
                    metadata['bounds'] = wgs84_bounds
                    metadata['crs'] = str(crs) if crs else 'Unknown'
                    metadata['pixel_size'] = f"{abs(transform.a):.6f}, {abs(transform.e):.6f}"
                    
                    # Calculate ground resolution
                    metadata['ground_resolution'] = self.calculate_ground_resolution(transform, crs)
                    
                    # Get tags/metadata
                    tags = src.tags()
                    if 'TIFFTAG_DATETIME' in tags:
                        metadata['creation_date'] = tags['TIFFTAG_DATETIME']
                    
            elif GDAL_AVAILABLE:
                # Fallback to GDAL
                dataset = gdal.Open(image_path)
                if dataset:
                    # Get geotransform and projection
                    gt = dataset.GetGeoTransform()
                    proj = dataset.GetProjection()
                    
                    # Store transform for coordinate calculations
                    metadata['transform'] = gt
                    metadata['crs_obj'] = proj
                    
                    # Calculate bounds
                    width = dataset.RasterXSize
                    height = dataset.RasterYSize
                    
                    minx = gt[0]
                    miny = gt[3] + height * gt[5]
                    maxx = gt[0] + width * gt[1]
                    maxy = gt[3]
                    
                    metadata['bounds'] = (minx, miny, maxx, maxy)
                    metadata['crs'] = proj if proj else 'Unknown'
                    metadata['pixel_size'] = f"{abs(gt[1]):.6f}, {abs(gt[5]):.6f}"
                    
                    # Calculate ground resolution
                    metadata['ground_resolution'] = self.calculate_ground_resolution(gt, proj)
                    
                    dataset = None  # Close dataset
            
            # Format text for display
            if metadata['bounds']:
                min_lon, min_lat, max_lon, max_lat = metadata['bounds']
                metadata['image_text'] = f"CRS:         {metadata['crs'][:30]}...\n"
                metadata['image_text'] += f"Min Lat:     {min_lat:.6f}\n"
                metadata['image_text'] += f"Max Lat:     {max_lat:.6f}\n"
                metadata['image_text'] += f"Min Lon:     {min_lon:.6f}\n"
                metadata['image_text'] += f"Max Lon:     {max_lon:.6f}\n"
                metadata['image_text'] += f"Pixel Size:  {metadata['pixel_size']}\n"
                metadata['image_text'] += f"Ground Res:  {metadata['ground_resolution']}\n"
                metadata['image_text'] += f"Created:     {metadata['creation_date']}\n"
            else:
                metadata['image_text'] = "No geospatial metadata found\n"
                
        except Exception as e:
            print(f"Error reading GeoTIFF metadata from {image_path}: {e}")
            metadata['image_text'] = f"Error reading metadata: {str(e)}\n"
        
        return metadata

    def load_image(self, index):
        if index >= 0 and index < len(self.image_files):
            image_path = self.image_files[index]
            self.current_image_path = image_path
            
            # Check cache first (but only if thumbnail size hasn't changed)
            cache_key = f"{image_path}_{self.thumbnail_size[0]}x{self.thumbnail_size[1]}"
            if cache_key in self.image_cache and image_path in self.metadata_cache:
                photo = self.image_cache[cache_key]
                metadata = self.metadata_cache[image_path]
                
                # Update the text in the sidebar
                self.text_sidebar.config(state=tk.NORMAL)
                self.text_sidebar.delete(1.0, tk.END)
                self.text_sidebar.insert(tk.END, metadata['image_text'])
                self.text_sidebar.config(state=tk.DISABLED)
                
                # Store transform for coordinate calculations
                self.current_transform = metadata.get('transform')
                self.current_crs = metadata.get('crs_obj')
                
                self.plot_bounding_box(metadata['bounds'])
                # Show relative path from parent folder
                rel_path = os.path.relpath(image_path, self.parent_folder) if hasattr(self, 'parent_folder') else os.path.basename(image_path)
                return photo, rel_path
            
            try:
                image = Image.open(image_path)
                # Store the original image for resizing
                self.current_original_image = image.copy()
                
            except Exception as e:
                print(f"Failed to load image {image_path}: {e}")
                return None, ""

            # Read GeoTIFF metadata instead of EXIF
            metadata = self.read_geotiff_metadata(image_path)

            # Add the bounding box to the list only if not already there
            if metadata['bounds'] and metadata['bounds'] not in self.bounding_boxes:
                self.bounding_boxes.append(metadata['bounds'])

            # Create thumbnail with current size
            image.thumbnail(self.thumbnail_size)
            photo = ImageTk.PhotoImage(image)
            
            # Cache the results with size-specific key
            self.image_cache[cache_key] = photo
            self.metadata_cache[image_path] = metadata
            
            # Clean up cache if needed
            self.cleanup_cache()

            # Update the text in the sidebar
            self.text_sidebar.config(state=tk.NORMAL)
            self.text_sidebar.delete(1.0, tk.END)
            self.text_sidebar.insert(tk.END, metadata['image_text'])
            self.text_sidebar.config(state=tk.DISABLED)

            # Store transform for coordinate calculations
            self.current_transform = metadata.get('transform')
            self.current_crs = metadata.get('crs_obj')

            self.plot_bounding_box(metadata['bounds'])
            # Show relative path from parent folder
            rel_path = os.path.relpath(image_path, self.parent_folder) if hasattr(self, 'parent_folder') else os.path.basename(image_path)
            return photo, rel_path
        return None, ""

    def show_image(self, index):
        """Display the image at the given index"""
        photo, filename = self.load_image(index)
        if photo:
            self.image_label.config(image=photo)
            self.image_label.image = photo  # Keep a reference to prevent garbage collection
            self.filename_label.config(text=f"Image {index + 1} of {len(self.image_files)}: {filename}")
        else:
            self.image_label.config(image="")
            self.image_label.image = None
            self.filename_label.config(text="Failed to load image")

    def play_slideshow(self):
        """Start the slideshow"""
        if not self.is_playing and self.image_files:
            self.is_playing = True
            self.next_slide()

    def pause_slideshow(self):
        """Pause the slideshow"""
        self.is_playing = False
        if self.slideshow_id:
            self.after_cancel(self.slideshow_id)
            self.slideshow_id = None

    def next_slide(self):
        """Show the next slide in the slideshow"""
        if self.is_playing and self.image_files:
            self.current_index = (self.current_index + 1) % len(self.image_files)
            self.show_image(self.current_index)
            self.slider.set(self.current_index)
            # Schedule the next slide
            self.slideshow_id = self.after(int(self.slideshow_interval * 1000), self.next_slide)

    def forward_image(self):
        """Move to the next image"""
        if self.image_files and self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.show_image(self.current_index)
            self.slider.set(self.current_index)

    def backward_image(self):
        """Move to the previous image"""
        if self.image_files and self.current_index > 0:
            self.current_index -= 1
            self.show_image(self.current_index)
            self.slider.set(self.current_index)

    def slider_changed(self, event):
        """Handle slider value changes"""
        if self.image_files:
            self.current_index = int(self.slider.get())
            self.show_image(self.current_index)

    def on_index_entry(self, event):
        """Handle Enter key press in index entry"""
        self.go_to_index()

    def go_to_index(self):
        """Go to the index specified in the entry field"""
        try:
            index = int(self.index_entry.get())
            if 0 <= index < len(self.image_files):
                self.current_index = index
                self.show_image(self.current_index)
                self.slider.set(self.current_index)
            else:
                messagebox.showwarning("Invalid Index", f"Index must be between 0 and {len(self.image_files) - 1}")
        except ValueError:
            messagebox.showwarning("Invalid Input", "Please enter a valid number")

    def plot_bounding_box(self, bounds):
        """Plot the bounding box on the map"""
        if not bounds or not self.ax:
            return
        
        try:
            # Clear the previous plot but keep the figure
            self.ax.clear()
            
            # Plot all bounding boxes in light color
            for bbox in self.bounding_boxes:
                if bbox:
                    min_lon, min_lat, max_lon, max_lat = bbox
                    width = max_lon - min_lon
                    height = max_lat - min_lat
                    rect = Rectangle((min_lon, min_lat), width, height, 
                                   linewidth=1, edgecolor='lightblue', 
                                   facecolor='lightblue', alpha=0.3)
                    self.ax.add_patch(rect)
            
            # Highlight current bounding box
            if bounds:
                min_lon, min_lat, max_lon, max_lat = bounds
                width = max_lon - min_lon
                height = max_lat - min_lat
                rect = Rectangle((min_lon, min_lat), width, height, 
                               linewidth=2, edgecolor='red', 
                               facecolor='red', alpha=0.5)
                self.ax.add_patch(rect)
                
                # Set plot limits with some padding
                all_lons = [bbox[0] for bbox in self.bounding_boxes if bbox] + [bbox[2] for bbox in self.bounding_boxes if bbox]
                all_lats = [bbox[1] for bbox in self.bounding_boxes if bbox] + [bbox[3] for bbox in self.bounding_boxes if bbox]
                
                if all_lons and all_lats:
                    lon_range = max(all_lons) - min(all_lons)
                    lat_range = max(all_lats) - min(all_lats)
                    padding = max(lon_range, lat_range) * 0.1
                    
                    self.ax.set_xlim(min(all_lons) - padding, max(all_lons) + padding)
                    self.ax.set_ylim(min(all_lats) - padding, max(all_lats) + padding)
            
            self.ax.set_xlabel('Longitude')
            self.ax.set_ylabel('Latitude')
            self.ax.set_title('Image Bounding Boxes')
            self.ax.grid(True, alpha=0.3)
            
            # Redraw the canvas
            self.canvas.draw()
            
        except Exception as e:
            print(f"Error plotting bounding box: {e}")

    def select_image_folder(self):
        folder_path = filedialog.askdirectory(title="Select Parent Folder (will search recursively)")
        if folder_path:
            # Show loading message
            self.filename_label.config(text="Loading images from subdirectories...")
            self.update_idletasks()
            
            self.load_image_files(folder_path)
            if self.image_files:
                self.slider.config(to=len(self.image_files) - 1)
                self.show_image(self.current_index)
            else:
                messagebox.showinfo("No Images Found", 
                                     f"No .tif files found in {folder_path} or its subdirectories.\n\n"
                                     f"Looking for: *.tif files\n"
                                     f"Excluding: *.bathy.tif files")

    def on_closing(self):
        """Clean up resources before closing"""
        if self.fig:
            plt.close(self.fig)
        self.image_cache.clear()
        self.metadata_cache.clear()
        gc.collect()
        self.destroy()


if __name__ == "__main__":
    app = SASImageSlideshow()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)  # Handle window close
    app.mainloop()
