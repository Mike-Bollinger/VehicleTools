"""
Shapefile to REMUS 600 RMF Mission File Generator
Converts a shapefile of AUV tracklines (one polyline per dive) into individual
RMF mission files, one per feature.

Author: Mike Bollinger
Last Updated: 2026-09-10

USAGE:
    Run the script and use the Tkinter GUI to select an input shapefile and
    an output folder:
        python R620_SHP_to_RMF.py

INPUTS:
    - A polyline shapefile (WGS84 lat/lon) where each feature is one dive
      trackline, with an attribute field to use as the dive/file name.

OUTPUTS:
    One .rmf mission file per feature, saved to the chosen output folder,
    plus an in-app matplotlib preview of all tracklines.

NOTES:
    The [Objective] field layout and the trailing "#$!..." comments are
    copied verbatim from a known-good REMUS 600 RMF export so the generated
    files match the expected schema as closely as possible without access
    to the official mission-planning software. Those trailing comments
    appear to be per-field schema/checksum metadata (constant for a given
    field name) rather than a checksum of the value itself, but that
    assumption has not been verified against the real planning tool -
    validate generated files there before flying them.
"""

import re
import math
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import geopandas as gpd


class CoordinateConverter:
    """Convert decimal degrees to the RMF DMS coordinate string format."""

    @staticmethod
    def dd_to_dms(lat: float, lon: float) -> str:
        """
        Convert decimal degrees to degrees-decimal-minutes.
        (27.9101, -93.3229) -> "27N54.605  93W19.376"
        """
        lat_hem = 'N' if lat >= 0 else 'S'
        lon_hem = 'E' if lon >= 0 else 'W'

        lat_abs = abs(lat)
        lon_abs = abs(lon)

        lat_deg = int(lat_abs)
        lat_min = (lat_abs - lat_deg) * 60.0

        lon_deg = int(lon_abs)
        lon_min = (lon_abs - lon_deg) * 60.0

        return f"{lat_deg}{lat_hem}{lat_min:06.3f}  {lon_deg}{lon_hem}{lon_min:06.3f}"


