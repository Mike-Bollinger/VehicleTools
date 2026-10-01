"""GUI tool for creating bathymetric raster derivatives with ArcPy.

================================================================================
Author:         Mike Bollinger
Last Updated:   September 10, 2026

FUNCTION:
    Opens a Tkinter GUI where a user selects one input bathymetric raster
    (e.g. BAG or GeoTIFF), chooses which derivative surfaces to generate
    (slope, aspect, curvature, hillshade, etc.), edits per-derivative options,
    and selects an output folder or file geodatabase. This script intentionally
    does not mosaic or standardize source rasters.

USAGE:
    Run with the ArcGIS Pro Python environment so Spatial Analyst tools are
    available:
        "C:\\Program Files\\ArcGIS\\Pro\\bin\\Python\\envs\\arcgispro-py3\\python.exe" Bathy_Derivatives_GUI.py
    Select the input raster and derivatives in the GUI, then run.

INPUTS:
    - Input raster (required): path to a single BAG or GeoTIFF bathymetric
      raster, selected via file dialog.
    - Derivative selections and per-derivative options (e.g. neighborhood
      distance/type, z-unit, slope measurement), set in the GUI.
    - Output folder or file geodatabase (required): destination for the
      generated derivative rasters.

OUTPUTS:
    One raster per selected derivative (e.g. slope, aspect, curvature) saved
    to the chosen output workspace, plus a raster footprint shapefile and a
    progress log displayed in the GUI.
================================================================================
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Callable

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


SURFACE_PARAMETER_DEFAULTS = {
    "local_surface_type": "QUADRATIC",
    "neighborhood_distance": "3 Meters",
    "adaptive_neighborhood": "FIXED_NEIGHBORHOOD",
    "z_unit": "METER",
    "slope_measurement": "DEGREE",
    "project_geodesic_azimuths": "GEODESIC_AZIMUTHS",
    "equatorial_aspect": "NORTH_POLE_ASPECT",
}


@dataclass
class DerivativeConfig:
    label: str
    output_name: str
    selected: tk.BooleanVar
    options: dict[str, tk.Variable] = field(default_factory=dict)


def load_arcpy():
    import arcpy  # pyright: ignore[reportMissingImports]
    from arcpy.sa import FocalStatistics, NbrCircle, NbrRectangle  # pyright: ignore[reportMissingImports]

    arcpy.CheckOutExtension("Spatial")
    return arcpy, FocalStatistics, NbrCircle, NbrRectangle


def sanitize_name(name: str) -> str:
    cleaned = "".join(character if character.isalnum() or character == "_" else "_" for character in name.strip())
    return cleaned.strip("_") or "output"


def sanitize_filename(name: str, default_extension: str) -> str:
    base_name = os.path.basename(name.strip())
    stem, extension = os.path.splitext(base_name)
    clean_stem = sanitize_name(stem)
    clean_extension = extension if extension else default_extension
    return f"{clean_stem}{clean_extension}"


def output_path(output_workspace: str, output_name: str) -> str:
    name = sanitize_name(output_name)
    if output_workspace.lower().endswith(".gdb"):
        return os.path.join(output_workspace, name)

    if not os.path.splitext(name)[1]:
        name = f"{name}.tif"
    return os.path.join(output_workspace, name)


def save_raster(raster, path: str, log: Callable[[str], None]) -> str:
    log(f"Saving {path}")
    raster.save(path)
    return path


def shapefile_workspace(output_workspace: str) -> str:
    if output_workspace.lower().endswith(".gdb"):
        workspace_parent = os.path.dirname(output_workspace.rstrip(os.sep))
        workspace_name = os.path.splitext(os.path.basename(output_workspace))[0]
        return os.path.join(workspace_parent, f"{workspace_name}_Derivative_Shapefiles")
    return output_workspace


def shapefile_path(output_workspace: str, output_name: str) -> str:
    return os.path.join(shapefile_workspace(output_workspace), f"{sanitize_name(output_name)}_footprint.shp")


def create_raster_footprint(arcpy, raster_path: str, output_workspace: str, output_name: str, log: Callable[[str], None]) -> str:
    output_folder = shapefile_workspace(output_workspace)
    os.makedirs(output_folder, exist_ok=True)
    footprint_path = shapefile_path(output_workspace, output_name)
    log(f"Creating raster footprint shapefile {footprint_path}")
    arcpy.management.RasterDomain(raster_path, footprint_path, "POLYGON")
    return footprint_path


def validate_input_raster(arcpy, input_raster: str, log: Callable[[str], None]) -> None:
    if not arcpy.Exists(input_raster) and not os.path.exists(input_raster):
        raise FileNotFoundError(f"Input raster was not found: {input_raster}")

    try:
        description = arcpy.Describe(input_raster)
        data_type = getattr(description, "dataType", "unknown")
        band_count = getattr(description, "bandCount", "unknown")
        spatial_reference = getattr(description, "spatialReference", None)
        spatial_reference_name = getattr(spatial_reference, "name", "unknown")
    except Exception as exc:
        raise RuntimeError(f"ArcPy could not read the selected raster. BAG and GeoTIFF inputs must be readable by ArcGIS Pro. {exc}") from exc

    log(f"Input data type: {data_type}")
    log(f"Input band count: {band_count}")
    log(f"Input spatial reference: {spatial_reference_name}")


def surface_parameters(arcpy, input_raster: str, parameter_type: str, options: dict[str, str]):
    if hasattr(arcpy.sa, "SurfaceParameters"):
        return arcpy.sa.SurfaceParameters(
            input_raster,
            parameter_type,
            options["local_surface_type"],
            options["neighborhood_distance"],
            options["adaptive_neighborhood"],
            options["z_unit"],
            options.get("slope_measurement", "DEGREE"),
            options.get("project_geodesic_azimuths", "GEODESIC_AZIMUTHS"),
            options.get("equatorial_aspect", "NORTH_POLE_ASPECT"),
        )

    if parameter_type == "SLOPE":
        return arcpy.sa.Slope(input_raster, options.get("slope_measurement", "DEGREE"), "1", "PLANAR", options["z_unit"])
    if parameter_type == "ASPECT":
        return arcpy.sa.Aspect(input_raster, "PLANAR", options["z_unit"])

    raise RuntimeError("Surface Parameters is not available in this ArcPy environment.")


def make_curvature(
    arcpy,
    input_raster: str,
    output_workspace: str,
    profile_options: dict[str, str],
    planform_options: dict[str, str],
    log: Callable[[str], None],
) -> tuple[str, str]:
    profile_curvature = output_path(output_workspace, profile_options["output_name"])
    planform_curvature = output_path(output_workspace, planform_options["output_name"])
    if hasattr(arcpy.sa, "SurfaceParameters"):
        log("Creating profile curvature with Surface Parameters")
        profile_raster = surface_parameters(arcpy, input_raster, "PROFILE_CURVATURE", profile_options)
        save_raster(profile_raster, profile_curvature, log)
        log("Creating plan curvature with Surface Parameters")
        planform_raster = surface_parameters(arcpy, input_raster, "CONTOUR_CURVATURE", planform_options)
        save_raster(planform_raster, planform_curvature, log)
        return profile_curvature, planform_curvature

    base_curvature = output_path(output_workspace, "curvature")
    log("Surface Parameters is not available; creating curvature rasters with Curvature")
    arcpy.gp.Curvature_sa(input_raster, base_curvature, profile_options.get("z_factor", "1"), profile_curvature, planform_curvature)
    return profile_curvature, planform_curvature


def create_footprint_if_requested(
    arcpy,
    raster_path: str,
    output_workspace: str,
    output_name: str,
    create_shapefiles: bool,
    footprint_outputs: list[str],
    log: Callable[[str], None],
) -> None:
    if create_shapefiles:
        footprint_outputs.append(create_raster_footprint(arcpy, raster_path, output_workspace, output_name, log))


def run_derivative_job(job: dict, log: Callable[[str], None]) -> None:
    start = time.time()
    created_outputs: list[str] = []
    generated_for_pca: list[str] = []
    footprint_outputs: list[str] = []
    selected = job["selected"]
    options_by_key = job["options"]
    input_raster = job["input_raster"]
    output_workspace = job["output_workspace"]
    create_shapefiles = job["create_shapefiles"]

    arcpy, FocalStatistics, NbrCircle, NbrRectangle = load_arcpy()
    arcpy.env.overwriteOutput = job["overwrite_output"]
    arcpy.env.workspace = output_workspace

    log("Starting derivative job")
    log(f"Input raster: {input_raster}")
    log(f"Output workspace: {output_workspace}")
    validate_input_raster(arcpy, input_raster, log)

    if selected.get("slope"):
        options = options_by_key["slope"]
        log("Creating slope")
        raster = surface_parameters(arcpy, input_raster, "SLOPE", options)
        path = save_raster(raster, output_path(output_workspace, options["output_name"]), log)
        created_outputs.append(path)
        generated_for_pca.append(path)
        create_footprint_if_requested(arcpy, path, output_workspace, options["output_name"], create_shapefiles, footprint_outputs, log)

    if selected.get("aspect"):
        options = options_by_key["aspect"]
        log("Creating aspect")
        raster = surface_parameters(arcpy, input_raster, "ASPECT", options)
        path = save_raster(raster, output_path(output_workspace, options["output_name"]), log)
        created_outputs.append(path)
        generated_for_pca.append(path)
        create_footprint_if_requested(arcpy, path, output_workspace, options["output_name"], create_shapefiles, footprint_outputs, log)

    profile_selected = selected.get("profile_curvature", False)
    planform_selected = selected.get("planform_curvature", False)
    if profile_selected or planform_selected:
        curvature_cache = make_curvature(
            arcpy,
            input_raster,
            output_workspace,
            options_by_key["profile_curvature"],
            options_by_key["planform_curvature"],
            log,
        )
        if profile_selected:
            profile_path = curvature_cache[0]
            created_outputs.append(profile_path)
            generated_for_pca.append(profile_path)
            profile_name = options_by_key["profile_curvature"]["output_name"]
            create_footprint_if_requested(arcpy, profile_path, output_workspace, profile_name, create_shapefiles, footprint_outputs, log)
            log(f"Profile curvature saved to {profile_path}")
        if planform_selected:
            planform_path = curvature_cache[1]
            created_outputs.append(planform_path)
            generated_for_pca.append(planform_path)
            planform_name = options_by_key["planform_curvature"]["output_name"]
            create_footprint_if_requested(arcpy, planform_path, output_workspace, planform_name, create_shapefiles, footprint_outputs, log)
            log(f"Planform curvature saved to {planform_path}")

    if selected.get("rugosity"):
        options = options_by_key["rugosity"]
        log("Creating roughness / rugosity")
        if options["neighborhood_shape"] == "CIRCLE":
            neighborhood = NbrCircle(float(options["radius"]), options["units"])
        else:
            neighborhood = NbrRectangle(float(options["width"]), float(options["height"]), options["units"])
        raster = FocalStatistics(input_raster, neighborhood, options["statistic_type"], options["ignore_nodata"])
        path = save_raster(raster, output_path(output_workspace, options["output_name"]), log)
        created_outputs.append(path)
        generated_for_pca.append(path)
        create_footprint_if_requested(arcpy, path, output_workspace, options["output_name"], create_shapefiles, footprint_outputs, log)

    if selected.get("pca"):
        options = options_by_key["pca"]
        pca_source = input_raster if options["source"] == "Input raster bands" else ";".join(generated_for_pca)
        if not pca_source:
            raise RuntimeError("PCA from generated derivatives requires at least one non-PCA derivative output.")
        output = output_path(output_workspace, options["output_name"])
        stats_file = os.path.join(output_workspace, sanitize_filename(options["stats_file"], ".txt"))
        log("Creating principal components analysis")
        arcpy.gp.PrincipalComponents_sa(pca_source, output, options["number_components"], stats_file)
        created_outputs.append(output)
        create_footprint_if_requested(arcpy, output, output_workspace, options["output_name"], create_shapefiles, footprint_outputs, log)
        log(f"PCA saved to {output}")

    elapsed = (time.time() - start) / 60
    log("Finished derivative job")
    log(f"Created {len(created_outputs)} output(s) in {elapsed:.2f} minutes")
    if footprint_outputs:
        log(f"Created {len(footprint_outputs)} footprint shapefile(s)")


def run_worker(job_path: str) -> int:
    with open(job_path, "r", encoding="utf-8") as job_file:
        job = json.load(job_file)
    try:
        run_derivative_job(job, lambda message: print(message, flush=True))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", flush=True)
        print(traceback.format_exc(), flush=True)
        return 1


class BathyDerivativeApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Bathy Derivative Builder")
        self.geometry("960x680")
        self.minsize(820, 560)

        self.input_raster = tk.StringVar()
        self.output_workspace = tk.StringVar()
        self.overwrite_output = tk.BooleanVar(value=True)
        self.create_shapefiles = tk.BooleanVar(value=True)
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.worker_process: subprocess.Popen[str] | None = None
        self.worker_thread: threading.Thread | None = None
        self.worker_job_file: str | None = None

        self.derivatives = self.build_derivative_configs()
        self.build_ui()
        self.after(100, self.flush_log_queue)

    def build_derivative_configs(self) -> dict[str, DerivativeConfig]:
        return {
            "slope": DerivativeConfig("Slope", "slope", tk.BooleanVar(value=True)),
            "aspect": DerivativeConfig("Aspect", "aspect", tk.BooleanVar(value=True)),
            "profile_curvature": DerivativeConfig("Profile Curvature", "profile_curvature", tk.BooleanVar(value=True)),
            "planform_curvature": DerivativeConfig("Planform Curvature", "planform_curvature", tk.BooleanVar(value=True)),
            "rugosity": DerivativeConfig("Roughness / Rugosity", "rugosity", tk.BooleanVar(value=True)),
            "pca": DerivativeConfig("Principal Components Analysis", "pca", tk.BooleanVar(value=False)),
        }

    def build_ui(self) -> None:
        outer = ttk.Frame(self, padding=16)
        outer.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        source_frame = ttk.LabelFrame(outer, text="Input and Output", padding=12)
        source_frame.grid(row=0, column=0, sticky="ew")
        source_frame.columnconfigure(1, weight=1)

        ttk.Label(source_frame, text="Input raster").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(source_frame, textvariable=self.input_raster).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(source_frame, text="Browse", command=self.choose_input_raster).grid(row=0, column=2, padx=(8, 0), pady=4)

        ttk.Label(source_frame, text="Output folder or .gdb").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(source_frame, textvariable=self.output_workspace).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(source_frame, text="Browse", command=self.choose_output_workspace).grid(row=1, column=2, padx=(8, 0), pady=4)
        ttk.Checkbutton(source_frame, text="Overwrite existing outputs", variable=self.overwrite_output).grid(row=2, column=1, sticky="w", pady=(6, 0))
        ttk.Checkbutton(source_frame, text="Create a footprint shapefile for each raster", variable=self.create_shapefiles).grid(row=3, column=1, sticky="w", pady=(2, 0))

        derivative_frame = ttk.LabelFrame(outer, text="Derivatives", padding=12)
        derivative_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        derivative_frame.columnconfigure(1, weight=1)

        for row_index, (key, config) in enumerate(self.derivatives.items()):
            ttk.Checkbutton(derivative_frame, text=config.label, variable=config.selected).grid(row=row_index, column=0, sticky="w", pady=4)
            ttk.Label(derivative_frame, text=self.description_for(key), wraplength=560).grid(row=row_index, column=1, sticky="w", padx=12, pady=4)
            ttk.Button(derivative_frame, text="Options", command=lambda selected_key=key: self.open_options(selected_key)).grid(row=row_index, column=2, sticky="e", pady=4)

        log_frame = ttk.LabelFrame(outer, text="Run Log", padding=12)
        log_frame.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=12, wrap="word", state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

        button_frame = ttk.Frame(outer)
        button_frame.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        button_frame.columnconfigure(0, weight=1)
        self.run_button = ttk.Button(button_frame, text="Create Derivatives", command=self.start_processing)
        self.run_button.grid(row=0, column=1, sticky="e")

    def description_for(self, key: str) -> str:
        descriptions = {
            "slope": "Steepness in degrees or percent rise. Default is degrees for a 1 m bathymetric surface.",
            "aspect": "Compass direction of slope face, useful for flow and exposure interpretation.",
            "profile_curvature": "Flow acceleration and deceleration along the steepest slope direction.",
            "planform_curvature": "Flow convergence and divergence across the surface.",
            "rugosity": "Local surface complexity from focal statistics. Default is 3 by 3 cell standard deviation.",
            "pca": "Principal components from generated derivatives or source raster bands.",
        }
        return descriptions[key]

    def choose_input_raster(self) -> None:
        path = filedialog.askopenfilename(
            title="Select input raster",
            filetypes=[
                ("Bathymetry and raster datasets", "*.bag *.tif *.tiff *.img *.jp2 *.vrt *.asc *.bil *.bip *.bsq"),
                ("BAG bathymetry", "*.bag"),
                ("GeoTIFF", "*.tif *.tiff"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.input_raster.set(path)

    def choose_output_workspace(self) -> None:
        path = filedialog.askdirectory(title="Select output folder or file geodatabase")
        if path:
            self.output_workspace.set(path)

    def open_options(self, key: str) -> None:
        config = self.derivatives[key]
        window = tk.Toplevel(self)
        window.title(f"{config.label} Options")
        window.resizable(False, False)
        body = ttk.Frame(window, padding=14)
        body.grid(row=0, column=0, sticky="nsew")

        if key in {"slope", "aspect", "profile_curvature", "planform_curvature"}:
            self.ensure_surface_options(config, key)
            self.surface_options_ui(body, config, key)
        elif key == "rugosity":
            self.ensure_rugosity_options(config)
            self.rugosity_options_ui(body, config)
        elif key == "pca":
            self.ensure_pca_options(config)
            self.pca_options_ui(body, config)

        ttk.Button(body, text="Done", command=window.destroy).grid(row=99, column=1, sticky="e", pady=(12, 0))

    def ensure_surface_options(self, config: DerivativeConfig, key: str) -> None:
        if config.options:
            return
        defaults = dict(SURFACE_PARAMETER_DEFAULTS)
        if key in {"profile_curvature", "planform_curvature"}:
            defaults["z_factor"] = "1"
        config.options = {
            "output_name": tk.StringVar(value=config.output_name),
            "local_surface_type": tk.StringVar(value=defaults["local_surface_type"]),
            "neighborhood_distance": tk.StringVar(value=defaults["neighborhood_distance"]),
            "adaptive_neighborhood": tk.StringVar(value=defaults["adaptive_neighborhood"]),
            "z_unit": tk.StringVar(value=defaults["z_unit"]),
            "slope_measurement": tk.StringVar(value=defaults["slope_measurement"]),
            "project_geodesic_azimuths": tk.StringVar(value=defaults["project_geodesic_azimuths"]),
            "equatorial_aspect": tk.StringVar(value=defaults["equatorial_aspect"]),
        }
        if "z_factor" in defaults:
            config.options["z_factor"] = tk.StringVar(value=defaults["z_factor"])

    def ensure_rugosity_options(self, config: DerivativeConfig) -> None:
        if config.options:
            return
        config.options = {
            "output_name": tk.StringVar(value=config.output_name),
            "statistic_type": tk.StringVar(value="STD"),
            "neighborhood_shape": tk.StringVar(value="RECTANGLE"),
            "width": tk.StringVar(value="3"),
            "height": tk.StringVar(value="3"),
            "radius": tk.StringVar(value="1.5"),
            "units": tk.StringVar(value="CELL"),
            "ignore_nodata": tk.StringVar(value="DATA"),
        }

    def ensure_pca_options(self, config: DerivativeConfig) -> None:
        if config.options:
            return
        config.options = {
            "output_name": tk.StringVar(value=config.output_name),
            "number_components": tk.StringVar(value="3"),
            "source": tk.StringVar(value="Generated derivatives"),
            "stats_file": tk.StringVar(value="pca_stats.txt"),
        }

    def surface_options_ui(self, body: ttk.Frame, config: DerivativeConfig, key: str) -> None:
        self.add_entry(body, 0, "Output name", config.options["output_name"])
        self.add_combo(body, 1, "Local surface type", config.options["local_surface_type"], ["QUADRATIC", "BIQUADRATIC"])
        self.add_entry(body, 2, "Neighborhood distance", config.options["neighborhood_distance"])
        self.add_combo(body, 3, "Neighborhood mode", config.options["adaptive_neighborhood"], ["FIXED_NEIGHBORHOOD", "ADAPTIVE_NEIGHBORHOOD"])
        self.add_combo(body, 4, "Z unit", config.options["z_unit"], ["METER", "FOOT", "KILOMETER", "CENTIMETER"])
        if key == "slope":
            self.add_combo(body, 5, "Slope measurement", config.options["slope_measurement"], ["DEGREE", "PERCENT_RISE"])
        if key == "aspect":
            self.add_combo(body, 6, "Azimuth projection", config.options["project_geodesic_azimuths"], ["GEODESIC_AZIMUTHS", "PROJECT_GEODESIC_AZIMUTHS"])
            self.add_combo(body, 7, "Equatorial aspect", config.options["equatorial_aspect"], ["NORTH_POLE_ASPECT", "EQUATORIAL_ASPECT"])
        if key in {"profile_curvature", "planform_curvature"}:
            self.add_entry(body, 5, "Fallback z-factor", config.options["z_factor"])

    def rugosity_options_ui(self, body: ttk.Frame, config: DerivativeConfig) -> None:
        self.add_entry(body, 0, "Output name", config.options["output_name"])
        self.add_combo(body, 1, "Statistic", config.options["statistic_type"], ["STD", "RANGE", "MEAN", "VARIETY"])
        self.add_combo(body, 2, "Neighborhood shape", config.options["neighborhood_shape"], ["RECTANGLE", "CIRCLE"])
        self.add_entry(body, 3, "Rectangle width", config.options["width"])
        self.add_entry(body, 4, "Rectangle height", config.options["height"])
        self.add_entry(body, 5, "Circle radius", config.options["radius"])
        self.add_combo(body, 6, "Units", config.options["units"], ["CELL", "MAP"])
        self.add_combo(body, 7, "NoData handling", config.options["ignore_nodata"], ["DATA", "NODATA"])

    def pca_options_ui(self, body: ttk.Frame, config: DerivativeConfig) -> None:
        self.add_entry(body, 0, "Output name", config.options["output_name"])
        self.add_entry(body, 1, "Number of components", config.options["number_components"])
        self.add_combo(body, 2, "PCA source", config.options["source"], ["Generated derivatives", "Input raster bands"])
        self.add_entry(body, 3, "Statistics file name", config.options["stats_file"])

    def add_entry(self, parent: ttk.Frame, row: int, label: str, variable: tk.Variable) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=5)
        ttk.Entry(parent, textvariable=variable, width=34).grid(row=row, column=1, sticky="ew", pady=5)

    def add_combo(self, parent: ttk.Frame, row: int, label: str, variable: tk.Variable, values: list[str]) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=5)
        ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=31).grid(row=row, column=1, sticky="ew", pady=5)

    def start_processing(self) -> None:
        if self.worker_process and self.worker_process.poll() is None:
            messagebox.showinfo("Processing", "A derivative job is already running.")
            return
        if not self.input_raster.get().strip():
            messagebox.showerror("Missing input", "Select an input raster.")
            return
        if not self.output_workspace.get().strip():
            messagebox.showerror("Missing output", "Select an output folder or file geodatabase.")
            return
        if not any(config.selected.get() for config in self.derivatives.values()):
            messagebox.showerror("Missing derivatives", "Select at least one derivative.")
            return

        self.run_button.configure(state="disabled")
        self.clear_log()
        self.start_worker_process()

    def build_job_config(self) -> dict:
        selected = {key: config.selected.get() for key, config in self.derivatives.items()}
        options: dict[str, dict[str, str]] = {}
        for key, config in self.derivatives.items():
            if key in {"slope", "aspect", "profile_curvature", "planform_curvature"}:
                self.ensure_surface_options(config, key)
            elif key == "rugosity":
                self.ensure_rugosity_options(config)
            elif key == "pca":
                self.ensure_pca_options(config)
            options[key] = self.option_values(config)

        return {
            "input_raster": self.input_raster.get().strip(),
            "output_workspace": self.output_workspace.get().strip(),
            "overwrite_output": self.overwrite_output.get(),
            "create_shapefiles": self.create_shapefiles.get(),
            "selected": selected,
            "options": options,
        }

    def start_worker_process(self) -> None:
        job = self.build_job_config()
        job_file = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        try:
            json.dump(job, job_file, indent=2)
        finally:
            job_file.close()
        self.worker_job_file = job_file.name
        command = [sys.executable, os.path.abspath(__file__), "--worker", job_file.name]
        self.log(f"Launching worker process: {sys.executable}")
        try:
            self.worker_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as exc:
            self.run_button.configure(state="normal")
            self.cleanup_worker_job_file()
            messagebox.showerror("Could not start worker", str(exc))
            return

        self.worker_thread = threading.Thread(target=self.read_worker_output, daemon=True)
        self.worker_thread.start()

    def read_worker_output(self) -> None:
        process = self.worker_process
        if not process:
            self.log("__JOB_DONE__")
            return
        if process.stdout:
            for line in process.stdout:
                self.log(line.rstrip())
        exit_code = process.wait()
        self.cleanup_worker_job_file()
        self.log(f"Worker process exited with code {exit_code}")
        self.log("__JOB_DONE__")

    def cleanup_worker_job_file(self) -> None:
        if self.worker_job_file and os.path.exists(self.worker_job_file):
            try:
                os.remove(self.worker_job_file)
            except OSError:
                pass
        self.worker_job_file = None

    def process_derivatives(self) -> None:
        start = time.time()
        created_outputs: list[str] = []
        generated_for_pca: list[str] = []
        footprint_outputs: list[str] = []
        curvature_cache: tuple[str, str] | None = None
        try:
            input_raster = self.input_raster.get().strip()
            output_workspace = self.output_workspace.get().strip()
            arcpy, FocalStatistics, NbrCircle, NbrRectangle = load_arcpy()
            arcpy.env.overwriteOutput = self.overwrite_output.get()
            arcpy.env.workspace = output_workspace

            self.log("Starting derivative job")
            self.log(f"Input raster: {input_raster}")
            self.log(f"Output workspace: {output_workspace}")
            validate_input_raster(arcpy, input_raster, self.log)

            if self.derivatives["slope"].selected.get():
                config = self.derivatives["slope"]
                self.ensure_surface_options(config, "slope")
                options = self.option_values(config)
                self.log("Creating slope")
                raster = surface_parameters(arcpy, input_raster, "SLOPE", options)
                path = save_raster(raster, output_path(output_workspace, options["output_name"]), self.log)
                created_outputs.append(path)
                generated_for_pca.append(path)
                self.create_footprint_if_requested(arcpy, path, output_workspace, options["output_name"], footprint_outputs)

            if self.derivatives["aspect"].selected.get():
                config = self.derivatives["aspect"]
                self.ensure_surface_options(config, "aspect")
                options = self.option_values(config)
                self.log("Creating aspect")
                raster = surface_parameters(arcpy, input_raster, "ASPECT", options)
                path = save_raster(raster, output_path(output_workspace, options["output_name"]), self.log)
                created_outputs.append(path)
                generated_for_pca.append(path)
                self.create_footprint_if_requested(arcpy, path, output_workspace, options["output_name"], footprint_outputs)

            profile_selected = self.derivatives["profile_curvature"].selected.get()
            planform_selected = self.derivatives["planform_curvature"].selected.get()
            if profile_selected or planform_selected:
                profile_config = self.derivatives["profile_curvature"]
                planform_config = self.derivatives["planform_curvature"]
                self.ensure_surface_options(profile_config, "profile_curvature")
                self.ensure_surface_options(planform_config, "planform_curvature")
                profile_options = self.option_values(profile_config)
                planform_options = self.option_values(planform_config)
                curvature_cache = make_curvature(arcpy, input_raster, output_workspace, profile_options, planform_options, self.log)

            if profile_selected and curvature_cache:
                profile_path = curvature_cache[0]
                created_outputs.append(profile_path)
                generated_for_pca.append(profile_path)
                profile_name = self.option_values(self.derivatives["profile_curvature"])["output_name"]
                self.create_footprint_if_requested(arcpy, profile_path, output_workspace, profile_name, footprint_outputs)
                self.log(f"Profile curvature saved to {profile_path}")

            if planform_selected and curvature_cache:
                planform_path = curvature_cache[1]
                created_outputs.append(planform_path)
                generated_for_pca.append(planform_path)
                planform_name = self.option_values(self.derivatives["planform_curvature"])["output_name"]
                self.create_footprint_if_requested(arcpy, planform_path, output_workspace, planform_name, footprint_outputs)
                self.log(f"Planform curvature saved to {planform_path}")

            if self.derivatives["rugosity"].selected.get():
                config = self.derivatives["rugosity"]
                self.ensure_rugosity_options(config)
                options = self.option_values(config)
                self.log("Creating roughness / rugosity")
                if options["neighborhood_shape"] == "CIRCLE":
                    neighborhood = NbrCircle(float(options["radius"]), options["units"])
                else:
                    neighborhood = NbrRectangle(float(options["width"]), float(options["height"]), options["units"])
                raster = FocalStatistics(input_raster, neighborhood, options["statistic_type"], options["ignore_nodata"])
                path = save_raster(raster, output_path(output_workspace, options["output_name"]), self.log)
                created_outputs.append(path)
                generated_for_pca.append(path)
                self.create_footprint_if_requested(arcpy, path, output_workspace, options["output_name"], footprint_outputs)

            if self.derivatives["pca"].selected.get():
                config = self.derivatives["pca"]
                self.ensure_pca_options(config)
                options = self.option_values(config)
                pca_source = input_raster if options["source"] == "Input raster bands" else ";".join(generated_for_pca)
                if not pca_source:
                    raise RuntimeError("PCA from generated derivatives requires at least one non-PCA derivative output.")
                output = output_path(output_workspace, options["output_name"])
                stats_file = os.path.join(output_workspace, sanitize_filename(options["stats_file"], ".txt"))
                self.log("Creating principal components analysis")
                arcpy.gp.PrincipalComponents_sa(pca_source, output, options["number_components"], stats_file)
                created_outputs.append(output)
                self.create_footprint_if_requested(arcpy, output, output_workspace, options["output_name"], footprint_outputs)
                self.log(f"PCA saved to {output}")

            elapsed = (time.time() - start) / 60
            self.log("Finished derivative job")
            self.log(f"Created {len(created_outputs)} output(s) in {elapsed:.2f} minutes")
            if footprint_outputs:
                self.log(f"Created {len(footprint_outputs)} footprint shapefile(s)")
        except Exception as exc:
            self.log(f"ERROR: {exc}")
            self.log(traceback.format_exc())
        finally:
            self.log("__JOB_DONE__")

    def option_values(self, config: DerivativeConfig) -> dict[str, str]:
        return {key: variable.get() for key, variable in config.options.items()}

    def create_footprint_if_requested(
        self,
        arcpy,
        raster_path: str,
        output_workspace: str,
        output_name: str,
        footprint_outputs: list[str],
    ) -> None:
        if self.create_shapefiles.get():
            footprint_outputs.append(create_raster_footprint(arcpy, raster_path, output_workspace, output_name, self.log))

    def log(self, message: str) -> None:
        self.log_queue.put(message)

    def clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def flush_log_queue(self) -> None:
        try:
            while True:
                message = self.log_queue.get_nowait()
                if message == "__JOB_DONE__":
                    self.run_button.configure(state="normal")
                    continue
                self.log_text.configure(state="normal")
                self.log_text.insert("end", message + "\n")
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self.flush_log_queue)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        raise SystemExit(run_worker(sys.argv[2]))

    app = BathyDerivativeApp()
    app.mainloop()