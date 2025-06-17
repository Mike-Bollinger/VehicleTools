# VehicleTools

A collection of standalone data analysis and processing tools for uncrewed underwater vehicle (UUV) systems. This repository contains specialized scripts and applications designed to handle data from various underwater platforms including AUVs, ROVs, and other marine robotics systems.

## Overview

VehicleTools provides a comprehensive suite of data processing utilities for marine research and underwater operations. Each tool is designed to be largely standalone, focusing on specific aspects of data analysis, visualization, and processing for different uncrewed vehicle platforms.

## Repository Structure

### Vehicle-Specific Tools

#### **Remus600/**
Tools for processing Remus 600 AUV data:
- [`Remus_NavTXTToSHP.py`](Remus600/Remus_NavTXTToSHP.py ) - Convert navigation text files to CSV and shapefile formats
- [`Script2_NavTXTtoCSV.py`](Remus600/Script2_NavTXTtoCSV.py ) - Navigation data format conversion
- **VOYIS_FirstLookMetrics/** - Comprehensive image analysis suite for VOYIS camera systems
  - Image counting and classification
  - Geographic analysis with GPS extraction
  - Overlap analysis (vertical, horizontal, overall)
  - ML-based visibility analysis
  - Highlight image selection and panel creation

#### **Riptide-uUUV/**
Tools for BAE Systems Riptide UUV data:
- [`MissionDataParser.py`](Riptide-uUUV/MissionDataParser.py ) - Parse and analyze mission log data
- **MissionViewer/** - Post-mission analysis tool for MOOS database variables
- **AISconverter-master/** - Convert text data to NMEA-0183 AIS format

#### **BlueROV/**
Tools for BlueROV underwater vehicle systems:
- **USBL_Nav_Smoother/** - Advanced navigation data smoothing using multiple algorithms
  - Kalman filtering
  - Window smoothing
  - OER (Outlier, Error, Regression) models
- **USBL_Nav_EnhancerOld/** - Legacy navigation enhancement tools

#### **RTsys-NemoSens uUUV/**
Tools for RTsys NemoSens systems:
- [`SurveyPointstoNemoSensJson.ipynb`](RTsys-NemoSens uUUV/SurveyPointstoNemoSensJson.ipynb ) - Convert survey points to Cousto-compatible mission files
- [`CatSidecars_NemoSens.py`](RTsys-NemoSens uUUV/CatSidecars_NemoSens.py ) - Concatenate sidecar CSV files with GUI
- [`HBdetector_NemoSens.py`](RTsys-NemoSens uUUV/HBdetector_NemoSens.py ) - Hard bottom detection using machine learning

### General Tools

#### **VehicleGISTools/**
Geographic Information System utilities:
- [`ArcPro_layout_automator.py`](VehicleGISTools/WIP/ArcPro_layout_automator.py ) - Automate ArcGIS Pro layout creation

#### **Visibility_Analyzer_Tool/**
Standalone visibility analysis tools for underwater imagery

#### **AdNav-Hydrus-uUUV/**
Navigation tools for Hydrus UUV systems:
- [`NavFromExif.py`](AdNav-Hydrus-uUUV/NavFromExif.py ) - Extract navigation data from image EXIF

### Data Management Tools

#### **BOEM Data Processing**
Tools for Bureau of Ocean Energy Management data workflows:
- [`BOEM_Dashboard_Update.ipynb`](BOEM_Dashboard_Update.ipynb ) - Update sampling point dashboards
- [`BOEM_SamplePts_Update.ipynb`](BOEM_SamplePts_Update.ipynb ) - Process and update sampling point databases

#### **Quality Control**
- [`ImageQAQCer.py`](ImageQAQCer.py ) - Image quality assurance and quality control

## Key Features

### Navigation Processing
- **Multi-format Support**: Convert between various navigation file formats (TXT, CSV, SHP)
- **USBL Enhancement**: Advanced smoothing algorithms for USBL navigation data
- **Real-time Processing**: Tools for both post-processing and real-time data handling

### Image Analysis
- **Comprehensive Metrics**: Count, classify, and analyze underwater imagery
- **Overlap Analysis**: Calculate vertical and horizontal image overlap for survey coverage
- **Visibility Assessment**: ML-based visibility classification for underwater images
- **Geographic Integration**: GPS extraction and GIS-ready outputs

### Mission Planning & Analysis
- **Post-Mission Tools**: Analyze vehicle performance and mission parameters
- **Mission File Generation**: Create platform-specific mission files from survey data
- **Quality Assurance**: Automated QA/QC tools for data validation

### Data Integration
- **Database Updates**: Tools for updating sampling point databases
- **Dashboard Integration**: Automated dashboard and visualization updates
- **Multi-platform Support**: Handle data from various UUV manufacturers

## System Requirements

- **Python 3.8+**
- **Core Libraries**: pandas, numpy, matplotlib, geopandas
- **Optional Dependencies**: 
  - TensorFlow (for ML-based analysis)
  - ArcPy (for ArcGIS integration)
  - Various GUI libraries (tkinter, etc.)

## Usage

Each tool is designed to be largely standalone. Navigate to the specific tool directory and refer to individual documentation:

```bash
# Example: Run VOYIS image analysis
cd Remus600/VOYIS_FirstLookMetrics
python src/main.py

# Example: Process Remus navigation data
python Remus600/Remus_NavTXTToSHP.py

# Example: Launch BlueROV navigation smoother
cd BlueROV/USBL_Nav_Smoother
python src/main.py
```

## Contributing

Each tool maintains its own development guidelines. When contributing:
1. Test thoroughly with representative datasets
2. Maintain backward compatibility where possible
3. Update relevant documentation
4. Follow existing code style conventions

## Platform Support

These tools have been tested and deployed with:
- **Remus 600 AUV** (Woods Hole Oceanographic Institution (WHOI)/Hydroid(HII))
- **Riptide UUV** (BAE Systems)
- **BlueROV** (Blue Robotics)
- **NemoSens UUV** (RTsys)
- **Hydrus UUV** (Advanced Navigation)
- Various **UxS platforms**

## License

Individual tools may have specific licensing. Refer to individual tool directories for license information.

## Support

For tool-specific issues, refer to the individual README files in each directory. Many tools include built-in help and error handling to assist with troubleshooting.

---

*This repository represents an active collection of tools developed for marine research and underwater vehicle operations. Tools are continuously updated based on field experience and user feedback.*