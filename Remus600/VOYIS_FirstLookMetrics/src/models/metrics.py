import os
import re
from typing import Dict, List, Tuple, Callable, Optional
try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

class Metrics:
    def __init__(self, altitude_threshold=9.0):
        # Initialize counters
        self.processed_count = 0
        self.processed_size = 0
        self.raw_count = 0
        self.raw_size = 0
        self.other_count = 0
        self.other_size = 0
        
        # Store GPS data for mapping
        self.gps_data = []
        
        # Save the altitude threshold
        self.altitude_threshold = altitude_threshold
        
        # Initialize overlap statistics (will be set from footprint_map if available)
        self.vertical_overlap_stats = None
        self.horizontal_overlap_stats = None
        self.overall_overlap_stats = None
        
        # Track images with issues
        self.no_gps_images = []
        self.above_threshold_images = []
        self.above_threshold_values = {}
        
        # Patterns for recognizing files
        self.raw_pattern = re.compile(r'ESC_stills_raw_PPS_')
        self.processed_pattern = re.compile(r'ESC_stills_processed_PPS_')
    
    def analyze_directory(self, input_folder: str, progress_callback: Callable = None, extract_gps: bool = False) -> Tuple[int, List[str]]:
        """
        Analyze the input directory and count/measure image files
        
        Args:
            input_folder: Path to input directory
            progress_callback: Function to call with progress updates (receives percentage and message)
            extract_gps: Whether to extract GPS data for mapping
            
        Returns:
            Tuple of (total_files_processed, results_list)
        """
        # Reset metrics
        self.processed_count = 0
        self.processed_size = 0
        self.raw_count = 0
        self.raw_size = 0
        self.other_count = 0
        self.other_size = 0
        self.gps_data = []
        
        # Check if PIL is available for GPS extraction
        if extract_gps and not PIL_AVAILABLE:
            if progress_callback:
                progress_callback(0, "Warning: PIL/Pillow library not available. GPS data extraction disabled.")
            extract_gps = False
        
        # Count total files for progress tracking
        total_files = 0
        for root, _, files in os.walk(input_folder):
            total_files += len(files)
            
        if progress_callback:
            progress_callback(0, f"Found {total_files} files to analyze...")
        
        processed_files = 0
        
        # Walk through all files in the input folder
        for root, _, files in os.walk(input_folder):
            for file in files:
                file_path = os.path.join(root, file)
                file_size = os.path.getsize(file_path)
                
                # Update progress
                processed_files += 1
                if progress_callback:
                    progress = (processed_files / total_files) * 100 if total_files > 0 else 0
                    
                    # Only report progress on milestones to avoid GUI flooding
                    if processed_files == 1 or processed_files == total_files or processed_files % 1000 == 0:
                        progress_callback(progress, f"Analyzed {processed_files} of {total_files} files...")
                
                # Determine file type
                file_type = None
                if self.processed_pattern.search(file):
                    self.processed_count += 1
                    self.processed_size += file_size
                    file_type = "processed"
                    # Report milestones
                    if self.processed_count % 100 == 0 and progress_callback:
                        progress_callback(progress, f"Found {self.processed_count} processed images so far...")
                    
                    # Extract GPS data from processed images only
                    if extract_gps and file.lower().endswith(('.jpg', '.jpeg', '.tiff', '.tif', '.png')):
                        try:
                            gps_info = self.extract_gps_from_image(file_path)
                            if gps_info:
                                gps_info['file_type'] = file_type
                                gps_info['filename'] = file
                                self.gps_data.append(gps_info)
                                if len(self.gps_data) % 10 == 0 and progress_callback:
                                    progress_callback(progress, f"Extracted GPS data from {len(self.gps_data)} processed images so far...")
                        except Exception as e:
                            if progress_callback:
                                progress_callback(progress, f"Could not extract GPS data from {file}: {str(e)}")
                
                elif self.raw_pattern.search(file):
                    self.raw_count += 1
                    self.raw_size += file_size
                    file_type = "raw"
                    # Report milestones
                    if self.raw_count % 100 == 0 and progress_callback:
                        progress_callback(progress, f"Found {self.raw_count} raw images so far...")
                    # Note: We no longer extract GPS data from raw images
                
                else:
                    self.other_count += 1
                    self.other_size += file_size
                    file_type = "other"
        
        # Generate results
        results = self.get_summary_report()
        return processed_files, results
                
    def get_summary(self) -> Dict:
        """Return metrics dictionary"""
        return {
            "Processed Images": self.processed_count,
            "Processed Size": self.processed_size,
            "Raw Images": self.raw_count,
            "Raw Size": self.raw_size,
            "Other Files": self.other_count,
            "Other Size": self.other_size,
            "Total Images": self.processed_count + self.raw_count,
            "Total Files": self.processed_count + self.raw_count + self.other_count,
            "Total Size": self.processed_size + self.raw_size + self.other_size,
            "Images with GPS data": len(self.gps_data)
        }
    
    def get_summary_report(self) -> List[str]:
        """Return formatted summary as list of strings"""
        # Format sizes for display
        processed_size_hr = self.format_size(self.processed_size)
        raw_size_hr = self.format_size(self.raw_size)
        other_size_hr = self.format_size(self.other_size)
        total_size_hr = self.format_size(self.processed_size + self.raw_size + self.other_size)
        
        report = [
            "Image Analysis Summary:",
            "-----------------------",
            f"Processed Still Images: {self.processed_count}",
            f"Processed Stills Size: {processed_size_hr}",
            f"Raw Images: {self.raw_count}",
            f"Raw Images Size: {raw_size_hr}",
            f"Other Files: {self.other_count}",
            f"Other Files Size: {other_size_hr}",
            f"Total Files: {self.processed_count + self.raw_count + self.other_count}",
            f"Total Size: {total_size_hr}"
        ]
        
        # Add GPS data summary if available
        if self.gps_data:
            altitude_stats = self.get_altitude_statistics(threshold=self.altitude_threshold)
            
            if altitude_stats:
                # Add altitude statistics to the report
                report.extend([
                    "",
                    "Altitude Analysis (Processed Images Only):",
                    "----------------------------------------",
                    f"Images with GPS data: {len(self.gps_data)} of {self.processed_count} processed images",
                    f"Images below {self.altitude_threshold:.1f}m: {altitude_stats['below_threshold']} ({altitude_stats['below_percent']:.1f}%)",
                    f"Images above {self.altitude_threshold:.1f}m: {altitude_stats['above_threshold']} ({altitude_stats['above_percent']:.1f}%)",
                    f"Altitude range: {altitude_stats['min']:.2f}m to {altitude_stats['max']:.2f}m",
                    f"Average altitude: {altitude_stats['avg']:.2f}m",
                    f"Median altitude: {altitude_stats['median']:.2f}m",
                    f"Standard deviation: {altitude_stats['std_dev']:.2f}m"
                ])
            else:
                report.extend([
                    "",
                    f"Processed Images with GPS data: {len(self.gps_data)}",
                    "(No altitude data available in the GPS information)"
                ])
        
             
        return report
    
    def extract_gps_from_image(self, image_path: str) -> Optional[Dict]:
        """
        Extract GPS information and camera parameters from image EXIF data
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary with location and camera parameters if available, None otherwise
        """
        if not PIL_AVAILABLE:
            return None
            
        try:
            with Image.open(image_path) as img:
                # Get image dimensions directly from the image
                width, height = img.size
                
                # Start with base info including dimensions
                result = {
                    'width': width,
                    'height': height
                }
                
                # If no EXIF data available, return just the dimensions
                if not hasattr(img, '_getexif') or img._getexif() is None:
                    return result
                
                # Extract all EXIF data
                exif_data = {
                    TAGS.get(tag, tag): value
                    for tag, value in img._getexif().items()
                }
                
                # Extract camera parameters
                # ExposureTime
                if 'ExposureTime' in exif_data:
                    exposure = exif_data['ExposureTime']
                    if isinstance(exposure, tuple) and len(exposure) == 2:
                        result['ExposureTime'] = f"{exposure[0]}/{exposure[1]}"
                    else:
                        result['ExposureTime'] = str(exposure)
                
                # FNumber
                if 'FNumber' in exif_data:
                    fnumber = exif_data['FNumber']
                    if isinstance(fnumber, tuple) and len(fnumber) == 2:
                        result['FNumber'] = round(fnumber[0] / fnumber[1], 1)
                    else:
                        result['FNumber'] = fnumber
                
                # FocalLength
                if 'FocalLength' in exif_data:
                    focal = exif_data['FocalLength']
                    if isinstance(focal, tuple) and len(focal) == 2:
                        result['FocalLength'] = round(focal[0] / focal[1], 1)
                    else:
                        result['FocalLength'] = focal
                    
                # SubjectDistance
                if 'SubjectDistance' in exif_data:
                    distance = exif_data['SubjectDistance']
                    if isinstance(distance, tuple) and len(distance) == 2:
                        result['SubjectDistance'] = round(distance[0] / distance[1], 1)
                    else:
                        result['SubjectDistance'] = distance
                
                # DateTime
                if 'DateTimeOriginal' in exif_data:
                    result['DateTime'] = exif_data['DateTimeOriginal']
                elif 'DateTime' in exif_data:
                    result['DateTime'] = exif_data['DateTime']
                
                # If no GPS info, return what we have so far - camera parameters are valuable even without GPS
                if 'GPSInfo' not in exif_data:
                    return result
                
                # Process GPS data
                gps_info = {
                    GPSTAGS.get(tag, tag): value
                    for tag, value in exif_data['GPSInfo'].items()
                }
                
                # Extract latitude
                if 'GPSLatitude' in gps_info and 'GPSLatitudeRef' in gps_info:
                    lat = self._convert_to_degrees(gps_info['GPSLatitude'])
                    if gps_info['GPSLatitudeRef'] == 'S':
                        lat = -lat
                    result['latitude'] = lat
                
                # Extract longitude
                if 'GPSLongitude' in gps_info and 'GPSLongitudeRef' in gps_info:
                    lon = self._convert_to_degrees(gps_info['GPSLongitude'])
                    if gps_info['GPSLongitudeRef'] == 'W':
                        lon = -lon
                    result['longitude'] = lon
                
                # Extract altitude
                if 'GPSAltitude' in gps_info:
                    try:
                        if isinstance(gps_info['GPSAltitude'], tuple) and len(gps_info['GPSAltitude']) == 2:
                            altitude = float(gps_info['GPSAltitude'][0]) / float(gps_info['GPSAltitude'][1])
                        else:
                            altitude = float(gps_info['GPSAltitude'])
                            
                        if 'GPSAltitudeRef' in gps_info and gps_info['GPSAltitudeRef'] == 1:
                            altitude = -altitude
                        
                        result['altitude'] = altitude
                    except (ValueError, TypeError, ZeroDivisionError):
                        print(f"Warning: Could not parse altitude value in {image_path}")
                
                return result
                
        except Exception as e:
            print(f"Error extracting data from {image_path}: {e}")
            return None

    def _convert_to_degrees(self, value):
        """Helper function to convert GPS coordinates from EXIF format to decimal degrees"""
        degrees = float(value[0])
        minutes = float(value[1])
        seconds = float(value[2])
        return degrees + (minutes / 60.0) + (seconds / 3600.0)
    
    @staticmethod
    def format_size(size_bytes: int) -> str:
        """Convert bytes to human-readable size format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024 or unit == 'TB':
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024

    def get_altitude_statistics(self, threshold: float = 9.0) -> Dict:
        """
        Calculate altitude statistics from the GPS data
        
        Args:
            threshold: Altitude threshold in meters (default 9.0m)
            
        Returns:
            Dictionary with altitude statistics
        """
        if not self.gps_data:
            return {}
            
        altitudes = [point['altitude'] for point in self.gps_data if 'altitude' in point]
        
        if not altitudes:
            return {}
            
        below_threshold = sum(1 for alt in altitudes if alt < threshold)
        above_threshold = len(altitudes) - below_threshold
        
        min_altitude = min(altitudes)
        max_altitude = max(altitudes)
        avg_altitude = sum(altitudes) / len(altitudes)
        
        # Calculate standard deviation
        variance = sum((alt - avg_altitude) ** 2 for alt in altitudes) / len(altitudes)
        std_dev = variance ** 0.5
        
        # Calculate percentiles
        sorted_altitudes = sorted(altitudes)
        percentile_25 = sorted_altitudes[int(len(sorted_altitudes) * 0.25)]
        percentile_50 = sorted_altitudes[int(len(sorted_altitudes) * 0.50)]  # median
        percentile_75 = sorted_altitudes[int(len(sorted_altitudes) * 0.75)]
        
        return {
            "count": len(altitudes),
            "below_threshold": below_threshold,
            "above_threshold": above_threshold,
            "below_percent": (below_threshold / len(altitudes) * 100) if altitudes else 0,
            "above_percent": (above_threshold / len(altitudes) * 100) if altitudes else 0,
            "min": min_altitude,
            "max": max_altitude,
            "range": max_altitude - min_altitude,
            "avg": avg_altitude,
            "median": percentile_50,
            "std_dev": std_dev,
            "percentile_25": percentile_25,
            "percentile_50": percentile_50,
            "percentile_75": percentile_75
        }