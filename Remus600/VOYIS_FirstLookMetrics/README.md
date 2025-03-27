# VOYIS First Look Metrics

## Overview
The VOYIS First Look Metrics application is designed to calculate summary statistics about a folder of images. It provides a user-friendly graphical interface for selecting input and output folders, and displays the processing status of the images.

## Features
- Count of processed still images.
- GUI for easy folder selection.
- Display of processing status.

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
2. Use the GUI to select the input folder containing images and the output folder for the results.
3. Monitor the processing status displayed in the application.

## Contributing
Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License.