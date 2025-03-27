# FILE: /USBL_Nav_Smoother/USBL_Nav_Smoother/src/utils/file_handlers.py

import os
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString

def read_csv(file_path):
    """
    Read a CSV file and return its contents as a DataFrame.
    """
    return pd.read_csv(file_path)

def write_csv(dataframe, file_path):
    """
    Write a DataFrame to a CSV file.
    """
    dataframe.to_csv(file_path, index=False)

def append_to_csv(dataframe, file_path):
    """
    Append a DataFrame to an existing CSV file.
    """
    dataframe.to_csv(file_path, mode='a', header=False, index=False)

def read_multiple_csv(file_paths):
    """
    Read multiple CSV files and concatenate them into a single DataFrame.
    """
    dataframes = [pd.read_csv(file) for file in file_paths]
    return pd.concat(dataframes, ignore_index=True)

def read_navigation_files(file_paths):
    """
    Read and combine navigation data from ROV navigation CSV files.
    
    Args:
        file_paths (list): List of paths to navigation CSV files
        
    Returns:
        pd.DataFrame: Combined navigation data
    """
    dfs = []
    
    for file_path in file_paths:
        try:
            print(f"Reading navigation file: {file_path}")
            
            # Read CSV file - the files don't have headers, so we'll assign them
            df = pd.read_csv(file_path, header=None)
            
            # Determine the number of columns to assign appropriate headers
            num_cols = df.shape[1]
            
            if num_cols >= 6:
                # Assign column names based on the observed data format
                # Timestamp, ID, Latitude, Longitude, Depth, Additional columns...
                column_names = ['Timestamp', 'ID', 'Latitude', 'Longitude', 'Depth', 'X', 'Y']
                
                # If there are more columns, add generic names
                if num_cols > 7:
                    for i in range(7, num_cols):
                        column_names.append(f'Column_{i}')
                        
                # Assign the column names to the dataframe
                df.columns = column_names[:num_cols]
                
                # Convert timestamp to datetime
                df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
                
                # Keep only the required columns
                df = df[['Timestamp', 'Latitude', 'Longitude', 'Depth']].copy()
                
                dfs.append(df)
                print(f"Successfully processed file with {len(df)} records")
            else:
                print(f"Warning: File {file_path} has unexpected column count ({num_cols}). Skipping.")
                
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            import traceback
            traceback.print_exc()
    
    if not dfs:
        raise ValueError("No valid navigation files were found.")
        
    # Combine all dataframes and sort by timestamp
    combined_df = pd.concat(dfs, ignore_index=True)
    combined_df = combined_df.sort_values('Timestamp').reset_index(drop=True)
    
    return combined_df

def read_diagnostic_files(file_paths):
    """
    Read and combine diagnostic data from ROV diagnostic CSV files.
    
    Args:
        file_paths (list): List of paths to diagnostic CSV files
        
    Returns:
        pd.DataFrame: Combined diagnostic data
    """
    if not file_paths:
        return None
        
    dfs = []
    
    for file_path in file_paths:
        try:
            print(f"Reading diagnostic file: {file_path}")
            
            # Read the file line by line
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            # Process each line
            data = []
            for i, line in enumerate(lines):
                try:
                    # Remove any trailing commas that might cause parsing issues
                    cleaned_line = line.rstrip(',\n')
                    # Split by comma
                    parts = cleaned_line.split(',')
                    # Strip whitespace from each part
                    parts = [part.strip() for part in parts]
                    
                    # Skip lines that don't look like data or are headers
                    if i == 0 and any(word in line for word in ["Timestamp", "ID", "Yaw"]):
                        continue
                        
                    # Ensure we have at least the required fields
                    if len(parts) >= 8:  # We need at least timestamp through range
                        # Keep first 9 fields if available, otherwise pad with None
                        while len(parts) < 9:
                            parts.append(None)
                        
                        # Only take the first 9 fields (discard extras)
                        row = parts[:9]
                        data.append(row)
                    else:
                        print(f"Warning: Line {i+1} does not have sufficient fields. Skipping: {line}")
                        
                except Exception as e:
                    print(f"Error processing line {i+1}: {e}")
            
            # Create dataframe from processed data
            if data:
                # Define column names
                column_names = ['Timestamp', 'ID', 'Local_Yaw', 'Local_Pitch', 'Local_Roll', 
                               'Azimuth', 'Elevation', 'Range', 'Fit_Error']
                
                # Create dataframe
                df = pd.DataFrame(data, columns=column_names)
                
                # Convert timestamp to datetime - handle potential parsing failures
                df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
                
                # Convert numeric columns
                numeric_cols = ['ID', 'Local_Yaw', 'Local_Pitch', 'Local_Roll', 'Azimuth', 'Elevation', 'Range', 'Fit_Error']
                for col in numeric_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # Drop rows with invalid timestamps
                df = df.dropna(subset=['Timestamp'])
                
                dfs.append(df)
                print(f"Successfully processed diagnostic file with {len(df)} records")
            else:
                print(f"Warning: No valid data found in {file_path}")
                
        except Exception as e:
            print(f"Error reading diagnostic file {file_path}: {e}")
            import traceback
            traceback.print_exc()
    
    if not dfs:
        return None
        
    # Combine all dataframes and sort by timestamp
    combined_df = pd.concat(dfs, ignore_index=True)
    combined_df = combined_df.sort_values('Timestamp').reset_index(drop=True)
    
    return combined_df

