import os
import glob
import pandas as pd
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

class DiveReportGenerator:
    def __init__(self, base_path="D:\\AUV\\VOYIS\\PC-24-03", 
                 csv_file_path="C:\\Users\\Mike.Bollinger\\Downloads\\AUV_Mission_Log_Draft - Mission_Overview.csv"):
        self.base_path = base_path
        self.csv_file_path = csv_file_path
        
        # Dictionary to map filename patterns to captions
        # Use {dive_name} and {dive_number} as placeholders
        self.caption_mapping = {
            # Navigation and Track plots
            '{dive_name}_map': 'Map of the AUV path for {dive_name}. Map of the AUV path for DIVE003. The trackline of the AUV is shown in a thin black line. Altitude for acquired images is shown by color indicating too low (<4) in yellow, optimal altitude in orange, and too high (>8m) in violet. The start and end of the trackline are labeled, and predefined ground truthing points are shown as standalone green circles.',
            
            
            #Vehicle statistics
            'track_plot': 'AUV track plot for {dive_name} showing the complete mission path.',
            
                    
            # Sonar and SAS plots
            'sas_coverage': 'SAS coverage map for {dive_name} showing sonar data collection areas.',
            'sonar_plot': 'Sonar imagery collected during {dive_name}.',
            'sidescan': 'Side scan sonar data from {dive_name}.',
            
            # Imagery from Voyis
            'top_highlights_panel': 'Example images for {dive_name}.',
            'altitude_histogram': 'Histogram of altitudes of images between 0-50 meters on {dive_name}.',
            'overall_overlap_map': 'Image overlap count for images below altitude threshold for all of {dive_name}.',
            'horizontal_overlap_map': 'Image horizontal overlap percentage for images below altitude threshold for all of {dive_name}.',
            'visibility_analysis': 'Results from the visibility analysis for {dive_name}. Example images are what the model considered the best example from each category.',
            'visibility_analysis': 'Results from the visibility analysis for {dive_name}. Example images are what the model considered the best example from each category.',
            
            # LLS Data from Voyis
            'lls_processing_3cnjkhft_AUV_Dive_Profile': 'Plot showing AUV dive profile in Blue, seafloor in black, and overlaid good and bad data from the laser scan based on agreement between AUV echo sounder and laser scan depth measurements. ',
            'lls_processing_3cnjkhft_AUV_Position': 'AUV track and laser scan coverage where green denotes good laser scan data reaching the seafloor, and red areas are where the laser scan did not reach the seafloor.',
            'lls_processing_3cnjkhft_AUV_Depth_vs_Intensity': 'Laser intensity values for scans that reach the seafloor, shown as a histogram and as intensity vs depth.',
            'lls_processing_3cnjkhft_AUV_Position_Depth_Color': 'Map of good data colored based on water depth. The black line shows the complete AUV track.',    
            'lls_processing_3cnjkhft_AUV_Position_Depth_Deviation_Color': 'Map showing bottom deviations from a spatially averaged depth across 5m. Red positive values indicate emergent objects such as boulders and reefs, '
                'and blue negative values indicate dropoffs or low points in the seafloor. The black line shows the complete AUV track.',
            'lls_processing_3cnjkhft_AUV_Position_Intensity_Color': 'Map showing the return laser reflectance intensity for good data. Large values are associated with strong returns in good water clarity, '
                ' or objects with high reflectance such as hard bottom and low values indicate poor visibility or low reflectance from the seafloor. The black line shows the complete AUV track.',
            
            # Default fallback
            'default': 'Plot from {dive_name} mission data.'
        }
        
    def get_dive_metadata(self):
        """Read dive metadata from local CSV file"""
        try:
            # Read CSV file, skipping the first row (mission info) and using row 2 as headers
            df = pd.read_csv(self.csv_file_path, skiprows=1, header=0)
            
            # Clean up column names (remove extra spaces, etc.)
            df.columns = df.columns.str.strip()
            
            # Convert to dictionary with dive names as keys
            dive_data = {}
            for _, row in df.iterrows():
                # Look for dive identifier in 'Dive' column or first column
                dive_id = None
                if 'Dive' in df.columns:
                    dive_id = str(row['Dive']).strip() if not pd.isna(row['Dive']) else None
                elif len(df.columns) > 0:
                    dive_id = str(row.iloc[0]).strip() if not pd.isna(row.iloc[0]) else None
                
                if dive_id and 'DIVE' in dive_id.upper() and dive_id.upper() != 'DIVE':
                    # Create a clean dictionary with relevant fields
                    clean_data = {}
                    
                    # Map CSV columns to report fields
                    column_mapping = {
                        'Vehicle': 'Vehicle',
                        'Status': 'Dive Type',
                        'Dive Start': 'Start Time', 
                        'Location Start Position': 'Start Location',
                        'Duration': 'Total Duration',
                        'Actual': 'Linear Distance Covered',
                        'Dive Narrative': 'Dive Narrative'
                    }
                    
                    for csv_col, report_field in column_mapping.items():
                        if csv_col in df.columns:
                            value = row[csv_col]
                            if not pd.isna(value) and str(value).strip() != '':
                                clean_data[report_field] = str(value).strip()
                            else:
                                clean_data[report_field] = 'N/A'
                        else:
                            clean_data[report_field] = 'N/A'
                    
                    # Create a date field from start time if available
                    if 'Dive Start' in df.columns and not pd.isna(row['Dive Start']):
                        try:
                            # Try to parse the date from the start time
                            start_time = str(row['Dive Start']).strip()
                            if '/' in start_time:
                                # Format like "6/6/2024 19:42:19"
                                date_part = start_time.split(' ')[0]
                                # Convert to sentence case format
                                from datetime import datetime
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
                    
                    # Handle start location - combine lat/lon if separate columns
                    if 'Location Start Position' not in df.columns:
                        lat_col = None
                        lon_col = None
                        for col in df.columns:
                            if 'latitude' in col.lower() or 'start latitude' in col.lower():
                                lat_col = col
                            elif 'longitude' in col.lower() or 'start longitude' in col.lower():
                                lon_col = col
                        
                        if lat_col and lon_col:
                            lat = row[lat_col] if not pd.isna(row[lat_col]) else ''
                            lon = row[lon_col] if not pd.isna(row[lon_col]) else ''
                            if lat and lon:
                                clean_data['Start Location'] = f"{lat}, {lon}"
                    
                    dive_data[dive_id] = clean_data
            
            print(f"Found metadata for {len(dive_data)} dives: {list(dive_data.keys())}")
            return dive_data
            
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            print(f"Make sure the CSV file '{self.csv_file_path}' exists in the script directory")
            return {}
    
    def find_dive_folders(self):
        """Find all dive folders in the base path"""
        dive_folders = []
        pattern = os.path.join(self.base_path, "DIVE*")
        
        for folder in glob.glob(pattern):
            if os.path.isdir(folder):
                dive_name = os.path.basename(folder)
                report_plots_path = os.path.join(folder, "Report_Plots")
                if os.path.exists(report_plots_path):
                    dive_folders.append({
                        'name': dive_name,
                        'path': folder,
                        'plots_path': report_plots_path
                    })
        
        return sorted(dive_folders, key=lambda x: x['name'])
    
    def create_document(self, title="Dive Post-Mission Analysis"):
        """Create a new Word document"""
        doc = Document()
        
        # Add main title
        title_para = doc.add_heading('Appendix A: Dive Post-Mission Analysis', level=1)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add date note
        date_note = doc.add_paragraph()
        date_note.add_run("Dates in the section headers are ranges taking into account the local or US Central Daylight Time (CDT) ")
        date_note.add_run("and Universal Coordinated Time (UTC) that the dive was started as the \"dive day\". Date and times in the ")
        date_note.add_run("main body represent the UTC for each dive. Each dive day goes over UTC midnight but is still part of ")
        date_note.add_run("the local time dive day.")
        
        return doc
    
    def add_dive_section(self, doc, dive_info, metadata, images, progress_callback=None):
        """Add a dive section to the document"""
        dive_name = dive_info['name']
        
        # Get dive date from metadata or use placeholder
        dive_date = metadata.get('Date', 'Date TBD')
        if pd.isna(dive_date) or dive_date == '':
            dive_date = 'Date TBD'
        
        # Add dive heading (increment section number based on dive number)
        dive_number = dive_name.replace('DIVE', '').replace('dive', '').lstrip('0') or '0'
        heading_text = f"A.{dive_number}. {dive_name} {dive_date}"
        heading = doc.add_heading(heading_text, level=2)
        
        # Add metadata as formatted text
        metadata_items = [
            ('Vehicle', metadata.get('Vehicle', 'N/A')),
            ('Dive Type', metadata.get('Dive Type', 'N/A')),
            ('Start Time', metadata.get('Start Time', 'N/A')),
            ('Start Location', metadata.get('Start Location', 'N/A')),
            ('Total Duration', metadata.get('Total Duration', 'N/A')),
            ('Linear Distance Covered', metadata.get('Linear Distance Covered', 'N/A')),
        ]
        
        for label, value in metadata_items:
            if pd.isna(value) or value == '':
                value = 'N/A'
            para = doc.add_paragraph()
            para.add_run(f"{label}: ").bold = True
            para.add_run(str(value))
            # Set single spacing for metadata paragraphs
            para.paragraph_format.space_after = Pt(0)
            para.paragraph_format.line_spacing = 1.0
        
        # Add dive narrative
        narrative = metadata.get('Dive Narrative', 'N/A')
        if pd.isna(narrative) or narrative == '':
            narrative = 'N/A'
        
        narrative_para = doc.add_paragraph()
        narrative_para.add_run("Dive Narrative: ").bold = True
        narrative_para.add_run(str(narrative))
        # Set single spacing for narrative paragraph
        narrative_para.paragraph_format.space_after = Pt(0)
        narrative_para.paragraph_format.line_spacing = 1.0
        
        # Add images organized by category
        if images:
            # Filter and categorize images
            vehicle_images = []
            imaging_images = []
            laser_images = []
            
            for image_path in images:
                caption_text = self.get_image_caption(image_path, dive_name, dive_number)
                if caption_text is not None:
                    filename = os.path.basename(image_path).lower()
                    
                    # Categorize based on caption dictionary structure
                    if any(key in filename.replace('_', '').replace('-', '') for key in [
                        'gismapplot', 'trackplot', 'sascoverage', 'sonarplot', 'sidescan'
                    ]):
                        vehicle_images.append((image_path, caption_text))
                    elif any(key in filename.replace('_', '').replace('-', '') for key in [
                        'tophighlightspanel', 'altitudehistogram', 'overalloverlapmap', 
                        'horizontaloverlapmap', 'visibilityanalysis'
                    ]):
                        imaging_images.append((image_path, caption_text))
                    elif any(key in filename.replace('_', '').replace('-', '') for key in [
                        'llsprocessing3cnjkhftauvdiveprofile', 'llsprocessing3cnjkhftauvposition',
                        'llsprocessing3cnjkhftauvdepthvsintensity', 'llsprocessing3cnjkhftauvpositiondepthcolor',
                        'llsprocessing3cnjkhftauvpositiondepthdeviationcolor', 'llsprocessing3cnjkhftauvpositionintensitycolor'
                    ]):
                        laser_images.append((image_path, caption_text))
            
            if progress_callback:
                total_included = len(vehicle_images) + len(imaging_images) + len(laser_images)
                excluded_count = len(images) - total_included
                if excluded_count > 0:
                    progress_callback(f"  Excluded {excluded_count} plots not in caption dictionary")
            
            figure_counter = 1
            
            # Vehicle Data Summary section
            if vehicle_images:
                doc.add_paragraph()  # Add space
                vehicle_heading = doc.add_heading('Vehicle Data Summary', level=3)
                
                for image_path, caption_text in vehicle_images:
                    try:
                        doc.add_picture(image_path, width=Inches(6))
                        
                        caption_para = doc.add_paragraph()
                        caption_para.add_run(f"Figure A.{dive_number}.{figure_counter}. ").bold = True
                        caption_para.add_run(caption_text)
                        caption_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        
                        doc.add_paragraph()  # Add space after image
                        figure_counter += 1
                        
                    except Exception as e:
                        print(f"Error adding image {image_path}: {e}")
            
            # Imaging Summary section
            if imaging_images:
                doc.add_paragraph()  # Add space
                imaging_heading = doc.add_heading('Imaging Summary', level=3)
                
                for image_path, caption_text in imaging_images:
                    try:
                        doc.add_picture(image_path, width=Inches(6))
                        
                        caption_para = doc.add_paragraph()
                        caption_para.add_run(f"Figure A.{dive_number}.{figure_counter}. ").bold = True
                        caption_para.add_run(caption_text)
                        caption_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        
                        doc.add_paragraph()  # Add space after image
                        figure_counter += 1
                        
                    except Exception as e:
                        print(f"Error adding image {image_path}: {e}")
            
            # Laser Analysis Summary section
            if laser_images:
                doc.add_paragraph()  # Add space
                laser_heading = doc.add_heading('Laser Analysis Summary', level=3)
                
                for image_path, caption_text in laser_images:
                    try:
                        doc.add_picture(image_path, width=Inches(6))
                        
                        caption_para = doc.add_paragraph()
                        caption_para.add_run(f"Figure A.{dive_number}.{figure_counter}. ").bold = True
                        caption_para.add_run(caption_text)
                        caption_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        
                        doc.add_paragraph()  # Add space after image
                        figure_counter += 1
                        
                    except Exception as e:
                        print(f"Error adding image {image_path}: {e}")
        
        # Add page break after each dive section
        doc.add_page_break()
    
    def generate_report(self, output_filename=None, progress_callback=None, output_folder=None):
        """Main method to generate the complete report"""
        if output_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"Dive_Report_{timestamp}.docx"
            
        if output_folder is None:
            output_folder = os.path.dirname(__file__)
        
        if progress_callback:
            progress_callback("Reading dive metadata from CSV file...")
        metadata = self.get_dive_metadata()
        
        if progress_callback:
            progress_callback("Finding dive folders...")
        dive_folders = self.find_dive_folders()
        
        if not dive_folders:
            error_msg = f"No dive folders found!\nChecked path: {self.base_path}"
            if progress_callback:
                progress_callback(error_msg)
            return None
        
        if progress_callback:
            progress_callback(f"Found {len(dive_folders)} dive folders: {[d['name'] for d in dive_folders]}")
        
        # Create document
        if progress_callback:
            progress_callback("Creating Word document...")
        doc = self.create_document()
        
        # Process each dive
        total_dives = len(dive_folders)
        for idx, dive_info in enumerate(dive_folders, 1):
            if progress_callback:
                progress_callback(f"Processing {dive_info['name']} ({idx}/{total_dives})...")
            
            # Get images from Report_Plots folder
            image_extensions = ['*.png', '*.jpg', '*.jpeg', '*.gif', '*.bmp']
            images = []
            for ext in image_extensions:
                images.extend(glob.glob(os.path.join(dive_info['plots_path'], ext)))
            
            # Sort images by name for consistent ordering
            images.sort()
            if progress_callback:
                progress_callback(f"  Found {len(images)} images for {dive_info['name']}")
            
            # Get metadata for this dive
            dive_metadata = metadata.get(dive_info['name'], {})
            if not dive_metadata:
                if progress_callback:
                    progress_callback(f"  Warning: No metadata found for {dive_info['name']}")
                # Create default metadata
                dive_metadata = {
                    'Date': 'Date TBD',
                    'Vehicle': 'N/A',
                    'Dive Type': 'N/A',
                    'Start Time': 'N/A',
                    'Start Location': 'N/A',
                    'Total Duration': 'N/A',
                    'Linear Distance Covered': 'N/A',
                    'Dive Narrative': 'N/A'
                }
            
            # Add dive section to document
            self.add_dive_section(doc, dive_info, dive_metadata, images, progress_callback)
        
        # Save document
        output_path = os.path.join(output_folder, output_filename)
        doc.save(output_path)
        
        if progress_callback:
            progress_callback(f"Report generated successfully!\nSaved as: {output_path}")
        
        return output_path

    def get_image_caption(self, image_path, dive_name, dive_number):
        """
        Determine the appropriate caption for an image based on its filename
        Returns None if no matching caption is found (indicating plot should be excluded)
        """
        filename = os.path.basename(image_path).lower()
        
        # Check for keywords in filename to determine plot type
        for key, caption_template in self.caption_mapping.items():
            if key == 'default':
                continue
                
            # Check if any of the key words are in the filename
            if key.replace('_', '') in filename.replace('_', '').replace('-', ''):
                return caption_template.format(dive_name=dive_name, dive_number=dive_number)
        
        # Check for common plot types by keywords
        plot_keywords = {
            'nav': 'nav_plot',
            'track': 'track_plot', 
            'altitude': 'altitude_plot',
            'depth': 'depth_plot',
            'bath': 'bathymetry',
            'sas': 'sas_coverage',
            'sonar': 'sonar_plot',
            'sidescan': 'sidescan',
            'coverage': 'coverage_plot',
            'quality': 'data_quality',
            'summary': 'mission_summary',
            'ctd': 'ctd_plot',
            'current': 'current_plot'
        }
        
        for keyword, caption_key in plot_keywords.items():
            if keyword in filename and caption_key in self.caption_mapping:
                return self.caption_mapping[caption_key].format(dive_name=dive_name, dive_number=dive_number)
        
        # Return None if no specific caption found (exclude from report)
        return None
        
    def add_custom_caption_mapping(self, filename_pattern, caption_template):
        """
        Add a custom caption mapping for specific filename patterns
        
        Args:
            filename_pattern (str): Pattern to match in filename (case-insensitive)
            caption_template (str): Caption template with {dive_name} and {dive_number} placeholders
        """
        self.caption_mapping[filename_pattern.lower()] = caption_template
    
    def update_caption_mappings_from_dict(self, caption_dict):
        """
        Update caption mappings from a dictionary
        
        Args:
            caption_dict (dict): Dictionary of filename patterns to caption templates
        """
        for pattern, caption in caption_dict.items():
            self.caption_mapping[pattern.lower()] = caption
    
class ReportGeneratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Dive Report Generator")
        self.root.geometry("600x500")
        
        # Variables for file paths
        self.mission_folder_var = tk.StringVar(value="D:\\AUV\\VOYIS\\PC-24-03")
        self.csv_file_var = tk.StringVar(value="C:\\Users\\Mike.Bollinger\\Downloads\\AUV_Mission_Log_Draft - Mission_Overview.csv")
        self.output_folder_var = tk.StringVar(value=os.path.dirname(__file__))
        
        self.setup_ui()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="Dive Report Generator", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Mission Folder section
        ttk.Label(main_frame, text="Mission Folder:", font=("Arial", 10, "bold")).grid(
            row=1, column=0, sticky=tk.W, pady=(0, 5))
        
        mission_frame = ttk.Frame(main_frame)
        mission_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        
        mission_entry = ttk.Entry(mission_frame, textvariable=self.mission_folder_var, width=50)
        mission_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        mission_browse_btn = ttk.Button(mission_frame, text="Browse", 
                                       command=self.browse_mission_folder)
        mission_browse_btn.grid(row=0, column=1)
        
        mission_frame.columnconfigure(0, weight=1)
        
        # CSV File section
        ttk.Label(main_frame, text="Mission Log Overview CSV:", 
                 font=("Arial", 10, "bold")).grid(row=3, column=0, sticky=tk.W, pady=(0, 5))
        
        csv_frame = ttk.Frame(main_frame)
        csv_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 20))
        
        csv_entry = ttk.Entry(csv_frame, textvariable=self.csv_file_var, width=50)
        csv_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        csv_browse_btn = ttk.Button(csv_frame, text="Browse", 
                                   command=self.browse_csv_file)
        csv_browse_btn.grid(row=0, column=1)
        
        csv_frame.columnconfigure(0, weight=1)
        
        # Output Folder section
        ttk.Label(main_frame, text="Output Folder:", 
                 font=("Arial", 10, "bold")).grid(row=5, column=0, sticky=tk.W, pady=(0, 5))
        
        output_frame = ttk.Frame(main_frame)
        output_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 20))
        
        output_entry = ttk.Entry(output_frame, textvariable=self.output_folder_var, width=50)
        output_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        output_browse_btn = ttk.Button(output_frame, text="Browse", 
                                      command=self.browse_output_folder)
        output_browse_btn.grid(row=0, column=1)
        
        output_frame.columnconfigure(0, weight=1)
        
        # Generate button
        generate_btn = ttk.Button(main_frame, text="Generate Report", 
                                 command=self.generate_report, style="Accent.TButton")
        generate_btn.grid(row=7, column=0, columnspan=3, pady=20)
        
        # Progress text area
        ttk.Label(main_frame, text="Progress:", font=("Arial", 10, "bold")).grid(
            row=8, column=0, sticky=tk.W, pady=(10, 5))
        
        # Create frame for text widget and scrollbar
        text_frame = ttk.Frame(main_frame)
        text_frame.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        self.progress_text = tk.Text(text_frame, height=12, width=70, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.progress_text.yview)
        self.progress_text.configure(yscrollcommand=scrollbar.set)
        
        self.progress_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        # Configure main frame weights
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(9, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
    def browse_mission_folder(self):
        folder = filedialog.askdirectory(
            title="Select Mission Folder",
            initialdir=self.mission_folder_var.get() if os.path.exists(self.mission_folder_var.get()) else "/"
        )
        if folder:
            self.mission_folder_var.set(folder)
            
    def browse_csv_file(self):
        file = filedialog.askopenfilename(
            title="Select Mission Log Overview CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir=os.path.dirname(self.csv_file_var.get()) if os.path.exists(os.path.dirname(self.csv_file_var.get())) else "/"
        )
        if file:
            self.csv_file_var.set(file)
            
    def browse_output_folder(self):
        folder = filedialog.askdirectory(
            title="Select Output Folder",
            initialdir=self.output_folder_var.get() if os.path.exists(self.output_folder_var.get()) else "/"
        )
        if folder:
            self.output_folder_var.set(folder)
            
    def update_progress(self, message):
        self.progress_text.insert(tk.END, message + "\n")
        self.progress_text.see(tk.END)
        self.root.update_idletasks()
        
    def generate_report(self):
        # Validate inputs
        mission_folder = self.mission_folder_var.get().strip()
        csv_file = self.csv_file_var.get().strip()
        output_folder = self.output_folder_var.get().strip()
        
        if not mission_folder:
            messagebox.showerror("Error", "Please select a mission folder.")
            return
            
        if not csv_file:
            messagebox.showerror("Error", "Please select a CSV file.")
            return
            
        if not output_folder:
            messagebox.showerror("Error", "Please select an output folder.")
            return
            
        if not os.path.exists(mission_folder):
            messagebox.showerror("Error", f"Mission folder does not exist:\n{mission_folder}")
            return
            
        if not os.path.exists(csv_file):
            messagebox.showerror("Error", f"CSV file does not exist:\n{csv_file}")
            return
            
        if not os.path.exists(output_folder):
            messagebox.showerror("Error", f"Output folder does not exist:\n{output_folder}")
            return
        
        # Clear progress text
        self.progress_text.delete(1.0, tk.END)
        
        # Create generator and run
        try:
            generator = DiveReportGenerator(base_path=mission_folder, csv_file_path=csv_file)
            
            self.update_progress("Starting report generation...")
            self.update_progress(f"Mission Folder: {mission_folder}")
            self.update_progress(f"CSV File: {csv_file}")
            self.update_progress(f"Output Folder: {output_folder}")
            self.update_progress("-" * 50)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"Dive_Report_{timestamp}.docx"
            
            output_path = generator.generate_report(
                output_filename=output_filename, 
                progress_callback=self.update_progress,
                output_folder=output_folder
            )
            
            if output_path:
                self.update_progress("-" * 50)
                messagebox.showinfo("Success", f"Report generated successfully!\n\nSaved as:\n{output_path}")
            else:
                messagebox.showerror("Error", "Report generation failed. Check the progress log for details.")
                
        except Exception as e:
            error_msg = f"Error generating report: {str(e)}"
            self.update_progress(error_msg)
            messagebox.showerror("Error", error_msg)

def main():
    root = tk.Tk()
    app = ReportGeneratorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()