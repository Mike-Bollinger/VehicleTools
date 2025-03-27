import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter1d
from shapely.geometry import Point, LineString
import os
import tkinter as tk
from tkinter import filedialog, messagebox, Label, Button, Frame
from geopy.distance import geodesic
from scipy.interpolate import interp1d
import matplotlib.dates as mdates
import utm
import datetime
from filterpy.kalman import KalmanFilter
import matplotlib.animation as animation
from matplotlib.patches import Circle
import imageio
from PIL import Image
import platform
import subprocess
from tkinter import IntVar, Checkbutton, ttk

# USBL Moving Window Smoothing Configuration Parameters
SMOOTHING_WINDOW_SIZE = 7     # Size of the rolling window for weighted moving average
SMOOTHING_SIGMA = 1.5         # Sigma parameter for Gaussian filter
FIT_ERROR_THRESHOLD = 10      # Maximum acceptable Fit_Error value

# Kalman Filter Configuration Parameters
# These parameters control how the Kalman filter smooths navigation data
KF_MEASUREMENT_NOISE = 1.0    # Measurement noise (R matrix diagonal) - lower values trust measurements more (default: 25.0)
                              # Represents expected USBL accuracy in meters^2. Lower = less smoothing, more responsive to measurements.
                              
KF_PROCESS_NOISE = 3.0      # Process noise (Q matrix diagonal) - higher values allow more model flexibility (default: 0.025)
                              # Represents expected vehicle dynamics/maneuverability. Higher = more responsive to changes in direction.
                              
KF_INITIAL_COVARIANCE = 50.0 # Initial state covariance - high values indicate higher initial uncertainty (default: 1000.0)
                              # How uncertain we are about the initial position and velocity. Lower = more confidence in initial state.
                              
KF_TIME_GAP_THRESHOLD = 3.0   # Time gap threshold in seconds - filter will be reinitialized if gap exceeds this (default: 1.5)
                              # Helps handle discontinuities in the tracking data.

# Animation Configuration Parameters
ANIMATION_FRAME_RATE = 2     # Frames per second for GIF animation (suggested values: 1-slow, 4-moderate, 8-fast)
ANIMATION_MAX_FRAMES = 300   # Maximum number of frames to generate (to keep file size reasonable)

# OER Moving Average Configuration Parameters
OER_WINDOW_SIZE = 15     # Window size for moving average (number of points)
OER_TOLERANCE = 0.00001  # Tolerance for line simplification in decimal degrees (~1m)

# Function to browse and add multiple files
def browse_files(file_list, labels_frame, title):
    files = filedialog.askopenfilenames(title=title, filetypes=[("CSV Files", "*.csv")])
    for file in files:
        file_list.append(file)
        Label(labels_frame, text=os.path.basename(file), pady=2).pack()

# Function to browse for output directory
def browse_output():
    global output_dir
    output_dir = filedialog.askdirectory(title="Select Output Directory")
    output_label.config(text=output_dir)

# Function to reset selections
def reset_selections():
    global nav_files, diag_files, output_dir
    nav_files.clear()
    diag_files.clear()
    output_dir = ""
    for widget in nav_frame.winfo_children():
        widget.destroy()
    for widget in diag_frame.winfo_children():
        widget.destroy()
    output_label.config(text="No directory selected")

