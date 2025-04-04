# VOYIS First Look Metrics

**Version:** 1.3.0  
**Last Updated:** June 2025  
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
  
- **Visibility Analysis**
  - Machine learning-based classification of underwater image visibility
  - Categorization into zero, low, good, and great visibility classes
  - Random sampling of images below specified altitude threshold
  - CSV output with visibility metrics and geolocation data
  - Shapefile export with visibility information for GIS integration
  - Visualization of randomly selected sample locations
  
- **Export Capabilities**
  - Comprehensive summary report in text format
  - CSV export of image metadata with overlap statistics
  - Shapefile export for GIS integration including overlap metrics
  - Visualization plots showing coverage and overlap

- **User Interface**
  - Intuitive GUI for input/output folder selection
  - Real-time processing status updates
  - Error handling with detailed diagnostics
  - Configurable altitude threshold for filtering images

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
- Optional: 
  - rtree for improved spatial query performance
  - TensorFlow for visibility analysis
  - shapely for advanced spatial operations

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
4. Optional: Install TensorFlow for visibility analysis:
   ```
   pip install tensorflow
   ```

## Usage
1. Run the application:
   ```
   python src/main.py
   ```
2. Use the GUI to select:
   - Input folder containing VOYIS images
   - Output folder for the results
   - Configure analysis options and select processing steps
   - Set altitude threshold for filtering (default: 8.0m)
   - Select navigation file for improved footprint orientation (optional)
   - Choose pre-trained visibility model or training data directory
3. Click "Process Images" and monitor progress in the status area
4. Examine the generated reports and visualizations in the output folder

## Output Files
The application generates the following outputs:
- `image_metrics.txt`: Text file with comprehensive statistics
- `image_locations.csv`: CSV file with image metadata and GPS coordinates
- `image_locations_map.png`: Map showing image locations colored by altitude
- `altitude_histogram.png`: Histogram showing the distribution of image altitudes
- `image_footprints.csv`: CSV file with detailed image metadata and overlap statistics
- `image_footprints.shp`: Shapefile for GIS applications with overlap metrics as attributes
- `image_footprints_map.png`: Map showing image coverage with footprints
- `vertical_overlap_map.png`: Map showing overlap between sequential images
- `horizontal_overlap_map.png`: Map showing overlap between adjacent survey lines
- `overall_overlap_map.png`: Map showing total number of overlapping images per footprint
- `visibility_results.csv`: CSV file with visibility classifications and confidence scores
- `selected_images_map.png`: Map showing selected vs. non-selected images for visibility analysis
- `shapefiles/selected_images.shp`: Shapefile of randomly selected images with visibility data

## Version History
- **1.3.0** - Added ML-based visibility analysis, improved workflow organization, and added shapefile exports
- **1.2.0** - Added overall overlap analysis and optimized spatial processing
- **1.1.0** - Added horizontal overlap analysis and GIS exports
- **1.0.0** - Initial release with basic image metrics and vertical overlap

## Known Issues
- Processing large datasets (>10,000 images) may be slow, especially for overlap calculations
- Requires geopandas for advanced mapping features
- TensorFlow needed for visibility analysis
- The visibility analysis may need additional training data for optimal performance in varied environments

## Contributing
Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License.