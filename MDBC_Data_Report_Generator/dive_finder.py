"""
Dive Finder Module
Handles recursive scanning of directories to find dive folders and Report_Plots
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Optional


class DiveFinder:
    """Finds dive folders and their Report_Plots across multiple data sources"""
    
    def __init__(self):
        self.dive_pattern = re.compile(r'DIVE(\d+)', re.IGNORECASE)
    
    def _find_report_plots_folder(self, dive_folder: str) -> Optional[str]:
        """
        Recursively search for Report_Plots folder within a dive folder
        Returns the first Report_Plots path found, or None
        """
        try:
            for root, dirs, files in os.walk(dive_folder):
                if 'Report_Plots' in dirs:
                    report_plots_path = os.path.join(root, 'Report_Plots')
                    # Verify it actually contains image files
                    if self._folder_has_images(report_plots_path):
                        return report_plots_path
        except Exception as e:
            print(f"Error searching for Report_Plots in {dive_folder}: {e}")
        return None
    
    def _folder_has_images(self, folder_path: str) -> bool:
        """Check if folder contains any image files"""
        try:
            image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}
            for file in os.listdir(folder_path):
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    return True
        except Exception:
            pass
        return False
        
    def find_dives_in_folder(self, base_path: str) -> List[Dict]:
        """
        Recursively search for dive folders in a given path
        
        Returns list of dicts with:
        - dive_number: str (e.g., "003")
        - dive_name: str (e.g., "DIVE003")
        - folder_path: str (full path to dive folder)
        - report_plots_path: Optional[str] (path to Report_Plots if exists)
        - has_report_plots: bool
        - source: str (base path where it was found)
        """
        dives = []
        
        if not os.path.exists(base_path):
            return dives
            
        try:
            for root, dirs, files in os.walk(base_path):
                for dir_name in dirs:
                    match = self.dive_pattern.search(dir_name)
                    if match:
                        dive_number = match.group(1).zfill(3)  # Pad to 3 digits
                        full_path = os.path.join(root, dir_name)
                        
                        # Check for Report_Plots subfolder - search recursively within dive folder
                        report_plots_path = self._find_report_plots_folder(full_path)
                        has_report_plots = report_plots_path is not None
                        
                        dive_info = {
                            'dive_number': dive_number,
                            'dive_name': dir_name,  # Keep original casing
                            'folder_path': full_path,
                            'report_plots_path': report_plots_path,
                            'has_report_plots': has_report_plots,
                            'source': base_path
                        }
                        
                        dives.append(dive_info)
        except Exception as e:
            print(f"Error scanning {base_path}: {e}")
            
        return dives
    
    def find_dives_in_multiple_folders(self, base_paths: List[str]) -> Dict[str, List[Dict]]:
        """
        Find dives across multiple source folders
        
        Returns dict where keys are dive_numbers and values are lists of dive_info dicts
        This allows handling multiple sources for the same dive number
        """
        all_dives = {}
        
        for base_path in base_paths:
            dives = self.find_dives_in_folder(base_path)
            
            for dive in dives:
                dive_num = dive['dive_number']
                if dive_num not in all_dives:
                    all_dives[dive_num] = []
                all_dives[dive_num].append(dive)
        
        return all_dives
    
    def merge_dive_sources(self, dive_list: List[Dict]) -> Dict:
        """
        Merge multiple sources for the same dive into one entry
        Prioritizes sources with Report_Plots folders
        """
        if not dive_list:
            return None
            
        # Sort by has_report_plots (True first) and then by path length (shorter first)
        sorted_dives = sorted(dive_list, 
                             key=lambda x: (not x['has_report_plots'], len(x['folder_path'])))
        
        primary = sorted_dives[0]
        
        # Collect all sources
        all_sources = [d['source'] for d in dive_list]
        all_folders = [d['folder_path'] for d in dive_list]
        
        merged = {
            'dive_number': primary['dive_number'],
            'dive_name': primary['dive_name'],
            'folder_path': primary['folder_path'],
            'report_plots_path': primary['report_plots_path'],
            'has_report_plots': primary['has_report_plots'],
            'primary_source': primary['source'],
            'all_sources': all_sources,
            'all_folders': all_folders,
            'source_count': len(dive_list)
        }
        
        return merged
    
    def get_images_from_report_plots(self, report_plots_path: str) -> List[str]:
        """Get list of image and metrics files from Report_Plots folder"""
        if not report_plots_path or not os.path.exists(report_plots_path):
            return []
            
        # Include both images and metrics text files
        file_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.txt']
        files = []
        
        try:
            for file in os.listdir(report_plots_path):
                if any(file.lower().endswith(ext) for ext in file_extensions):
                    files.append(os.path.join(report_plots_path, file))
        except Exception as e:
            print(f"Error reading files from {report_plots_path}: {e}")
            
        return sorted(files)
    
    def categorize_images(self, image_paths: List[str]) -> Dict[str, List[str]]:
        """
        Categorize images by type based on filename patterns
        Note: This method is deprecated - new workflow uses ordered content in report_generator
        
        Returns dict with categories:
        - navigation: nav, motion analysis
        - imaging: camera data, overlaps, visibility
        - laser: LLS processing plots
        - metrics: text files with metrics data
        - other: uncategorized
        """
        categories = {
            'navigation': [],
            'imaging': [],
            'laser': [],
            'metrics': [],
            'other': []
        }
        
        navigation_keywords = ['nav', 'motion', 'analysis', 'track', 'attitude']
        imaging_keywords = ['image', 'highlight', 'altitude', 'overlap', 'visibility', 'footprint']
        laser_keywords = ['lls', 'laser', 'dive_profile', 'intensity', 'depth', 'deviation']
        
        for file_path in image_paths:
            filename = os.path.basename(file_path).lower()
            
            # Check if it's a metrics file
            if filename.endswith('.txt') and 'metric' in filename:
                categories['metrics'].append(file_path)
                continue
            
            categorized = False
            for keyword in navigation_keywords:
                if keyword in filename:
                    categories['navigation'].append(file_path)
                    categorized = True
                    break
                    
            if not categorized:
                for keyword in imaging_keywords:
                    if keyword in filename:
                        categories['imaging'].append(file_path)
                        categorized = True
                        break
                        
            if not categorized:
                for keyword in laser_keywords:
                    if keyword in filename:
                        categories['laser'].append(file_path)
                        categorized = True
                        break
                        
            if not categorized:
                categories['other'].append(file_path)
        
        return categories