class RMFMissionBuilder:
    """Builds RMF mission file text from a sequence of waypoints."""

    # Static boilerplate copied verbatim from a known-good RMF export.
    FOOTER = """
[Macros]
@label=                                                                         #$!S*BB

[Location]
type=#waypoint                                                                  #$!S#waypoint*59

[Instrument Setup:Transit]
Kraken processing enabled=YES                                                   #$!Y1*F2
Kraken ping enabled=YES                                                         #$!Y1*F2
Kraken Power=YES                                                                #$!Y1*F2
Kraken pulse interval (s)=0.4                                                   #$!F0.4,0.1,2.0*B7
Kraken HF pulse length (s)=0.01                                                 #$!F0.01,0.001,0.012*A5
Kraken LF pulse length (s)=0.01                                                 #$!F0.01,0.001,0.012*A5
Kraken gain (dB)=20                                                             #$!C020,25,27,30*F4
Kraken Include Bathy=YES                                                        #$!Y1*F2
VOYIS_Pwr power=Same                                                            #$!C0Same,Force On,Force Off*AF


[Instrument Setup:Survey]
Kraken processing enabled=YES                                                   #$!Y1*F2
Kraken ping enabled=YES                                                         #$!Y1*F2
Kraken Power=YES                                                                #$!Y1*F2
Kraken pulse interval (s)=0.4                                                   #$!F0.4,0.1,2.0*B7
Kraken HF pulse length (s)=0.01                                                 #$!F0.01,0.001,0.012*A5
Kraken LF pulse length (s)=0.01                                                 #$!F0.01,0.001,0.012*A5
Kraken gain (dB)=20                                                             #$!C020,25,27,30*F4
Kraken Include Bathy=YES                                                        #$!Y1*F2
VOYIS_Pwr power=Same                                                            #$!C0Same,Force On,Force Off*AF
"""

    def __init__(self, speed_knots: float = 3.5, altitude_m: float = 7.0,
                 min_depth_m: float = 1.5, max_depth_m: float = 600.0):
        self.speed_knots = speed_knots
        self.altitude_m = altitude_m
        self.min_depth_m = min_depth_m
        self.max_depth_m = max_depth_m

    def _depth_control(self) -> str:
        return (f"Altitude {self.altitude_m:g} meters; "
                f"Minimum depth {self.min_depth_m:g} meter; "
                f"Maximum depth {self.max_depth_m:g} meters")

    def _set_position(self, lat: float, lon: float) -> str:
        dest = CoordinateConverter.dd_to_dms(lat, lon)
        return f"""[Objective]
Type=Set Position                                                               #$!S*BB
Destination={dest}                                                #$!S*BB
Offset direction=0.0                                                            #$!F0.0,0,360*5D
Offset distance (Meters)=0.0                                                    #$!F0.0,-10000,10000*A3
Offset Y axis (Meters)=0.0                                                      #$!F0,-10000,10000*45
Allow RECON control=NO                                                          #$!Y0*F1
"""

    def _wait_run(self, lat: float, lon: float) -> str:
        pos = CoordinateConverter.dd_to_dms(lat, lon)
        return f"""[Objective]
Type=Wait Run                                                                   #$!S*BB
Verify range to nearest transponder=YES                                         #$!Y1*F2
Auto calibrate depth sensor=Yes                                                 #$!Y0*F1
Symbol Position on Chart=  {pos}
"""

    def _navigate(self, lat: float, lon: float) -> str:
        dest = CoordinateConverter.dd_to_dms(lat, lon)
        return f"""[Objective]
Type=Navigate                                                                   #$!S*BB
Destination={dest}                                                #$!S*BB
Offset direction=0.0                                                            #$!F0.0,0,360*5D
Offset distance (Meters)=0.0                                                    #$!F0.0,-10000,10000*A3
Offset Y axis (Meters)=0.0                                                      #$!F0,-10000,10000*45
Minimum range (M.)=10
Timeout (seconds)=AUTO                                                          #$!SAUTO*F4
Follow trackline?=Yes                                                           #$!Y1*F2
Speed={self.speed_knots:g} knots                                                                 #$!SSame*41
Depth control={self._depth_control()} #$!S*BB
Instrument setup name=SURVEY                                                    #$!S*BB
Navigation method=Dead Reckon                                                   #$!C1Best method (Any),Dead Reckon,Long baseline,GPS Only,No GPS (no surfacing),Range Only*B5
Get GPS fix before completing=NO                                                #$!Y0*F1
Allow RECON control=NO                                                          #$!Y0*F1
Max end zone speed=4.0 KNOTS                                                    #$!S4.0 KNOTS*FC
End zone distance(m)=30                                                         #$!F30,0,100*2A
"""

    def _surface(self, lat: float, lon: float) -> str:
        pos = CoordinateConverter.dd_to_dms(lat, lon)
        return f"""[Objective]
Type=Surface                                                                    #$!S*BB
Speed=4.0 knots                                                                 #$!SSame*41
Fast surface=NO                                                                 #$!Y1*F2
Symbol Position on Chart=  {pos}
Allow RECON control=NO                                                          #$!Y0*F1
"""

    def _get_gps_fix(self, lat: float, lon: float) -> str:
        pos = CoordinateConverter.dd_to_dms(lat, lon)
        return f"""[Objective]
Type=Get gps fix                                                                #$!S*BB
Max minutes to try=10.0                                                         #$!F10.0,3,60*5E
Symbol Position on Chart=  {pos}
Allow RECON control=NO                                                          #$!Y0*F1
"""

    def build(self, vertices: list) -> str:
        """
        Build full RMF mission text from a list of (lon, lat) vertices
        (shapely coordinate order).
        """
        if len(vertices) < 2:
            raise ValueError("A dive trackline needs at least 2 vertices")

        first_lon, first_lat = vertices[0]
        last_lon, last_lat = vertices[-1]

        blocks = [
            self._set_position(first_lat, first_lon),
            self._wait_run(first_lat, first_lon),
        ]
        for lon, lat in vertices[1:]:
            blocks.append(self._navigate(lat, lon))
        blocks.append(self._surface(last_lat, last_lon))
        blocks.append(self._get_gps_fix(last_lat, last_lon))

        return "\n".join(blocks) + self.FOOTER