# Add this new function for smoothing navigation data
def smooth_navigation(df):
    """
    Enhanced smoothing for navigation data with better handling of duplicates and outliers
    Uses global parameters: SMOOTHING_WINDOW_SIZE, SMOOTHING_SIGMA, FIT_ERROR_THRESHOLD
    """
    # Create a copy of the dataframe to hold smoothed data
    smoothed_df = df.copy()
    
    # First, remove duplicated timestamps keeping only the best quality point at each time
    if 'Fit_Error' in df.columns:
        # Sort by timestamp and Fit_Error (best quality first)
        deduped_df = df.sort_values(['Timestamp', 'Fit_Error']).drop_duplicates('Timestamp', keep='first')
        deduped_df = deduped_df.sort_values('Timestamp').reset_index(drop=True)
        
        # Convert Fit_Error to weights (inverse relationship) with adjusted scaling
        # Higher contrast between good and bad points
        deduped_df['Weight'] = 1 / (deduped_df['Fit_Error']**2 + 0.01)
        
        # Filter out extremely poor quality points
        quality_data = deduped_df[deduped_df['Fit_Error'] < FIT_ERROR_THRESHOLD].copy()
        
        if len(quality_data) > 10:  # Only smooth if we have enough quality points
            # First-pass weighted moving average to remove the worst jitter
            quality_data['Longitude'] = quality_data['Longitude'].rolling(
                window=SMOOTHING_WINDOW_SIZE, center=True, min_periods=1
            ).apply(lambda x: np.average(x, weights=quality_data.loc[x.index, 'Weight']))
            
            quality_data['Latitude'] = quality_data['Latitude'].rolling(
                window=SMOOTHING_WINDOW_SIZE, center=True, min_periods=1
            ).apply(lambda x: np.average(x, weights=quality_data.loc[x.index, 'Weight']))
            
            # Second pass with Gaussian filter for more gradual transitions
            quality_data['Longitude'] = gaussian_filter1d(quality_data['Longitude'], sigma=SMOOTHING_SIGMA)
            quality_data['Latitude'] = gaussian_filter1d(quality_data['Latitude'], sigma=SMOOTHING_SIGMA)
            
            # Create a time-based index for proper interpolation
            time_idx = pd.to_datetime(quality_data['Timestamp'])
            
            # Interpolate smoothed positions back to original timestamps 
            # to maintain same record count as original data
            lon_interpolator = interp1d(
                mdates.date2num(time_idx), 
                quality_data['Longitude'],
                bounds_error=False, 
                fill_value='extrapolate'
            )
            lat_interpolator = interp1d(
                mdates.date2num(time_idx), 
                quality_data['Latitude'],
                bounds_error=False, 
                fill_value='extrapolate'
            )
            
            # Apply interpolation to get smoothed values for all original timestamps
            smoothed_times = mdates.date2num(pd.to_datetime(df['Timestamp']))
            smoothed_df['Longitude'] = lon_interpolator(smoothed_times)
            smoothed_df['Latitude'] = lat_interpolator(smoothed_times)
            
            print(f"Smoothing applied based on {len(quality_data)} quality data points")
    
    else:
        # Handle data without Fit_Error by removing duplicates first
        deduped_df = df.drop_duplicates('Timestamp').sort_values('Timestamp').reset_index(drop=True)
        print("Diagnostic data not available. Using simple smoothing methods.")
        
        # First apply outlier removal (distance-based)
        coords = np.column_stack([deduped_df['Longitude'], deduped_df['Latitude']])
        if len(coords) > 10:
            # Calculate relative distances between consecutive points
            distances = np.sqrt(np.sum(np.diff(coords, axis=0)**2, axis=1))
            # Find points that are statistical outliers
            mean_dist = np.mean(distances)
            std_dist = np.std(distances)
            threshold = mean_dist + 2 * std_dist
            
            # Create mask for valid points
            good_point_mask = np.ones(len(coords), dtype=bool)
            for i in range(1, len(coords)):
                if i < len(distances) and distances[i-1] > threshold:
                    good_point_mask[i] = False
            
            # Apply simple moving average to filtered data
            filtered_df = deduped_df[good_point_mask]
            
            # Apply simple moving average
            filtered_df['Longitude'] = filtered_df['Longitude'].rolling(
                window=SMOOTHING_WINDOW_SIZE, center=True, min_periods=1
            ).mean()
            
            filtered_df['Latitude'] = filtered_df['Latitude'].rolling(
                window=SMOOTHING_WINDOW_SIZE, center=True, min_periods=1
            ).mean()
            
            # Apply Gaussian filter for additional smoothing
            filtered_df['Longitude'] = gaussian_filter1d(filtered_df['Longitude'], sigma=SMOOTHING_SIGMA)
            filtered_df['Latitude'] = gaussian_filter1d(filtered_df['Latitude'], sigma=SMOOTHING_SIGMA)
            
            # Interpolate back to original timestamps
            time_idx = pd.to_datetime(filtered_df['Timestamp'])
            
            lon_interpolator = interp1d(
                mdates.date2num(time_idx), 
                filtered_df['Longitude'],
                bounds_error=False, 
                fill_value='extrapolate'
            )
            lat_interpolator = interp1d(
                mdates.date2num(time_idx), 
                filtered_df['Latitude'],
                bounds_error=False, 
                fill_value='extrapolate'
            )
            
            smoothed_times = mdates.date2num(pd.to_datetime(df['Timestamp']))
            smoothed_df['Longitude'] = lon_interpolator(smoothed_times)
            smoothed_df['Latitude'] = lat_interpolator(smoothed_times)
    
    return smoothed_df

# New function for Kalman Filter smoothing
def svd_inv(a):
    """Compute matrix inverse using SVD for better numerical stability"""
    u, s, v = np.linalg.svd(a)
    ainv = np.dot(v.transpose(), np.dot(np.diag(s**-1), u.transpose()))
    return ainv

