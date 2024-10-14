"""
Location Utilities

This module provides utility functions for geocoding, calculating distances,
and working with geographical coordinates.
"""

import logging
from typing import Tuple, Optional, List
from math import radians, sin, cos, sqrt, atan2
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

# Configure logging
logger = logging.getLogger(__name__)

# Constants
EARTH_RADIUS_METERS = 6371000
DEFAULT_BOUNDING_BOX_RADIUS_KM = 50
DEGREES_TO_RADIANS = 3.141592653589793 / 180

def get_lat_lng_from_address(address: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Get latitude and longitude coordinates for a given address.

    Args:
        address (str): The address to geocode.

    Returns:
        Tuple[Optional[float], Optional[float]]: Latitude and longitude, or (None, None) if geocoding fails.
    """
    geolocator = Nominatim(user_agent="your_app_name")
    try:
        location = geolocator.geocode(address)
        if location:
            return location.latitude, location.longitude
        logger.warning(f"Could not find coordinates for address: {address}")
        return None, None
    except (GeocoderTimedOut, GeocoderUnavailable) as e:
        logger.error(f"Geocoding error: {e}")
        return None, None

def get_bounding_box(location: str) -> Optional[Tuple[float, float, float, float]]:
    """
    Calculate a bounding box around a given location.

    Args:
        location (str): The location to create a bounding box for.

    Returns:
        Optional[Tuple[float, float, float, float]]: Bounding box coordinates (min_lat, min_lon, max_lat, max_lon),
                                                     or None if geocoding fails.
    """
    lat, lng = get_lat_lng_from_address(location)
    if lat is None or lng is None:
        return None

    lat_change = DEFAULT_BOUNDING_BOX_RADIUS_KM / 111.32
    lon_change = abs(DEFAULT_BOUNDING_BOX_RADIUS_KM / (111.32 * cos(radians(lat))))

    return (lat - lat_change, lng - lon_change, lat + lat_change, lng + lon_change)

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth.

    Args:
        lat1, lon1 (float): Coordinates of the first point.
        lat2, lon2 (float): Coordinates of the second point.

    Returns:
        float: Distance between the points in meters.
    """
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return EARTH_RADIUS_METERS * c

def get_circle_centers(sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float, radius: float) -> List[Tuple[float, float]]:
    """
    Generate a grid of circle centers within a bounding box.

    Args:
        sw_lat, sw_lng (float): Coordinates of the southwest corner.
        ne_lat, ne_lng (float): Coordinates of the northeast corner.
        radius (float): Radius of each circle in meters.

    Returns:
        List[Tuple[float, float]]: List of (latitude, longitude) pairs for circle centers.
    """
    centers = []
    lat_step = (radius * 2) / 111320
    lat = sw_lat
    while lat <= ne_lat:
        lng = sw_lng
        lng_step = (radius * 2) / (111320 * cos(radians(lat)))
        while lng <= ne_lng:
            centers.append((lat, lng))
            lng += lng_step
        lat += lat_step
    return centers

def is_point_in_rectangle(lat: float, lng: float, sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float) -> bool:
    """
    Check if a point is within a rectangular area.

    Args:
        lat, lng (float): Coordinates of the point to check.
        sw_lat, sw_lng (float): Coordinates of the southwest corner of the rectangle.
        ne_lat, ne_lng (float): Coordinates of the northeast corner of the rectangle.

    Returns:
        bool: True if the point is within the rectangle, False otherwise.
    """
    return sw_lat <= lat <= ne_lat and sw_lng <= lng <= ne_lng
