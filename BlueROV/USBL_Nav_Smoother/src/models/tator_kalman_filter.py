# FILE: /USBL_Nav_Smoother/USBL_Nav_Smoother/src/models/kalman_filter.py

import numpy as np
import pandas as pd
import datetime
from filterpy.kalman import KalmanFilter
import math

# Fine-tuned Kalman filter parameters for more subtle smoothing

# Configuration Parameters for TATOR Kalman Filter
# ---------------------------------------------------------
# KF_MEASUREMENT_NOISE: Represents expected measurement error in the USBL system.
#   - Higher values (e.g., 50.0, 100.0): Less trust in measurements, more smoothing
#   - Lower values (e.g., 5.0, 10.0): More trust in measurements, less smoothing
#   - Adjust based on USBL accuracy: Higher for deep water (>1000m), lower for shallow water
#   - Recommended range: 10.0-100.0
KF_MEASUREMENT_NOISE = 30.0    # Mild smoothing effect, still respects measurements

# KF_PROCESS_NOISE: Controls how much the model expects vehicle motion to change randomly.
#   - Higher values (e.g., 0.05, 0.1): Allow rapid velocity changes, follow data more closely
#   - Lower values (e.g., 0.01, 0.005): Assume smoother vehicle motion, create more uniform tracks
#   - Recommended range: 0.005-0.1
KF_PROCESS_NOISE = 0.02        # Slightly higher to allow more natural movement

# KF_TIME_GAP_THRESHOLD: Determines when to reset filter due to time gaps in data.
#   - Higher values (e.g., 10.0, 30.0): Maintain filtering across longer data gaps
#   - Lower values (e.g., 3.0, 5.0): Reset filter more frequently with sparse data
#   - Should be 2-3× the normal sampling interval of your data
#   - Recommended range: 3.0-30.0 seconds
KF_TIME_GAP_THRESHOLD = 12.0   # High enough to prevent frequent resets but not too high

# KF_INIT_COVARIANCE: Sets initial uncertainty when filter starts or restarts.
#   - Higher values (e.g., 2000.0, 5000.0): More initial reliance on measurements
#   - Lower values (e.g., 500.0, 100.0): More initial trust in model predictions
#   - Recommended range: 500.0-5000.0
KF_INIT_COVARIANCE = 1200.0    # Moderate value for balanced initial behavior

def is_valid(x):
    """Check if a value is valid (not NaN)"""
    try:
        return not math.isnan(float(x))
    except:
        return False

def svd_inv(a):
    """Compute inverse using SVD for numerical stability"""
    u, s, v = np.linalg.svd(a)
    ainv = np.dot(v.transpose(), np.dot(np.diag(s**-1), u.transpose()))
    return ainv

def rts_smoother(kf, mu, cov, Fs, Qs, inv=svd_inv):
    """
    Rauch-Tung-Striebel smoother implementation
    
    Args:
        kf: Kalman filter instance
        mu: List of state means
        cov: List of state covariances
        Fs: List of state transition matrices
        Qs: List of process noise covariances
        inv: Matrix inversion function
        
    Returns:
        x: Smoothed states
        P: Smoothed covariances
        K: Smoother gains
        PP: Predicted covariances
    """
    if len(mu) < 2:
        return mu, cov, None, None
        
    n = len(mu)
    dim_x = mu[0].shape[0]
    
    # Allocate numpy arrays
    x = np.zeros((n, dim_x, 1))
    P = np.zeros((n, dim_x, dim_x))
    K = np.zeros((n-1, dim_x, dim_x))
    PP = np.zeros((n-1, dim_x, dim_x))
    
    # Set last state
    x[-1] = mu[-1]
    P[-1] = cov[-1]
    
    # Run the smoother backward
    for k in range(n-2, -1, -1):
        PP[k] = Fs[k+1] @ cov[k] @ Fs[k+1].T + Qs[k+1]
        
        try:
            K[k] = cov[k] @ Fs[k+1].T @ inv(PP[k])
        except:
            # Fallback if inversion fails
            K[k] = cov[k] @ Fs[k+1].T @ np.linalg.pinv(PP[k])
        
        x[k] = mu[k] + K[k] @ (x[k+1] - Fs[k+1] @ mu[k])
        P[k] = cov[k] + K[k] @ (P[k+1] - PP[k]) @ K[k].T
    
    return x, P, K, PP

