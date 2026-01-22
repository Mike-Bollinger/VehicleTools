"""
Main GUI Module
Enhanced interface for dive report generation with preview and flexible data sources
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from datetime import datetime
from typing import List, Dict, Optional

from dive_finder import DiveFinder
from report_generator import ReportGenerator
from preview_widget import PreviewWidget


class DataSourcePanel(ttk.Frame):
    """Panel for managing multiple data source folders"""
    
    def __init__(self, parent, on_change_callback=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_change_callback = on_change_callback
        self.data_sources = []
        self.setup_ui()
        
    def setup_ui(self):
        # Title
        ttk.Label(self, text="Data Sources", font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        # Listbox frame
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Listbox
        self.listbox = tk.Listbox(list_frame, height=4, yscrollcommand=scrollbar.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)
        
        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="Add Folder", command=self.add_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Remove Selected", command=self.remove_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Clear All", command=self.clear_all).pack(side=tk.LEFT, padx=2)
        
    def add_folder(self):
        """Add a data source folder"""
        folder = filedialog.askdirectory(title="Select Data Source Folder")
        if folder and folder not in self.data_sources:
            self.data_sources.append(folder)
            self.listbox.insert(tk.END, folder)
            if self.on_change_callback:
                self.on_change_callback()
                
    def remove_selected(self):
        """Remove selected data source"""
        selection = self.listbox.curselection()
        if selection:
            idx = selection[0]
            self.data_sources.pop(idx)
            self.listbox.delete(idx)
            if self.on_change_callback:
                self.on_change_callback()
                
    def clear_all(self):
        """Clear all data sources"""
        self.data_sources.clear()
        self.listbox.delete(0, tk.END)
        if self.on_change_callback:
            self.on_change_callback()
            
    def get_sources(self) -> List[str]:
        """Get list of data sources"""
        return self.data_sources.copy()


class DiveSelectionPanel(ttk.Frame):
    """Panel for selecting dives with checkboxes"""
    
    def __init__(self, parent, on_selection_change=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_selection_change = on_selection_change
        self.dive_items = {}  # Maps tree item id to dive info
        self.setup_ui()
        
    def setup_ui(self):
        # Title and controls
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(top_frame, text="Available Dives", font=("Arial", 11, "bold")).pack(side=tk.LEFT)
        
        btn_frame = ttk.Frame(top_frame)
        btn_frame.pack(side=tk.RIGHT)
        
        ttk.Button(btn_frame, text="Select All", command=self.select_all, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Deselect All", command=self.deselect_all, width=10).pack(side=tk.LEFT, padx=2)
        
        # Treeview frame
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Treeview
        self.tree = ttk.Treeview(tree_frame, columns=("status", "location"), 
                                 show="tree headings", yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.config(command=self.tree.yview)
        
        # Columns
        self.tree.heading("#0", text="Dive")
        self.tree.heading("status", text="Status")
        self.tree.heading("location", text="Location")
        
        self.tree.column("#0", width=150)
        self.tree.column("status", width=150)
        self.tree.column("location", width=300)
        
        # Bind events
        self.tree.bind("<space>", self.toggle_selected)
        self.tree.bind("<Button-1>", self.on_click)
        
    def on_click(self, event):
        """Handle click events on tree items"""
        region = self.tree.identify_region(event.x, event.y)
        if region == "tree":
            item = self.tree.identify_row(event.y)
            if item:
                self.toggle_item(item)
                
    def toggle_selected(self, event):
        """Toggle selected item with spacebar"""
        selection = self.tree.selection()
        if selection:
            self.toggle_item(selection[0])
            
    def toggle_item(self, item):
        """Toggle checkbox state of an item"""
        if item in self.dive_items:
            dive_info = self.dive_items[item]
            dive_info['selected'] = not dive_info.get('selected', False)
            self.update_item_display(item, dive_info)
            if self.on_selection_change:
                self.on_selection_change()
                
    def update_item_display(self, item, dive_info):
        """Update the display of a tree item"""
        checkbox = "☑" if dive_info.get('selected', False) else "☐"
        dive_name = dive_info['dive_name']
        
        status = "✓ Has Report_Plots" if dive_info['has_report_plots'] else "⚠ No Report_Plots"
        location = dive_info.get('folder_path', '')
        
        self.tree.item(item, text=f"{checkbox} {dive_name}", 
                      values=(status, location))
        
    def load_dives(self, dive_dict: Dict[str, List[Dict]]):
        """
        Load dives into the tree
        
        Args:
            dive_dict: Dict mapping dive numbers to lists of dive info
        """
        # Clear existing
        self.tree.delete(*self.tree.get_children())
        self.dive_items.clear()
        
        # Sort by dive number
        sorted_dives = sorted(dive_dict.items(), key=lambda x: x[0])
        
        for dive_num, dive_list in sorted_dives:
            # Merge sources for same dive
            from dive_finder import DiveFinder
            finder = DiveFinder()
            merged = finder.merge_dive_sources(dive_list)
            
            if merged:
                merged['selected'] = False  # Default unselected
                item_id = self.tree.insert("", tk.END)
                self.dive_items[item_id] = merged
                self.update_item_display(item_id, merged)
                
    def select_all(self):
        """Select all dives"""
        for item, dive_info in self.dive_items.items():
            dive_info['selected'] = True
            self.update_item_display(item, dive_info)
        if self.on_selection_change:
            self.on_selection_change()
            
    def deselect_all(self):
        """Deselect all dives"""
        for item, dive_info in self.dive_items.items():
            dive_info['selected'] = False
            self.update_item_display(item, dive_info)
        if self.on_selection_change:
            self.on_selection_change()
            
    def get_selected_dives(self) -> List[Dict]:
        """Get list of selected dive info dicts"""
        selected = []
        for dive_info in self.dive_items.values():
            if dive_info.get('selected', False):
                selected.append(dive_info)
        return sorted(selected, key=lambda x: x['dive_number'])


class MainGUI:
    """Main application window"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Dive Report Generator - Enhanced")
        self.root.geometry("1400x900")
        
        self.dive_finder = DiveFinder()
        self.report_generator = ReportGenerator()
        
        self.csv_file_var = tk.StringVar(value="C:\\Users\\Mike.Bollinger\\Downloads\\EN2501_AUV_Mission_Log_IMAGING_LASER - Mission_Overview.csv")
        self.map_folder_var = tk.StringVar(value="")
        self.output_folder_var = tk.StringVar(value=os.path.dirname(__file__))
        
        self.metadata_cache = {}
        self.current_dives = {}
        
        self.setup_ui()
        self.load_default_sources()
        
    def setup_ui(self):
        """Setup main UI"""
        # Main container
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel (controls)
        left_panel = ttk.Frame(main_container)
        main_container.add(left_panel, weight=1)
        
        # Right panel (preview)
        right_panel = ttk.Frame(main_container)
        main_container.add(right_panel, weight=1)
        
        # Setup left panel
        self.setup_left_panel(left_panel)
        
        # Setup right panel (preview)
        self.preview_widget = PreviewWidget(right_panel)
        self.preview_widget.pack(fill=tk.BOTH, expand=True)
        
    def setup_left_panel(self, parent):
        """Setup left control panel"""
        # Title
        title_label = ttk.Label(parent, text="Dive Report Generator", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=10)
        
        # CSV File section
        csv_frame = ttk.LabelFrame(parent, text="Mission Log CSV", padding=10)
        csv_frame.pack(fill=tk.X, padx=5, pady=5)
        
        csv_entry_frame = ttk.Frame(csv_frame)
        csv_entry_frame.pack(fill=tk.X)
        
        ttk.Entry(csv_entry_frame, textvariable=self.csv_file_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(csv_entry_frame, text="Browse", command=self.browse_csv).pack(side=tk.LEFT)
        ttk.Button(csv_entry_frame, text="Load", command=self.load_metadata).pack(side=tk.LEFT, padx=(5, 0))
        
        # Map Folder section (optional)
        map_frame = ttk.LabelFrame(parent, text="Dive Maps Folder (Optional)", padding=10)
        map_frame.pack(fill=tk.X, padx=5, pady=5)
        
        map_entry_frame = ttk.Frame(map_frame)
        map_entry_frame.pack(fill=tk.X)
        
        ttk.Entry(map_entry_frame, textvariable=self.map_folder_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(map_entry_frame, text="Browse", command=self.browse_map_folder).pack(side=tk.LEFT)
        
        # Data Sources section
        sources_frame = ttk.LabelFrame(parent, text="Data Sources", padding=10)
        sources_frame.pack(fill=tk.BOTH, expand=False, padx=5, pady=5)
        
        self.data_source_panel = DataSourcePanel(sources_frame, on_change_callback=self.scan_data_sources)
        self.data_source_panel.pack(fill=tk.BOTH, expand=True)
        
        ttk.Button(sources_frame, text="Scan for Dives", command=self.scan_data_sources).pack(pady=5)
        
        # Dive Selection section
        selection_frame = ttk.LabelFrame(parent, text="Dive Selection", padding=10)
        selection_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.dive_selection_panel = DiveSelectionPanel(selection_frame, 
                                                       on_selection_change=self.update_preview)
        self.dive_selection_panel.pack(fill=tk.BOTH, expand=True)
        
        # Output section
        output_frame = ttk.LabelFrame(parent, text="Output", padding=10)
        output_frame.pack(fill=tk.X, padx=5, pady=5)
        
        output_entry_frame = ttk.Frame(output_frame)
        output_entry_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Entry(output_entry_frame, textvariable=self.output_folder_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(output_entry_frame, text="Browse", command=self.browse_output).pack(side=tk.LEFT)
        
        # Generate button
        self.generate_btn = ttk.Button(output_frame, text="Generate Report", 
                                       command=self.generate_report)
        self.generate_btn.pack(fill=tk.X)
        
        # Status bar
        self.status_label = ttk.Label(parent, text="Ready", relief=tk.SUNKEN)
        self.status_label.pack(fill=tk.X, padx=5, pady=5)
        
    def load_default_sources(self):
        """Load default data sources"""
        default_sources = [
            "E:\\EN2501\\Image_LLS",
            "Q:\\EN2501\\Image_LLS"
        ]
        
        for source in default_sources:
            if os.path.exists(source):
                self.data_source_panel.data_sources.append(source)
                self.data_source_panel.listbox.insert(tk.END, source)
        
        # Auto-scan if sources were added
        if self.data_source_panel.data_sources:
            self.scan_data_sources()
            
    def browse_csv(self):
        """Browse for CSV file"""
        file = filedialog.askopenfilename(
            title="Select Mission Log CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir=os.path.dirname(self.csv_file_var.get())
        )
        if file:
            self.csv_file_var.set(file)
            self.load_metadata()
    
    def browse_map_folder(self):
        """Browse for map folder"""
        folder = filedialog.askdirectory(
            title="Select Dive Maps Folder",
            initialdir=self.map_folder_var.get() if self.map_folder_var.get() else os.path.dirname(__file__)
        )
        if folder:
            self.map_folder_var.set(folder)
            
    def browse_output(self):
        """Browse for output folder"""
        folder = filedialog.askdirectory(
            title="Select Output Folder",
            initialdir=self.output_folder_var.get()
        )
        if folder:
            self.output_folder_var.set(folder)
            
    def load_metadata(self):
        """Load metadata from CSV"""
        csv_path = self.csv_file_var.get()
        if not os.path.exists(csv_path):
            messagebox.showerror("Error", f"CSV file not found:\n{csv_path}")
            return
            
        try:
            self.metadata_cache = self.report_generator.load_metadata_from_csv(csv_path)
            self.status_label.config(text=f"Loaded metadata for {len(self.metadata_cache)} dives")
        except Exception as e:
            messagebox.showerror("Error", f"Error loading CSV:\n{e}")
            
    def scan_data_sources(self):
        """Scan data sources for dives"""
        sources = self.data_source_panel.get_sources()
        
        if not sources:
            messagebox.showwarning("Warning", "No data sources added")
            return
            
        self.status_label.config(text="Scanning for dives...")
        self.root.update_idletasks()
        
        try:
            self.current_dives = self.dive_finder.find_dives_in_multiple_folders(sources)
            self.dive_selection_panel.load_dives(self.current_dives)
            
            total_dives = len(self.current_dives)
            with_plots = sum(1 for dives in self.current_dives.values() 
                           if any(d['has_report_plots'] for d in dives))
            
            self.status_label.config(text=f"Found {total_dives} dives ({with_plots} with Report_Plots)")
            
            # Load metadata if not already loaded
            if not self.metadata_cache:
                self.load_metadata()
                
        except Exception as e:
            messagebox.showerror("Error", f"Error scanning for dives:\n{e}")
            self.status_label.config(text="Error scanning")
            
    def update_preview(self):
        """Update preview with first selected dive"""
        selected = self.dive_selection_panel.get_selected_dives()
        
        if not selected:
            self.preview_widget.clear_preview()
            return
            
        # Preview first selected dive
        first_dive = selected[0]
        
        # Try to get metadata with multiple key variations
        dive_name = first_dive['dive_name']
        metadata = self.metadata_cache.get(dive_name, {})
        
        # Try variations if not found
        if not metadata:
            # Try just the dive number part (e.g., DIVE021 from DIVE021_Stokey)
            dive_num_only = dive_name.split('_')[0] if '_' in dive_name else dive_name
            metadata = self.metadata_cache.get(dive_num_only, {})
        
        if not metadata:
            # Still not found, create default
            metadata = {
                'Date': 'Date TBD',
                'Vehicle': 'N/A',
                'Operations Area': 'N/A',
                'Survey Box': 'N/A',
                'Dive Type': 'N/A',
                'Start Time': 'N/A',
                'End Time': 'N/A',
                'Start Location': 'N/A',
                'Total Duration': 'N/A',
                'Linear Distance Covered': 'N/A',
                'Dive Narrative': 'N/A'
            }
            print(f"Warning: No metadata found for {dive_name}, tried {dive_num_only}")
            print(f"Available keys: {list(self.metadata_cache.keys())[:5]}")
        
        # Get images
        images = []
        if first_dive['report_plots_path']:
            images = self.dive_finder.get_images_from_report_plots(first_dive['report_plots_path'])
        
        # Get map folder
        map_folder = self.map_folder_var.get().strip() if self.map_folder_var.get() else ""
        
        self.preview_widget.load_dive_preview(first_dive, metadata, images, map_folder)
        
    def generate_report(self):
        """Generate the report"""
        selected = self.dive_selection_panel.get_selected_dives()
        
        if not selected:
            messagebox.showwarning("Warning", "No dives selected")
            return
            
        output_folder = self.output_folder_var.get()
        if not os.path.exists(output_folder):
            messagebox.showerror("Error", "Output folder does not exist")
            return
            
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"Dive_Report_{timestamp}.docx"
        output_path = os.path.join(output_folder, output_filename)
        
        # Progress dialog
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Generating Report")
        progress_window.geometry("600x400")
        progress_window.transient(self.root)
        
        ttk.Label(progress_window, text="Generating Report...", 
                 font=("Arial", 12, "bold")).pack(pady=10)
        
        progress_text = tk.Text(progress_window, height=20, wrap=tk.WORD)
        progress_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        def log_progress(message):
            progress_text.insert(tk.END, message + "\n")
            progress_text.see(tk.END)
            progress_window.update_idletasks()
        
        # Get map folder (optional)
        map_folder = self.map_folder_var.get().strip()
        
        try:
            log_progress(f"Generating report for {len(selected)} dives...")
            log_progress(f"Output: {output_path}")
            if map_folder:
                log_progress(f"Map folder: {map_folder}")
            log_progress("-" * 50)
            
            success = self.report_generator.generate_report(
                selected, 
                self.metadata_cache, 
                output_path, 
                log_progress,
                map_folder=map_folder
            )
            
            if success:
                log_progress("-" * 50)
                log_progress("Report generated successfully!")
                messagebox.showinfo("Success", f"Report generated:\n{output_path}")
            else:
                messagebox.showerror("Error", "Report generation failed")
                
        except Exception as e:
            log_progress(f"ERROR: {e}")
            messagebox.showerror("Error", f"Error generating report:\n{e}")
        finally:
            ttk.Button(progress_window, text="Close", 
                      command=progress_window.destroy).pack(pady=10)


def main():
    root = tk.Tk()
    app = MainGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
