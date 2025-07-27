#!/usr/bin/env python3
"""
Zambonify Mission NemoSens

This script converts an AUV JSON mission from a lawnmower pattern to a zamboni pattern.
The zamboni pattern reduces sharp turns by reordering lines to create multiple smaller boxes
within the survey area, making the AUV navigation more efficient.

Author: [Your Name]
Date: July 27, 2025
"""

import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox
import matplotlib.pyplot as plt
import numpy as np
import math
from typing import List, Dict, Tuple, Any


class ZamboniConverter:
    """Class to handle conversion from lawnmower to zamboni pattern."""
    
    def __init__(self):
        self.mission_data = None
        self.rail_family = None
        self.original_stages = []
        self.zamboni_stages = []
        
    def load_mission(self, file_path: str) -> bool:
        """Load the JSON mission file."""
        try:
            with open(file_path, 'r') as f:
                self.mission_data = json.load(f)
            
            # Find the rail family path
            self.rail_family = self._find_rail_family()
            if not self.rail_family:
                messagebox.showerror("Error", "No rail family found in mission file!")
                return False
                
            self.original_stages = self.rail_family['stages'].copy()
            print(f"Loaded mission with {len(self.original_stages)} rail stages")
            return True
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load mission file: {str(e)}")
            return False
    
    def _find_rail_family(self) -> Dict[str, Any]:
        """Find the rail family path in the mission data."""
        try:
            nemosens_device = None
            for device in self.mission_data['mission']['devices']:
                if device.get('type') == 'DEVICE_DRONE':
                    nemosens_device = device
                    break
            
            if not nemosens_device:
                return None
                
            for path in nemosens_device.get('paths', []):
                if path.get('type') == 'PATH_RAIL':
                    return path
                    
            return None
        except Exception:
            return None
    
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
    
    def group_stages_into_lines(self) -> List[List[Dict]]:
        """Group stages into lines (pairs of A and B points)."""
        lines = []
        i = 0
        
        while i < len(self.original_stages) - 1:
            stage_a = self.original_stages[i]
            stage_b = self.original_stages[i + 1]
            
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
        if i < len(self.original_stages):
            lines.append([self.original_stages[i]])
            
        return lines
    
    def convert_to_zamboni(self) -> bool:
        """Convert lawnmower pattern to zamboni pattern."""
        try:
            lines = self.group_stages_into_lines()
            print(f"Found {len(lines)} lines to reorder")
            
            # Create zamboni pattern using approach from Zamboni2 example
            # This approach reorders lines and reverses direction for efficiency
            zamboni_lines = self._create_zamboni_pattern(lines)
            
            # Flatten back to stages
            self.zamboni_stages = []
            for line in zamboni_lines:
                self.zamboni_stages.extend(line)
            
            # Update the mission data
            self.rail_family['stages'] = self.zamboni_stages
            
            print(f"Created zamboni pattern with {len(self.zamboni_stages)} stages")
            return True
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to convert to zamboni pattern: {str(e)}")
            return False
    
    def _create_zamboni_pattern(self, lines: List[List[Dict]]) -> List[List[Dict]]:
        """
        Create zamboni pattern using the corrected algorithm:
        
        1. Divide lines into halves (1-10 first half, 11-20 second half)
        2. First half: odd lines normal (A→B), even lines reversed (B→A)  
        3. Second half: even lines normal (A→B), odd lines reversed (B→A)
        4. Interleave: pos1 first half, pos1 second half, pos2 first half, pos2 second half, etc.
        
        This ensures all first half lines go one way and all second half lines go the other way.
        """
        if len(lines) < 2:
            print(f"Not enough lines ({len(lines)}) for zamboni pattern, returning as-is")
            return lines
            
        total_lines = len(lines)
        half_lines = total_lines // 2
        
        print(f"\n=== ZAMBONI PATTERN CREATION ===")
        print(f"Total lines: {total_lines}")
        print(f"Half lines: {half_lines}")
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
        
        # Handle any remaining lines if total is odd
        if total_lines % 2 == 1:
            zamboni_pos = len(zamboni_lines) + 1
            remaining_line = lines[-1].copy()
            remaining_line_num = total_lines
            remaining_line_name = remaining_line[0]['name'][:-2] if len(remaining_line) == 2 and remaining_line[0]['name'].endswith(' A') else remaining_line[0]['name']
            print(f"Zamboni pos {zamboni_pos:2d}: Remaining line {remaining_line_num:2d} ({remaining_line_name}) - (odd total)")
            zamboni_lines.append(remaining_line)
        
        print(f"\nCreated zamboni pattern with {len(zamboni_lines)} lines")
        print("=== END ZAMBONI PATTERN CREATION ===\n")
        
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
    
    def create_visualization(self, output_dir: str) -> bool:
        """Create a visualization map showing the zamboni pattern with directional indicators."""
        try:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
            
            # Plot original pattern
            self._plot_pattern(ax1, self.original_stages, "Original Lawnmower Pattern")
            
            # Plot zamboni pattern
            self._plot_pattern(ax2, self.zamboni_stages, "Zamboni Pattern")
            
            plt.tight_layout()
            
            # Save the plot
            map_file = os.path.join(output_dir, "zamboni_pattern_comparison.png")
            plt.savefig(map_file, dpi=300, bbox_inches='tight')
            plt.show()
            
            print(f"Saved visualization to: {map_file}")
            return True
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create visualization: {str(e)}")
            return False
    
    def _plot_pattern(self, ax, stages: List[Dict], title: str):
        """Plot a single pattern on the given axes."""
        # Extract coordinates
        lats = [stage['latitude'] for stage in stages]
        lons = [stage['longitude'] for stage in stages]
        
        # Plot waypoints as small dots
        ax.scatter(lons, lats, c='black', s=15, zorder=5, alpha=0.7)
        
        # Plot lines with directional colors
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
                ax.plot([lon1, lon2], [lat1, lat2], color=color, linewidth=2, alpha=0.8)
        
        # Connect consecutive lines with thin dashed gray lines (transit paths)
        for i in range(1, len(stages) - 1, 2):
            if i + 1 < len(stages):
                lat1, lon1 = stages[i]['latitude'], stages[i]['longitude']
                lat2, lon2 = stages[i + 1]['latitude'], stages[i + 1]['longitude']
                ax.plot([lon1, lon2], [lat1, lat2], 'gray', linewidth=0.5, 
                       alpha=0.4, linestyle='--')
        
        # Add waypoint labels for key points only
        for i, stage in enumerate(stages):
            if i % 8 == 0:  # Only label every 8th point to reduce clutter
                ax.annotate(stage['name'], 
                           (stage['longitude'], stage['latitude']),
                           xytext=(3, 3), textcoords='offset points',
                           fontsize=7, alpha=0.7)
        
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
            Line2D([0], [0], color='gray', lw=1, linestyle='--', label='Transit between lines')
        ]
        ax.legend(handles=legend_elements, loc='upper right', fontsize=8)


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
    if not converter.create_visualization(output_dir):
        return
    
    messagebox.showinfo("Success", 
                       f"Zamboni conversion completed successfully!\n\n"
                       f"Output files saved to:\n{output_dir}")
    
    print("Zamboni conversion completed successfully!")


if __name__ == "__main__":
    main()
