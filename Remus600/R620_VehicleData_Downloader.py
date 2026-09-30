"""
R620_VehicleData_Downloader

What this does:
- Connects to one of multiple AUV SFTP endpoints.
- Downloads configured files/directories from the SFTP server.
- Flattens most files into one local folder, but preserves bag folder structure
  for paths expanded with "latest_day_folder" (e.g. remus_bag_YYYY-MM-DD_HH-MM-SS/).
- Prefixes each file/folder with: <MissionName>_<DiveName>_
- Shows transfer progress in a GUI.

Configuration notes:
- Edit VEHICLE_CONFIGS below for each vehicle's source list.
- Each source can have its own host/login and remote_paths.
"""

from __future__ import annotations

import os
import posixpath
import queue
import re
import time
import stat
import threading
import tkinter as tk
import importlib
import importlib.util
import traceback
from dataclasses import dataclass
from tkinter import filedialog, messagebox, ttk


# ==============================
# CONFIGURE HERE
# ==============================
# Add/update your two AUVs here. You can rename the keys (e.g., "Remus 1", "Remus 2").
# Use "sources" to define all endpoints to pull from for a selected vehicle.
# Example: NAS + Sensor each with its own host/login/path list.
# remote_paths can include file paths, directory paths, or selector objects.
# Selector object examples:
#   {"path": "/home/remus/phins_logs", "selection": "latest_day_files"}
#   {"path": "/home/remus/remus_bags", "selection": "latest_day_folder"}
# Example file path: "/data/logs/mission01/nav.log"
# Example directory path: "/data/logs/mission01/"
VEHICLE_CONFIGS: dict[str, dict] = {
    "Wahoo SN401": {
        "serial_number": "SN401",
        "sources": [
            {
                "label": "Vehicle",
                "host": "192.168.20.10",
                "port": 22,
                "username": "remus",
                "password": "hydroid",
                "remote_paths": [
                    "/home/remus/data/remus.rlf",
                    "/home/remus/data/adcp.dat",
                    "/home/remus/data/gps.dat",
                    "/home/remus/bin/remus.out",
                    "/home/remus/config/adcp.txt",
                    "/home/remus/config/remus_v.ini",
                    "/home/remus/logs/phins_raw.log",
                    "/home/remus/logs/phins_std.log",
                    "/home/remus/logs/remus.log",
                    "/home/remus/missions/mission.rmf",
                ],
            },
            {
                "label": "Kraken",
                "host": "192.168.20.37", #SN005 Kraken = 192.168.20.17
                "port": 22,
                "username": "kraken",
                "password": "Kraken",
                "remote_paths": [
                    "/kraken/receiver/RTSAS.xml",
                    "/kraken/receiver/RTSAS.ini",
                    "/kraken/receiver/RTSAS.log",
                ],
            },
        ],
    },
    "Mahi SN402 Imaging": {
        "serial_number": "SN402",
        "sources": [
            {
                "label": "Vehicle",
                "host": "192.168.20.30",
                "port": 22,
                "username": "remus",
                "password": "hydroid",
                "remote_paths": [
                    "/home/remus/data/remus.rlf",
                    "/home/remus/data/adcp.dat",
                    "/home/remus/data/gps.dat",
                    "/home/remus/bin/remus.out",
                    "/home/remus/config/adcp.txt",
                    "/home/remus/config/remus_v.ini",
                    "/home/remus/logs/phins_raw.log",
                    "/home/remus/logs/phins_std.log",
                    "/home/remus/logs/remus.log",
                    "/home/remus/missions/mission.rmf",
                ],
            },
            {
                "label": "Backseat",
                "host": "192.168.20.36",
                "port": 22,
                "username": "remus",
                "password": "whoi-remus",
                "remote_paths": [
                    "/home/remus/profiles.yaml",
                    "/home/remus/voyis_params.yaml",
                    {"path": "/home/remus/phins_logs", "selection": "latest_day_files"},
                    {"path": "/home/remus/remus_bags", "selection": "latest_day_folder"},
                ],
            },
        ],
    }, 
    "Mahi SN402 SAS": {
        "serial_number": "SN402",
        "sources": [
            {
                "label": "Vehicle",
                "host": "192.168.20.30",
                "port": 22,
                "username": "remus",
                "password": "hydroid",
                "remote_paths": [
                    "/home/remus/data/remus.rlf",
                    "/home/remus/data/adcp.dat",
                    "/home/remus/data/gps.dat",
                    "/home/remus/bin/remus.out",
                    "/home/remus/config/adcp.txt",
                    "/home/remus/config/remus_v.ini",
                    "/home/remus/logs/phins_raw.log",
                    "/home/remus/logs/phins_std.log",
                    "/home/remus/logs/remus.log",
                    "/home/remus/missions/mission.rmf",
                ],
            },
            {
                "label": "Kraken",
                "host": "192.168.20.37", #SN005 Kraken = 192.168.20.17
                "port": 22,
                "username": "kraken",
                "password": "Kraken",
                "remote_paths": [
                    "/kraken/receiver/RTSAS.xml",
                    "/kraken/receiver/RTSAS.ini",
                    "/kraken/receiver/RTSAS.log", 
                ],
            },
        ],    
    },
}

