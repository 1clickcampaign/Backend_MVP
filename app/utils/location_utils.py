import requests
from typing import Tuple, Optional, List
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from math import radians, sin, cos, sqrt, atan2

def get_lat_lng_from_address(address: str) -> Tuple[Optional[float], Optional[float]]:
    geolocator = Nominatim(user_agent="your_app_name")
    try:
        location = geolocator.geocode(address)
        if location:
            return location.latitude, location.longitude
        else:
            print(f"Could not find coordinates for address: {address}")
            return None, None
    except (GeocoderTimedOut, GeocoderUnavailable) as e:
        print(f"Geocoding error: {e}")
        return None, None

def get_bounding_box(location: str) -> Optional[Tuple[float, float, float, float]]:
    lat, lng = get_lat_lng_from_address(location)
    if lat is None or lng is None:
        return None

    # Define a default radius (in kilometers) for the bounding box
    radius_km = 50

    # Calculate the bounding box
    lat_change = radius_km / 111.32
    lon_change = abs(radius_km / (111.32 * cos(radians(lat))))

    min_lat = lat - lat_change
    max_lat = lat + lat_change
    min_lon = lng - lon_change
    max_lon = lng + lon_change

    return (min_lat, min_lon, max_lat, max_lon)

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000  # Earth radius in meters

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def get_circle_centers(sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float, radius: float) -> List[Tuple[float, float]]:
    centers = []
    lat = sw_lat
    while lat <= ne_lat:
        lng = sw_lng
        while lng <= ne_lng:
            centers.append((lat, lng))
            lng += (radius * 2) / (111320 * cos(radians(lat)))
        lat += (radius * 2) / 111320
    return centers

def is_point_in_rectangle(lat: float, lng: float, sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float) -> bool:
    return sw_lat <= lat <= ne_lat and sw_lng <= lng <= ne_lng
