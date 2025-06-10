"""
Dive Layout Automator - ArcGIS Pro Toolbox
Automates the creation of dive maps with interactive extent control
"""

import arcpy
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox

class Toolbox(object):
    def __init__(self):
        self.label = "Dive Layout Automator"
        self.alias = "DiveLayoutAutomator"
        self.tools = [DiveLayoutTool]

class DiveLayoutTool(object):
    def __init__(self):
        self.label = "Interactive Dive Layout Generator"
        self.description = "Generate maps for dive layers with interactive extent control"
        self.canRunInBackground = False
        
    def getParameterInfo(self):
        """Define tool parameters"""
        
        # Layout parameter
        layout_param = arcpy.Parameter(
            displayName="Layout",
            name="layout",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )
        layout_param.filter.type = "ValueList"
        
        # Layer groups parameter
        groups_param = arcpy.Parameter(
            displayName="Layer Groups (containing dive layers)",
            name="layer_groups", 
            datatype="GPString",
            parameterType="Required",
            direction="Input",
            multiValue=True
        )
        groups_param.filter.type = "ValueList"
        
        # Output folder parameter
        output_param = arcpy.Parameter(
            displayName="Output Folder",
            name="output_folder",
            datatype="DEFolder", 
            parameterType="Required",
            direction="Input"
        )
        
        # DPI parameter
        dpi_param = arcpy.Parameter(
            displayName="Export DPI",
            name="dpi",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input"
        )
        dpi_param.value = 300
        
        return [layout_param, groups_param, output_param, dpi_param]
    
    def isLicensed(self):
        """Check if tool is licensed to execute"""
        return True
    
    def updateParameters(self, parameters):
        """Update parameter values and properties"""
        try:
            # Get current project
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            
            # Update layout choices
            layouts = [layout.name for layout in aprx.listLayouts()]
            parameters[0].filter.list = layouts
            
            # Update layer group choices
            group_choices = []
            for map_obj in aprx.listMaps():
                for layer in map_obj.listLayers():
                    if hasattr(layer, 'isGroupLayer') and layer.isGroupLayer:
                        group_choices.append(f"{map_obj.name}:{layer.name}")
            
            parameters[1].filter.list = group_choices
            
        except Exception as e:
            arcpy.AddWarning(f"Could not update parameters: {str(e)}")
        
        return
    
    def updateMessages(self, parameters):
        """Update messages for parameters"""
        return
    
    def execute(self, parameters, messages):
        """Execute the tool"""
        try:
            # Get parameters
            layout_name = parameters[0].valueAsText
            
            # Fix the parameter parsing for multiValue groups
            if parameters[1].valueAsText:
                # Handle both single and multiple selections
                raw_groups = parameters[1].valueAsText
                # Remove quotes and split properly
                raw_groups = raw_groups.replace("'", "").replace('"', '')
                selected_groups = [group.strip() for group in raw_groups.split(';') if group.strip()]
            else:
                selected_groups = []
                
            output_folder = parameters[2].valueAsText
            dpi = parameters[3].value if parameters[3].value else 300
            
            arcpy.AddMessage(f"Starting dive layout automation...")
            arcpy.AddMessage(f"Layout: {layout_name}")
            arcpy.AddMessage(f"Groups: {len(selected_groups)} selected")
            
            # Debug: Show the cleaned group names
            arcpy.AddMessage("Selected groups:")
            for i, group in enumerate(selected_groups):
                arcpy.AddMessage(f"  {i+1}. '{group}'")
            
            arcpy.AddMessage(f"Output: {output_folder}")
            
            # Initialize the processor
            processor = DiveLayoutProcessor(layout_name, selected_groups, output_folder, dpi)
            
            # Run the interactive process
            processor.run_interactive_process()
            
        except Exception as e:
            arcpy.AddError(f"Tool execution failed: {str(e)}")
            import traceback
            arcpy.AddError(traceback.format_exc())

