# USBL Navigation Smoother

## Overview
The USBL Navigation Smoother is a Python application designed to process and smooth navigation data collected from underwater vehicles using various smoothing algorithms. The application provides a graphical user interface (GUI) for users to select navigation and diagnostic files, choose smoothing models, and visualize the results.

## Features
- Supports multiple smoothing algorithms:
  - Kalman Filter
  - Window Smoothing
  - OER Moving Average
- Visualization of raw and smoothed navigation data.
- Generation of output files including CSVs and shapefiles.
- Animation of navigation tracks.

## Project Structure
```
USBL_Nav_Smoother
├── src
│   ├── models
│   │   ├── kalman_filter.py       # Implementation of the Kalman filter smoothing algorithm.
│   │   ├── window_smoother.py      # Implementation of the window smoothing algorithm.
│   │   └── oer_smoother.py         # Implementation of the OER model for smoothing navigation data.
│   ├── utils
│   │   ├── file_handlers.py         # Utility functions for file operations.
│   │   ├── geo_utils.py             # Geographic utility functions.
│   │   └── visualization.py          # Functions for visualizing navigation data.
│   ├── gui
│   │   ├── app.py                   # Main application logic for the GUI.
│   │   └── widgets.py               # Custom widgets for the GUI.
│   ├── main.py                      # Entry point for the application.
├── tests
│   ├── test_kalman_filter.py        # Unit tests for the Kalman filter implementation.
│   ├── test_window_smoother.py      # Unit tests for the window smoother implementation.
│   └── test_oer_smoother.py         # Unit tests for the OER smoother implementation.
├── data
│   ├── sample
│   │   ├── sample_nav.csv           # Sample navigation data in CSV format.
│   │   └── sample_diag.csv          # Sample diagnostic data in CSV format.
│   └── output                        # Directory for output files.
├── requirements.txt                  # Lists dependencies required for the project.
├── setup.py                          # Packaging information for the application.
└── README.md                         # Documentation for the project.
```

## Installation
1. Clone the repository:
   ```
   git clone <repository-url>
   ```
2. Navigate to the project directory:
   ```
   cd USBL_Nav_Smoother
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
2. Use the GUI to select navigation and diagnostic files.
3. Choose the desired smoothing models and process the data.
4. View the results in the generated plots and output files.

## Contributing
Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for details.