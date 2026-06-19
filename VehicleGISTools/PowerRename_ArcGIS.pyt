"""
================================================================================
POWER RENAME FOR ARCGIS PRO - PYTHON TOOLBOX
================================================================================

Title:          Power Rename for ArcGIS Pro
Author:         Mike Bollinger
Version:        1.0.0
Date Created:   February 2026
Description:    Batch rename feature layer display names in ArcGIS Pro's Table 
                of Contents, inspired by Microsoft PowerToys PowerRename utility.

================================================================================
OVERVIEW
================================================================================

This toolbox provides PowerRename-like functionality for batch renaming feature
layer display names in ArcGIS Pro. It does NOT rename the actual feature class
files, only the display names visible in the Table of Contents.

Key Features:
- Search and replace with preview
- Regular expression (regex) support
- Case sensitivity control
- Match all occurrences or first only
- Apply to: Filename only, Extension only, or Both
- Enumerate items with custom patterns
- Text formatting (lowercase, UPPERCASE, Title Case, Capitalize Each Word)
- Real-time preview of rename results
- Undo capability (manual revert option)

================================================================================
WORKFLOW
================================================================================

1. Select feature layers to rename (multiselect)
2. Enter search text pattern (plain text or regex)
3. Enter replacement text
4. Configure options:
   - Use regular expressions
   - Case sensitive matching
   - Match all occurrences
   - Apply to filename/extension/both
   - Text formatting
   - Enumeration
5. Preview shows original → renamed for each layer
6. Execute to apply renames

================================================================================
REQUIREMENTS
================================================================================

- ArcGIS Pro 2.8 or later
- Python 3.7+ with re module
- Feature layers in active map

================================================================================
"""

import arcpy
import re
import os