def smooth_with_kalman(df):
    """
    Apply Kalman filter smoothing to navigation data with dynamic measurement noise
    based on the Fit_Error values if available.
    Returns a dataframe with smoothed coordinates
    """
    # Create a copy to hold the smoothed data
    kalman_df = df.copy()
    
    # Sort by timestamp and drop duplicates
    sorted_df = df.sort_values('Timestamp').reset_index(drop=True)
    
    # Check if we have enough points
    if len(sorted_df) < 2:
        print("Not enough points for Kalman filtering")
        return kalman_df
        
    # Check if Fit_Error is available
    has_fit_error = 'Fit_Error' in sorted_df.columns
    if has_fit_error:
        print("Using Fit_Error values to adjust measurement noise dynamically")
        # Scale Fit_Error values to appropriate measurement noise range
        # Convert fit errors to measurement confidence (higher fit error = higher measurement noise)
        sorted_df['R_scale'] = sorted_df['Fit_Error'] ** 2 + 0.25  # Square to emphasize poor quality points
    else:
        print("No Fit_Error values found, using constant measurement noise")
    
    # Convert lat/lon to UTM for better distance calculations
    northings = []
    eastings = []
    timestamps = []
    utm_zones = []  # Store UTM zone info for each point
    r_scales = []   # Store R scaling factors
    
    for i, row in sorted_df.iterrows():
        try:
            # Get UTM coordinates (easting, northing, zone_number, zone_letter)
            e, n, zone_number, zone_letter = utm.from_latlon(row['Latitude'], row['Longitude'])
            northings.append(n)
            eastings.append(e)
            timestamps.append(pd.to_datetime(row['Timestamp']))
            utm_zones.append((zone_number, zone_letter))  # Store zone info for later conversion
            
            # Store R scaling factor (measurement noise multiplier)
            if has_fit_error:
                r_scales.append(row['R_scale'])
            else:
                r_scales.append(1.0)  # Default scaling if no Fit_Error
        except Exception as ex:
            print(f"Error converting lat/lon to UTM: {ex}")
    
    # Use the most common UTM zone for consistency
    zone_counts = {}
    for zone in utm_zones:
        if zone in zone_counts:
            zone_counts[zone] += 1
        else:
            zone_counts[zone] = 1
    
    # Get the most common zone
    common_zone = max(zone_counts.items(), key=lambda x: x[1])[0]
    zone_number, zone_letter = common_zone
    
    print(f"Using UTM zone {zone_number}{zone_letter} for Kalman filter calculations")
    
    # Initialize Kalman filter
    kf = KalmanFilter(dim_x=4, dim_z=2)  # State: [x, y, vx, vy], Measurement: [x, y]
    
    # Initial state
    kf.x = np.array([
        [eastings[0]],
        [northings[0]],
        [eastings[1]-eastings[0]],
        [northings[1]-northings[0]],
    ])
    
    # State transition matrix (constant velocity model)
    kf.F = np.array([
        [1., 0., 1., 0.],
        [0., 1., 0., 1.],
        [0., 0., 1., 0.],
        [0., 0., 0., 1.],
    ])
    
    # Measurement matrix
    kf.H = np.array([
        [1., 0., 0., 0.],
        [0., 1., 0., 0.],
    ])
    
    # Covariance matrix - using global parameter
    kf.P = np.eye(4) * KF_INITIAL_COVARIANCE
    
    # Base measurement noise - will be scaled by fit_error for each measurement
    base_R = np.eye(2) * KF_MEASUREMENT_NOISE
    
    # Process noise - using global parameter
    kf.Q = np.eye(4) * KF_PROCESS_NOISE
    
    # Variables to store filter states for smoothing
    mu = []  # Filtered state means
    cov = []  # Filtered state covariances
    Fs = []  # State transition matrices
    Qs = []  # Process noise matrices
    
    # Apply filter in forward pass
    print("Applying Kalman filter...")
    last_timestamp = timestamps[0]
    
    for i in range(len(eastings)):
        meas = np.array([[eastings[i]], [northings[i]]])
        
        # Handle time gaps - reinitialize filter if gap is too large
        if i > 0:
            dt = (timestamps[i] - last_timestamp).total_seconds()
            if dt > KF_TIME_GAP_THRESHOLD:  # Using global parameter
                print(f"Time gap detected ({dt}s) at point {i}, reinitializing filter")
                kf.x[0][0] = eastings[i]
                kf.x[1][0] = northings[i]
                if i < len(eastings) - 1:
                    kf.x[2][0] = eastings[i+1] - eastings[i]
                    kf.x[3][0] = northings[i+1] - northings[i]
                else:
                    kf.x[2][0] = 0
                    kf.x[3][0] = 0
                kf.P = np.eye(4) * KF_INITIAL_COVARIANCE
        
        last_timestamp = timestamps[i]
        
        # Set measurement noise based on fit_error for this measurement
        # Higher fit_error = higher measurement uncertainty = less weight on this measurement
        kf.R = base_R * r_scales[i]
        
        # If this point has very high fit error, we may want to increase process noise 
        # to allow the filter to adapt more quickly after a potentially bad measurement
        if r_scales[i] > 5.0:
            kf.Q = np.eye(4) * (KF_PROCESS_NOISE * 1.5)  # Temporarily increase process noise
        else:
            kf.Q = np.eye(4) * KF_PROCESS_NOISE  # Return to normal process noise
        
        # Predict and store
        kf.predict()
        if not np.any(np.isnan(kf.P)) and not np.any(np.isnan(kf.x)):
            mu.append(kf.x.copy())
            cov.append(kf.P.copy())
            Fs.append(kf.F.copy())
            Qs.append(kf.Q.copy())
        
        # Update with measurement
        kf.update(meas)
    
    # Apply RTS smoother for backward pass
    print(f"Smoothing {len(mu)} points...")
    mu_array = np.array([m.flatten() for m in mu])
    cov_array = np.array(cov)
    Fs_array = np.array(Fs)
    Qs_array = np.array(Qs)
    
    smoothed_states, _, _, _ = kf.rts_smoother(mu_array, cov_array, Fs_array, Qs_array, inv=svd_inv)
    
    # Extract smoothed eastings and northings
    smoothed_eastings = smoothed_states[:, 0]
    smoothed_northings = smoothed_states[:, 1]
    
    # Convert back to lat/lon
    smoothed_lats = []
    smoothed_lons = []
    
    for i in range(len(smoothed_eastings)):
        try:
            # Use the common zone for consistent conversion back to lat/lon
            lat, lon = utm.to_latlon(smoothed_eastings[i], smoothed_northings[i], 
                                     zone_number=zone_number, zone_letter=zone_letter)
            smoothed_lats.append(lat)
            smoothed_lons.append(lon)
        except Exception as ex:
            print(f"Error converting UTM back to lat/lon at point {i}: {ex}")
            # If conversion fails, use original coordinates
            if i < len(sorted_df):
                smoothed_lats.append(sorted_df.iloc[i]['Latitude'])
                smoothed_lons.append(sorted_df.iloc[i]['Longitude'])
            else:
                # Fallback if index is out of range
                smoothed_lats.append(sorted_df.iloc[-1]['Latitude'])
                smoothed_lons.append(sorted_df.iloc[-1]['Longitude'])
    
    # Create a dataframe with original timestamps but smoothed coordinates
    result_df = pd.DataFrame({
        'Timestamp': sorted_df['Timestamp'].values[:len(smoothed_lats)],
        'Latitude': smoothed_lats,
        'Longitude': smoothed_lons
    })
    
    # Debug: Print the first few points to verify proper conversion
    print("First 3 Kalman smoothed points:")
    for i in range(min(3, len(result_df))):
        print(f"Point {i}: Lat={result_df.iloc[i]['Latitude']:.6f}, Lon={result_df.iloc[i]['Longitude']:.6f}")
    
    # Interpolate back to original timestamps if necessary
    if len(result_df) != len(df):
        print(f"Interpolating Kalman results to match original {len(df)} points")
        time_idx = pd.to_datetime(result_df['Timestamp'])
        
        lon_interpolator = interp1d(
            mdates.date2num(time_idx), 
            result_df['Longitude'],
            bounds_error=False, 
            fill_value='extrapolate'
        )
        lat_interpolator = interp1d(
            mdates.date2num(time_idx), 
            result_df['Latitude'],
            bounds_error=False, 
            fill_value='extrapolate'
        )
        
        # Apply interpolation
        all_times = mdates.date2num(pd.to_datetime(df['Timestamp']))
        kalman_df['Longitude'] = lon_interpolator(all_times)
        kalman_df['Latitude'] = lat_interpolator(all_times)
    else:
        # Just copy the values
        kalman_df['Longitude'] = result_df['Longitude'].values
        kalman_df['Latitude'] = result_df['Latitude'].values
        
    return kalman_df

