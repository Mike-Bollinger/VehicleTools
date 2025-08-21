"""
Title: Image QAQC Application with EXIF Metadata Display
Author: Mike Bollinger with contributions from ChatGPT
Date: 2024-10-09
Version: 1.0

Description:
This is an image QAQC application that loads images from a selected folder, extracts EXIF metadata, and displays relevant fields in a sidebar along with a plot of image locations (latitude/longitude).
The sidebar includes fields such as date, time, exposure time, subject distance, altitude, latitude, and longitude.
Users can navigate through the images with play, pause, forward, and backward controls.

The application also includes a slider to manually navigate between images, and it plots the GPS locations on a matplotlib plot.
"""
import os
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk, ExifTags
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import gc

ImageX = 900  # Monitor = 1100, Laptop = 900
ImageY = 750  # Monitor = 750


class ImageSlideshow(tk.Tk):
    def __init__(self, slideshow_interval=0.1):
        super().__init__()
        self.title("Image QAQCer")
        self.slideshow_interval = slideshow_interval
        self.base_thumbnail_size = (ImageX, ImageY)  # Base size for reference
        self.thumbnail_size = (ImageX, ImageY)  # Current size (will be dynamic)

        self.image_files = []
        self.current_index = 0
        self.is_playing = False
        self.slideshow_id = None
        self.locations = []
        
        # Performance optimizations
        self.image_cache = {}  # Cache for thumbnails
        self.exif_cache = {}   # Cache for EXIF data
        self.cache_size_limit = 50  # Limit cache to prevent memory issues
        self.fig = None  # Reuse single figure
        self.ax = None
        self.canvas = None
        
        # Track the original image for resizing
        self.current_image_path = None
        self.current_original_image = None

        # Create a frame for the image and the side panel (text + plot)
        self.display_frame = tk.Frame(self)
        self.display_frame.pack(fill=tk.BOTH, expand=True)

        # Create the image label (left side)
        self.image_label = tk.Label(self.display_frame)
        self.image_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

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
        
        if len(self.exif_cache) > self.cache_size_limit:
            items_to_remove = len(self.exif_cache) // 2
            for _ in range(items_to_remove):
                self.exif_cache.popitem()
        
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

    def select_image_folder(self):
        folder_path = filedialog.askdirectory(title="Select Image Folder")
        if folder_path:
            self.load_image_files(folder_path)
            if self.image_files:
                self.slider.config(to=len(self.image_files) - 1)
                self.show_image(self.current_index)

    def load_image_files(self, folder_path):
        # Filter out raw images and only include processed images
        self.image_files = []
        for f in os.listdir(folder_path):
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                # Skip raw files - look for common raw image indicators
                if 'raw' not in f.lower():
                    self.image_files.append(os.path.join(folder_path, f))

    def load_image(self, index):
        if index >= 0 and index < len(self.image_files):
            image_path = self.image_files[index]
            self.current_image_path = image_path
            
            # Check cache first (but only if thumbnail size hasn't changed)
            cache_key = f"{image_path}_{self.thumbnail_size[0]}x{self.thumbnail_size[1]}"
            if cache_key in self.image_cache and image_path in self.exif_cache:
                photo = self.image_cache[cache_key]
                lat, lon, alt, image_text = self.exif_cache[image_path]
                
                # Update the text in the sidebar
                self.text_sidebar.config(state=tk.NORMAL)
                self.text_sidebar.delete(1.0, tk.END)
                self.text_sidebar.insert(tk.END, image_text)
                self.text_sidebar.config(state=tk.DISABLED)
                
                self.plot_coordinates(lat, lon)
                return photo, os.path.basename(image_path)
            
            try:
                image = Image.open(image_path)
                # Store the original image for resizing
                self.current_original_image = image.copy()
                
                # Try to get EXIF data, handling different image formats
                exif_data = None
                if hasattr(image, '_getexif') and callable(image._getexif):
                    exif_data = image._getexif()
                elif hasattr(image, 'getexif'):
                    exif_data = image.getexif()
            except Exception as e:
                print(f"Failed to load image {image_path}: {e}")
                return None, ""

            image_text = ""
            lat, lon, alt = 999, 999, "Unknown"  # Default values

            if exif_data:
                exif = {ExifTags.TAGS[k]: v for k, v in exif_data.items() if k in ExifTags.TAGS}

                # Date/Time
                date_time = exif.get('DateTimeOriginal', "Unknown")
                date, time = ("Unknown", "Unknown") if date_time == "Unknown" else date_time.split(' ')

                # Exposure Time
                exposure_time = exif.get('ExposureTime', "Unknown")

                # Subject Distance
                subject_distance = exif.get('SubjectDistance', "Unknown")

                # GPS Info (lat, lon, altitude)
                gps_info = exif.get('GPSInfo', None)
                if gps_info:
                    lat_ref = self.get_if_exist(gps_info, 1)  # N or S
                    lat = self.get_if_exist(gps_info, 2)
                    lon_ref = self.get_if_exist(gps_info, 3)  # E or W
                    lon = self.get_if_exist(gps_info, 4)
                    alt = self.get_if_exist(gps_info, 6)

                    if lat and lon:
                        lat = self.convert_to_degrees(lat)
                        lon = self.convert_to_degrees(lon)
                        
                        # Apply hemisphere corrections
                        if lat_ref and lat_ref == 'S':
                            lat = -lat
                        if lon_ref and lon_ref == 'W':
                            lon = -lon
            else:
                # Set default values when no EXIF data
                date, time = "Unknown", "Unknown"
                exposure_time = "Unknown"
                subject_distance = "Unknown"

            # Populate text in sidebar
            image_text = f"Date:        {date}\n"
            image_text += f"Time:        {time}\n"
            image_text += f"Exposure:    {exposure_time}\n"
            image_text += f"Distance:    {subject_distance}\n"
            image_text += f"Altitude:    {alt}\n"
            image_text += f"Latitude:    {lat}\n"
            image_text += f"Longitude:   {lon}\n"

            # Add the location to the list only if not already there
            if (lat, lon) not in self.locations:
                self.locations.append((lat, lon))

            # Create thumbnail with current size
            image.thumbnail(self.thumbnail_size)
            photo = ImageTk.PhotoImage(image)
            
            # Cache the results with size-specific key
            self.image_cache[cache_key] = photo
            self.exif_cache[image_path] = (lat, lon, alt, image_text)
            
            # Clean up cache if needed
            self.cleanup_cache()

            # Update the text in the sidebar
            self.text_sidebar.config(state=tk.NORMAL)
            self.text_sidebar.delete(1.0, tk.END)
            self.text_sidebar.insert(tk.END, image_text)
            self.text_sidebar.config(state=tk.DISABLED)

            self.plot_coordinates(lat, lon)
            return photo, os.path.basename(image_path)
        return None, ""

    def get_if_exist(self, data, key):
        return data[key] if key in data else None

    def convert_to_degrees(self, value):
        d, m, s = value
        return d + (m / 60.0) + (s / 3600.0)

    def plot_coordinates(self, lat, lon):
        if self.ax is None:
            return
            
        # Clear the previous plot
        self.ax.clear()

        valid_locations = [(lat, lon) for lat, lon in self.locations if lat != 999 and lon != 999]
        if valid_locations:
            all_lats, all_lons = zip(*valid_locations)
            self.ax.scatter(all_lons, all_lats, label="All Locations", c='blue', s=30)

        if lat != 999 and lon != 999:
            self.ax.scatter(lon, lat, label="Current Image", c='red', s=50)

        self.ax.set_xlabel("Longitude")
        self.ax.set_ylabel("Latitude")
        self.ax.legend()
        
        # Redraw the canvas
        self.canvas.draw_idle()  # Use draw_idle for better performance

    def show_image(self, index):
        if index >= 0 and index < len(self.image_files):
            photo, filename = self.load_image(index)
            if photo:
                self.image_label.config(image=photo)
                self.image_label.image = photo
                self.filename_label.config(text=filename)
                self.update_idletasks()

    def show_next_image(self):
        if self.is_playing:
            self.current_index = (self.current_index + 1) % len(self.image_files)
            self.show_image(self.current_index)
            self.slider.set(self.current_index)
            self.slideshow_id = self.after(int(self.slideshow_interval * 1000), self.show_next_image)

    def pause_slideshow(self):
        if self.slideshow_id:
            self.after_cancel(self.slideshow_id)
            self.slideshow_id = None
        self.is_playing = False

    def play_slideshow(self):
        if not self.is_playing:
            self.is_playing = True
            self.show_next_image()

    def forward_image(self):
        self.pause_slideshow()
        self.current_index = (self.current_index + 1) % len(self.image_files)
        self.show_image(self.current_index)
        self.slider.set(self.current_index)

    def backward_image(self):
        self.pause_slideshow()
        self.current_index = (self.current_index - 1) % len(self.image_files)
        self.show_image(self.current_index)
        self.slider.set(self.current_index)

    def slider_changed(self, value):
        if not self.is_playing:
            self.current_index = int(value)
            self.show_image(self.current_index)
    
    def on_index_entry(self, event):
        """Handle Enter key press in the index entry box"""
        self.go_to_index()
    
    def go_to_index(self):
        """Go to the specified image index with error handling"""
        try:
            # Get the index from the entry box
            index_text = self.index_entry.get().strip()
            if not index_text:
                return
            
            target_index = int(index_text)
            
            # Check bounds
            if target_index < 0:
                self.show_index_error(f"Index {target_index} is too low. Minimum index is 0.")
                return
            elif target_index >= len(self.image_files):
                max_index = len(self.image_files) - 1
                self.show_index_error(f"Index {target_index} is too high. Maximum index is {max_index}.")
                return
            
            # Valid index - navigate to it
            self.pause_slideshow()  # Stop slideshow if running
            self.current_index = target_index
            self.show_image(self.current_index)
            self.slider.set(self.current_index)
            
            # Clear the entry box
            self.index_entry.delete(0, tk.END)
            
        except ValueError:
            self.show_index_error(f"'{self.index_entry.get()}' is not a valid number.")
    
    def show_index_error(self, message):
        """Show error message for invalid index input"""
        # Flash the entry box red to indicate error
        original_bg = self.index_entry.cget('bg')
        self.index_entry.config(bg='#ffcccc')
        
        # Show error in filename label temporarily
        original_text = self.filename_label.cget('text')
        self.filename_label.config(text=f"Error: {message}", fg='red')
        
        # Reset after 3 seconds
        def reset_error():
            self.index_entry.config(bg=original_bg)
            self.filename_label.config(text=original_text, fg='black')
        
        self.after(3000, reset_error)
    
    def on_closing(self):
        """Clean up resources before closing"""
        if self.fig:
            plt.close(self.fig)
        self.image_cache.clear()
        self.exif_cache.clear()
        gc.collect()
        self.destroy()


if __name__ == "__main__":
    app = ImageSlideshow()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)  # Handle window close
    app.mainloop()