# If False, a single file failure is logged and transfer continues.
FAIL_FAST_ON_FILE_ERROR = False

# Retry behavior for transient connection drops.
SOURCE_CONNECT_RETRIES = 3
FILE_DOWNLOAD_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2


@dataclass
class TransferSummary:
    files_total: int = 0
    files_done: int = 0
    files_failed: int = 0
    files_skipped: int = 0
    bytes_total: int = 0
    bytes_done: int = 0


def safe_filename(text: str) -> str:
    """Sanitize text for Windows file naming."""
    sanitized = re.sub(r"[<>:\"/\\|?*]", "-", text.strip())
    sanitized = re.sub(r"\s+", "", sanitized)
    return sanitized


def format_size(num_bytes: int) -> str:
    """Format bytes into human-readable units (KB/MB/GB)."""
    size = float(max(0, num_bytes))
    units = ["B", "KB", "MB", "GB", "TB"]
    unit = units[0]
    for candidate in units:
        unit = candidate
        if size < 1024.0 or candidate == units[-1]:
            break
        size /= 1024.0

    if unit == "B":
        return f"{int(size)} {unit}"
    return f"{size:.2f} {unit}"


def extract_date_token(text: str) -> str | None:
    """Extract YYYY-MM-DD token from a filename/path segment."""
    match = re.search(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)", text)
    return match.group(1) if match else None


def extract_datetime_sort_key(text: str) -> tuple:
    """Build sortable key from embedded date/time like 2026-06-08_01-34-14."""
    match = re.search(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?:[_-](\d{2})-(\d{2})-(\d{2}))?", text)
    if not match:
        return ("", "00", "00", "00", text)

    date_part = match.group(1)
    hh = match.group(2) or "00"
    mm = match.group(3) or "00"
    ss = match.group(4) or "00"
    return (date_part, hh, mm, ss, text)


