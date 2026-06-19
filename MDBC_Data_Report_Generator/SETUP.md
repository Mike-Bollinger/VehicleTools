# Quick Setup Guide

## First Time Setup

### 1. Install Dependencies

Open PowerShell or Command Prompt in this folder and run:

```powershell
pip install -r requirements.txt
```

This installs:
- `python-docx` - for Word document generation
- `pandas` - for CSV data processing
- `Pillow` - for image preview functionality

### 2. Verify Installation

Run the application to test:

```powershell
python main.py
```

Or double-click: **`Run_Report_Generator.bat`**

## Quick Start

### Option A: Use the Batch File (Easiest)

1. Double-click **`Run_Report_Generator.bat`**
2. Application opens with GUI

### Option B: Use Python Directly

```powershell
python main.py
```

## Initial Configuration

When the application opens:

1. **CSV File Path** (top section)
   - Default: `C:\Users\Mike.Bollinger\Downloads\EN2501_AUV_Mission_Log_IMAGING_LASER - Mission_Overview.csv`
   - Click "Browse" if your CSV is elsewhere
   - Click "Load" to import metadata

2. **Data Sources** (middle-top section)
   - Default sources are pre-loaded:
     - `E:\EN2501\Image_LLS`
     - `Q:\EN2501\Image_LLS`
   - Click "Add Folder" for additional sources
   - Click "Scan for Dives" to search for dive folders

3. **Dive Selection** (middle section)
   - Checkboxes appear for each found dive
   - Click dives to select/deselect
   - Use "Select All" / "Deselect All" buttons

4. **Preview** (right side)
   - Automatically shows first selected dive
   - Scroll to see metadata and sample plots

5. **Generate Report** (bottom section)
   - Choose output folder (default: same folder as script)
   - Click "Generate Report"
   - Progress window shows status

## Typical Workflow

```
1. Launch app (Run_Report_Generator.bat)
2. Load CSV metadata (if not auto-loaded)
3. Scan data sources
4. Select dives to include
5. Review preview
6. Generate report
```

## File Locations

- **Application**: This folder
- **CSV**: `C:\Users\Mike.Bollinger\Downloads\`
- **Data Sources**: 
  - `E:\EN2501\Image_LLS`
  - `Q:\EN2501\Image_LLS`
- **Output**: Configurable (default: application folder)

## Troubleshooting

### Python not found
- Install Python 3.7 or higher
- Add Python to PATH during installation

### Missing packages error
- Run: `pip install -r requirements.txt`
- Make sure you're in the correct folder

### No dives found
- Verify data source paths are correct
- Check that folders contain "DIVE" in their name
- Ensure folders have read permissions

### CSV error
- Verify CSV file exists at the specified path
- Check CSV has proper format (see README_NEW.md)
- Try clicking "Load" again after browsing

## Need Help?

See **README_NEW.md** for:
- Detailed feature descriptions
- Advanced configuration
- Complete troubleshooting guide
- Module documentation

## Files in This Folder

- **main.py** - Entry point (run this)
- **main_gui.py** - Main application GUI
- **dive_finder.py** - Dive folder scanner
- **report_generator.py** - Word document generator
- **preview_widget.py** - Preview pane
- **requirements.txt** - Python dependencies
- **Run_Report_Generator.bat** - Windows launcher
- **README_NEW.md** - Complete documentation
- **SETUP.md** - This file