def save_output_files(data, smoothed_data, comparison_data, output_dir, base_name, model_name=None):
    """
    Save processed navigation data to various output formats.
    
    Args:
        data (pd.DataFrame): Original navigation data
        smoothed_data (pd.DataFrame): Smoothed navigation data
        comparison_data (pd.DataFrame): Comparison data with all models
        output_dir (str): Directory to save output files
        base_name (str): Base name for output files
        model_name (str, optional): Name of the smoothing model used
        
    Returns:
        dict: Dictionary with paths to saved files
    """
    output_files = {}
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Determine file names
    output_csv = os.path.join(output_dir, f"{base_name}_Final.csv")
    output_comparison_csv = os.path.join(output_dir, f"{base_name}_Smoothing_Comparison.csv")
    output_point_shapefile = os.path.join(output_dir, f"{base_name}_Points.shp")
    output_line_shapefile = os.path.join(output_dir, f"{base_name}_Line.shp")
    
    model_suffix = f"_{model_name}" if model_name else "_Smoothed"
    output_smoothed_point_shapefile = os.path.join(output_dir, f"{base_name}_Points{model_suffix}.shp")
    output_smoothed_line_shapefile = os.path.join(output_dir, f"{base_name}_Line{model_suffix}.shp")
    
    # Save CSV files
    data.to_csv(output_csv, index=False)
    comparison_data.to_csv(output_comparison_csv, index=False)
    
    output_files['csv'] = output_csv
    output_files['comparison_csv'] = output_comparison_csv
    
    # Convert original data to GeoDataFrame and save as shapefile
    data_copy = data.copy()
    if isinstance(data_copy['Timestamp'].iloc[0], pd.Timestamp):
        data_copy["Timestamp"] = data_copy["Timestamp"].astype(str)
    
    # Create point shapefile for original data
    gdf_points = gpd.GeoDataFrame(
        data_copy,
        geometry=[Point(xy) for xy in zip(data_copy["Longitude"], data_copy["Latitude"])],
        crs="EPSG:4326"
    )
    gdf_points.to_file(output_point_shapefile)
    output_files['point_shapefile'] = output_point_shapefile
    
    # Create line shapefile for original data
    gdf_sorted = gdf_points.sort_values(by="Timestamp")
    if len(gdf_sorted) > 1:
        line_geometry = LineString([row.geometry for _, row in gdf_sorted.iterrows()])
        gdf_line = gpd.GeoDataFrame(
            pd.DataFrame([{"Timestamp": base_name, "geometry": line_geometry}]), 
            crs="EPSG:4326"
        )
        gdf_line.to_file(output_line_shapefile)
        output_files['line_shapefile'] = output_line_shapefile
    
    # Convert smoothed data to GeoDataFrame and save as shapefile
    smoothed_copy = smoothed_data.copy()
    if isinstance(smoothed_copy['Timestamp'].iloc[0], pd.Timestamp):
        smoothed_copy["Timestamp"] = smoothed_copy["Timestamp"].astype(str)
    
    # Create point shapefile for smoothed data
    gdf_points_smoothed = gpd.GeoDataFrame(
        smoothed_copy,
        geometry=[Point(xy) for xy in zip(smoothed_copy["Longitude"], smoothed_copy["Latitude"])],
        crs="EPSG:4326"
    )
    gdf_points_smoothed.to_file(output_smoothed_point_shapefile)
    output_files['smoothed_point_shapefile'] = output_smoothed_point_shapefile
    
    # Create line shapefile for smoothed data
    gdf_sorted_smoothed = gdf_points_smoothed.sort_values(by="Timestamp")
    if len(gdf_sorted_smoothed) > 1:
        smoothed_line_geometry = LineString([row.geometry for _, row in gdf_sorted_smoothed.iterrows()])
        
        # Add distance attribute if provided in smoothed_data
        attributes = {"Timestamp": base_name}
        if model_name:
            attributes["Model"] = model_name
        
        gdf_line_smoothed = gpd.GeoDataFrame(
            pd.DataFrame([{**attributes, "geometry": smoothed_line_geometry}]),
            crs="EPSG:4326"
        )
        gdf_line_smoothed.to_file(output_smoothed_line_shapefile)
        output_files['smoothed_line_shapefile'] = output_smoothed_line_shapefile
    
    return output_files