class DiveLayoutProcessor:
    """Main processor for dive layout automation"""
    
    def __init__(self, layout_name, selected_groups, output_folder, dpi):
        self.layout_name = layout_name
        self.selected_groups = selected_groups
        self.output_folder = output_folder
        self.dpi = dpi
        self.aprx = arcpy.mp.ArcGISProject("CURRENT")
        self.dive_pattern = re.compile(r'DIVE(\d+)', re.IGNORECASE)
        
        # Create output folder
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
    
    def find_dive_numbers(self):
        """Find all dive numbers in selected layer groups"""
        dive_numbers = set()
        
        arcpy.AddMessage(f"Analyzing {len(self.selected_groups)} selected groups for dive layers...")
        
        # First, let's see what maps are available
        available_maps = [m.name for m in self.aprx.listMaps()]
        arcpy.AddMessage(f"Available maps in project: {available_maps}")
        
        for group_key in self.selected_groups:
            try:
                # Debug the splitting
                arcpy.AddMessage(f"Processing group_key: '{group_key}'")
                
                if ':' not in group_key:
                    arcpy.AddWarning(f"Invalid group format (expected 'Map:Group'): '{group_key}'")
                    continue
                    
                map_name, group_name = group_key.split(':', 1)
                arcpy.AddMessage(f"Parsed - Map: '{map_name}', Group: '{group_name}'")
                
                # Get map
                map_obj = None
                for m in self.aprx.listMaps():
                    arcpy.AddMessage(f"Checking map: '{m.name}' against '{map_name}'")
                    if m.name == map_name:
                        map_obj = m
                        break
                
                if not map_obj:
                    arcpy.AddWarning(f"Map '{map_name}' not found")
                    arcpy.AddWarning(f"Available maps: {[m.name for m in self.aprx.listMaps()]}")
                    continue
                
                arcpy.AddMessage(f"Found map: '{map_obj.name}'")
                
                # Get group layer
                group_layer = None
                available_groups = []
                for layer in map_obj.listLayers():
                    available_groups.append(layer.name)
                    if layer.name == group_name:
                        group_layer = layer
                        break
                
                if not group_layer:
                    arcpy.AddWarning(f"Group layer '{group_name}' not found in map '{map_name}'")
                    arcpy.AddWarning(f"Available groups in '{map_name}': {available_groups}")
                    continue
                
                arcpy.AddMessage(f"Found group layer: '{group_layer.name}'")
                
                # Find dive layers - let's be more flexible with the pattern
                layers_in_group = list(group_layer.listLayers())
                arcpy.AddMessage(f"Found {len(layers_in_group)} layers in group '{group_name}':")
                
                for layer in layers_in_group:
                    arcpy.AddMessage(f"  - {layer.name}")
                    
                    # Try multiple dive patterns
                    patterns_to_try = [
                        r'DIVE(\d+)',           # DIVE001, DIVE002, etc.
                        r'Dive(\d+)',           # Dive001, Dive002, etc.
                        r'dive(\d+)',           # dive001, dive002, etc.
                        r'D(\d+)',              # D001, D002, etc.
                        r'(\d+)',               # Just numbers: 001, 002, etc.
                    ]
                    
                    found_match = False
                    for pattern in patterns_to_try:
                        match = re.search(pattern, layer.name, re.IGNORECASE)
                        if match:
                            dive_num = int(match.group(1))
                            dive_numbers.add(dive_num)
                            arcpy.AddMessage(f"    ✓ Found dive number: {dive_num} (pattern: {pattern})")
                            found_match = True
                            break
                    
                    if not found_match:
                        arcpy.AddMessage(f"    - No dive pattern found in: {layer.name}")
            
            except Exception as e:
                arcpy.AddError(f"Error processing group '{group_key}': {str(e)}")
                import traceback
                arcpy.AddError(traceback.format_exc())
    
        if dive_numbers:
            sorted_dives = sorted(dive_numbers)
            arcpy.AddMessage(f"\nTotal dive numbers found: {sorted_dives}")
            return sorted_dives
        else:
            arcpy.AddWarning("No dive layers found. Please check:")
            arcpy.AddWarning("1. Layer names contain dive numbers (e.g., DIVE001, Dive1, D001)")
            arcpy.AddWarning("2. Selected groups contain the correct layers")
            arcpy.AddWarning("3. Layer names are spelled correctly")
            return []

    def set_dive_visibility(self, dive_number):
        """Set layer visibility for a specific dive"""
        dive_patterns = [
            f"DIVE{dive_number:03d}",  # DIVE001
            f"Dive{dive_number:03d}",  # Dive001
            f"dive{dive_number:03d}",  # dive001
            f"D{dive_number:03d}",     # D001
            f"DIVE{dive_number}",      # DIVE1
            f"Dive{dive_number}",      # Dive1
            f"dive{dive_number}",      # dive1
            f"D{dive_number}",         # D1
            f"{dive_number:03d}",      # 001
            f"{dive_number}",          # 1
        ]
        
        arcpy.AddMessage(f"Setting visibility for dive {dive_number}...")
        
        for group_key in self.selected_groups:
            map_name, group_name = group_key.split(':', 1)
            
            # Get map and group
            map_obj = None
            for m in self.aprx.listMaps():
                if m.name == map_name:
                    map_obj = m
                    break
            
            if not map_obj:
                continue
            
            group_layer = None
            for layer in map_obj.listLayers():
                if layer.name == group_name:
                    group_layer = layer
                    break
            
            if not group_layer:
                continue
            
            # Set visibility for all layers in group
            for layer in group_layer.listLayers():
                layer_name_upper = layer.name.upper()
                
                # Check if this layer matches any dive pattern
                is_dive_layer = False
                matches_current_dive = False
                
                # Check against all possible dive patterns
                for pattern in [r'DIVE(\d+)', r'D(\d+)', r'(\d+)']:
                    match = re.search(pattern, layer.name, re.IGNORECASE)
                    if match:
                        is_dive_layer = True
                        layer_dive_num = int(match.group(1))
                        if layer_dive_num == dive_number:
                            matches_current_dive = True
                        break
                
                if is_dive_layer:
                    if matches_current_dive:
                        layer.visible = True
                        arcpy.AddMessage(f"  ✓ Showing: {layer.name}")
                    else:
                        layer.visible = False
                        arcpy.AddMessage(f"  - Hiding: {layer.name}")
                else:
                    # Non-dive layer - leave as is
                    arcpy.AddMessage(f"  → Keeping: {layer.name} (not a dive layer)")
    
    def export_current_layout(self, dive_number):
        """Export the current layout state"""
        dive_id = f"DIVE{dive_number:03d}"
        output_file = os.path.join(self.output_folder, f"{dive_id}.jpg")
        
        # Get layout
        layout = None
        for l in self.aprx.listLayouts():
            if l.name == self.layout_name:
                layout = l
                break
        
        if not layout:
            raise Exception(f"Layout '{self.layout_name}' not found")
        
        # Export
        layout.exportToJPEG(output_file, resolution=self.dpi, jpeg_quality=95)
        arcpy.AddMessage(f"  Exported: {output_file}")
        
        return output_file
    
    def run_interactive_process(self):
        """Run the interactive process with GUI"""
        # Find all dives
        dive_numbers = self.find_dive_numbers()
        
        if not dive_numbers:
            arcpy.AddWarning("No dive layers found in selected groups")
            return
        
        arcpy.AddMessage(f"Found {len(dive_numbers)} dives: {dive_numbers}")
        
        # Create and run the interactive GUI
        gui = InteractiveExtentGUI(self, dive_numbers)
        gui.run()

