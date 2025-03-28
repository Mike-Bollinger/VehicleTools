import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os
from typing import List, Dict, Optional, Tuple
import warnings
import datetime
from dateutil import parser
import traceback

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
        
        # Adjust layout
        plt.tight_layout()
        
        # Configure axis formatting to show full coordinate values
        # Round to 6 decimal places (approximately 0.1 meter precision)
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:.6f}"))
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:.6f}"))
        
        # Rotate x-axis labels for better readability
        plt.xticks(rotation=45, ha='right')
        
        # Adjust layout to accommodate the longer tick labels
        plt.tight_layout()
        
        # Save plot
        output_file = os.path.join(output_path, filename)
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        # Calculate all types of overlap first
        
        # Calculate vertical overlap
        if len(footprints) >= 2:
            print("\nCalculating vertical overlap between sequential images...")
            vertical_overlap_stats = self.calculate_vertical_overlap(footprints)
            print("Vertical overlap calculation complete")
            # Store overlap stats for later use in exports
            self.vertical_overlap_stats = vertical_overlap_stats


        
        # Calculate horizontal overlap
        if len(footprints) >= 21:  # Need at least min_separation+1 images
            print("\nCalculating horizontal overlap...")
            horizontal_overlap_stats = self.calculate_horizontal_overlap(footprints)
            print("Horizontal overlap calculation complete")
            # Store overlap stats for later use in exports
            self.horizontal_overlap_stats = horizontal_overlap_stats
        
        # Calculate overall overlap
        if len(footprints) >= 2:
            print("\nCalculating overall overlap...")
            overall_overlap_stats = self.calculate_overall_overlap(footprints)
            print("Overall overlap calculation complete")
            # Store overlap stats for later use in exports
            self.overall_overlap_stats = overall_overlap_stats


        # Export to CSV and shapefile AFTER all overlap metrics are calculated
        print("\nExporting to CSV and shapefile...")
        self.export_footprints(footprints, output_path) 
        
               
        # Create various overlap maps
        
        # Create vertical overlap map
        if len(footprints) >= 2:
            print("\nCreating vertical overlap map...")
            self.create_vertical_overlap_map(footprints, output_path)
            print("Vertical overlap map created")
        
        # Create horizontal overlap map
        if len(footprints) >= 21:  # Need at least min_separation+1 images
            print("\nCreating horizontal overlap map...")
            self.create_horizontal_overlap_map(footprints, output_path)
            print("Horizontal overlap map created")
        
        # Create overall overlap map
        if len(footprints) >= 2:
            print("\nCreating overall overlap map...")
            self.create_overall_overlap_map(footprints, output_path)
            print("Overall overlap map created")
        
        # Identify meaningful subsets and create all zoomed maps in one place
        subsets = self.identify_subsets(footprints)
        if subsets:
            self.create_zoomed_maps(footprints, subsets, output_path)
        

        
        return output_file

    def calculate_vertical_overlap(self, footprints: List[Dict]) -> Dict:
        """
        Calculate overlap between sequential images in a survey line
        
        Args:
            footprints: List of footprint data dictionaries
            
        Returns:
            Dictionary with overlap statistics and detailed overlap data
        """
        if not GEOPANDAS_AVAILABLE:
            print("Geopandas not available. Cannot calculate vertical overlap.")
            return None
            
        if len(footprints) < 2:
            print("Not enough images to calculate vertical overlap.")
            return None
        
        try:
            # Sort footprints by filename (which should put them in sequence)
            sorted_footprints = sorted(footprints, key=lambda x: x['filename'])
            
            # Calculate overlaps between sequential images
            overlap_data = []
            total_overlap_area = 0
            total_overlap_count = 0
            
            # Counters for overlap categories
            low_overlap = 0
            medium_overlap = 0
            high_overlap = 0
            
            for i in range(len(sorted_footprints) - 1):
                current_fp = sorted_footprints[i]
                next_fp = sorted_footprints[i + 1]
                
                # Create Shapely polygons
                current_poly = Polygon(current_fp['vertices'])
                next_poly = Polygon(next_fp['vertices'])
                
                # Calculate intersection
                if current_poly.intersects(next_poly):
                    intersection = current_poly.intersection(next_poly)
                    
                    # Calculate overlap area and percentage
                    current_area = current_poly.area
                    next_area = next_poly.area
                    intersection_area = intersection.area
                    
                    # Overlap as percentage of the smaller footprint
                    overlap_percent = (intersection_area / min(current_area, next_area)) * 100.0
                    
                    # Calculate center point of intersection
                    if intersection.geom_type == 'Polygon':
                        midpoint = (intersection.centroid.x, intersection.centroid.y)
                    elif intersection.geom_type == 'MultiPolygon':
                        # Find the largest polygon in the collection
                        largest_poly = max(intersection.geoms, key=lambda p: p.area)
                        midpoint = (largest_poly.centroid.x, largest_poly.centroid.y)
                    else:
                        # Default to midpoint between the two footprints
                        midpoint = ((current_fp['longitude'] + next_fp['longitude']) / 2,
                                   (current_fp['latitude'] + next_fp['latitude']) / 2)
                    
                    # Categorize overlap
                    if overlap_percent < 40:
                        overlap_category = 'low'
                        low_overlap += 1
                    elif overlap_percent < 70:
                        overlap_category = 'medium'
                        medium_overlap += 1
                    else:
                        overlap_category = 'high'
                        high_overlap += 1
                    
                    # Store overlap data for this pair
                    overlap_info = {
                        'current_fp': current_fp,
                        'next_fp': next_fp,
                        'overlap_area': intersection_area,
                        'overlap_percent': overlap_percent,
                        'category': overlap_category,
                        'midpoint': midpoint,
                        'intersection': intersection
                    }
                    
                    overlap_data.append(overlap_info)
                    total_overlap_area += intersection_area
                    total_overlap_count += 1
            
            # Calculate statistics
            if total_overlap_count > 0:
                overlap_percentages = [d['overlap_percent'] for d in overlap_data]
                avg_overlap = sum(overlap_percentages) / len(overlap_percentages)
                median_overlap = np.median(overlap_percentages)
                min_overlap = min(overlap_percentages)
                max_overlap = max(overlap_percentages)
            else:
                avg_overlap = 0
                median_overlap = 0
                min_overlap = 0
                max_overlap = 0
            
            print(f"\nVertical Overlap Statistics:")
            print(f"  Total overlapping pairs: {total_overlap_count}")
            print(f"  Average overlap: {avg_overlap:.2f}%")
            print(f"  Median overlap: {median_overlap:.2f}%")
            print(f"  Range: {min_overlap:.2f}% - {max_overlap:.2f}%")
            print(f"  Low overlap (<40%): {low_overlap}")
            print(f"  Medium overlap (40-70%): {medium_overlap}")
            print(f"  High overlap (>70%): {high_overlap}")
            
            return {
                'overlap_data': overlap_data,
                'total_overlap_count': total_overlap_count,
                'avg_overlap': avg_overlap,
                'median_overlap': median_overlap,
                'min_overlap': min_overlap,
                'max_overlap': max_overlap,
                'low_overlap': low_overlap,
                'medium_overlap': medium_overlap,
                'high_overlap': high_overlap
            }
        
        except Exception as e:
            print(f"Error calculating vertical overlap: {e}")
            import traceback
            print(traceback.format_exc())
            return None

    def calculate_horizontal_overlap(self, footprints: List[Dict], min_separation: int = 20) -> Dict:
        """
        Calculate overlap between non-sequential images (likely in adjacent survey lines)
        
        Args:
            footprints: List of footprint data dictionaries
            min_separation: Minimum separation in sequence to consider non-sequential
            
        Returns:
            Dictionary with overlap statistics and detailed overlap data
        """
        if not GEOPANDAS_AVAILABLE:
            print("Geopandas not available. Cannot calculate horizontal overlap.")
            return None
            
        if len(footprints) < min_separation + 1:
            print(f"Not enough images to calculate horizontal overlap (need at least {min_separation + 1}).")
            return None
        
        try:
            print(f"Calculating horizontal overlap for {len(footprints)} images...")
            
            # Sort footprints by filename for consistent ordering
            sorted_footprints = [(i, fp) for i, fp in enumerate(sorted(footprints, key=lambda x: x['filename']))]
            
            # Create an RTtree spatial index for fast intersection checks
            try:
                from rtree import index
                
                # Set up the spatial index
                idx = index.Index()
                poly_lookup = {}
                
                # Add polygons to the spatial index
                for i, (idx_i, fp) in enumerate(sorted_footprints):
                    poly = Polygon(fp['vertices'])
                    # Store the polygon and index in the lookup dictionary
                    poly_lookup[i] = (idx_i, fp, poly)
                    # Add to spatial index using the polygon's bounds (minx, miny, maxx, maxy)
                    idx.insert(i, poly.bounds)
                
                print("Using RTree spatial index for efficient overlap calculation")
            except ImportError:
                print("RTree not available, falling back to brute force comparison (slower)")
                idx = None
                
            # Calculate overlaps between non-sequential images
            overlap_data = []
            total_overlap_count = 0
            
            # Counters for overlap categories
            low_overlap = 0    # < 10%
            medium_overlap = 0 # 10-40%
            high_overlap = 0   # > 40%
            
            # Process in chunks to show progress
            total_checks = 0
            chunk_size = min(1000, len(sorted_footprints) // 10 or 1)
            
            # If we have RTree, use spatial index to speed up calculations
            if idx is not None:
                for i, (idx_i, fp) in enumerate(sorted_footprints):
                    # Create polygon for current footprint
                    poly = Polygon(fp['vertices'])
                    
                    # Show progress for large datasets
                    if i % chunk_size == 0 and i > 0:
                        print(f"Processed {i}/{len(sorted_footprints)} footprints, found {total_overlap_count} horizontal overlaps")
                    
                    # Find potential intersections using the spatial index
                    potential_matches = list(idx.intersection(poly.bounds))
                    
                    for j in potential_matches:
                        idx_j, distant_fp, distant_poly = poly_lookup[j]
                        
                        # Skip self-comparison
                        if idx_i == idx_j:
                            continue
                            
                        # Skip if the images are close in sequence (likely same survey line)
                        if abs(idx_i - idx_j) < min_separation:
                            continue
                        
                        total_checks += 1
                        
                        # Now do the exact intersection check
                        if poly.intersects(distant_poly):
                            intersection = poly.intersection(distant_poly)
                            
                            # Calculate overlap area and percentage
                            current_area = poly.area
                            distant_area = distant_poly.area
                            intersection_area = intersection.area
                            
                            # Overlap as percentage of the smaller footprint
                            overlap_percent = (intersection_area / min(current_area, distant_area)) * 100.0
                            
                            # Calculate center point of intersection
                            if intersection.geom_type == 'Polygon':
                                midpoint = (intersection.centroid.x, intersection.centroid.y)
                            elif intersection.geom_type == 'MultiPolygon':
                                largest_poly = max(intersection.geoms, key=lambda p: p.area)
                                midpoint = (largest_poly.centroid.x, largest_poly.centroid.y)
                            else:
                                midpoint = ((fp['longitude'] + distant_fp['longitude']) / 2,
                                           (fp['latitude'] + distant_fp['latitude']) / 2)
                            
                            # Categorize overlap - horizontal overlaps are typically lower than vertical
                            if overlap_percent < 10:
                                overlap_category = 'low'
                                low_overlap += 1
                            elif overlap_percent < 40:
                                overlap_category = 'medium'
                                medium_overlap += 1
                            else:
                                overlap_category = 'high'
                                high_overlap += 1
                            
                            # Store overlap data for this pair
                            overlap_info = {
                                'current_fp': fp,
                                'next_fp': distant_fp,
                                'overlap_area': intersection_area,
                                'overlap_percent': overlap_percent,
                                'category': overlap_category,
                                'midpoint': midpoint,
                                'intersection': intersection,
                                'sequence_distance': abs(idx_i - idx_j)
                            }
                            
                            overlap_data.append(overlap_info)
                            total_overlap_count += 1
            else:
                # Fallback to brute force comparison if RTree is not available
                for i in range(len(sorted_footprints)):
                    idx_i, current_fp = sorted_footprints[i]
                    current_poly = Polygon(current_fp['vertices'])
                    
                    # Show progress for large datasets
                    if i % chunk_size == 0 and i > 0:
                        print(f"Processed {i}/{len(sorted_footprints)} footprints, found {total_overlap_count} horizontal overlaps")
                    
                    for j in range(i + 1, len(sorted_footprints)):
                        idx_j, distant_fp = sorted_footprints[j]
                        
                        # Skip if the images are close in sequence (likely same survey line)
                        if abs(idx_i - idx_j) < min_separation:
                            continue
                        
                        total_checks += 1
                        
                        # Create Shapely polygon
                        distant_poly = Polygon(distant_fp['vertices'])
                        
                        # Check for intersection
                        if current_poly.intersects(distant_poly):
                            intersection = current_poly.intersection(distant_poly)
                            
                            # Calculate overlap area and percentage
                            current_area = current_poly.area
                            distant_area = distant_poly.area
                            intersection_area = intersection.area
                            
                            # Overlap as percentage of the smaller footprint
                            overlap_percent = (intersection_area / min(current_area, distant_area)) * 100.0
                            
                            # Calculate center point of intersection
                            if intersection.geom_type == 'Polygon':
                                midpoint = (intersection.centroid.x, intersection.centroid.y)
                            elif intersection.geom_type == 'MultiPolygon':
                                largest_poly = max(intersection.geoms, key=lambda p: p.area)
                                midpoint = (largest_poly.centroid.x, largest_poly.centroid.y)
                            else:
                                midpoint = ((current_fp['longitude'] + distant_fp['longitude']) / 2,
                                           (current_fp['latitude'] + distant_fp['latitude']) / 2)
                            
                            # Categorize overlap - horizontal overlaps are typically lower than vertical
                            if overlap_percent < 10:
                                overlap_category = 'low'
                                low_overlap += 1
                            elif overlap_percent < 40:
                                overlap_category = 'medium'
                                medium_overlap += 1
                            else:
                                overlap_category = 'high'
                                high_overlap += 1
                            
                            # Store overlap data for this pair
                            overlap_info = {
                                'current_fp': current_fp,
                                'next_fp': distant_fp,
                                'overlap_area': intersection_area,
                                'overlap_percent': overlap_percent,
                                'category': overlap_category,
                                'midpoint': midpoint,
                                'intersection': intersection,
                                'sequence_distance': abs(idx_i - idx_j)
                            }
                            
                            overlap_data.append(overlap_info)
                            total_overlap_count += 1
            
            # Calculate statistics
            if total_overlap_count > 0:
                overlap_percentages = [d['overlap_percent'] for d in overlap_data]
                avg_overlap = sum(overlap_percentages) / len(overlap_percentages)
                median_overlap = np.median(overlap_percentages)
                min_overlap = min(overlap_percentages)
                max_overlap = max(overlap_percentages)
                avg_sequence_distance = np.mean([d['sequence_distance'] for d in overlap_data])
            else:
                avg_overlap = 0
                median_overlap = 0
                min_overlap = 0
                max_overlap = 0
                avg_sequence_distance = 0
            
            print(f"\nHorizontal Overlap Statistics:")
            print(f"  Total pairs checked: {total_checks}")
            print(f"  Total overlapping pairs: {total_overlap_count}")
            print(f"  Average overlap: {avg_overlap:.2f}%")
            print(f"  Median overlap: {median_overlap:.2f}%")
            print(f"  Range: {min_overlap:.2f}% - {max_overlap:.2f}%")
            print(f"  Low overlap (<10%): {low_overlap}")
            print(f"  Medium overlap (10-40%): {medium_overlap}")
            print(f"  High overlap (>40%): {high_overlap}")
            print(f"  Average sequence distance: {avg_sequence_distance:.1f} images")
            
            return {
                'overlap_data': overlap_data,
                'total_overlap_count': total_overlap_count,
                'total_checks': total_checks,
                'avg_overlap': avg_overlap,
                'median_overlap': median_overlap,
                'min_overlap': min_overlap,
                'max_overlap': max_overlap,
                'low_overlap': low_overlap,
                'medium_overlap': medium_overlap,
                'high_overlap': high_overlap,
                'avg_sequence_distance': avg_sequence_distance
            }
        
        except Exception as e:
            print(f"Error calculating horizontal overlap: {e}")
            import traceback
            print(traceback.format_exc())
            return None

    def calculate_overall_overlap(self, footprints: List[Dict]) -> Dict:
        """Calculate overlap between all image footprints, counting how many overlaps each footprint has"""
        if not GEOPANDAS_AVAILABLE:
            print("Geopandas not available. Cannot calculate overall overlap.")
            return None
            
        if len(footprints) < 2:
            print("Not enough images to calculate overall overlap.")
            return None
        
        try:
            print(f"Calculating overall overlap for {len(footprints)} images")
            
            # Create Shapely polygons from vertices
            polygons = []
            for i, fp in enumerate(footprints):
                poly = Polygon(fp['vertices'])
                polygons.append({
                    'index': i,
                    'polygon': poly, 
                    'footprint': fp,
                    'overlap_count': 0,  # Will track number of other footprints overlapping this one
                    'overlapping_indices': []  # Will track which footprints overlap with this one
                })
            
            # Variables for tracking overlap statistics
            total_checks = 0
            total_overlaps = 0
            
            # Process in chunks to show progress
            chunk_size = min(1000, len(polygons) // 10 or 1)
            
            # Try to use RTree spatial index for faster overlap calculations
            rtree_available = False
            try:
                from rtree import index
                
                # Set up the spatial index
                idx = index.Index()
                
                # Add polygons to the spatial index
                for i, poly_data in enumerate(polygons):
                    # Add to spatial index using the polygon's bounds (minx, miny, maxx, maxy)
                    idx.insert(i, poly_data['polygon'].bounds)
                    
                print("Using RTree spatial index for efficient overlap calculation")
                rtree_available = True
                
                # Calculate all pairwise overlaps using the spatial index
                for i, current in enumerate(polygons):
                    # Find potential intersections using the spatial index
                    potential_matches = list(idx.intersection(current['polygon'].bounds))
                    
                    # Skip self-comparison and check actual intersections
                    for j in potential_matches:
                        if i == j:
                            continue
                            
                        total_checks += 1
                        other = polygons[j]
                        
                        # Calculate intersection
                        if current['polygon'].intersects(other['polygon']):
                            current['overlap_count'] += 1
                            current['overlapping_indices'].append(j)
                            total_overlaps += 1
                            
                    # Show progress for large datasets
                    if i % chunk_size == 0 and i > 0:
                        print(f"Processed {i}/{len(polygons)} images, found {total_overlaps} overlaps so far")
                        
            except ImportError:
                print("RTree not available, falling back to brute force comparison (slower)")
                
            # If RTree failed or wasn't available, use brute force comparison
            if not rtree_available:
                # Calculate all pairwise overlaps using brute force
                for i in range(len(polygons)):
                    current = polygons[i]
                    
                    # Compare with all other footprints
                    for j in range(len(polygons)):
                        if i == j:
                            continue
                            
                        total_checks += 1
                        other = polygons[j]
                        
                        # Calculate intersection
                        if current['polygon'].intersects(other['polygon']):
                            current['overlap_count'] += 1
                            current['overlapping_indices'].append(j)
                            total_overlaps += 1
                            
                    # Show progress for large datasets
                    if i % chunk_size == 0 and i > 0:
                        print(f"Processed {i}/{len(polygons)} images, found {total_overlaps} overlaps so far")
            
            # Extract overlap counts and statistics
            overlap_counts = [p['overlap_count'] for p in polygons]
            
            # Calculate statistics
            avg_count = np.mean(overlap_counts)
            median_count = np.median(overlap_counts)
            min_count = np.min(overlap_counts)
            max_count = np.max(overlap_counts)
            
            print(f"\nOverall Overlap Statistics:")
            print(f"  Total pairs checked: {total_checks}")
            print(f"  Total overlapping pairs: {total_overlaps}")
            print(f"  Average overlap count per image: {avg_count:.2f}")
            print(f"  Median overlap count: {median_count:.2f}")
            print(f"  Minimum overlap count: {min_count}")
            print(f"  Maximum overlap count: {max_count}")
            
            # Store the results
            return {
                'avg_count': avg_count,
                'median_count': median_count,
                'min_count': min_count,
                'max_count': max_count,
                'total_checks': total_checks,
                'total_overlaps': total_overlaps,
                'polygons': polygons  # Store for mapping
            }
            
        except Exception as e:
            print(f"Error calculating overall overlap: {e}")
            import traceback
            print(traceback.format_exc())
            return None

    def create_vertical_overlap_map(self, footprints: List[Dict], output_path: str, 
                                  filename: str = "vertical_overlap_map.png") -> Optional[str]:
        """
        Create a map showing vertical overlap between sequential images
        
        Args:
            footprints: List of dictionaries with footprint data
            output_path: Directory to save the output files
            filename: Filename for the generated map
            
        Returns:
            Path to the saved plot file, or None if no data or error
        """
        if not GEOPANDAS_AVAILABLE:
            print("Geopandas not available. Cannot create vertical overlap map.")
            return None
            
        if not hasattr(self, 'vertical_overlap_stats') or not self.vertical_overlap_stats:
            print("No vertical overlap data available.")
            return None
        
        try:
            # Use non-interactive backend to avoid threading issues
            import matplotlib
            matplotlib.use('Agg')
            
            # Create figure for plotting
            fig, ax = plt.subplots(figsize=(12, 10))
            
            # Setup colors
            low_color = '#FF4040'      # Red
            medium_color = '#FFFF40'   # Yellow
            high_color = '#40FF40'     # Green
            
            # Plot all footprints with very low alpha for context
            for fp in footprints:
                polygon = np.array(fp['vertices'])
                ax.fill(polygon[:, 0], polygon[:, 1], alpha=0.05, edgecolor='gray', facecolor='whitesmoke')
            
            # Plot overlap regions with colors by category
            for overlap in self.vertical_overlap_stats['overlap_data']:
                intersection = overlap['intersection']
                category = overlap['category']
                
                # Set color based on overlap category
                if category == 'low':
                    color = low_color
                elif category == 'medium':
                    color = medium_color
                else:
                    color = high_color
                
                # Plot intersection
                if intersection.geom_type == 'Polygon':
                    x, y = intersection.exterior.xy
                    ax.fill(x, y, alpha=0.7, edgecolor='none', facecolor=color)
                    
                    # Add percentage label for larger polygons
                    if intersection.area > 0.0001:
                        centroid = intersection.centroid
                        ax.text(centroid.x, centroid.y, f"{overlap['overlap_percent']:.0f}%", 
                               fontsize=8, ha='center', va='center', color='black',
                               bbox=dict(facecolor='white', alpha=0.7, pad=1, boxstyle='round,pad=0.2'))
                    
                elif intersection.geom_type == 'MultiPolygon':
                    for poly in intersection.geoms:
                        x, y = poly.exterior.xy
                        ax.fill(x, y, alpha=0.7, edgecolor='none', facecolor=color)
            
            # Set labels and title
            ax.set_xlabel('Longitude (Decimal Degrees)')
            ax.set_ylabel('Latitude (Decimal Degrees)')
            ax.set_title('Vertical Overlap Between Sequential Images')
            
            # Add grid
            ax.grid(True, linestyle='--', alpha=0.3)
            
            # Create legend
            from matplotlib.patches import Patch
            legend_elements = [
                Patch(facecolor=low_color, edgecolor='none', alpha=0.7, label='Low (<40%)'),
                Patch(facecolor=medium_color, edgecolor='none', alpha=0.7, label='Medium (40-70%)'),
                Patch(facecolor=high_color, edgecolor='none', alpha=0.7, label='High (>70%)')
            ]
            ax.legend(handles=legend_elements, loc='upper right')
            
            # Add statistics
            stats = self.vertical_overlap_stats
            stats_text = 'Vertical Overlap Statistics:\n'
            stats_text += f'Avg: {stats["avg_overlap"]:.1f}%\n'
            stats_text += f'Median: {stats["median_overlap"]:.1f}%\n'
            stats_text += f'Range: {stats["min_overlap"]:.1f}% - {stats["max_overlap"]:.1f}%\n'
            stats_text += f'Low: {stats["low_overlap"]} pairs\n'
            stats_text += f'Medium: {stats["medium_overlap"]} pairs\n'
            stats_text += f'High: {stats["high_overlap"]} pairs'
            
            ax.text(0.02, 0.98, stats_text, 
                    transform=ax.transAxes, fontsize=9, 
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            
            # Configure axis formatting
            ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:.6f}"))
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:.6f}"))
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            # Save plot
            output_file = os.path.join(output_path, filename)
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close(fig)
            
            return output_file
            
        except Exception as e:
            print(f"Error creating vertical overlap map: {e}")
            print(traceback.format_exc())
            return None

    def create_horizontal_overlap_map(self, footprints: List[Dict], output_path: str, 
                                   filename: str = "horizontal_overlap_map.png") -> Optional[str]:
        """
        Create a map showing horizontal overlap between non-sequential images
        
        Args:
            footprints: List of dictionaries with footprint data
            output_path: Directory to save the output files
            filename: Filename for the generated map
            
        Returns:
            Path to the saved plot file, or None if no data or error
        """
        if not GEOPANDAS_AVAILABLE:
            print("Geopandas not available. Cannot create horizontal overlap map.")
            return None
            
        if not hasattr(self, 'horizontal_overlap_stats') or not self.horizontal_overlap_stats:
            print("No horizontal overlap data available.")
            return None
        
        try:
            # Use non-interactive backend
            import matplotlib
            matplotlib.use('Agg')
            
            # Create figure for plotting
            fig, ax = plt.subplots(figsize=(12, 10))
            
            # Setup colors - different color scheme than vertical to distinguish
            low_color = '#FF4040'      # Red
            medium_color = '#FFA500'   # Orange
            high_color = '#40FF40'     # Green
            
            # Plot all footprints with very low alpha for context
            for fp in footprints:
                polygon = np.array(fp['vertices'])
                ax.fill(polygon[:, 0], polygon[:, 1], alpha=0.05, edgecolor='gray', facecolor='whitesmoke')
            
            # Plot overlap regions with colors by category
            for overlap in self.horizontal_overlap_stats['overlap_data']:
                intersection = overlap['intersection']
                category = overlap['category']
                
                # Set color based on overlap category
                if category == 'low':
                    color = low_color
                elif category == 'medium':
                    color = medium_color
                else:
                    color = high_color
                
                # Plot intersection
                if intersection.geom_type == 'Polygon':
                    x, y = intersection.exterior.xy
                    ax.fill(x, y, alpha=0.7, edgecolor='none', facecolor=color)
                    
                    # Add percentage label for larger polygons
                    if intersection.area > 0.0001:
                        centroid = intersection.centroid
                        ax.text(centroid.x, centroid.y, f"{overlap['overlap_percent']:.0f}%", 
                               fontsize=8, ha='center', va='center', color='black',
                               bbox=dict(facecolor='white', alpha=0.7, pad=1, boxstyle='round,pad=0.2'))
                    
                elif intersection.geom_type == 'MultiPolygon':
                    for poly in intersection.geoms:
                        x, y = poly.exterior.xy
                        ax.fill(x, y, alpha=0.7, edgecolor='none', facecolor=color)
            
            # Set labels and title
            ax.set_xlabel('Longitude (Decimal Degrees)')
            ax.set_ylabel('Latitude (Decimal Degrees)')
            ax.set_title('Horizontal Overlap Between Non-Sequential Images')
            
            # Add grid
            ax.grid(True, linestyle='--', alpha=0.3)
            
            # Create legend
            from matplotlib.patches import Patch
            legend_elements = [
                Patch(facecolor=low_color, edgecolor='none', alpha=0.7, label='Low (<10%)'),
                Patch(facecolor=medium_color, edgecolor='none', alpha=0.7, label='Medium (10-40%)'),
                Patch(facecolor=high_color, edgecolor='none', alpha=0.7, label='High (>40%)')
            ]
            ax.legend(handles=legend_elements, loc='upper right')
            
            # Add statistics
            stats = self.horizontal_overlap_stats
            stats_text = 'Horizontal Overlap Statistics:\n'
            stats_text += f'Avg: {stats["avg_overlap"]:.1f}%\n'
            stats_text += f'Median: {stats["median_overlap"]:.1f}%\n'
            stats_text += f'Range: {stats["min_overlap"]:.1f}% - {stats["max_overlap"]:.1f}%\n'
            stats_text += f'Low: {stats["low_overlap"]} pairs\n'
            stats_text += f'Medium: {stats["medium_overlap"]} pairs\n'
            stats_text += f'High: {stats["high_overlap"]} pairs'
            
            ax.text(0.02, 0.98, stats_text, 
                    transform=ax.transAxes, fontsize=9, 
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            
            # Configure axis formatting
            ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:.6f}"))
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:.6f}"))
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            # Save plot
            output_file = os.path.join(output_path, filename)
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close(fig)
            
            return output_file
            
        except Exception as e:
            print(f"Error creating horizontal overlap map: {e}")
            print(traceback.format_exc())
            return None

    def create_overall_overlap_map(self, footprints: List[Dict], output_path: str, 
                                filename: str = "overall_overlap_map.png") -> Optional[str]:
        """
        Create a map showing overall overlap counts with rainbow color gradient
        
        Args:
            footprints: List of dictionaries with footprint data
            output_path: Directory to save the output files
            filename: Filename for the generated map
            
        Returns:
            Path to the saved plot file, or None if no data or error
        """
        if not GEOPANDAS_AVAILABLE:
            print("Geopandas not available. Cannot create overall overlap map.")
            return None
        
        # Calculate overall overlap if not already done
        if not hasattr(self, 'overall_overlap_stats') or not self.overall_overlap_stats:
            print("No overall overlap data available.")
            return None
        
        try:
            # Use non-interactive backend to avoid threading issues
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.colors as mcolors
            
            # Create figure for plotting
            fig, ax = plt.subplots(figsize=(14, 12))
            
            # Get polygons with overlap counts
            polygons = self.overall_overlap_stats['polygons']
            
            # Create a rainbow colormap from blue/purple (high) to red (low)
            # This reverses the usual rainbow order to have purple as highest
            cmap = plt.cm.rainbow_r
            
            # Determine color normalization based on overlap count range
            min_count = self.overall_overlap_stats['min_count']
            max_count = self.overall_overlap_stats['max_count']
            
            # Create a normalization that handles the case where min=max
            if min_count == max_count:
                norm = mcolors.Normalize(vmin=min_count-0.5, vmax=max_count+0.5)
            else:
                norm = mcolors.Normalize(vmin=min_count, vmax=max_count)
            
            # Plot each footprint with color based on overlap count
            for poly_data in polygons:
                count = poly_data['overlap_count']
                polygon = poly_data['polygon']
                
                # Get color from colormap
                color = cmap(norm(count))
                
                # Plot polygon
                x, y = polygon.exterior.xy
                ax.fill(x, y, alpha=0.7, edgecolor='none', linewidth=0, facecolor=color)
                
                # Add count label for larger polygons
                if polygon.area > 0.0001:
                    centroid = polygon.centroid
                    ax.text(centroid.x, centroid.y, str(count), 
                           fontsize=8, ha='center', va='center', color='white',
                           bbox=dict(facecolor='black', alpha=0.5, pad=1, boxstyle='round,pad=0.2'))
            
            # Set labels and title
            ax.set_xlabel('Longitude (Decimal Degrees)')
            ax.set_ylabel('Latitude (Decimal Degrees)')
            ax.set_title('Overall Image Overlap Count')
            
            # Add grid
            ax.grid(True, linestyle='--', alpha=0.3)
            
            # Add a colorbar
            sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
            sm.set_array([])  # ScalarMappable needs an array for the colorbar
            cbar = plt.colorbar(sm, ax=ax)
            cbar.set_label('Number of Overlapping Images')
            
            # Add overlap statistics
            stats_text = 'Overall Overlap Statistics:\n'
            stats_text += f'Avg overlaps: {self.overall_overlap_stats["avg_count"]:.1f} images\n'
            stats_text += f'Median: {self.overall_overlap_stats["median_count"]:.1f} images\n'
            stats_text += f'Range: {self.overall_overlap_stats["min_count"]} to {self.overall_overlap_stats["max_count"]} images\n'
            
            ax.text(0.02, 0.98, stats_text, 
                    transform=ax.transAxes, fontsize=9, 
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            
            # Configure axis formatting to show full coordinate values
            ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:.6f}"))
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:.6f}"))
            
            # Rotate x-axis labels for better readability
            plt.xticks(rotation=45, ha='right')
            
            # Adjust layout to accommodate the longer tick labels
            plt.tight_layout()
            
            # Save plot
            output_file = os.path.join(output_path, filename)
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close(fig)  # Explicitly close figure
            
            print(f"Overall overlap map saved to: {output_file}")
            return output_file
            
        except Exception as e:
            print(f"Error creating overall overlap map: {e}")
            import traceback
            print(traceback.format_exc())
            return None

    def export_footprints(self, footprints: List[Dict], output_path: str,
                         csv_filename: str = "image_footprints.csv",
                         shapefile_filename: str = "image_footprints.shp") -> Dict[str, str]:
        """
        Export footprint data to CSV and shapefile formats, including overlap metrics
        
        Args:
            footprints: List of dictionaries with footprint data
            output_path: Directory to save the output files
            csv_filename: Name for the CSV file
            shapefile_filename: Name for the shapefile
            
        Returns:
            Dictionary with paths to created files
        """
        if not footprints:
            print("No footprint data to export")
            return {}
        
        result_files = {}
        
        try:
            # Create lookup dictionaries for overlap metrics
            vertical_overlaps = {}
            horizontal_overlaps = {}
            overall_overlap_counts = {}
            
            # Build vertical overlap lookup if available
            if hasattr(self, 'vertical_overlap_stats') and self.vertical_overlap_stats and 'overlap_data' in self.vertical_overlap_stats:
                for overlap in self.vertical_overlap_stats['overlap_data']:
                    # Get current and next footprint filename
                    current_filename = overlap['current_fp']['filename']
                    next_filename = overlap['next_fp']['filename']
                    overlap_pct = overlap['overlap_percent']
                    
                    # Store overlap percentage for both images
                    if current_filename not in vertical_overlaps:
                        vertical_overlaps[current_filename] = []
                    vertical_overlaps[current_filename].append(overlap_pct)
                    
                    if next_filename not in vertical_overlaps:
                        vertical_overlaps[next_filename] = []
                    vertical_overlaps[next_filename].append(overlap_pct)
            
            # Build horizontal overlap lookup if available
            if hasattr(self, 'horizontal_overlap_stats') and self.horizontal_overlap_stats and 'overlap_data' in self.horizontal_overlap_stats:
                for overlap in self.horizontal_overlap_stats['overlap_data']:
                    # Get current and next footprint filename
                    current_filename = overlap['current_fp']['filename']
                    next_filename = overlap['next_fp']['filename']
                    overlap_pct = overlap['overlap_percent']
                    
                    # Store overlap percentage for both images
                    if current_filename not in horizontal_overlaps:
                        horizontal_overlaps[current_filename] = []
                    horizontal_overlaps[current_filename].append(overlap_pct)
                    
                    if next_filename not in horizontal_overlaps:
                        horizontal_overlaps[next_filename] = []
                    horizontal_overlaps[next_filename].append(overlap_pct)
            
            # Build overall overlap count lookup if available
            if hasattr(self, 'overall_overlap_stats') and self.overall_overlap_stats and 'polygons' in self.overall_overlap_stats:
                for poly_data in self.overall_overlap_stats['polygons']:
                    filename = poly_data['footprint']['filename']
                    overlap_count = poly_data['overlap_count']
                    overall_overlap_counts[filename] = overlap_count
            
            # Process each footprint and add overlap metrics
            formatted_footprints = []
            for fp in footprints:
                # Format datetime for CSV
                datetime_str = fp.get('DateTime', 'unknown')
                if isinstance(datetime_str, datetime.datetime):
                    datetime_str = datetime_str.strftime("%Y-%m-%d %H:%M:%S")
                
                # Get filename for lookups
                filename = fp['filename']
                
                # Calculate average vertical overlap for this footprint
                vert_overlap_avg = 0.0
                if filename in vertical_overlaps and vertical_overlaps[filename]:
                    vert_overlap_avg = sum(vertical_overlaps[filename]) / len(vertical_overlaps[filename])
                
                # Calculate average horizontal overlap for this footprint
                horiz_overlap_avg = 0.0
                if filename in horizontal_overlaps and horizontal_overlaps[filename]:
                    horiz_overlap_avg = sum(horizontal_overlaps[filename]) / len(horizontal_overlaps[filename])
                
                # Get overall overlap count for this footprint
                overall_count = overall_overlap_counts.get(filename, 0)
                
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
                    'below_threshold': 'Yes',  # Always Yes, since we've already filtered
                    'vert_overlap_avg': round(vert_overlap_avg, 2),
                    'horiz_overlap_avg': round(horiz_overlap_avg, 2),
                    'overall_overlap_count': overall_count
                }
                formatted_footprints.append(formatted_fp)
            
            # Create a pandas DataFrame
            import pandas as pd
            df = pd.DataFrame(formatted_footprints)
            
            # Replace any NaN values with "N/A"
            df = df.fillna("N/A")
            
            # Print some statistics on headings
            non_zero_headings = df[df['heading'] > 0]['heading'].count()
            total_rows = len(df)
            print(f"Footprints with non-zero heading: {non_zero_headings}/{total_rows} ({non_zero_headings/total_rows*100:.1f}%)")
            
            # Export to CSV
            csv_path = os.path.join(output_path, csv_filename)
            df.to_csv(csv_path, index=False)
            result_files['csv'] = csv_path
            print(f"Footprint data exported to CSV: {csv_path}")
            
            # Export to shapefile if geopandas is available
            if GEOPANDAS_AVAILABLE:
                try:
                    # Create geometry column (Polygon objects) from vertices
                    import geopandas as gpd
                    from shapely.geometry import Point, Polygon
                    
                    geometries = []
                    for fp in footprints:
                        geometries.append(Polygon(fp['vertices']))
                    
                    # Create GeoDataFrame
                    gdf = gpd.GeoDataFrame(df, geometry=geometries)
                    
                    # Set coordinate reference system (CRS) to WGS84
                    gdf.crs = "EPSG:4326"  # WGS84 - standard GPS coordinate system
                    
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
            
        except Exception as e:
            print(f"Error exporting footprint data: {e}")
            import traceback
            print(traceback.format_exc())
            return result_files

    def identify_subsets(self, footprints: List[Dict], max_subsets=4) -> List[Dict]:
        """
        Identify meaningful subsets of the data for creating zoomed maps
        
        Args:
            footprints: List of dictionaries with footprint data
            max_subsets: Maximum number of subsets to create
            
        Returns:
            List of subset definitions containing bounds and description
        """
        if len(footprints) < 20:  # Not worth subsetting for small datasets
            return []
            
        try:
            print(f"Identifying meaningful subsets for zoomed maps...")
            
            # Extract all points for analysis
            all_lons = []
            all_lats = []
            all_alts = []
            
            for fp in footprints:
                all_lons.append(fp['longitude'])
                all_lats.append(fp['latitude'])
                all_alts.append(fp['altitude'])
                
            # Method 1: Try altitude-based clustering
            altitude_subsets = []
            
            # Sort footprints by altitude
            alt_sorted = sorted(footprints, key=lambda x: x['altitude'])
            
            # Find natural breaks in altitude (if they exist)
            alt_diffs = [alt_sorted[i+1]['altitude'] - alt_sorted[i]['altitude'] 
                        for i in range(len(alt_sorted)-1)]
            
            # Find significant gaps (more than 2x the average difference)
            avg_diff = sum(alt_diffs) / len(alt_diffs)
            gap_indices = [i for i, diff in enumerate(alt_diffs) if diff > 2 * avg_diff]
            
            # If we found natural breaks in altitude
            if gap_indices and len(gap_indices) <= max_subsets:
                # Create subsets based on altitude breaks
                start_idx = 0
                for i in gap_indices:
                    subset_fps = alt_sorted[start_idx:i+1]
                    # Get spatial bounds of this subset
                    lons = [fp['longitude'] for fp in subset_fps]
                    lats = [fp['latitude'] for fp in subset_fps]
                    
                    # Add padding to bounds (5%)
                    lon_range = max(lons) - min(lons)
                    lat_range = max(lats) - min(lats)
                    
                    altitude_subsets.append({
                        'min_lon': min(lons) - 0.05 * lon_range,
                        'max_lon': max(lons) + 0.05 * lon_range,
                        'min_lat': min(lats) - 0.05 * lat_range,
                        'max_lat': max(lats) + 0.05 * lat_range,
                        'description': f"Altitude {subset_fps[0]['altitude']:.1f}m to {subset_fps[-1]['altitude']:.1f}m",
                        'count': len(subset_fps)
                    })
                    
                    start_idx = i+1
                    
                # Add final subset if needed
                if start_idx < len(alt_sorted):
                    subset_fps = alt_sorted[start_idx:]
                    lons = [fp['longitude'] for fp in subset_fps]
                    lats = [fp['latitude'] for fp in subset_fps]
                    
                    # Add padding to bounds (5%)
                    lon_range = max(lons) - min(lons)
                    lat_range = max(lats) - min(lats)
                    
                    altitude_subsets.append({
                        'min_lon': min(lons) - 0.05 * lon_range,
                        'max_lon': max(lons) + 0.05 * lon_range,
                        'min_lat': min(lats) - 0.05 * lat_range,
                        'max_lat': max(lats) + 0.05 * lat_range,
                        'description': f"Altitude {subset_fps[0]['altitude']:.1f}m to {subset_fps[-1]['altitude']:.1f}m",
                        'count': len(subset_fps)
                    })
            
            # Method 2: Spatial clustering (DBSCAN)
            try:
                import numpy as np
                from sklearn.cluster import DBSCAN
                
                # Create points array for clustering
                points = np.array([[fp['longitude'], fp['latitude']] for fp in footprints])
                
                # Scale the coordinates to handle Earth's spherical shape
                # (approximate correction for lat/lon at the survey location)
                mean_lat = np.mean(all_lats)
                lon_scale = np.cos(np.radians(mean_lat))
                scaled_points = np.column_stack([
                    points[:, 0] * lon_scale,  # Scale longitude
                    points[:, 1]               # Latitude unchanged
                ])
                
                # Determine epsilon (max distance) based on data spread
                # Start with a reasonable default
                epsilon = 0.0001  # about 10 meters
                
                # Determine min_samples based on dataset size (higher for larger sets)
                min_samples = max(5, len(footprints) // 100)
                
                # Perform clustering
                clustering = DBSCAN(eps=epsilon, min_samples=min_samples).fit(scaled_points)
                labels = clustering.labels_
                
                # Number of clusters (ignore noise points with label -1)
                n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
                
                # If we have a reasonable number of clusters
                if 1 < n_clusters <= max_subsets:
                    spatial_subsets = []
                    
                    # For each cluster, create a subset
                    for i in range(n_clusters):
                        cluster_indices = np.where(labels == i)[0]
                        if len(cluster_indices) < 10:  # Skip very small clusters
                            continue
                            
                        cluster_fps = [footprints[idx] for idx in cluster_indices]
                        
                        # Get bounds of this cluster
                        lons = [fp['longitude'] for fp in cluster_fps]
                        lats = [fp['latitude'] for fp in cluster_fps]
                        
                        # Add padding to bounds (5%)
                        lon_range = max(lons) - min(lons)
                        lat_range = max(lats) - min(lats)
                        
                        spatial_subsets.append({
                            'min_lon': min(lons) - 0.05 * lon_range,
                            'max_lon': max(lons) + 0.05 * lon_range,
                            'min_lat': min(lats) - 0.05 * lat_range,
                            'max_lat': max(lats) + 0.05 * lat_range,
                            'description': f"Cluster {i+1}",
                            'count': len(cluster_fps)
                        })
                    
                    # If we found good spatial clusters, use those
                    if spatial_subsets:
                        return spatial_subsets
            except ImportError:
                print("scikit-learn not available, skipping spatial clustering")
            except Exception as e:
                print(f"Error during spatial clustering: {e}")
            
            # Method 3: Simple grid-based division if nothing else worked
            if not altitude_subsets:
                # Divide into quadrants
                lon_mid = (min(all_lons) + max(all_lons)) / 2
                lat_mid = (min(all_lats) + max(all_lats)) / 2
                
                # Add padding (5%)
                full_lon_range = max(all_lons) - min(all_lons)
                full_lat_range = max(all_lats) - min(all_lats)
                
                # Create 4 quadrants
                quadrants = [
                    {
                        'min_lon': min(all_lons) - 0.05 * full_lon_range,
                        'max_lon': lon_mid + 0.05 * full_lon_range,
                        'min_lat': lat_mid - 0.05 * full_lat_range, 
                        'max_lat': max(all_lats) + 0.05 * full_lat_range,
                        'description': "Northwest Quadrant",
                        'count': sum(1 for fp in footprints if fp['longitude'] <= lon_mid and fp['latitude'] >= lat_mid)
                    },
                    {
                        'min_lon': lon_mid - 0.05 * full_lon_range,
                        'max_lon': max(all_lons) + 0.05 * full_lon_range,
                        'min_lat': lat_mid - 0.05 * full_lat_range,
                        'max_lat': max(all_lats) + 0.05 * full_lat_range,
                        'description': "Northeast Quadrant",
                        'count': sum(1 for fp in footprints if fp['longitude'] > lon_mid and fp['latitude'] >= lat_mid)
                    },
                    {
                        'min_lon': min(all_lons) - 0.05 * full_lon_range,
                        'max_lon': lon_mid + 0.05 * full_lon_range,
                        'min_lat': min(all_lats) - 0.05 * full_lat_range,
                        'max_lat': lat_mid + 0.05 * full_lat_range,
                        'description': "Southwest Quadrant",
                        'count': sum(1 for fp in footprints if fp['longitude'] <= lon_mid and fp['latitude'] < lat_mid)
                    },
                    {
                        'min_lon': lon_mid - 0.05 * full_lon_range,
                        'max_lon': max(all_lons) + 0.05 * full_lon_range,
                        'min_lat': min(all_lats) - 0.05 * full_lat_range,
                        'max_lat': lat_mid + 0.05 * full_lat_range,
                        'description': "Southeast Quadrant",
                        'count': sum(1 for fp in footprints if fp['longitude'] > lon_mid and fp['latitude'] < lat_mid)
                    }
                ]
                
                # Filter out empty quadrants
                quadrants = [q for q in quadrants if q['count'] > 10]
                
                return quadrants
            
            # If altitude-based subsets were found, use those
            return altitude_subsets
                
        except Exception as e:
            print(f"Error identifying subsets: {e}")
            import traceback
            print(traceback.format_exc())
            return []

    def create_zoomed_maps(self, footprints: List[Dict], subsets: List[Dict], output_path: str) -> Dict[str, List[str]]:
        """
        Create zoomed maps for identified subsets
        
        Args:
            footprints: List of footprint dictionaries
            subsets: List of subset definitions from identify_subsets()
            output_path: Directory to save the output files
            
        Returns:
            Dictionary with paths to the created zoomed maps
        """
        print(f"Creating zoomed maps for {len(subsets)} identified regions...")
        result_files = {}
        
        try:
            # First, create zoomed footprint maps
            result_files['footprint_maps'] = []
            
            for i, subset in enumerate(subsets):
                try:
                    # Create zoomed footprint map
                    filename = f"image_footprints_map_zoom_{i+1}.png"
                    file_path = self._create_zoomed_footprint_map(footprints, subset, output_path, filename)
                    if file_path:
                        result_files['footprint_maps'].append(file_path)
                except Exception as e:
                    print(f"Error creating zoomed footprint map for subset {i+1}: {e}")
                    import traceback
                    print(traceback.format_exc())
            
            # Create zoomed vertical overlap maps
            if hasattr(self, 'vertical_overlap_stats') and self.vertical_overlap_stats:
                result_files['vertical_overlap_maps'] = []
                for i, subset in enumerate(subsets):
                    try:
                        filename = f"vertical_overlap_map_zoom_{i+1}.png"
                        file_path = self._create_zoomed_vertical_overlap_map(footprints, subset, output_path, filename)
                        if file_path:
                            result_files['vertical_overlap_maps'].append(file_path)
                    except Exception as e:
                        print(f"Error creating zoomed vertical overlap map for subset {i+1}: {e}")
                        import traceback
                        print(traceback.format_exc())
            
            # Create zoomed horizontal overlap maps
            if hasattr(self, 'horizontal_overlap_stats') and self.horizontal_overlap_stats:
                result_files['horizontal_overlap_maps'] = []
                for i, subset in enumerate(subsets):
                    try:
                        filename = f"horizontal_overlap_map_zoom_{i+1}.png"
                        file_path = self._create_zoomed_horizontal_overlap_map(footprints, subset, output_path, filename)
                        if file_path:
                            result_files['horizontal_overlap_maps'].append(file_path)
                    except Exception as e:
                        print(f"Error creating zoomed horizontal overlap map for subset {i+1}: {e}")
                        import traceback
                        print(traceback.format_exc())
            
            # Create zoomed overall overlap maps
            if hasattr(self, 'overall_overlap_stats') and self.overall_overlap_stats:
                result_files['overall_overlap_maps'] = []
                for i, subset in enumerate(subsets):
                    try:
                        filename = f"overall_overlap_map_zoom_{i+1}.png"
                        file_path = self._create_zoomed_overall_overlap_map(footprints, subset, output_path, filename)
                        if file_path:
                            result_files['overall_overlap_maps'].append(file_path)
                    except Exception as e:
                        print(f"Error creating zoomed overall overlap map for subset {i+1}: {e}")
                        import traceback
                        print(traceback.format_exc())
            
            count = sum(len(maps) for maps in result_files.values())
            print(f"Created {count} zoomed maps")
            
            return result_files
            
        except Exception as e:
            print(f"Error creating zoomed maps: {e}")
            import traceback
            print(traceback.format_exc())
            return result_files

    def _create_zoomed_footprint_map(self, footprints: List[Dict], subset: Dict, 
                                  output_path: str, filename: str) -> Optional[str]:
        """Create a zoomed footprint map for a specific subset"""
        try:
            # Use non-interactive backend to avoid threading issues
            import matplotlib
            matplotlib.use('Agg')
            
            # Create figure for plotting
            fig, ax = plt.subplots(figsize=(12, 10))
            
            # Count footprints in view
            count_in_view = 0
            
            # Plot only footprints in this subset
            for fp in footprints:
                # Check if footprint is in this subset bounds
                if (subset['min_lon'] <= fp['longitude'] <= subset['max_lon'] and
                    subset['min_lat'] <= fp['latitude'] <= subset['max_lat']):
                    
                    # Plot polygon
                    polygon = np.array(fp['vertices'])
                    ax.fill(polygon[:, 0], polygon[:, 1], alpha=0.3, edgecolor='blue', facecolor='skyblue')
                    
                    # Plot center point
                    ax.plot(fp['longitude'], fp['latitude'], 'r.', markersize=2)
                    
                    count_in_view += 1
            
            # Set bounds based on subset
            ax.set_xlim(subset['min_lon'], subset['max_lon'])
            ax.set_ylim(subset['min_lat'], subset['max_lat'])
            
            # Set labels and title
            ax.set_xlabel('Longitude (Decimal Degrees)')
            ax.set_ylabel('Latitude (Decimal Degrees)')
            ax.set_title(f'Image Footprints - {subset["description"]} ({count_in_view} images)')
            
            # Add grid
            ax.grid(True, linestyle='--', alpha=0.5)
            
            # Add subset info
            # Calculate average altitude of images in this subset
            altitudes = [fp["altitude"] for fp in footprints 
                        if subset["min_lon"] <= fp["longitude"] <= subset["max_lon"] 
                        and subset["min_lat"] <= fp["latitude"] <= subset["max_lat"]]
            avg_altitude = sum(altitudes) / len(altitudes) if altitudes else 0
            
            info_text = f'Subset: {subset["description"]}\n'
            info_text += f'Images: {count_in_view}\n'
            info_text += f'Avg Altitude: {avg_altitude:.2f}m'
            
            ax.text(0.02, 0.98, info_text, 
                    transform=ax.transAxes, fontsize=9, 
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            
            # Configure axis formatting
            ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:.6f}"))
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:.6f}"))
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            # Save file
            output_file = os.path.join(output_path, filename)
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close(fig)
            
            print(f"Created zoomed footprint map: {filename}")
            return output_file
            
        except Exception as e:
            print(f"Error creating zoomed footprint map: {e}")
            import traceback
            print(traceback.format_exc())
            return None

    def _create_zoomed_vertical_overlap_map(self, footprints: List[Dict], subset: Dict, 
                                          output_path: str, filename: str) -> Optional[str]:
        """Create a zoomed vertical overlap map for a specific subset"""
        if not hasattr(self, 'vertical_overlap_stats') or not self.vertical_overlap_stats:
            return None
            
        try:
            # Use non-interactive backend
            import matplotlib
            matplotlib.use('Agg')
            
            # Create figure for plotting
            fig, ax = plt.subplots(figsize=(12, 10))
            
            # Setup colors
            low_color = '#FF4040'      # Red
            medium_color = '#FFFF40'   # Yellow
            high_color = '#40FF40'     # Green
            
            # Count items in view
            count_in_view = 0
            overlap_count = 0
            
            # Plot footprints in this subset with low alpha
            for fp in footprints:
                # Check if footprint is in this subset bounds
                if (subset['min_lon'] <= fp['longitude'] <= subset['max_lon'] and
                    subset['min_lat'] <= fp['latitude'] <= subset['max_lat']):
                    # Plot the footprint outline
                    polygon = np.array(fp['vertices'])
                    ax.fill(polygon[:, 0], polygon[:, 1], alpha=0.05, edgecolor='gray', facecolor='whitesmoke')
                    count_in_view += 1
            
            # Plot overlap regions
            for overlap in self.vertical_overlap_stats['overlap_data']:
                # Get midpoint of overlap
                midpoint = overlap['midpoint']
                
                # Check if midpoint is in this subset
                if (subset['min_lon'] <= midpoint[0] <= subset['max_lon'] and
                    subset['min_lat'] <= midpoint[1] <= subset['max_lat']):
                    
                    # Get intersection and category
                    intersection = overlap['intersection']
                    category = overlap['category']
                    
                    # Determine color based on category
                    if category == 'low':
                        color = low_color
                    elif category == 'medium':
                        color = medium_color
                    else:
                        color = high_color
                    
                    # Plot intersection
                    if intersection.geom_type == 'Polygon':
                        x, y = intersection.exterior.xy
                        ax.fill(x, y, alpha=0.7, edgecolor='none', facecolor=color)
                        
                        # Add percentage label for significant areas
                        if intersection.area > 0.0001:
                            centroid = intersection.centroid
                            ax.text(centroid.x, centroid.y, f"{overlap['overlap_percent']:.0f}%", 
                                   fontsize=8, ha='center', va='center', color='black',
                                   bbox=dict(facecolor='white', alpha=0.7, pad=1, boxstyle='round,pad=0.2'))
                    
                    elif intersection.geom_type == 'MultiPolygon':
                        for poly in intersection.geoms:
                            x, y = poly.exterior.xy
                            ax.fill(x, y, alpha=0.7, edgecolor='none', facecolor=color)
                    
                    overlap_count += 1
            
            # Set bounds based on subset
            ax.set_xlim(subset['min_lon'], subset['max_lon'])
            ax.set_ylim(subset['min_lat'], subset['max_lat'])
            
            # Set labels and title
            ax.set_xlabel('Longitude (Decimal Degrees)')
            ax.set_ylabel('Latitude (Decimal Degrees)')
            ax.set_title(f'Vertical Overlap - {subset["description"]} ({overlap_count} overlaps)')
            
            # Add grid
            ax.grid(True, linestyle='--', alpha=0.3)
            
            # Create legend
            from matplotlib.patches import Patch
            legend_elements = [
                Patch(facecolor=low_color, edgecolor='none', alpha=0.7, label='Low (<40%)'),
                Patch(facecolor=medium_color, edgecolor='none', alpha=0.7, label='Medium (40-70%)'),
                Patch(facecolor=high_color, edgecolor='none', alpha=0.7, label='High (>70%)')
            ]
            ax.legend(handles=legend_elements, loc='upper right')
            
            # Add subset info
            info_text = f'Subset: {subset["description"]}\n'
            info_text += f'Images: {count_in_view}\n'
            info_text += f'Overlaps: {overlap_count}'
            
            ax.text(0.02, 0.98, info_text, 
                    transform=ax.transAxes, fontsize=9, 
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            
            # Configure axis formatting
            ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:.6f}"))
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:.6f}"))
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            # Save file
            output_file = os.path.join(output_path, filename)
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close(fig)
            
            print(f"Created zoomed vertical overlap map: {filename}")
            return output_file
            
        except Exception as e:
            print(f"Error creating zoomed vertical overlap map: {e}")
            import traceback
            print(traceback.format_exc())
            return None

    def _create_zoomed_horizontal_overlap_map(self, footprints: List[Dict], subset: Dict, 
                                           output_path: str, filename: str) -> Optional[str]:
        """Create a zoomed horizontal overlap map for a specific subset"""
        if not hasattr(self, 'horizontal_overlap_stats') or not self.horizontal_overlap_stats:
            return None
            
        try:
            # Use non-interactive backend
            import matplotlib
            matplotlib.use('Agg')
            
            # Create figure for plotting
            fig, ax = plt.subplots(figsize=(12, 10))
            
            # Setup colors - different color scheme to distinguish from vertical
            low_color = '#FF4040'      # Red
            medium_color = '#FFA500'   # Orange
            high_color = '#40FF40'     # Green
            
            # Count items in view
            count_in_view = 0
            overlap_count = 0
            
            # Plot footprints in this subset with low alpha
            for fp in footprints:
                # Check if footprint is in this subset bounds
                if (subset['min_lon'] <= fp['longitude'] <= subset['max_lon'] and
                    subset['min_lat'] <= fp['latitude'] <= subset['max_lat']):
                    # Plot the footprint outline
                    polygon = np.array(fp['vertices'])
                    ax.fill(polygon[:, 0], polygon[:, 1], alpha=0.05, edgecolor='gray', facecolor='whitesmoke')
                    count_in_view += 1
            
            # Plot overlap regions
            for overlap in self.horizontal_overlap_stats['overlap_data']:
                # Get midpoint of overlap
                midpoint = overlap['midpoint']
                
                # Check if midpoint is in this subset
                if (subset['min_lon'] <= midpoint[0] <= subset['max_lon'] and
                    subset['min_lat'] <= midpoint[1] <= subset['max_lat']):
                    
                    # Get intersection and category
                    intersection = overlap['intersection']
                    category = overlap['category']
                    
                    # Determine color based on category
                    if category == 'low':
                        color = low_color
                    elif category == 'medium':
                        color = medium_color
                    else:
                        color = high_color
                    
                    # Plot intersection
                    if intersection.geom_type == 'Polygon':
                        x, y = intersection.exterior.xy
                        ax.fill(x, y, alpha=0.7, edgecolor='none', facecolor=color)
                        
                        # Add percentage label for significant areas
                        if intersection.area > 0.0001:
                            centroid = intersection.centroid
                            ax.text(centroid.x, centroid.y, f"{overlap['overlap_percent']:.0f}%", 
                                   fontsize=8, ha='center', va='center', color='black',
                                   bbox=dict(facecolor='white', alpha=0.7, pad=1, boxstyle='round,pad=0.2'))
                    
                    elif intersection.geom_type == 'MultiPolygon':
                        for poly in intersection.geoms:
                            x, y = poly.exterior.xy
                            ax.fill(x, y, alpha=0.7, edgecolor='none', facecolor=color)
                    
                    overlap_count += 1
            
            # Set bounds based on subset
            ax.set_xlim(subset['min_lon'], subset['max_lon'])
            ax.set_ylim(subset['min_lat'], subset['max_lat'])
            
            # Set labels and title
            ax.set_xlabel('Longitude (Decimal Degrees)')
            ax.set_ylabel('Latitude (Decimal Degrees)')
            ax.set_title(f'Horizontal Overlap - {subset["description"]} ({overlap_count} overlaps)')
            
            # Add grid
            ax.grid(True, linestyle='--', alpha=0.3)
            
            # Create legend
            from matplotlib.patches import Patch
            legend_elements = [
                Patch(facecolor=low_color, edgecolor='none', alpha=0.7, label='Low (<10%)'),
                Patch(facecolor=medium_color, edgecolor='none', alpha=0.7, label='Medium (10-40%)'),
                Patch(facecolor=high_color, edgecolor='none', alpha=0.7, label='High (>40%)')
            ]
            ax.legend(handles=legend_elements, loc='upper right')
            
            # Add subset info
            info_text = f'Subset: {subset["description"]}\n'
            info_text += f'Images: {count_in_view}\n'
            info_text += f'Horizontal Overlaps: {overlap_count}'
            
            ax.text(0.02, 0.98, info_text, 
                    transform=ax.transAxes, fontsize=9, 
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            
            # Configure axis formatting
            ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:.6f}"))
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:.6f}"))
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            # Save file
            output_file = os.path.join(output_path, filename)
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close(fig)
            
            print(f"Created zoomed horizontal overlap map: {filename}")
            return output_file
            
        except Exception as e:
            print(f"Error creating zoomed horizontal overlap map: {e}")
            import traceback
            print(traceback.format_exc())
            return None

    def _create_zoomed_overall_overlap_map(self, footprints: List[Dict], subset: Dict, 
                                        output_path: str, filename: str) -> Optional[str]:
        """Create a zoomed overall overlap map for a specific subset"""
        if not hasattr(self, 'overall_overlap_stats') or not self.overall_overlap_stats:
            return None
            
        try:
            # Use non-interactive backend
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.colors as mcolors
            
            # Create figure for plotting
            fig, ax = plt.subplots(figsize=(12, 10))
            
            # Filter polygons in this subset
            polygons_in_view = [p for p in self.overall_overlap_stats['polygons'] 
                             if subset['min_lon'] <= p['footprint']['longitude'] <= subset['max_lon'] 
                             and subset['min_lat'] <= p['footprint']['latitude'] <= subset['max_lat']]
            
            if not polygons_in_view:
                print(f"No footprints found in subset for overall overlap map: {subset['description']}")
                plt.close(fig)
                return None
                
            # Get min/max counts for this subset only
            counts = [p['overlap_count'] for p in polygons_in_view]
            min_count = min(counts) if counts else 0
            max_count = max(counts) if counts else 0
            
            # Create rainbow colormap and normalization
            cmap = plt.cm.rainbow_r  # Purple for high, red for low
            
            # Create a normalization that handles the case where min=max
            if min_count == max_count:
                norm = mcolors.Normalize(vmin=min_count-0.5, vmax=max_count+0.5)
            else:
                norm = mcolors.Normalize(vmin=min_count, vmax=max_count)
            
            # Plot each footprint with color based on overlap count
            for poly_data in polygons_in_view:
                count = poly_data['overlap_count']
                polygon = poly_data['polygon']
                
                # Get color from colormap
                color = cmap(norm(count))
                
                # Plot polygon
                x, y = polygon.exterior.xy
                ax.fill(x, y, alpha=0.7, edgecolor='none', linewidth=0, facecolor=color)
                
                # Add count label for larger polygons
                if polygon.area > 0.0001:
                    centroid = polygon.centroid
                    ax.text(centroid.x, centroid.y, str(count), 
                           fontsize=8, ha='center', va='center', color='white',
                           bbox=dict(facecolor='black', alpha=0.5, pad=1, boxstyle='round,pad=0.2'))
            
            # Set bounds based on subset
            ax.set_xlim(subset['min_lon'], subset['max_lon'])
            ax.set_ylim(subset['min_lat'], subset['max_lat'])
            
            # Set labels and title
            ax.set_xlabel('Longitude (Decimal Degrees)')
            ax.set_ylabel('Latitude (Decimal Degrees)')
            ax.set_title(f'Overall Overlap Count - {subset["description"]} ({len(polygons_in_view)} images)')
            
            # Add grid
            ax.grid(True, linestyle='--', alpha=0.3)
            
            # Add a colorbar
            sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
            sm.set_array([])  # ScalarMappable needs an array for the colorbar
            cbar = plt.colorbar(sm, ax=ax)
            cbar.set_label('Number of Overlapping Images')
            
            # Add subset info
            avg_count = sum(counts) / len(counts) if counts else 0
            
            info_text = f'Subset: {subset["description"]}\n'
            info_text += f'Images: {len(polygons_in_view)}\n'
            info_text += f'Avg Overlaps: {avg_count:.1f}\n'
            info_text += f'Range: {min_count} to {max_count}'
            
            ax.text(0.02, 0.98, info_text, 
                    transform=ax.transAxes, fontsize=9, 
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            
            # Configure axis formatting
            ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:.6f}"))
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:.6f}"))
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            # Save file
            output_file = os.path.join(output_path, filename)
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close(fig)
            
            print(f"Created zoomed overall overlap map: {filename}")
            return output_file
            
        except Exception as e:
            print(f"Error creating zoomed overall overlap map: {e}")
            import traceback
            print(traceback.format_exc())
            return None