def smooth_with_kalman(df, measurement_noise=KF_MEASUREMENT_NOISE, 
                      process_noise=KF_PROCESS_NOISE, 
                      time_gap_threshold=KF_TIME_GAP_THRESHOLD,
                      init_covariance=KF_INIT_COVARIANCE,
                      fit_error_weight=0.5):
    """
    Apply TATOR Kalman filter with RTS smoothing to navigation data
    
    Args:
        df (pandas.DataFrame): DataFrame with navigation data including Latitude, Longitude, Timestamp
        measurement_noise (float): Measurement noise parameter (default: global KF_MEASUREMENT_NOISE)
        process_noise (float): Process noise parameter (default: global KF_PROCESS_NOISE)
        time_gap_threshold (float): Time gap threshold in seconds (default: global KF_TIME_GAP_THRESHOLD)
        init_covariance (float): Initial covariance (default: global KF_INIT_COVARIANCE)
        fit_error_weight (float): Weight to apply to fit error when scaling measurement noise (0-1)
        
    Returns:
        pandas.DataFrame: DataFrame with smoothed navigation data
    """
    print(f"Applying TATOR Kalman Filter with noise={measurement_noise}, process={process_noise}, gap={time_gap_threshold}...")
    
    # Create a copy of the dataframe to hold smoothed data
    smoothed_df = df.copy()
    
    # Convert timestamps to datetime objects if they're not already
    if not pd.api.types.is_datetime64_any_dtype(df['Timestamp']):
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    
    # Extract required data
    timestamps = df['Timestamp'].to_list()
    latitudes = df['Latitude'].to_list()
    longitudes = df['Longitude'].to_list()
    
    # Check if we have fit error in the diagnostic data
    fit_errors = None
    if 'Fit_Error' in df.columns:
        fit_errors = df['Fit_Error'].to_list()
        print("Using Fit_Error data to adjust measurement noise")
    
    # Initialize Kalman filter for 4D state: [x, y, vx, vy]
    kf = KalmanFilter(dim_x=4, dim_z=2)
    
    # Check if we have enough points
    if len(latitudes) < 2:
        print("Not enough points for Kalman filtering")
        return smoothed_df
        
    # Initialize state
    # We need at least two points to estimate initial velocity
    lat0, lon0 = latitudes[0], longitudes[0]
    lat1, lon1 = latitudes[1], longitudes[1]
    
    # Initial state: [lon, lat, lon_velocity, lat_velocity]
    kf.x = np.array([
        [lon0],
        [lat0],
        [lon1 - lon0],
        [lat1 - lat0],
    ])
    
    # State transition matrix (constant velocity model)
    kf.F = np.array([
        [1., 0., 1., 0.],
        [0., 1., 0., 1.],
        [0., 0., 1., 0.],
        [0., 0., 0., 1.],
    ])
    
    # Measurement matrix (we only measure position)
    kf.H = np.array([
        [1., 0., 0., 0.],
        [0., 1., 0., 0.],
    ])
    
    # Initial covariance matrix (high uncertainty)
    kf.P = np.eye(4) * init_covariance
    
    # Measurement noise (can be adjusted based on fit_error if available)
    kf.R = np.eye(2) * measurement_noise
    
    # Process noise
    kf.Q = np.eye(4) * process_noise
    
    # Storage for filter states for RTS smoothing
    mu = []        # State means
    cov = []       # State covariances
    Fs = []        # State transition matrices
    Qs = []        # Process noise covariances
    
    # Placeholders for smoothed states
    lon_smoothed = []
    lat_smoothed = []
    
    # Track segments for RTS smoothing
    segments = []
    current_segment = {
        'mu': [],
        'cov': [],
        'Fs': [],
        'Qs': [],
        'timestamps': [],
        'indices': []
    }
    
    # Apply Kalman filter
    last_timestamp = timestamps[0]
    
    for i, (timestamp, lat, lon) in enumerate(zip(timestamps, latitudes, longitudes)):
        # Check for time gap
        dt = 0
        if i > 0:
            time_diff = timestamp - last_timestamp
            if isinstance(time_diff, datetime.timedelta):
                dt = time_diff.total_seconds()
            else:
                # Handle numpy.timedelta64
                dt = time_diff.astype('timedelta64[ns]').astype(float) / 1e9
        
        # If there's a large time gap, we start a new segment
        if dt > time_gap_threshold and i > 0:
            # Store the current segment for processing
            if len(current_segment['mu']) > 0:
                segments.append(current_segment)
                
            # Start a new segment
            current_segment = {
                'mu': [],
                'cov': [],
                'Fs': [],
                'Qs': [],
                'timestamps': [],
                'indices': []
            }
            
            # Reinitialize the filter with current position and zero velocity
            if i < len(latitudes) - 1:
                next_lat = latitudes[i+1]
                next_lon = longitudes[i+1]
                kf.x = np.array([
                    [lon],
                    [lat],
                    [next_lon - lon],
                    [next_lat - lat],
                ])
            else:
                kf.x = np.array([
                    [lon],
                    [lat],
                    [0],
                    [0],
                ])
                
            kf.P = np.eye(4) * init_covariance
            print(f"Time gap of {dt:.2f}s detected at index {i}. Starting new filter segment.")
        
        # Adjust measurement noise based on fit error if available
        if fit_errors is not None and i < len(fit_errors) and fit_errors[i] is not None:
            try:
                error_scale = 1.0 + fit_error_weight * float(fit_errors[i])
                kf.R = np.eye(2) * measurement_noise * error_scale
                # print(f"Adjusted R matrix by factor {error_scale} for point {i}")
            except (ValueError, TypeError):
                # If fit_error can't be converted to float, use default noise
                pass
        
        # Create measurement vector [longitude, latitude]
        meas = np.array([[lon], [lat]])
        
        # Prediction step
        kf.predict()
        
        # Store filter state for smoothing if valid
        if not np.any(np.isnan(kf.P)) and not np.any(np.isnan(kf.x)):
            current_segment['mu'].append(kf.x.copy())
            current_segment['cov'].append(kf.P.copy())
            current_segment['Fs'].append(kf.F.copy())
            current_segment['Qs'].append(kf.Q.copy())
            current_segment['timestamps'].append(timestamp)
            current_segment['indices'].append(i)
        
        # Update step with measurement
        kf.update(meas)
        
        # Update last timestamp
        last_timestamp = timestamp
    
    # Add the last segment
    if len(current_segment['mu']) > 0:
        segments.append(current_segment)
    
    # Initialize array for smoothed values with original values
    # (we'll override them with smoothed values where available)
    smoothed_lons = np.array(longitudes)
    smoothed_lats = np.array(latitudes)
    
    # Apply RTS smoothing to each segment
    total_smoothed = 0
    for segment_idx, segment in enumerate(segments):
        if len(segment['mu']) < 2:
            print(f"Segment {segment_idx} has fewer than 2 points, skipping smoothing")
            continue
            
        print(f"Smoothing segment {segment_idx+1}/{len(segments)} with {len(segment['mu'])} points")
        
        # Apply RTS smoothing
        x, P, K, PP = rts_smoother(kf, 
                                 segment['mu'], 
                                 segment['cov'], 
                                 segment['Fs'], 
                                 segment['Qs'])
        
        # Extract smoothed values
        for i, idx in enumerate(segment['indices']):
            if i < len(x):
                smoothed_lons[idx] = x[i][0][0]  # Longitude
                smoothed_lats[idx] = x[i][1][0]  # Latitude
                total_smoothed += 1
    
    # Update the DataFrame with smoothed values
    smoothed_df['Longitude'] = smoothed_lons
    smoothed_df['Latitude'] = smoothed_lats
    
    print(f"TATOR Kalman Filter plus Fit smoothing completed - {total_smoothed}/{len(df)} points smoothed")
    print(f"Total segments: {len(segments)}")
    
    return smoothed_df
