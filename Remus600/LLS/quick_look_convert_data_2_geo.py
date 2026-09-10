"""
quick_look_convert_data_2_geo.py
---------------------
Author: Mike Bollinger
Last Updated: 2026-06-07

Quick-look georeferencing of LLS .xyz files.

Reads every *.xyz in BASE_DIR/lls_raw, sub-samples timestamps by TIME_SKIP,
applies the sensor-to-ENU rotation using vehicle navigation data, and writes
geo_<stem>.xyz to BASE_DIR/quick_look/LLS/geo/.

Navigation data is read from pre-processed PHINS CSV files in
BASE_DIR/processing/vehicle/:
  ATITUD.csv, HEHDT.csv, UTMWGS.csv, DEPIN_.csv,
  LOGDVL.csv, SPEED_.csv, POSITI.csv

USAGE:
    Edit BASE_DIR, OFFSETS, TIME_OFFSET, and TIME_SKIP below to match your
    dive, then run:
        python quick_look_convert_data_2_geo.py

INPUTS:
    - Raw LLS .xyz files in BASE_DIR/lls_raw.
    - Pre-processed PHINS navigation CSVs in BASE_DIR/processing/vehicle/.

OUTPUTS:
    Georeferenced geo_<stem>.xyz point files written to
    BASE_DIR/quick_look/LLS/geo/.
"""

import os
import csv
import glob
import datetime
import re
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR    = "E:\EN2501_LLS\DIVE033_Stokey"

# Sensor-to-IMU lever-arm offsets
# [X_offset, Y_offset, Z_offset, Pitch_offset_deg, Roll_offset_deg, Heading_offset_deg]
OFFSETS     = [0.091, 0.996, -0.16, 0.0, 0.0, 180.0]

# Time offset applied to navigation timestamps (seconds)
TIME_OFFSET = 0.0

# Process only every N-th unique timestamp (1 = all, 50 = every 50th)
TIME_SKIP   = 10

# ---------------------------------------------------------------------------
# Derived paths
# ---------------------------------------------------------------------------
LLS_DIR    = os.path.join(BASE_DIR, "lls_raw")
VEHICLE_DIR = os.path.join(BASE_DIR, "vehicle_raw")
NAV_DIR    = os.path.join(BASE_DIR, "processing", "vehicle")
OUTPUT_DIR  = os.path.join(BASE_DIR, "geo")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ===========================================================================
# Helper: Lat/Lon → UTM  (no external projection library required)
# ===========================================================================
def lat_lon_to_utm_vectorized(latitudes, longitudes):
    """Vectorised WGS-84 lat/lon → UTM (assumes single zone)."""
    a  = 6378137.0
    f  = 1 / 298.257223563
    k0 = 0.9996

    lat0, lon0  = latitudes.iloc[0], longitudes.iloc[0]
    zone_number = int((lon0 + 180) / 6) + 1
    is_northern = lat0 >= 0
    lon_origin  = (zone_number - 1) * 6 - 180 + 3

    lat_rad        = np.radians(latitudes.values)
    lon_rad        = np.radians(longitudes.values)
    lon_origin_rad = np.radians(lon_origin)

    e  = np.sqrt(f * (2 - f))
    N  = a / np.sqrt(1 - e**2 * np.sin(lat_rad)**2)
    T  = np.tan(lat_rad)**2
    C  = (e**2 / (1 - e**2)) * np.cos(lat_rad)**2
    A  = np.cos(lat_rad) * (lon_rad - lon_origin_rad)
    e2 = e**2 / (1 - e**2)

    M = a * (
        (1 - e**2/4 - 3*e**4/64 - 5*e**6/256) * lat_rad
        - (3*e**2/8 + 3*e**4/32 + 45*e**6/1024) * np.sin(2*lat_rad)
        + (15*e**4/256 + 45*e**6/1024) * np.sin(4*lat_rad)
        - (35*e**6/3072) * np.sin(6*lat_rad)
    )

    eastings = k0 * N * (
        A + (1-T+C)*A**3/6
        + (5-18*T+T**2+72*C-58*e2)*A**5/120
    ) + 500000

    northings = k0 * (
        M + N * np.tan(lat_rad) * (
            A**2/2
            + (5-T+9*C+4*C**2)*A**4/24
            + (61-58*T+T**2+600*C-330*e2)*A**6/720
        )
    )
    if not is_northern:
        northings += 10_000_000.0

    zone_letters     = "CDEFGHJKLMNPQRSTUVWXX"
    zone_letter      = zone_letters[int((lat0 + 80) / 8)]
    zone_numbers_arr = np.full(len(eastings), zone_number, dtype=int)
    zone_letters_arr = np.full(len(eastings), zone_letter, dtype=object)
    return eastings, northings, zone_numbers_arr, zone_letters_arr


