"""
REMUS 600 RMF Mission File Parser and Shapefile Generator
Parses RMF mission files and creates GIS-compatible shapefiles with visualization.
"""

import re
import math
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import geopandas as gpd
from shapely.geometry import Point, LineString
import pandas as pd


class CoordinateConverter:
    """Convert between coordinate formats and apply offsets."""
    
    @staticmethod
    def dms_to_dd(dms_str: str) -> Tuple[float, float]:
        """
        Convert degrees decimal minutes to decimal degrees.
        Format: "27N54.605  93W19.376" -> (27.9101, -93.3229)
        """
        parts = dms_str.strip().split()
        if len(parts) != 2:
            raise ValueError(f"Invalid coordinate format: {dms_str}")
        
        # Parse latitude
        lat_match = re.match(r'(\d+)([NS])([\d.]+)', parts[0])
        if not lat_match:
            raise ValueError(f"Invalid latitude format: {parts[0]}")
        lat_deg = float(lat_match.group(1))
        lat_min = float(lat_match.group(3))
        lat_dd = lat_deg + lat_min / 60.0
        if lat_match.group(2) == 'S':
            lat_dd = -lat_dd
        
        # Parse longitude
        lon_match = re.match(r'(\d+)([EW])([\d.]+)', parts[1])
        if not lon_match:
            raise ValueError(f"Invalid longitude format: {parts[1]}")
        lon_deg = float(lon_match.group(1))
        lon_min = float(lon_match.group(3))
        lon_dd = lon_deg + lon_min / 60.0
        if lon_match.group(2) == 'W':
            lon_dd = -lon_dd
        
        return lat_dd, lon_dd
    
    @staticmethod
    def apply_offset(lat: float, lon: float, bearing: float, 
                     distance: float, y_offset: float = 0.0) -> Tuple[float, float]:
        """
        Apply offset to coordinates.
        
        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees
            bearing: Bearing in degrees (0-360)
            distance: Distance in meters along bearing
            y_offset: Perpendicular offset in meters
            
        Returns:
            Tuple of (new_lat, new_lon)
        """
        # Earth radius in meters
        R = 6378137.0
        
        # Convert to radians
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        bearing_rad = math.radians(bearing)
        
        # Apply primary offset
        new_lat_rad = math.asin(
            math.sin(lat_rad) * math.cos(distance / R) +
            math.cos(lat_rad) * math.sin(distance / R) * math.cos(bearing_rad)
        )
        new_lon_rad = lon_rad + math.atan2(
            math.sin(bearing_rad) * math.sin(distance / R) * math.cos(lat_rad),
            math.cos(distance / R) - math.sin(lat_rad) * math.sin(new_lat_rad)
        )
        
        # Apply Y axis offset (perpendicular to bearing)
        if y_offset != 0.0:
            perp_bearing_rad = math.radians(bearing + 90)
            new_lat_rad = math.asin(
                math.sin(new_lat_rad) * math.cos(y_offset / R) +
                math.cos(new_lat_rad) * math.sin(y_offset / R) * math.cos(perp_bearing_rad)
            )
            new_lon_rad = new_lon_rad + math.atan2(
                math.sin(perp_bearing_rad) * math.sin(y_offset / R) * math.cos(lat_rad),
                math.cos(y_offset / R) - math.sin(lat_rad) * math.sin(new_lat_rad)
            )
        
        return math.degrees(new_lat_rad), math.degrees(new_lon_rad)
    
    @staticmethod
    def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate bearing between two points in degrees."""
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlon_rad = math.radians(lon2 - lon1)
        
        y = math.sin(dlon_rad) * math.cos(lat2_rad)
        x = math.cos(lat1_rad) * math.sin(lat2_rad) - \
            math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon_rad)
        
        bearing = math.degrees(math.atan2(y, x))
        return (bearing + 360) % 360


class RMFParser:
    """Parse REMUS 600 RMF mission files."""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.objectives = []
        self.current_position = None
        
    def parse(self) -> List[Dict]:
        """Parse the RMF file and return list of objectives."""
        with open(self.filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Split into objectives
        objective_blocks = re.split(r'\[Objective\]', content)[1:]
        
        for block in objective_blocks:
            obj = self._parse_objective(block)
            if obj:
                self.objectives.append(obj)
        
        return self.objectives
    
    def _clean_line(self, line: str) -> str:
        """Remove comments from line."""
        return re.sub(r'#.*$', '', line).strip()
    
    def _parse_objective(self, block: str) -> Optional[Dict]:
        """Parse a single objective block."""
        lines = [self._clean_line(line) for line in block.split('\n') if line.strip()]
        
        obj = {
            'type': None,
            'destination': None,
            'offset_direction': 0.0,
            'offset_distance': 0.0,
            'offset_y': 0.0,
            'num_rows': 1,
            'first_turn_left': False,
            'line_spacings': [],
        }
        
        for line in lines:
            if not line:
                continue
            
            if line.startswith('Type='):
                obj['type'] = line.split('=', 1)[1].strip()
            elif line.startswith('Destination='):
                obj['destination'] = line.split('=', 1)[1].strip()
            elif line.startswith('Offset direction='):
                obj['offset_direction'] = float(line.split('=', 1)[1].strip())
            elif line.startswith('Offset distance (Meters)='):
                obj['offset_distance'] = float(line.split('=', 1)[1].strip())
            elif line.startswith('Offset Y axis (Meters)='):
                obj['offset_y'] = float(line.split('=', 1)[1].strip())
            elif line.startswith('Number of rows='):
                obj['num_rows'] = int(line.split('=', 1)[1].strip())
            elif line.startswith('First turn to the left='):
                value = line.split('=', 1)[1].strip().upper()
                obj['first_turn_left'] = value in ['YES', 'Y', 'TRUE', '1']
            elif line.startswith('Line spacings (meters)='):
                spacings_str = line.split('=', 1)[1].strip()
                obj['line_spacings'] = [float(s.strip()) for s in spacings_str.split(',')]
            elif line.startswith('Symbol Position on Chart='):
                # Some objectives use this instead of Destination
                if not obj['destination']:
                    obj['destination'] = line.split('=', 1)[1].strip()
        
        return obj if obj['type'] else None
    
    def generate_geometries(self) -> List[Dict]:
        """Generate geometries from parsed objectives."""
        geometries = []
        
        for i, obj in enumerate(self.objectives):
            obj_type = obj['type']
            
            if obj_type in ['Set Position', 'Wait Run', 'Surface', 'Get gps fix']:
                # Single point objectives
                geom = self._generate_point(obj)
                if geom:
                    geometries.append({
                        'objective_num': i + 1,
                        'type': obj_type,
                        'geometry': geom,
                        'description': obj_type
                    })
                    
            elif obj_type == 'Navigate':
                # Line from current position to destination
                geom = self._generate_navigate_line(obj)
                if geom:
                    geometries.append({
                        'objective_num': i + 1,
                        'type': obj_type,
                        'geometry': geom,
                        'description': f"Navigate to destination"
                    })
                    
            elif obj_type == 'Navigate rows':
                # Generate lawnmower pattern
                geoms = self._generate_navigate_rows(obj, i + 1)
                geometries.extend(geoms)
        
        return geometries
    
    def _generate_point(self, obj: Dict) -> Optional[Point]:
        """Generate a point geometry."""
        if not obj['destination']:
            return None
        
        try:
            lat, lon = CoordinateConverter.dms_to_dd(obj['destination'])
            
            # Apply offsets
            if obj['offset_distance'] != 0.0 or obj['offset_y'] != 0.0:
                lat, lon = CoordinateConverter.apply_offset(
                    lat, lon,
                    obj['offset_direction'],
                    obj['offset_distance'],
                    obj['offset_y']
                )
            
            self.current_position = (lat, lon)
            return Point(lon, lat)
        except Exception as e:
            print(f"Error parsing point: {e}")
            return None
    
    def _generate_navigate_line(self, obj: Dict) -> Optional[LineString]:
        """Generate a line from current position to destination."""
        if not self.current_position or not obj['destination']:
            # If no current position, just set position
            point = self._generate_point(obj)
            return None
        
        try:
            lat, lon = CoordinateConverter.dms_to_dd(obj['destination'])
            
            # Apply offsets
            if obj['offset_distance'] != 0.0 or obj['offset_y'] != 0.0:
                lat, lon = CoordinateConverter.apply_offset(
                    lat, lon,
                    obj['offset_direction'],
                    obj['offset_distance'],
                    obj['offset_y']
                )
            
            # Create line
            line = LineString([
                (self.current_position[1], self.current_position[0]),
                (lon, lat)
            ])
            
            self.current_position = (lat, lon)
            return line
        except Exception as e:
            print(f"Error generating navigate line: {e}")
            return None
    
    def _generate_navigate_rows(self, obj: Dict, obj_num: int) -> List[Dict]:
        """Generate lawnmower pattern for Navigate rows."""
        geometries = []
        
        if not obj['destination']:
            return geometries
        
        try:
            # Get destination
            dest_lat, dest_lon = CoordinateConverter.dms_to_dd(obj['destination'])
            
            # Apply offsets to destination
            if obj['offset_distance'] != 0.0 or obj['offset_y'] != 0.0:
                dest_lat, dest_lon = CoordinateConverter.apply_offset(
                    dest_lat, dest_lon,
                    obj['offset_direction'],
                    obj['offset_distance'],
                    obj['offset_y']
                )
            
            # First leg: current position to destination
            if self.current_position:
                line = LineString([
                    (self.current_position[1], self.current_position[0]),
                    (dest_lon, dest_lat)
                ])
                geometries.append({
                    'objective_num': obj_num,
                    'type': 'Navigate rows',
                    'geometry': line,
                    'description': f"Row 1 of {obj['num_rows']}"
                })
                
                # Calculate bearing of first leg
                bearing = CoordinateConverter.calculate_bearing(
                    self.current_position[0], self.current_position[1],
                    dest_lat, dest_lon
                )
            else:
                # No current position, start from destination
                self.current_position = (dest_lat, dest_lon)
                bearing = obj['offset_direction']
            
            # Track the last endpoint for connecting rows
            last_end_point = (dest_lon, dest_lat)
            
            # Generate additional rows
            current_start = self.current_position
            current_end = (dest_lat, dest_lon)
            turn_left = obj['first_turn_left']
            
            for row in range(1, obj['num_rows']):
                # Determine spacing for this row
                if obj['line_spacings']:
                    spacing_idx = (row - 1) % len(obj['line_spacings'])
                    spacing = obj['line_spacings'][spacing_idx]
                else:
                    spacing = 100  # Default spacing
                
                # Calculate perpendicular offset
                # Turn left = subtract 90 degrees, Turn right = add 90 degrees
                perp_bearing = (bearing - 90) if turn_left else (bearing + 90)
                
                # Calculate new start and end positions
                new_start_lat, new_start_lon = CoordinateConverter.apply_offset(
                    current_start[0], current_start[1],
                    perp_bearing % 360, spacing
                )
                new_end_lat, new_end_lon = CoordinateConverter.apply_offset(
                    current_end[0], current_end[1],
                    perp_bearing % 360, spacing
                )
                
                # Create connecting turn line from last endpoint to start of new row
                if row % 2 == 1:
                    # Previous row ended at current_end, next row starts at new_end (going backwards)
                    turn_line = LineString([
                        last_end_point,
                        (new_end_lon, new_end_lat)
                    ])
                    geometries.append({
                        'objective_num': obj_num,
                        'type': 'Navigate rows',
                        'geometry': turn_line,
                        'description': f"Turn to Row {row + 1}"
                    })
                    
                    # Return leg: end to start
                    line = LineString([
                        (new_end_lon, new_end_lat),
                        (new_start_lon, new_start_lat)
                    ])
                    last_end_point = (new_start_lon, new_start_lat)
                else:
                    # Previous row ended at current_start, next row starts at new_start
                    turn_line = LineString([
                        last_end_point,
                        (new_start_lon, new_start_lat)
                    ])
                    geometries.append({
                        'objective_num': obj_num,
                        'type': 'Navigate rows',
                        'geometry': turn_line,
                        'description': f"Turn to Row {row + 1}"
                    })
                    
                    # Forward leg: start to end
                    line = LineString([
                        (new_start_lon, new_start_lat),
                        (new_end_lon, new_end_lat)
                    ])
                    last_end_point = (new_end_lon, new_end_lat)
                
                geometries.append({
                    'objective_num': obj_num,
                    'type': 'Navigate rows',
                    'geometry': line,
                    'description': f"Row {row + 1} of {obj['num_rows']}"
                })
                
                current_start = (new_start_lat, new_start_lon)
                current_end = (new_end_lat, new_end_lon)
            
            # Update current position to end of last row
            if obj['num_rows'] % 2 == 1:
                self.current_position = current_end
            else:
                self.current_position = current_start
                
        except Exception as e:
            print(f"Error generating navigate rows: {e}")
        
        return geometries


class RMFVisualizerGUI:
    """GUI for RMF file visualization and shapefile export."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("REMUS 600 RMF Parser & Shapefile Generator")
        self.root.geometry("1200x800")
        
        self.rmf_file = None
        self.geometries = []
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create GUI widgets."""
        # Top frame for controls
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.pack(side=tk.TOP, fill=tk.X)
        
        # File selection
        ttk.Label(control_frame, text="RMF File:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.file_entry = ttk.Entry(control_frame, width=60)
        self.file_entry.grid(row=0, column=1, padx=5)
        ttk.Button(control_frame, text="Browse", command=self._browse_file).grid(row=0, column=2, padx=5)
        ttk.Button(control_frame, text="Load & Plot", command=self._load_and_plot).grid(row=0, column=3, padx=5)
        
        # Export controls
        ttk.Label(control_frame, text="Output Directory:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.output_entry = ttk.Entry(control_frame, width=60)
        self.output_entry.grid(row=1, column=1, padx=5)
        ttk.Button(control_frame, text="Browse", command=self._browse_output).grid(row=1, column=2, padx=5)
        ttk.Button(control_frame, text="Export Shapefile", command=self._export_shapefile).grid(row=1, column=3, padx=5)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(control_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=2, column=0, columnspan=4, sticky=tk.EW, pady=5)
        
        # Plotting frame
        plot_frame = ttk.Frame(self.root)
        plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create matplotlib figure
        self.fig = Figure(figsize=(12, 8))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Initial plot
        self.ax.set_title("Load an RMF file to view mission plan")
        self.ax.set_xlabel("Longitude")
        self.ax.set_ylabel("Latitude")
        self.ax.grid(True, alpha=0.3)
        self.canvas.draw()
    
    def _browse_file(self):
        """Browse for RMF file."""
        filename = filedialog.askopenfilename(
            title="Select RMF File",
            filetypes=[("RMF files", "*.rmf"), ("All files", "*.*")]
        )
        if filename:
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, filename)
    
    def _browse_output(self):
        """Browse for output directory."""
        directory = filedialog.askdirectory(title="Select Output Directory")
        if directory:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, directory)
    
    def _load_and_plot(self):
        """Load RMF file and plot mission."""
        rmf_file = self.file_entry.get()
        if not rmf_file:
            messagebox.showerror("Error", "Please select an RMF file")
            return
        
        if not Path(rmf_file).exists():
            messagebox.showerror("Error", "File does not exist")
            return
        
        try:
            self.status_var.set("Parsing RMF file...")
            self.root.update()
            
            # Parse file
            parser = RMFParser(rmf_file)
            parser.parse()
            self.geometries = parser.generate_geometries()
            
            if not self.geometries:
                messagebox.showwarning("Warning", "No geometries found in RMF file")
                return
            
            # Plot
            self._plot_mission()
            self.status_var.set(f"Loaded {len(self.geometries)} features from {Path(rmf_file).name}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to parse RMF file:\n{str(e)}")
            self.status_var.set("Error")
    
    def _plot_mission(self):
        """Plot the mission plan."""
        self.ax.clear()
        
        # Plot different objective types in different colors
        colors = {
            'Set Position': 'green',
            'Wait Run': 'yellow',
            'Navigate': 'blue',
            'Navigate rows': 'red',
            'Surface': 'cyan',
            'Get gps fix': 'magenta'
        }
        
        # Separate points and lines
        points = []
        lines = []
        
        for geom_data in self.geometries:
            geom = geom_data['geometry']
            obj_type = geom_data['type']
            color = colors.get(obj_type, 'gray')
            
            if isinstance(geom, Point):
                points.append((geom.x, geom.y, color, obj_type))
            elif isinstance(geom, LineString):
                coords = list(geom.coords)
                lons = [c[0] for c in coords]
                lats = [c[1] for c in coords]
                lines.append((lons, lats, color, obj_type))
        
        # Plot lines
        plotted_types = set()
        for lons, lats, color, obj_type in lines:
            label = obj_type if obj_type not in plotted_types else None
            self.ax.plot(lons, lats, color=color, linewidth=2, label=label, alpha=0.7)
            plotted_types.add(obj_type)
        
        # Plot points
        for lon, lat, color, obj_type in points:
            label = obj_type if obj_type not in plotted_types else None
            self.ax.plot(lon, lat, 'o', color=color, markersize=8, label=label)
            plotted_types.add(obj_type)
        
        # Add objective numbers at the start of each objective
        objective_positions = {}
        for geom_data in self.geometries:
            geom = geom_data['geometry']
            obj_num = geom_data['objective_num']
            
            # Only label each objective once at its starting point
            if obj_num not in objective_positions:
                if isinstance(geom, Point):
                    objective_positions[obj_num] = (geom.x, geom.y)
                elif isinstance(geom, LineString):
                    coords = list(geom.coords)
                    if coords:
                        objective_positions[obj_num] = coords[0]
        
        # Draw objective numbers
        for obj_num, (lon, lat) in objective_positions.items():
            self.ax.annotate(str(obj_num), 
                           xy=(lon, lat), 
                           xytext=(5, 5), 
                           textcoords='offset points',
                           fontsize=9, 
                           fontweight='bold',
                           color='black',
                           bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='black', alpha=0.7))
        
        # Add legend entry for objective numbers
        self.ax.plot([], [], ' ', label='Numbers = Objectives')
        
        self.ax.set_xlabel("Longitude (degrees)")
        self.ax.set_ylabel("Latitude (degrees)")
        self.ax.set_title(f"Mission Plan - {len(self.geometries)} Features")
        self.ax.grid(True, alpha=0.3)
        self.ax.legend(loc='best')
        self.ax.set_aspect('equal', adjustable='datalim')
        
        self.canvas.draw()
    
    def _export_shapefile(self):
        """Export geometries to shapefile."""
        if not self.geometries:
            messagebox.showerror("Error", "No data to export. Load an RMF file first.")
            return
        
        output_dir = self.output_entry.get()
        if not output_dir:
            messagebox.showerror("Error", "Please select an output directory")
            return
        
        if not Path(output_dir).exists():
            messagebox.showerror("Error", "Output directory does not exist")
            return
        
        try:
            # Get base filename
            rmf_file = self.file_entry.get()
            base_name = Path(rmf_file).stem
            
            # Create line-only geometries for shapefile
            line_geometries = []
            all_points = []
            
            # Collect all coordinates in sequence
            for geom_data in self.geometries:
                geom = geom_data['geometry']
                if isinstance(geom, Point):
                    # Add point to sequence
                    all_points.append((geom.x, geom.y))
                elif isinstance(geom, LineString):
                    # Add line to output and collect its points
                    line_geometries.append(geom_data)
                    coords = list(geom.coords)
                    all_points.extend(coords)
            
            # Create a continuous path connecting all waypoints
            if all_points:
                continuous_path = LineString(all_points)
                line_geometries.append({
                    'objective_num': 0,
                    'type': 'Mission Path',
                    'geometry': continuous_path,
                    'description': 'Complete mission path'
                })
            
            # Create GeoDataFrame with only line geometries
            gdf = gpd.GeoDataFrame(line_geometries, crs="EPSG:4326")
            
            # Export
            output_path = Path(output_dir) / f"{base_name}_RMF.shp"
            gdf.to_file(output_path)
            
            messagebox.showinfo("Success", f"Shapefile exported to:\n{output_path}")
            self.status_var.set(f"Exported to {output_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export shapefile:\n{str(e)}")
            self.status_var.set("Export failed")


def main():
    """Main entry point."""
    root = tk.Tk()
    app = RMFVisualizerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
