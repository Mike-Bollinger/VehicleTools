# AUV FOV Calculator - Python GUI

This is a standalone Python application that converts the original R script functionality into a user-friendly GUI application.

## Features

- **Camera Selection**: Dropdown menu with pre-configured camera settings including:
  - VOYIS
  - Micro UUV 6.3MP
  - Micro UUV 12MP
  - Nikon D780
  - GoPro Hero7 Black
  - SONY ILCE-6300
  - UAV Onboard

- **User Inputs**: 
  - Frame Rate (fps) - editable input box
  - Altitude above seafloor (meters) - editable input box

- **Calculations**: All the original R script calculations including:
  - Field of view coverage (horizontal and vertical)
  - Ground resolution
  - Line spacing with overlap
  - Maximum speed calculations
  - Storage requirements for area coverage
  - Focal length estimation (when applicable)

- **Visualizations**: Interactive plots showing:
  - Vehicle Height vs Resolution relationship
  - Speed vs Frame Rate relationship

## Requirements

### Minimum Requirements (Core functionality):
- Python 3.6 or higher (with tkinter - usually included)

### Optional Requirements (For plotting):
- matplotlib (for graphical plots)

## Installation and Running

### Method 1: Direct Python execution
```bash
python FOV_Calculator.py
```

### Method 2: Using the batch file (Windows)
Double-click `Run_FOV_Calculator.bat`

### Method 3: Installing matplotlib for full functionality
```bash
pip install matplotlib
python FOV_Calculator.py
```

## Usage

1. **Select Camera**: Choose your camera configuration from the dropdown menu
2. **Enter Frame Rate**: Input your desired frame rate in fps
3. **Enter Altitude**: Input your altitude above seafloor in meters
4. **Calculate**: Click the "Calculate FOV Parameters" button
5. **Review Results**: View detailed calculations in the results panel
6. **Analyze Plots**: Review the graphical analysis (if matplotlib is available)

## Camera Configurations

The application includes pre-configured settings for various camera systems with their respective:
- Field of view specifications
- Image dimensions
- Overlap percentages
- Image file sizes

When you select a different camera, the default altitude and frame rate values will automatically adjust to typical values for that camera type.

## Output Information

The calculator provides comprehensive information including:
- Coverage dimensions at specified altitude
- Image seafloor footprint: width x length in meters and total area in square meters
- Unique footprint area added by each subsequent frame, excluding overlap with the previous frame
- Ground resolution (mm/pixel)
- Mission planning parameters (line spacing, maximum speed)
- Storage requirements for area coverage
- Technical camera specifications used in calculations

Both calculation modes report footprint dimensions and areas. The full image area is
width x length. Unique area is full image area x (1 - vertical overlap / 100).
In speed-based planning, unique area is capped at the full image area when frames
have gaps between them; those gaps are not counted as imaged seafloor.

These estimates assume a downward-looking camera over flat seafloor with constant
altitude and orientation, traveling straight along the image's vertical axis.
The first frame contributes its full footprint. Subsequent-frame unique area only
excludes the previous frame, not adjacent survey lines or earlier passes.
Horizontal overlap still applies to the existing survey-area/storage estimates.
At 100% overlap, those estimates are reported as not achievable instead of dividing
by zero.

## Notes

- This is a standalone application - no internet connection required
- The GUI is responsive and will work on different screen sizes
- All calculations match the original R script methodology
- Error handling is included for invalid inputs
- The application gracefully handles missing matplotlib dependency

## Original Credits

- Original R script by Mike Bollinger (9/2020)
- Python GUI conversion (2025)
