import pandas as pd
from datetime import datetime


# Function to convert degrees-minutes format to decimal degrees
def dms_to_decimal(coord):
    # Identify the direction (N, S, E, W)
    direction = coord[-1]  # Get the last character which is the direction

    # Remove the directional character (N/S/E/W) to isolate the numeric part
    coord_num = coord[:-1]  # Isolate the numbers, e.g., '28N05.55220' -> '28N05.55220'

    if direction in ['N', 'S']:
        degrees = coord_num[:2]  # First two characters for latitude degrees
        minutes = coord_num[2:]  # Rest is minutes
    elif direction in ['E', 'W']:
        degrees = coord_num[:3]  # First three characters for longitude degrees
        minutes = coord_num[3:]  # Rest is minutes
    else:
        raise ValueError(f"Invalid coordinate direction: {direction}")

    # Convert to decimal degrees
    try:
        decimal_degrees = int(degrees) + float(minutes) / 60
    except ValueError as e:
        raise ValueError(f"Error converting {coord} to decimal degrees: {e}")

    # Handle negative values for S and W
    if direction in ['S', 'W']:
        decimal_degrees *= -1

    return decimal_degrees


# Load and parse the NAV txt file
def load_nav_data(nav_file):
    nav_data = []
    with open(nav_file, 'r') as file:
        for line in file.readlines()[2:]:  # Skip the header rows
            fields = line.split(',')
            nav_time = parse_nav_time(fields[0].strip())

            # Extract lon/lat and split them by the space separator
            lon_lat_str = fields[2].strip()  # Example: '28N05.55220  90W56.45729'
            lon_lat = lon_lat_str.split()  # Split into two parts: [Lat, Lon]

            # Ensure we have two parts (lat and long)
            if len(lon_lat) != 2:
                print(f"Error: Unexpected lat/lon format in line: {line}")
                continue

            # Convert Lat and Lon into decimal degrees
            try:
                lat_dd = dms_to_decimal(lon_lat[0])  # Latitude in decimal degrees
                lon_dd = dms_to_decimal(lon_lat[1])  # Longitude in decimal degrees
            except ValueError as e:
                print(f"Error converting lat/lon: {e}")
                continue

            altitude = float(fields[3].strip())
            heading = float(fields[5].strip())
            pitch = float(fields[8].strip())
            roll = float(fields[10].strip())

            nav_data.append({
                'time': nav_time, 'lon': lon_dd, 'lat': lat_dd, 'altitude': altitude,
                'heading': heading, 'pitch': pitch, 'roll': roll
            })
    return nav_data


# Function to parse NAV time to datetime object
def parse_nav_time(nav_time_str):
    return datetime.strptime(nav_time_str, "%H:%M:%S.%f")


# Function to find the closest nav data for a given image timestamp
def find_closest_nav_data(image_time, nav_data):
    closest_entry = min(nav_data, key=lambda x: abs(x['time'] - image_time))
    return closest_entry


# Process the template and navigation files to generate the output
def process_files(template_file, nav_file, output_file):
    # Load the NAV data
    nav_data = load_nav_data(nav_file)

    # Read the template file (assuming it's structured similarly to CSV)
    with open(template_file, 'r') as file:
        lines = file.readlines()

    # Extract the header from the template
    header = lines[0].strip()
    template_data = lines[1:]

    # List to store new rows for output
    output_rows = []

    # Process each row in the template
    for row in template_data:
        fields = row.split(',')
        image_filename = fields[0].strip()  # Extract the image filename
        image_time = parse_image_timestamp(image_filename)  # Extract timestamp from filename
        closest_nav = find_closest_nav_data(image_time, nav_data)  # Find closest nav data

        # Modify the fields with updated values (longitude, latitude, yaw, pitch, roll)
        fields[2] = f"{closest_nav['lon']:.6f}"  # Longitude
        fields[3] = f"{closest_nav['lat']:.6f}"  # Latitude
        fields[4] = f"{closest_nav['altitude']:.6f}"  # Altitude
        fields[5] = f"{closest_nav['heading']:.6f}"  # Yaw (Heading)
        fields[6] = f"{closest_nav['pitch']:.6f}"  # Pitch
        fields[7] = f"{closest_nav['roll']:.6f}"  # Roll

        output_rows.append(','.join(fields))  # Create a new row

    # Write the updated data to the output CSV file
    with open(output_file, 'w') as outfile:
        outfile.write(header + '\n')  # Write the header
        outfile.write('\n'.join(output_rows))  # Write the data rows

    print(f"CSV file has been generated at {output_file}")


# Main function for manual testing
def main():
    # Define file paths manually for testing
    template_file = r"C:\Users\Mike.Bollinger\Downloads\Template.txt"  # Replace with your template file path
    nav_file = r"C:\Users\Mike.Bollinger\Downloads\DIVE003_NAV.txt"  # Replace with your NAV file path
    output_file = r"C:\Users\Mike.Bollinger\Downloads\DIVE003_Attitude_Output.txt"  # Define where to save the output CSV

    # Call the processing function
    process_files(template_file, nav_file, output_file)


if __name__ == "__main__":
    main()