class InteractiveExtentGUI:
    """Simple GUI for interactive extent control"""
    
    def __init__(self, processor, dive_numbers):
        self.processor = processor
        self.dive_numbers = dive_numbers
        self.current_index = 0
        self.completed_dives = []
        
    def run(self):
        """Run the interactive GUI"""
        self.root = tk.Tk()
        self.root.title("Dive Layout Automator - Interactive Mode")
        self.root.geometry("500x400")
        self.root.attributes('-topmost', True)  # Keep on top
        
        # Make window modal
        self.root.grab_set()
        
        self.create_widgets()
        self.load_current_dive()
        
        # Center the window
        self.root.geometry("+%d+%d" % (
            (self.root.winfo_screenwidth() / 2) - 250,
            (self.root.winfo_screenheight() / 2) - 200
        ))
        
        self.root.mainloop()
    
    def create_widgets(self):
        """Create GUI widgets"""
        # Title
        title_frame = ttk.Frame(self.root)
        title_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(title_frame, text="Interactive Dive Layout Generator", 
                 font=("Arial", 14, "bold")).pack()
        
        # Current dive info
        info_frame = ttk.LabelFrame(self.root, text="Current Dive", padding="10")
        info_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.dive_label = ttk.Label(info_frame, text="", font=("Arial", 12, "bold"))
        self.dive_label.pack()
        
        self.progress_label = ttk.Label(info_frame, text="")
        self.progress_label.pack()
        
        # Instructions
        instructions_frame = ttk.LabelFrame(self.root, text="Instructions", padding="10")
        instructions_frame.pack(fill=tk.X, padx=20, pady=10)
        
        instructions = """1. The layers for the current dive are now visible in ArcPro
2. Use ArcPro's navigation tools to set the desired map extent
3. Click 'Export & Next' when you're satisfied with the extent
4. Repeat for each dive"""
        
        ttk.Label(instructions_frame, text=instructions, justify=tk.LEFT).pack()
        
        # Status
        self.status_label = ttk.Label(self.root, text="Ready to start...", 
                                     foreground="blue")
        self.status_label.pack(pady=10)
        
        # Buttons
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=20, pady=20)
        
        self.export_button = ttk.Button(button_frame, text="Export & Next Dive", 
                                       command=self.export_and_next,
                                       style="Accent.TButton")
        self.export_button.pack(side=tk.RIGHT, padx=5)
        
        self.skip_button = ttk.Button(button_frame, text="Skip This Dive", 
                                     command=self.skip_dive)
        self.skip_button.pack(side=tk.RIGHT, padx=5)
        
        self.cancel_button = ttk.Button(button_frame, text="Cancel", 
                                       command=self.cancel)
        self.cancel_button.pack(side=tk.LEFT, padx=5)
        
        # Results
        results_frame = ttk.LabelFrame(self.root, text="Completed", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        self.results_listbox = tk.Listbox(results_frame)
        self.results_listbox.pack(fill=tk.BOTH, expand=True)
    
    def load_current_dive(self):
        """Load the current dive"""
        if self.current_index >= len(self.dive_numbers):
            self.complete_process()
            return
        
        current_dive = self.dive_numbers[self.current_index]
        dive_id = f"DIVE{current_dive:03d}"
        
        # Update GUI
        self.dive_label.config(text=f"Current: {dive_id}")
        self.progress_label.config(text=f"Dive {self.current_index + 1} of {len(self.dive_numbers)}")
        
        progress_pct = int(((self.current_index + 1) / len(self.dive_numbers)) * 100)
        self.status_label.config(text=f"Set extent for {dive_id} in ArcPro, then click 'Export & Next' ({progress_pct}% complete)")
        
        # Set layer visibility
        try:
            arcpy.AddMessage(f"\nLoading {dive_id}...")
            self.processor.set_dive_visibility(current_dive)
            arcpy.AddMessage(f"Layers updated for {dive_id}")
            
        except Exception as e:
            arcpy.AddError(f"Error loading {dive_id}: {str(e)}")
            messagebox.showerror("Error", f"Error loading {dive_id}: {str(e)}")
    
    def export_and_next(self):
        """Export current dive and move to next"""
        if self.current_index >= len(self.dive_numbers):
            return
        
        current_dive = self.dive_numbers[self.current_index]
        dive_id = f"DIVE{current_dive:03d}"
        
        try:
            # Export the layout
            self.status_label.config(text=f"Exporting {dive_id}...", foreground="orange")
            self.root.update()
            
            output_file = self.processor.export_current_layout(current_dive)
            
            # Add to completed list
            self.completed_dives.append(current_dive)
            self.results_listbox.insert(tk.END, f"{dive_id} ✓")
            
            arcpy.AddMessage(f"Successfully exported {dive_id}")
            
            # Move to next
            self.current_index += 1
            self.load_current_dive()
            
        except Exception as e:
            arcpy.AddError(f"Error exporting {dive_id}: {str(e)}")
            messagebox.showerror("Error", f"Error exporting {dive_id}: {str(e)}")
            self.status_label.config(text=f"Error exporting {dive_id}", foreground="red")
    
    def skip_dive(self):
        """Skip the current dive"""
        if self.current_index >= len(self.dive_numbers):
            return
        
        current_dive = self.dive_numbers[self.current_index]
        dive_id = f"DIVE{current_dive:03d}"
        
        self.results_listbox.insert(tk.END, f"{dive_id} (skipped)")
        arcpy.AddMessage(f"Skipped {dive_id}")
        
        self.current_index += 1
        self.load_current_dive()
    
    def complete_process(self):
        """Complete the process"""
        self.status_label.config(text="All dives completed!", foreground="green")
        self.export_button.config(state=tk.DISABLED)
        self.skip_button.config(state=tk.DISABLED)
        self.cancel_button.config(text="Close")
        
        arcpy.AddMessage(f"\nProcess completed! Exported {len(self.completed_dives)} dives")
        arcpy.AddMessage(f"Output folder: {self.processor.output_folder}")
        
        messagebox.showinfo("Complete", 
                           f"Process completed!\n\n"
                           f"Exported: {len(self.completed_dives)} dives\n"
                           f"Output: {self.processor.output_folder}")
    
    def cancel(self):
        """Cancel the process"""
        if self.completed_dives:
            if not messagebox.askyesno("Cancel", 
                                      f"You have completed {len(self.completed_dives)} dives.\n\n"
                                      "Do you want to cancel the process?"):
                return
        
        arcpy.AddMessage("Process cancelled by user")
        self.root.destroy()