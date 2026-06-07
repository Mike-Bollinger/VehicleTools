"""
LLS_quick_look_video.py
------------------
Reads an LLS .xyz file and produces a video with three subplots per frame:
  Front View  ->  X vs Z
  Side View   ->  Y vs Z
  Top Down    ->  X vs Y
Points are coloured by intensity (red = low, blue = high).
Points below INTENSITY_THRESHOLD are excluded from all views.
Every Nth unique timestamp becomes one frame; axes are fixed from the full dataset.
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")          # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cv2

# ---------------------------------------------------------------------------
# GUI – collect configuration from the user before processing
# ---------------------------------------------------------------------------

# Default values (edit these to change what pre-populates the GUI)
_DEFAULT_INPUT_FILE         = r"E:\620_training_RAW\260504_LaserOrientationTest\lls_raw\LLS_2026-05-04T223304.008238_0.xyz"
_DEFAULT_OUTPUT_DIR         = r"E:\620_training_RAW\260504_LaserOrientationTest\quick_look"
_DEFAULT_INTENSITY_THRESHOLD = 0
_DEFAULT_EVERY_NTH           = 5
_DEFAULT_FPS                 = 30


def _run_gui():
    """Open a settings dialog and return (INPUT_FILE, OUTPUT_DIR, INTENSITY_THRESHOLD, EVERY_NTH, FPS)
    or raise SystemExit if the user cancels."""

    root = tk.Tk()
    root.title("LLS Quick Look Video – Settings")
    root.resizable(False, False)

    PAD = {"padx": 8, "pady": 4}

    # ── Title / description ──────────────────────────────────────────────────
    title_frame = tk.Frame(root, bg="#1e3a5f")
    title_frame.grid(row=0, column=0, columnspan=3, sticky="ew")
    tk.Label(
        title_frame,
        text="LLS Quick Look Video Generator",
        bg="#1e3a5f", fg="white",
        font=("Segoe UI", 13, "bold"),
        pady=8,
    ).pack()
    tk.Label(
        title_frame,
        text="Generates a 3-view (Front / Side / Top-Down) MP4 from an LLS .xyz file",
        bg="#1e3a5f", fg="#aac8e8",
        font=("Segoe UI", 9),
        pady=2,
    ).pack()

    frm = tk.Frame(root, padx=16, pady=12)
    frm.grid(row=1, column=0, sticky="nsew")

    def _label(row, text, note=None):
        tk.Label(frm, text=text, anchor="w", font=("Segoe UI", 9, "bold")).grid(
            row=row, column=0, sticky="w", **PAD
        )
        if note:
            tk.Label(frm, text=note, anchor="w", fg="#555555",
                     font=("Segoe UI", 8, "italic"), wraplength=380).grid(
                row=row + 1, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 4)
            )

    # ── Input file ───────────────────────────────────────────────────────────
    _label(0, "Input .xyz File")
    var_input = tk.StringVar(value=_DEFAULT_INPUT_FILE)
    tk.Entry(frm, textvariable=var_input, width=55, font=("Segoe UI", 9)).grid(
        row=0, column=1, **PAD
    )
    tk.Button(
        frm, text="Browse…",
        command=lambda: var_input.set(
            filedialog.askopenfilename(
                title="Select LLS .xyz file",
                filetypes=[("XYZ files", "*.xyz"), ("All files", "*.*")],
                initialfile=var_input.get(),
            ) or var_input.get()
        ),
    ).grid(row=0, column=2, **PAD)

    # ── Output directory ─────────────────────────────────────────────────────
    _label(2, "Output Directory")
    var_output = tk.StringVar(value=_DEFAULT_OUTPUT_DIR)
    tk.Entry(frm, textvariable=var_output, width=55, font=("Segoe UI", 9)).grid(
        row=2, column=1, **PAD
    )
    tk.Button(
        frm, text="Browse…",
        command=lambda: var_output.set(
            filedialog.askdirectory(title="Select output folder") or var_output.get()
        ),
    ).grid(row=2, column=2, **PAD)

    # ── Separator ────────────────────────────────────────────────────────────
    ttk.Separator(frm, orient="horizontal").grid(
        row=4, column=0, columnspan=3, sticky="ew", pady=8
    )

    # ── Intensity threshold ───────────────────────────────────────────────────
    _label(5,  "Intensity Threshold",
           note="Points with intensity below this value are excluded from all views.  "
                "Set to 0 to keep all points.")
    var_thresh = tk.IntVar(value=_DEFAULT_INTENSITY_THRESHOLD)
    tk.Spinbox(frm, from_=0, to=9999, textvariable=var_thresh,
               width=10, font=("Segoe UI", 9)).grid(row=5, column=1, sticky="w", **PAD)

    # ── Every Nth ────────────────────────────────────────────────────────────
    _label(7,  "Every Nth Timestamp",
           note="Use every Nth unique timestamp as a video frame.  "
                "1 = all frames (slowest);  5 = every 5th (5× faster, fewer frames).  "
                "Increase this value to speed up processing on large files.")
    var_nth = tk.IntVar(value=_DEFAULT_EVERY_NTH)
    tk.Spinbox(frm, from_=1, to=1000, textvariable=var_nth,
               width=10, font=("Segoe UI", 9)).grid(row=7, column=1, sticky="w", **PAD)

    # ── FPS ──────────────────────────────────────────────────────────────────
    _label(9,  "Output Video FPS",
           note="Frames per second for the output MP4.  30 fps is standard.")
    var_fps = tk.IntVar(value=_DEFAULT_FPS)
    tk.Spinbox(frm, from_=1, to=120, textvariable=var_fps,
               width=10, font=("Segoe UI", 9)).grid(row=9, column=1, sticky="w", **PAD)

    # ── Buttons ───────────────────────────────────────────────────────────────
    result = {}

    def _run():
        inp = var_input.get().strip()
        out = var_output.get().strip()
        if not inp or not os.path.isfile(inp):
            messagebox.showerror("Error", "Please select a valid input .xyz file.")
            return
        if not out:
            messagebox.showerror("Error", "Please select an output directory.")
            return
        try:
            nth = int(var_nth.get())
            fps = int(var_fps.get())
            thr = int(var_thresh.get())
            if nth < 1:
                raise ValueError("Every Nth must be ≥ 1")
            if fps < 1:
                raise ValueError("FPS must be ≥ 1")
            if thr < 0:
                raise ValueError("Intensity threshold must be ≥ 0")
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("Invalid input", str(exc))
            return
        result["INPUT_FILE"]          = inp
        result["OUTPUT_DIR"]          = out
        result["INTENSITY_THRESHOLD"] = thr
        result["EVERY_NTH"]           = nth
        result["FPS"]                 = fps
        root.destroy()

    def _cancel():
        root.destroy()

    btn_frame = tk.Frame(root, padx=16, pady=8)
    btn_frame.grid(row=2, column=0, sticky="e")
    tk.Button(btn_frame, text="Cancel", width=10, command=_cancel).pack(side="right", padx=4)
    tk.Button(btn_frame, text="Run", width=10, bg="#1e3a5f", fg="white",
              font=("Segoe UI", 9, "bold"), command=_run).pack(side="right", padx=4)

    root.mainloop()

    if not result:
        print("Cancelled by user.")
        sys.exit(0)

    return (
        result["INPUT_FILE"],
        result["OUTPUT_DIR"],
        result["INTENSITY_THRESHOLD"],
        result["EVERY_NTH"],
        result["FPS"],
    )


INPUT_FILE, OUTPUT_DIR, INTENSITY_THRESHOLD, EVERY_NTH, FPS = _run_gui()

# ---------------------------------------------------------------------------
# Derive output video path from the chosen input file
# ---------------------------------------------------------------------------
_stem        = os.path.splitext(os.path.basename(INPUT_FILE))[0]   # filename without .xyz
OUTPUT_VIDEO = os.path.join(OUTPUT_DIR, f"{_stem}_3views.mp4")
os.makedirs(OUTPUT_DIR, exist_ok=True)


INTENSITY_MIN       = 0
INTENSITY_MAX       = 1000
POINT_SIZE          = 2     # scatter marker size (pts²)
FIG_W_PX            = 1920  # output frame width  in pixels
FIG_H_PX            = 640   # output frame height in pixels
DPI                 = 100

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
print(f"Loading: {INPUT_FILE}")
df = pd.read_csv(
    INPUT_FILE,
    sep=",",
    skipinitialspace=True,
    header=None,
    names=["time", "x", "y", "z", "intensity", "quality"],
    dtype={"time": np.int64, "x": np.float64, "y": np.float64,
           "z": np.float64, "intensity": np.float64, "quality": np.float64},
)
print(f"  {len(df):,} points loaded")

# ---------------------------------------------------------------------------
# Unique timestamps (preserve temporal order)
# ---------------------------------------------------------------------------
unique_times = np.sort(df["time"].unique())
if EVERY_NTH > 1:
    unique_times = unique_times[::EVERY_NTH]
n_frames     = len(unique_times)
print(f"  {len(df['time'].unique()):,} total unique timestamps; using every {EVERY_NTH}th → {n_frames} frames")

# ---------------------------------------------------------------------------
# Fixed spatial extents computed from the full dataset (consistent axes)
# ---------------------------------------------------------------------------
df_above = df[df["intensity"] >= INTENSITY_THRESHOLD]
if df_above.empty:
    raise ValueError("No points remain after applying INTENSITY_THRESHOLD – lower the threshold.")

def _padded(lo, hi, pct=0.05):
    p = (hi - lo) * pct if hi != lo else 1.0
    return lo - p, hi + p

x_lim = _padded(df_above["x"].min(), df_above["x"].max())
y_lim = _padded(df_above["y"].min(), df_above["y"].max())
z_lim = _padded(df_above["z"].min(), df_above["z"].max())
print(f"  X range: {x_lim[0]:.2f} – {x_lim[1]:.2f} m")
print(f"  Y range: {y_lim[0]:.2f} – {y_lim[1]:.2f} m")
print(f"  Z range: {z_lim[0]:.2f} – {z_lim[1]:.2f} m")

# ---------------------------------------------------------------------------
# Colour map and normalisation
# ---------------------------------------------------------------------------
cmap = matplotlib.colormaps["RdBu_r"]   # red at low intensity, blue at high
norm = mcolors.Normalize(vmin=INTENSITY_MIN, vmax=INTENSITY_MAX)

# ---------------------------------------------------------------------------
# Matplotlib figure: 1 row × 3 subplots  (Front | Side | Top-Down)
# ---------------------------------------------------------------------------
fig_w_in = FIG_W_PX / DPI
fig_h_in = FIG_H_PX / DPI

fig, (ax_front, ax_side, ax_top) = plt.subplots(
    1, 3, figsize=(fig_w_in, fig_h_in), dpi=DPI
)
fig.patch.set_facecolor("black")
fig.subplots_adjust(left=0.05, right=0.90, bottom=0.10, top=0.88, wspace=0.14)

_VIEWS = [
    (ax_front, "Front View looking at AUV (+X port side)",  "Starboard <- X (m) -> Port", "Z (m)",  x_lim, z_lim),
    (ax_side,  "Side View looking at port side",   "AUV Front <- Y (m) -> AUV Tail", "Z (m)",  y_lim, z_lim),
    (ax_top,   "Top Down",    "Starboard <- X (m) -> Port", "AUV Front <- Y (m) -> AUV Tail",  x_lim, y_lim),
]

for ax, ttl, xlabel, ylabel, xlim, ylim in _VIEWS:
    ax.set_facecolor("black")
    ax.set_title(ttl, color="white", fontsize=10, fontweight="bold")
    ax.set_xlabel(xlabel, color="white", fontsize=8)
    ax.set_ylabel(ylabel, color="white", fontsize=8)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.tick_params(colors="white", labelsize=7)
    for spine in ax.spines.values():
        spine.set_edgecolor("white")

# Shared colorbar on the right
sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
sm.set_array([])
cax = fig.add_axes([0.92, 0.13, 0.013, 0.74])
cbar = fig.colorbar(sm, cax=cax)
cbar.set_label("Intensity", color="white", fontsize=9)
cbar.ax.yaxis.set_tick_params(color="white")
plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")

suptitle = fig.suptitle("", color="white", fontsize=9, y=0.98)

# ---------------------------------------------------------------------------
# OpenCV video writer
# ---------------------------------------------------------------------------
fourcc = cv2.VideoWriter_fourcc(*"mp4v")

fig.canvas.draw()
canvas_w, canvas_h = fig.canvas.get_width_height()
print(f"  Frame size: {canvas_w} × {canvas_h} px")
print(f"  Output:     {OUTPUT_VIDEO}")

writer = cv2.VideoWriter(OUTPUT_VIDEO, fourcc, FPS, (canvas_w, canvas_h))
if not writer.isOpened():
    raise RuntimeError(f"Could not open VideoWriter for: {OUTPUT_VIDEO}")

# ---------------------------------------------------------------------------
# Render frames – every selected unique time gets one frame
# ---------------------------------------------------------------------------
print("Rendering frames ...")
for i, t in enumerate(unique_times):
    frame_df = df[(df["time"] == t) & (df["intensity"] >= INTENSITY_THRESHOLD)]
    colours  = cmap(norm(frame_df["intensity"].values))

    x = frame_df["x"].values
    y = frame_df["y"].values
    z = frame_df["z"].values

    # Remove previous scatter artists, then draw new ones
    if i > 0:
        sc_front.remove()
        sc_side.remove()
        sc_top.remove()

    sc_front = ax_front.scatter(x, z, c=colours, s=POINT_SIZE, linewidths=0)
    sc_side  = ax_side.scatter( y, z, c=colours, s=POINT_SIZE, linewidths=0)
    sc_top   = ax_top.scatter(  x, y, c=colours, s=POINT_SIZE, linewidths=0)

    t_sec = t / 1e6
    suptitle.set_text(
        f"Time: {t_sec:.6f} s   |   Ping {i + 1}/{n_frames}   |   "
        f"Points (≥{INTENSITY_THRESHOLD}): {len(frame_df):,}"
    )

    fig.canvas.draw()
    buf = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8)
    buf = buf.reshape(canvas_h, canvas_w, 4)
    bgr = cv2.cvtColor(buf, cv2.COLOR_RGBA2BGR)
    writer.write(bgr)

    if (i + 1) % 100 == 0 or (i + 1) == n_frames:
        print(f"  Frame {i + 1:,} / {n_frames:,}  ({100*(i+1)/n_frames:.1f}%)")

writer.release()
plt.close(fig)
print(f"\nDone. Video saved to:\n  {OUTPUT_VIDEO}")