def sanitize_filename(name: str) -> str:
    return re.sub(r'[^\w\-]', '_', str(name).strip())


class SHPToRMFGUI:
    """GUI for shapefile-to-RMF conversion."""

    def __init__(self, root):
        self.root = root
        self.root.title("Shapefile to REMUS 600 RMF Generator")
        self.root.geometry("1200x800")

        self.gdf = None
        self.name_field = tk.StringVar()

        self._create_widgets()

    def _create_widgets(self):
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(control_frame, text="Trackline Shapefile:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.file_entry = ttk.Entry(control_frame, width=60)
        self.file_entry.grid(row=0, column=1, padx=5)
        ttk.Button(control_frame, text="Browse", command=self._browse_file).grid(row=0, column=2, padx=5)
        ttk.Button(control_frame, text="Load & Plot", command=self._load_and_plot).grid(row=0, column=3, padx=5)

        ttk.Label(control_frame, text="Dive Name Field:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.name_field_combo = ttk.Combobox(control_frame, textvariable=self.name_field, width=20, state="readonly")
        self.name_field_combo.grid(row=1, column=1, sticky=tk.W, padx=5)

        params_frame = ttk.LabelFrame(control_frame, text="Mission Defaults", padding="5")
        params_frame.grid(row=2, column=0, columnspan=4, sticky=tk.EW, pady=5)

        ttk.Label(params_frame, text="Speed (knots):").grid(row=0, column=0, padx=5)
        self.speed_entry = ttk.Entry(params_frame, width=10)
        self.speed_entry.insert(0, "3.5")
        self.speed_entry.grid(row=0, column=1, padx=5)

        ttk.Label(params_frame, text="Altitude (m):").grid(row=0, column=2, padx=5)
        self.altitude_entry = ttk.Entry(params_frame, width=10)
        self.altitude_entry.insert(0, "7")
        self.altitude_entry.grid(row=0, column=3, padx=5)

        ttk.Label(params_frame, text="Min Depth (m):").grid(row=0, column=4, padx=5)
        self.min_depth_entry = ttk.Entry(params_frame, width=10)
        self.min_depth_entry.insert(0, "1.5")
        self.min_depth_entry.grid(row=0, column=5, padx=5)

        ttk.Label(params_frame, text="Max Depth (m):").grid(row=0, column=6, padx=5)
        self.max_depth_entry = ttk.Entry(params_frame, width=10)
        self.max_depth_entry.insert(0, "600")
        self.max_depth_entry.grid(row=0, column=7, padx=5)

        ttk.Label(control_frame, text="Output Directory:").grid(row=3, column=0, sticky=tk.W, padx=5)
        self.output_entry = ttk.Entry(control_frame, width=60)
        self.output_entry.grid(row=3, column=1, padx=5)
        ttk.Button(control_frame, text="Browse", command=self._browse_output).grid(row=3, column=2, padx=5)
        ttk.Button(control_frame, text="Export All RMF Files", command=self._export_all).grid(row=3, column=3, padx=5)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(control_frame, textvariable=self.status_var, relief=tk.SUNKEN).grid(
            row=4, column=0, columnspan=4, sticky=tk.EW, pady=5)

        plot_frame = ttk.Frame(self.root)
        plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.fig = Figure(figsize=(12, 8))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.ax.set_title("Load a shapefile to view tracklines")
        self.ax.set_xlabel("Longitude")
        self.ax.set_ylabel("Latitude")
        self.ax.grid(True, alpha=0.3)
        self.canvas.draw()

    def _browse_file(self):
        filename = filedialog.askopenfilename(
            title="Select Trackline Shapefile",
            filetypes=[("Shapefiles", "*.shp"), ("All files", "*.*")]
        )
        if filename:
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, filename)

    def _browse_output(self):
        directory = filedialog.askdirectory(title="Select Output Directory")
        if directory:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, directory)

    def _load_and_plot(self):
        shp_file = self.file_entry.get()
        if not shp_file or not Path(shp_file).exists():
            messagebox.showerror("Error", "Please select a valid shapefile")
            return

        try:
            self.status_var.set("Loading shapefile...")
            self.root.update()

            gdf = gpd.read_file(shp_file)
            if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)
            self.gdf = gdf

            fields = [c for c in gdf.columns if c != 'geometry']
            self.name_field_combo['values'] = fields
            if fields:
                default_field = 'ID' if 'ID' in fields else fields[0]
                self.name_field.set(default_field)

            self._plot_tracklines()
            self.status_var.set(f"Loaded {len(gdf)} tracklines from {Path(shp_file).name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load shapefile:\n{str(e)}")
            self.status_var.set("Error")

    def _plot_tracklines(self):
        self.ax.clear()
        name_field = self.name_field.get() or None

        for _, row in self.gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.geom_type != 'LineString':
                continue
            lons, lats = zip(*geom.coords)
            self.ax.plot(lons, lats, marker='o', markersize=3, linewidth=1.5)
            label = row[name_field] if name_field else ""
            self.ax.annotate(str(label), xy=(lons[0], lats[0]), xytext=(5, 5),
                              textcoords='offset points', fontsize=8, fontweight='bold')

        self.ax.set_xlabel("Longitude (degrees)")
        self.ax.set_ylabel("Latitude (degrees)")
        self.ax.set_title(f"Tracklines - {len(self.gdf)} Dives")
        self.ax.grid(True, alpha=0.3)
        self.ax.set_aspect('equal', adjustable='datalim')
        self.canvas.draw()

    def _export_all(self):
        if self.gdf is None:
            messagebox.showerror("Error", "Load a shapefile first")
            return

        output_dir = self.output_entry.get()
        if not output_dir or not Path(output_dir).exists():
            messagebox.showerror("Error", "Please select a valid output directory")
            return

        name_field = self.name_field.get()
        if not name_field:
            messagebox.showerror("Error", "Please select a dive name field")
            return

        try:
            speed = float(self.speed_entry.get())
            altitude = float(self.altitude_entry.get())
            min_depth = float(self.min_depth_entry.get())
            max_depth = float(self.max_depth_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Mission defaults must be numeric")
            return

        builder = RMFMissionBuilder(speed_knots=speed, altitude_m=altitude,
                                     min_depth_m=min_depth, max_depth_m=max_depth)

        written = []
        errors = []
        for idx, row in self.gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.geom_type != 'LineString':
                errors.append(f"Row {idx}: not a LineString, skipped")
                continue

            dive_name = sanitize_filename(row[name_field])
            try:
                mission_text = builder.build(list(geom.coords))
                out_path = Path(output_dir) / f"{dive_name}_mission.rmf"
                out_path.write_text(mission_text, encoding='utf-8')
                written.append(out_path.name)
            except Exception as e:
                errors.append(f"{dive_name}: {e}")

        summary = f"Wrote {len(written)} RMF file(s) to {output_dir}"
        if errors:
            summary += "\n\nErrors:\n" + "\n".join(errors)
        messagebox.showinfo("Export Complete", summary)
        self.status_var.set(f"Exported {len(written)} of {len(self.gdf)} dives")


def main():
    root = tk.Tk()
    app = SHPToRMFGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
