"""
SAS RASTER FILE TOOLS - ARCGIS PRO PYTHON TOOLBOX

Author: Mike Bollinger
Last Updated: 2025-07-26

FUNCTION:
    Copies or moves synthetic aperture sonar (SAS) raster files to a new
    directory from within ArcGIS Pro.

USAGE:
    Load this .pyt in ArcGIS Pro's Geoprocessing pane (Toolboxes > Add Toolbox),
    then run the "SAS Move Raster Files" tool. To move (not copy) files,
    remove them from the Table of Contents first.

INPUTS:
    - Input Raster Layers (multi-value, required): raster layers to copy or
      move.
    - Destination folder and copy/move mode (see tool parameters).

OUTPUTS:
    Raster file(s) copied or moved to the destination folder.
"""

import arcpy
import os
import shutil
from pathlib import Path


class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the .pyt file)."""
        self.label = "SAS Raster File Tools"
        self.alias = "SASRasterTools"
        
        # List of tool classes associated with this toolbox
        self.tools = [MoveRasterFiles]


class MoveRasterFiles(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "SAS Move Raster Files"
        self.description = """Copy or move raster files to a new directory. 
        
        IMPORTANT: Move operations will fail if the raster files are currently loaded as layers in ArcGIS Pro. 
        To move files, first remove them from the Table of Contents, then run the tool.
        
        Copy operations work regardless of whether files are loaded in the map."""
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        
        # Input raster layers (allow multiple)
        param0 = arcpy.Parameter(
            displayName="Input Raster Layers",
            name="input_rasters",
            datatype="GPRasterLayer",
            parameterType="Required",
            direction="Input",
            multiValue=True)
        # Remove restrictive filter to allow any raster layer from TOC
        # param0.filter.list = ["GRID", "IMAGINE Image", "TIFF", "BMP", "GIF", "JPEG", "PNG"]
        
        # Output directory
        param1 = arcpy.Parameter(
            displayName="Output Directory",
            name="output_directory",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")
        
        # Operation type (Copy or Move)
        param2 = arcpy.Parameter(
            displayName="Operation",
            name="operation",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param2.filter.type = "ValueList"
        param2.filter.list = ["Copy", "Move"]
        param2.value = "Copy"
        
        # Overwrite existing files
        param3 = arcpy.Parameter(
            displayName="Overwrite Existing Files",
            name="overwrite",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        param3.value = False

        return [param0, param1, param2, param3]

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        
        # Get parameters
        input_rasters = parameters[0].valueAsText.split(';') if parameters[0].valueAsText else []
        output_directory = parameters[1].valueAsText
        operation = parameters[2].valueAsText
        overwrite = parameters[3].value
        
        arcpy.AddMessage(f"Starting {operation.lower()} operation...")
        arcpy.AddMessage(f"Output directory: {output_directory}")
        arcpy.AddMessage(f"Overwrite existing files: {overwrite}")
        
        # Add warning for move operations
        if operation == "Move":
            arcpy.AddWarning("NOTE: Move operations will fail if files are currently loaded in ArcGIS Pro. Remove layers from the map first if you encounter errors.")
        
        # Ensure output directory exists
        os.makedirs(output_directory, exist_ok=True)
        
        processed_files = 0
        skipped_files = 0
        
        # Process each input raster
        for raster_input in input_rasters:
            try:
                # Remove quotes if present
                raster_input = raster_input.strip("'\"")
                
                # Get the data source (file path) of the raster layer
                source_path = self.get_raster_source_path(raster_input)
                
                if not source_path:
                    arcpy.AddWarning(f"Could not determine source path for: {raster_input}")
                    skipped_files += 1
                    continue
                
                if not os.path.exists(source_path):
                    arcpy.AddWarning(f"Source file does not exist: {source_path}")
                    skipped_files += 1
                    continue
                
                # Get the filename
                filename = os.path.basename(source_path)
                destination_path = os.path.join(output_directory, filename)
                
                # Check if destination already exists
                if os.path.exists(destination_path) and not overwrite:
                    arcpy.AddWarning(f"File already exists (skipping): {filename}")
                    skipped_files += 1
                    continue
                
                # Perform the operation
                if operation == "Copy":
                    shutil.copy2(source_path, destination_path)
                    arcpy.AddMessage(f"Copied: {filename}")
                elif operation == "Move":
                    try:
                        shutil.move(source_path, destination_path)
                        arcpy.AddMessage(f"Moved: {filename}")
                    except PermissionError as e:
                        if "WinError 32" in str(e) or "being used by another process" in str(e):
                            arcpy.AddWarning(f"Cannot move {filename}: File is currently open in ArcGIS Pro. Remove the layer from the map before moving.")
                            skipped_files += 1
                            continue
                        else:
                            raise e
                
                processed_files += 1
                
            except Exception as e:
                arcpy.AddError(f"Error processing {raster_input}: {str(e)}")
                continue
        
        # Summary message
        arcpy.AddMessage(f"\nOperation completed!")
        arcpy.AddMessage(f"Files processed: {processed_files}")
        if skipped_files > 0:
            arcpy.AddMessage(f"Files skipped: {skipped_files}")
    
    def get_raster_source_path(self, raster_input):
        """
        Get the actual file path of the raster layer.
        Handles both direct file paths and CIMPATH layer references from the TOC.
        """
        try:
            # First, check if it's already a direct file path
            if os.path.exists(raster_input):
                return raster_input
            
            # Handle CIMPATH references
            if raster_input.startswith("CIMPATH="):
                layer_name = self.parse_cimpath_to_layer_name(raster_input)
                if layer_name:
                    arcpy.AddMessage(f"Parsed CIMPATH layer name: {layer_name}")
                    return self.find_layer_by_name(layer_name)
            
            # Check if it's a layer in the current map by direct name
            return self.find_layer_by_name(raster_input)
            
        except Exception as e:
            arcpy.AddMessage(f"Debug - Error getting source path for {raster_input}: {str(e)}")
            return None
    
    def parse_cimpath_to_layer_name(self, cimpath):
        """
        Parse CIMPATH reference to extract the layer name.
        Example: CIMPATH=Map/KRAKEN___2025_07_23T23_44_29___HBL___0_tif.json
        Should become: KRAKEN - 2025-07-23T23:44:29 - HBL - 0.tif
        """
        try:
            # Remove CIMPATH=Map/ prefix and .json suffix
            path_part = cimpath.replace("CIMPATH=Map/", "").replace(".json", "")
            
            # Replace triple underscores with appropriate separators
            # Convert ___ to spaces/dashes and handle the .tif extension
            if path_part.endswith("_tif"):
                path_part = path_part[:-4] + ".tif"
            elif path_part.endswith("_clip_tif"):
                path_part = path_part[:-9] + "_clip.tif"
            
            # Replace triple underscores with dashes, but be careful with timestamps
            # Convert KRAKEN___2025_07_23T23_44_29___HBL___0 format
            parts = path_part.split("___")
            if len(parts) >= 3:
                # Rejoin with appropriate separators
                name_part = parts[0]  # KRAKEN
                timestamp_part = parts[1].replace("_", ":")  # Convert underscores in timestamp to colons
                remaining_parts = parts[2:]  # HBL, 0, etc.
                
                # Reconstruct with dashes
                layer_name = f"{name_part} - {timestamp_part} - " + " - ".join(remaining_parts)
                return layer_name
            else:
                # Fallback: just replace triple underscores with dashes
                return path_part.replace("___", " - ")
                
        except Exception as e:
            arcpy.AddMessage(f"Error parsing CIMPATH: {e}")
            return None
    
    def find_layer_by_name(self, layer_name):
        """
        Find a layer in the current map by name and return its data source.
        """
        try:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            map_obj = aprx.activeMap
            
            if map_obj:
                for layer in map_obj.listLayers():
                    if hasattr(layer, 'dataSource'):
                        arcpy.AddMessage(f"Checking layer: '{layer.name}' against target: '{layer_name}'")
                        if layer.name == layer_name:
                            arcpy.AddMessage(f"Found exact match: {layer.dataSource}")
                            return layer.dataSource
                        
                        # Try partial matching if exact match fails
                        if layer_name in layer.name or layer.name in layer_name:
                            arcpy.AddMessage(f"Found partial match: {layer.dataSource}")
                            return layer.dataSource
                
                # If no match found, list all layer names for debugging
                arcpy.AddMessage("Available layers in map:")
                for layer in map_obj.listLayers():
                    if hasattr(layer, 'name'):
                        arcpy.AddMessage(f"  - {layer.name}")
            
            return None
            
        except Exception as e:
            arcpy.AddMessage(f"Error finding layer: {e}")
            return None
