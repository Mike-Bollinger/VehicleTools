"""
Survey123 to Smartsheet Integration Script

METADATA:
    Title: Survey123 to Smartsheet Dive Log Integration
    Author: Mike Bollinger (mike.bollinger@noaa.gov)
    Organization: NOAA/NCCOS
    Version: 2.0.0
    Created: December 2, 2024
    Last Modified: June 27, 2025
    Python Version: 3.8+

CREDITS:
    Original Framework: Logan Kline
    AI Assistance: GitHub Copilot & ChatGPT v4.0
    Based on: NCCOS UMS AUV Database integration workflows

DESCRIPTION:
    Integrates Survey123 dive log data with Smartsheet to automatically update 
    Smartsheet rows with new Survey123 submissions. The script fetches data from 
    ArcGIS Online, processes and formats it, then uploads new records to Smartsheet 
    while avoiding duplicates.

FEATURES:
    - Connects to ArcGIS Online Survey123 service
    - Extracts and processes dive log data
    - Formats data for Smartsheet compatibility
    - Checks for existing records to prevent duplicates
    - Uploads new records with comprehensive error handling
    - Provides detailed logging and progress tracking

REQUIREMENTS:
    - arcgis (ArcGIS API for Python)
    - smartsheet-python-sdk
    - pandas
    - Valid ArcGIS Online credentials
    - Valid Smartsheet API token with appropriate permissions

USAGE:
    python survey123_to_smartsheet_logs.py

CONFIGURATION:
    - Survey123 Layer ID: ca90818eee7343f88e9ff02d0f0a9dd3 (NCCOS ONLY)
    - Smartsheet ID: 3136216628520844 (NCCOS ONLY)
    - Update access tokens and IDs as needed

CHANGELOG:
    v2.0.0 (2025-06-27): Converted from Jupyter notebook to standalone script
                         Added comprehensive error handling and logging
                         Improved code organization and documentation
    v1.0.0 (2024-12-02): Initial Jupyter notebook version
"""

import arcgis.apps.survey123
import smartsheet
import pandas as pd
from arcgis.gis import GIS
import requests
import json
from datetime import datetime

# Script version for internal tracking
__version__ = "2.0.0"