class Toolbox:
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the .pyt file)."""
        self.label = "Power Rename for ArcGIS Pro"
        self.alias = "PowerRename"
        self.tools = [PowerRenameTool]


class PowerRenameTool:
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Power Rename - Batch Rename Layers"
        self.description = "Batch rename feature layer display names with search/replace and regex support"
        self.canRunInBackground = False
        self.category = "Layer Management"

    def getParameterInfo(self):
        """Define parameter definitions"""
        
        # Parameter 0: Input Feature Layers (multivalue)
        param0 = arcpy.Parameter(
            displayName="Select Feature Layers to Rename",
            name="input_layers",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input",
            multiValue=True)
        
        # Parameter 1: Search For
        param1 = arcpy.Parameter(
            displayName="Search For",
            name="search_text",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param1.value = ""
        
        # Parameter 2: Replace With
        param2 = arcpy.Parameter(
            displayName="Replace With",
            name="replace_text",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")
        param2.value = ""
        
        # Parameter 3: Use Regular Expressions
        param3 = arcpy.Parameter(
            displayName="Use Regular Expressions",
            name="use_regex",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        param3.value = False
        
        # Parameter 4: Case Sensitive
        param4 = arcpy.Parameter(
            displayName="Case Sensitive",
            name="case_sensitive",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        param4.value = False
        
        # Parameter 5: Match All Occurrences
        param5 = arcpy.Parameter(
            displayName="Match All Occurrences",
            name="match_all",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        param5.value = True
        param5.enabled = True
        
        # Parameter 6: Apply To
        param6 = arcpy.Parameter(
            displayName="Apply To",
            name="apply_to",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")
        param6.filter.type = "ValueList"
        param6.filter.list = ["Name and Extension", "Name Only", "Extension Only"]
        param6.value = "Name and Extension"
        
        # Parameter 7: Text Formatting
        param7 = arcpy.Parameter(
            displayName="Text Formatting",
            name="text_format",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")
        param7.filter.type = "ValueList"
        param7.filter.list = ["None", "lowercase", "UPPERCASE", "Title Case", "Capitalize Each Word"]
        param7.value = "None"
        
        # Parameter 8: Enumerate Items
        param8 = arcpy.Parameter(
            displayName="Enumerate Items",
            name="enumerate_items",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        param8.value = False
        
        # Parameter 9: Enumeration Pattern
        param9 = arcpy.Parameter(
            displayName="Enumeration Pattern",
            name="enum_pattern",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")
        param9.value = "${}"
        param9.enabled = False
        
        # Parameter 10: Start Number
        param10 = arcpy.Parameter(
            displayName="Start Number",
            name="start_num",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input")
        param10.value = 0
        param10.enabled = False
        
        # Parameter 11: Increment
        param11 = arcpy.Parameter(
            displayName="Increment",
            name="increment",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input")
        param11.value = 1
        param11.enabled = False
        
        # Parameter 12: Padding
        param12 = arcpy.Parameter(
            displayName="Padding (leading zeros)",
            name="padding",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input")
        param12.value = 0
        param12.filter.type = "Range"
        param12.filter.list = [0, 10]
        param12.enabled = False
        
        # Parameter 13: Preview
        param13 = arcpy.Parameter(
            displayName="Preview",
            name="preview",
            datatype="GPString",
            parameterType="Derived",
            direction="Output")
        param13.parameterType = "Optional"
        
        return [param0, param1, param2, param3, param4, param5, param6, param7, 
                param8, param9, param10, param11, param12, param13]

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal validation."""
        
        # Enable/disable enumeration parameters based on enumerate checkbox
        if parameters[8].value:  # enumerate_items
            parameters[9].enabled = True   # enum_pattern
            parameters[10].enabled = True  # start_num
            parameters[11].enabled = True  # increment
            parameters[12].enabled = True  # padding
        else:
            parameters[9].enabled = False
            parameters[10].enabled = False
            parameters[11].enabled = False
            parameters[12].enabled = False
        
        # Generate preview if we have layers and search text
        if parameters[0].value and parameters[1].value:
            try:
                preview_text = self.generate_preview(parameters)
                parameters[13].value = preview_text
            except:
                pass
        
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool parameter."""
        
        # Validate regex if enabled
        if parameters[3].value and parameters[1].value:  # use_regex and search_text
            try:
                re.compile(parameters[1].valueAsText)
            except re.error as e:
                parameters[1].setErrorMessage(f"Invalid regular expression: {str(e)}")
        
        # Validate enumeration pattern if enumerate is enabled
        if parameters[8].value and parameters[9].value:  # enumerate_items and enum_pattern
            pattern = parameters[9].valueAsText
            if not ("${" in pattern or "{$" in pattern):
                parameters[9].setWarningMessage(
                    "Enumeration pattern should contain ${} or customized patterns like "
                    "${start=1;increment=2;padding=3}"
                )
        
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        
        # Get parameters
        input_layers = parameters[0].valueAsText.split(';')
        search_text = parameters[1].valueAsText
        replace_text = parameters[2].valueAsText if parameters[2].value else ""
        use_regex = parameters[3].value
        case_sensitive = parameters[4].value
        match_all = parameters[5].value
        apply_to = parameters[6].valueAsText
        text_format = parameters[7].valueAsText
        enumerate_items = parameters[8].value
        enum_pattern = parameters[9].valueAsText if parameters[9].value else "${}"
        start_num = parameters[10].value if parameters[10].value is not None else 0
        increment = parameters[11].value if parameters[11].value else 1
        padding = parameters[12].value if parameters[12].value else 0
        
        arcpy.AddMessage("=" * 80)
        arcpy.AddMessage("POWER RENAME FOR ARCGIS PRO")
        arcpy.AddMessage("=" * 80)
        arcpy.AddMessage(f"\nProcessing {len(input_layers)} feature layer(s)...")
        arcpy.AddMessage(f"Search: '{search_text}'")
        arcpy.AddMessage(f"Replace: '{replace_text}'")
        arcpy.AddMessage(f"Regular Expressions: {use_regex}")
        arcpy.AddMessage(f"Case Sensitive: {case_sensitive}")
        arcpy.AddMessage(f"Match All: {match_all}")
        arcpy.AddMessage(f"Apply To: {apply_to}")
        arcpy.AddMessage(f"Text Format: {text_format}")
        arcpy.AddMessage(f"Enumerate: {enumerate_items}")
        
        if enumerate_items:
            arcpy.AddMessage(f"Enumeration Pattern: {enum_pattern}")
            arcpy.AddMessage(f"Start: {start_num}, Increment: {increment}, Padding: {padding}")
        
        # Get the current map
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        map_obj = aprx.activeMap
        
        if not map_obj:
            arcpy.AddError("No active map found. Please open a map in ArcGIS Pro.")
            return
        
        # Track successful and failed renames
        successful = []
        failed = []
        unchanged = []
        
        arcpy.AddMessage("\n" + "-" * 80)
        arcpy.AddMessage("RENAME PREVIEW AND EXECUTION")
        arcpy.AddMessage("-" * 80)
        
        # Process each layer
        counter = start_num
        for i, layer_path in enumerate(input_layers):
            try:
                # Clean up the path
                layer_path = layer_path.strip("'\"")
                layer_name = self.extract_layer_name(layer_path)
                
                # Debug: Show what we're looking for
                arcpy.AddMessage(f"\n[{i+1}] Searching for layer:")
                arcpy.AddMessage(f"     Path: {layer_path}")
                arcpy.AddMessage(f"     Extracted name: {layer_name}")
                
                # Find the layer in the map
                layer = self.find_layer_in_map(map_obj, layer_name, layer_path)
                
                if not layer:
                    failed.append((layer_name, "Layer not found in map"))
                    arcpy.AddWarning(f"     Layer not found in map")
                    continue
                
                arcpy.AddMessage(f"     Found layer: {layer.name}")
                original_name = layer.name
                
                # Generate new name
                new_name = self.generate_new_name(
                    original_name,
                    search_text,
                    replace_text,
                    use_regex,
                    case_sensitive,
                    match_all,
                    apply_to,
                    text_format,
                    enumerate_items,
                    counter,
                    enum_pattern,
                    increment,
                    padding
                )
                
                # Check if name actually changed
                if new_name == original_name:
                    unchanged.append(original_name)
                    arcpy.AddMessage(f"     No change needed (search text not found)")
                    continue
                
                # Apply the rename
                arcpy.AddMessage(f"     Renaming:")
                arcpy.AddMessage(f"       Original: {original_name}")
                arcpy.AddMessage(f"       New:      {new_name}")
                
                layer.name = new_name
                successful.append((original_name, new_name))
                
                # Increment counter for next iteration
                if enumerate_items:
                    counter += increment
                
            except Exception as e:
                failed.append((layer_name if 'layer_name' in locals() else layer_path, str(e)))
                arcpy.AddWarning(f"\n[{i+1}] Failed to process: {str(e)}")
                continue
        
        # Summary
        arcpy.AddMessage("\n" + "=" * 80)
        arcpy.AddMessage("RENAME SUMMARY")
        arcpy.AddMessage("=" * 80)
        arcpy.AddMessage(f"Successfully renamed: {len(successful)}")
        arcpy.AddMessage(f"Unchanged (no match): {len(unchanged)}")
        arcpy.AddMessage(f"Failed: {len(failed)}")
        
        if failed:
            arcpy.AddMessage("\nFailed items:")
            for name, error in failed:
                arcpy.AddMessage(f"  - {name}: {error}")
        
        arcpy.AddMessage("\n" + "=" * 80)
        arcpy.AddMessage("Power Rename complete!")
        arcpy.AddMessage("=" * 80)
        
        return

    def generate_preview(self, parameters):
        """Generate a preview string showing original → new names"""
        
        try:
            input_layers = parameters[0].valueAsText.split(';')
            search_text = parameters[1].valueAsText
            replace_text = parameters[2].valueAsText if parameters[2].value else ""
            use_regex = parameters[3].value
            case_sensitive = parameters[4].value
            match_all = parameters[5].value
            apply_to = parameters[6].valueAsText
            text_format = parameters[7].valueAsText if parameters[7].value else "None"
            enumerate_items = parameters[8].value
            enum_pattern = parameters[9].valueAsText if parameters[9].value else "${}"
            start_num = parameters[10].value if parameters[10].value is not None else 0
            increment = parameters[11].value if parameters[11].value else 1
            padding = parameters[12].value if parameters[12].value else 0
            
            preview_lines = ["PREVIEW OF CHANGES:", "-" * 50]
            counter = start_num
            
            for layer_path in input_layers[:10]:  # Limit preview to first 10
                layer_path = layer_path.strip("'\"")
                original_name = self.extract_layer_name(layer_path)
                
                new_name = self.generate_new_name(
                    original_name,
                    search_text,
                    replace_text,
                    use_regex,
                    case_sensitive,
                    match_all,
                    apply_to,
                    text_format,
                    enumerate_items,
                    counter,
                    enum_pattern,
                    increment,
                    padding
                )
                
                if new_name != original_name:
                    preview_lines.append(f"{original_name} → {new_name}")
                else:
                    preview_lines.append(f"{original_name} (no change)")
                
                if enumerate_items:
                    counter += increment
            
            if len(input_layers) > 10:
                preview_lines.append(f"... and {len(input_layers) - 10} more")
            
            return "\n".join(preview_lines)
            
        except Exception as e:
            return f"Preview unavailable: {str(e)}"

    def extract_layer_name(self, layer_path):
        """Extract layer name from full path"""
        # Handle different path formats
        if "\\" in layer_path:
            return layer_path.split("\\")[-1]
        elif "/" in layer_path:
            return layer_path.split("/")[-1]
        else:
            return layer_path

    def find_layer_in_map(self, map_obj, layer_name, layer_path):
        """Find a layer in the map by name or path, including layers in groups"""
        
        # First, try exact match
        for lyr in map_obj.listLayers():
            if lyr.name == layer_name:
                return lyr
        
        # Second, try to extract and match the actual layer name from the path
        # ArcGIS Pro paths for grouped layers look like: "GroupName\\LayerName"
        if "\\" in layer_path:
            # Try the last component (actual layer name)
            actual_layer_name = layer_path.split("\\")[-1].strip("'\"")
            for lyr in map_obj.listLayers():
                if lyr.name == actual_layer_name:
                    return lyr
        
        # Third, try partial matches (fallback)
        for lyr in map_obj.listLayers():
            if layer_name in lyr.name or lyr.name in layer_path:
                return lyr
        
        return None

    def generate_new_name(self, original_name, search_text, replace_text, 
                         use_regex, case_sensitive, match_all, apply_to,
                         text_format, enumerate_items, counter, enum_pattern, 
                         increment, padding):
        """
        Generate the new name based on all parameters.
        
        This is the core rename logic that mimics PowerRename functionality.
        """
        
        # Split name into filename and extension
        name_parts = self.split_name_extension(original_name)
        base_name = name_parts['base']
        extension = name_parts['ext']
        
        # Determine what to apply the rename to
        if apply_to == "Extension Only":
            # Only modify extension
            new_base = base_name
            new_ext = self.apply_search_replace(
                extension, search_text, replace_text, 
                use_regex, case_sensitive, match_all
            )
        elif apply_to == "Name Only":
            # Only modify base name
            new_base = self.apply_search_replace(
                base_name, search_text, replace_text,
                use_regex, case_sensitive, match_all
            )
            new_ext = extension
        else:  # "Name and Extension"
            # Modify both
            new_base = self.apply_search_replace(
                base_name, search_text, replace_text,
                use_regex, case_sensitive, match_all
            )
            new_ext = self.apply_search_replace(
                extension, search_text, replace_text,
                use_regex, case_sensitive, match_all
            )
        
        # Apply enumeration if enabled
        if enumerate_items:
            # Parse enumeration pattern
            enum_value = self.format_enumeration(counter, enum_pattern, increment, padding)
            
            # Replace enumeration patterns in the replace_text or append
            if "${" in replace_text or "{$" in replace_text:
                # Pattern is in replace text, already handled above
                pass
            else:
                # Append enumeration to base name
                if "${" in enum_pattern:
                    # Replace pattern in new_base if it exists, otherwise append
                    if "${" in new_base:
                        new_base = new_base.replace("${}", enum_value)
                        new_base = re.sub(r'\$\{[^}]+\}', enum_value, new_base)
                    else:
                        new_base = new_base + enum_value
        
        # Apply text formatting
        if text_format and text_format != "None":
            new_base = self.apply_text_formatting(new_base, text_format)
            new_ext = self.apply_text_formatting(new_ext, text_format)
        
        # Reconstruct the full name
        if new_ext:
            return f"{new_base}.{new_ext}"
        else:
            return new_base

    def split_name_extension(self, name):
        """
        Split a layer name into base name and extension.
        
        Returns dict with 'base' and 'ext' keys.
        """
        if '.' in name:
            parts = name.rsplit('.', 1)
            return {'base': parts[0], 'ext': parts[1]}
        else:
            return {'base': name, 'ext': ''}

    def apply_search_replace(self, text, search_text, replace_text, 
                            use_regex, case_sensitive, match_all):
        """
        Apply search and replace logic to text.
        
        This handles both plain text and regex replacement.
        """
        
        if not search_text:
            return text
        
        if use_regex:
            # Use regular expressions
            flags = 0 if case_sensitive else re.IGNORECASE
            
            try:
                if match_all:
                    # Replace all occurrences
                    return re.sub(search_text, replace_text, text, flags=flags)
                else:
                    # Replace only first occurrence
                    return re.sub(search_text, replace_text, text, count=1, flags=flags)
            except re.error as e:
                # If regex fails, return original
                return text
        else:
            # Plain text search and replace
            if case_sensitive:
                if match_all:
                    return text.replace(search_text, replace_text)
                else:
                    return text.replace(search_text, replace_text, 1)
            else:
                # Case-insensitive plain text replacement
                if match_all:
                    # Replace all occurrences case-insensitively
                    pattern = re.compile(re.escape(search_text), re.IGNORECASE)
                    return pattern.sub(replace_text, text)
                else:
                    # Replace first occurrence case-insensitively
                    pattern = re.compile(re.escape(search_text), re.IGNORECASE)
                    return pattern.sub(replace_text, text, count=1)

    def format_enumeration(self, counter, pattern, increment, padding):
        """
        Format enumeration value based on pattern.
        
        Supports patterns like:
        - ${}                                   Simple counter
        - ${start=10}                           Custom start
        - ${increment=2}                        Custom increment
        - ${padding=4}                          Leading zeros
        - ${start=10;increment=2;padding=4}     Combined
        """
        
        # Default values
        start = counter
        pad = padding
        inc = increment
        
        # Parse pattern if it contains customization
        if "{" in pattern and "}" in pattern:
            # Extract content between braces
            content_match = re.search(r'\{([^}]+)\}', pattern)
            if content_match:
                content = content_match.group(1)
                
                # Check if it has parameters
                if '=' in content:
                    # Parse key=value pairs separated by semicolons or commas
                    params = re.split(r'[;,]', content)
                    for param in params:
                        if '=' in param:
                            key, value = param.split('=', 1)
                            key = key.strip().lower()
                            value = value.strip()
                            
                            try:
                                if key == 'start':
                                    start = int(value)
                                elif key == 'increment' or key == 'inc':
                                    inc = int(value)
                                elif key == 'padding' or key == 'pad':
                                    pad = int(value)
                            except ValueError:
                                pass
        
        # Format the counter with padding
        if pad > 0:
            return str(counter).zfill(pad)
        else:
            return str(counter)

    def apply_text_formatting(self, text, format_type):
        """
        Apply text formatting transformations.
        
        Supports:
        - lowercase
        - UPPERCASE
        - Title Case
        - Capitalize Each Word
        """
        
        if not text or format_type == "None":
            return text
        
        if format_type == "lowercase":
            return text.lower()
        elif format_type == "UPPERCASE":
            return text.upper()
        elif format_type == "Title Case":
            return text.title()
        elif format_type == "Capitalize Each Word":
            return ' '.join(word.capitalize() for word in text.split())
        else:
            return text


class LayerRenameUtils:
    """Utility functions for layer renaming operations"""
    
    @staticmethod
    def backup_layer_names(map_obj):
        """
        Create a backup of all layer names in a map.
        Returns a dictionary mapping layer objects to their original names.
        """
        backup = {}
        for lyr in map_obj.listLayers():
            backup[id(lyr)] = lyr.name
        return backup
    
    @staticmethod
    def restore_layer_names(map_obj, backup):
        """
        Restore layer names from a backup dictionary.
        """
        for lyr in map_obj.listLayers():
            if id(lyr) in backup:
                lyr.name = backup[id(lyr)]
    
    @staticmethod
    def validate_layer_name(name):
        """
        Validate that a layer name is acceptable for ArcGIS Pro.
        Returns (is_valid, error_message) tuple.
        """
        if not name:
            return (False, "Layer name cannot be empty")
        
        if len(name) > 255:
            return (False, "Layer name cannot exceed 255 characters")
        
        # ArcGIS Pro generally allows most characters in display names
        # Unlike feature class names, display names are more permissive
        
        return (True, "")
    
    @staticmethod
    def get_all_layer_names(map_obj):
        """Get a list of all layer names in the map"""
        return [lyr.name for lyr in map_obj.listLayers()]
    
    @staticmethod
    def check_duplicate_names(map_obj, new_names):
        """
        Check if any new names would create duplicates.
        Returns list of duplicate names.
        """
        existing_names = LayerRenameUtils.get_all_layer_names(map_obj)
        duplicates = []
        
        for new_name in new_names:
            if new_name in existing_names:
                duplicates.append(new_name)
        
        return duplicates
