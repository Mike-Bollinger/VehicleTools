import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Load the CSV file with the correct delimiter
file_path = r"D:\AUV\NF-24-06\DIVE016\Vehicle Data\DIVE016_2024-06-18_NAVLOG_240618_135714_nav.csv"
data = pd.read_csv(file_path, delimiter=';')

# Define the epoch time for January 1, 2024
epoch_2024 = 1704067200

# Filter the data to include only timestamps greater than the epoch time for 2024
data = data[data['timestamp s'] > epoch_2024]


# Convert timestamp to a more readable format if necessary
# Uncomment if timestamps are in epoch format
data['timestamp s'] = pd.to_datetime(data['timestamp s'], unit='s')

# Convert Pitch, Roll, and Heading from radians to degrees
data['Pitch deg'] = np.degrees(data['Pitch rad'])
data['Roll deg'] = np.degrees(data['Roll rad'])
data['Heading deg'] = np.degrees(data['Heading rad'])

# Convert Speed from m/s to knots
data['Speed knots'] = data['Speed m/s'] * 1.94384

# List of attributes
attributes = ['latitude deg', 'Longitude deg', 'Depth m', 'Bottom m', 'Pitch deg', 'Roll deg', 'Heading deg', 'Speed knots']

# Function to plot the selected attribute against time
def plot_attribute(attribute):
    plt.figure(figsize=(10, 6))
    plt.plot(data['timestamp s'], data[attribute], label=attribute)
    plt.xlabel('Time')
    plt.ylabel(attribute)
    plt.title(f'{attribute} vs Time')
    plt.legend()
    plt.grid(True)
    plt.show()


# Example usage: Plot 'Depth m' against time
plot_attribute('Roll deg')