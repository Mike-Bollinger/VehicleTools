# FILE: /USBL_Nav_Smoother/USBL_Nav_Smoother/src/models/window_smoother.py

import pandas as pd
import numpy as np
from scipy.ndimage import gaussian_filter1d
from geopy.distance import geodesic  # Add this import as it's used in calculate_window_distance

# Configuration parameters for NCCOS Window & Gaussian Filter
# ---------------------------------------------------------
# WINDOW_SIZE: Controls how many points are included in each moving window calculation.
#   - Higher values (e.g., 11, 15): Create smoother tracks but may miss small-scale features
#   - Lower values (e.g., 3, 5): Preserve more detail but provide less smoothing
#   - Should be an odd number to ensure the window is centered on each point
#   - Recommended range: 3-15, depending on data density and noise level
WINDOW_SIZE = 7

# GAUSSIAN_SIGMA: Determines the width of the Gaussian kernel for weighting points within window.
#   - Higher values (e.g., 3.0, 4.0): Give more weight to distant points, stronger smoothing
#   - Lower values (e.g., 0.5, 1.0): Focus more on central points, preserving more detail
#   - Recommended range: 0.5-4.0, with 1.0-2.0 being a good balance for most data
GAUSSIAN_SIGMA = 2.0

def smooth_navigation(df, window_size=WINDOW_SIZE, gaussian_sigma=GAUSSIAN_SIGMA):
    """
    Apply NCCOS window-based smoothing with Gaussian filter to navigation data
    
    Args:
        df (pandas.DataFrame): DataFrame with navigation data including Latitude, Longitude
        window_size (int): Size of the moving window (default: WINDOW_SIZE global)
        gaussian_sigma (float): Standard deviation for Gaussian kernel (default: GAUSSIAN_SIGMA global)
        
    Returns:
        pandas.DataFrame: DataFrame with smoothed navigation data
    """
    print(f"Applying NCCOS Moving Window and Gaussian Filter smoothing with window={window_size}, sigma={gaussian_sigma}...")
    
    # Create a copy of the dataframe to hold smoothed data
    smoothed_df = df.copy()
    
    # Apply windowed Gaussian smoothing to Latitude and Longitude
    # We use a centered window approach with Gaussian weighting
    
    # Extract coordinates to numpy arrays
    lats = df['Latitude'].values
    lons = df['Longitude'].values
    
    # Apply Gaussian filter directly to the arrays
    # Note: mode='nearest' handles edges by using the nearest value
    smoothed_lats = gaussian_filter1d(lats, sigma=gaussian_sigma, mode='nearest')
    smoothed_lons = gaussian_filter1d(lons, sigma=gaussian_sigma, mode='nearest')
    
    # Additional moving window averaging for enhanced smoothing
    window_half = window_size // 2
    final_lats = np.copy(smoothed_lats)
    final_lons = np.copy(smoothed_lons)
    
    for i in range(len(df)):
        # Calculate window indices, handling boundaries
        start_idx = max(0, i - window_half)
        end_idx = min(len(df), i + window_half + 1)
        
        # Compute mean within window
        final_lats[i] = np.mean(smoothed_lats[start_idx:end_idx])
        final_lons[i] = np.mean(smoothed_lons[start_idx:end_idx])
    
    # Update the dataframe with smoothed values
    smoothed_df['Latitude'] = final_lats
    smoothed_df['Longitude'] = final_lons
    
    print(f"NCCOS Moving Window and Gaussian Filter smoothing completed with window size {window_size} and sigma {gaussian_sigma}")
    return smoothed_df

def calculate_window_distance(df):
    """
    Calculate the total distance traveled in the track using the smoothed data.

    Args:
        df (pd.DataFrame): DataFrame containing smoothed navigation data.

    Returns:
        float: Total distance traveled in kilometers.
    """
    total_distance = 0
    for i in range(1, len(df)):
        point1 = (df.iloc[i-1]['Latitude'], df.iloc[i-1]['Longitude'])
        point2 = (df.iloc[i]['Latitude'], df.iloc[i]['Longitude'])
        distance = geodesic(point1, point2).kilometers
        total_distance += distance
    return total_distance