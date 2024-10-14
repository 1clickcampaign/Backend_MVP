"""
Google Maps Service

This module provides functionality to fetch business leads from Google Maps API.
It includes methods for searching areas, making API requests, and handling rate limiting.
"""

import math
import time
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, wait
import requests
import numpy as np

from app.utils.config import GOOGLE_MAPS_API_KEY
from app.utils.location_utils import get_bounding_box, haversine_distance

# Constants
BASE_URL = "https://places.googleapis.com/v1/places:searchNearby"
MAX_RESULTS_PER_QUERY = 20
MAX_RADIUS = 50000  # Maximum radius allowed by the API
MIN_RADIUS = 100  # Minimum radius to avoid too many small searches
MAX_REQUESTS_PER_MINUTE = 590  # Setting it slightly below 600 for safety
COST_PER_REQUEST = 0.032  # $0.032 per request as of 2023

# Global variables
API_REQUEST_COUNT = 0
request_timestamps = []

def three_circle_tiling(lon: float, lat: float, radius: float) -> List[tuple]:
    """
    Generate three subcircles that cover the area of a larger circle.

    Args:
        lon (float): Longitude of the center of the main circle.
        lat (float): Latitude of the center of the main circle.
        radius (float): Radius of the main circle in meters.

    Returns:
        List[tuple]: List of tuples containing (longitude, latitude, radius) for each subcircle.
    """
    subcircles = []
    for rad in np.linspace(0, 2 * np.pi, 3, endpoint=False):
        km_per_lon = 6374. * 1000 * (2*np.pi/360) * np.cos(np.radians(lat))
        km_per_lat = 6374. * 1000 * (2*np.pi/360)
        radius_subcircle = radius * 0.72791
        lon_subcircle = lon + (radius*0.72791) * np.cos(rad) / km_per_lon
        lat_subcircle = lat + (radius*0.72791) * np.sin(rad) / km_per_lat
        subcircles.append((lon_subcircle, lat_subcircle, radius_subcircle))
    return subcircles

def make_api_request(business_types: List[str], lat: float, lon: float, radius: float) -> Dict[str, Any]:
    """
    Make a request to the Google Maps API with rate limiting.

    Args:
        business_types (List[str]): Types of businesses to search for.
        lat (float): Latitude of the search center.
        lon (float): Longitude of the search center.
        radius (float): Search radius in meters.

    Returns:
        Dict[str, Any]: JSON response from the API or an empty dict if there's an error.
    """
    global API_REQUEST_COUNT, request_timestamps
    
    current_time = time.time()
    request_timestamps = [ts for ts in request_timestamps if current_time - ts < 60]
    
    if len(request_timestamps) >= MAX_REQUESTS_PER_MINUTE:
        sleep_time = 60 - (current_time - request_timestamps[0])
        print(f"Rate limit approaching. Sleeping for {sleep_time:.2f} seconds...")
        time.sleep(sleep_time)
        current_time = time.time()
    
    request_timestamps.append(current_time)
    API_REQUEST_COUNT += 1

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.internationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,places.types,places.businessStatus,places.location"
    }

    data = {
        "includedTypes": business_types,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": radius
            }
        },
        "rankPreference": "DISTANCE",
        "maxResultCount": MAX_RESULTS_PER_QUERY
    }

    response = requests.post(BASE_URL, json=data, headers=headers)
    
    if response.status_code != 200:
        print(f"Error response from Google Maps API: {response.text}")
        return {}

    return response.json()

def search_area(business_types: List[str], lon: float, lat: float, radius: float, 
                all_leads: List[Dict[str, Any]], depth: int = 0, max_depth: int = 3, 
                max_leads: Optional[int] = None) -> bool:
    """
    Recursively search an area for businesses using the Google Maps API.

    Args:
        business_types (List[str]): Types of businesses to search for.
        lon (float): Longitude of the search center.
        lat (float): Latitude of the search center.
        radius (float): Search radius in meters.
        all_leads (List[Dict[str, Any]]): List to store all found leads.
        depth (int): Current depth of recursion.
        max_depth (int): Maximum depth of recursion.
        max_leads (Optional[int]): Maximum number of leads to collect.

    Returns:
        bool: True if all places match the business types, False otherwise.
    """
    if depth > max_depth or (max_leads and len(all_leads) >= max_leads):
        return True

    result = make_api_request(business_types, lat, lon, radius)
    places = result.get("places", [])
    
    fully_matched = True
    for place in places:
        if max_leads and len(all_leads) >= max_leads:
            return fully_matched
        lead = {
            "name": place.get("displayName", {}).get("text", ""),
            "source": "Google Maps",
            "external_id": place.get("id", ""),
            "business_phone": place.get("internationalPhoneNumber", ""),
            "formatted_address": place.get("formattedAddress", ""),
            "website": place.get("websiteUri", ""),
            "rating": place.get("rating", 0),
            "user_ratings_total": place.get("userRatingCount", 0),
            "types": place.get("types", []),
            "business_status": place.get("businessStatus", ""),
            "latitude": place.get("location", {}).get("latitude", 0),
            "longitude": place.get("location", {}).get("longitude", 0),
        }
        if lead["external_id"] not in [l["external_id"] for l in all_leads]:
            all_leads.append(lead)
        
        place_types = set(place.get("types", []))
        if not any(bt.lower() in place_types for bt in business_types):
            fully_matched = False

    if len(places) >= MAX_RESULTS_PER_QUERY and radius > MIN_RADIUS and (not max_leads or len(all_leads) < max_leads):
        subcircles = three_circle_tiling(lon, lat, radius)
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(search_area, business_types, sub_lon, sub_lat, sub_radius, all_leads, depth + 1, max_depth, max_leads) 
                       for sub_lon, sub_lat, sub_radius in subcircles]
            wait(futures)
            fully_matched = all(f.result() for f in futures)
    elif radius > MIN_RADIUS and (not max_leads or len(all_leads) < max_leads):
        new_radius = max(radius / 2, MIN_RADIUS)
        fully_matched = search_area(business_types, lon, lat, new_radius, all_leads, depth + 1, max_depth, max_leads)

    return fully_matched

def fetch_leads_from_google_maps(business_types: List[str], location: str, max_leads: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Fetch business leads from Google Maps for given business types and location.

    Args:
        business_types (List[str]): Types of businesses to search for.
        location (str): Location to search in.
        max_leads (Optional[int]): Maximum number of leads to collect.

    Returns:
        List[Dict[str, Any]]: List of business leads found.
    """
    print(f"Fetching leads for {business_types} in {location}")
    
    all_leads = []

    bounding_box = get_bounding_box(location)
    if not bounding_box:
        print(f"Could not find bounding box for location: {location}")
        return []

    sw_lat, sw_lng, ne_lat, ne_lng = bounding_box
    center_lat = (sw_lat + ne_lat) / 2
    center_lng = (sw_lng + ne_lng) / 2
    radius = min(haversine_distance(sw_lat, sw_lng, ne_lat, ne_lng) / 2, MAX_RADIUS)

    search_area(business_types, center_lng, center_lat, radius, all_leads, max_leads=max_leads)

    if max_leads:
        all_leads = all_leads[:max_leads]

    print(f"Total unique places found: {len(all_leads)}")
    
    calculate_cost(API_REQUEST_COUNT)
    return all_leads

def calculate_cost(num_requests: int) -> None:
    """
    Calculate and print the estimated cost of API requests.

    Args:
        num_requests (int): Number of API requests made.
    """
    total_cost = num_requests * COST_PER_REQUEST 
    print(f"Total API requests made: {num_requests}")
    print(f"Estimated cost: ${total_cost:.2f}")