#!/usr/bin/env python3
"""
Zambonify Mission NemoSens

This script converts an AUV JSON mission from a lawnmower pattern to a zamboni pattern.
The zamboni pattern reduces sharp turns by reordering lines to create multiple smaller boxes
within the survey area, making the AUV navigation more efficient.

Author: Mike Bollinger
Date: July 27, 2025

USAGE:
    Run the script to launch the Tkinter GUI:
        python Zambonify_Mission_NemoSens.py
    Load a lawnmower-pattern mission JSON, review the optional plot preview,
    and export the converted zamboni-pattern mission JSON.

INPUTS:
    - A NemoSens/AUV mission JSON file containing one or more rail family
      lawnmower survey patterns (selected via the GUI file dialog).

OUTPUTS:
    A new mission JSON file with survey lines reordered into a zamboni
    pattern, saved to a user-chosen location, plus an optional matplotlib
    preview plot (when matplotlib is available).
"""

import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox
try:
    import matplotlib.pyplot as plt
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not available. Visualization will be disabled.")
import math
from typing import List, Dict, Tuple, Any


class ZamboniConverter:
    """Class to handle conversion from lawnmower to zamboni pattern."""
    
    def __init__(self):
        self.mission_data = None
        self.rail_families = []  # Support multiple rail families
        self.all_original_stages = []
        self.all_zamboni_stages = []
        
    def load_mission(self, file_path: str) -> bool:
        """Load the JSON mission file."""
        try:
            with open(file_path, 'r') as f:
                self.mission_data = json.load(f)
            
            # Find all rail family paths
            self.rail_families = self._find_all_rail_families()
            if not self.rail_families:
                messagebox.showerror("Error", "No rail families found in mission file!")
                return False
                
            # Collect all original stages from all rail families
            self.all_original_stages = []
            total_stages = 0
            for i, rail_family in enumerate(self.rail_families):
                stages = rail_family['stages'].copy()
                self.all_original_stages.extend(stages)
                total_stages += len(stages)
                print(f"Rail Family {i+1} ({rail_family['name']}): {len(stages)} stages")
            
            print(f"Loaded mission with {len(self.rail_families)} rail families, {total_stages} total rail stages")
            return True
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load mission file: {str(e)}")
            return False
    
    def _find_all_rail_families(self) -> List[Dict[str, Any]]:
        """Find all rail family paths in the mission data."""
        try:
            rail_families = []
            nemosens_device = None
            for device in self.mission_data['mission']['devices']:
                if device.get('type') == 'DEVICE_DRONE':
                    nemosens_device = device
                    break
            
            if not nemosens_device:
                return []
                
            for path in nemosens_device.get('paths', []):
                if path.get('type') == 'PATH_RAIL':
                    rail_families.append(path)
                    
            return rail_families
        except Exception:
            return []
    
    def calculate_heading(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate bearing between two points in degrees (0-360)."""
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlon_rad = math.radians(lon2 - lon1)
        
        # Calculate bearing
        y = math.sin(dlon_rad) * math.cos(lat2_rad)
        x = (math.cos(lat1_rad) * math.sin(lat2_rad) - 
             math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon_rad))
        
        bearing_rad = math.atan2(y, x)
        bearing_deg = math.degrees(bearing_rad)
        
        # Normalize to 0-360
        return (bearing_deg + 360) % 360
    
    def group_stages_into_lines(self, stages: List[Dict]) -> List[List[Dict]]:
        """Group stages into lines (pairs of A and B points)."""
        lines = []
        i = 0
        
        while i < len(stages) - 1:
            stage_a = stages[i]
            stage_b = stages[i + 1]
            
            # Check if they form a line pair (same number, different A/B)
            name_a = stage_a['name']
            name_b = stage_b['name']
            
            if (name_a.endswith(' A') and name_b.endswith(' B') and 
                name_a[:-2] == name_b[:-2]):
                lines.append([stage_a, stage_b])
                i += 2
            else:
                # Single waypoint or unpaired
                lines.append([stage_a])
                i += 1
                
        # Handle last stage if unpaired
        if i < len(stages):
            lines.append([stages[i]])
            
        return lines
    
    def convert_to_zamboni(self) -> bool:
        """Convert lawnmower pattern to zamboni pattern for all rail families."""
        try:
            self.all_zamboni_stages = []
            
            for i, rail_family in enumerate(self.rail_families):
                print(f"\n{'='*60}")
                print(f"PROCESSING RAIL FAMILY {i+1}: {rail_family['name']}")
                print(f"{'='*60}")
                
                original_stages = rail_family['stages'].copy()
                lines = self.group_stages_into_lines(original_stages)
                print(f"Found {len(lines)} lines in {rail_family['name']}")
                
                # Create zamboni pattern for this rail family
                zamboni_lines = self._create_zamboni_pattern(lines, rail_family['name'])
                
                # Flatten back to stages
                zamboni_stages = []
                for line in zamboni_lines:
                    zamboni_stages.extend(line)
                
                # Update the rail family in mission data
                rail_family['stages'] = zamboni_stages
                
                # Keep track of all zamboni stages for visualization
                self.all_zamboni_stages.extend(zamboni_stages)
                
                print(f"Converted {rail_family['name']}: {len(original_stages)} → {len(zamboni_stages)} stages")
            
            print(f"\nCompleted zamboni conversion for {len(self.rail_families)} rail families")
            print(f"Total zamboni stages: {len(self.all_zamboni_stages)}")
            return True
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to convert to zamboni pattern: {str(e)}")
            return False
    
    def _create_zamboni_pattern(self, lines: List[List[Dict]], rail_family_name: str = "") -> List[List[Dict]]:
        """
        Create zamboni pattern using the corrected algorithm with support for odd-numbered line counts:
        
        1. If odd number of lines, exclude the last line from zamboni processing
        2. Divide remaining lines into halves (1-N first half, N+1-2N second half)
        3. First half: odd lines normal (A→B), even lines reversed (B→A)  
        4. Second half: even lines normal (A→B), odd lines reversed (B→A)
        5. Interleave: pos1 first half, pos1 second half, pos2 first half, pos2 second half, etc.
        6. If there was an excluded line, append it at the end unchanged
        
        This ensures all first half lines go one way and all second half lines go the other way.
        """
        if len(lines) < 2:
            print(f"Not enough lines ({len(lines)}) for zamboni pattern, returning as-is")
            return lines
            
        total_lines = len(lines)
        excluded_line = None
        
        # Handle odd number of lines - exclude the last line
        if total_lines % 2 == 1:
            excluded_line = lines[-1].copy()
            lines = lines[:-1]  # Remove last line from processing
            total_lines = len(lines)
            excluded_line_name = excluded_line[0]['name'][:-2] if len(excluded_line) == 2 and excluded_line[0]['name'].endswith(' A') else excluded_line[0]['name']
            print(f"Odd number of lines detected. Excluding last line ({excluded_line_name}) from zamboni processing.")
        
        half_lines = total_lines // 2
        
        print(f"\n=== ZAMBONI PATTERN CREATION - {rail_family_name} ===")
        print(f"Total lines for processing: {total_lines}")
        print(f"Half lines: {half_lines}")
        if excluded_line:
            print(f"Excluded line: {excluded_line_name} (will be appended unchanged)")
        print(f"Algorithm: First half odd=normal/even=reversed, Second half even=normal/odd=reversed")
        print()
        
        # Step 1: Apply direction rules to each half
        first_half_lines = []
        second_half_lines = []
        
        # Process first half (lines 1 to half_lines)
        print("=== FIRST HALF DIRECTION PROCESSING ===")
        for i in range(half_lines):
            line = lines[i].copy()
            line_num = i + 1  # 1-indexed line number
            line_name = line[0]['name'][:-2] if len(line) == 2 and line[0]['name'].endswith(' A') else line[0]['name']
            
            # First half: odd lines normal (A→B), even lines reversed (B→A)
            if line_num % 2 == 1:  # Odd line numbers (1, 3, 5, 7, 9...)
                direction = "NORMAL (A→B)"
                # Keep line as-is for normal direction
            else:  # Even line numbers (2, 4, 6, 8, 10...)
                direction = "REVERSED (B→A)"
                # Reverse the line for reversed direction
                if len(line) == 2:
                    line = [line[1], line[0]]
            
            print(f"First half line {line_num:2d} ({line_name}): {direction}")
            first_half_lines.append(line)
        
        # Process second half (lines half_lines+1 to total_lines)  
        print("\n=== SECOND HALF DIRECTION PROCESSING ===")
        for i in range(half_lines, total_lines):
            line = lines[i].copy()
            line_num = i + 1  # 1-indexed line number
            line_name = line[0]['name'][:-2] if len(line) == 2 and line[0]['name'].endswith(' A') else line[0]['name']
            
            # Second half: even lines normal (A→B), odd lines reversed (B→A)
            if line_num % 2 == 0:  # Even line numbers (12, 14, 16, 18, 20...)
                direction = "NORMAL (A→B)"
                # Keep line as-is for normal direction
            else:  # Odd line numbers (11, 13, 15, 17, 19...)
                direction = "REVERSED (B→A)"
                # Reverse the line for reversed direction
                if len(line) == 2:
                    line = [line[1], line[0]]
            
            print(f"Second half line {line_num:2d} ({line_name}): {direction}")
            second_half_lines.append(line)
        
        # Step 2: Interleave the halves
        print("\n=== INTERLEAVING HALVES ===")
        zamboni_lines = []
        
        for i in range(half_lines):
            zamboni_pos = len(zamboni_lines) + 1
            
            # Add first half line
            first_line = first_half_lines[i]
            first_line_num = i + 1
            first_line_name = first_line[0]['name'][:-2] if len(first_line) == 2 and first_line[0]['name'].endswith(' A') else first_line[0]['name']
            print(f"Zamboni pos {zamboni_pos:2d}: First half line {first_line_num:2d} ({first_line_name})")
            zamboni_lines.append(first_line)
            
            # Add corresponding second half line
            if i < len(second_half_lines):
                zamboni_pos = len(zamboni_lines) + 1
                second_line = second_half_lines[i]
                second_line_num = half_lines + i + 1
                second_line_name = second_line[0]['name'][:-2] if len(second_line) == 2 and second_line[0]['name'].endswith(' A') else second_line[0]['name']
                print(f"Zamboni pos {zamboni_pos:2d}: Second half line {second_line_num:2d} ({second_line_name})")
                zamboni_lines.append(second_line)
        
        # Step 3: Handle excluded line (if any)
        if excluded_line:
            zamboni_pos = len(zamboni_lines) + 1
            print(f"\n=== APPENDING EXCLUDED LINE ===")
            print(f"Zamboni pos {zamboni_pos:2d}: Excluded line ({excluded_line_name}) - UNCHANGED")
            zamboni_lines.append(excluded_line)
        
        print(f"\nCreated zamboni pattern with {len(zamboni_lines)} lines")
        print(f"=== END ZAMBONI PATTERN CREATION - {rail_family_name} ===\n")
        
        return zamboni_lines
    
    def save_mission(self, input_file_path: str) -> bool:
        """Save the modified mission to a new JSON file."""
        try:
            # Create output filename based on input filename
            input_dir = os.path.dirname(input_file_path)
            input_name = os.path.splitext(os.path.basename(input_file_path))[0]
            
            print(f"Input file path: {input_file_path}")
            print(f"Input directory: {input_dir}")
            print(f"Input filename (no ext): {input_name}")
            
            if not input_name.endswith('_Zamboni'):
                output_name = f"{input_name}_Zamboni"
            else:
                output_name = input_name
            
            output_file = os.path.join(input_dir, f"{output_name}.json")
            
            print(f"Output filename: {output_name}")
            print(f"Output file path: {output_file}")
            
            # Update mission name and comment
            self.mission_data['mission']['name'] = output_name
            self.mission_data['mission']['comment'] = f"Zamboni pattern - {self.mission_data['mission']['comment']}"
            
            with open(output_file, 'w') as f:
                json.dump(self.mission_data, f, indent=2)
            
            print(f"Saved zamboni mission to: {output_file}")
            return True
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save mission file: {str(e)}")
            return False
    
    def create_visualization(self, output_dir: str, input_file_path: str = "") -> bool:
        """Create a visualization map showing the zamboni pattern with directional indicators."""
        if not MATPLOTLIB_AVAILABLE:
            print("Matplotlib not available. Skipping visualization.")
            return True
            
        try:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
            
            # Get all waypoints from the mission for context
            all_waypoints = self._get_all_mission_waypoints()
            
            # Plot original pattern
            self._plot_pattern(ax1, self.all_original_stages, "Original Lawnmower Pattern", all_waypoints)
            
            # Plot zamboni pattern
            self._plot_pattern(ax2, self.all_zamboni_stages, "Zamboni Pattern", all_waypoints)
            
            plt.tight_layout()
            
            # Create output filename based on input filename
            if input_file_path:
                input_name = os.path.splitext(os.path.basename(input_file_path))[0]
                map_filename = f"{input_name}_Zamboni_Results.png"
            else:
                map_filename = "zamboni_pattern_comparison.png"
            
            map_file = os.path.join(output_dir, map_filename)
            plt.savefig(map_file, dpi=300, bbox_inches='tight')
            plt.show()
            
            print(f"Saved visualization to: {map_file}")
            return True
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create visualization: {str(e)}")
            return False
    
    def _plot_pattern(self, ax, stages: List[Dict], title: str, all_waypoints: List[Dict] = None):
        """Plot a single pattern on the given axes."""
        # Extract coordinates from rail family stages
        lats = [stage['latitude'] for stage in stages]
        lons = [stage['longitude'] for stage in stages]
        
        # Plot all waypoints as small grey dots for context
        if all_waypoints:
            all_lats = [wp['latitude'] for wp in all_waypoints]
            all_lons = [wp['longitude'] for wp in all_waypoints]
            ax.scatter(all_lons, all_lats, c='lightgrey', s=8, zorder=1, alpha=0.5, label='Other waypoints')
            
            # Plot mission path connecting all waypoints in order with dashed lines
            if len(all_waypoints) > 1:
                mission_lats = [wp['latitude'] for wp in all_waypoints]
                mission_lons = [wp['longitude'] for wp in all_waypoints]
                ax.plot(mission_lons, mission_lats, color='darkgrey', linewidth=1.5, 
                       alpha=0.7, linestyle='--', zorder=1, label='Mission path')
        
        # Plot rail family waypoints as larger black dots
        ax.scatter(lons, lats, c='black', s=15, zorder=5, alpha=0.7, label='Rail waypoints')
        
        # Plot rail lines with directional colors
        for i in range(0, len(stages) - 1, 2):
            if i + 1 < len(stages):
                stage_a = stages[i]
                stage_b = stages[i + 1]
                
                lat1, lon1 = stage_a['latitude'], stage_a['longitude']
                lat2, lon2 = stage_b['latitude'], stage_b['longitude']
                
                # Calculate heading
                heading = self.calculate_heading(lat1, lon1, lat2, lon2)
                
                # Color based on heading: 0-180 = blue (East), 180-360 = red (West)
                color = 'blue' if heading <= 180 else 'red'
                
                # Plot colored line based on heading
                ax.plot([lon1, lon2], [lat1, lat2], color=color, linewidth=2, alpha=0.8, zorder=4)
        
        # Connect consecutive rail lines with dashed lines (mission path within rail families)
        for i in range(1, len(stages) - 1, 2):
            if i + 1 < len(stages):
                lat1, lon1 = stages[i]['latitude'], stages[i]['longitude']
                lat2, lon2 = stages[i + 1]['latitude'], stages[i + 1]['longitude']
                ax.plot([lon1, lon2], [lat1, lat2], 'darkgrey', linewidth=1.5, 
                       alpha=0.7, linestyle='--', zorder=3)
        
        # Set axis limits based on rail family stages only (not all waypoints)
        if lats and lons:
            lat_margin = (max(lats) - min(lats)) * 0.05
            lon_margin = (max(lons) - min(lons)) * 0.05
            ax.set_xlim(min(lons) - lon_margin, max(lons) + lon_margin)
            ax.set_ylim(min(lats) - lat_margin, max(lats) + lat_margin)
        
        # Add waypoint labels for key rail points only
        for i, stage in enumerate(stages):
            if i % 8 == 0:  # Only label every 8th point to reduce clutter
                ax.annotate(stage['name'], 
                           (stage['longitude'], stage['latitude']),
                           xytext=(3, 3), textcoords='offset points',
                           fontsize=7, alpha=0.7, zorder=6)
        
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')
        
        # Add legend
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], color='blue', lw=2, label='Heading 0-180° (East)'),
            Line2D([0], [0], color='red', lw=2, label='Heading 180-360° (West)'),
            Line2D([0], [0], color='darkgrey', lw=1.5, linestyle='--', label='Mission path'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='black', markersize=4, label='Rail waypoints'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='lightgrey', markersize=3, label='Other waypoints')
        ]
        ax.legend(handles=legend_elements, loc='upper right', fontsize=7)
    
    def _get_all_mission_waypoints(self) -> List[Dict]:
        """Extract all waypoints from the entire mission for context plotting."""
        all_waypoints = []
        
        try:
            # Find the NemoSens device
            nemosens_device = None
            for device in self.mission_data['mission']['devices']:
                if device.get('type') == 'DEVICE_DRONE':
                    nemosens_device = device
                    break
            
            if nemosens_device and 'paths' in nemosens_device:
                for path in nemosens_device['paths']:
                    if 'stages' in path:
                        for stage in path['stages']:
                            if 'latitude' in stage and 'longitude' in stage:
                                all_waypoints.append({
                                    'name': stage['name'],
                                    'latitude': stage['latitude'],
                                    'longitude': stage['longitude'],
                                    'path_name': path.get('name', 'Unknown'),
                                    'is_rail': path.get('type') == 'PATH_RAIL'
                                })
            
        except Exception as e:
            print(f"Warning: Could not extract all waypoints: {e}")
        
        return all_waypoints

def select_input_file() -> str:
    """Open file dialog to select input JSON mission file."""
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    file_path = filedialog.askopenfilename(
        title="Select Input Mission JSON File",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        initialdir=os.getcwd()
    )
    
    root.destroy()
    return file_path


def select_output_directory() -> str:
    """Open dialog to select output directory."""
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    dir_path = filedialog.askdirectory(
        title="Select Output Directory",
        initialdir=os.getcwd()
    )
    
    root.destroy()
    return dir_path


def main():
    """Main function to run the Zamboni converter."""
    print("=== AUV Mission Zambonify Tool ===")
    print("Converting lawnmower pattern to zamboni pattern...")
    
    # Select input file
    input_file = select_input_file()
    if not input_file:
        print("No input file selected. Exiting.")
        return
    
    # Select output directory
    output_dir = select_output_directory()
    if not output_dir:
        print("No output directory selected. Exiting.")
        return
    
    # Create converter and process
    converter = ZamboniConverter()
    
    # Load mission
    if not converter.load_mission(input_file):
        return
    
    # Convert to zamboni pattern
    if not converter.convert_to_zamboni():
        return
    
    # Save modified mission
    if not converter.save_mission(input_file):
        return
    
    # Create visualization
    if not converter.create_visualization(output_dir, input_file):
        return
    
    messagebox.showinfo("Success", 
                       f"Zamboni conversion completed successfully!\n\n"
                       f"Output files saved to:\n{output_dir}")
    
    print("Zamboni conversion completed successfully!")


if __name__ == "__main__":
    main()