# ===========================================================================
# PHINS binary parser – produces the same CSVs that load_nav expects
# ===========================================================================
def _verify_nmea_checksum(row_str):
    if not row_str.startswith('$') or '*' not in row_str:
        return False
    data, checksum_str = row_str[1:].split('*', 1)
    calc = 0
    for ch in data:
        calc ^= ord(ch)
    try:
        expected = int(checksum_str[:2], 16)
    except ValueError:
        return False
    return calc == expected


def _read_phins_binary(file_path):
    """Parse a phinsdata_*.bin file and return a dict of DataFrames."""
    match = re.search(r'phinsdata_(\d{8})', os.path.basename(file_path))
    if not match:
        raise ValueError(f"Cannot extract date from: {file_path}")
    date = match.group(1)

    frames = {
        'DEPIN_': {'Depth': [], 'Time': [], 'Time_REF': []},
        'GPSIN_': {'Latitude': [], 'Longitude': [], 'Altitude': [],
                   'Time': [], 'Quality': [], 'Time_REF': []},
        'ATITUD': {'Roll': [], 'Pitch': [], 'Time_REF': []},
        'UTMWGS': {'LatZone': [], 'LonZone': [], 'Easting': [],
                   'Northing': [], 'Altitude': [], 'Time_REF': []},
        'SPEED_': {'EastSpeed': [], 'NorthSpeed': [],
                   'UpSpeed': [], 'Velocity': [], 'Time_REF': []},
        'POSITI': {'Latitude': [], 'Longitude': [], 'Altitude': [], 'Time_REF': []},
        'LOGDVL': {'SoundVelocity': [], 'Compensation': [],
                   'DVL_Distance_2btm': [], 'Time_REF': []},
        'HEHDT':  {'Heading': [], 'Time_REF': []},
        'HETHS':  {'Heading': [], 'Mode': [], 'Time_REF': []},
        'HEAVE_': {'Surge': [], 'Sway': [], 'Heave': [], 'Time_REF': []},
        'STDPOS': {'Latitude': [], 'Longitude': [], 'Altitude': [], 'Time_REF': []},
        'STDSPD': {'NorthSpeed': [], 'EastSpeed': [], 'VerticalSpeed': [], 'Time_REF': []},
        'STDHRP': {'HeadingSTD': [], 'RollSTD': [], 'PitchSTD': [], 'Time_REF': []},
    }

    TIME = ""
    Time_Last = 0

    with open(file_path, 'rb') as fh:
        decoded = fh.read().replace(b'\x00', b'').decode('utf-8', errors='replace')

    for row in csv.reader(decoded.splitlines()):
        row_str = ','.join(row)
        if not _verify_nmea_checksum(row_str):
            continue
        row = [col.split('*')[0] for col in row]
        if len(row) < 2:
            continue
        ident = row[0]

        if ident == '$PIXSE':
            id2 = row[1]
            if id2 == 'TIME__' and len(row) >= 3:
                try:
                    t = float(row[2])
                except ValueError:
                    continue
                if t == 0:
                    continue
                if t < Time_Last and Time_Last > 235900:
                    dt = datetime.datetime.strptime(date, "%Y%m%d") + datetime.timedelta(days=1)
                    date = dt.strftime("%Y%m%d")
                Time_Last = t
                TIME = date + " " + row[2]
            elif id2 == 'DEPIN_' and len(row) >= 4:
                frames['DEPIN_']['Depth'].append(float(row[2]))
                frames['DEPIN_']['Time'].append(float(row[3]))
                frames['DEPIN_']['Time_REF'].append(TIME)
            elif id2 == 'GPSIN_' and len(row) >= 7:
                if float(row[2]) == 0 and float(row[3]) == 0:
                    continue
                frames['GPSIN_']['Latitude'].append(float(row[2]))
                frames['GPSIN_']['Longitude'].append(float(row[3]))
                frames['GPSIN_']['Altitude'].append(float(row[4]))
                frames['GPSIN_']['Time'].append(float(row[5]))
                frames['GPSIN_']['Quality'].append(int(row[6]))
                frames['GPSIN_']['Time_REF'].append(TIME)
            elif id2 == 'ATITUD' and len(row) >= 4:
                frames['ATITUD']['Roll'].append(float(row[2]))
                frames['ATITUD']['Pitch'].append(float(row[3]))
                frames['ATITUD']['Time_REF'].append(TIME)
            elif id2 == 'UTMWGS' and len(row) >= 7:
                frames['UTMWGS']['LatZone'].append(row[2])
                frames['UTMWGS']['LonZone'].append(int(row[3]))
                frames['UTMWGS']['Easting'].append(float(row[4]))
                frames['UTMWGS']['Northing'].append(float(row[5]))
                frames['UTMWGS']['Altitude'].append(float(row[6]))
                frames['UTMWGS']['Time_REF'].append(TIME)
            elif id2 == 'SPEED_' and len(row) >= 5:
                e, n, u = float(row[2]), float(row[3]), float(row[4])
                frames['SPEED_']['EastSpeed'].append(e)
                frames['SPEED_']['NorthSpeed'].append(n)
                frames['SPEED_']['UpSpeed'].append(u)
                frames['SPEED_']['Velocity'].append((e**2 + n**2) ** 0.5)
                frames['SPEED_']['Time_REF'].append(TIME)
            elif id2 == 'POSITI' and len(row) >= 5:
                frames['POSITI']['Latitude'].append(float(row[2]))
                frames['POSITI']['Longitude'].append(float(row[3]))
                frames['POSITI']['Altitude'].append(float(row[4]))
                frames['POSITI']['Time_REF'].append(TIME)
            elif id2 == 'LOGDVL' and len(row) >= 5:
                if float(row[2]) > 0:
                    frames['LOGDVL']['SoundVelocity'].append(float(row[2]))
                    frames['LOGDVL']['Compensation'].append(float(row[3]))
                    frames['LOGDVL']['DVL_Distance_2btm'].append(float(row[4]))
                    frames['LOGDVL']['Time_REF'].append(TIME)
            elif id2 == 'HEAVE_' and len(row) >= 5:
                frames['HEAVE_']['Surge'].append(float(row[2]))
                frames['HEAVE_']['Sway'].append(float(row[3]))
                frames['HEAVE_']['Heave'].append(float(row[4]))
                frames['HEAVE_']['Time_REF'].append(TIME)
            elif id2 == 'STDPOS' and len(row) >= 5:
                frames['STDPOS']['Latitude'].append(float(row[2]))
                frames['STDPOS']['Longitude'].append(float(row[3]))
                frames['STDPOS']['Altitude'].append(float(row[4]))
                frames['STDPOS']['Time_REF'].append(TIME)
            elif id2 == 'STDSPD' and len(row) >= 5:
                frames['STDSPD']['NorthSpeed'].append(float(row[2]))
                frames['STDSPD']['EastSpeed'].append(float(row[3]))
                frames['STDSPD']['VerticalSpeed'].append(float(row[4]))
                frames['STDSPD']['Time_REF'].append(TIME)
            elif id2 == 'STDHRP' and len(row) >= 5:
                frames['STDHRP']['HeadingSTD'].append(float(row[2]))
                frames['STDHRP']['RollSTD'].append(float(row[3]))
                frames['STDHRP']['PitchSTD'].append(float(row[4]))
                frames['STDHRP']['Time_REF'].append(TIME)
        elif ident == '$HEHDT' and len(row) >= 2:
            try:
                frames['HEHDT']['Heading'].append(float(row[1]))
                frames['HEHDT']['Time_REF'].append(TIME)
            except ValueError:
                pass
        elif ident == '$HETHS' and len(row) >= 3:
            try:
                frames['HETHS']['Heading'].append(float(row[1]))
                frames['HETHS']['Mode'].append(row[2])
                frames['HETHS']['Time_REF'].append(TIME)
            except ValueError:
                pass

    # Convert lists → DataFrames, parse Date_Time
    for key, d in frames.items():
        df = pd.DataFrame(d)
        if 'Time_REF' in df.columns:
            df['Date_Time'] = pd.to_datetime(
                df['Time_REF'], format='%Y%m%d %H%M%S.%f', errors='coerce'
            )
            df.drop(columns=['Time_REF'], inplace=True)
        frames[key] = df

    return frames


