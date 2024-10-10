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

ImageX = 900  # Monitor = 1100, Laptop = 900
ImageY = 750  # Monitor = 750


class ImageSlideshow(tk.Tk):
    def __init__(self, slideshow_interval=0.1):
        super().__init__()
        self.title("Image QAQCer")
        self.slideshow_interval = slideshow_interval
        self.thumbnail_size = (ImageX, ImageY)  # Set before the class

        self.image_files = []
        self.current_index = 0
        self.is_playing = False
        self.slideshow_id = None
        self.locations = []

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

        # Slider for image navigation
        self.slider = tk.Scale(self, from_=0, to=0, orient=tk.HORIZONTAL, command=self.slider_changed)
        self.slider.pack(fill=tk.X)

        self.update_idletasks()  # Ensure the widget size is updated
        self.minsize(self.winfo_width(), self.winfo_height())

        self.select_image_folder()

    def select_image_folder(self):
        folder_path = filedialog.askdirectory(title="Select Image Folder")
        if folder_path:
            self.load_image_files(folder_path)
            if self.image_files:
                self.slider.config(to=len(self.image_files) - 1)
                self.show_image(self.current_index)

    def load_image_files(self, folder_path):
        self.image_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path)
                            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.tiff', '.tif'))]

    def load_image(self, index):
        if index >= 0 and index < len(self.image_files):
            image_path = self.image_files[index]
            try:
                image = Image.open(image_path)
                exif_data = image._getexif()
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
                    lat = self.get_if_exist(gps_info, 2)
                    lon = self.get_if_exist(gps_info, 4)
                    alt = self.get_if_exist(gps_info, 6)

                    if lat and lon:
                        lat = self.convert_to_degrees(lat)
                        lon = self.convert_to_degrees(lon)

            # Populate text in sidebar
            image_text = f"Date:        {date}\n"
            image_text += f"Time:        {time}\n"
            image_text += f"Exposure:    {exposure_time}\n"
            image_text += f"Distance:    {subject_distance}\n"
            image_text += f"Altitude:    {alt}\n"
            image_text += f"Latitude:    {lat}\n"
            image_text += f"Longitude:   {lon}\n"

            # Add the location to the list
            self.locations.append((lat, lon))

            image.thumbnail(self.thumbnail_size)
            photo = ImageTk.PhotoImage(image)

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
        fig, ax = plt.subplots(figsize=(4, 3))

        valid_locations = [(lat, lon) for lat, lon in self.locations if lat != 999 and lon != 999]
        if valid_locations:
            all_lats, all_lons = zip(*valid_locations)
            ax.scatter(all_lons, all_lats, label="All Locations", c='blue', s=30)

        if lat != 999 and lon != 999:
            ax.scatter(lon, lat, label="Current Image", c='red', s=50)

        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.legend()

        for widget in self.plot_frame.winfo_children():
            widget.destroy()

        canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
        canvas.draw()
        canvas.get_tk_widget().pack()

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


if __name__ == "__main__":
    app = ImageSlideshow()
    app.mainloop()
