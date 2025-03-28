import pandas as pd
import numpy as np
from src.models.window_smoother import smooth_with_window
from src.models.oer_smoother import smooth_with_oer_average

def test_window_smoother():
    # Sample data for testing
    data = {
        'Timestamp': pd.date_range(start='2023-01-01', periods=10, freq='T'),
        'Latitude': np.random.uniform(low=34.0, high=35.0, size=10),
        'Longitude': np.random.uniform(low=-118.0, high=-117.0, size=10),
        'Depth': np.random.uniform(low=0, high=100, size=10)
    }
    df = pd.DataFrame(data)

    # Apply window smoothing
    smoothed_df = smooth_with_window(df)

    # Check if the output DataFrame has the same length as the input
    assert len(smoothed_df) == len(df), "Output DataFrame length does not match input length."

    # Check if the smoothed latitude and longitude are within expected range
    assert smoothed_df['Latitude'].min() >= df['Latitude'].min(), "Smoothed latitude is lower than original."
    assert smoothed_df['Latitude'].max() <= df['Latitude'].max(), "Smoothed latitude is higher than original."
    assert smoothed_df['Longitude'].min() >= df['Longitude'].min(), "Smoothed longitude is lower than original."
    assert smoothed_df['Longitude'].max() <= df['Longitude'].max(), "Smoothed longitude is higher than original."

def test_oer_smoother():
    # Sample data for testing
    data = {
        'Timestamp': pd.date_range(start='2023-01-01', periods=10, freq='T'),
        'Latitude': np.random.uniform(low=34.0, high=35.0, size=10),
        'Longitude': np.random.uniform(low=-118.0, high=-117.0, size=10),
        'Depth': np.random.uniform(low=0, high=100, size=10)
    }
    df = pd.DataFrame(data)

    # Apply OER smoothing
    smoothed_df = smooth_with_oer_average(df)

    # Check if the output DataFrame has the same length as the input
    assert len(smoothed_df) == len(df), "Output DataFrame length does not match input length."

    # Check if the smoothed latitude and longitude are within expected range
    assert smoothed_df['Latitude'].min() >= df['Latitude'].min(), "Smoothed latitude is lower than original."
    assert smoothed_df['Latitude'].max() <= df['Latitude'].max(), "Smoothed latitude is higher than original."
    assert smoothed_df['Longitude'].min() >= df['Longitude'].min(), "Smoothed longitude is lower than original."
    assert smoothed_df['Longitude'].max() <= df['Longitude'].max(), "Smoothed longitude is higher than original."