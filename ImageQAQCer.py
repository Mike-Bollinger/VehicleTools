#Author: Mike Bollinger with help from ChatGPT 3.5
    # Image viewer to increment through a folder of images to get a quick look at the results of an image aquisition system.
    #This is intended to be a quick look tool as of v2. more in depth analysis should be done in another viewer.
    # July 07, 2024
    #
    ######################################################################

# UPDATED v1 06.28.2024
#This is the first version - Mike Bollinger & ChatGPT
# UPDATED v2 07.08.2024
#Updated to add a slider functionality to quickly scroll through images and also maintain play button functionality.

import os
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk

class ImageSlideshow(tk.Tk):
    def __init__(self, slideshow_interval=0.1, thumbnail_size=(800, 600)):
        super().__init__()
        self.title("Image Slideshow")
        self.slideshow_interval = slideshow_interval
        self.thumbnail_size = thumbnail_size
        self.image_files = []
        self.current_index = 0

        # Initialize attributes
        self.is_playing = False
        self.slideshow_id = None

        # Create widgets
        self.image_label = tk.Label(self)
        self.image_label.pack()
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
        self.min_width = self.winfo_width()
        self.min_height = self.winfo_height()
        self.minsize(self.min_width, self.min_height)

        self.select_image_folder()

    def select_image_folder(self):
        folder_path = filedialog.askdirectory(title="Select Image Folder")
        if folder_path:
            self.load_image_files(folder_path)
            self.slider.config(to=len(self.image_files) - 1)  # Update slider range
            self.show_image(self.current_index)

    def load_image_files(self, folder_path):
        self.image_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path)
                            if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

    def load_image(self, index):
        if index >= 0 and index < len(self.image_files):
            image_path = self.image_files[index]
            image = Image.open(image_path)
            image.thumbnail(self.thumbnail_size)
            photo = ImageTk.PhotoImage(image)
            return photo, os.path.basename(image_path)
        return None, ""

    def show_image(self, index):
        if index >= 0 and index < len(self.image_files):
            photo, filename = self.load_image(index)
            if photo:
                self.image_label.config(image=photo)
                self.image_label.image = photo
                self.filename_label.config(text=filename)
                self.update_idletasks()  # Ensure the widget size is updated

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