def main():
    print("=" * 80)
    print(f"Survey123 to Smartsheet Integration Script v{__version__}")
    print("=" * 80)
    
    # Start by pulling down the Survey123 data and formatting it
    print("\n1. Connecting to ArcGIS Online...")
    try:
        gis = GIS('home')
        print(f"✓ Logged in to {gis.properties.name} as {gis.properties.user.username}")
    except Exception as e:
        print(f"✗ Error connecting to ArcGIS Online: {e}")
        return
    
    # Survey123 Configuration
    print("\n2. Fetching Survey123 data...")
    try:
        # Access and save layers from AGOL
        s123_divedata = gis.content.get('ca90818eee7343f88e9ff02d0f0a9dd3').layers[1]  # NCCOS UMS AUV database point layer
        print("✓ Connected to Survey123 layer")
        
        # Convert to DataFrame
        s123_divedata_dbf = pd.DataFrame(s123_divedata.query().sdf)
        print(f"✓ Retrieved {len(s123_divedata_dbf)} records from Survey123")
        print(f"  Columns: {list(s123_divedata_dbf.columns)}")
    except Exception as e:
        print(f"✗ Error fetching Survey123 data: {e}")
        return
    
    # Extract x, y coordinates from SHAPE column
    print("\n3. Processing coordinate data...")
    try:
        s123_divedata_dbf[['x', 'y']] = s123_divedata_dbf['SHAPE'].apply(
            lambda shape: pd.Series([shape['x'], shape['y']]) if isinstance(shape, dict) else pd.Series([None, None])
        )
        print("✓ Extracted coordinates from SHAPE column")
    except Exception as e:
        print(f"✗ Error processing coordinates: {e}")
        return
    
    # Select relevant columns
    print("\n4. Selecting and formatting data columns...")
    try:
        columns_to_keep = ["globalid", "Project", "CruiseID", "StudyRegion", "VesselPlatform", 
                          "Vehicle", "Pilot", "Crew", "DeployID", "SiteID", "DeployDate", 
                          "DeployTime", "y", "x", "SurfaceTime", "DeploymentNotes"]
        
        s123_divedata_dbf_sub = s123_divedata_dbf.loc[:, columns_to_keep]
        s123_divedata_dbf_sub = s123_divedata_dbf_sub.reset_index(drop=True)
        print(f"✓ Selected {len(columns_to_keep)} columns for processing")
    except Exception as e:
        print(f"✗ Error selecting columns: {e}")
        return
    
    # Rename columns to match Smartsheet
    print("\n5. Renaming columns to match Smartsheet format...")
    try:
        column_mapping = {
            "globalid": "globalid",
            "Project": "Project", 
            "CruiseID": "Mission",
            "StudyRegion": "Location",
            "VesselPlatform": "Platform",
            "Vehicle": "Vehicle",
            "Pilot": "Pilot",
            "Crew": "Team",
            "DeployDate": "Dive Date",
            "DeployID": "Dive Number",
            "SiteID": "Site",
            "DeployTime": "Mission Start Time",
            "y": "Start Latitude",
            "x": "Start Longitude",
            "SurfaceTime": "End Time",
            "DeploymentNotes": "Dive Description"
        }
        
        s123_divedata_dbf_reset = s123_divedata_dbf_sub.rename(columns=column_mapping)
        s123_divedata_dbf_reset.reset_index(drop=True, inplace=True)
        print("✓ Columns renamed successfully")
        print(f"  New columns: {list(s123_divedata_dbf_reset.columns)}")
    except Exception as e:
        print(f"✗ Error renaming columns: {e}")
        return
    
    # Format data fields
    print("\n6. Formatting data fields...")
    try:
        # Debug: Print data types and sample values before formatting
        print("  Debug - Data types and sample values:")
        for col in ['Mission Start Time', 'End Time', 'Dive Date']:
            print(f"    {col}:")
            print(f"      Data type: {s123_divedata_dbf_reset[col].dtype}")
            print(f"      Non-null count: {s123_divedata_dbf_reset[col].notna().sum()}")
            print(f"      Null count: {s123_divedata_dbf_reset[col].isna().sum()}")
            print(f"      Sample values: {s123_divedata_dbf_reset[col].dropna().head(3).tolist()}")
            print(f"      Null values preview: {s123_divedata_dbf_reset[col].isna().head(10).tolist()}")
        
        # Convert time fields to HH:MM format with null handling
        print("  Processing Mission Start Time...")
        s123_divedata_dbf_reset['Mission Start Time'] = s123_divedata_dbf_reset['Mission Start Time'].apply(
            lambda x: pd.to_datetime(x, format='%H:%M:%S:%f', errors='coerce').strftime('%H:%M') 
            if pd.notna(x) else ''
        )
        
        print("  Processing End Time...")
        s123_divedata_dbf_reset['End Time'] = s123_divedata_dbf_reset['End Time'].apply(
            lambda x: pd.to_datetime(x, format='%H:%M:%S:%f', errors='coerce').strftime('%H:%M') 
            if pd.notna(x) else ''
        )
        
        # Format dates with null handling
        print("  Processing Dive Date...")
        s123_divedata_dbf_reset['Dive Date'] = s123_divedata_dbf_reset['Dive Date'].apply(
            lambda x: datetime.strptime(x, "%m/%d/%Y").strftime("%Y-%m-%d") 
            if pd.notna(x) and isinstance(x, str) else ''
        )
        
        # Fix data inconsistencies
        s123_divedata_dbf_reset['Location'] = s123_divedata_dbf_reset['Location'].replace(
            "FloridaAtlantic", "Florida Atlantic"
        )
        s123_divedata_dbf_reset['Project'] = s123_divedata_dbf_reset['Project'].replace(
            "M:IR", "Mission: Iconic Reefs"
        )
        s123_divedata_dbf_reset['Project'] = s123_divedata_dbf_reset['Project'].replace(
            "BOEM-CLB", "BOEM: Carolina Long Bay"
        )
        
        print("✓ Data formatting completed")
    except Exception as e:
        print(f"✗ Error formatting data: {e}")
        return
    
    # Get list of Survey123 global IDs
    s123_divedata_globalid = s123_divedata_dbf_reset['globalid'].tolist()
    print(f"✓ Found {len(s123_divedata_globalid)} global IDs in Survey123 data")
    
    # Start working with Smartsheet
    print("\n" + "=" * 60)
    print("Starting Smartsheet Integration")
    print("=" * 60)
    
    print("\n7. Connecting to Smartsheet...")
    try:
        # Set up Smartsheet access
        access_token = '6H72JtOX0pVZaTumEofA0zla9X1stAruyhHBz'
        smartSheet_Client = smartsheet.Smartsheet(access_token, api_base=smartsheet.__gov_base__)
        smartSheet_Client.errors_as_exceptions(True)
        divelog_sheetid = '3136216628520844'
        print("✓ Connected to Smartsheet successfully")
    except Exception as e:
        print(f"✗ Error connecting to Smartsheet: {e}")
        return
    
    # Get sheet and find most recent edit
    print("\n8. Analyzing existing Smartsheet data...")
    try:
        client = smartSheet_Client
        sheet = client.Sheets.get_sheet(divelog_sheetid)
        column_id_map = get_column_id_map(sheet)
        
        edit_date_column_id = column_id_map.get('Edit Date')
        if not edit_date_column_id:
            print("⚠ Edit Date column not found.")
        else:
            max_edit_date = get_max_edit_date(sheet, edit_date_column_id)
            if not max_edit_date:
                print("⚠ No edit date found in the Smartsheet.")
            else:
                print(f"✓ Max Edit Date found: {max_edit_date}")
        
        print(f"✓ Retrieved sheet with {len(sheet.rows)} rows")
    except Exception as e:
        print(f"✗ Error analyzing Smartsheet: {e}")
        return
    
    # Get existing global IDs from Smartsheet
    print("\n9. Extracting existing global IDs from Smartsheet...")
    try:
        COLUMN_NAME = "globalid"
        
        # Find the column ID based on the column name
        column_id = None
        for column in sheet.columns:
            if column.title == COLUMN_NAME:
                column_id = column.id
                break
        
        if column_id is None:
            print(f"✗ Column '{COLUMN_NAME}' not found in the sheet.")
            return
        else:
            # Extract populated values from the specified column
            smartsheet_divedata_globalids = []
            for row in sheet.rows:
                for cell in row.cells:
                    if cell.column_id == column_id and cell.value is not None:
                        smartsheet_divedata_globalids.append(cell.value)
                        break  # Move to the next row after finding a populated value
            
            print(f"✓ Found {len(smartsheet_divedata_globalids)} existing global IDs in Smartsheet")
    except Exception as e:
        print(f"✗ Error extracting global IDs: {e}")
        return
    
    # Compare lists and identify new records
    print("\n10. Identifying new records to upload...")
    try:
        newdivedata = s123_divedata_dbf_reset[
            ~s123_divedata_dbf_reset['globalid'].isin(smartsheet_divedata_globalids)
        ]
        print(f"✓ Found {len(newdivedata)} new records to upload")
        
        if len(newdivedata) == 0:
            print("ℹ No new records to upload. Process complete.")
            return
        else:
            print(f"  New records preview:")
            print(f"  {newdivedata[['globalid', 'Project', 'Mission', 'Dive Date']].head()}")
    except Exception as e:
        print(f"✗ Error comparing records: {e}")
        return
    
    # Upload new records to Smartsheet
    print("\n11. Uploading new records to Smartsheet...")
    try:
        # Define the information for the sheet
        sheets_info = [
            {
                'sheet_id': '3136216628520844',
                'fields_map': {
                    'Project': 'Project',
                    'Mission': 'Mission',
                    'Location': 'Location',
                    'Platform': 'Platform',
                    'Vehicle': 'Vehicle',
                    'Dive Date': 'Dive Date',
                    'Dive Number': 'Dive Number',
                    'Site': 'Site',
                    'Mission Start Time': 'Mission Start Time',
                    'Start Latitude': 'Start Latitude',
                    'Start Longitude': 'Start Longitude',
                    'End Time': 'End Time',
                    'Dive Description': 'Dive Description',
                    'globalid': 'globalid'
                }
            }
        ]
        
        # Run the processing for each sheet
        for sheet_info in sheets_info:
            # Map DataFrame columns based on 'fields_map'
            data_to_upload = newdivedata[list(sheet_info['fields_map'].keys())]
            data_to_upload.rename(columns=sheet_info['fields_map'], inplace=True)
            process_sheet(smartSheet_Client, sheet_info, data_to_upload)
        
        print("✓ Upload process completed successfully")
    except Exception as e:
        print(f"✗ Error uploading to Smartsheet: {e}")
        return
    
    print("\n" + "=" * 60)
    print("Process completed successfully!")
    print("=" * 60)


