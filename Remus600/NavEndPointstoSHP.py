import csv
import os
import re
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from datetime import datetime

def parse_lat_long(lat_str, long_str):
    """Parse latitude and longitude from strings like '28N05.739' and '090W57.551'"""
    
    if not lat_str or not long_str or pd.isna(lat_str) or pd.isna(long_str):
        return None, None
    
    # Clean input strings
    lat_str = str(lat_str).strip()
    long_str = str(long_str).strip()
    
    # Debug output
    print(f"Attempting to parse: '{lat_str}', '{long_str}'")
    
    # Extract degrees, minutes, and direction using more flexible patterns
    lat_match = re.match(r'(\d+)([NS])(\d+\.\d+)', lat_str)
    long_match = re.match(r'(\d+)([EW])(\d+\.\d+)', long_str)
    
    # Try alternate pattern for longitude that might have leading zeros
    if not long_match:
        long_match = re.match(r'0*(\d+)([EW])(\d+\.\d+)', long_str)
    
    if lat_match and long_match:
        lat_deg = float(lat_match.group(1))
        lat_dir = lat_match.group(2)
        lat_min = float(lat_match.group(3))
        
        long_deg = float(long_match.group(1))
        long_dir = long_match.group(2)
        long_min = float(long_match.group(3))
        
        # Convert to decimal degrees
        lat_decimal = lat_deg + lat_min/60.0
        if lat_dir == 'S':
            lat_decimal = -lat_decimal
            
        long_decimal = long_deg + long_min/60.0
        if long_dir == 'W':
            long_decimal = -long_decimal
            
        return lat_decimal, long_decimal
    else:
        print(f"Warning: Could not parse coordinates: '{lat_str}', '{long_str}'")
        return None, None

def convert_csv_to_individual_shapefiles(csv_path, output_dir):
    """
    Convert the CSV file to individual shapefiles for each dive,
    with each shapefile containing start and end points for that dive
    """
    
    # Read the CSV file
    df = pd.read_csv(csv_path)
    
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # Counter for successful dive shapefiles
    successful_dives = 0
    
    for i, row in df.iterrows():
        print(f"\nProcessing row {i+1}")
        
        dive_num = str(row.get('Dive ', '')).strip()
        if not dive_num or pd.isna(dive_num):
            print(f"Skipping row with no dive number")
            continue
        
        print(f"Processing dive: {dive_num}")
        
        # List to store data for this dive's points
        dive_data = []
        
        # Extract latitude and longitude for start and end points
        start_lat_str = str(row.get('LatitudeStart', ''))
        start_long_str = str(row.get('LongitudeStart', ''))
        end_lat_str = str(row.get('LatitudeEnd', ''))
        end_long_str = str(row.get('LongitudeEnd', ''))
        
        # Parse coordinates
        print(f"Parsing start coordinates: '{start_lat_str}', '{start_long_str}'")
        start_lat, start_long = parse_lat_long(start_lat_str, start_long_str)
        
        print(f"Parsing end coordinates: '{end_lat_str}', '{end_long_str}'")
        end_lat, end_long = parse_lat_long(end_lat_str, end_long_str)
        
        # Convert numeric values safely
        try:
            plan_dist = int(str(row.get('Planned', '0')).replace(',', '')) if pd.notna(row.get('Planned', '')) and str(row.get('Planned', '')).replace(',', '').strip().isdigit() else 0
        except (ValueError, TypeError):
            plan_dist = 0
            
        try:
            act_dist = int(str(row.get('Actual', '0')).replace(',', '')) if pd.notna(row.get('Actual', '')) and str(row.get('Actual', '')).replace(',', '').strip().isdigit() else 0
        except (ValueError, TypeError):
            act_dist = 0
        
        # Add start point if valid
        if start_lat is not None and start_long is not None:
            start_point = Point(start_long, start_lat)
            point_data = {
                'DIVE_NUM': dive_num,
                'POINT_TYPE': 'Start',
                'LABEL': f"{dive_num}_Start",
                'CRUISE': str(row.get('Cruise', '')),
                'TIME': str(row.get('Dive Start', '')),
                'DURATION': str(row.get('Duration', '')),
                'PLAN_DIST': plan_dist,
                'ACT_DIST': act_dist,
                'AREA': str(row.get('Operations Area', '')),
                'ALTITUDE': str(row.get('Altitude', '')),
                'geometry': start_point
            }
            dive_data.append(point_data)
            print(f"Added start point for dive {dive_num}: ({start_lat}, {start_long})")
        else:
            print(f"Skipping start point for dive {dive_num} due to coordinate parsing issues")
        
        # Add end point if valid
        if end_lat is not None and end_long is not None:
            end_point = Point(end_long, end_lat)
            point_data = {
                'DIVE_NUM': dive_num,
                'POINT_TYPE': 'End',
                'LABEL': f"{dive_num}_End",
                'CRUISE': str(row.get('Cruise', '')),
                'TIME': str(row.get('Dive End ', '')),
                'DURATION': str(row.get('Duration', '')),
                'PLAN_DIST': plan_dist,
                'ACT_DIST': act_dist,
                'AREA': str(row.get('Operations Area', '')),
                'ALTITUDE': str(row.get('Altitude', '')),
                'geometry': end_point
            }
            dive_data.append(point_data)
            print(f"Added end point for dive {dive_num}: ({end_lat}, {end_long})")
        else:
            print(f"Skipping end point for dive {dive_num} due to coordinate parsing issues")
        
        # Skip creating shapefile if no valid data for this dive
        if not dive_data:
            print(f"No valid coordinates found for {dive_num}. Shapefile not created.")
            continue
        
        # Create a GeoDataFrame for this dive
        gdf = gpd.GeoDataFrame(dive_data, crs="EPSG:4326")
        
        # Define output shapefile path for this dive
        output_shp = os.path.join(output_dir, f"{dive_num}_Start-End_Points.shp")
        
        # Save to shapefile
        gdf.to_file(output_shp, driver='ESRI Shapefile')
        
        print(f"Shapefile created successfully for {dive_num}: {output_shp}")
        successful_dives += 1
    
    print(f"\nProcessing complete. Created {successful_dives} individual dive shapefiles.")

if __name__ == "__main__":
    # Input CSV file path
    csv_path = r"c:\Users\Mike.Bollinger\Downloads\NOAA_MDBC_AUV Mission Log_Combined.xlsx - PC2403_VOYIS.csv"
    
    # Output directory for shapefiles - in the same directory as the CSV
    csv_dir = os.path.dirname(csv_path)
    output_dir = os.path.join(csv_dir, "Dive_Endpoints")
    
    # Convert CSV to individual shapefiles
    convert_csv_to_individual_shapefiles(csv_path, output_dir)