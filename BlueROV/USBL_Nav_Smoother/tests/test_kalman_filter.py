import unittest
import pandas as pd
from src.models.kalman_filter import smooth_with_kalman
from src.models.window_smoother import smooth_navigation
from src.models.oer_smoother import smooth_with_oer_average

class TestKalmanFilter(unittest.TestCase):

    def setUp(self):
        # Sample data for testing
        self.df = pd.DataFrame({
            'Timestamp': pd.date_range(start='2023-01-01', periods=5, freq='T'),
            'Latitude': [34.0, 34.1, 34.2, 34.1, 34.0],
            'Longitude': [-118.0, -118.1, -118.2, -118.1, -118.0],
            'Depth': [10, 10, 10, 10, 10],
            'Fit_Error': [0.1, 0.2, 0.1, 0.2, 0.1]
        })

    def test_kalman_smoothing(self):
        smoothed_df = smooth_with_kalman(self.df)
        self.assertEqual(len(smoothed_df), len(self.df))
        self.assertTrue('Latitude' in smoothed_df.columns)
        self.assertTrue('Longitude' in smoothed_df.columns)

    def test_window_smoothing(self):
        window_smoothed_df = smooth_navigation(self.df)
        self.assertEqual(len(window_smoothed_df), len(self.df))
        self.assertTrue('Latitude' in window_smoothed_df.columns)
        self.assertTrue('Longitude' in window_smoothed_df.columns)

    def test_oer_smoothing(self):
        oer_smoothed_df = smooth_with_oer_average(self.df)
        self.assertEqual(len(oer_smoothed_df), len(self.df))
        self.assertTrue('Latitude' in oer_smoothed_df.columns)
        self.assertTrue('Longitude' in oer_smoothed_df.columns)

if __name__ == '__main__':
    unittest.main()