# Add this function to calculate distance
def calculate_track_distance(df):
    """
    Calculate the total distance traveled in the track in kilometers
    """
    total_distance = 0
    for i in range(1, len(df)):
        point1 = (df.iloc[i-1]['Latitude'], df.iloc[i-1]['Longitude'])
        point2 = (df.iloc[i]['Latitude'], df.iloc[i]['Longitude'])
        # Calculate distance between consecutive points in meters
        distance = geodesic(point1, point2).kilometers
        total_distance += distance
    return total_distance

# Add this new function for the OER Moving Average model
def smooth_with_oer_average(df):
    """
    Apply OER's simple moving average algorithm to navigation data
    Based on the smooth_rov_nav script, but adapted for direct DataFrame input/output
    Uses global parameters: OER_WINDOW_SIZE, OER_TOLERANCE
    """
    print("Applying OER Moving Average smoothing...")
    
    # Create a copy of the dataframe to hold smoothed data
    smoothed_df = df.copy()
    
    # Get coordinates as numpy arrays for efficient processing
    x = df['Longitude'].values
    y = df['Latitude'].values
    z = df['Depth'].values if 'Depth' in df.columns else np.zeros(len(df))
    
    out_pts = []
    window = OER_WINDOW_SIZE
    
    # Apply moving average
    for i in range(len(x)):
        if i > window/2 and i < len(x) - window/2:
            start_idx = math.floor(i - window/2)
            end_idx = math.floor(i + window/2)
            avg_x = sum(x[start_idx:end_idx]) / window
            avg_y = sum(y[start_idx:end_idx]) / window
            avg_z = sum(z[start_idx:end_idx]) / window
            
            out_pts.append((avg_x, avg_y, avg_z))
        else:
            # For points at beginning and end, use existing values
            out_pts.append((x[i], y[i], z[i]))
    
    # Convert to LineString and apply simplification if tolerance > 0
    if OER_TOLERANCE > 0 and len(out_pts) > 2:
        line = LineString([(p[0], p[1]) for p in out_pts]).simplify(OER_TOLERANCE)
        
        # Extract points from simplified line
        simplified_pts = list(line.coords)
        
        # If we lost points due to simplification, we need to resample 
        # to match the original length
        if len(simplified_pts) < len(out_pts):
            print(f"Simplification reduced points from {len(out_pts)} to {len(simplified_pts)}. Re-interpolating...")
            
            # Create a new array of points for the final result
            final_x = np.zeros(len(x))
            final_y = np.zeros(len(y))
            
            # Keep the original points for the beginning and end
            # (outside the window)
            for i in range(len(x)):
                if i <= window/2 or i >= len(x) - window/2:
                    final_x[i] = x[i]
                    final_y[i] = y[i]
            
            # For the middle section, use the simplified line points
            # We'll need to distribute them evenly across the original indices
            middle_start = math.ceil(window/2)
            middle_end = len(x) - math.ceil(window/2)
            middle_len = middle_end - middle_start
            
            # If we have at least 2 simplified points, interpolate
            if len(simplified_pts) >= 2:
                # Create interpolators for the simplified line
                simplified_indices = np.linspace(middle_start, middle_end, len(simplified_pts))
                interp_x = interp1d(simplified_indices, [p[0] for p in simplified_pts], 
                                    bounds_error=False, fill_value="extrapolate")
                interp_y = interp1d(simplified_indices, [p[1] for p in simplified_pts], 
                                    bounds_error=False, fill_value="extrapolate")
                
                # Interpolate simplified points to match the original indices
                middle_indices = range(middle_start, middle_end)
                for i in middle_indices:
                    final_x[i] = interp_x(i)
                    final_y[i] = interp_y(i)
            else:
                # If simplification was too aggressive, revert to original points
                print("Simplification too aggressive, reverting to original moving average")
                final_x = [p[0] for p in out_pts]
                final_y = [p[1] for p in out_pts]
            
            # Update the smoothed dataframe
            smoothed_df['Longitude'] = final_x
            smoothed_df['Latitude'] = final_y
        else:
            # No need for resampling, just use the simplified points
            smoothed_df['Longitude'] = [p[0] for p in simplified_pts] + [x[i] for i in range(len(simplified_pts), len(x))]
            smoothed_df['Latitude'] = [p[1] for p in simplified_pts] + [y[i] for i in range(len(simplified_pts), len(y))]
    else:
        # No simplification, just use the moving average results
        smoothed_df['Longitude'] = [p[0] for p in out_pts]
        smoothed_df['Latitude'] = [p[1] for p in out_pts]
    
    print(f"OER Moving Average smoothing completed with window size {OER_WINDOW_SIZE}")  # Fixed closing bracket
    return smoothed_df

