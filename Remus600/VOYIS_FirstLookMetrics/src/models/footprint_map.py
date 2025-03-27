import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os
from typing import List, Dict, Optional, Tuple
import warnings
import datetime
from dateutil import parser

# Try importing geopandas, but handle the case where it might not be installed
try:
    import geopandas as gpd
    from shapely.geometry import Point, Polygon
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False
    warnings.warn("geopandas or shapely not available. Shapefile export will be disabled.")

class FootprintMap:
    def __init__(self, altitude_threshold=5.0):
        """
        Initialize the footprint map generator
        
        Args:
            altitude_threshold: Maximum altitude to include in the footprint map (in meters)
        """
        # VOYIS camera parameters from FoV Overlap Calculator.R
        self.hfov = 56  # Horizontal Field of View in degrees
        self.vfov = 42  # Vertical Field of View in degrees
        self.nav_data = None
        self.altitude_threshold = altitude_threshold  # Add threshold parameter
        
    def load_nav_data(self, nav_file_path: str) -> bool:
        """
        Load navigation data from a text file, focusing only on time and heading
        
        Args:
            nav_file_path: Path to the navigation file
            
        Returns:
            Boolean indicating success
        """
        try:
            print(f"Loading navigation data from {nav_file_path}")
            
            # First, examine the file structure to determine format
            with open(nav_file_path, 'r') as f:
                # Read the first few lines to analyze structure
                header_lines = [f.readline() for _ in range(5)]
            
            # Look for header line with "Time" and "Heading"
            header_line_index = -1
            for i, line in enumerate(header_lines):
                if 'Time' in line and ('Heading' in line or 'heading' in line.lower()):
                    header_line_index = i
                    break
            
            if header_line_index == -1:
                print("Could not identify header line with 'Time' and 'Heading' columns")
                # Try to find any line with commas as potential header
                for i, line in enumerate(header_lines):
                    if ',' in line and line.strip():
                        header_line_index = i
                        break
            
            # Read the file with pandas
            try:
                # Skip identified header lines
                if header_line_index >= 0:
                    self.nav_data = pd.read_csv(nav_file_path, skiprows=header_line_index)
                else:
                    # Try reading with default settings
                    self.nav_data = pd.read_csv(nav_file_path)
                
                # Clean column names
                self.nav_data.columns = self.nav_data.columns.str.strip()
                
                # Print available columns for debugging
                print(f"Available columns in nav file: {list(self.nav_data.columns)}")
                
                # Find time column (could be named Time, time, timestamp, etc.)
                time_col = None
                date_col = None
                
                for col in self.nav_data.columns:
                    if col.lower() == 'time':
                        time_col = col
                    elif col.lower() == 'date':
                        date_col = col
                
                if time_col is None:
                    # Try to find any column with 'time' in the name
                    time_candidates = [col for col in self.nav_data.columns if 'time' in col.lower()]
                    if time_candidates:
                        time_col = time_candidates[0]
                        print(f"Using '{time_col}' as time column")
                
                # Find heading column
                heading_col = None
                for col in self.nav_data.columns:
                    if col.lower() == 'heading':
                        heading_col = col
                
                if heading_col is None:
                    # Try to find any column with 'head' in the name
                    heading_candidates = [col for col in self.nav_data.columns if 'head' in col.lower()]
                    if heading_candidates:
                        heading_col = heading_candidates[0]
                        print(f"Using '{heading_col}' as heading column")
                
                # Extract and process only the columns we need
                if heading_col:
                    # Ensure heading is numeric
                    self.nav_data['Heading'] = pd.to_numeric(self.nav_data[heading_col], errors='coerce')
                    print(f"Processed heading data from column: {heading_col}")
                    # Remove rows with missing heading
                    self.nav_data = self.nav_data.dropna(subset=['Heading'])
                else:
                    print("Warning: No heading column found. Using default heading of 0.")
                    self.nav_data['Heading'] = 0.0
                
                # Extract datetime from time and date columns
                if time_col and date_col:
                    # Both time and date columns available
                    print(f"Using time column '{time_col}' and date column '{date_col}'")
                    
                    # Create datetime column
                    try:
                        # Show sample data
                        print(f"Sample time: {self.nav_data[time_col].iloc[0]}")
                        print(f"Sample date: {self.nav_data[date_col].iloc[0]}")
                        
                        # Convert to datetime - try different formats
                        self.nav_data['Datetime'] = pd.to_datetime(
                            self.nav_data[date_col].astype(str) + ' ' + self.nav_data[time_col].astype(str),
                            errors='coerce'
                        )
                    except Exception as e:
                        print(f"Error converting date and time to datetime: {e}")
                        return False
                elif time_col:
                    # Only time column available
                    print(f"Only time column '{time_col}' available, no date column")
                    try:
                        # Try to parse the time column directly
                        self.nav_data['Datetime'] = pd.to_datetime(self.nav_data[time_col], errors='coerce')
                    except Exception as e:
                        print(f"Error converting time to datetime: {e}")
                        return False
                else:
                    print("Warning: No time column found. Navigation data timing won't be available.")
                    return False
                
                # Remove rows with invalid datetime
                self.nav_data = self.nav_data.dropna(subset=['Datetime'])
                
                print(f"Successfully loaded {len(self.nav_data)} navigation records with datetime and heading")
                if not self.nav_data.empty:
                    print("First navigation record:")
                    print(f"  Datetime: {self.nav_data['Datetime'].iloc[0]}")
                    print(f"  Heading: {self.nav_data['Heading'].iloc[0]}")
                    print("Last navigation record:")
                    print(f"  Datetime: {self.nav_data['Datetime'].iloc[-1]}")
                    print(f"  Heading: {self.nav_data['Heading'].iloc[-1]}")
                
                return True
                
            except Exception as e:
                print(f"Error reading navigation file with pandas: {e}")
                return False
                
        except Exception as e:
            print(f"Error loading navigation data: {e}")
            import traceback
            print(traceback.format_exc())
            self.nav_data = None
            return False
    
    def _parse_nav_datetime(self, date_str, time_str):
        """Parse navigation date and time into datetime object"""
        try:
            # Print raw input for debugging
            print(f"Parsing date: '{date_str}' and time: '{time_str}'")
            
            # Convert MM/DD/YYYY to YYYY-MM-DD
            if isinstance(date_str, str) and '/' in date_str:
                date_parts = date_str.strip().split('/')
                if len(date_parts) == 3:
                    # Check if year is in position 2 (MM/DD/YYYY)
                    if len(date_parts[2]) == 4:  # Likely YYYY
                        formatted_date = f"{date_parts[2]}-{date_parts[0].zfill(2)}-{date_parts[1].zfill(2)}"
                    # Or if it's in position 0 (YYYY/MM/DD)
                    elif len(date_parts[0]) == 4:  # Likely YYYY
                        formatted_date = f"{date_parts[0]}-{date_parts[1].zfill(2)}-{date_parts[2].zfill(2)}"
                    else:
                        # Default to MM/DD/YYYY and assume current century
                        year = date_parts[2]
                        if len(year) == 2:
                            year = f"20{year}"
                        formatted_date = f"{year}-{date_parts[0].zfill(2)}-{date_parts[1].zfill(2)}"
                else:
                    # Couldn't parse, use as-is
                    formatted_date = date_str.strip()
            else:
                formatted_date = str(date_str).strip()
            
            # Handle time format HH:MM:SS.SSS or similar
            if isinstance(time_str, str):
                time_str = time_str.strip()
            else:
                time_str = str(time_str).strip()
            
            # Create datetime string
            datetime_str = f"{formatted_date} {time_str}"
            print(f"Attempting to parse: '{datetime_str}'")
            
            # Try to parse
            return parser.parse(datetime_str)
            
        except Exception as e:
            print(f"Error parsing datetime: {date_str, time_str, {e}}")
            
            # Try even more basic approach - just combine and try to parse
            try:
                datetime_str = f"{str(date_str).strip()} {str(time_str).strip()}"
                return parser.parse(datetime_str)
            except:
                return None
    
    def _extract_latitude(self, lon_lat_str):
        """Extract latitude from combined Lon/Lat string"""
        try:
            # Format: 28N05.40726  90W56.15713
            parts = lon_lat_str.strip().split()
            if len(parts) >= 1:
                lat_str = parts[0]
                
                # Check if format is like 28N05.40726
                if 'N' in lat_str or 'S' in lat_str:
                    direction = 1 if 'N' in lat_str else -1
                    lat_parts = lat_str.replace('N', ' ').replace('S', ' ').split()
                    degrees = float(lat_parts[0])
                    minutes = float(lat_parts[1])
                    return direction * (degrees + minutes / 60)
            
            return None
            
        except Exception as e:
            print(f"Error extracting latitude from {lon_lat_str}: {e}")
            return None
    
    def _extract_longitude(self, lon_lat_str):
        """Extract longitude from combined Lon/Lat string"""
        try:
            # Format: 28N05.40726  90W56.15713
            parts = lon_lat_str.strip().split()
            if len(parts) >= 2:
                lon_str = parts[1]
                
                # Check if format is like 90W56.15713
                if 'E' in lon_str or 'W' in lon_str:
                    direction = 1 if 'E' in lon_str else -1
                    lon_parts = lon_str.replace('E', ' ').replace('W', ' ').split()
                    degrees = float(lon_parts[0])
                    minutes = float(lon_parts[1])
                    return direction * (degrees + minutes / 60)
            
            return None
            
        except Exception as e:
            print(f"Error extracting longitude from {lon_lat_str}: {e}")
            return None
    
    def _calculate_footprint(self, altitude: float) -> Tuple[float, float]:
        """
        Calculate image footprint dimensions based on altitude
        
        Args:
            altitude: Distance from seafloor in meters
            
        Returns:
            Tuple of (width, height) in meters
        """
        # Calculate width using horizontal field of view
        width = 2 * altitude * np.tan(np.radians(self.hfov / 2))
        
        # Calculate height using vertical field of view
        height = 2 * altitude * np.tan(np.radians(self.vfov / 2))
        
        return width, height
    
    def _calculate_polygon_vertices(self, lat: float, lon: float, altitude: float, 
                                   heading: float) -> List[Tuple[float, float]]:
        """
        Calculate the four corners of the image footprint on the seafloor
        
        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees
            altitude: Distance from seafloor in meters
            heading: Vehicle heading in degrees (0=North, 90=East)
            
        Returns:
            List of (lon, lat) coordinates for the four corners
        """
        # Calculate footprint dimensions
        width, height = self._calculate_footprint(altitude)
        
        # For VOYIS camera, width is typically larger than height (horizontal FOV > vertical FOV)
        # To align the shorter edge with the heading direction, we need to orient the rectangle correctly
        
        # Convert heading to radians
        heading_rad = np.radians(heading)
        
        # Calculate the offset vectors in the heading direction and perpendicular to it
        # The heading direction corresponds to the short edge (height)
        # The perpendicular direction corresponds to the long edge (width)
        
        # Unit vector in heading direction
        dx_heading = np.sin(heading_rad)  # x component of heading vector
        dy_heading = np.cos(heading_rad)  # y component of heading vector
        
        # Unit vector perpendicular to heading (90 degrees clockwise from heading)
        dx_perp = np.sin(heading_rad + np.pi/2)  # x component of perpendicular vector
        dy_perp = np.cos(heading_rad + np.pi/2)  # y component of perpendicular vector
        
        # Calculate half-dimensions for convenience
        half_width = width / 2
        half_height = height / 2
        
        # Approximate meters per degree of latitude and longitude at this location
        meters_per_lat = 111320  # approximate meters per degree latitude
        meters_per_lon = 111320 * np.cos(np.radians(lat))  # approximate meters per degree longitude
        
        # Calculate the four corners:
        # - along the heading vector (use the height dimension for forward/backward)
        # - along the perpendicular vector (use the width dimension for left/right)
        corners = [
            # Bottom left: back-left corner (-height/2 along heading, -width/2 perpendicular)
            (lon + (-half_height * dx_heading - half_width * dx_perp) / meters_per_lon, 
             lat + (-half_height * dy_heading - half_width * dy_perp) / meters_per_lat),
            
            # Bottom right: back-right corner (-height/2 along heading, +width/2 perpendicular)
            (lon + (-half_height * dx_heading + half_width * dx_perp) / meters_per_lon,
             lat + (-half_height * dy_heading + half_width * dy_perp) / meters_per_lat),
            
            # Top right: front-right corner (+height/2 along heading, +width/2 perpendicular)
            (lon + (half_height * dx_heading + half_width * dx_perp) / meters_per_lon,
             lat + (half_height * dy_heading + half_width * dy_perp) / meters_per_lat),
            
            # Top left: front-left corner (+height/2 along heading, -width/2 perpendicular)
            (lon + (half_height * dx_heading - half_width * dx_perp) / meters_per_lon,
             lat + (half_height * dy_heading - half_width * dy_perp) / meters_per_lat)
        ]
        
        return corners
    
    def _match_image_to_nav(self, image_datetime, tolerance_seconds=60):
        """
        Find matching navigation record for an image timestamp
        
        Args:
            image_datetime: Image timestamp
            tolerance_seconds: Max allowable time difference
        
        Returns:
            Closest matching navigation record's heading or None
        """
        if self.nav_data is None or 'Datetime' not in self.nav_data.columns:
            return None
        
        try:
            # Check if we need to adjust the year (in case nav data and images have different years)
            if not hasattr(self, '_year_difference_checked'):
                self._year_difference_checked = True
                
                # Get a sample image datetime
                img_year = image_datetime.year
                nav_year = self.nav_data['Datetime'].iloc[0].year
                
                if img_year != nav_year:
                    print(f"Warning: Image year ({img_year}) differs from navigation data year ({nav_year})")
                    print(f"Will adjust image datetime year to match navigation data")
                    
                    # Store the year difference for future adjustments
                    self._year_difference = nav_year - img_year
                else:
                    self._year_difference = 0
            
            # Adjust the image datetime year if needed
            if hasattr(self, '_year_difference') and self._year_difference != 0:
                adjusted_datetime = image_datetime.replace(year=image_datetime.year + self._year_difference)
            else:
                adjusted_datetime = image_datetime
                
            # Convert to pandas timestamp for comparison
            img_time = pd.Timestamp(adjusted_datetime)
            
            # Calculate time differences
            time_diffs = abs(self.nav_data['Datetime'] - img_time)
            
            # Find closest match
            if not time_diffs.empty:
                min_diff_seconds = time_diffs.min().total_seconds()
                
                if min_diff_seconds <= tolerance_seconds:
                    closest_idx = time_diffs.idxmin()
                    closest_match = self.nav_data.iloc[closest_idx]
                    
                    # Only print for the first few matches to avoid flooding the console
                    if not hasattr(self, '_match_count'):
                        self._match_count = 0
                        
                    if self._match_count < 10:
                        print(f"Matched image at {img_time} to nav record at {closest_match['Datetime']}, "
                             f"diff: {min_diff_seconds:.2f}s, heading: {closest_match['Heading']}")
                        self._match_count += 1
                    elif self._match_count == 10:
                        print("(Suppressing further match messages)")
                        self._match_count += 1
                    
                    # Just return the heading
                    return closest_match['Heading']
                else:
                    if not hasattr(self, '_nomatch_count'):
                        self._nomatch_count = 0
                        
                    if self._nomatch_count < 5:
                        print(f"No match within tolerance: Image time {img_time}, "
                             f"closest nav diff: {min_diff_seconds:.2f}s (tolerance: {tolerance_seconds}s)")
                        self._nomatch_count += 1
                    elif self._nomatch_count == 5:
                        print("(Suppressing further no-match messages)")
                        self._nomatch_count += 1
            
        except Exception as e:
            print(f"Error matching image to nav: {e}")
            
        return None
    
    def _parse_datetime_from_filename(self, filename):
        """Extract datetime from filename format like ESC_stills_processed_PPS_2024-06-27T074938.458700_2170.jpg"""
        try:
            if '_' not in filename or 'T' not in filename:
                return None
                
            # Extract the date-time part
            parts = filename.split('_')
            datetime_part = None
            
            for part in parts:
                if 'T' in part and len(part.split('T')) == 2:
                    datetime_part = part
                    break
                    
            if not datetime_part:
                return None
                
            # Split into date and time
            date_str, time_str = datetime_part.split('T')
            
            # Remove milliseconds if present
            if '.' in time_str:
                time_str = time_str.split('.')[0]
                
            # Format time with colons if needed
            if len(time_str) >= 6 and ':' not in time_str:
                time_str = f"{time_str[0:2]}:{time_str[2:4]}:{time_str[4:6]}"
                
            # Create datetime string and parse it
            datetime_str = f"{date_str} {time_str}"
            return datetime.datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
            
        except Exception as e:
            print(f"Error parsing datetime from filename '{filename}': {e}")
            return None
    
    def create_footprint_map(self, gps_data: List[Dict], output_path: str, 
                            nav_file_path: str = None,
                            filename: str = "image_footprints_map.png") -> Optional[str]:
        """
        Create a map showing image footprints on the seafloor
        
        Args:
            gps_data: List of dictionaries with GPS and EXIF data
            output_path: Directory to save the output files
            nav_file_path: Path to vehicle navigation file
            filename: Filename for the generated map
            
        Returns:
            Path to the saved plot file, or None if no data or error
        """
        if not gps_data:
            print("No GPS data available")
            return None
        
        # Load navigation data if provided
        if nav_file_path and os.path.exists(nav_file_path):
            self.load_nav_data(nav_file_path)
        
        print(f"Processing {len(gps_data)} GPS data points")
        
        # Debug: Print the keys available in the first few GPS points
        if gps_data:
            print("First GPS point keys:", list(gps_data[0].keys()))
        
        # Extract valid points - filter by altitude threshold
        valid_points = []
        filtered_out_count = 0
        
        for point in gps_data:
            # Check if required fields are present
            if not all(key in point for key in ['latitude', 'longitude', 'altitude']):
                continue
                
            # Apply altitude threshold filter
            if point['altitude'] > self.altitude_threshold:
                filtered_out_count += 1
                continue
                
            # Add to valid points
            valid_points.append(point)
                
        if not valid_points:
            print("No valid GPS points with altitude below threshold found")
            return None
            
        print(f"Found {len(valid_points)} valid points with altitude below threshold ({filtered_out_count} points filtered out)")
        
        # Add footprint data to the points
        footprints = []
        
        # Keep track of points with/without datetime for logging
        datetime_available_count = 0
        match_found_count = 0
        
        for point in valid_points:
            # Default heading - will be used if we can't match with nav data
            heading = 0
            image_datetime = None
            
            try:
                # Try to extract datetime from the point for nav matching
                
                # Try to get DateTime from EXIF
                if 'DateTime' in point and point['DateTime'] and point['DateTime'] != 'N/A':
                    try:
                        # Handle common EXIF datetime format: "2024:06:27 07:49:38"
                        if isinstance(point['DateTime'], str):
                            if ':' in point['DateTime']:
                                # Replace colons in date part with dashes for parsing
                                date_time = point['DateTime'].replace(':', '-', 2)
                                image_datetime = parser.parse(date_time)
                            else:
                                image_datetime = parser.parse(point['DateTime'])
                        else:
                            # If it's already a datetime object
                            image_datetime = point['DateTime']
                    except Exception as e:
                        print(f"Error parsing DateTime from EXIF: {e}")
                        
                # Try from filename if DateTime not available from EXIF
                if image_datetime is None and 'filename' in point:
                    image_datetime = self._parse_datetime_from_filename(point['filename'])
                    if image_datetime:
                        print(f"Parsed datetime from filename: {image_datetime}")
                
                # If we have a datetime, count it for logging
                if image_datetime:
                    datetime_available_count += 1
                    
                    # Get heading from nav data
                    if self.nav_data is not None:
                        matched_heading = self._match_image_to_nav(image_datetime)
                        if matched_heading is not None:
                            heading = matched_heading
                            match_found_count += 1
                
                # Calculate footprint dimensions
                width, height = self._calculate_footprint(point['altitude'])
                
                # Calculate polygon vertices
                vertices = self._calculate_polygon_vertices(
                    point['latitude'], 
                    point['longitude'], 
                    point['altitude'], 
                    heading
                )
                
                # Add footprint data to the point
                footprint_data = {
                    'latitude': point['latitude'],
                    'longitude': point['longitude'],
                    'altitude': point['altitude'],
                    'heading': heading,
                    'width': width,
                    'height': height,
                    'vertices': vertices,
                    'filename': point.get('filename', 'unknown'),
                    'DateTime': str(image_datetime) if image_datetime else 'unknown'
                }
                
                footprints.append(footprint_data)
                
            except Exception as e:
                print(f"Error processing point: {e}")
                continue
        
        print(f"Created {len(footprints)} footprints for mapping")
        print(f"Points with datetime: {datetime_available_count} of {len(valid_points)}")
        print(f"Points with matched heading from nav: {match_found_count}")
        
        if not footprints:
            print("No valid footprints could be calculated")
            return None
            
        # Calculate image overlap if we have enough footprints
        overlap_stats = None
        if len(footprints) >= 2:
            print("\nCalculating image overlap...")
            overlap_stats = self.calculate_image_overlap(footprints)
        
        # Store overlap stats for later use in exports
        self.overlap_stats = overlap_stats
        
        # Create figure for plotting
        print("Creating plot...")
        fig, ax = plt.subplots(figsize=(12, 10))
        
        # Plot each footprint
        for i, fp in enumerate(footprints):
            try:
                # Plot polygon with low alpha for overlap visibility
                polygon = np.array(fp['vertices'])
                ax.fill(polygon[:, 0], polygon[:, 1], alpha=0.3, edgecolor='blue', facecolor='skyblue')
                
                # Only plot every Nth center point to reduce clutter for large datasets
                if len(footprints) > 500:
                    if i % 20 == 0:  # Plot every 20th point for large datasets
                        ax.plot(fp['longitude'], fp['latitude'], 'r.', markersize=2)
                else:
                    ax.plot(fp['longitude'], fp['latitude'], 'r.', markersize=2)
            except Exception as e:
                print(f"Error plotting footprint: {e}")
                continue
        
        # Set labels and title
        ax.set_xlabel('Longitude (Decimal Degrees)')
        ax.set_ylabel('Latitude (Decimal Degrees)')
        ax.set_title('Image Footprints on Seafloor')
        
        # Add grid
        ax.grid(True, linestyle='--', alpha=0.5)
        
        # Add statistics text box with overlap info if available
        stats_text = 'Total Images: {}\nAvg. Footprint: {:.2f}m × {:.2f}m\nAvg. Altitude: {:.2f}m'.format(
            len(footprints),
            np.mean([fp["width"] for fp in footprints]),
            np.mean([fp["height"] for fp in footprints]),
            np.mean([fp["altitude"] for fp in footprints])
        )
        
        if overlap_stats:
            stats_text += '\n\nImage Overlap:\nAvg: {:.1f}%\nMedian: {:.1f}%\nRange: {:.1f}%-{:.1f}%'.format(
                overlap_stats['avg_overlap'],
                overlap_stats['median_overlap'],
                overlap_stats['min_overlap'],
                overlap_stats['max_overlap']
            )
        
        ax.text(0.02, 0.98, stats_text, 
                transform=ax.transAxes, fontsize=9, 
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Adjust layout
        plt.tight_layout()
        
        # Save plot
        output_file = os.path.join(output_path, filename)
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        # Export to CSV and shapefile
        print("Exporting to CSV and shapefile...")
        self.export_footprints(footprints, output_path)
        
        # Create overlap map if we have enough footprints
        if len(footprints) >= 2:
            print("\nCreating image overlap map...")
            self.create_overlap_map(footprints, output_path)

        return output_file
    
    def export_footprints(self, footprints: List[Dict], output_path: str,
                         csv_filename: str = "image_footprints.csv",
                         shapefile_filename: str = "image_footprints.shp") -> Dict[str, str]:
        """
        Export footprint data to CSV and shapefile formats
        
        Args:
            footprints: List of dictionaries with footprint data
            output_path: Directory to save the output files
            csv_filename: Name for the CSV file
            shapefile_filename: Name for the shapefile
            
        Returns:
            Dictionary with paths to created files
        """
        result_files = {}
        
        # Ensure all footprints have proper formatting
        formatted_footprints = []
        for fp in footprints:
            # Format datetime for CSV
            datetime_str = fp.get('DateTime', 'unknown')
            if isinstance(datetime_str, datetime.datetime):
                datetime_str = datetime_str.strftime("%Y-%m-%d %H:%M:%S")
                
            formatted_fp = {
                'filename': fp['filename'],
                'latitude': fp['latitude'],
                'longitude': fp['longitude'],
                'altitude': fp['altitude'],
                'heading': fp['heading'],
                'width': fp['width'],
                'height': fp['height'],
                'area': fp['width'] * fp['height'],
                'DateTime': datetime_str,
                'below_threshold': 'Yes'  # Always Yes, since we've already filtered
            }
            formatted_footprints.append(formatted_fp)
        
        # Create a pandas DataFrame from the footprint data
        df = pd.DataFrame(formatted_footprints)
        
        # Replace any NaN values with "N/A"
        df = df.fillna("N/A")
        
        # Print some statistics on headings
        non_zero_headings = df[df['heading'] > 0]['heading'].count()
        total_rows = len(df)
        print(f"\nHeading statistics:")
        print(f"  Total footprints: {total_rows}")
        print(f"  Footprints with non-zero heading: {non_zero_headings} ({non_zero_headings/total_rows*100:.1f}%)")
        if non_zero_headings > 0:
            print(f"  Average heading: {df['heading'].mean():.1f} degrees")
            print(f"  Heading range: {df['heading'].min():.1f} to {df['heading'].max():.1f} degrees")
        
        # Print overlap statistics if available
        if hasattr(self, 'overlap_stats') and self.overlap_stats:
            print(f"\nImage Overlap Statistics:")
            print(f"  Average overlap: {self.overlap_stats['avg_overlap']:.1f}%")
            print(f"  Median overlap: {self.overlap_stats['median_overlap']:.1f}%")
            print(f"  Overlap range: {self.overlap_stats['min_overlap']:.1f}% to {self.overlap_stats['max_overlap']:.1f}%")
            print(f"  Low overlap (<20%): {self.overlap_stats['low_overlap']} image pairs")
            print(f"  Medium overlap (20-60%): {self.overlap_stats['medium_overlap']} image pairs")
            print(f"  High overlap (>60%): {self.overlap_stats['high_overlap']} image pairs")
        
        # Export to CSV
        csv_path = os.path.join(output_path, csv_filename)
        df.to_csv(csv_path, index=False)
        result_files['csv'] = csv_path
        print(f"Footprint data exported to CSV: {csv_path}")
        
        # Add threshold information to the statistics
        print(f"All points are below the altitude threshold of {self.altitude_threshold}m")
        
        # Export to shapefile if geopandas is available
        if GEOPANDAS_AVAILABLE:
            try:
                # Create polygon geometries from vertices
                polygons = [Polygon(fp['vertices']) for fp in footprints]
                
                # Create GeoDataFrame
                gdf = gpd.GeoDataFrame(df, geometry=polygons)
                
                # Set coordinate reference system to WGS84
                gdf.crs = "EPSG:4326"
                
                # Export to shapefile
                shapefile_path = os.path.join(output_path, shapefile_filename)
                gdf.to_file(shapefile_path)
                result_files['shapefile'] = shapefile_path
                print(f"Footprint data exported to shapefile: {shapefile_path}")
                
            except Exception as e:
                print(f"Error creating shapefile: {e}")
        else:
            print("Geopandas not available. Skipping shapefile creation.")
        
        return result_files

    def set_altitude_threshold(self, threshold):
        """Set the altitude threshold for filtering images"""
        self.altitude_threshold = threshold

    def calculate_image_overlap(self, footprints: List[Dict]) -> Dict:
        """
        Calculate overlap between sequential images in the dataset
        
        Args:
            footprints: List of footprint data dictionaries
            
        Returns:
            Dictionary with overlap statistics
        """
        if not GEOPANDAS_AVAILABLE:
            print("Geopandas not available. Cannot calculate image overlap.")
            return None
            
        if len(footprints) < 2:
            print("Not enough images to calculate overlap.")
            return None
        
        try:
            # Sort footprints by datetime if available
            sorted_footprints = []
            for fp in footprints:
                # Extract datetime from the DateTime field
                dt_str = fp.get('DateTime', None)
                if dt_str and dt_str != 'unknown':
                    try:
                        if isinstance(dt_str, str):
                            dt = parser.parse(dt_str)
                        else:
                            dt = dt_str  # Assuming it's already a datetime object
                        sorted_footprints.append((dt, fp))
                    except:
                        # If parsing fails, skip this footprint
                        pass
            
            # Sort by datetime
            sorted_footprints.sort(key=lambda x: x[0])
            
            if len(sorted_footprints) < 2:
                print("Not enough images with valid datetimes to calculate overlap.")
                return None
                
            print(f"Calculating overlap for {len(sorted_footprints)} sorted images")
            
            # Calculate overlap between sequential pairs
            overlaps = []
            overlap_areas = []
            
            for i in range(len(sorted_footprints) - 1):
                _, current_fp = sorted_footprints[i]
                _, next_fp = sorted_footprints[i + 1]
                
                # Create Shapely polygons from vertices
                current_poly = Polygon(current_fp['vertices'])
                next_poly = Polygon(next_fp['vertices'])
                
                # Calculate areas
                current_area = current_poly.area
                next_area = next_poly.area
                
                # Calculate intersection
                if current_poly.intersects(next_poly):
                    intersection = current_poly.intersection(next_poly)
                    intersection_area = intersection.area
                    
                    # Calculate overlap percentage (based on the smaller footprint)
                    smaller_area = min(current_area, next_area)
                    overlap_percent = (intersection_area / smaller_area) * 100
                    
                    overlaps.append(overlap_percent)
                    overlap_areas.append(intersection_area)
                    
                    # Debug first few overlaps
                    if i < 5:
                        print(f"Overlap {i}: {overlap_percent:.2f}% ({intersection_area:.2f}m² of {smaller_area:.2f}m²)")
            
            # Calculate statistics
            if overlaps:
                avg_overlap = np.mean(overlaps)
                min_overlap = np.min(overlaps)
                max_overlap = np.max(overlaps)
                median_overlap = np.median(overlaps)
                
                # Count images with different overlap ranges
                low_overlap = sum(1 for o in overlaps if o < 20)
                medium_overlap = sum(1 for o in overlaps if 20 <= o < 60)
                high_overlap = sum(1 for o in overlaps if o >= 60)
                
                print(f"\nOverlap Statistics:")
                print(f"  Average overlap: {avg_overlap:.2f}%")
                print(f"  Median overlap: {median_overlap:.2f}%")
                print(f"  Minimum overlap: {min_overlap:.2f}%")
                print(f"  Maximum overlap: {max_overlap:.2f}%")
                print(f"  Low overlap (<20%): {low_overlap} image pairs")
                print(f"  Medium overlap (20-60%): {medium_overlap} image pairs")
                print(f"  High overlap (>60%): {high_overlap} image pairs")
                
                return {
                    'avg_overlap': avg_overlap,
                    'median_overlap': median_overlap,
                    'min_overlap': min_overlap,
                    'max_overlap': max_overlap,
                    'total_pairs': len(overlaps),
                    'low_overlap': low_overlap,
                    'medium_overlap': medium_overlap,
                    'high_overlap': high_overlap
                }
            else:
                print("No overlap found between sequential images.")
                return None
        
        except Exception as e:
            print(f"Error calculating image overlap: {e}")
            import traceback
            print(traceback.format_exc())
            return None

    def create_overlap_map(self, footprints: List[Dict], output_path: str, 
                          filename: str = "image_overlap_map.png") -> Optional[str]:
        """
        Create a map showing overlap between sequential images
        
        Args:
            footprints: List of dictionaries with footprint data
            output_path: Directory to save the output files
            filename: Filename for the generated map
            
        Returns:
            Path to the saved plot file, or None if no data or error
        """
        if not GEOPANDAS_AVAILABLE:
            print("Geopandas not available. Cannot create overlap map.")
            return None
        
        if len(footprints) < 2:
            print("Not enough images to calculate overlap.")
            return None
        
        try:
            # Sort footprints by datetime if available
            sorted_footprints = []
            for fp in footprints:
                # Extract datetime from the DateTime field
                dt_str = fp.get('DateTime', None)
                if dt_str and dt_str != 'unknown':
                    try:
                        if isinstance(dt_str, str):
                            dt = parser.parse(dt_str)
                        else:
                            dt = dt_str  # Assuming it's already a datetime object
                        sorted_footprints.append((dt, fp))
                    except:
                        # If parsing fails, skip this footprint
                        pass
            
            # Sort by datetime
            sorted_footprints.sort(key=lambda x: x[0])
            
            if len(sorted_footprints) < 2:
                print("Not enough images with valid datetimes to calculate overlap.")
                return None
            
            # Create figure for plotting
            fig, ax = plt.subplots(figsize=(12, 10))
            
            # Calculate and plot overlaps
            for i in range(len(sorted_footprints) - 1):
                _, current_fp = sorted_footprints[i]
                _, next_fp = sorted_footprints[i + 1]
                
                # Create Shapely polygons from vertices
                current_poly = Polygon(current_fp['vertices'])
                next_poly = Polygon(next_fp['vertices'])
                
                # Plot the footprints with low alpha
                current_poly_coords = np.array(current_fp['vertices'])
                next_poly_coords = np.array(next_fp['vertices'])
                
                ax.fill(current_poly_coords[:, 0], current_poly_coords[:, 1], 
                       alpha=0.2, edgecolor='blue', facecolor='skyblue')
                ax.fill(next_poly_coords[:, 0], next_poly_coords[:, 1], 
                       alpha=0.2, edgecolor='green', facecolor='lightgreen')
                
                # Calculate and plot intersection if it exists
                if current_poly.intersects(next_poly):
                    intersection = current_poly.intersection(next_poly)
                    
                    # Extract coordinates from the intersection geometry
                    if intersection.geom_type == 'Polygon':
                        x, y = intersection.exterior.xy
                        ax.fill(x, y, alpha=0.6, edgecolor='red', facecolor='orange')
                    
                    # For multi-polygons, extract each polygon
                    elif intersection.geom_type == 'MultiPolygon':
                        for poly in intersection.geoms:
                            x, y = poly.exterior.xy
                            ax.fill(x, y, alpha=0.6, edgecolor='red', facecolor='orange')
            
            # Set labels and title
            ax.set_xlabel('Longitude (Decimal Degrees)')
            ax.set_ylabel('Latitude (Decimal Degrees)')
            ax.set_title('Image Overlap Analysis')
            
            # Add grid
            ax.grid(True, linestyle='--', alpha=0.5)
            
            # Add legend
            import matplotlib.patches as mpatches
            blue_patch = mpatches.Patch(color='skyblue', alpha=0.2, label='Image N')
            green_patch = mpatches.Patch(color='lightgreen', alpha=0.2, label='Image N+1')
            orange_patch = mpatches.Patch(color='orange', alpha=0.6, label='Overlap')
            ax.legend(handles=[blue_patch, green_patch, orange_patch], loc='upper right')
            
            # Add overlap statistics if available
            if hasattr(self, 'overlap_stats') and self.overlap_stats:
                stats_text = 'Overlap Statistics:\n'
                stats_text += 'Avg: {:.1f}%\n'.format(self.overlap_stats['avg_overlap'])
                stats_text += 'Median: {:.1f}%\n'.format(self.overlap_stats['median_overlap'])
                stats_text += 'Range: {:.1f}%-{:.1f}%\n'.format(
                    self.overlap_stats['min_overlap'], 
                    self.overlap_stats['max_overlap']
                )
                stats_text += 'Image pairs: {}\n'.format(self.overlap_stats['total_pairs'])
                stats_text += 'Low (<20%): {}\n'.format(self.overlap_stats['low_overlap'])
                stats_text += 'Medium (20-60%): {}\n'.format(self.overlap_stats['medium_overlap'])
                stats_text += 'High (>60%): {}'.format(self.overlap_stats['high_overlap'])
                
                ax.text(0.02, 0.98, stats_text, 
                        transform=ax.transAxes, fontsize=9, 
                        verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            
            # Adjust layout
            plt.tight_layout()
            
            # Save plot
            output_file = os.path.join(output_path, filename)
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"Image overlap map saved to: {output_file}")
            return output_file
            
        except Exception as e:
            print(f"Error creating overlap map: {e}")
            import traceback
            print(traceback.format_exc())
            return None