def _remove_outliers(series, time_series, max_change_rate=15, variance_max=20):
    """Return a boolean mask of outliers (True = outlier)."""
    time_diff = time_series.diff().dt.total_seconds().abs()
    rate       = series.diff().abs() / time_diff
    by_rate    = rate > max_change_rate
    rolling_mean = series.rolling(window=50, center=True).mean()
    by_variance  = (series - rolling_mean).abs() > variance_max
    return by_rate | by_variance


def ensure_phins_csvs(nav_dir, vehicle_raw_dir):
    """
    Check that the required PHINS CSV files exist in nav_dir.
    If not, locate a phinsdata_*.bin in vehicle_raw_dir, parse it,
    apply basic outlier removal, and save the CSVs.
    """
    required = ['ATITUD.csv', 'HEHDT.csv', 'UTMWGS.csv',
                'DEPIN_.csv', 'LOGDVL.csv', 'SPEED_.csv', 'POSITI.csv']

    missing = [f for f in required if not os.path.exists(os.path.join(nav_dir, f))]
    if not missing:
        print("  PHINS CSVs already exist – skipping binary parse.")
        return

    print(f"  Missing CSVs: {missing}")
    bin_files = glob.glob(os.path.join(vehicle_raw_dir, 'phinsdata_*.bin'))
    if not bin_files:
        raise FileNotFoundError(
            f"No phinsdata_*.bin found in {vehicle_raw_dir} "
            f"and required CSVs are missing from {nav_dir}"
        )
    bin_path = bin_files[0]
    print(f"  Parsing PHINS binary: {os.path.basename(bin_path)} ...")

    frames = _read_phins_binary(bin_path)

    # outlier removal on depth and DVL
    if not frames['DEPIN_'].empty and 'Depth' in frames['DEPIN_'].columns:
        mask = _remove_outliers(frames['DEPIN_']['Depth'], frames['DEPIN_']['Date_Time'])
        frames['DEPIN_'] = frames['DEPIN_'][~mask]

    if not frames['LOGDVL'].empty and 'DVL_Distance_2btm' in frames['LOGDVL'].columns:
        mask = _remove_outliers(frames['LOGDVL']['DVL_Distance_2btm'], frames['LOGDVL']['Date_Time'])
        frames['LOGDVL'] = frames['LOGDVL'][~mask]

    os.makedirs(nav_dir, exist_ok=True)
    for key, df in frames.items():
        if not df.empty:
            out = os.path.join(nav_dir, f"{key}.csv")
            df.to_csv(out, index=False)
            print(f"    Saved {key}.csv  ({len(df):,} rows)")

    print("  PHINS CSV export complete.")


