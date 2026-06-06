# Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         main.py                                  │
│                    (Entry Point)                                 │
│  - Checks dependencies                                           │
│  - Launches main_gui.MainGUI                                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      main_gui.py                                 │
│                   (Main Application)                             │
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐│
│  │  Data Source     │  │  Dive Selection  │  │    Preview    ││
│  │     Panel        │  │      Panel       │  │    Widget     ││
│  │                  │  │                  │  │               ││
│  │ - Add folders    │  │ - Checkbox tree  │  │ - 8.5x11"     ││
│  │ - Remove folders │  │ - Select all     │  │ - Scrollable  ││
│  │ - List sources   │  │ - Get selected   │  │ - Image view  ││
│  └──────────────────┘  └──────────────────┘  └───────────────┘│
│                                                                   │
└───────┬───────────────────────┬───────────────────────┬─────────┘
        │                       │                       │
        ▼                       ▼                       ▼
┌──────────────┐      ┌──────────────────┐    ┌──────────────────┐
│dive_finder.py│      │report_generator.py│    │preview_widget.py │
│              │      │                   │    │                  │
│ DiveFinder   │      │ ReportGenerator   │    │ PreviewWidget    │
│              │      │                   │    │                  │
│ - Scan folders│     │ - Load CSV        │    │ - Render page   │
│ - Match dives│      │ - Create Word doc │    │ - Show metadata │
│ - Get images │      │ - Add sections    │    │ - Display images│
│ - Categorize │      │ - Caption mapping │    │ - Scroll view   │
└──────────────┘      └───────────────────┘    └──────────────────┘
```

## Data Flow

### Startup Flow
```
1. main.py
   ↓
2. Check dependencies (pandas, python-docx, Pillow)
   ↓
3. Launch MainGUI
   ↓
4. Load default data sources
   ↓
5. Auto-scan for dives
```

### User Interaction Flow
```
User adds data sources
   ↓
Click "Scan for Dives"
   ↓
DiveFinder.find_dives_in_multiple_folders()
   ↓
Returns: {dive_number: [dive_info_list]}
   ↓
DiveFinder.merge_dive_sources()
   ↓
DiveSelectionPanel.load_dives()
   ↓
Display in checkbox tree
```

### Preview Flow
```
User selects/deselects dive
   ↓
on_selection_change callback
   ↓
MainGUI.update_preview()
   ↓
Get first selected dive
   ↓
Get metadata from cache
   ↓
Get images from Report_Plots
   ↓
PreviewWidget.load_dive_preview()
   ↓
Render on 8.5x11" canvas
```

### Report Generation Flow
```
User clicks "Generate Report"
   ↓
Get selected dives
   ↓
ReportGenerator.create_document()
   ↓
For each selected dive:
   ├── Get metadata from CSV cache
   ├── Get images from Report_Plots
   ├── Categorize images (vehicle/imaging/laser)
   └── ReportGenerator.add_dive_section()
       ├── Add metadata
       ├── Add Vehicle Data Summary (with images)
       ├── Add Imaging Summary (with images)
       └── Add Laser Analysis Summary (with images)
   ↓
Save .docx file
   ↓
Show success message
```

## Module Responsibilities

### dive_finder.py (Data Discovery)
- **Input**: List of folder paths
- **Process**: Recursive walk, regex matching on "DIVE\d+"
- **Output**: Structured dive data with paths
- **Key Feature**: Merges multiple sources for same dive

### report_generator.py (Document Generation)
- **Input**: Selected dives, metadata dict, output path
- **Process**: Create Word doc, add sections with images
- **Output**: .docx file
- **Key Feature**: Caption mapping for automatic figure captions

### preview_widget.py (UI Preview)
- **Input**: Dive info, metadata, images
- **Process**: Render on canvas with proper spacing
- **Output**: Visual preview
- **Key Feature**: 8.5x11" aspect ratio for QAQC

### main_gui.py (Orchestration)
- **Input**: User interactions
- **Process**: Coordinate all modules
- **Output**: Complete application
- **Key Feature**: Three-panel layout with preview

## Component Communication

```
DataSourcePanel ──(on_change)──> MainGUI.scan_data_sources()
                                      ↓
                                 DiveFinder.find_dives()
                                      ↓
DiveSelectionPanel <──(load_dives)── MainGUI
                                      ↓
DiveSelectionPanel ─(on_select)──> MainGUI.update_preview()
                                      ↓
PreviewWidget <──(load_preview)──── MainGUI
                                      
MainGUI.generate_report() ──> ReportGenerator.generate_report()
                                      ↓
                              DiveFinder (for images)
```

## State Management

```
MainGUI maintains:
├── csv_file_var: StringVar (CSV path)
├── output_folder_var: StringVar (output path)
├── metadata_cache: Dict[str, Dict] (dive metadata from CSV)
├── current_dives: Dict[str, List[Dict]] (found dives by number)
└── Components maintain their own state:
    ├── DataSourcePanel.data_sources: List[str]
    ├── DiveSelectionPanel.dive_items: Dict (tree items)
    └── PreviewWidget.current_dive: Dict
```

## Extension Points

To add new features:

1. **New plot type**: Add to `report_generator.caption_mapping`
2. **New metadata field**: Update `report_generator._extract_metadata_from_row()`
3. **New preview section**: Extend `preview_widget._render_preview()`
4. **New data source type**: Extend `dive_finder.find_dives_in_folder()`
5. **New export format**: Create new generator inheriting from `ReportGenerator`

## Dependencies

```
main.py
  └── tkinter (stdlib)
  
main_gui.py
  ├── tkinter (stdlib)
  ├── dive_finder
  ├── report_generator
  └── preview_widget
  
dive_finder.py
  ├── os (stdlib)
  ├── re (stdlib)
  └── pathlib (stdlib)
  
report_generator.py
  ├── pandas
  └── python-docx
  
preview_widget.py
  ├── tkinter (stdlib)
  └── PIL (Pillow)
```
