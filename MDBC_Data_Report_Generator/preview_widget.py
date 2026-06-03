"""
Preview Widget Module
Creates an 8.5x11" preview canvas for QAQC of dive reports
"""

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import os
from typing import Dict, List, Optional


class PreviewWidget(ttk.Frame):
    """
    Preview pane that shows a dive report page at 8.5x11" proportions
    """
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        # 8.5 x 11 inch aspect ratio (scaled for laptop screens)
        self.page_width = 580  # pixels (scaled down)
        self.page_height = 1000  # pixels (scaled down)
        self.dpi_scale = 100  # 100 pixels per inch for display
        
        self.current_dive = None
        self.current_metadata = None
        self.current_images = []
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the preview UI"""
        # Title
        title_frame = ttk.Frame(self)
        title_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(title_frame, text="Preview (First Dive)", 
                 font=("Arial", 12, "bold")).pack(side=tk.LEFT)
        
        self.dive_label = ttk.Label(title_frame, text="No dive selected", 
                                    font=("Arial", 10))
        self.dive_label.pack(side=tk.LEFT, padx=10)
        
        # Canvas frame with scrollbar
        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Canvas with white background (paper)
        self.canvas = tk.Canvas(canvas_frame, 
                               width=self.page_width,
                               height=self.page_height,
                               bg='white',
                               yscrollcommand=scrollbar.set,
                               highlightthickness=1,
                               highlightbackground='gray')
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar.config(command=self.canvas.yview)
        
        # Configure scrollregion
        self.canvas.configure(scrollregion=(0, 0, self.page_width, self.page_height * 3))
        
    def load_dive_preview(self, dive_info: Dict, metadata: Dict, images: List[str], 
                          map_folder: str = "", vis_maps_folder: str = ""):
        """
        Load a dive preview
        
        Args:
            dive_info: Dict with dive_name, dive_number, etc.
            metadata: Dict with dive metadata (date, vehicle, duration, etc.)
            images: List of image paths to display
            map_folder: Optional path to folder containing dive maps
            vis_maps_folder: Optional path to folder containing visibility maps
        """
        self.current_dive = dive_info
        self.current_metadata = metadata
        self.current_images = images
        self.map_folder = map_folder
        self.vis_maps_folder = vis_maps_folder
        
        # Update title
        self.dive_label.config(text=f"{dive_info['dive_name']} - {len(images)} files")
        
        # Clear canvas
        self.canvas.delete("all")
        
        # Clear image refs
        if hasattr(self, 'image_refs'):
            self.image_refs.clear()
        
        # Render preview
        self._render_preview()
        
    def _render_preview(self):
        """Render the dive report preview on canvas"""
        if not self.current_dive or not self.current_metadata:
            self.canvas.create_text(self.page_width // 2, 100,
                                   text="No dive selected for preview",
                                   font=("Arial", 14),
                                   fill='gray')
            return
            
        y_pos = 20
        margin = 40
        content_width = self.page_width - (2 * margin)
        
        # Title - use CSV dive number if available
        dive_name = self.current_dive['dive_name']
        csv_dive_number = self.current_metadata.get('Dive Number', dive_name)
        dive_date = self.current_metadata.get('Date', 'Date TBD')
        title_text = f"{csv_dive_number} - {dive_date}"
        
        self.canvas.create_text(self.page_width // 2, y_pos,
                               text=title_text,
                               font=("Arial", 16, "bold"),
                               anchor=tk.N)
        y_pos += 40
        
        # Metadata section
        raw_dist = self.current_metadata.get('Linear Distance Covered', 'N/A')
        if raw_dist not in ('N/A', '', None):
            try:
                dist_display = f"{float(str(raw_dist).replace(',', '')) / 1000:.1f}km"
            except (ValueError, TypeError):
                dist_display = str(raw_dist)
        else:
            dist_display = 'N/A'

        raw_pct = self.current_metadata.get('Percentage of Usable Images', 'N/A')
        if raw_pct not in ('N/A', '', None):
            try:
                pct_display = f"{float(str(raw_pct).replace('%', '').strip()):.1f}%"
            except (ValueError, TypeError):
                pct_display = str(raw_pct)
        else:
            pct_display = 'N/A'

        metadata_items = [
            ('Dive Type', self.current_metadata.get('Dive Type', 'N/A')),
            ('Start Time', self.current_metadata.get('Start Time', 'N/A')),
            ('Start Location', self.current_metadata.get('Start Location', 'N/A')),
            ('Total Duration', self.current_metadata.get('Total Duration', 'N/A')),
            ('Distance Covered', dist_display),
            ('Usable Images', pct_display),
        ]
        
        for label, value in metadata_items:
            # Bold label, normal value
            self.canvas.create_text(margin, y_pos,
                                   text=f"{label}: ",
                                   font=("Arial", 9, "bold"),
                                   anchor=tk.W)
            label_width = len(label) * 6 + 16  # approximate bold label pixel width
            self.canvas.create_text(margin + label_width, y_pos,
                                   text=str(value),
                                   font=("Arial", 9),
                                   anchor=tk.W)
            y_pos += 18
        
        # Narrative
        narrative = self.current_metadata.get('Dive Narrative', 'N/A')
        self.canvas.create_text(margin, y_pos,
                               text="Dive Narrative:",
                               font=("Arial", 9, "bold"),
                               anchor=tk.W)
        y_pos += 18
        
        # Wrap narrative text
        narrative_lines = self._wrap_text(str(narrative), content_width - 20, ("Arial", 9))
        for line in narrative_lines:
            self.canvas.create_text(margin + 10, y_pos,
                                   text=line,
                                   font=("Arial", 9),
                                   anchor=tk.W)
            y_pos += 16
        
        y_pos += 20
        
        # Add dive map if available
        if hasattr(self, 'map_folder') and self.map_folder and os.path.exists(self.map_folder):
            map_file = self._find_map_file(csv_dive_number)
            if map_file:
                y_pos = self._add_image_to_canvas(map_file, y_pos, margin, content_width,
                                                  f"Figure 1. Map of the AUV path for {csv_dive_number}")
        
        # Categorize images
        vehicle_images = []
        imaging_images = []
        visibility_images = []
        laser_images = []
        
        for image_path in self.current_images:
            if not image_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                continue  # Skip non-image files (like .txt)
                
            filename = os.path.basename(image_path).lower()
            filename_normalized = filename.replace('_', '').replace('-', '')
            
            # Categorize based on report_generator.py ordered_items
            # Only include what's actually in the report
            if 'navmotionanalysis' in filename_normalized:
                vehicle_images.append(image_path)
            elif 'imagevisibility' in filename_normalized:
                visibility_images.append(image_path)
            elif any(key in filename_normalized for key in [
                'imagetophighlights', 'imagealtitudehistogram', 'imageoverall',
                'imagefootprint', 'imagehorizontal', 'imagevertical'
            ]):
                imaging_images.append(image_path)
            elif any(key in filename_normalized for key in [
                'llsauvdiveprofile', 'llsauvposition', 'llsauvdepth', 'llsauvintensity', 'llsauvdeviation'
            ]):
                laser_images.append(image_path)
        
        figure_num = 2  # Start at 2 since map is figure 1
        
        # Vehicle Data Summary section
        if vehicle_images:
            self.canvas.create_text(margin, y_pos,
                                   text="Vehicle Data Summary",
                                   font=("Arial", 12, "bold"),
                                   anchor=tk.W,
                                   fill='#2c3e50')
            y_pos += 30
            
            # Show first 3 vehicle images
            for img_path in vehicle_images[:3]:
                caption = f"Figure {figure_num}. {os.path.basename(img_path)}"
                y_pos = self._add_image_to_canvas(img_path, y_pos, margin, content_width, caption)
                figure_num += 1
            
            if len(vehicle_images) > 3:
                self.canvas.create_text(self.page_width // 2, y_pos,
                                       text=f"... and {len(vehicle_images) - 3} more vehicle plots",
                                       font=("Arial", 9, "italic"),
                                       fill='gray')
                y_pos += 25
        
        # Imaging Summary section
        if imaging_images:
            y_pos += 20
            self.canvas.create_text(margin, y_pos,
                                   text="Imaging Summary",
                                   font=("Arial", 12, "bold"),
                                   anchor=tk.W,
                                   fill='#2c3e50')
            y_pos += 30
            
            # Show first 3 imaging images
            for img_path in imaging_images[:3]:
                caption = f"Figure {figure_num}. {os.path.basename(img_path)}"
                y_pos = self._add_image_to_canvas(img_path, y_pos, margin, content_width, caption)
                figure_num += 1
            
            if len(imaging_images) > 3:
                self.canvas.create_text(self.page_width // 2, y_pos,
                                       text=f"... and {len(imaging_images) - 3} more imaging plots",
                                       font=("Arial", 9, "italic"),
                                       fill='gray')
                y_pos += 25
        
        # Visibility Analysis section
        if visibility_images or (hasattr(self, 'vis_maps_folder') and self.vis_maps_folder):
            y_pos += 20
            self.canvas.create_text(margin, y_pos,
                                   text="Visibility Analysis",
                                   font=("Arial", 12, "bold"),
                                   anchor=tk.W,
                                   fill='#2c3e50')
            y_pos += 30
            
            # Add visibility map if available
            if hasattr(self, 'vis_maps_folder') and self.vis_maps_folder:
                vis_map_file = self._find_vis_map_file(csv_dive_number)
                if vis_map_file:
                    caption = f"Figure {figure_num}. Visibility Map for {csv_dive_number}"
                    y_pos = self._add_image_to_canvas(vis_map_file, y_pos, margin, content_width, caption)
                    figure_num += 1
            
            # Show visibility analysis images
            for img_path in visibility_images[:2]:
                caption = f"Figure {figure_num}. {os.path.basename(img_path)}"
                y_pos = self._add_image_to_canvas(img_path, y_pos, margin, content_width, caption)
                figure_num += 1
            
            if len(visibility_images) > 2:
                self.canvas.create_text(self.page_width // 2, y_pos,
                                       text=f"... and {len(visibility_images) - 2} more visibility plots",
                                       font=("Arial", 9, "italic"),
                                       fill='gray')
                y_pos += 25
        
        # Laser Analysis Summary section
        if laser_images:
            y_pos += 20
            self.canvas.create_text(margin, y_pos,
                                   text="Laser Analysis Summary",
                                   font=("Arial", 12, "bold"),
                                   anchor=tk.W,
                                   fill='#2c3e50')
            y_pos += 30
            
            # Show first 3 laser images
            for img_path in laser_images[:3]:
                caption = f"Figure {figure_num}. {os.path.basename(img_path)}"
                y_pos = self._add_image_to_canvas(img_path, y_pos, margin, content_width, caption)
                figure_num += 1
            
            if len(laser_images) > 3:
                self.canvas.create_text(self.page_width // 2, y_pos,
                                       text=f"... and {len(laser_images) - 3} more laser plots",
                                       font=("Arial", 9, "italic"),
                                       fill='gray')
                y_pos += 25
        
        # Show summary
        total_shown = (min(3, len(vehicle_images)) + min(3, len(imaging_images)) + 
                      min(2, len(visibility_images)) + min(3, len(laser_images)))
        total_images = len(vehicle_images) + len(imaging_images) + len(visibility_images) + len(laser_images)
        
        # Count maps
        maps_count = 0
        if hasattr(self, 'map_folder') and self.map_folder and self._find_map_file(csv_dive_number):
            maps_count += 1
        if hasattr(self, 'vis_maps_folder') and self.vis_maps_folder and self._find_vis_map_file(csv_dive_number):
            maps_count += 1
        
        if total_images > total_shown:
            y_pos += 30
            self.canvas.create_text(self.page_width // 2, y_pos,
                                   text=f"Preview showing {total_shown + maps_count} of {total_images + maps_count} total figures",
                                   font=("Arial", 10, "bold"),
                                   fill='#34495e')
            y_pos += 30
        
        # Update scroll region to fit content
        self.canvas.configure(scrollregion=(0, 0, self.page_width, y_pos + 50))
    
    def _find_map_file(self, csv_dive_number: str) -> Optional[str]:
        """Find map file for the dive"""
        if not self.map_folder or not os.path.exists(self.map_folder):
            return None
        
        # Extract dive number from csv_dive_number (e.g., DIVE021 -> 021)
        dive_num_part = csv_dive_number.upper().replace('DIVE', '').strip()
        
        # Build expected map filename pattern
        map_filename_pattern = f"DIVE{dive_num_part}_map"
        
        # Search for map file
        for file in os.listdir(self.map_folder):
            if map_filename_pattern.lower() in file.lower():
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp')):
                    return os.path.join(self.map_folder, file)
        
        return None
    
    def _find_vis_map_file(self, csv_dive_number: str) -> Optional[str]:
        """Find visibility map file for the dive - matches any file containing DIVE### in filename"""
        if not hasattr(self, 'vis_maps_folder') or not self.vis_maps_folder or not os.path.exists(self.vis_maps_folder):
            return None
        
        dive_num_part = csv_dive_number.upper().replace('DIVE', '').strip()
        dive_pattern = f"DIVE{dive_num_part}"
        
        for file in os.listdir(self.vis_maps_folder):
            if dive_pattern.upper() in file.upper():
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp')):
                    return os.path.join(self.vis_maps_folder, file)
        
        return None
    
    def _add_image_to_canvas(self, img_path: str, y_pos: int, margin: int, 
                            content_width: int, caption: str) -> int:
        """
        Add an image to the canvas and return the new y position
        
        Args:
            img_path: Path to image file
            y_pos: Current y position on canvas
            margin: Left/right margin
            content_width: Available width for content
            caption: Caption text for the image
            
        Returns:
            New y position after adding image and caption
        """
        try:
            img = Image.open(img_path)
            
            # Scale to fit width
            max_width = content_width
            max_height = 350
            
            img_ratio = img.width / img.height
            target_width = min(max_width, img.width)
            target_height = int(target_width / img_ratio)
            
            if target_height > max_height:
                target_height = max_height
                target_width = int(target_height * img_ratio)
            
            img_resized = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img_resized)
            
            # Keep reference to avoid garbage collection
            if not hasattr(self, 'image_refs'):
                self.image_refs = []
            self.image_refs.append(photo)
            
            # Center image
            x_pos = self.page_width // 2
            self.canvas.create_image(x_pos, y_pos + target_height // 2,
                                    image=photo,
                                    anchor=tk.N)
            y_pos += target_height + 10
            
            # Caption
            caption_lines = self._wrap_text(caption, content_width, ("Arial", 8))
            for line in caption_lines:
                self.canvas.create_text(self.page_width // 2, y_pos,
                                       text=line,
                                       font=("Arial", 8, "italic"),
                                       anchor=tk.N)
                y_pos += 14
            
            y_pos += 25
            
        except Exception as e:
            # Show error message
            error_text = f"[Error loading {os.path.basename(img_path)}]"
            self.canvas.create_text(self.page_width // 2, y_pos,
                                   text=error_text,
                                   font=("Arial", 8, "italic"),
                                   fill='red')
            y_pos += 30
            print(f"Preview error for {img_path}: {e}")
        
        return y_pos
        
    def _wrap_text(self, text: str, max_width: int, font: tuple) -> List[str]:
        """Wrap text to fit within max_width"""
        # Simple word wrapping
        words = text.split()
        lines = []
        current_line = []
        
        # Estimate character width (rough approximation)
        char_width = 7 if font[1] == 9 else 6
        max_chars = max_width // char_width
        
        for word in words:
            if len(' '.join(current_line + [word])) <= max_chars:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
            
        return lines if lines else [text]
    
    def clear_preview(self):
        """Clear the preview canvas"""
        self.canvas.delete("all")
        self.dive_label.config(text="No dive selected")
        self.current_dive = None
        self.current_metadata = None
        self.current_images = []
        if hasattr(self, 'image_refs'):
            self.image_refs.clear()