# ===========================================================================
# Helper: Load and interpolate navigation data
# ===========================================================================
def _to_timestamp(series):
    return series.apply(lambda x: x.timestamp() if pd.notnull(x) else np.nan)


def load_nav(nav_dir, time_offset_sec):
    """
    Loads pre-processed PHINS CSV files and returns a DataFrame with columns:
        Timestamp, AUV_Roll, AUV_Pitch, AUV_Heading,
        AUV_Northing, AUV_Easting, AUV_Depth,
        AUV_Altitude, AUV_Velocity, AUV_Latitude, AUV_Longitude
    Sorted by Timestamp.
    """
    td = pd.Timedelta(seconds=time_offset_sec)

    def read_csv_utc(path):
        df = pd.read_csv(path)
        df['Date_Time'] = (
            pd.to_datetime(df['Date_Time'], format='%Y-%m-%d %H:%M:%S.%f')
              .dt.tz_localize('UTC') + td
        )
        df.dropna(subset=['Date_Time'], inplace=True)
        df['Timestamp'] = _to_timestamp(df['Date_Time'])
        return df.sort_values('Timestamp')

    att = read_csv_utc(os.path.join(nav_dir, 'ATITUD.csv'))
    hdg = read_csv_utc(os.path.join(nav_dir, 'HEHDT.csv'))
    utm = read_csv_utc(os.path.join(nav_dir, 'UTMWGS.csv'))
    dep = read_csv_utc(os.path.join(nav_dir, 'DEPIN_.csv'))
    dvl = read_csv_utc(os.path.join(nav_dir, 'LOGDVL.csv'))
    spd = read_csv_utc(os.path.join(nav_dir, 'SPEED_.csv'))
    pos = read_csv_utc(os.path.join(nav_dir, 'POSITI.csv'))

    # reference timeline: attitude (highest rate)
    nav = att[['Timestamp']].copy()
    nav['AUV_Roll']      = att['Roll'].values
    nav['AUV_Pitch']     = att['Pitch'].values
    nav['AUV_Heading']   = np.interp(nav['Timestamp'], hdg['Timestamp'], hdg['Heading'])
    nav['AUV_Northing']  = np.interp(nav['Timestamp'], utm['Timestamp'], utm['Northing'])
    nav['AUV_Easting']   = np.interp(nav['Timestamp'], utm['Timestamp'], utm['Easting'])
    nav['AUV_Depth']     = -np.interp(nav['Timestamp'], dep['Timestamp'], dep['Depth'])
    nav['AUV_Altitude']  = np.interp(nav['Timestamp'], dvl['Timestamp'], dvl['DVL_Distance_2btm'])
    nav['AUV_Velocity']  = np.interp(nav['Timestamp'], spd['Timestamp'], spd['Velocity'])
    nav['AUV_Latitude']  = np.interp(nav['Timestamp'], pos['Timestamp'], pos['Latitude'])
    nav['AUV_Longitude'] = np.interp(nav['Timestamp'], pos['Timestamp'], pos['Longitude'])

    return nav.sort_values('Timestamp').reset_index(drop=True)


