import os
import csv
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont

class ImageSlideshow(tk.Tk):
    def __init__(self, slideshow_interval=0.1, thumbnail_size=(1000, 650)):
        super().__init__()
        self.title("Image QAQCer")
        self.slideshow_interval = slideshow_interval
        self.thumbnail_size = thumbnail_size
        self.image_files = []
        self.current_index = 0

        # Initialize attributes
        self.is_playing = False
        self.slideshow_id = None

        # Create a frame for the image and text
        self.display_frame = tk.Frame(self)
        self.display_frame.pack(fill=tk.BOTH, expand=True)

        # Create the image label
        self.image_label = tk.Label(self.display_frame)
        self.image_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create the text sidebar
        self.text_sidebar = tk.Text(self.display_frame, width=20, height=10, font=("Arial", 12), state=tk.DISABLED)
        self.text_sidebar.pack(side=tk.RIGHT, fill=tk.Y)

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
        self.min_width = self.winfo_width()
        self.min_height = self.winfo_height()
        self.minsize(self.min_width, self.min_height)

        self.select_image_folder()

    def select_image_folder(self):
        folder_path = filedialog.askdirectory(title="Select Image Folder")
        if folder_path:
            self.load_image_files(folder_path)
            if self.image_files:  # Check if any image files were found
                self.slider.config(to=len(self.image_files) - 1)  # Update slider range
                self.show_image(self.current_index)
            else:
                messagebox.showerror("Error", "No image files found in the selected folder.")

    def load_image_files(self, folder_path):
        self.image_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path)
                            if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

    def load_image(self, index):
        if index >= 0 and index < len(self.image_files):
            image_path = self.image_files[index]
            try:
                image = Image.open(image_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load image {image_path}: {e}")
                return None, ""

            data_path = os.path.splitext(image_path)[0] + '.csv'
            image_text = ""
            if os.path.isfile(data_path):  # Fixed the file existence check
                try:
                    with open(data_path, newline='') as csvfile:
                        reader = csv.reader(csvfile)
                        for row in reader:
                            if reader.line_num == 1:
                                image_text  = "Time:     " + row[1] + "\n"
                                image_text += "Depth:    " + row[4] + "\n"
                                image_text += "Altitude: " + row[5] + "\n"
                                image_text += "Pitch:    " + row[6] + "\n"
                                image_text += "Roll:     " + row[7] + "\n"
                            elif reader.line_num == 2:
                                image_text += "Exposure: " + row[2]
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load CSV data from {data_path}: {e}")

            image.thumbnail(self.thumbnail_size)
            photo = ImageTk.PhotoImage(image)

            # Update the text in the sidebar
            self.text_sidebar.config(state=tk.NORMAL)
            self.text_sidebar.delete(1.0, tk.END)
            self.text_sidebar.insert(tk.END, image_text)
            self.text_sidebar.config(state=tk.DISABLED)

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