def get_max_edit_date(sheet, edit_date_column_id):
    """Function to get the maximum Edit Date from Smartsheet"""
    max_edit_date = None
    for row in sheet.rows:
        for cell in row.cells:
            if cell.column_id == edit_date_column_id and cell.value:
                edit_date = datetime.strptime(cell.value, '%Y-%m-%dT%H:%M:%SZ').date()
                if not max_edit_date or edit_date > max_edit_date:
                    max_edit_date = edit_date
    return max_edit_date


def get_column_id_map(sheet):
    """Function to get the column ID map"""
    return {col.title: col.id for col in sheet.columns}


def prepare_smartsheet_rows(data, column_id_map, extra_columns):
    """Function to prepare Smartsheet rows"""
    new_rows = []
    
    # Create reverse mapping for debugging (column_id -> column_name)
    id_to_column_map = {v: k for k, v in column_id_map.items()}
    
    # Print column ID mapping for debugging
    print("  Debug - Column ID mapping:")
    for column_name, column_id in column_id_map.items():
        print(f"    {column_name}: {column_id}")
    
    # Check for problematic values in data before creating rows
    print("  Debug - Checking for potential picklist issues:")
    for column in data.columns:
        if column in column_id_map:
            unique_values = data[column].dropna().unique()
            print(f"    {column} (ID: {column_id_map[column]}): {len(unique_values)} unique values")
            print(f"      Values: {list(unique_values)[:10]}{'...' if len(unique_values) > 10 else ''}")
    
    for row_idx, item in data.iterrows():  # Use iterrows to loop through DataFrame rows
        row = smartsheet.models.Row()
        row.to_bottom = True
        for column, value in item.items():
            if column in column_id_map and pd.notna(value):  # Check for missing values
                # Additional debugging for the problematic column ID
                if column_id_map[column] == 6576620866692996:
                    print(f"  DEBUG - Row {row_idx}: Column '{column}' (ID: 6576620866692996) = '{value}'")
                row.cells.append({'column_id': column_id_map[column], 'value': value})
            elif column in column_id_map:
                row.cells.append({'column_id': column_id_map[column], 'value': ''})  # Use an empty string if NA
        if extra_columns:
            for column, value in extra_columns.items():
                row.cells.append({'column_id': column_id_map[column], 'value': value})
        new_rows.append(row)
    return new_rows


