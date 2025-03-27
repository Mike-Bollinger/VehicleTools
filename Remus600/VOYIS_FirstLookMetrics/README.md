# VOYIS First Look Metrics

**Version:** 1.2.0  
**Last Updated:** March 2025
**Author:** Mike Bollinger  

## Overview
The VOYIS First Look Metrics application is designed to calculate summary statistics about a folder of images collected by an AUV. It analyzes processed stills and raw images, providing comprehensive metrics about image coverage, overlap, and quality. The application features a user-friendly graphical interface for selecting input and output folders and displays real-time processing status.

## Features
- **Image Counting and Classification**
  - Count and categorize processed stills and raw images
  - Calculate total storage size by image type
  
- **Geographic Analysis**
  - Extract and visualize GPS data from image EXIF
  - Generate image footprint maps showing coverage area
  - Calculate altitude statistics with configurable threshold warnings
  
- **Overlap Analysis**
  - Vertical overlap between sequential images in a survey line
  - Horizontal overlap between adjacent survey lines
  - Overall overlap count showing total overlapping images for each footprint
  - Color-coded visualization maps for all overlap types (vertical, horizontal, overall)
  
- **Export Capabilities**
  - Comprehensive summary report in text format
  - CSV export of image metadata with overlap statistics
  - Shapefile export for GIS integration including overlap metrics
  - Visualization plots showing coverage and overlap

- **User Interface**
  - Intuitive GUI for input/output folder selection
  - Real-time processing status updates
  - Error handling with detailed diagnostics

## Project Structure
```
VOYIS_FirstLookMetrics
├── src
│   ├── main.py                # Entry point of the application
│   ├── gui                    # Contains GUI related files
│   │   ├── __init__.py
│   │   └── app_window.py      # Defines the GUI window
│   ├── processors             # Contains image processing logic
│   │   ├── __init__.py
│   │   └── image_processor.py  # Image processing functionalities
│   ├── utils                  # Utility functions for file handling
│   │   ├── __init__.py
│   │   └── file_utils.py      # File handling utilities
│   └── models                 # Data models for metrics
│       ├── __init__.py
│       └── metrics.py         # Summary statistics for processed images
├── tests                      # Contains unit tests
│   ├── __init__.py
│   ├── test_image_processor.py # Tests for image processing
│   └── test_file_utils.py     # Tests for file utilities
├── requirements.txt           # Project dependencies
└── README.md                  # Project documentation
```

## System Requirements
- Python 3.8 or higher
- Required libraries: tkinter, PIL/Pillow, numpy, matplotlib, geopandas
- Optional: rtree for improved spatial query performance

## Installation
1. Clone the repository:
   ```
   git clone <repository-url>
   ```
2. Navigate to the project directory:
   ```
   cd VOYIS_FirstLookMetrics
   ```
3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage
1. Run the application:
   ```
   python src/main.py
   ```
2. Use the GUI to select:
- Input folder containing VOYIS images
- Output folder for the results
- Configure analysis options (if needed)
3. Click "Start Processing" and monitor progress in the status area
4. Examine the generated reports and visualizations in the output folder

## Output Files
The application generates the following outputs:
- `summary_report.txt`: Text file with comprehensive statistics
- `image_footprints.csv`: CSV file with detailed image metadata and overlap statistics
- `image_footprints.shp`: Shapefile for GIS applications with overlap metrics as attributes
- `image_footprints_map.png`: Map showing image coverage
- `vertical_overlap_map.png`: Map showing overlap between sequential images
- `horizontal_overlap_map.png`: Map showing overlap between adjacent survey lines
- `overall_overlap_map.png`: Map showing total number of overlapping images per footprint

## Version History
- **1.2.0** - Added overall overlap analysis and optimized spatial processing
- **1.1.0** - Added horizontal overlap analysis and GIS exports
- **1.0.0** - Initial release with basic image metrics and vertical overlap

## Known Issues
- Processing large datasets (>10,000 images) may be slow, especially for overlap calculations
- Requires geopandas for advanced mapping features

## Contributing
Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License.