class R620VehicleDataDownloaderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("R620_VehicleData_Downloader")
        self.root.geometry("760x460")

        self.ui_queue: queue.Queue = queue.Queue()
        self.transfer_thread: threading.Thread | None = None
        self.is_transferring = False

        self.summary = TransferSummary()
        self.had_failures = False
        self.conflict_policy = "ask"
        self.transfer_started_at: float | None = None

        self._build_ui()
        self.root.after(100, self._process_ui_queue)

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}

        frame = ttk.Frame(self.root)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Vehicle").grid(row=0, column=0, sticky="w", **pad)
        self.vehicle_var = tk.StringVar(value=list(VEHICLE_CONFIGS.keys())[0])
        self.vehicle_combo = ttk.Combobox(
            frame,
            textvariable=self.vehicle_var,
            values=list(VEHICLE_CONFIGS.keys()),
            state="readonly",
            width=30,
        )
        self.vehicle_combo.grid(row=0, column=1, sticky="we", **pad)
        self.vehicle_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_prefix_preview())

        ttk.Label(frame, text="Output Directory").grid(row=1, column=0, sticky="w", **pad)
        self.output_var = tk.StringVar()
        self.output_entry = ttk.Entry(frame, textvariable=self.output_var)
        self.output_entry.grid(row=1, column=1, sticky="we", **pad)
        ttk.Button(frame, text="Browse", command=self._browse_output).grid(
            row=1, column=2, sticky="we", **pad
        )

        ttk.Label(frame, text="Mission Name").grid(row=2, column=0, sticky="w", **pad)
        self.mission_var = tk.StringVar()
        self.mission_var.trace_add("write", lambda *_: self._update_prefix_preview())
        ttk.Entry(frame, textvariable=self.mission_var).grid(row=2, column=1, sticky="we", **pad)

        ttk.Label(frame, text="Dive Name").grid(row=3, column=0, sticky="w", **pad)
        self.dive_var = tk.StringVar()
        self.dive_var.trace_add("write", lambda *_: self._update_prefix_preview())
        ttk.Entry(frame, textvariable=self.dive_var).grid(row=3, column=1, sticky="we", **pad)

        self.prefix_preview_var = tk.StringVar(value="Prefix Preview: <Mission>_<Dive>_<Serial>")
        ttk.Label(frame, textvariable=self.prefix_preview_var).grid(
            row=4, column=0, columnspan=3, sticky="w", padx=10, pady=(0, 6)
        )

        self.start_button = ttk.Button(frame, text="Start Download", command=self._start_transfer)
        self.start_button.grid(row=5, column=1, sticky="we", **pad)

        self.progress = ttk.Progressbar(frame, orient="horizontal", mode="determinate", maximum=100)
        self.progress.grid(row=6, column=0, columnspan=3, sticky="we", padx=10, pady=(16, 6))

        self.progress_label_var = tk.StringVar(value="Ready")
        ttk.Label(frame, textvariable=self.progress_label_var).grid(
            row=7, column=0, columnspan=3, sticky="w", padx=10, pady=(0, 8)
        )

        ttk.Label(frame, text="Transfer Log").grid(row=8, column=0, sticky="w", **pad)
        self.log_text = tk.Text(frame, height=12, wrap="word")
        self.log_text.grid(row=9, column=0, columnspan=3, sticky="nsew", padx=10, pady=(0, 10))

        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(9, weight=1)
        self._update_prefix_preview()

    def _browse_output(self) -> None:
        chosen = filedialog.askdirectory(title="Select Output Folder")
        if chosen:
            self.output_var.set(chosen)

    def _start_transfer(self) -> None:
        if self.is_transferring:
            return

        if importlib.util.find_spec("paramiko") is None:
            messagebox.showerror(
                "Missing Dependency",
                "Paramiko is required for SFTP. Install with: pip install paramiko",
            )
            return

        vehicle_name = self.vehicle_var.get().strip()
        output_dir = self.output_var.get().strip()
        mission = self.mission_var.get().strip()
        dive = self.dive_var.get().strip()

        if vehicle_name not in VEHICLE_CONFIGS:
            messagebox.showerror("Config Error", "Selected vehicle is not configured.")
            return

        if not output_dir:
            messagebox.showerror("Input Error", "Select an output directory.")
            return

        if not os.path.isdir(output_dir):
            messagebox.showerror("Input Error", "Output directory does not exist.")
            return

        if not mission or not dive:
            messagebox.showerror("Input Error", "Mission Name and Dive Name are required.")
            return

        serial = self._get_vehicle_serial(vehicle_name)
        if not serial:
            messagebox.showerror(
                "Config Error",
                "Selected vehicle is missing serial_number in VEHICLE_CONFIGS.",
            )
            return

        mission_clean = safe_filename(mission)
        dive_clean = safe_filename(dive)
        serial_clean = safe_filename(serial)
        if not mission_clean or not dive_clean or not serial_clean:
            messagebox.showerror(
                "Input Error",
                "Mission/Dive/Serial contain only invalid characters.",
            )
            return

        prefix = f"{mission_clean}_{dive_clean}_{serial_clean}"

        self.summary = TransferSummary()
        self.had_failures = False
        self.conflict_policy = "ask"
        self.transfer_started_at = time.time()
        self.progress["value"] = 0
        self.progress_label_var.set("Starting transfer...")
        self._append_log("=" * 60)
        self._append_log(f"Vehicle: {vehicle_name}")
        self._append_log(f"Output: {output_dir}")
        self._append_log(f"Prefix: {prefix}")

        self.is_transferring = True
        self.start_button.configure(state="disabled")

        vehicle_cfg = VEHICLE_CONFIGS[vehicle_name]
        self.transfer_thread = threading.Thread(
            target=self._transfer_worker,
            args=(vehicle_cfg, output_dir, prefix),
            daemon=True,
        )
        self.transfer_thread.start()

    def _get_vehicle_serial(self, vehicle_name: str) -> str:
        vehicle_cfg = VEHICLE_CONFIGS.get(vehicle_name, {})
        serial = str(vehicle_cfg.get("serial_number", "")).strip()
        if serial:
            return serial

        # Fallback: infer from display name if needed (e.g., "Wahoo SN401").
        match = re.search(r"\bSN\d+\b", vehicle_name.upper())
        return match.group(0) if match else ""

    def _update_prefix_preview(self) -> None:
        vehicle_name = self.vehicle_var.get().strip()
        mission = self.mission_var.get().strip()
        dive = self.dive_var.get().strip()
        serial = self._get_vehicle_serial(vehicle_name)

        mission_part = safe_filename(mission) if mission else "<Mission>"
        dive_part = safe_filename(dive) if dive else "<Dive>"
        serial_part = safe_filename(serial) if serial else "<Serial>"

        self.prefix_preview_var.set(
            f"Prefix Preview: {mission_part}_{dive_part}_{serial_part}"
        )

    def _transfer_worker(self, vehicle_cfg: dict, output_dir: str, prefix: str) -> None:
        paramiko = importlib.import_module("paramiko")
        try:
            sources = vehicle_cfg.get("sources")
            if not sources:
                # Backward compatibility with older single-source config blocks.
                if all(k in vehicle_cfg for k in ("host", "username", "password", "remote_paths")):
                    sources = [
                        {
                            "label": "Primary",
                            "host": vehicle_cfg["host"],
                            "port": vehicle_cfg.get("port", 22),
                            "username": vehicle_cfg["username"],
                            "password": vehicle_cfg["password"],
                            "remote_paths": vehicle_cfg["remote_paths"],
                        }
                    ]
                else:
                    raise RuntimeError("No sources configured for this vehicle.")

            source_plans: list[tuple[dict, list[str]]] = []
            bytes_total = 0

            for source in sources:
                source_label = source.get("label", source.get("host", "Source"))
                ssh_client = None
                sftp = None
                try:
                    ssh_client, sftp = self._open_source_session(paramiko, source)
                    self.ui_queue.put(
                        {
                            "type": "log",
                            "text": f"Connected to {source_label} ({source['host']})",
                        }
                    )

                    remote_targets = source.get("remote_paths", [])
                    if not remote_targets:
                        self.ui_queue.put(
                            {
                                "type": "log",
                                "text": f"No remote_paths configured for {source_label}; skipping.",
                            }
                        )
                        continue

                    all_files: list[tuple[str, str]] = []
                    for target in remote_targets:
                        all_files.extend(self._expand_remote_target(sftp, target))

                    # Dedupe by remote path, preserving the anchor for each path.
                    seen_paths: dict[str, str] = {}
                    for path, anchor in all_files:
                        if path not in seen_paths:
                            seen_paths[path] = anchor
                    unique_files = sorted(seen_paths.items())
                    if not unique_files:
                        self.ui_queue.put(
                            {
                                "type": "log",
                                "text": f"No files found for {source_label}; skipping.",
                            }
                        )
                        continue

                    source_plans.append((source, unique_files))
                    source_bytes = sum(max(self._remote_size(sftp, p), 0) for p, _ in unique_files)
                    bytes_total += source_bytes

                    self.ui_queue.put(
                        {
                            "type": "log",
                            "text": (
                                f"Discovered {len(unique_files)} files from {source_label} "
                                f"({format_size(source_bytes)})."
                            ),
                        }
                    )

                except Exception as source_exc:
                    self.had_failures = True
                    detailed = self._format_exception(
                        source_exc,
                        context=(
                            f"Source discovery failed for source={source_label} "
                            f"host={source.get('host', 'unknown')}"
                        ),
                    )
                    self.ui_queue.put({"type": "log", "text": detailed})
                    # Keep going so other configured sources still run.
                    continue

                finally:
                    if sftp is not None:
                        try:
                            sftp.close()
                        except Exception:
                            pass
                    if ssh_client is not None:
                        try:
                            ssh_client.close()
                        except Exception:
                            pass

            if not source_plans:
                raise RuntimeError("No files found from configured sources.")

            self.summary.files_total = sum(len(files) for _, files in source_plans)
            self.summary.bytes_total = bytes_total

            self.ui_queue.put(
                {
                    "type": "log",
                    "text": (
                        f"Total files queued: {self.summary.files_total} "
                        f"({format_size(self.summary.bytes_total)} total)."
                    ),
                }
            )

            for source, remote_files in source_plans:
                source_label = source.get("label", source.get("host", "Source"))
                ssh_client = None
                sftp = None
                try:
                    ssh_client, sftp = self._open_source_session(paramiko, source)
                    self.ui_queue.put(
                        {
                            "type": "log",
                            "text": (
                                f"Download session opened for {source_label} "
                                f"({len(remote_files)} file(s))"
                            ),
                        }
                    )

                    for remote_file, anchor in remote_files:
                        try:
                            retry_count = 0
                            while True:
                                try:
                                    downloaded = self._download_one_file(
                                        sftp,
                                        remote_file,
                                        output_dir,
                                        prefix,
                                        source_label,
                                        anchor=anchor,
                                    )
                                    break
                                except Exception as download_exc:
                                    if (
                                        self._is_connection_error(download_exc)
                                        and retry_count < FILE_DOWNLOAD_RETRIES
                                    ):
                                        retry_count += 1
                                        self.ui_queue.put(
                                            {
                                                "type": "log",
                                                "text": (
                                                    f"Connection dropped while downloading {remote_file}. "
                                                    f"Retry {retry_count}/{FILE_DOWNLOAD_RETRIES} for {source_label}."
                                                ),
                                            }
                                        )
                                        self._close_source_session(ssh_client, sftp)
                                        ssh_client, sftp = self._open_source_session(paramiko, source)
                                        self.ui_queue.put(
                                            {
                                                "type": "log",
                                                "text": f"Reconnected to {source_label} ({source['host']}).",
                                            }
                                        )
                                        continue
                                    raise

                            if downloaded:
                                self.summary.files_done += 1
                            else:
                                self.summary.files_skipped += 1
                            self.ui_queue.put({"type": "progress"})
                        except Exception as exc:
                            self.summary.files_failed += 1
                            self.had_failures = True
                            detailed = self._format_exception(
                                exc,
                                context=(
                                    f"Download failed for source={source_label} "
                                    f"host={source.get('host', 'unknown')} file={remote_file}"
                                ),
                            )
                            self.ui_queue.put({"type": "log", "text": detailed})
                            self.ui_queue.put({"type": "progress"})
                            if FAIL_FAST_ON_FILE_ERROR:
                                raise
                finally:
                    self._close_source_session(ssh_client, sftp)

            self.ui_queue.put({"type": "done"})

        except Exception as exc:
            detailed = self._format_exception(exc, context="Transfer worker failed")
            self.ui_queue.put({"type": "error", "text": detailed})

    def _open_source_session(self, paramiko, source: dict):
        source_label = source.get("label", source.get("host", "Source"))
        last_exc = None
        for attempt in range(1, SOURCE_CONNECT_RETRIES + 1):
            ssh_client = None
            sftp = None
            try:
                ssh_client = paramiko.SSHClient()
                ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh_client.connect(
                    hostname=source["host"],
                    port=source.get("port", 22),
                    username=source["username"],
                    password=source["password"],
                    timeout=30,
                    look_for_keys=False,
                    allow_agent=False,
                )
                sftp = ssh_client.open_sftp()
                return ssh_client, sftp
            except Exception as exc:
                last_exc = exc
                self._close_source_session(ssh_client, sftp)
                if attempt < SOURCE_CONNECT_RETRIES:
                    wait_seconds = RETRY_BACKOFF_SECONDS * attempt
                    self.ui_queue.put(
                        {
                            "type": "log",
                            "text": (
                                f"Connection attempt {attempt}/{SOURCE_CONNECT_RETRIES} failed for "
                                f"{source_label} ({source['host']}). Retrying in {wait_seconds}s..."
                            ),
                        }
                    )
                    time.sleep(wait_seconds)
                else:
                    raise RuntimeError(
                        f"Unable to connect to {source_label} ({source['host']}) after "
                        f"{SOURCE_CONNECT_RETRIES} attempts"
                    ) from exc

        raise RuntimeError("Source session open failed") from last_exc

    def _close_source_session(self, ssh_client, sftp) -> None:
        if sftp is not None:
            try:
                sftp.close()
            except Exception:
                pass
        if ssh_client is not None:
            try:
                ssh_client.close()
            except Exception:
                pass

    def _is_connection_error(self, exc: Exception) -> bool:
        if isinstance(exc, (EOFError, OSError, TimeoutError, ConnectionError)):
            return True

        text = f"{type(exc).__name__}: {exc}".lower()
        markers = [
            "server connection dropped",
            "socket is closed",
            "forcibly closed",
            "connection reset",
            "broken pipe",
            "channel closed",
            "eof",
            "timed out",
        ]
        return any(marker in text for marker in markers)

    def _expand_remote_target(self, sftp, target) -> list[tuple[str, str]]:
        selection_mode = ""
        if isinstance(target, dict):
            selection_mode = str(target.get("selection", "")).strip().lower()
            target = str(target.get("path", "")).strip()
        else:
            target = str(target).strip()

        if not target:
            return []

        normalized = posixpath.normpath(target)

        if selection_mode == "latest_day_files":
            return self._expand_latest_day_files(sftp, normalized)

        if selection_mode == "latest_day_folder":
            return self._expand_latest_day_folder(sftp, normalized)

        if self._is_remote_file(sftp, normalized):
            return [(normalized, "")]

        if self._is_remote_dir(sftp, normalized):
            return self._walk_remote_dir(sftp, normalized)

        return []

    def _expand_latest_day_files(self, sftp, remote_dir: str) -> list[tuple[str, str]]:
        """Select all regular files whose names share the most recent date token."""
        try:
            entries = sftp.listdir_attr(remote_dir)
        except Exception:
            return []

        dated_files = []
        for entry in entries:
            if not stat.S_ISREG(entry.st_mode):
                continue
            date_token = extract_date_token(entry.filename)
            if not date_token:
                continue
            dated_files.append((date_token, entry.filename))

        if not dated_files:
            return []

        latest_date = max(date for date, _ in dated_files)
        selected = [
            (posixpath.normpath(posixpath.join(remote_dir, name)), "")
            for date, name in dated_files
            if date == latest_date
        ]
        selected.sort()
        self.ui_queue.put(
            {
                "type": "log",
                "text": (
                    f"Selector latest_day_files chose date {latest_date} "
                    f"in {remote_dir} ({len(selected)} files)."
                ),
            }
        )
        return selected

    def _expand_latest_day_folder(self, sftp, remote_dir: str) -> list[tuple[str, str]]:
        """Select all dated folders from newest date and expand all files within them."""
        try:
            entries = sftp.listdir_attr(remote_dir)
        except Exception:
            return []

        dated_entries = []
        for entry in entries:
            date_token = extract_date_token(entry.filename)
            if not date_token:
                continue
            dated_entries.append((date_token, entry))

        if not dated_entries:
            return []

        # Prefer dated folders over loose files so we always pull companion files
        # that live alongside the bag in the same folder.
        dated_dirs = [(date, entry) for date, entry in dated_entries if stat.S_ISDIR(entry.st_mode)]
        if dated_dirs:
            latest_date = max(date for date, _ in dated_dirs)
            same_day_dirs = [entry for date, entry in dated_dirs if date == latest_date]
            same_day_files = []
        else:
            latest_date = max(date for date, _ in dated_entries)
            same_day_entries = [entry for date, entry in dated_entries if date == latest_date]
            same_day_dirs = []
            same_day_files = [entry for entry in same_day_entries if stat.S_ISREG(entry.st_mode)]

        # Sort by embedded date/time token to keep output deterministic.
        same_day_dirs.sort(key=lambda e: extract_datetime_sort_key(e.filename))
        same_day_files.sort(key=lambda e: extract_datetime_sort_key(e.filename))

        selected_files: list[tuple[str, str]] = []
        if same_day_dirs:
            for entry in same_day_dirs:
                selected_path = posixpath.normpath(posixpath.join(remote_dir, entry.filename))
                # Use selected_path as anchor so files are placed inside a named subfolder.
                selected_files.extend(self._walk_remote_dir(sftp, selected_path, anchor=selected_path))
        else:
            # Fallback for non-directory datasets: include same-day files (flat, no anchor).
            for entry in same_day_files:
                selected_files.append((posixpath.normpath(posixpath.join(remote_dir, entry.filename)), ""))

        self.ui_queue.put(
            {
                "type": "log",
                "text": (
                    f"Selector latest_day_folder chose date {latest_date} in {remote_dir} "
                    f"({len(same_day_dirs)} folder(s), {len(selected_files)} file(s))."
                ),
            }
        )

        return selected_files

    def _walk_remote_dir(self, sftp, remote_dir: str, anchor: str = "") -> list[tuple[str, str]]:
        files: list[tuple[str, str]] = []
        try:
            entries = sftp.listdir_attr(remote_dir)
        except Exception:
            return files

        for entry in entries:
            name = entry.filename
            if name in (".", ".."):
                continue

            child = posixpath.join(remote_dir, name)
            child = posixpath.normpath(child)

            if stat.S_ISREG(entry.st_mode):
                files.append((child, anchor))
            elif stat.S_ISDIR(entry.st_mode):
                files.extend(self._walk_remote_dir(sftp, child, anchor=anchor))

        return files

    def _is_remote_file(self, sftp, path: str) -> bool:
        try:
            return stat.S_ISREG(sftp.stat(path).st_mode)
        except Exception:
            return False

    def _is_remote_dir(self, sftp, path: str) -> bool:
        try:
            return stat.S_ISDIR(sftp.stat(path).st_mode)
        except Exception:
            return False

    def _remote_size(self, sftp, path: str) -> int:
        try:
            return int(sftp.stat(path).st_size)
        except Exception:
            return 0

    def _download_one_file(
        self,
        sftp,
        remote_file: str,
        output_dir: str,
        prefix: str,
        source_label: str,
        anchor: str = "",
    ) -> bool:
        if anchor:
            # Preserve the bag folder structure: files land in <prefix>_<bag_folder_name>/...
            bag_folder_name = posixpath.basename(anchor)
            rel_path = posixpath.relpath(remote_file, anchor)  # e.g. "file.bag" or "sub/file"
            rel_parts = rel_path.split("/")
            local_subdir = os.path.join(output_dir, f"{prefix}_{bag_folder_name}", *rel_parts[:-1])
            local_name = rel_parts[-1]
        else:
            local_subdir = output_dir
            local_name = f"{prefix}_{posixpath.basename(remote_file)}"

        local_path = os.path.join(local_subdir, local_name)
        remote_size, remote_mtime = self._remote_file_info(sftp, remote_file)

        if os.path.exists(local_path):
            action, resolved_path = self._resolve_conflict_action(
                local_path,
                local_subdir,
                local_name,
                remote_size,
                remote_mtime,
                remote_file,
                source_label,
            )
            if action == "skip":
                self.ui_queue.put(
                    {
                        "type": "log",
                        "text": f"Skipped [{source_label}]: {resolved_path}",
                    }
                )
                return False
            local_path = resolved_path

        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        temp_path = local_path + ".part"

        file_size = max(remote_size, 0)

        self.ui_queue.put({"type": "log", "text": f"Downloading [{source_label}]: {remote_file}"})

        attempt_bytes = [0]
        try:
            with open(temp_path, "wb") as out_f:
                previous = [0]

                def progress_callback(transferred: int, _total: int) -> None:
                    delta = max(0, transferred - previous[0])
                    previous[0] = transferred
                    attempt_bytes[0] += delta
                    self.summary.bytes_done += delta
                    self.ui_queue.put({"type": "progress"})

                sftp.getfo(remote_file, out_f, callback=progress_callback)

            os.replace(temp_path, local_path)
        except Exception:
            # Avoid counting partial transferred bytes when a file is retried.
            self.summary.bytes_done = max(0, self.summary.bytes_done - attempt_bytes[0])
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError:
                pass
            raise

        if file_size == 0:
            # If server did not report size, ensure progress still updates per-file.
            self.ui_queue.put({"type": "progress"})

        self.ui_queue.put({"type": "log", "text": f"Saved [{source_label}]: {local_path}"})
        return True

    def _remote_file_info(self, sftp, path: str) -> tuple[int, int]:
        try:
            st = sftp.stat(path)
            return int(getattr(st, "st_size", 0) or 0), int(getattr(st, "st_mtime", 0) or 0)
        except Exception:
            return 0, 0

    def _resolve_conflict_action(
        self,
        local_path: str,
        output_dir: str,
        local_name: str,
        remote_size: int,
        remote_mtime: int,
        remote_file: str,
        source_label: str,
    ) -> tuple[str, str]:
        local_size = 0
        local_mtime = 0
        try:
            local_size = os.path.getsize(local_path)
            local_mtime = int(os.path.getmtime(local_path))
        except OSError:
            pass

        if self.conflict_policy == "ask":
            choice, apply_all = self._prompt_conflict_choice(
                remote_file=remote_file,
                local_path=local_path,
                remote_size=remote_size,
                remote_mtime=remote_mtime,
                local_size=local_size,
                local_mtime=local_mtime,
                source_label=source_label,
            )
            if apply_all:
                self.conflict_policy = choice
            action = choice
        else:
            action = self.conflict_policy

        if action == "overwrite":
            return "overwrite", local_path
        if action == "overwrite_if_newer":
            return ("overwrite", local_path) if remote_mtime > local_mtime else ("skip", local_path)
        if action == "overwrite_if_larger":
            return ("overwrite", local_path) if remote_size > local_size else ("skip", local_path)
        if action == "overwrite_if_newer_or_larger":
            should_overwrite = (remote_mtime > local_mtime) or (remote_size > local_size)
            return ("overwrite", local_path) if should_overwrite else ("skip", local_path)
        if action == "overwrite_if_size_differs":
            return ("overwrite", local_path) if remote_size != local_size else ("skip", local_path)
        if action == "rename":
            return "overwrite", os.path.join(output_dir, self._dedupe_local_name(output_dir, local_name))
        if action == "skip":
            return "skip", local_path

        return "overwrite", local_path

    def _prompt_conflict_choice(
        self,
        remote_file: str,
        local_path: str,
        remote_size: int,
        remote_mtime: int,
        local_size: int,
        local_mtime: int,
        source_label: str,
    ) -> tuple[str, bool]:
        event = threading.Event()
        result: dict = {"choice": "overwrite_if_newer_or_larger", "apply_all": False}
        self.ui_queue.put(
            {
                "type": "conflict_prompt",
                "event": event,
                "result": result,
                "data": {
                    "remote_file": remote_file,
                    "local_path": local_path,
                    "remote_size": remote_size,
                    "remote_mtime": remote_mtime,
                    "local_size": local_size,
                    "local_mtime": local_mtime,
                    "source_label": source_label,
                },
            }
        )
        event.wait()
        return result.get("choice", "overwrite_if_newer_or_larger"), bool(result.get("apply_all", False))

    def _show_conflict_dialog(self, data: dict) -> tuple[str, bool]:
        dialog = tk.Toplevel(self.root)
        dialog.title("File already exists")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        outer = ttk.Frame(dialog, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="A file with this name already exists.").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        ttk.Label(outer, text=f"Source: {data['source_label']}").grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Label(outer, text=f"Remote: {data['remote_file']}").grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Label(outer, text=f"Local: {data['local_path']}").grid(row=3, column=0, columnspan=2, sticky="w")
        ttk.Label(
            outer,
            text=f"Remote size: {format_size(data['remote_size'])} ({data['remote_size']:,} bytes)",
        ).grid(row=4, column=0, columnspan=2, sticky="w")
        ttk.Label(
            outer,
            text=f"Local size: {format_size(data['local_size'])} ({data['local_size']:,} bytes)",
        ).grid(row=5, column=0, columnspan=2, sticky="w")
        ttk.Label(outer, text=f"Remote mtime: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(max(0, data['remote_mtime'])))}").grid(row=6, column=0, columnspan=2, sticky="w")
        ttk.Label(outer, text=f"Local mtime: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(max(0, data['local_mtime'])))}").grid(row=7, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(outer, text="Action:").grid(row=8, column=0, sticky="w")
        choice_var = tk.StringVar(value="overwrite_if_newer_or_larger")
        options = [
            ("overwrite_if_newer_or_larger", "Overwrite if source newer or larger (default)"),
            ("overwrite", "Overwrite"),
            ("overwrite_if_newer", "Overwrite if source newer"),
            ("overwrite_if_larger", "Overwrite if source larger"),
            ("overwrite_if_size_differs", "Overwrite if size differs"),
            ("rename", "Rename new file"),
            ("skip", "Skip"),
            ("ask", "Ask for each file"),
        ]
        option_menu = ttk.Combobox(
            outer,
            textvariable=choice_var,
            state="readonly",
            values=[label for _, label in options],
            width=44,
        )
        option_menu.grid(row=8, column=1, sticky="we")
        option_menu.current(0)

        apply_all_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            outer,
            text="Apply this action to all remaining conflicts",
            variable=apply_all_var,
        ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(8, 8))

        selected: dict = {"choice": "overwrite_if_newer_or_larger", "apply_all": True}

        def on_ok() -> None:
            selected_label = option_menu.get()
            mapping = {label: value for value, label in options}
            selected["choice"] = mapping.get(selected_label, "overwrite_if_newer_or_larger")
            selected["apply_all"] = bool(apply_all_var.get())
            dialog.destroy()

        def on_cancel() -> None:
            selected["choice"] = "skip"
            selected["apply_all"] = False
            dialog.destroy()

        button_frame = ttk.Frame(outer)
        button_frame.grid(row=10, column=0, columnspan=2, sticky="e")
        ttk.Button(button_frame, text="OK", command=on_ok).pack(side="right", padx=(8, 0))
        ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side="right")

        outer.columnconfigure(1, weight=1)
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        dialog.wait_window()
        return selected["choice"], selected["apply_all"]

    def _dedupe_local_name(self, output_dir: str, filename: str) -> str:
        base, ext = os.path.splitext(filename)
        candidate = filename
        idx = 1
        while os.path.exists(os.path.join(output_dir, candidate)):
            idx += 1
            candidate = f"{base}_{idx}{ext}"
        return candidate

    def _append_log(self, message: str) -> None:
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        # Echo to terminal so logs are visible outside the GUI window too.
        print(message, flush=True)

    def _format_exception(self, exc: Exception, context: str = "") -> str:
        exc_type = type(exc).__name__
        exc_message = str(exc).strip()
        if not exc_message:
            exc_message = repr(exc)
        if not exc_message:
            exc_message = "No exception message provided by source library"

        traceback_text = traceback.format_exc().strip()
        parts = ["ERROR"]
        if context:
            parts.append(context)
        parts.append(f"{exc_type}: {exc_message}")
        if traceback_text and traceback_text != "NoneType: None":
            parts.append("Traceback:")
            parts.append(traceback_text)
        return "\n".join(parts)

    def _process_ui_queue(self) -> None:
        while True:
            try:
                item = self.ui_queue.get_nowait()
            except queue.Empty:
                break

            item_type = item.get("type")

            if item_type == "log":
                self._append_log(item.get("text", ""))

            elif item_type == "conflict_prompt":
                event = item["event"]
                result = item["result"]
                data = item["data"]
                try:
                    choice, apply_all = self._show_conflict_dialog(data)
                    result["choice"] = choice
                    result["apply_all"] = apply_all
                finally:
                    event.set()

            elif item_type == "progress":
                self._refresh_progress()

            elif item_type == "error":
                self._append_log(f"ERROR: {item.get('text', 'Unknown error')}")
                self.progress_label_var.set("Transfer failed")
                self.is_transferring = False
                self.start_button.configure(state="normal")
                err = item.get("text", "Unknown error")
                messagebox.showerror("Transfer Error", err if err.strip() else "Unknown error")

            elif item_type == "done":
                self._refresh_progress(final=True)
                self._append_log("Transfer completed.")
                if self.had_failures:
                    self.progress_label_var.set("Transfer complete with errors")
                    self._append_log(
                        f"Completed with failures: {self.summary.files_failed} file(s) failed."
                    )
                else:
                    self.progress_label_var.set("Transfer complete")
                self.is_transferring = False
                self.start_button.configure(state="normal")
                if self.had_failures:
                    messagebox.showwarning(
                        "Done with Errors",
                        (
                            "SFTP transfer finished with errors.\n\n"
                            f"Succeeded: {self.summary.files_done}\n"
                            f"Failed: {self.summary.files_failed}"
                        ),
                    )
                else:
                    messagebox.showinfo("Done", "SFTP transfer completed successfully.")

        self.root.after(100, self._process_ui_queue)

    def _refresh_progress(self, final: bool = False) -> None:
        bytes_total = self.summary.bytes_total
        bytes_done = self.summary.bytes_done

        if final:
            self.progress["value"] = 100
        elif bytes_total > 0:
            self.progress["value"] = min(100, (bytes_done / bytes_total) * 100)
        else:
            # Fallback progress mode if server does not provide sizes.
            files_total = max(self.summary.files_total, 1)
            self.progress["value"] = min(100, (self.summary.files_done / files_total) * 100)

        elapsed = 0.0
        if self.transfer_started_at is not None:
            elapsed = max(0.001, time.time() - self.transfer_started_at)
        avg_rate_bps = int(bytes_done / elapsed) if elapsed > 0 else 0

        self.progress_label_var.set(
            "Files: "
            f"{self.summary.files_done}/{self.summary.files_total} "
            f"(failed: {self.summary.files_failed}, skipped: {self.summary.files_skipped}) | "
            "Data: "
            f"{format_size(bytes_done)}/{format_size(bytes_total)} | "
            "Rate: "
            f"{format_size(avg_rate_bps)}/s"
        )


def main() -> None:
    root = tk.Tk()
    app = R620VehicleDataDownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
