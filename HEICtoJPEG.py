import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
from PIL import Image
import pillow_heif
from pathlib import Path
import threading
import time

class HEICConverter:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("HEIC to JPEG Converter")
        self.root.geometry("600x400")
        
        # Register HEIF opener with Pillow
        pillow_heif.register_heif_opener()
        
        self.setup_ui()
        
    def setup_ui(self):
        """Create the user interface"""
        # Title
        title_label = tk.Label(self.root, text="HEIC to JPEG Converter", 
                              font=("Arial", 16, "bold"))
        title_label.pack(pady=10)
        
        # Instructions
        instructions = tk.Label(self.root, 
                               text="Select HEIC files to convert to high-quality JPEG",
                               font=("Arial", 10))
        instructions.pack(pady=5)
        
        # File selection frame
        file_frame = ttk.Frame(self.root)
        file_frame.pack(pady=10, padx=20, fill=tk.X)
        
        # Select files button
        self.select_button = ttk.Button(file_frame, text="Select HEIC Files", 
                                       command=self.select_files)
        self.select_button.pack(side=tk.LEFT, padx=5)
        
        # Convert button
        self.convert_button = ttk.Button(file_frame, text="Convert to JPEG", 
                                        command=self.start_conversion, state=tk.DISABLED)
        self.convert_button.pack(side=tk.LEFT, padx=5)
        
        # Selected files label
        self.files_label = tk.Label(self.root, text="No files selected", fg="gray")
        self.files_label.pack(pady=5)
        
        # Duplicate file handling frame
        duplicate_frame = ttk.LabelFrame(self.root, text="Duplicate File Handling")
        duplicate_frame.pack(pady=5, padx=20, fill=tk.X)
        
        self.overwrite_var = tk.StringVar(value="ask")
        
        ttk.Radiobutton(duplicate_frame, text="Ask for each file (default)", 
                       variable=self.overwrite_var, value="ask").pack(anchor='w', padx=10, pady=2)
        ttk.Radiobutton(duplicate_frame, text="Overwrite all existing files", 
                       variable=self.overwrite_var, value="overwrite").pack(anchor='w', padx=10, pady=2)
        ttk.Radiobutton(duplicate_frame, text="Skip all existing files", 
                       variable=self.overwrite_var, value="skip").pack(anchor='w', padx=10, pady=2)
        
        # Quality settings frame
        quality_frame = ttk.LabelFrame(self.root, text="JPEG Quality")
        quality_frame.pack(pady=5, padx=20, fill=tk.X)
        
        self.quality_var = tk.IntVar(value=95)
        quality_scale = ttk.Scale(quality_frame, from_=50, to=100, 
                                 variable=self.quality_var, orient=tk.HORIZONTAL)
        quality_scale.pack(fill=tk.X, padx=10, pady=5)
        
        quality_label = tk.Label(quality_frame, text="Quality: 95% (Higher = Better Quality)")
        quality_label.pack()
        
        # Update quality label when scale changes
        def update_quality_label(*args):
            quality_label.config(text=f"Quality: {self.quality_var.get()}% (Higher = Better Quality)")
        self.quality_var.trace('w', update_quality_label)
        
        # Progress frame
        progress_frame = ttk.Frame(self.root)
        progress_frame.pack(pady=10, padx=20, fill=tk.X)
        
        # Progress bar
        self.progress = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress.pack(fill=tk.X, pady=5)
        
        # Progress label
        self.progress_label = tk.Label(self.root, text="Ready", fg="blue")
        self.progress_label.pack(pady=5)
        
        # Log text area
        log_frame = ttk.LabelFrame(self.root, text="Conversion Log")
        log_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_frame, height=8, width=70)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.selected_files = []
        
    def log_message(self, message):
        """Add message to log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def select_files(self):
        """Open file dialog to select HEIC files"""
        try:
            files = filedialog.askopenfilenames(
                title="Select HEIC Files",
                filetypes=[
                    ("HEIC Files", "*.heic"),
                    ("HEIF Files", "*.heif"),
                    ("All HEIC/HEIF", "*.heic;*.heif"),
                    ("All Files", "*.*")
                ]
            )
            
            if files:
                self.selected_files = list(files)
                count = len(self.selected_files)
                self.files_label.config(text=f"{count} file(s) selected", fg="green")
                self.convert_button.config(state=tk.NORMAL)
                
                self.log_message(f"Selected {count} HEIC files for conversion")
                for file in self.selected_files:
                    self.log_message(f"  - {os.path.basename(file)}")
            else:
                self.log_message("No files selected")
                
        except Exception as e:
            self.log_message(f"Error selecting files: {str(e)}")
            messagebox.showerror("Error", f"Failed to select files: {str(e)}")
    
    def start_conversion(self):
        """Start conversion in a separate thread"""
        if not self.selected_files:
            messagebox.showwarning("No Files", "Please select HEIC files first")
            return
            
        # Disable buttons during conversion
        self.select_button.config(state=tk.DISABLED)
        self.convert_button.config(state=tk.DISABLED)
        
        # Start conversion in background thread
        thread = threading.Thread(target=self.convert_files)
        thread.daemon = True
        thread.start()
    
    def convert_files(self):
        """Convert HEIC files to JPEG"""
        try:
            total_files = len(self.selected_files)
            successful = 0
            failed = 0
            skipped = 0
            
            self.progress['maximum'] = total_files
            self.progress['value'] = 0
            
            quality = self.quality_var.get()
            overwrite_option = self.overwrite_var.get()
            
            self.log_message(f"Starting conversion of {total_files} files at {quality}% quality...")
            self.log_message(f"Duplicate handling: {overwrite_option}")
            
            for i, heic_path in enumerate(self.selected_files):
                try:
                    # Update progress
                    self.progress['value'] = i
                    self.progress_label.config(text=f"Converting {i+1}/{total_files}: {os.path.basename(heic_path)}")
                    self.root.update_idletasks()
                    
                    # Create output filename (same directory, .jpg extension)
                    path_obj = Path(heic_path)
                    jpeg_path = path_obj.with_suffix('.jpg')
                    
                    # Check if output file already exists
                    if jpeg_path.exists():
                        if overwrite_option == "skip":
                            self.log_message(f"Skipped: {os.path.basename(heic_path)} (file exists)")
                            skipped += 1
                            continue
                        elif overwrite_option == "ask":
                            response = messagebox.askyesno(
                                "File Exists", 
                                f"JPEG file already exists:\n{jpeg_path}\n\nOverwrite it?"
                            )
                            if not response:
                                self.log_message(f"Skipped: {os.path.basename(heic_path)} (user chose not to overwrite)")
                                skipped += 1
                                continue
                        # If overwrite_option == "overwrite", proceed without asking
                    
                    # Open and convert HEIC to JPEG
                    self.log_message(f"Converting: {os.path.basename(heic_path)}")
                    
                    with Image.open(heic_path) as img:
                        # Convert to RGB if necessary (HEIC might be in different color space)
                        if img.mode in ('RGBA', 'LA', 'P'):
                            img = img.convert('RGB')
                        
                        # Save as high-quality JPEG
                        img.save(
                            jpeg_path, 
                            'JPEG', 
                            quality=quality,
                            optimize=True,
                            progressive=True
                        )
                    
                    self.log_message(f"✓ Successfully converted: {os.path.basename(jpeg_path)}")
                    successful += 1
                    
                except Exception as e:
                    self.log_message(f"✗ Failed to convert {os.path.basename(heic_path)}: {str(e)}")
                    failed += 1
                    continue
            
            # Update final progress
            self.progress['value'] = total_files
            self.progress_label.config(text="Conversion Complete!")
            
            # Show summary
            self.log_message(f"\nConversion Summary:")
            self.log_message(f"  Total files: {total_files}")
            self.log_message(f"  Successful: {successful}")
            self.log_message(f"  Skipped: {skipped}")
            self.log_message(f"  Failed: {failed}")
            
            # Show completion message
            if successful > 0:
                messagebox.showinfo(
                    "Conversion Complete", 
                    f"Successfully converted {successful} of {total_files} files!\n"
                    f"Skipped: {skipped}\n"
                    f"Failed: {failed}\n\n"
                    f"JPEG files saved in the same location as HEIC files."
                )
            else:
                messagebox.showerror(
                    "Conversion Failed", 
                    f"No files were converted.\nSkipped: {skipped}\nFailed: {failed}\n\n"
                    f"Check the log for details."
                )
                
        except Exception as e:
            self.log_message(f"Critical error during conversion: {str(e)}")
            messagebox.showerror("Error", f"Conversion failed: {str(e)}")
        
        finally:
            # Re-enable buttons
            self.select_button.config(state=tk.NORMAL)
            self.convert_button.config(state=tk.NORMAL)
            self.progress_label.config(text="Ready")
    
    def run(self):
        """Start the application"""
        try:
            self.log_message("HEIC to JPEG Converter started")
            self.log_message("Select HEIC files and click 'Convert to JPEG'")
            self.root.mainloop()
        except Exception as e:
            print(f"Error running application: {e}")

def main():
    """Main entry point"""
    try:
        # Check if required modules are available
        import pillow_heif
        from PIL import Image
        
        converter = HEICConverter()
        converter.run()
        
    except ImportError as e:
        print("Required modules not found. Please install them with:")
        print("pip install pillow pillow-heif")
        input("Press Enter to exit...")
    except Exception as e:
        print(f"Error starting application: {e}")
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()