# Function to process the selected files
def process_files():
    # Import modules again to ensure they're available within this function
    import os as os_module  # Use a different name to avoid shadows
    
    if not nav_files or not output_dir:
        messagebox.showerror("Error", "Navigation files and output directory are required.")
        return
    
    # Check if at least one model is selected when not in compare mode
    if compare_mode_var.get() == 0 and window_var.get() == 0 and kalman_var.get() == 0:
        messagebox.showerror("Error", "Please select at least one smoothing model.")
        return

    # Use os_module instead of os
    base_name = os_module.path.splitext(os_module.path.basename(nav_files[0]))[0].replace("_Nav", "")
    output_csv = os_module.path.join(output_dir, f"{base_name}_Final.csv")
    output_point_shapefile = os_module.path.join(output_dir, f"{base_name}_Points.shp")
    output_line_shapefile = os_module.path.join(output_dir, f"{base_name}_Line.shp")
    output_smoothed_point_shapefile = os_module.path.join(output_dir, f"{base_name}_Points_Smoothed.shp")
    output_smoothed_line_shapefile = os_module.path.join(output_dir, f"{base_name}_Line_Smoothed.shp")
    output_plot = os_module.path.join(output_dir, f"{base_name}_Track_Comparison.png")
    # Add new output file for comparison CSV
    output_comparison_csv = os_module.path.join(output_dir, f"{base_name}_Smoothing_Comparison.csv")

    # Define column names
    nav_columns = ["Timestamp", "ID", "Latitude", "Longitude", "Easting", "Northing", "Depth"]
    diag_columns = ["Timestamp", "ID", "Local_Yaw", "Local_Pitch", "Local_Roll", "Azimuth", "Elevation", "Range", "Fit_Error", "Blank"]

    # Read and combine _Nav CSV files
    df_nav = pd.concat([pd.read_csv(f, header=None, names=nav_columns) for f in nav_files], ignore_index=True)
    df_nav["Timestamp"] = pd.to_datetime(df_nav["Timestamp"]).dt.round('s')

    df_diag = None
    if diag_files:
        df_diag = pd.concat([pd.read_csv(f, header=None, names=diag_columns, skiprows=1) for f in diag_files], ignore_index=True)
        df_diag["Timestamp"] = pd.to_datetime(df_diag["Timestamp"], format='%a %b %d %H:%M:%S %Y', errors='coerce')
        df_diag["Timestamp"] = df_diag["Timestamp"].dt.round('s')

    # Merge the data
    merged_df = pd.merge(df_nav, df_diag, on="Timestamp", how="inner") if df_diag is not None else df_nav
    merged_df.to_csv(output_csv, index=False)
    
    # Create a copy with string timestamps for GeoDataFrame
    merged_df_geo = merged_df.copy()
    merged_df_geo["Timestamp"] = merged_df_geo["Timestamp"].astype(str)

    # Determine which model(s) to use
    compare_mode = compare_mode_var.get() == 1
    use_window = window_var.get() == 1 or compare_mode
    use_kalman = kalman_var.get() == 1 or compare_mode
    
    # Apply selected smoothing method(s)
    smoothed_df = None
    window_df = None
    kalman_df = None
    window_track_distance = 0
    kalman_track_distance = 0
    
    if use_window:
        window_df = smooth_navigation(merged_df)
        window_track_distance = calculate_track_distance(window_df)
    
    if use_kalman:
        kalman_df = smooth_with_kalman(merged_df)
        kalman_track_distance = calculate_track_distance(kalman_df)
    
    # Determine which smoothed data to use for shapefiles
    if compare_mode:
        # In compare mode, use both for comparison but don't export shapefiles
        smoothed_df = window_df  # Arbitrary choice for compare mode
    else:
        # Not in compare mode, use the selected model
        if use_window:
            smoothed_df = window_df
        elif use_kalman:
            smoothed_df = kalman_df
    
    # Create a copy with string timestamps for GeoDataFrame (only if not in compare mode)
    if not compare_mode:
        smoothed_df_geo = smoothed_df.copy()
        smoothed_df_geo["Timestamp"] = smoothed_df_geo["Timestamp"].astype(str)
    
    # Create comparison dataframe based on selected models
    comparison_columns = {
        'Timestamp': merged_df['Timestamp'],
        'Original_Latitude': merged_df['Latitude'],
        'Original_Longitude': merged_df['Longitude']
    }
    
    if use_window:
        comparison_columns.update({
            'Window_Latitude': window_df['Latitude'],
            'Window_Longitude': window_df['Longitude']
        })
    
    if use_kalman:
        comparison_columns.update({
            'Kalman_Latitude': kalman_df['Latitude'],
            'Kalman_Longitude': kalman_df['Longitude']
        })
    
    comparison_df = pd.DataFrame(comparison_columns)
    
    # Add other columns from the original data
    if 'Easting' in merged_df.columns and 'Northing' in merged_df.columns:
        comparison_df['Original_Easting'] = merged_df['Easting']
        comparison_df['Original_Northing'] = merged_df['Northing']
    
    if 'Fit_Error' in merged_df.columns:
        comparison_df['Fit_Error'] = merged_df['Fit_Error']
    
    # Add zone info
    try:
        _, _, zone_number, zone_letter = utm.from_latlon(
            merged_df['Latitude'].iloc[0], 
            merged_df['Longitude'].iloc[0]
        )
        comparison_df['UTM_Zone'] = f"{zone_number}{zone_letter}"
    except:
        print("Warning: Could not determine UTM zone for the data")
    
    # Save the comparison CSV
    comparison_df.to_csv(output_comparison_csv, index=False)
    print(f"Comparison CSV saved to: {output_comparison_csv}")
    
    # Convert original data to GeoDataFrame and save
    merged_df_geo = merged_df.copy()
    merged_df_geo["Timestamp"] = merged_df_geo["Timestamp"].astype(str)
    
    gdf_points = gpd.GeoDataFrame(
        merged_df_geo,
        geometry=[Point(xy) for xy in zip(merged_df_geo["Longitude"], merged_df_geo["Latitude"])],
        crs="EPSG:4326"
    )
    gdf_points.to_file(output_point_shapefile)
    
    # Create and save shapefiles only if not in compare mode
    if not compare_mode:
        # Convert smoothed data to GeoDataFrame with distance attribute
        gdf_points_smoothed = gpd.GeoDataFrame(
            smoothed_df_geo,
            geometry=[Point(xy) for xy in zip(smoothed_df_geo["Longitude"], smoothed_df_geo["Latitude"])],
            crs="EPSG:4326"
        )
        gdf_points_smoothed.to_file(output_smoothed_point_shapefile)
        
        # Create LineString geometry for original data
        gdf_sorted = gdf_points.sort_values(by="Timestamp")
        if len(gdf_sorted) > 1:
            line_geometry = LineString([row.geometry for _, row in gdf_sorted.iterrows()])
            gdf_line = gpd.GeoDataFrame(pd.DataFrame([{"Timestamp": base_name, "geometry": line_geometry}]), crs="EPSG:4326")
            gdf_line.to_file(output_line_shapefile)
        
        # Create LineString geometry for smoothed data
        gdf_sorted_smoothed = gdf_points_smoothed.sort_values(by="Timestamp")
        if len(gdf_sorted_smoothed) > 1:
            smoothed_line_geometry = LineString([row.geometry for row in gdf_sorted_smoothed.iterrows()])
            
            # Determine which distance to use based on the selected model
            track_distance = window_track_distance if use_window else kalman_track_distance
            model_name = "Window" if use_window else "Kalman"
            
            gdf_line_smoothed = gpd.GeoDataFrame(
                pd.DataFrame([{
                    "Timestamp": base_name, 
                    "Model": model_name,
                    "Distance_km": round(track_distance, 3),
                    "geometry": smoothed_line_geometry
                }]), 
                crs="EPSG:4326"
            )
            gdf_line_smoothed.to_file(output_smoothed_line_shapefile)
    else:
        # In compare mode, don't create smoothed shapefiles
        print("Compare mode enabled - smoothed shapefiles not created")

    # Create a plot comparing tracks based on selected models
    plt.figure(figsize=(12, 10))
    
    # First, let's make sure all the data is in the same coordinate system
    print(f"Coordinate ranges - Raw data: Lon ({merged_df['Longitude'].min():.6f} to {merged_df['Longitude'].max():.6f}), "
          f"Lat ({merged_df['Latitude'].min():.6f} to {merged_df['Latitude'].max():.6f})")
    
    # Plot the tracks based on selected models
    plt.plot(merged_df["Longitude"], merged_df["Latitude"], 'b.-', alpha=0.5, label='Raw USBL Data')
    
    if use_window:
        plt.plot(window_df["Longitude"], window_df["Latitude"], 'r-', linewidth=2, label='Window Smoothed')
        print(f"Coordinate ranges - Window smoothed: Lon ({window_df['Longitude'].min():.6f} to {window_df['Longitude'].max():.6f}), "
              f"Lat ({window_df['Latitude'].min():.6f} to {window_df['Latitude'].max():.6f})")
    
    if use_kalman:
        plt.plot(kalman_df["Longitude"], kalman_df["Latitude"], 'g-', linewidth=2, label='Kalman Smoothed')
        print(f"Coordinate ranges - Kalman smoothed: Lon ({kalman_df['Longitude'].min():.6f} to {kalman_df['Longitude'].max():.6f}), "
              f"Lat ({kalman_df['Latitude'].min():.6f} to {kalman_df['Latitude'].max():.6f})")
    
    # Calculate the proper axis limits based on all data being displayed
    all_lons = [merged_df["Longitude"].min(), merged_df["Longitude"].max()]
    all_lats = [merged_df["Latitude"].min(), merged_df["Latitude"].max()]
    
    if use_window:
        all_lons.extend([window_df["Longitude"].min(), window_df["Longitude"].max()])
        all_lats.extend([window_df["Latitude"].min(), window_df["Latitude"].max()])
    
    if use_kalman:
        all_lons.extend([kalman_df["Longitude"].min(), kalman_df["Longitude"].max()])
        all_lats.extend([kalman_df["Latitude"].min(), kalman_df["Latitude"].max()])
    
    lon_min, lon_max = min(all_lons), max(all_lons)
    lat_min, lat_max = min(all_lats), max(all_lats)
    
    # Calculate ranges
    lon_range = lon_max - lon_min
    lat_range = lat_max - lat_min
    
    # Add a bit of padding (5% on each side)
    padding = 0.05
    lon_padding = max(lon_range * padding, 0.00001)  # Ensure minimum padding
    lat_padding = max(lat_range * padding, 0.00001)  # Ensure minimum padding
    
    lon_min -= lon_padding
    lon_max += lon_padding
    lat_min -= lat_padding
    lat_max += lat_padding
    
    # Set the axis limits explicitly
    plt.xlim(lon_min, lon_max)
    plt.ylim(lat_min, lat_max)
    
    # Ensure plot has reasonable aspect ratio
    if 0.1 < lon_range/lat_range < 10:
        plt.axis('equal')
    else:
        print("Warning: Longitude and latitude ranges differ significantly. Using automatic aspect ratio.")
    
    # Add distance information as text on plot - only for selected models
    distance_text = ""
    if use_window:
        distance_text += f"Window Method Distance: {round(window_track_distance, 3)} km\n"
    if use_kalman:
        distance_text += f"Kalman Method Distance: {round(kalman_track_distance, 3)} km"
    
    if distance_text:
        plt.annotate(distance_text, 
                    xy=(0.05, 0.95), xycoords='axes fraction',
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8),
                    fontsize=12)
                
    # Plot title - reflect single model or comparison mode
    if compare_mode:
        title = f"USBL Track Comparison - {base_name}"
    else:
        model_name = "Window" if use_window else "Kalman"
        title = f"USBL Track - {model_name} Smoothing - {base_name}"
    
    plt.title(title, fontsize=14)
    plt.xlabel('Longitude', fontsize=12)
    plt.ylabel('Latitude', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=12)
    plt.tight_layout()
    
    # Save the plot without showing it
    plt.savefig(output_plot, dpi=300)
    plt.close()  # Close the plot instead of showing it
    
    # Create animation frames showing the progression along each track
    frames_dir, gif_path = create_animation_frames(
        comparison_df, 
        output_dir, 
        base_name
    )
    
    # Update the success message
    animation_message = ""
    if gif_path:
        animation_message = f"\nAnimation frames: {frames_dir}\nAnimation GIF: {gif_path}"
        
        # Open the GIF file with the default image viewer
        try:
            print(f"Opening GIF: {gif_path}")
            if platform.system() == 'Darwin':  # macOS
                subprocess.call(('open', gif_path))
            elif platform.system() == 'Windows':  # Windows
                os_module.startfile(gif_path)  # Use os_module here
            else:  # linux
                subprocess.call(('xdg-open', gif_path))
        except Exception as e:
            print(f"Failed to open GIF: {e}")

    # Build success message based on mode
    if compare_mode:
        success_msg = f"Comparison files saved:\n{output_csv}\n{output_comparison_csv}\n{output_plot}{animation_message}"
    else:
        success_msg = f"Files saved:\n{output_csv}\n{output_comparison_csv}\n{output_point_shapefile} & {output_smoothed_point_shapefile}\n{output_line_shapefile} & {output_smoothed_line_shapefile}\n{output_plot}{animation_message}"
    
    messagebox.showinfo("Success", success_msg)