def interp_nav_at(nav_df, timestamps):
    """Interpolate all AUV nav columns to the supplied unix timestamps (float s)."""
    ts   = nav_df['Timestamp'].values
    cols = [c for c in nav_df.columns if c.startswith('AUV_')]
    out  = {}
    for c in cols:
        out[c] = np.interp(timestamps, ts, nav_df[c].values)
    return out


# ===========================================================================
# Helper: ENU conversion (from old_convert_geo.py)
# ===========================================================================
def convert_2_enu(points, offsets, pitch_deg, roll_deg, heading_deg,
                  northing, easting, depth):
    """
    Rotate sensor-frame XYZ points into ENU world coordinates.
    points   : (N,3) array  [x, y, z]
    offsets  : [dx, dy, dz, d_pitch_deg, d_roll_deg, d_heading_deg]
    Returns  : (N,3) array  [easting, northing, depth]
    """
    pr = np.radians(pitch_deg   + offsets[3])
    rr = np.radians(roll_deg    + offsets[4])
    hr = np.radians(heading_deg + offsets[5])

    R_h = np.array([[ np.cos(hr), np.sin(hr), 0, 0],
                    [-np.sin(hr), np.cos(hr), 0, 0],
                    [ 0,          0,          1, 0],
                    [ 0,          0,          0, 1]])

    R_r = np.array([[ np.cos(rr), 0, np.sin(rr), 0],
                    [ 0,          1, 0,           0],
                    [-np.sin(rr), 0, np.cos(rr), 0],
                    [ 0,          0, 0,           1]])

    R_p = np.array([[1, 0,          0,           0],
                    [0, np.cos(pr), -np.sin(pr), 0],
                    [0, np.sin(pr),  np.cos(pr), 0],
                    [0, 0,           0,           1]])

    T = np.array([[1, 0, 0, offsets[0]],
                  [0, 1, 0, offsets[1]],
                  [0, 0, 1, offsets[2]],
                  [0, 0, 0, 1]])

    combined = R_h @ R_r @ R_p @ T

    # homogeneous transform
    N = len(points)
    homo = np.hstack([points, np.ones((N, 1))])      # (N,4)
    rotated = (combined @ homo.T).T                   # (N,4)
    geo = rotated[:, :3] + np.array([easting, northing, depth])
    return geo


