import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
import traceback

def create_gui():
    window = tk.Tk()
    window.title("Visibility Photo Sorter")
    window.geometry("600x400")
    
    # Initialize variables
    csv_path = tk.StringVar()
    source_path = tk.StringVar()
    output_path = tk.StringVar()
    status_var = tk.StringVar()
    status_var.set("Ready to sort photos...")
    
    # Browse functions
    def browse_csv():
        filepath = filedialog.askopenfilename(
            title="Select Results CSV",
            filetypes=[("CSV files", "*.csv")]
        )
        if filepath:
            csv_path.set(filepath)
    
    def browse_source():
        folderpath = filedialog.askdirectory(title="Select Source Folder")
        if folderpath:
            source_path.set(folderpath)
    
    def browse_output():
        folderpath = filedialog.askdirectory(title="Select Output Folder")
        if folderpath:
            output_path.set(folderpath)
    
    def process_files():
        try:
            # Validate inputs
            if not csv_path.get() or not os.path.exists(csv_path.get()):
                messagebox.showerror("Error", "Please select a valid CSV file")
                return
                
            if not source_path.get() or not os.path.exists(source_path.get()):
                messagebox.showerror("Error", "Please select a valid source folder")
                return
                
            if not output_path.get():
                messagebox.showerror("Error", "Please select an output folder")
                return
            
            # Read the CSV file
            status_var.set("Reading CSV file...")
            window.update()
            
            df = pd.read_csv(csv_path.get())
            
            # Create visibility category folders
            status_var.set("Creating category folders...")
            window.update()
            
            visibility_categories = df['visibility'].unique()
            for category in visibility_categories:
                os.makedirs(os.path.join(output_path.get(), category), exist_ok=True)
            
            # Process files
            status_var.set("Sorting files...")
            window.update()
            
            processed_images = 0
            processed_csvs = 0
            skipped_files = 0
            
            total_files = len(df)
            
            for index, row in df.iterrows():
                image_name = row['image']
                visibility = row['visibility']
                
                status_var.set(f"Processing {index+1}/{total_files}: {image_name}")
                window.update()
                
                # Process image file
                source_image = os.path.join(source_path.get(), image_name)
                dest_folder = os.path.join(output_path.get(), visibility)
                dest_image = os.path.join(dest_folder, image_name)
                
                if os.path.exists(source_image):
                    shutil.copy2(source_image, dest_image)
                    processed_images += 1
                else:
                    skipped_files += 1
                    continue
                
                # Process CSV file if it exists
                base_name = os.path.splitext(image_name)[0]
                csv_name = f"{base_name}.csv"
                source_csv = os.path.join(source_path.get(), csv_name)
                dest_csv = os.path.join(dest_folder, csv_name)
                
                if os.path.exists(source_csv):
                    shutil.copy2(source_csv, dest_csv)
                    processed_csvs += 1
            
            status_var.set("Sorting complete!")
            messagebox.showinfo(
                "Success", 
                f"Files sorted successfully!\n\n"
                f"Images processed: {processed_images}\n"
                f"CSV files processed: {processed_csvs}\n"
                f"Files skipped: {skipped_files}"
            )
            
        except Exception as e:
            status_var.set("Error occurred")
            messagebox.showerror("Error", str(e))
            traceback.print_exc()
    
    # Create GUI elements
    tk.Label(window, text="Results CSV:").pack(pady=(10,0), anchor="w", padx=20)
    tk.Entry(window, textvariable=csv_path, width=50).pack(pady=(0,5), padx=20)
    tk.Button(window, text="Browse", command=browse_csv).pack(padx=20)
    
    tk.Label(window, text="Source Folder:").pack(pady=(10,0), anchor="w", padx=20)
    tk.Entry(window, textvariable=source_path, width=50).pack(pady=(0,5), padx=20)
    tk.Button(window, text="Browse", command=browse_source).pack(padx=20)
    
    tk.Label(window, text="Output Folder:").pack(pady=(10,0), anchor="w", padx=20)
    tk.Entry(window, textvariable=output_path, width=50).pack(pady=(0,5), padx=20)
    tk.Button(window, text="Browse", command=browse_output).pack(padx=20)
    
    # Process button
    process_btn = tk.Button(
        window, 
        text="Sort Photos", 
        command=process_files,
        bg="#4CAF50",
        fg="white",
        height=2
    )
    process_btn.pack(pady=20)
    
    # Status label
    status_label = tk.Label(window, textvariable=status_var, fg="blue")
    status_label.pack(pady=10)
    
    # Start the main loop
    window.mainloop()

if __name__ == "__main__":
    create_gui()