# Add this function after your existing functions
def create_animation_frames(comparison_df, output_dir, base_name, frame_rate=None):
    """
    Creates animation frames showing the progression of the vehicle along the selected tracks.
    
    Args:
        comparison_df: DataFrame with position tracks (may include some or all models)
        output_dir: Directory to save frames and GIF
        base_name: Base filename for outputs
        frame_rate: Optional frame rate override (uses global ANIMATION_FRAME_RATE if None)
    """
    # Import modules again to ensure they're available within this function
    import os as os_module
    
    # Use global frame rate if not specified
    if frame_rate is None:
        frame_rate = ANIMATION_FRAME_RATE
        
    print(f"Creating animation frames with rate {frame_rate} FPS...")
    
    # Create frames directory if it doesn't exist
    frames_dir = os_module.path.join(output_dir, f"{base_name}_frames")
    os_module.makedirs(frames_dir, exist_ok=True)
    
    # Check which models are available in the comparison_df
    has_window = 'Window_Longitude' in comparison_df.columns
    has_kalman = 'Kalman_Longitude' in comparison_df.columns
    
    # Determine plot boundaries with extra padding
    all_lons = [comparison_df['Original_Longitude'].min(), comparison_df['Original_Longitude'].max()]
    all_lats = [comparison_df['Original_Latitude'].min(), comparison_df['Original_Latitude'].max()]
    
    if has_window:
        all_lons.extend([comparison_df['Window_Longitude'].min(), comparison_df['Window_Longitude'].max()])
        all_lats.extend([comparison_df['Window_Latitude'].min(), comparison_df['Window_Latitude'].max()])
    
    if has_kalman:
        all_lons.extend([comparison_df['Kalman_Longitude'].min(), comparison_df['Kalman_Longitude'].max()])
        all_lats.extend([comparison_df['Kalman_Latitude'].min(), comparison_df['Kalman_Latitude'].max()])
    
    lon_min, lon_max = min(all_lons), max(all_lons)
    lat_min, lat_max = min(all_lats)
    
    # Add padding (5% on each side)
    lon_range = lon_max - lon_min
    lat_range = lat_max - lat_min
    lon_padding = lon_range * 0.05
    lat_padding = lat_range * 0.05
    lon_min -= lon_padding
    lon_max += lon_padding
    lat_min -= lat_padding
    lat_max += lat_padding
    
    # Create frames (one per timestamp)
    frame_files = []
    
    # Determine marker size based on track length
    points_count = len(comparison_df)
    marker_size = max(50, min(200, 10000 / points_count))  # Scale marker size based on point count
    
    # Calculate time range for progress indicator
    min_time = pd.to_datetime(comparison_df['Timestamp'].min())
    max_time = pd.to_datetime(comparison_df['Timestamp'].max())
    time_range = (max_time - min_time).total_seconds()
    
    # Determine how many frames to skip to stay under the maximum
    skip_factor = 1
    if points_count > ANIMATION_MAX_FRAMES:
        skip_factor = int(points_count / ANIMATION_MAX_FRAMES) + 1
        print(f"Limiting animation to ~{ANIMATION_MAX_FRAMES} frames by using every {skip_factor}th point")
    
    # For each timestamp, create a frame
    for i, row in comparison_df.iterrows():
        # Skip frames based on skip_factor (except first and last frame)
        if i % skip_factor != 0 and i != 0 and i != len(comparison_df)-1:
            continue
            
        current_time = pd.to_datetime(row['Timestamp'])
        progress = ((current_time - min_time).total_seconds() / time_range) * 100
        
        print(f"Creating frame {i+1}/{len(comparison_df)} - Time: {current_time.strftime('%H:%M:%S')} - {progress:.1f}% complete")
        
        fig, ax = plt.figure(figsize=(10, 8)), plt.gca()
        
        # Plot full tracks with transparency
        # Original USBL in blue
        plt.plot(comparison_df['Original_Longitude'], comparison_df['Original_Latitude'], 
                 'b-', alpha=0.4, linewidth=1, label='Raw USBL Data')
        
        # Window-smoothed in red (if present)
        if has_window:
            plt.plot(comparison_df['Window_Longitude'], comparison_df['Window_Latitude'], 
                     'r-', alpha=0.4, linewidth=1.5, label='Window Smoothed')
        
        # Kalman-smoothed in green (if present)
        if has_kalman:
            plt.plot(comparison_df['Kalman_Longitude'], comparison_df['Kalman_Latitude'], 
                     'g-', alpha=0.4, linewidth=1.5, label='Kalman Smoothed')
        
        # Plot the tracks up to current point with full opacity
        current_df = comparison_df.iloc[:i+1]
        
        # Original USBL with marker
        plt.plot(current_df['Original_Longitude'], current_df['Original_Latitude'], 
                 'b-', linewidth=1.5)
        
        # Window-smoothed with marker (if present)
        if has_window:
            plt.plot(current_df['Window_Longitude'], current_df['Window_Latitude'], 
                     'r-', linewidth=2)
        
        # Kalman-smoothed with marker (if present)
        if has_kalman:
            plt.plot(current_df['Kalman_Longitude'], current_df['Kalman_Latitude'], 
                     'g-', linewidth=2)
        
        # Add circular markers at current position for each track
        circle1 = plt.Circle((row['Original_Longitude'], row['Original_Latitude']), 
                            lon_range/500, color='blue', alpha=1.0, zorder=10)
        ax.add_patch(circle1)
        
        if has_window:
            circle2 = plt.Circle((row['Window_Longitude'], row['Window_Latitude']), 
                                lon_range/500, color='red', alpha=1.0, zorder=10)
            ax.add_patch(circle2)
        
        if has_kalman:
            circle3 = plt.Circle((row['Kalman_Longitude'], row['Kalman_Latitude']), 
                                lon_range/500, color='green', alpha=1.0, zorder=10)
            ax.add_patch(circle3)
        
        # Add time indicator
        plt.annotate(f"Time: {current_time.strftime('%H:%M:%S')}", 
                    xy=(0.05, 0.95), xycoords='axes fraction',
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8),
                    fontsize=12)
        
        # Configure plot
        plt.title(f"Navigation Track Comparison - {base_name}", fontsize=14)
        plt.xlabel('Longitude', fontsize=12)
        plt.ylabel('Latitude', fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.legend(loc='lower left', fontsize=10)
        
        # Set axis limits to keep consistent view across all frames
        plt.xlim(lon_min, lon_max)
        plt.ylim(lat_min, lat_max)
        
        # Ensure equal aspect ratio if ranges are similar
        if 0.1 < lon_range/lat_range < 10:
            plt.axis('equal')
        
        # Save the frame
        frame_filename = os_module.path.join(frames_dir, f"frame_{i:04d}.png")
        plt.savefig(frame_filename, dpi=150)
        frame_files.append(frame_filename)
        plt.close()
    
    # Create a single GIF from frames with the specified frame rate
    if frame_files:
        print(f"Creating GIF with {len(frame_files)} frames at {frame_rate} FPS...")
        gif_path = os_module.path.join(output_dir, f"{base_name}_Animation_{frame_rate}fps.gif")
        
        # Read all frames
        images = []
        for frame_file in frame_files:
            images.append(imageio.imread(frame_file))
        
        # Create just one GIF with the specified frame rate
        imageio.mimsave(gif_path, images, fps=frame_rate, loop=0)
        print(f"GIF saved at {frame_rate} FPS: {gif_path}")
        
        return frames_dir, gif_path
    else:
        print("No frames were created.")
        return None, None

# Initialize GUI
root = tk.Tk()
root.title("ROV-SeaTrac USBL Navigation File Selection")
root.geometry("500x450")
root.configure(padx=20, pady=20)

# Function to update model selection (Define this BEFORE using it)
def update_model_selection():
    """Enable/disable appropriate checkboxes based on compare mode selection"""
    if compare_mode_var.get() == 1:
        # If compare mode is selected, enable both models and select them
        window_checkbox.select()
        kalman_checkbox.select()
        window_checkbox.config(state="disabled")
        kalman_checkbox.config(state="disabled")
    else:
        # If compare mode is not selected, enable individual selection
        window_checkbox.config(state="normal")
        kalman_checkbox.config(state="normal")

nav_files, diag_files = [], []

# Navigation File Selection
Label(root, text="Select Navigation (_Nav) Files:", pady=5, font=("Arial", 10, "bold")).pack()
nav_frame = Frame(root)
nav_frame.pack()
Button(root, text="Add More Nav Files", command=lambda: browse_files(nav_files, nav_frame, "Select Navigation (_Nav) Files"), pady=5).pack()

# Horizontal Line Separator
Frame(root, height=2, width=450, bg="#CCCCCC").pack(pady=10)

# Diagnostic File Selection
Label(root, text="Select Diagnostic (_Diag) Files:", pady=5, font=("Arial", 10, "bold")).pack()
diag_frame = Frame(root)
diag_frame.pack()
Button(root, text="Add More Diag Files", command=lambda: browse_files(diag_files, diag_frame, "Select Diagnostic (_Diag) Files"), pady=5).pack()

# Horizontal Line Separator
Frame(root, height=2, width=450, bg="#CCCCCC").pack(pady=10)

# Output Directory Selection
Label(root, text="Select Output Directory:", pady=5, font=("Arial", 10, "bold")).pack()
output_label = Label(root, text="No directory selected", width=50, pady=5)
output_label.pack()
Button(root, text="Browse", command=browse_output, pady=5).pack()

# Horizontal Line Separator
Frame(root, height=2, width=450, bg="#CCCCCC").pack(pady=10)

# Add model selection options with checkboxes
model_frame = ttk.LabelFrame(root, text="Smoothing Model Selection")
model_frame.pack(fill="x", padx=10, pady=10)

# Create variables for checkboxes
window_var = IntVar(value=1)  # Default: Window method selected
kalman_var = IntVar(value=0)  # Default: Kalman method not selected
compare_mode_var = IntVar(value=0)  # Default: Compare mode not selected

# Add checkboxes
window_checkbox = Checkbutton(model_frame, text="Window Smoothing", variable=window_var)
window_checkbox.grid(row=0, column=0, sticky="w", padx=20, pady=5)

kalman_checkbox = Checkbutton(model_frame, text="Kalman Filter", variable=kalman_var)
kalman_checkbox.grid(row=0, column=1, sticky="w", padx=20, pady=5)

compare_checkbox = Checkbutton(model_frame, text="Compare All Models (No Shapefiles)", 
                             variable=compare_mode_var, command=update_model_selection)
compare_checkbox.grid(row=1, column=0, columnspan=2, sticky="w", padx=20, pady=5)

# Add a note about compare mode
ttk.Label(model_frame, text="Note: Compare mode shows all models but doesn't generate shapefiles", 
         font=("Arial", 8, "italic")).grid(row=2, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 5))

# Horizontal Line Separator
Frame(root, height=2, width=450, bg="#CCCCCC").pack(pady=10)

# Buttons for Processing & Reset
Button(root, text="Process", command=process_files, pady=10, font=("Arial", 10, "bold"), bg="#4CAF50", fg="white").pack(pady=(10, 5))
Button(root, text="Reset", command=reset_selections, pady=10, font=("Arial", 10, "bold"), bg="#f44336", fg="white").pack()

root.mainloop()  # Start the GUI event loop

