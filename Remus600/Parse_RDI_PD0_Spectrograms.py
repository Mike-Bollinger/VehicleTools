#!/usr/bin/env python3
"""
Parse Teledyne RDI-style PD0 binary logs and generate echograms.

This script focuses on common PD0 data blocks:
- Fixed Leader (0x0000)
- Variable Leader (0x0080)
- Velocity (0x0100)
- Correlation (0x0200)
- Amplitude/Echo Intensity (0x0300)
- Percent Good (0x0400)
- Status (0x0500)

It estimates sampling rate from timestamps when possible, otherwise from fixed
leader timing fields.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
except Exception:
    tk = None
    filedialog = None
    messagebox = None


SYNC_BYTES = b"\x7f\x7f"


@dataclass
class PingData:
    time_utc: Optional[datetime]
    ensemble_number: Optional[int]
    n_cells: Optional[int]
    bin1_dist_m: Optional[float]
    cell_size_m: Optional[float]
    pings_per_ensemble: Optional[int]
    sec_between_ping_groups: Optional[float]
    velocity: Optional[np.ndarray]
    correlation: Optional[np.ndarray]
    amplitude: Optional[np.ndarray]
    percent_good: Optional[np.ndarray]
    status: Optional[np.ndarray]


@dataclass
class ParseResult:
    pings: List[PingData]
    fs_hz: Optional[float]
    dt_seconds: Optional[float]
    first_time_utc: Optional[datetime]
    last_time_utc: Optional[datetime]
    n_ensembles: int


def u8(buf: bytes, idx: int) -> int:
    return int(buf[idx])


def i8(buf: bytes, idx: int) -> int:
    return int(np.frombuffer(buf[idx:idx + 1], dtype=np.int8)[0])


def u16(buf: bytes, idx: int) -> int:
    return int.from_bytes(buf[idx:idx + 2], byteorder="little", signed=False)


def i16(buf: bytes, idx: int) -> int:
    return int.from_bytes(buf[idx:idx + 2], byteorder="little", signed=True)


def _decode_fixed_leader(block: bytes) -> Dict[str, float]:
    # block starts at ID word (0x0000)
    # Field order follows common TRDI PD0 fixed leader structure.
    out: Dict[str, float] = {}
    if len(block) < 42:
        return out

    pos = 2
    fw_major = u8(block, pos)
    fw_minor = u8(block, pos + 1)
    config0 = u8(block, pos + 2)
    config1 = u8(block, pos + 3)
    out["prog_ver"] = fw_major + fw_minor / 100.0
    beam5 = 1 if (config1 & 16) == 16 else 0

    pos += 5  # [fw_major, fw_minor, config0, config1, simflag]
    pos += 1  # spare

    out["n_beams"] = u8(block, pos) + beam5
    out["n_cells"] = u8(block, pos + 1)
    out["pings_per_ensemble"] = u16(block, pos + 2)
    out["cell_size_m"] = u16(block, pos + 4) * 0.01
    out["blank_dist_m"] = u16(block, pos + 6) * 0.01

    pos += 8
    pos += 4  # profiling mode, min corr, n_code_reps, min_prcnt_gd
    out["max_error_vel_mps"] = u16(block, pos) / 1000.0
    pos += 2

    t0 = u8(block, pos)
    t1 = u8(block, pos + 1)
    t2 = u8(block, pos + 2)
    out["sec_between_ping_groups"] = t0 * 60.0 + t1 + t2 * 0.01

    pos += 3
    pos += 1  # coord_sys
    pos += 2  # heading_misalign
    pos += 2  # magnetic_var
    pos += 1  # sensors_src
    pos += 1  # sensors_avail

    if pos + 2 <= len(block):
        out["bin1_dist_m"] = u16(block, pos) * 0.01

    return out


def _decode_variable_leader(block: bytes, base_year: int = 2000) -> Dict[str, object]:
    # block starts at ID word (0x0080)
    pos = 2
    out: Dict[str, object] = {}
    if len(block) < 30:
        return out

    ensemble_number = u16(block, pos)
    rtc = [u8(block, pos + 2 + i) for i in range(7)]
    ensemble_number += 65535 * u8(block, pos + 9)

    year = rtc[0]
    if year < 100:
        year += base_year

    month, day, hour, minute, second = rtc[1:6]
    hundredths = rtc[6]

    try:
        time_utc = datetime(
            year,
            month,
            day,
            hour,
            minute,
            second,
            hundredths * 10000,
            tzinfo=timezone.utc,
        )
    except ValueError:
        time_utc = None

    out["ensemble_number"] = ensemble_number
    out["time_utc"] = time_utc
    out["heading_deg"] = u16(block, pos + 16) * 0.01
    out["pitch_deg"] = i16(block, pos + 18) * 0.01
    out["roll_deg"] = i16(block, pos + 20) * 0.01
    out["temperature_c"] = i16(block, pos + 24) * 0.01

    return out


def _decode_matrix_i16(block: bytes, n_cells: int, n_beams: int = 4, scale: float = 1.0) -> np.ndarray:
    needed = 2 + n_cells * n_beams * 2
    if len(block) < needed:
        return np.empty((0, n_beams), dtype=np.float32)
    arr = np.frombuffer(block[2:needed], dtype="<i2").astype(np.float32)
    arr = arr.reshape((n_cells, n_beams))
    return arr * scale


def _decode_matrix_u8(block: bytes, n_cells: int, n_beams: int = 4) -> np.ndarray:
    needed = 2 + n_cells * n_beams
    if len(block) < needed:
        return np.empty((0, n_beams), dtype=np.float32)
    arr = np.frombuffer(block[2:needed], dtype=np.uint8).astype(np.float32)
    return arr.reshape((n_cells, n_beams))


def iter_pd0_ensembles(data: bytes) -> Iterable[Tuple[int, bytes, List[int]]]:
    pos = 0
    n = len(data)

    while pos + 8 <= n:
        start = data.find(SYNC_BYTES, pos)
        if start < 0 or start + 8 > n:
            break

        nbyte = u16(data, start + 2)
        end = start + 2 + nbyte
        if nbyte < 6 or end > n:
            pos = start + 1
            continue

        ndat = u8(data, start + 5)
        offsets_start = start + 6
        offsets_end = offsets_start + ndat * 2
        if offsets_end > end:
            pos = start + 1
            continue

        offsets = [u16(data, offsets_start + 2 * i) for i in range(ndat)]
        if not offsets:
            pos = start + 1
            continue
        if any((off >= nbyte or off < 6) for off in offsets):
            pos = start + 1
            continue

        ensemble = data[start:end]
        yield start, ensemble, offsets

        # Move to expected next ensemble boundary; scanner will recover if wrong.
        pos = end


def parse_pd0_file(path: Path, fs_hint: Optional[float] = None, max_ensembles: Optional[int] = None) -> ParseResult:
    raw = path.read_bytes()

    pings: List[PingData] = []
    last_fixed: Dict[str, float] = {}

    for _, ens, offsets in iter_pd0_ensembles(raw):
        if max_ensembles is not None and len(pings) >= max_ensembles:
            break

        cfg = dict(last_fixed)
        vlead: Dict[str, object] = {}

        vel = None
        corr = None
        amp = None
        pg = None
        stat = None

        sorted_offsets = sorted(offsets)
        block_ranges: List[Tuple[int, int]] = []
        for i, off in enumerate(sorted_offsets):
            nxt = sorted_offsets[i + 1] if i + 1 < len(sorted_offsets) else len(ens)
            block_ranges.append((off, nxt))

        for off, nxt in block_ranges:
            if off + 2 > len(ens):
                continue
            block = ens[off:nxt]
            block_id = u16(ens, off)

            if block_id == 0x0000:
                cfg.update(_decode_fixed_leader(block))
                last_fixed = dict(cfg)
            elif block_id == 0x0080:
                vlead = _decode_variable_leader(block)
            elif block_id == 0x0100:
                n_cells = int(cfg.get("n_cells", 0))
                vel = _decode_matrix_i16(block, n_cells=n_cells, n_beams=4, scale=0.001)
            elif block_id == 0x0200:
                n_cells = int(cfg.get("n_cells", 0))
                corr = _decode_matrix_u8(block, n_cells=n_cells, n_beams=4)
            elif block_id == 0x0300:
                n_cells = int(cfg.get("n_cells", 0))
                amp = _decode_matrix_u8(block, n_cells=n_cells, n_beams=4)
            elif block_id == 0x0400:
                n_cells = int(cfg.get("n_cells", 0))
                pg = _decode_matrix_u8(block, n_cells=n_cells, n_beams=4)
            elif block_id == 0x0500:
                n_cells = int(cfg.get("n_cells", 0))
                stat = _decode_matrix_u8(block, n_cells=n_cells, n_beams=4)

        pings.append(
            PingData(
                time_utc=vlead.get("time_utc"),
                ensemble_number=vlead.get("ensemble_number"),
                n_cells=int(cfg.get("n_cells", 0)) if cfg else None,
                bin1_dist_m=float(cfg.get("bin1_dist_m")) if cfg and cfg.get("bin1_dist_m") is not None else None,
                cell_size_m=float(cfg.get("cell_size_m")) if cfg and cfg.get("cell_size_m") is not None else None,
                pings_per_ensemble=int(cfg.get("pings_per_ensemble", 0)) if cfg else None,
                sec_between_ping_groups=float(cfg.get("sec_between_ping_groups", 0.0)) if cfg else None,
                velocity=vel,
                correlation=corr,
                amplitude=amp,
                percent_good=pg,
                status=stat,
            )
        )

    fs_hz, dt_seconds = estimate_sampling_rate(pings, fs_hint=fs_hint)

    valid_times = [p.time_utc for p in pings if p.time_utc is not None]
    first_time = min(valid_times) if valid_times else None
    last_time = max(valid_times) if valid_times else None

    return ParseResult(
        pings=pings,
        fs_hz=fs_hz,
        dt_seconds=dt_seconds,
        first_time_utc=first_time,
        last_time_utc=last_time,
        n_ensembles=len(pings),
    )


def estimate_sampling_rate(pings: List[PingData], fs_hint: Optional[float] = None) -> Tuple[Optional[float], Optional[float]]:
    if fs_hint and fs_hint > 0:
        return fs_hint, 1.0 / fs_hint

    times = [p.time_utc for p in pings if p.time_utc is not None]
    if len(times) >= 3:
        tsec = np.array([t.timestamp() for t in times], dtype=np.float64)
        dt = np.diff(tsec)
        dt = dt[np.isfinite(dt) & (dt > 0)]
        if dt.size > 0:
            dt_med = float(np.median(dt))
            if dt_med > 0:
                return 1.0 / dt_med, dt_med

    sec_pg = [p.sec_between_ping_groups for p in pings if p.sec_between_ping_groups and p.sec_between_ping_groups > 0]
    ppe = [p.pings_per_ensemble for p in pings if p.pings_per_ensemble and p.pings_per_ensemble > 0]

    if sec_pg and ppe:
        dt_est = float(np.median(sec_pg) * np.median(ppe))
        if dt_est > 0:
            return 1.0 / dt_est, dt_est

    return None, None


def _stack_signal(pings: List[PingData], attr: str) -> Optional[np.ndarray]:
    mats = [getattr(p, attr) for p in pings]
    valid = [m for m in mats if isinstance(m, np.ndarray) and m.size > 0]
    if not valid:
        return None

    n_cells_min = min(v.shape[0] for v in valid)
    n_beams_min = min(v.shape[1] for v in valid)

    out = np.full((len(pings), n_cells_min, n_beams_min), np.nan, dtype=np.float32)
    for i, m in enumerate(mats):
        if isinstance(m, np.ndarray) and m.size > 0:
            out[i, :, :] = m[:n_cells_min, :n_beams_min]

    return out


def _time_axis(pings: List[PingData], dt_seconds: float) -> List[datetime]:
    out: List[datetime] = []
    t0 = None
    for p in pings:
        if p.time_utc is not None:
            t0 = p.time_utc
            break

    if t0 is None:
        t0 = datetime(1970, 1, 1, tzinfo=timezone.utc)

    for i, p in enumerate(pings):
        if p.time_utc is not None:
            out.append(p.time_utc)
        else:
            out.append(t0 + timedelta(seconds=i * dt_seconds))

    return out


def save_timeseries_csv(
    out_csv: Path,
    times: List[datetime],
    amplitude: Optional[np.ndarray],
    correlation: Optional[np.ndarray],
    percent_good: Optional[np.ndarray],
    velocity: Optional[np.ndarray],
    status: Optional[np.ndarray],
) -> None:
    cols: Dict[str, np.ndarray] = {}

    def mean3(a: Optional[np.ndarray]) -> Optional[np.ndarray]:
        if a is None:
            return None
        return np.nanmean(a, axis=(1, 2))

    cols["timestamp_utc"] = np.array([t.isoformat() for t in times], dtype=object)

    amp_m = mean3(amplitude)
    corr_m = mean3(correlation)
    pg_m = mean3(percent_good)
    st_m = mean3(status)

    if amp_m is not None:
        cols["amplitude_mean_counts"] = amp_m
        cols["amplitude_cell1_beam1_counts"] = amplitude[:, 0, 0]
    if corr_m is not None:
        cols["correlation_mean_counts"] = corr_m
    if pg_m is not None:
        cols["percent_good_mean_pct"] = pg_m
    if st_m is not None:
        cols["status_mean_counts"] = st_m

    if velocity is not None:
        vel_rms = np.sqrt(np.nanmean(np.square(velocity), axis=(1, 2)))
        cols["velocity_rms_mps"] = vel_rms
        cols["velocity_cell1_beam1_mps"] = velocity[:, 0, 0]

    header = list(cols.keys())
    matrix = np.column_stack([cols[k] for k in header])
    np.savetxt(out_csv, matrix, delimiter=",", fmt="%s", header=",".join(header), comments="")


def export_block_level_csvs(out_dir: Path, pings: List[PingData]) -> List[str]:
    written: List[str] = []

    metadata_csv = out_dir / "ensemble_metadata.csv"
    with metadata_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "ensemble_index",
                "ensemble_number",
                "timestamp_utc",
                "n_cells",
                "bin1_dist_m",
                "cell_size_m",
                "pings_per_ensemble",
                "sec_between_ping_groups",
            ]
        )
        for i, p in enumerate(pings):
            w.writerow(
                [
                    i,
                    p.ensemble_number,
                    p.time_utc.isoformat() if p.time_utc else "",
                    p.n_cells,
                    p.bin1_dist_m,
                    p.cell_size_m,
                    p.pings_per_ensemble,
                    p.sec_between_ping_groups,
                ]
            )
    written.append(metadata_csv.name)

    def write_block(attr: str, filename: str, value_col: str) -> None:
        has_any = any(isinstance(getattr(p, attr), np.ndarray) and getattr(p, attr).size > 0 for p in pings)
        if not has_any:
            return

        out_csv = out_dir / filename
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "ensemble_index",
                    "ensemble_number",
                    "timestamp_utc",
                    "cell",
                    "beam",
                    "range_m",
                    value_col,
                ]
            )

            for i, p in enumerate(pings):
                arr = getattr(p, attr)
                if not isinstance(arr, np.ndarray) or arr.size == 0:
                    continue

                n_cells, n_beams = arr.shape
                for c in range(n_cells):
                    if p.bin1_dist_m is not None and p.cell_size_m is not None:
                        range_m = p.bin1_dist_m + c * p.cell_size_m
                    else:
                        range_m = ""

                    for b in range(n_beams):
                        val = arr[c, b]
                        if not np.isfinite(val):
                            continue
                        w.writerow(
                            [
                                i,
                                p.ensemble_number,
                                p.time_utc.isoformat() if p.time_utc else "",
                                c + 1,
                                b + 1,
                                range_m,
                                float(val),
                            ]
                        )

        written.append(out_csv.name)

    write_block("velocity", "velocity_long.csv", "velocity_mps")
    write_block("amplitude", "amplitude_long.csv", "amplitude_counts")
    write_block("correlation", "correlation_long.csv", "correlation_counts")
    write_block("percent_good", "percent_good_long.csv", "percent_good")
    write_block("status", "status_long.csv", "status_counts")

    return written


def make_echogram(
    amplitude_tcb: np.ndarray,
    times: List[datetime],
    out_png: Path,
    title: str,
    y_values: np.ndarray,
    y_label: str,
    db_mode: bool = False,
) -> None:
    # Average across beams to create a single time-range intensity image.
    amp_tc = np.nanmean(amplitude_tcb, axis=2)

    if db_mode:
        # Use magnitude so signed sources (e.g., velocity) can be mapped to dB-like scale.
        z = 10.0 * np.log10(np.clip(np.abs(amp_tc), 1e-6, None))
        cbar_label = "Relative intensity [dB, uncalibrated]"
    else:
        z = amp_tc
        cbar_label = "Echo intensity [counts]"

    t_nums = mdates.date2num(times)

    # Build edge vectors for pcolormesh.
    if len(t_nums) > 1:
        dt = np.median(np.diff(t_nums))
    else:
        dt = 1.0 / (24 * 3600)
    t_edges = np.concatenate(([t_nums[0] - dt / 2], (t_nums[:-1] + t_nums[1:]) / 2, [t_nums[-1] + dt / 2]))

    if len(y_values) > 1:
        dy = np.median(np.diff(y_values))
    else:
        dy = 1.0
    y_edges = np.concatenate(([y_values[0] - dy / 2], (y_values[:-1] + y_values[1:]) / 2, [y_values[-1] + dy / 2]))

    fig, ax = plt.subplots(figsize=(12, 6), constrained_layout=True)
    mesh = ax.pcolormesh(t_edges, y_edges, z.T, shading="auto", cmap="viridis")
    cbar = fig.colorbar(mesh, ax=ax)
    cbar.set_label(cbar_label)

    ax.set_title(title)
    ax.set_xlabel("UTC Time")
    ax.set_ylabel(y_label)
    ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=range(0, 60, 2), tz=timezone.utc))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=timezone.utc))
    plt.setp(ax.get_xticklabels(), rotation=90, ha="center")

    # Conventional echogram orientation: shallow/near bins at top.
    ax.invert_yaxis()

    fig.savefig(out_png, dpi=180)
    plt.close(fig)


def run(args: argparse.Namespace) -> None:
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if args.output_dir:
        out_dir = Path(args.output_dir).expanduser().resolve()
    else:
        out_dir = input_path.parent / f"{input_path.stem}_spectrograms"

    out_dir.mkdir(parents=True, exist_ok=True)

    result = parse_pd0_file(input_path, fs_hint=args.fs, max_ensembles=args.max_ensembles)

    if result.n_ensembles == 0:
        raise RuntimeError("No valid PD0-like ensembles were parsed.")

    if result.fs_hz is None or result.dt_seconds is None:
        raise RuntimeError(
            "Could not estimate sampling rate from timestamps or fixed-leader timing. "
            "Please rerun with --fs <Hz>."
        )

    times = _time_axis(result.pings, result.dt_seconds)

    amplitude = _stack_signal(result.pings, "amplitude")
    correlation = _stack_signal(result.pings, "correlation")
    percent_good = _stack_signal(result.pings, "percent_good")
    velocity = _stack_signal(result.pings, "velocity")
    status = _stack_signal(result.pings, "status")

    if all(arr is None for arr in [amplitude, correlation, percent_good, velocity, status]):
        raise RuntimeError("No supported signal blocks were decoded (amplitude/correlation/velocity/etc.).")

    # Echogram outputs (UTC time x range/cell, color = intensity).
    echograms_written: List[str] = []
    echogram_source_name = None
    echogram_source = None

    if amplitude is not None:
        echogram_source_name = "amplitude"
        echogram_source = amplitude
    elif correlation is not None:
        echogram_source_name = "correlation"
        echogram_source = correlation
    elif percent_good is not None:
        echogram_source_name = "percent_good"
        echogram_source = percent_good
    elif status is not None:
        echogram_source_name = "status"
        echogram_source = status
    elif velocity is not None:
        echogram_source_name = "velocity"
        echogram_source = velocity

    if echogram_source is not None:
        cell_size_vals = [p.cell_size_m for p in result.pings if p.cell_size_m and p.cell_size_m > 0]
        bin1_vals = [p.bin1_dist_m for p in result.pings if p.bin1_dist_m and p.bin1_dist_m >= 0]

        n_cells = echogram_source.shape[1]
        if cell_size_vals:
            cell_size_m = float(np.median(cell_size_vals))
            bin1_m = float(np.median(bin1_vals)) if bin1_vals else cell_size_m
            y_values = bin1_m + np.arange(n_cells, dtype=np.float64) * cell_size_m
            y_label = "Range [m]"
        else:
            y_values = np.arange(1, n_cells + 1, dtype=np.float64)
            y_label = "Cell Index"

        out_echogram_counts = out_dir / f"echogram_{echogram_source_name}_counts.png"
        make_echogram(
            amplitude_tcb=echogram_source,
            times=times,
            out_png=out_echogram_counts,
            title=f"{input_path.name} | Echogram ({echogram_source_name} Counts)",
            y_values=y_values,
            y_label=y_label,
            db_mode=False,
        )
        echograms_written.append(out_echogram_counts.name)

        out_echogram_db = out_dir / f"echogram_{echogram_source_name}_relative_db.png"
        make_echogram(
            amplitude_tcb=echogram_source,
            times=times,
            out_png=out_echogram_db,
            title=f"{input_path.name} | Echogram ({echogram_source_name} Relative dB, Uncalibrated)",
            y_values=y_values,
            y_label=y_label,
            db_mode=True,
        )
        echograms_written.append(out_echogram_db.name)

        # Hard check: if expected files are missing, surface explicit error.
        for fname in echograms_written:
            fpath = out_dir / fname
            if not fpath.exists() or fpath.stat().st_size == 0:
                raise RuntimeError(f"Echogram export failed: {fpath}")

    save_timeseries_csv(
        out_dir / "timeseries_summary.csv",
        times,
        amplitude,
        correlation,
        percent_good,
        velocity,
        status,
    )

    block_csvs_written = export_block_level_csvs(out_dir, result.pings)

    summary = {
        "input_file": str(input_path),
        "output_dir": str(out_dir),
        "n_ensembles": result.n_ensembles,
        "fs_hz": result.fs_hz,
        "dt_seconds": result.dt_seconds,
        "first_time_utc": result.first_time_utc.isoformat() if result.first_time_utc else None,
        "last_time_utc": result.last_time_utc.isoformat() if result.last_time_utc else None,
        "echogram_source": echogram_source_name,
        "echograms_written": echograms_written,
        "block_csvs_written": block_csvs_written,
    }

    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("Done.")
    print(f"Parsed ensembles: {result.n_ensembles}")
    print(f"Estimated sample rate: {result.fs_hz:.6f} Hz")
    print(f"Output directory: {out_dir}")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Parse RDI-style PD0 data and generate echograms.")
    p.add_argument("input", nargs="?", help="Path to PD0-like .dat file")
    p.add_argument("--output-dir", help="Directory for output plots and CSV")
    p.add_argument("--fs", type=float, default=None, help="Sampling rate override in Hz")
    p.add_argument("--max-ensembles", type=int, default=None, help="Limit number of ensembles to parse")
    p.add_argument("--gui", action="store_true", help="Open a simple GUI for inputs")
    return p


def launch_gui() -> None:
    if tk is None:
        raise RuntimeError("Tkinter is not available in this Python environment.")

    root = tk.Tk()
    root.title("RDI PD0 Echogram Generator")
    root.geometry("760x300")
    root.resizable(False, False)

    input_var = tk.StringVar()
    output_var = tk.StringVar()
    fs_var = tk.StringVar()
    max_ens_var = tk.StringVar()

    pad_x = 10
    pad_y = 6

    class Tooltip:
        def __init__(self, widget, text: str) -> None:
            self.widget = widget
            self.text = text
            self.tipwindow = None
            widget.bind("<Enter>", self.show)
            widget.bind("<Leave>", self.hide)

        def show(self, _event=None) -> None:
            if self.tipwindow is not None:
                return
            x = self.widget.winfo_rootx() + 20
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 2

            self.tipwindow = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")

            label = tk.Label(
                tw,
                text=self.text,
                justify="left",
                background="#ffffe0",
                relief="solid",
                borderwidth=1,
                padx=6,
                pady=4,
                wraplength=320,
            )
            label.pack()

        def hide(self, _event=None) -> None:
            if self.tipwindow is not None:
                self.tipwindow.destroy()
                self.tipwindow = None

    def choose_input() -> None:
        path = filedialog.askopenfilename(
            title="Select PD0 .dat file",
            filetypes=[("Data files", "*.dat"), ("All files", "*.*")],
        )
        if path:
            input_var.set(path)

    def choose_output() -> None:
        path = filedialog.askdirectory(title="Select output directory")
        if path:
            output_var.set(path)

    def build_args_from_form() -> argparse.Namespace:
        input_path = input_var.get().strip()
        if not input_path:
            raise ValueError("Please select an input .dat file.")

        output_dir = output_var.get().strip() or None

        fs = None
        if fs_var.get().strip():
            fs = float(fs_var.get().strip())
            if fs <= 0:
                raise ValueError("Sampling rate must be positive.")

        max_ensembles = None
        if max_ens_var.get().strip():
            max_ensembles = int(max_ens_var.get().strip())
            if max_ensembles <= 0:
                raise ValueError("Max ensembles must be positive.")

        return argparse.Namespace(
            input=input_path,
            output_dir=output_dir,
            fs=fs,
            max_ensembles=max_ensembles,
            gui=False,
        )

    def on_run() -> None:
        try:
            args = build_args_from_form()
            run(args)
            out_dir = (
                Path(args.output_dir).expanduser().resolve()
                if args.output_dir
                else Path(args.input).expanduser().resolve().parent
                / f"{Path(args.input).stem}_spectrograms"
            )
            messagebox.showinfo(
                "Completed",
                f"Processing finished successfully.\n\nOutput:\n{out_dir}",
            )
        except Exception as exc:
            messagebox.showerror("Run Failed", str(exc))

    frame = tk.Frame(root)
    frame.pack(fill="both", expand=True, padx=pad_x, pady=pad_y)

    tk.Label(frame, text="Input .dat file").grid(row=0, column=0, sticky="w", pady=pad_y)
    tk.Entry(frame, textvariable=input_var, width=72).grid(row=0, column=1, sticky="we", pady=pad_y)
    tk.Button(frame, text="Browse", command=choose_input, width=10).grid(row=0, column=2, padx=6, pady=pad_y)

    tk.Label(frame, text="Output directory").grid(row=1, column=0, sticky="w", pady=pad_y)
    tk.Entry(frame, textvariable=output_var, width=72).grid(row=1, column=1, sticky="we", pady=pad_y)
    tk.Button(frame, text="Browse", command=choose_output, width=10).grid(row=1, column=2, padx=6, pady=pad_y)

    fs_label = tk.Label(frame, text="Sampling rate override (Hz)")
    fs_label.grid(row=2, column=0, sticky="w", pady=pad_y)
    fs_entry = tk.Entry(frame, textvariable=fs_var, width=24)
    fs_entry.grid(row=2, column=1, sticky="w", pady=pad_y)

    fs_tip = (
        "Optional fixed sample rate in Hz. Leave blank to estimate from timestamps or "
        "ensemble timing fields."
    )
    Tooltip(fs_label, fs_tip)
    Tooltip(fs_entry, fs_tip)

    max_label = tk.Label(frame, text="Max ensembles")
    max_label.grid(row=3, column=0, sticky="w", pady=pad_y)
    max_entry = tk.Entry(frame, textvariable=max_ens_var, width=24)
    max_entry.grid(row=3, column=1, sticky="w", pady=pad_y)

    max_tip = (
        "Parser limit: only process the first N ensembles/pings. Useful for quick tests. "
        "Leave blank to process entire file."
    )
    Tooltip(max_label, max_tip)
    Tooltip(max_entry, max_tip)

    tk.Button(frame, text="Run", command=on_run, width=16).grid(row=4, column=1, sticky="w", pady=14)
    tk.Button(frame, text="Close", command=root.destroy, width=16).grid(row=4, column=1, sticky="e", pady=14)

    frame.columnconfigure(1, weight=1)
    root.mainloop()


if __name__ == "__main__":
    args = build_arg_parser().parse_args()
    if args.gui or not args.input:
        launch_gui()
        sys.exit(0)

    run(args)