def add_rows_to_smartsheet(client, sheet_id, rows):
    """Function to add rows to Smartsheet"""
    try:
        response = client.Sheets.add_rows(sheet_id, rows)
        print(f"✓ Uploaded {len(rows)} rows successfully!")
        return True
    except smartsheet.exceptions.ApiError as e:
        print(f"✗ Error adding rows to Smartsheet: {e}")
        
        # Enhanced error debugging for picklist issues
        error_str = str(e)
        if "column" in error_str and "PICKLIST" in error_str:
            # Try to extract column ID from error message
            import re
            column_id_match = re.search(r'column (\d+)', error_str)
            if column_id_match:
                error_column_id = int(column_id_match.group(1))
                print(f"  🔍 Picklist error in column ID: {error_column_id}")
                
                # Get sheet to find column name
                try:
                    sheet = client.Sheets.get_sheet(sheet_id)
                    for col in sheet.columns:
                        if col.id == error_column_id:
                            print(f"  📋 Column name: '{col.title}'")
                            print(f"  📝 Column type: {getattr(col, 'type', 'Unknown')}")
                            if hasattr(col, 'options') and col.options:
                                print(f"  ✅ Valid picklist options: {[opt.value for opt in col.options]}")
                            break
                except Exception as sheet_error:
                    print(f"  ⚠ Could not retrieve column details: {sheet_error}")
        
        return False


def process_sheet(client, sheet_info, data):
    """Main function to process each sheet"""
    try:
        # Retrieve the sheet
        sheet = client.Sheets.get_sheet(sheet_info['sheet_id'])
        print(f"  Processing sheet: {sheet_info['sheet_id']}")
        
        # Get the column ID map
        column_id_map = get_column_id_map(sheet)
        print(f"  Found {len(column_id_map)} columns in target sheet")
        
        # Prepare rows for Smartsheet
        rows = prepare_smartsheet_rows(data, column_id_map, sheet_info.get('extra_columns'))
        print(f"  Prepared {len(rows)} rows for upload")
        
        # Add rows to Smartsheet
        success = add_rows_to_smartsheet(client, sheet_info['sheet_id'], rows)
        return success
    except Exception as e:
        print(f"✗ Error processing sheet: {e}")
        return False


if __name__ == "__main__":
    main()