import os
import random
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
import shutil

def select_random_samples(folder_path, num_samples):
    # Get all files in the directory
    all_files = os.listdir(folder_path)
    
    # Find all image files (assuming common image extensions)
    image_files = [f for f in all_files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff'))]
    
    # If we have fewer images than requested samples, adjust the number
    num_samples = min(num_samples, len(image_files))
    
    # Randomly select images
    selected_images = random.sample(image_files, num_samples)
    
    # Keep track of processed files
    kept_count = 0
    removed_count = 0
    
    # Process each file
    for file in all_files:
        file_path = os.path.join(folder_path, file)
        file_base = os.path.splitext(file)[0]
        
        # If it's a selected image or its corresponding CSV, keep it
        should_keep = any(os.path.splitext(img)[0] == file_base for img in selected_images)
        
        if not should_keep:
            try:
                os.remove(file_path)
                removed_count += 1
            except Exception as e:
                print(f"Error removing {file}: {e}")
        else:
            kept_count += 1

    return kept_count, removed_count

def main():
    # Create root window and hide it
    root = tk.Tk()
    root.withdraw()

    # Show folder selection dialog
    folder_path = filedialog.askdirectory(title="Select folder containing images and CSVs")
    
    if not folder_path:
        print("No folder selected. Exiting...")
        return
    
    # Count the total number of images for reference
    image_files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff'))]
    total_images = len(image_files)
    
    # Ask user for the number of samples to keep - without maximum limit
    num_samples = simpledialog.askinteger(
        title="Sample Count", 
        prompt=f"How many images to keep? (total available: {total_images})",
        minvalue=1
    )
    
    if not num_samples:
        print("Operation cancelled.")
        return

    # Confirm with user
    print(f"Selected folder: {folder_path}")
    print(f"Images to keep: {num_samples} out of {total_images}")
    proceed = input("Proceed with random selection? (y/n): ").lower()
    
    if proceed != 'y':
        print("Operation cancelled.")
        return

    # Process the files
    kept, removed = select_random_samples(folder_path, num_samples)
    
    print(f"Operation complete!")
    print(f"Files kept: {kept}")
    print(f"Files removed: {removed}")

if __name__ == "__main__":
    main()