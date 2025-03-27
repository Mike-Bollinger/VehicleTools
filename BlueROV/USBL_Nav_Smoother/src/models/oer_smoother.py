# FILE: /USBL_Nav_Smoother/USBL_Nav_Smoother/src/models/oer_smoother.py

import pandas as pd
import numpy as np

OER_WINDOW_SIZE = 5  # Example window size for moving average
OER_TOLERANCE = 0.1   # Example tolerance for simplification

def smooth_with_oer_average(df):
    """
    Apply OER's simple moving average algorithm to navigation data.
    Based on the smooth_rov_nav script, but adapted for direct DataFrame input/output.
    Uses global parameters: OER_WINDOW_SIZE, OER_TOLERANCE.
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
        if i > window // 2 and i < len(x) - window // 2:
            avg_x = np.mean(x[i - window // 2:i + window // 2 + 1])
            avg_y = np.mean(y[i - window // 2:i + window // 2 + 1])
            avg_z = np.mean(z[i - window // 2:i + window // 2 + 1])
            out_pts.append((avg_x, avg_y, avg_z))
        else:
            # For points at beginning and end, use existing values
            out_pts.append((x[i], y[i], z[i]))
    
    # Update the smoothed dataframe
    smoothed_df['Longitude'] = [p[0] for p in out_pts]
    smoothed_df['Latitude'] = [p[1] for p in out_pts]
    
    print(f"OER Moving Average smoothing completed with window size {OER_WINDOW_SIZE}")
    return smoothed_df

def calculate_track_distance(df):
    """
    Calculate the total distance traveled in the track in kilometers.
    """
    total_distance = 0
    for i in range(1, len(df)):
        point1 = (df.iloc[i-1]['Latitude'], df.iloc[i-1]['Longitude'])
        point2 = (df.iloc[i]['Latitude'], df.iloc[i]['Longitude'])
        # Calculate distance between consecutive points in meters
        distance = geodesic(point1, point2).kilometers
        total_distance += distance
    return total_distance