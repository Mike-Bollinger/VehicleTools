#Author: Mike Bollinger with help from ChatGPT 3.5
    # RTsys NemoSens Cousto Software
    # June 28, 2024
    #
    ######################################################################

# UPDATED v1 06.28.2024
#This is the first version - Mike Bollinger & ChatGPT

import os
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk


class ImageSlideshow(tk.Tk):
    def __init__(self, slideshow_interval=0.1, thumbnail_size=(500, 500)):
        super().__init__()
        self.title("Image QAQCer")
        #self.geometry("500x300") #Fixed Window Size

        # Initialize attributes
        self.is_paused = False
        self.is_playing = False
        self.slideshow_id = None

        self.slideshow_interval = slideshow_interval
        self.thumbnail_size = thumbnail_size
        self.images = []
        self.current_index = 0
        self.image_label = tk.Label(self)
        self.image_label.pack()
        self.filename_label = tk.Label(self, text="")
        self.filename_label.pack()
        self.backward_button = tk.Button(self, text="Backward", command=self.backward_image)
        self.backward_button.pack(side=tk.LEFT)
        self.pause_button = tk.Button(self, text="Pause", command=self.pause_slideshow)
        self.pause_button.pack(side=tk.LEFT)
        self.forward_button = tk.Button(self, text="Forward", command=self.forward_image)
        self.forward_button.pack(side=tk.RIGHT)
        self.play_button = tk.Button(self, text="Play", command=self.play_slideshow)
        self.play_button.pack(side=tk.RIGHT)


        self.select_image_folder()

    def select_image_folder(self):
        folder_path = filedialog.askdirectory(title="Select Image Folder")
        if folder_path:
            self.load_images(folder_path)
            self.show_next_image()

    def load_images(self, folder_path):
        self.images = []
        for filename in os.listdir(folder_path):
            if filename.endswith(".jpg") or filename.endswith(".png"):
                image_path = os.path.join(folder_path, filename)
                image = Image.open(image_path)
                image.thumbnail(self.thumbnail_size)  # Resize to thumbnail size
                self.images.append((image, filename))

    def show_next_image(self):
        if not self.is_paused and self.is_playing:
            if self.current_index < len(self.images):
                image, filename = self.images[self.current_index]
                photo = ImageTk.PhotoImage(image)
                self.image_label.config(image=photo)
                self.image_label.image = photo
                self.filename_label.config(text=filename)
                # Resize window to fit the image size
                self.update_idletasks()  # Ensure the widget size is updated
                self.geometry(f"{self.winfo_reqwidth()}x{self.winfo_reqheight()}")
                self.current_index += 1
                self.slideshow_id = self.after(int(self.slideshow_interval * 1000), self.show_next_image)
            else:
                self.destroy()

    def pause_slideshow(self):
        if self.slideshow_id:
            self.after_cancel(self.slideshow_id)
            self.is_paused = True
            self.is_playing = False

    def play_slideshow(self):
        self.is_paused = False
        self.is_playing = True
        self.show_next_image()

    def forward_image(self):
        if self.current_index < len(self.images) - 1:
            self.current_index += 1
            self.pause_slideshow()
            self.show_image(self.current_index)

    def backward_image(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.pause_slideshow()
            self.show_image(self.current_index)

    def show_image(self, index):
        if index >= 0 and index < len(self.images):
            image, filename = self.images[index]
            photo = ImageTk.PhotoImage(image)
            self.image_label.config(image=photo)
            self.image_label.image = photo
            self.filename_label.config(text=filename)

            # Resize the window to fit the photo size
            #self.geometry(f"{image.width}x{image.height}")

if __name__ == "__main__":
    app = ImageSlideshow()
    app.mainloop()




