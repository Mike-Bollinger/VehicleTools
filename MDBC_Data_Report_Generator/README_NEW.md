# Dive Report Generator - Enhanced Version

## Overview

This enhanced version of the Dive Report Generator provides a modern, modular interface for creating professional Word document reports from AUV dive data. It includes a preview pane for quality control, flexible data source management, and smart dive number matching across multiple locations.

## Features

### 🎯 Key Enhancements

1. **Preview Pane**: View the first selected dive on an 8.5x11" canvas for QAQC before generating the full report
2. **Flexible Data Sources**: Add multiple folders from different drives/locations
3. **Smart Dive Matching**: Automatically finds and matches dive folders across data sources
4. **Checkbox Selection**: Easy dive selection with "Select All" / "Deselect All" buttons
5. **Recursive Scanning**: Finds dive folders and Report_Plots anywhere in your data hierarchy
6. **Status Indicators**: Visual feedback showing which dives have Report_Plots folders

### 📋 Report Contents

Each dive section includes:
- Dive metadata (vehicle, start time, location, duration, distance)
- Dive narrative
- Organized plots in three categories:
  - **Vehicle Data Summary**: Navigation, track plots, sonar/SAS coverage
  - **Imaging Summary**: Camera data, altitude histograms, overlap maps, visibility analysis
  - **Laser Analysis Summary**: LLS processing plots (dive profile, position, intensity, depth deviation)

## Installation

### Requirements

- Python 3.7+
- Required packages (install via requirements.txt)

### Setup

1. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

2. **Verify installation:**
   ```powershell
   python main.py
   ```

## Usage

### Running the Application

**Main Entry Point:**
```powershell
python main.py
```

This launches the enhanced GUI with all features.

### Workflow

1. **Load Mission Log CSV**
   - Browse to your CSV file (e.g., `EN2501_AUV_Mission_Log_IMAGING_LASER - Mission_Overview.csv`)
   - Click "Load" to import dive metadata

2. **Add Data Sources**
   - Click "Add Folder" to add data directories
   - Add multiple sources (e.g., `E:\EN2501\Image_LLS`, `Q:\EN2501\Image_LLS`)
   - The system will automatically merge data from multiple sources for the same dive

3. **Scan for Dives**
   - Click "Scan for Dives" to recursively search all data sources
   - View results in the dive selection tree
   - Status column shows whether Report_Plots folder exists

4. **Select Dives**
   - Check/uncheck individual dives by clicking on them
   - Use "Select All" / "Deselect All" for batch operations
   - Preview pane automatically updates to show the first selected dive

5. **Preview First Dive**
   - Review metadata and sample plots in the 8.5x11" preview pane
   - Verify captions and plot order before generating full report
   - Scroll through the preview to see layout

6. **Generate Report**
   - Choose output folder
   - Click "Generate Report"
   - Monitor progress in the dialog
   - Report saved with timestamp: `Dive_Report_YYYYMMDD_HHMMSS.docx`

## Project Structure

```
MDBC_Data_Report_Generator/
├── main.py                    # Main entry point (run this)
├── main_gui.py               # Main GUI application
├── dive_finder.py            # Dive folder discovery and scanning
├── report_generator.py       # Word document generation
├── preview_widget.py         # Preview pane component
├── requirements.txt          # Python dependencies
├── README_NEW.md            # This file
└── MDBC_Data_Report_Generator.py  # Original monolithic version (kept for reference)
```

## Module Descriptions

### `main.py`
Entry point that checks dependencies and launches the application.

### `main_gui.py`
Main GUI with:
- Data source management panel
- Dive selection tree with checkboxes
- Preview pane integration
- Report generation controls

### `dive_finder.py`
Handles:
- Recursive folder scanning for DIVE* folders
- Report_Plots folder detection
- Multi-source dive merging
- Image categorization (vehicle/imaging/laser)

### `report_generator.py`
Handles:
- CSV metadata parsing
- Word document creation
- Image caption mapping
- Categorized plot insertion

### `preview_widget.py`
Provides:
- 8.5x11" proportional canvas
- Dive metadata display
- Image previews with captions
- Scrollable content

## Configuration

### Default Paths

Update in `main_gui.py` line ~460:
```python
default_sources = [
    "E:\\EN2501\\Image_LLS",
    "Q:\\EN2501\\Image_LLS"
]
```

### CSV Path

Default CSV path can be changed in `main_gui.py` line ~421:
```python
self.csv_file_var = tk.StringVar(value="C:\\Users\\...\\Mission_Overview.csv")
```

### Caption Mapping

Customize plot captions in `report_generator.py` starting at line ~18 in the `caption_mapping` dictionary.

## Data Requirements

### Expected Folder Structure

```
DataSource/
├── DIVE001/
│   ├── Report_Plots/
│   │   ├── DIVE001_map.png
│   │   ├── altitude_histogram.png
│   │   ├── lls_processing_3cnjkhft_AUV_Position.png
│   │   └── ...
│   └── [other dive data]
├── DIVE002/
│   └── Report_Plots/
└── ...
```

### CSV Format

Expected columns (first row skipped, second row as headers):
- `Dive`: Dive identifier (e.g., "DIVE001")
- `Vehicle`: AUV name
- `Status`: Dive type/status
- `Dive Start`: Start timestamp
- `Location Start Position`: Start coordinates
- `Duration`: Mission duration
- `Actual`: Linear distance covered
- `Dive Narrative`: Mission description

## Troubleshooting

### "No dives found"
- Verify data source folders exist and are readable
- Check that folders contain "DIVE" in their name (case-insensitive)
- Try "Scan for Dives" again after adding sources

### "No Report_Plots folder"
- Dives without Report_Plots will show a warning icon
- They can still be selected but won't include images
- Check that the Report_Plots subfolder exists in the dive folder

### Preview not showing images
- Verify image files are PNG, JPG, or other supported formats
- Check file permissions
- Large images may take time to load

### Missing metadata
- Ensure CSV file path is correct
- Click "Load" after browsing to a new CSV
- Check CSV has the expected column structure

## Advanced Usage

### Adding Custom Caption Mappings

Edit `report_generator.py` caption_mapping to add new plot types:

```python
self.caption_mapping = {
    'your_plot_keyword': 'Your caption template for {dive_name}',
    # ... existing mappings
}
```

### Programmatic Usage

Use the modules directly in scripts:

```python
from dive_finder import DiveFinder
from report_generator import ReportGenerator

# Find dives
finder = DiveFinder()
dives = finder.find_dives_in_folder("E:\\EN2501\\Image_LLS")

# Generate report
generator = ReportGenerator()
metadata = generator.load_metadata_from_csv("path/to/csv")
generator.generate_report(dives, metadata, "output.docx")
```

## Version History

### Version 2.0 (December 2025)
- Complete modular rewrite
- Added preview pane
- Multi-source data support
- Enhanced GUI with checkboxes
- Smart dive matching

### Version 1.0 (Original)
- Monolithic script
- Basic GUI
- Single data source
- No preview functionality

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Verify all dependencies are installed
3. Review the console output for error messages
4. Check file paths and permissions

## License

Internal use for MDBC AUV data processing.