# ===========================================================================
# Main processing loop
# ===========================================================================
def process_file(xyz_path, nav_df, offsets, time_skip, output_dir):
    stem      = os.path.splitext(os.path.basename(xyz_path))[0]
    out_path  = os.path.join(output_dir, f"geo_{stem}.xyz")

    print(f"\n  File: {os.path.basename(xyz_path)}")

    # Load raw data
    data = pd.read_csv(
        xyz_path, sep=",", skipinitialspace=True, header=None,
        names=["time", "x", "y", "z", "intensity", "quality"],
        dtype={"time": np.int64, "x": np.float64, "y": np.float64,
               "z": np.float64, "intensity": np.float64, "quality": np.float64},
    )
    data.dropna(inplace=True)
    print(f"  {len(data):,} points loaded")

    unique_times = np.sort(data["time"].unique())
    # Sub-sample: keep every TIME_SKIP-th timestamp
    unique_times = unique_times[::time_skip]
    print(f"  {len(unique_times):,} timestamps after 1-in-{time_skip} sub-sample")

    if len(unique_times) == 0:
        print("  No timestamps to process – skipping file.")
        return

    # Convert LLS unix-microsecond timestamps to POSIX seconds for nav interp
    ts_sec = unique_times / 1e6

    # Interpolate AUV nav to these timestamps
    nav_at = interp_nav_at(nav_df, ts_sec)

    # Build output block
    result_chunks = []
    for i, t in enumerate(unique_times):
        mask       = data["time"].values == t
        pts        = data.loc[mask, ["x", "y", "z"]].values
        intensity  = data.loc[mask, "intensity"].values
        quality    = data.loc[mask, "quality"].values

        geo_pts = convert_2_enu(
            pts, offsets,
            pitch_deg   = -nav_at["AUV_Pitch"][i],
            roll_deg    =  nav_at["AUV_Roll"][i],
            heading_deg =  nav_at["AUV_Heading"][i],
            northing    =  nav_at["AUV_Northing"][i],
            easting     =  nav_at["AUV_Easting"][i],
            depth       =  nav_at["AUV_Depth"][i],
        )

        n      = len(pts)
        times  = np.full(n, t, dtype=np.int64)
        chunk  = np.column_stack([times, geo_pts, intensity, quality])
        result_chunks.append(chunk)

    result = np.vstack(result_chunks)

    # Save: time(int), easting, northing, depth, intensity, quality
    fmt = ["%.0f", "%.4f", "%.4f", "%.4f", "%.0f", "%.0f"]
    np.savetxt(out_path, result, fmt=fmt, delimiter=",")
    print(f"  Saved {len(result):,} points → {out_path}")


def main():
    print(f"BASE_DIR  : {BASE_DIR}")
    print(f"TIME_SKIP : {TIME_SKIP}  (1-in-{TIME_SKIP} timestamps)")

    # Discover .xyz files
    xyz_files = sorted(glob.glob(os.path.join(LLS_DIR, "*.xyz")))
    if not xyz_files:
        print(f"No .xyz files found in {LLS_DIR}")
        return
    print(f"\nFound {len(xyz_files)} .xyz file(s):")
    for f in xyz_files:
        print(f"  {os.path.basename(f)}")

    # Ensure PHINS CSVs exist (parse binary if necessary)
    print(f"\nChecking PHINS navigation CSVs in {NAV_DIR} ...")
    ensure_phins_csvs(NAV_DIR, VEHICLE_DIR)

    # Load navigation data once (shared across all files)
    print(f"\nLoading navigation data from {NAV_DIR} ...")
    nav_df = load_nav(NAV_DIR, TIME_OFFSET)
    print(f"  {len(nav_df):,} nav records  "
          f"({datetime.datetime.utcfromtimestamp(nav_df['Timestamp'].min())} → "
          f"{datetime.datetime.utcfromtimestamp(nav_df['Timestamp'].max())} UTC)")

    # Process each file
    for xyz_path in xyz_files:
        try:
            process_file(xyz_path, nav_df, OFFSETS, TIME_SKIP, OUTPUT_DIR)
        except Exception as exc:
            print(f"  ERROR processing {os.path.basename(xyz_path)}: {exc}")

    print("\nAll files processed.")


if __name__ == "__main__":
    main()
