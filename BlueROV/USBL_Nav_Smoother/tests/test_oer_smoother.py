import pandas as pd
import numpy as np
from src.models.oer_smoother import smooth_with_oer_average

def test_oer_smoothing():
    # Create a sample DataFrame to test the OER smoothing function
    sample_data = {
        'Timestamp': pd.date_range(start='2023-01-01', periods=10, freq='T'),
        'Latitude': np.random.uniform(low=34.0, high=35.0, size=10),
        'Longitude': np.random.uniform(low=-120.0, high=-119.0, size=10),
        'Depth': np.random.uniform(low=0, high=100, size=10)
    }
    df = pd.DataFrame(sample_data)

    # Apply OER smoothing
    smoothed_df = smooth_with_oer_average(df)

    # Check if the output DataFrame has the same length as the input
    assert len(smoothed_df) == len(df), "Output DataFrame length does not match input length."

    # Check if the smoothed latitude and longitude are within expected ranges
    assert smoothed_df['Latitude'].min() >= df['Latitude'].min(), "Smoothed latitude is less than original minimum."
    assert smoothed_df['Latitude'].max() <= df['Latitude'].max(), "Smoothed latitude is greater than original maximum."
    assert smoothed_df['Longitude'].min() >= df['Longitude'].min(), "Smoothed longitude is less than original minimum."
    assert smoothed_df['Longitude'].max() <= df['Longitude'].max(), "Smoothed longitude is greater than original maximum."

    # Check if the depth column is unchanged
    assert np.array_equal(smoothed_df['Depth'].values, df['Depth'].values), "Depth values should remain unchanged."

    print("OER smoothing tests passed.")

if __name__ == "__main__":
    test_oer_smoothing()