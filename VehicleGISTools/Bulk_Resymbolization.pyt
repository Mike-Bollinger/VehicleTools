"""
ArcGIS Pro Python Toolbox for Batch Resymbolization
Applies random, distinct colors to multiple feature classes while considering background color
"""

import arcpy
import random
import colorsys


class Toolbox:
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the .pyt file)."""
        self.label = "Bulk Resymbolization Toolbox"
        self.alias = "BulkResymbolization"
        self.tools = [BulkResymbolizationTool]


class BulkResymbolizationTool:
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Batch Apply Random Colors"
        self.description = "Apply random, distinct colors to multiple feature classes based on background color"
        self.canRunInBackground = False
        self.category = "Symbolization"

    def getParameterInfo(self):
        """Define parameter definitions"""
        
        # Parameter 0: Input Feature Layers (multivalue)
        param0 = arcpy.Parameter(
            displayName="Input Feature Layers",
            name="input_layers",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input",
            multiValue=True)
        param0.description = "Select one or more feature layers to apply distinct colors to. Layers can be points, lines, or polygons. Colors will be applied in the order layers are listed."
        
        # Parameter 1: Background Color Type
        param1 = arcpy.Parameter(
            displayName="Background Color",
            name="background_color",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param1.filter.type = "ValueList"
        param1.filter.list = ["Light", "Dark"]
        param1.value = "Light"
        param1.description = "Choose based on your map background. Light backgrounds use darker, saturated colors for visibility. Dark backgrounds use brighter colors. Default: Light"
        
        # Parameter 2: Color Order
        param2 = arcpy.Parameter(
            displayName="Color Order",
            name="color_order",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param2.filter.type = "ValueList"
        param2.filter.list = ["Rainbow (Ordered)", "Random"]
        param2.value = "Rainbow (Ordered)"
        param2.description = "Rainbow (Ordered): Colors progress smoothly through the spectrum (red→orange→yellow→green→blue→purple). Random: Colors are randomly distributed for maximum contrast between adjacent layers."
        
        # Parameter 3: Apply Color To
        param3 = arcpy.Parameter(
            displayName="Apply Color To",
            name="apply_to",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param3.filter.type = "ValueList"
        param3.filter.list = ["All (Fill and Outline)", "Fill Only", "Outline/Stroke Only"]
        param3.value = "All (Fill and Outline)"
        param3.description = "All: Applies color to both fills and outlines. Fill Only: Colors polygon interiors only (for polygons). Outline/Stroke Only: Colors lines and polygon outlines only. For line features, use All or Outline/Stroke Only."
        
        # Parameter 4: Color Saturation
        param4 = arcpy.Parameter(
            displayName="Color Saturation (%)",
            name="saturation",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input")
        param4.value = 80
        param4.filter.type = "Range"
        param4.filter.list = [50, 100]
        param4.description = "Controls color intensity. Higher values (90-100%) produce vivid, pure colors. Lower values (50-70%) produce muted, pastel colors. Default: 80% provides good visibility and distinction."
        
        # Parameter 5: Minimum Color Separation
        param5 = arcpy.Parameter(
            displayName="Minimum Color Separation (degrees)",
            name="min_separation",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input")
        param5.value = 30
        param5.filter.type = "Range"
        param5.filter.list = [15, 90]
        param5.description = "Minimum spacing between colors on the color wheel (0-360°). Larger values (60-90°) ensure very distinct colors but limit variety. Smaller values (15-30°) allow more color variation but may produce similar hues. Default: 30°"
        
        return [param0, param1, param2, param3, param4, param5]

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        
        # Get parameters
        input_layers = parameters[0].valueAsText.split(';')
        background = parameters[1].valueAsText
        color_order = parameters[2].valueAsText
        apply_to = parameters[3].valueAsText
        saturation = parameters[4].value if parameters[4].value else 80
        min_separation = parameters[5].value if parameters[5].value else 30
        
        arcpy.AddMessage(f"Processing {len(input_layers)} feature layers...")
        arcpy.AddMessage(f"Background: {background}")
        arcpy.AddMessage(f"Color Order: {color_order}")
        arcpy.AddMessage(f"Apply To: {apply_to}")
        arcpy.AddMessage(f"Saturation: {saturation}%")
        arcpy.AddMessage(f"Minimum separation: {min_separation} degrees")
        
        # Generate distinct colors
        colors = self.generate_distinct_colors(
            len(input_layers), 
            background, 
            saturation / 100.0,
            min_separation,
            ordered=("Ordered" in color_order)
        )
        
        # Apply colors to each layer
        for i, layer_path in enumerate(input_layers):
            try:
                # Clean up the path (remove quotes if present)
                layer_path = layer_path.strip("'\"")
                
                # Get the layer name
                layer_name = layer_path.split("\\")[-1] if "\\" in layer_path else layer_path
                
                arcpy.AddMessage(f"\nProcessing layer {i+1}/{len(input_layers)}: {layer_name}")
                
                # Apply the color
                color = colors[i]
                self.apply_color_to_layer(layer_path, color, apply_to, messages)
                
                arcpy.AddMessage(f"  Applied RGB({color[0]}, {color[1]}, {color[2]})")
                
            except Exception as e:
                arcpy.AddWarning(f"  Failed to process {layer_path}: {str(e)}")
                continue
        
        arcpy.AddMessage("\nBatch resymbolization complete!")
        return

    def generate_distinct_colors(self, count, background, saturation, min_separation, ordered=True):
        """
        Generate a list of distinct colors based on background type.
        
        Args:
            count: Number of colors to generate
            background: "Light" or "Dark"
            saturation: Color saturation (0.0 to 1.0)
            min_separation: Minimum hue separation in degrees (0-360)
            ordered: If True, maintain rainbow order; if False, randomize
        
        Returns:
            List of RGB tuples (0-255 range)
        """
        colors = []
        
        # Define value (brightness) ranges based on background
        if background == "Light":
            # For light backgrounds, use darker, more saturated colors
            # Avoid light yellows and pastels
            min_value = 0.4
            max_value = 0.8
            # Avoid yellow range (45-75 degrees) for light backgrounds
            excluded_hue_ranges = [(45, 75)]
        else:  # Dark background
            # For dark backgrounds, use brighter colors
            # Avoid very dark colors
            min_value = 0.6
            max_value = 1.0
            # Avoid dark blue/purple range if too dark
            excluded_hue_ranges = []
        
        # Generate evenly spaced hues
        if count == 1:
            base_hues = [random.uniform(0, 360)]
        else:
            # Start with evenly spaced hues
            hue_step = 360.0 / count
            base_hues = [i * hue_step for i in range(count)]
            
            if not ordered:
                # Add randomness while maintaining separation for random mode
                random_offset = random.uniform(0, hue_step * 0.3)
                base_hues = [(h + random_offset) % 360 for h in base_hues]
        
        # Shuffle only if random order requested
        if not ordered:
            random.shuffle(base_hues)
        
        for hue in base_hues:
            # Check if hue is in excluded range
            is_excluded = False
            for exc_min, exc_max in excluded_hue_ranges:
                if exc_min <= hue <= exc_max:
                    # Shift hue to nearest acceptable value
                    if abs(hue - exc_min) < abs(hue - exc_max):
                        hue = exc_min - 10
                    else:
                        hue = exc_max + 10
                    hue = hue % 360
                    break
            
            # Add slight variation to value for more variety
            value = random.uniform(min_value, max_value)
            
            # Convert HSV to RGB (hue in 0-1 range for colorsys)
            r, g, b = colorsys.hsv_to_rgb(hue / 360.0, saturation, value)
            
            # Convert to 0-255 range
            rgb = (int(r * 255), int(g * 255), int(b * 255))
            colors.append(rgb)
        
        return colors

    def apply_color_recursive(self, symbol_layer, color_dict, apply_to):
        """
        Recursively apply color to symbol layers and nested graphics.
        
        Args:
            symbol_layer: CIM symbol layer object
            color_dict: Dictionary with color information
            apply_to: "All", "Fill", or "Stroke" to control which layers get colored
        """
        layer_type = getattr(symbol_layer, 'type', None)
        
        # Determine if we should apply color based on layer type and user preference
        should_apply = False
        
        if "All" in apply_to:
            # Apply to everything with a color property
            should_apply = hasattr(symbol_layer, 'color')
        elif "Fill" in apply_to:
            # Apply only to fill layers
            should_apply = layer_type in ['CIMSolidFill', 'CIMHatchFill', 'CIMGradientFill']
        elif "Outline" in apply_to or "Stroke" in apply_to:
            # Apply only to stroke/outline layers
            should_apply = layer_type in ['CIMSolidStroke', 'CIMGradientStroke']
        
        # Apply color if appropriate
        if should_apply and hasattr(symbol_layer, 'color'):
            symbol_layer.color = color_dict
        
        # Handle nested marker graphics (for point symbols)
        if hasattr(symbol_layer, 'markerGraphics'):
            for graphic in symbol_layer.markerGraphics:
                if hasattr(graphic, 'symbol') and hasattr(graphic.symbol, 'symbolLayers'):
                    for nested_layer in graphic.symbol.symbolLayers:
                        self.apply_color_recursive(nested_layer, color_dict, apply_to)
    
    def apply_color_to_layer(self, layer_path, color, apply_to, messages, retry_count=0):
        """
        Apply a color to a feature layer.
        
        Args:
            layer_path: Path to the layer or layer name
            color: RGB tuple (0-255 range)
            apply_to: Which symbol layers to apply color to
            messages: ArcGIS messages object
            retry_count: Internal counter to prevent infinite recursion
        """
        if retry_count > 1:
            arcpy.AddWarning(f"  Maximum retry attempts reached. Could not apply color.")
            return
            
        try:
            # Get the current map
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            map_obj = aprx.activeMap
            
            if not map_obj:
                arcpy.AddError("No active map found. Please open a map in ArcGIS Pro.")
                return
            
            # Find the layer in the map
            layer = None
            # Extract the actual layer name from the path (last part after last backslash)
            if "\\" in layer_path:
                layer_name = layer_path.split("\\")[-1]
            elif "/" in layer_path:
                layer_name = layer_path.split("/")[-1]
            else:
                layer_name = layer_path
            
            arcpy.AddMessage(f"  Looking for layer: {layer_name}")
            
            # Try to find layer by exact name match (handles nested layers in groups)
            def find_layer_recursive(layer_list, target_name):
                """Recursively search for a layer by name, including within group layers"""
                for lyr in layer_list:
                    if lyr.name == target_name:
                        return lyr
                    # If it's a group layer, search within it
                    if lyr.isGroupLayer:
                        result = find_layer_recursive(lyr.listLayers(), target_name)
                        if result:
                            return result
                return None
            
            layer = find_layer_recursive(map_obj.listLayers(), layer_name)
            
            if not layer:
                # If layer not found in map, try to add it
                arcpy.AddMessage(f"  Layer not found in map, attempting to add: {layer_path}")
                try:
                    layer = map_obj.addDataFromPath(layer_path)
                except:
                    arcpy.AddWarning(f"  Could not add layer to map: {layer_path}")
                    return
            
            if not layer:
                arcpy.AddWarning(f"  Could not find or add layer: {layer_path}")
                return
            
            arcpy.AddMessage(f"  Found layer: {layer.name}")
            arcpy.AddMessage(f"  Is feature layer: {layer.isFeatureLayer}")
            
            # Get the layer's symbology
            if layer.isFeatureLayer:
                arcpy.AddMessage(f"  Getting CIM definition...")
                
                # Get CIM definition for more direct control
                cim_layer = layer.getDefinition('V2')
                arcpy.AddMessage(f"  CIM definition retrieved: {cim_layer is not None}")
                
                # Create color dictionary
                color_dict = {
                    'type': 'CIMRGBColor',
                    'values': [color[0], color[1], color[2], 100]
                }
                
                # Get the renderer
                if hasattr(cim_layer, 'renderer') and cim_layer.renderer:
                    arcpy.AddMessage(f"  CIM layer has renderer")
                    renderer = cim_layer.renderer
                    renderer_type = getattr(renderer, 'type', None)
                    
                    arcpy.AddMessage(f"  Renderer type: {renderer_type}")
                    
                    # If renderer type is None or not recognized, create a new CIM simple renderer
                    if not renderer_type or renderer_type == "None":
                        arcpy.AddMessage(f"  Renderer type is invalid, creating new CIM simple renderer...")
                        
                        # Use the standard symbology approach instead of CIM for broken renderers
                        try:
                            sym = layer.symbology
                            
                            # Set the color directly on symbology
                            if hasattr(sym, 'renderer') and hasattr(sym.renderer, 'symbol'):
                                # Update the symbol color
                                symbol = sym.renderer.symbol
                                
                                # For line symbols
                                if hasattr(symbol, 'color'):
                                    symbol.color = {'RGB': [color[0], color[1], color[2], 100]}
                                    sym.renderer.symbol = symbol
                                    layer.symbology = sym
                                    arcpy.AddMessage(f"  Applied color via symbology (direct)")
                                    return
                                    
                            # Fallback: use updateRenderer
                            sym.updateRenderer('SimpleRenderer')
                            
                            # Now try to set color on the new renderer
                            if hasattr(sym, 'renderer') and hasattr(sym.renderer, 'symbol'):
                                symbol = sym.renderer.symbol
                                if hasattr(symbol, 'color'):
                                    symbol.color = {'RGB': [color[0], color[1], color[2], 100]}
                                elif hasattr(symbol, 'symbolLayers'):
                                    for sl in symbol.symbolLayers:
                                        if hasattr(sl, 'color'):
                                            sl.color = {'RGB': [color[0], color[1], color[2], 100]}
                                
                                sym.renderer.symbol = symbol
                                layer.symbology = sym
                                arcpy.AddMessage(f"  Applied color via symbology (after updateRenderer)")
                                return
                            else:
                                arcpy.AddWarning(f"  Could not access symbol to set color")
                                return
                                
                        except Exception as e:
                            arcpy.AddWarning(f"  Failed to apply via symbology: {str(e)}")
                            return
                    
                    # Handle SimpleRenderer
                    if renderer_type == "CIMSimpleRenderer":
                        symbol = renderer.symbol
                        
                        # Update color using recursive method
                        if hasattr(symbol, 'symbolLayers') and symbol.symbolLayers:
                            arcpy.AddMessage(f"  Found {len(symbol.symbolLayers)} symbol layers")
                            for symbol_layer in symbol.symbolLayers:
                                layer_type = getattr(symbol_layer, 'type', 'Unknown')
                                arcpy.AddMessage(f"    Symbol layer type: {layer_type}")
                                self.apply_color_recursive(symbol_layer, color_dict, apply_to)
                            
                            # Update the symbol back to the renderer
                            renderer.symbol = symbol
                        
                        # Set the renderer back to the layer
                        cim_layer.renderer = renderer
                        
                        # Apply the CIM definition back to the layer
                        layer.setDefinition(cim_layer)
                        
                        arcpy.AddMessage(f"  Successfully applied color to {layer.name}")
                        
                    elif renderer_type == "CIMUniqueValueRenderer":
                        # Handle unique value renderer - update all groups
                        if hasattr(renderer, 'groups'):
                            for group in renderer.groups:
                                if hasattr(group, 'classes'):
                                    for cls in group.classes:
                                        if hasattr(cls, 'symbol'):
                                            symbol = cls.symbol
                                            if hasattr(symbol, 'symbolLayers') and symbol.symbolLayers:
                                                for symbol_layer in symbol.symbolLayers:
                                                    self.apply_color_recursive(symbol_layer, color_dict, apply_to)
                        
                        cim_layer.renderer = renderer
                        layer.setDefinition(cim_layer)
                        arcpy.AddMessage(f"  Successfully applied color to {layer.name}")
                    
                    else:
                        arcpy.AddWarning(f"  Unsupported renderer type: {renderer_type}")
                        return
                else:
                    arcpy.AddWarning(f"  Layer has no renderer or renderer is None")
            else:
                arcpy.AddMessage(f"  Layer is not a feature layer (type: {type(layer).__name__})")
                
        except Exception as e:
            arcpy.AddError(f"  Error applying color: {str(e)}")
            import traceback
            arcpy.AddError(traceback.format_exc())


class ColorUtils:
    """Utility functions for color manipulation"""
    
    @staticmethod
    def rgb_to_hex(rgb):
        """Convert RGB tuple to hex string"""
        return "#{:02x}{:02x}{:02x}".format(rgb[0], rgb[1], rgb[2])
    
    @staticmethod
    def get_luminance(rgb):
        """Calculate perceived luminance of a color (0-255 scale)"""
        r, g, b = rgb
        # Perceived luminance formula
        return 0.299 * r + 0.587 * g + 0.114 * b
    
    @staticmethod
    def is_too_light(rgb, threshold=200):
        """Check if color is too light"""
        return ColorUtils.get_luminance(rgb) > threshold
    
    @staticmethod
    def is_too_dark(rgb, threshold=55):
        """Check if color is too dark"""
        return ColorUtils.get_luminance(rgb) < threshold
