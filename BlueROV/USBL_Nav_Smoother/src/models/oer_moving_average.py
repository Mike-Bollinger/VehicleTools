# FILE: /USBL_Nav_Smoother/src/models/oer_moving_average.py

import pandas as pd
import numpy as np
import math
from shapely.geometry import LineString
from scipy.interpolate import interp1d
import traceback

# Configuration parameters for OER Moving Average
# ---------------------------------------------
# OER_WINDOW_SIZE: Controls how many points are included in each moving average calculation.
#   - Higher values (e.g., 20, 25): Create smoother tracks but may oversmooth small movements
#   - Lower values (e.g., 5, 10): Retain more detail and smaller movements, less smoothing
#   - Should be an odd number for centered averaging
#   - Recommended range: 5-25, with 15 being a good balance for typical ROV data
OER_WINDOW_SIZE = 15

# OER_TOLERANCE: Controls track simplification after smoothing (in decimal degrees).
#   - Higher values (e.g., 0.0001): More aggressive simplification, fewer points, smoother lines
#   - Lower values (e.g., 0.000001): More detailed track, retains more points
#   - Setting to 0 disables simplification entirely
#   - Recommended range: 0.000001-0.0001 (1-10m at typical latitudes)
OER_TOLERANCE = 0.00001

def smooth_with_oer_average(df, window_size=OER_WINDOW_SIZE, tolerance=OER_TOLERANCE):
    """
    Apply OER's simple moving average algorithm to navigation data
    
    Args:
        df (pandas.DataFrame): DataFrame with navigation data including Latitude, Longitude
        window_size (int): Size of the moving window (default: global OER_WINDOW_SIZE)
        tolerance (float): Tolerance for line simplification (default: global OER_TOLERANCE)
        
    Returns:
        pandas.DataFrame: DataFrame with smoothed navigation data
    """
    print(f"Applying OER Moving Average smoothing with window={window_size}, tolerance={tolerance}...")
    
    # Create a copy of the dataframe to hold smoothed data
    smoothed_df = df.copy()
    
    # Get coordinates as numpy arrays for efficient processing
    x = df['Longitude'].values
    y = df['Latitude'].values
    z = df['Depth'].values if 'Depth' in df.columns else np.zeros(len(df))
    
    # Pre-allocate output arrays
    smoothed_x = np.copy(x)
    smoothed_y = np.copy(y)
    smoothed_z = np.copy(z)
    
    # Apply moving average directly to the arrays
    for i in range(len(x)):
        try:
            if i > window_size/2 and i < len(x) - window_size/2:
                # Calculate indices for window, ensuring we don't go out of bounds
                start_idx = max(0, math.floor(i - window_size/2))
                end_idx = min(len(x), math.floor(i + window_size/2))
                
                # Ensure we have actual values (not NaN)
                window_x = x[start_idx:end_idx]
                window_y = y[start_idx:end_idx]
                window_z = z[start_idx:end_idx]
                
                # Filter out any NaN values
                valid_indices = ~(np.isnan(window_x) | np.isnan(window_y))
                
                if np.any(valid_indices):
                    valid_x = window_x[valid_indices]
                    valid_y = window_y[valid_indices]
                    valid_z = window_z[valid_indices]
                    
                    # If we have enough valid values, compute average
                    if len(valid_x) > 0:
                        smoothed_x[i] = np.mean(valid_x)
                        smoothed_y[i] = np.mean(valid_y)
                        smoothed_z[i] = np.mean(valid_z)
        except Exception as e:
            print(f"Error processing point {i}: {e}")
            # Keep original values if there's an error
    
    # Apply line simplification if desired and possible
    if tolerance > 0 and len(df) > 2:
        try:
            # Filter out any NaN or invalid points before creating LineString
            valid_pts = []
            valid_indices = []
            for i in range(len(smoothed_x)):
                if not (np.isnan(smoothed_x[i]) or np.isnan(smoothed_y[i]) or 
                       (abs(smoothed_x[i]) < 0.0001 and abs(smoothed_y[i]) < 0.0001)):
                    valid_pts.append((smoothed_x[i], smoothed_y[i]))
                    valid_indices.append(i)
            
            # Only proceed if we have enough valid points
            if len(valid_pts) > 2:
                # Create and simplify LineString
                line = LineString(valid_pts).simplify(tolerance)
                
                # Get simplified points
                simplified_pts = list(line.coords)
                
                if len(simplified_pts) < len(valid_pts):
                    print(f"Simplification reduced points from {len(valid_pts)} to {len(simplified_pts)}. Re-interpolating...")
                    
                    # Only interp if we have at least 2 points
                    if len(simplified_pts) >= 2:
                        # Create mapping from original valid indices to simplified points
                        simple_idx = np.linspace(0, len(valid_indices)-1, len(simplified_pts))
                        
                        # Extract simplified coordinates
                        simple_x = [p[0] for p in simplified_pts]
                        simple_y = [p[1] for p in simplified_pts]
                        
                        # Create interpolators
                        interp_x = interp1d(simple_idx, simple_x, bounds_error=False, fill_value="extrapolate")
                        interp_y = interp1d(simple_idx, simple_y, bounds_error=False, fill_value="extrapolate")
                        
                        # Apply interpolation to re-populate the valid indices
                        for i, original_idx in enumerate(valid_indices):
                            smoothed_x[original_idx] = interp_x(i)
                            smoothed_y[original_idx] = interp_y(i)
        except Exception as e:
            print(f"Error during simplification: {e}")
            traceback.print_exc()
            # Continue with unsimplified points
    
    # Final check - ensure no invalid values (0,0 or NaN)
    for i in range(len(smoothed_x)):
        if (np.isnan(smoothed_x[i]) or np.isnan(smoothed_y[i]) or 
            (abs(smoothed_x[i]) < 0.0001 and abs(smoothed_y[i]) < 0.0001)):
            print(f"Warning: Invalid coordinate detected at index {i}. Using original coordinate.")
            smoothed_x[i] = x[i]
            smoothed_y[i] = y[i]
    
    # Update the smoothed dataframe
    smoothed_df['Longitude'] = smoothed_x
    smoothed_df['Latitude'] = smoothed_y
    if 'Depth' in smoothed_df.columns:
        smoothed_df['Depth'] = smoothed_z
    
    print(f"OER Moving Average smoothing completed with window size {window_size} and tolerance {tolerance}")
    return smoothed_df