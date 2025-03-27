# FILE: /USBL_Nav_Smoother/src/utils/geo_utils.py
# This file provides geographic utility functions, such as converting between coordinate systems or calculating distances.

import numpy as np
from geopy.distance import geodesic
import utm

def calculate_distance(point1, point2):
    """
    Calculate the distance between two geographic points.

    Args:
        point1: A tuple containing (latitude, longitude) for the first point.
        point2: A tuple containing (latitude, longitude) for the second point.

    Returns:
        Distance in kilometers between the two points.
    """
    return geodesic(point1, point2).kilometers

def lat_lon_to_utm(latitude, longitude):
    """
    Convert latitude and longitude to UTM coordinates.

    Args:
        latitude: Latitude of the point.
        longitude: Longitude of the point.

    Returns:
        A tuple containing (easting, northing, zone_number, zone_letter).
    """
    return utm.from_latlon(latitude, longitude)

def utm_to_lat_lon(easting, northing, zone_number, zone_letter):
    """
    Convert UTM coordinates back to latitude and longitude.

    Args:
        easting: Easting coordinate.
        northing: Northing coordinate.
        zone_number: UTM zone number.
        zone_letter: UTM zone letter.

    Returns:
        A tuple containing (latitude, longitude).
    """
    return utm.to_latlon(easting, northing, zone_number, zone_letter)

def calculate_bearing(point1, point2):
    """
    Calculate the bearing between two geographic points.

    Args:
        point1: A tuple containing (latitude, longitude) for the first point.
        point2: A tuple containing (latitude, longitude) for the second point.

    Returns:
        Bearing in degrees from the first point to the second point.
    """
    from math import atan2, degrees, radians, sin, cos
    lat1, lon1 = radians(point1[0]), radians(point1[1])
    lat2, lon2 = radians(point2[0]), radians(point2[1])
    
    d_lon = lon2 - lon1
    x = sin(d_lon) * cos(lat2)
    y = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(d_lon)
    
    initial_bearing = atan2(x, y)
    # Convert from radians to degrees and normalize to 0-360
    return (degrees(initial_bearing) + 360) % 360

def midpoint(point1, point2):
    """
    Calculate the midpoint between two geographic points.

    Args:
        point1: A tuple containing (latitude, longitude) for the first point.
        point2: A tuple containing (latitude, longitude) for the second point.

    Returns:
        A tuple containing (latitude, longitude) of the midpoint.
    """
    lat1, lon1 = point1
    lat2, lon2 = point2
    mid_lat = (lat1 + lat2) / 2
    mid_lon = (lon1 + lon2) / 2
    return (mid_lat, mid_lon)

def calculate_track_distance(df):
    """
    Calculate the total distance traveled in a track using latitude/longitude points
    
    Args:
        df (pd.DataFrame): DataFrame containing navigation data with Latitude and Longitude columns
        
    Returns:
        float: Total distance in kilometers
    """
    total_distance = 0
    for i in range(1, len(df)):
        point1 = (df.iloc[i-1]['Latitude'], df.iloc[i-1]['Longitude'])
        point2 = (df.iloc[i]['Latitude'], df.iloc[i]['Longitude'])
        distance = geodesic(point1, point2).kilometers
        total_distance += distance
    return total_distance

def convert_to_utm(lat, lon):
    """
    Convert latitude/longitude to UTM coordinates
    
    Args:
        lat (float): Latitude in decimal degrees
        lon (float): Longitude in decimal degrees
        
    Returns:
        tuple: (easting, northing, zone_number, zone_letter)
    """
    return utm.from_latlon(lat, lon)

def convert_from_utm(easting, northing, zone_number, zone_letter):
    """
    Convert UTM coordinates to latitude/longitude
    
    Args:
        easting (float): UTM easting coordinate
        northing (float): UTM northing coordinate
        zone_number (int): UTM zone number
        zone_letter (str): UTM zone letter
        
    Returns:
        tuple: (latitude, longitude) in decimal degrees
    """
    return utm.to_latlon(easting, northing, zone_number, zone_letter)