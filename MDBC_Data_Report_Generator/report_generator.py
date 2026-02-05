"""
Report Generator Module
Handles creation of Word documents from dive data
"""

import os
import pandas as pd
import glob
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from datetime import datetime
from typing import Dict, List, Optional, Callable


class ReportGenerator:
    """Generates Word document reports from dive data"""
    
    def __init__(self):
        # Caption mapping for different plot types
        # Order matters - these define the sequence plots appear in the report
        self.caption_mapping = {
            # Navigation and Motion Analysis
            'nav_motion_analysis': 'Plots showing summaries of AUV navigation and attitude data for {dive_name}. Plots show heave, pitch and roll by geographic coordinates (Row 1), by time (Row 2) and by counts (Row 3). Row 4 shows crab angle and geographic coordinates by depth (m). Vehicle axes of orientation are pitch positive=nose down, roll positive=starboard, heave positive = up.',
            
            # Image Summary Section
            'image_top_highlights': 'Example images from {dive_name}.',
            'image_altitude_histogram': 'Histogram of altitudes of images between 0-50 meters on {dive_name}.',
            
            # Overlap Section
            'image_overall_overlap_map': 'Image overlap count for images below altitude threshold for all of {dive_name}.',
            
            # Visibility Analysis
            'image_visibility_analysis': 'Results from the visibility analysis for {dive_name}. Example images are what the model considered the best example from each category.',
            
            # LLS Section
            'lls_auv_dive_profile': 'Plot showing AUV dive profile in Blue, seafloor in black, and overlaid good and bad data from the laser scan based on agreement between AUV echo sounder and laser scan depth measurements.',
            'lls_auv_position': 'AUV track and laser scan coverage where green denotes good laser scan data reaching the seafloor, and red areas are where the laser scan did not reach the seafloor.',
            'lls_auv_depth_vs_intensity': 'Laser intensity values for scans that reach the seafloor, shown as a histogram and as intensity vs depth.',
            'lls_auv_position_depth_color': 'Map of good data colored based on water depth. The black line shows the complete AUV track.',
            'lls_auv_position_depth_deviation_color': 'Map showing bottom deviations from a spatially averaged depth across 5m. Red positive values indicate emergent objects such as boulders and reefs, and blue negative values indicate dropoffs or low points in the seafloor. The black line shows the complete AUV track.',
            'lls_auv_position_intensity_color': 'Map showing the return laser reflectance intensity for good data. Large values are associated with strong returns in good water clarity, or objects with high reflectance such as hard bottom and low values indicate poor visibility or low reflectance from the seafloor. The black line shows the complete AUV track.',
        }
        
        # Metrics files to include as tables (without figures/captions)
        self.metrics_files = {
            'image_metrics.txt': 'Image Summary Metrics',
            'image_footprint_metrics.txt': 'Image Footprint Metrics',
            'image_overall_overlap_metrics.txt': 'Overall Overlap Metrics',
            'image_vertical_overlap_metrics.txt': 'Vertical Overlap Metrics',
            'image_horizontal_overlap_metrics.txt': 'Horizontal Overlap Metrics'
        }
        
        # Define which metrics to include for each table
        self.metrics_filters = {
            'Image Summary Metrics': [
                'Processed Still Images',
                'Processed Stills Size',
                'Raw Images',
                'Raw Images Size',
                'Total Files',
                'Total Size'
            ],
            'Image Footprint Metrics': [
                'Total Images Analyzed',
                'Average Altitude',
                'Average Width',
                'Average Height',
                'Average Footprint Area',
                'Latitude Range',
                'Longitude Range'
            ],
            'Overall Overlap Metrics': [
                'Total Pairs Checked',
                'Total Overlapping Pairs',
                'Average Overlap Count per Image'
            ],
            'Vertical Overlap Metrics': [
                'Total Overlapping Pairs',
                'Average Overlap'
            ],
            'Horizontal Overlap Metrics': [
                'Total Pairs Checked',
                'Total Overlapping Pairs',
                'Average Overlap'
            ],
            'LLS QuickLook Summary': [
                'Total Run Time',
                'Total size of files',
                'Number of files',
                'Total Points Processed',
                'Percent of Good Points',
                'Average Point Density',
                'Total Dive Time',
                'Total Voyis Time',
                'Total Voyis Time vs Total Dive Time'
            ]
        }
    
    def load_metadata_from_csv(self, csv_path: str) -> Dict[str, Dict]:
        """
        Load dive metadata from CSV file
        Header row is row 2 (index 1), units in row 3 (index 2), data starts row 4 (index 3)
        
        Returns dict with dive names as keys
        """
        try:
            # Read CSV: skip rows 0-2 (mission info, header, units), then set row 1 as header
            # This makes row 2 (index 1) the header, and we skip row 3 (units)
            df = pd.read_csv(csv_path, skiprows=[0, 2], header=0)
            df.columns = df.columns.str.strip()
            
            dive_data = {}
            
            print(f"CSV columns found: {list(df.columns)}")
            print(f"First few dive IDs: {df['Dive'].head() if 'Dive' in df.columns else 'No Dive column'}")
            
            for idx, row in df.iterrows():
                dive_id = None
                
                # Look for dive identifier
                if 'Dive' in df.columns:
                    dive_id = str(row['Dive']).strip() if not pd.isna(row['Dive']) else None
                elif 'Dive ' in df.columns:  # Sometimes has trailing space
                    dive_id = str(row['Dive ']).strip() if not pd.isna(row['Dive ']) else None
                elif len(df.columns) > 1:  # Second column is usually dive number
                    dive_id = str(row.iloc[1]).strip() if not pd.isna(row.iloc[1]) else None
                
                # Validate dive ID format
                if dive_id and 'DIVE' in dive_id.upper() and dive_id.upper() != 'DIVE':
                    clean_data = self._extract_metadata_from_row(row, df.columns)
                    # Store with multiple key variations for flexible matching
                    dive_data[dive_id] = clean_data
                    # Also store with just the dive number (e.g., DIVE021)
                    dive_num_only = dive_id.split('_')[0] if '_' in dive_id else dive_id
                    if dive_num_only != dive_id:
                        dive_data[dive_num_only] = clean_data
                    print(f"Loaded metadata for {dive_id}")
            
            print(f"Total dives loaded: {len(dive_data)}")
            return dive_data
            
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _extract_metadata_from_row(self, row, columns) -> Dict:
        """Extract and clean metadata from CSV row"""
        clean_data = {}
        
        # Store the dive number from CSV for use in title
        # Check for various possible column names
        dive_col = None
        for col_name in ['Dive', 'Dive ', 'Dive Number']:
            if col_name in columns:
                dive_col = col_name
                break
        
        if dive_col:
            dive_num = row[dive_col]
            clean_data['Dive Number'] = str(dive_num).strip() if not pd.isna(dive_num) else 'N/A'
            print(f"DEBUG: Extracted Dive Number = '{clean_data['Dive Number']}' from column '{dive_col}'")
        
        # Map CSV columns to report fields
        column_mapping = {
            'Vehicle': 'Vehicle',
            'Dive Type': 'Dive Type',
            'Dive Start': 'Start Time',
            'Dive End ': 'End Time',  # Note: has trailing space in CSV
            'Dive End': 'End Time',   # Also try without space
            'Duration': 'Total Duration',
            'Actual': 'Linear Distance Covered',
            'Dive Narrative': 'Dive Narrative',
            'Operations Area': 'Operations Area',
            'Survey Box': 'Survey Box'
        }
        
        for csv_col, report_field in column_mapping.items():
            if csv_col in columns:
                value = row[csv_col]
                clean_data[report_field] = str(value).strip() if not pd.isna(value) and str(value).strip() != '' else 'N/A'
            else:
                clean_data[report_field] = 'N/A'
        
        # Build start location from separate lat/lon columns
        # "Location Start Position" is latitude, next unnamed column is longitude
        lat = None
        lon = None
        
        if 'Location Start Position' in columns:
            lat = row['Location Start Position']
            lat = str(lat).strip() if not pd.isna(lat) and str(lat).strip() != '' else None
            
            # Find the longitude column - it's the column after "Location Start Position"
            col_list = list(columns)
            lat_idx = col_list.index('Location Start Position')
            if lat_idx + 1 < len(col_list):
                lon_col = col_list[lat_idx + 1]
                lon = row[lon_col]
                lon = str(lon).strip() if not pd.isna(lon) and str(lon).strip() != '' else None
        
        if lat and lon:
            clean_data['Start Location'] = f"{lat}, {lon}"
        else:
            clean_data['Start Location'] = 'N/A'
        
        # Parse date from start time
        if 'Dive Start' in columns and not pd.isna(row['Dive Start']):
            try:
                start_time = str(row['Dive Start']).strip()
                if '/' in start_time:
                    date_part = start_time.split(' ')[0]
                    try:
                        parsed_date = datetime.strptime(date_part, '%m/%d/%Y')
                        clean_data['Date'] = parsed_date.strftime('%B %d, %Y')
                    except:
                        try:
                            parsed_date = datetime.strptime(date_part, '%m/%d/%y')
                            clean_data['Date'] = parsed_date.strftime('%B %d, %Y')
                        except:
                            clean_data['Date'] = date_part
                else:
                    clean_data['Date'] = 'Date TBD'
            except:
                clean_data['Date'] = 'Date TBD'
        else:
            clean_data['Date'] = 'Date TBD'
        
        return clean_data
    
    def create_document(self, title: str = "Dive Post-Mission Analysis") -> Document:
        """Create a new Word document with title"""
        doc = Document()
        
        # Configure document styles
        # Normal style - Calibri 11pt Black
        normal_style = doc.styles['Normal']
        normal_font = normal_style.font
        normal_font.name = 'Calibri'
        normal_font.size = Pt(11)
        normal_font.color.rgb = RGBColor(0, 0, 0)  # Black
        
        # Heading 1 - Arial 18pt Black
        heading1_style = doc.styles['Heading 1']
        heading1_font = heading1_style.font
        heading1_font.name = 'Arial'
        heading1_font.size = Pt(18)
        heading1_font.color.rgb = RGBColor(0, 0, 0)  # Black
        
        # Heading 2 - Arial 14pt Black
        heading2_style = doc.styles['Heading 2']
        heading2_font = heading2_style.font
        heading2_font.name = 'Arial'
        heading2_font.size = Pt(14)
        heading2_font.color.rgb = RGBColor(0, 0, 0)  # Black
        
        title_para = doc.add_heading('Appendix A: Dive Post-Mission Analysis', level=1)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        date_note = doc.add_paragraph()
        date_note.add_run("Dates in the section headers are ranges taking into account the local or US Central Daylight Time (CDT) ")
        date_note.add_run("and Universal Coordinated Time (UTC) that the dive was started as the \"dive day\". Date and times in the ")
        date_note.add_run("main body represent the UTC for each dive. Each dive day goes over UTC midnight but is still part of ")
        date_note.add_run("the local time dive day.")
        
        return doc
    
    def add_dive_section(self, doc: Document, dive_info: Dict, metadata: Dict, 
                        images: List[str], categorized_images: Dict[str, List[str]] = None,
                        progress_callback: Optional[Callable] = None,
                        map_folder: str = "",
                        vis_maps_folder: str = ""):
        """
        Add a complete dive section to the document
        
        Args:
            doc: Document object
            dive_info: Dict with dive_name, dive_number
            metadata: Dict with dive metadata
            images: List of all image paths
            categorized_images: Optional dict with categorized images (deprecated)
            progress_callback: Optional callback for progress updates
            map_folder: Optional path to folder containing dive maps
            vis_maps_folder: Optional path to folder containing visibility maps
        """
        dive_name = dive_info['dive_name']  # Folder name (for file matching)
        dive_number = dive_info['dive_number'].lstrip('0') or '0'
        
        # Use CSV dive number for title if available, otherwise use folder-based dive number
        csv_dive_number = metadata.get('Dive Number', dive_name)
        print(f"DEBUG: dive_name={dive_name}, csv_dive_number={csv_dive_number}, metadata keys={list(metadata.keys())}")
        
        # Heading
        dive_date = metadata.get('Date', 'Date TBD')
        heading_text = f"A.{dive_number}. {csv_dive_number} - {dive_date}"
        doc.add_heading(heading_text, level=2)
        
        # Metadata
        self._add_metadata_section(doc, metadata)
        
        # Add map after dive narrative (if available)
        if map_folder:
            self._add_dive_map(doc, csv_dive_number, dive_number, 
                              map_folder, progress_callback)
        
        # Build file index for quick lookup
        all_files = {}
        report_plots_path = dive_info.get('report_plots_path', '')
        
        if report_plots_path and os.path.exists(report_plots_path):
            for file in os.listdir(report_plots_path):
                filepath = os.path.join(report_plots_path, file)
                if os.path.isfile(filepath):
                    # Normalize filename for matching
                    normalized = file.lower().replace('_', '').replace('-', '').replace(' ', '')
                    all_files[normalized] = filepath
        
        # Add content in specific order with metrics
        if all_files:
            # Pass both folder name (for file matching) and CSV dive number (for captions)
            # Figure numbering starts at 2 since map is Figure A#.1
            self._add_ordered_content(doc, dive_name, csv_dive_number, dive_number, 
                                     report_plots_path, all_files, progress_callback, vis_maps_folder)
        
        # Page break
        doc.add_page_break()
    
    def _add_metadata_section(self, doc: Document, metadata: Dict):
        """Add metadata section to document"""
        metadata_items = [
            ('Vehicle', metadata.get('Vehicle', 'N/A')),
            ('Operations Area', metadata.get('Operations Area', 'N/A')),
            ('Survey Box', metadata.get('Survey Box', 'N/A')),
            ('Dive Type', metadata.get('Dive Type', 'N/A')),
            ('Start Time', metadata.get('Start Time', 'N/A')),
            ('End Time', metadata.get('End Time', 'N/A')),
            ('Start Location', metadata.get('Start Location', 'N/A')),
            ('Total Duration', metadata.get('Total Duration', 'N/A')),
            ('Linear Distance Covered', metadata.get('Linear Distance Covered', 'N/A')),
        ]
        
        for label, value in metadata_items:
            para = doc.add_paragraph()
            para.add_run(f"{label}: ").bold = True
            para.add_run(str(value) if not pd.isna(value) and value != '' and value != 'N/A' else 'N/A')
            para.paragraph_format.space_after = Pt(0)
            para.paragraph_format.line_spacing = 1.0
        
        # Narrative
        narrative = metadata.get('Dive Narrative', 'N/A')
        narrative_para = doc.add_paragraph()
        narrative_para.add_run("Dive Narrative: ").bold = True
        narrative_para.add_run(str(narrative) if not pd.isna(narrative) and narrative != '' and narrative != 'N/A' else 'N/A')
        narrative_para.paragraph_format.space_after = Pt(0)
        narrative_para.paragraph_format.line_spacing = 1.0
    
    def _add_dive_map(self, doc: Document, csv_dive_number: str, 
                     dive_number: str, map_folder: str, progress_callback: Optional[Callable] = None):
        """
        Add dive map image after the dive narrative section
        
        Args:
            doc: Document object
            csv_dive_number: Dive number from CSV (e.g., DIVE021)
            dive_number: Numeric dive number for figure numbering (e.g., 21)
            map_folder: Path to folder containing dive maps
            progress_callback: Optional callback for progress updates
        """
        if not map_folder or not os.path.exists(map_folder):
            return
        
        # Extract dive number from csv_dive_number (e.g., DIVE021 -> 021)
        dive_num_part = csv_dive_number.upper().replace('DIVE', '').strip()
        
        # Build expected map filename pattern: DIVE###_map (mission agnostic)
        map_filename_pattern = f"DIVE{dive_num_part}_map"
        
        # Search for map file (may have different extensions)
        map_file = None
        for file in os.listdir(map_folder):
            # Check if filename contains the dive pattern
            if map_filename_pattern.lower() in file.lower():
                # Check if it's an image file
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp')):
                    map_file = os.path.join(map_folder, file)
                    break
        
        if not map_file:
            if progress_callback:
                progress_callback(f"  Warning: Map not found for {csv_dive_number} in {map_folder}")
            return
        
        try:
            # Add map image
            doc.add_picture(map_file, width=Inches(6.0))
            
            # Add caption
            caption_text = (f"Map of the AUV path for {csv_dive_number}. "
                          f"The trackline of the AUV is shown in a thin black line. Altitude for "
                          f"acquired images is shown by color indicating too low (<4) in yellow, "
                          f"optimal altitude in orange, and too high (>8m) in violet. The start and "
                          f"end of the trackline are labeled, and predefined ground truthing points "
                          f"are shown as standalone green circles.")
            
            caption_para = doc.add_paragraph()
            caption_para.add_run(f"Figure A{dive_number}.1. ").bold = True
            caption_para.add_run(caption_text)
            caption_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
            caption_para.paragraph_format.space_after = Pt(6)
            

            if progress_callback:
                progress_callback(f"  Added map for {csv_dive_number}")
                
        except Exception as e:
            if progress_callback:
                progress_callback(f"  Error adding map for {csv_dive_number}: {e}")
            print(f"Error adding map {map_file}: {e}")
    
    def _add_visibility_map(self, doc: Document, csv_dive_number: str, 
                           dive_number: str, vis_maps_folder: str, 
                           progress_callback: Optional[Callable] = None,
                           figure_number: int = 2) -> bool:
        """
        Add visibility map image to the document
        
        Args:
            doc: Document object
            csv_dive_number: Dive number from CSV (e.g., DIVE021)
            dive_number: Numeric dive number for figure numbering (e.g., 21)
            vis_maps_folder: Path to folder containing visibility maps
            progress_callback: Optional callback for progress updates
            figure_number: Figure number within the dive section
            
        Returns:
            True if map was successfully added, False otherwise
        """
        if not vis_maps_folder or not os.path.exists(vis_maps_folder):
            if progress_callback:
                progress_callback(f"  Vis maps folder not found: {vis_maps_folder}")
            return False
        
        # Extract dive number from csv_dive_number (e.g., DIVE021 -> 021)
        dive_num_part = csv_dive_number.upper().replace('DIVE', '').strip()
        
        # Build search pattern: just DIVE###
        dive_pattern = f"DIVE{dive_num_part}"
        
        if progress_callback:
            progress_callback(f"  Looking for visibility map containing: {dive_pattern}")
        
        # Search for vis map file - just check if DIVE### appears anywhere in filename
        vis_map_file = None
        for file in os.listdir(vis_maps_folder):
            # Check if dive pattern appears in filename (case insensitive)
            if dive_pattern.upper() in file.upper():
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp')):
                    vis_map_file = os.path.join(vis_maps_folder, file)
                    if progress_callback:
                        progress_callback(f"  Found visibility map: {file}")
                    break
        
        if not vis_map_file:
            if progress_callback:
                progress_callback(f"  No visibility map found for {csv_dive_number} (no file containing '{dive_pattern}')")
            return False
        
        try:
            # Add the visibility map image
            doc.add_picture(vis_map_file, width=Inches(6))
            
            # Add caption
            caption_text = (f"Machine learning visibility analysis map for {csv_dive_number}. "
                          f"Visibility is binned into categories excellent (dark green), good (light green), "
                          f"fair (yellow), poor (orange), and zero (red). The trackline of the AUV is shown "
                          f"in a thin black line. The start and end of the trackline are labeled. Any visibility "
                          f"of the thin black line without colored points indicates images were not taken at that location.")
            
            caption_para = doc.add_paragraph()
            caption_para.add_run(f"Figure A{dive_number}.{figure_number}. ").bold = True
            caption_para.add_run(caption_text)
            caption_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
            caption_para.paragraph_format.space_after = Pt(6)
            
            if progress_callback:
                progress_callback(f"  Added visibility map for {csv_dive_number}")
            
            return True
                
        except Exception as e:
            if progress_callback:
                progress_callback(f"  Error adding visibility map for {csv_dive_number}: {e}")
            print(f"Error adding visibility map {vis_map_file}: {e}")
            return False
    
    def _add_metrics_table(self, doc: Document, metrics_path: str, title: str):
        """Add metrics from text file as a properly formatted table"""
        try:
            if not os.path.exists(metrics_path):
                return
                
            with open(metrics_path, 'r') as f:
                content = f.read().strip()
            
            if not content:
                return
            
            # Add title
            para = doc.add_paragraph()
            para.add_run(title).bold = True
            para.paragraph_format.space_after = Pt(6)
            
            # Parse content into key-value pairs for table
            data_rows = []
            for line in content.split('\n'):
                line = line.strip()
                if not line or '===' in line:
                    continue
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        # Skip empty values
                        if value:
                            data_rows.append((key, value))
            
            if not data_rows:
                return
            
            # Apply filtering if specified
            if title in self.metrics_filters:
                allowed_keys = self.metrics_filters[title]
                filtered_rows = []
                for key, value in data_rows:
                    if key in allowed_keys:
                        filtered_rows.append((key, value))
                data_rows = filtered_rows
            
            if not data_rows:
                return
            
            # Create table with white background and black borders
            table = doc.add_table(rows=len(data_rows), cols=2)
            table.style = 'Table Grid'
            table.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # Populate table
            for i, (key, value) in enumerate(data_rows):
                row = table.rows[i]
                # Label cell
                label_cell = row.cells[0]
                label_cell.text = key
                # Make label bold
                for paragraph in label_cell.paragraphs:
                    for run in paragraph.runs:
                        run.bold = True
                
                # Value cell
                value_cell = row.cells[1]
                value_cell.text = value
            
            # Reduced space after table
            doc.add_paragraph().paragraph_format.space_after = Pt(0)
            
        except Exception as e:
            print(f"Error reading metrics file {metrics_path}: {e}")
    
    def _add_lls_quicklook_table(self, doc: Document, report_plots_path: str, dive_folder_name: str):
        """Add LLS QuickLook Summary as a table"""
        try:
            # Search for LLS QuickLook Summary file
            pattern = os.path.join(report_plots_path, f"*_LLS_Voyis_QuickLook_Summary.txt")
            matching_files = glob.glob(pattern)
            
            if not matching_files:
                return
            
            quicklook_path = matching_files[0]
            
            # Use the standard metrics table method with filtering
            self._add_metrics_table(doc, quicklook_path, 'LLS QuickLook Summary')
            
        except Exception as e:
            print(f"Error adding LLS QuickLook Summary: {e}")
    
    def _add_ordered_content(self, doc: Document, dive_folder_name: str, csv_dive_number: str,
                            dive_number: str, report_plots_path: str, all_files: Dict[str, str],
                            progress_callback: Optional[Callable], vis_maps_folder: str = ""):
        """
        Add content in specific order with metrics tables interspersed
        dive_folder_name: folder name for file matching
        csv_dive_number: dive number from CSV for captions (e.g., 'DIVE021')
        dive_number: numeric dive number for figure numbering (e.g., '21')
        all_files: dict mapping normalized filename to full path
        vis_maps_folder: optional path to folder containing visibility maps
        """
        # Start at 2 since map is Figure A#.1
        figure_counter = 2
        
        # Define the exact order of content
        ordered_items = [
            # Navigation Section
            ('nav_motion_analysis', 'image', 'Navigation and Motion Analysis'),
            
            # Image Summary Section
            ('image_summary', 'heading', 'Image Summary'),
            ('image_metrics.txt', 'metrics', 'Image Summary Metrics'),
            ('image_top_highlights', 'image', None),
            ('image_altitude_histogram', 'image', None),
            
            # Overlap Section
            ('overlap_analysis', 'heading', 'Overlap Analysis'),
            ('image_footprint_metrics.txt', 'metrics', 'Image Footprint Metrics'),
            ('image_overall_overlap_metrics.txt', 'metrics', 'Overall Overlap Metrics'),
            ('image_vertical_overlap_metrics.txt', 'metrics', 'Vertical Overlap Metrics'),
            ('image_horizontal_overlap_metrics.txt', 'metrics', 'Horizontal Overlap Metrics'),
            ('image_overall_overlap_map', 'image', None),
            
            # Visibility Section
            ('visibility_analysis', 'heading', 'Visibility Analysis'),
            ('visibility_map', 'vis_map', None),
            ('image_visibility_analysis', 'image', None),
            
            # LLS Section
            ('lls_analysis', 'heading', 'Laser Line Scan Analysis'),
            ('lls_quicklook', 'lls_metrics', None),
            ('lls_auv_dive_profile', 'image', None),
            ('lls_auv_position', 'image', None),
            ('lls_auv_depth_vs_intensity', 'image', None),
            ('lls_auv_position_depth_color', 'image', None),
            ('lls_auv_position_depth_deviation_color', 'image', None),
            ('lls_auv_position_intensity_color', 'image', None),
        ]
        
        for item_key, item_type, item_title in ordered_items:
            if item_type == 'heading':
                doc.add_heading(item_title, level=3)
                
            elif item_type == 'metrics':
                # Look for metrics file in report_plots_path
                metrics_path = os.path.join(report_plots_path, item_key)
                # Also try with dive prefix (using folder name for file matching)
                if not os.path.exists(metrics_path):
                    metrics_path = os.path.join(report_plots_path, f"{dive_folder_name}_{item_key}")
                
                self._add_metrics_table(doc, metrics_path, item_title)
                
            elif item_type == 'lls_metrics':
                # Handle LLS QuickLook Summary
                self._add_lls_quicklook_table(doc, report_plots_path, dive_folder_name)
            
            elif item_type == 'vis_map':
                # Handle visibility map from separate folder
                if vis_maps_folder:
                    if self._add_visibility_map(doc, csv_dive_number, dive_number, vis_maps_folder, progress_callback, figure_counter):
                        figure_counter += 1
                
            elif item_type == 'image':
                # Look for matching image file (using folder name for file matching)
                image_path = self._find_matching_image(item_key, all_files, dive_folder_name)
                
                if image_path:
                    # Use CSV dive number for caption
                    caption = self.get_image_caption(image_path, csv_dive_number, dive_number)
                    if caption:
                        try:
                            doc.add_picture(image_path, width=Inches(6))
                            
                            caption_para = doc.add_paragraph()
                            caption_para.add_run(f"Figure A{dive_number}.{figure_counter}. ").bold = True
                            caption_para.add_run(caption)
                            caption_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
                            caption_para.paragraph_format.space_after = Pt(6)
                            
                            figure_counter += 1
                        except Exception as e:
                            if progress_callback:
                                progress_callback(f"  Error adding image {os.path.basename(image_path)}: {e}")
    
    def _find_matching_image(self, key: str, all_files: Dict[str, str], dive_name: str) -> Optional[str]:
        """Find image file matching the key, checking with and without dive prefix"""
        key_normalized = key.replace('_', '').replace('-', '').replace(' ', '').lower()
        
        # Try exact match first
        if key_normalized in all_files:
            return all_files[key_normalized]
        
        # Try with dive prefix
        dive_prefix = dive_name.lower().replace('_', '').replace('-', '').replace(' ', '')
        prefixed_key = dive_prefix + key_normalized
        if prefixed_key in all_files:
            return all_files[prefixed_key]
        
        # Try partial match
        for norm_filename, filepath in all_files.items():
            if key_normalized in norm_filename:
                return filepath
        
        return None
    
    def _add_categorized_images(self, doc: Document, dive_name: str, dive_number: str,
                               categorized: Dict[str, List[str]], progress_callback: Optional[Callable]):
        """DEPRECATED: Use _add_ordered_content instead"""
        pass
    
    def _add_images_section(self, doc: Document, dive_name: str, dive_number: str,
                           images: List[str], progress_callback: Optional[Callable]):
        """Add images without categorization"""
        figure_counter = 1
        
        for image_path in images:
            caption = self.get_image_caption(image_path, dive_name, dive_number)
            if caption:
                try:
                    doc.add_picture(image_path, width=Inches(6))
                    
                    caption_para = doc.add_paragraph()
                    caption_para.add_run(f"Figure A.{dive_number}.{figure_counter}. ").bold = True
                    caption_para.add_run(caption)
                    caption_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    
                    doc.add_paragraph()
                    figure_counter += 1
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"  Error adding image {os.path.basename(image_path)}: {e}")
    def get_image_caption(self, image_path: str, csv_dive_number: str, dive_number: str) -> Optional[str]:
        """
        Get caption for an image based on filename
        csv_dive_number: dive number from CSV (e.g., 'DIVE021') for use in captions
        dive_number: numeric dive number (e.g., '21') for figure numbering
        """
        filename = os.path.basename(image_path).lower()
        filename_normalized = filename.replace('_', '').replace('-', '').replace(' ', '')
        
        # Check caption mapping
        for key, caption_template in self.caption_mapping.items():
            if key == 'default':
                continue
            key_normalized = key.replace('_', '').replace('-', '').replace(' ', '')
            if key_normalized in filename_normalized:
                # Use CSV dive number in captions
                return caption_template.format(dive_name=csv_dive_number, dive_number=dive_number)
        
        # Return None if no match (exclude from report)
        return None
    
    def generate_report(self, selected_dives: List[Dict], metadata_dict: Dict[str, Dict],
                       output_path: str, progress_callback: Optional[Callable] = None,
                       map_folder: str = "", vis_maps_folder: str = "") -> bool:
        """
        Generate complete report for selected dives
        
        Args:
            selected_dives: List of dive info dicts
            metadata_dict: Dict mapping dive names to metadata
            output_path: Full path for output file
            progress_callback: Optional callback for progress updates
            map_folder: Optional path to folder containing dive maps
            vis_maps_folder: Optional path to folder containing visibility maps
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc = self.create_document()
            
            for idx, dive_info in enumerate(selected_dives, 1):
                if progress_callback:
                    progress_callback(f"Processing {dive_info['dive_name']} ({idx}/{len(selected_dives)})...")
                
                # Get metadata with flexible matching
                dive_name = dive_info['dive_name']
                metadata = metadata_dict.get(dive_name, {})
                
                # Try variations if not found
                if not metadata:
                    dive_num_only = dive_name.split('_')[0] if '_' in dive_name else dive_name
                    metadata = metadata_dict.get(dive_num_only, {})
                
                if not metadata:
                    if progress_callback:
                        progress_callback(f"  Warning: No metadata found for {dive_name}")
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
                
                # Get images
                images = []
                if dive_info.get('report_plots_path'):
                    from dive_finder import DiveFinder
                    finder = DiveFinder()
                    images = finder.get_images_from_report_plots(dive_info['report_plots_path'])
                    categorized = finder.categorize_images(images)
                    
                    self.add_dive_section(doc, dive_info, metadata, images, categorized, 
                                        progress_callback, map_folder, vis_maps_folder)
                else:
                    if progress_callback:
                        progress_callback(f"  Warning: No Report_Plots folder for {dive_info['dive_name']}")
                    self.add_dive_section(doc, dive_info, metadata, [], None, 
                                        progress_callback, map_folder, vis_maps_folder)
            
            # Save document
            doc.save(output_path)
            
            if progress_callback:
                progress_callback(f"Report saved successfully: {output_path}")
            
            return True
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error generating report: {e}")
            return False
