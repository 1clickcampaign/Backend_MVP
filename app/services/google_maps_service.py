import math
import numpy as np
import concurrent.futures
from typing import List, Dict, Any, Set
import requests
import json
from app.utils.config import GOOGLE_MAPS_API_KEY
from app.utils.location_utils import (
    get_bounding_box,
    haversine_distance,
    get_circle_centers,
    is_point_in_rectangle
)

BASE_URL = "https://places.googleapis.com/v1/places:searchNearby"
MAX_RESULTS_PER_QUERY = 20
MAX_RADIUS = 50000  # Maximum radius allowed by the API
MIN_RADIUS = 100  # Minimum radius to avoid too many small searches

def three_circle_tiling(lon: float, lat: float, radius: float) -> list:
    subcircles = []
    for rad in np.linspace(0, 2 * np.pi, 3, endpoint=False):
        km_per_lon = 6374. * 1000 * (2*np.pi/360) * np.cos(lat)
        km_per_lat = 6374. * 1000 * (2*np.pi/360)
        radius_subcircle = radius * 0.72791
        lon_subcircle = lon + (radius*0.72791) * np.cos(rad) / km_per_lon
        lat_subcircle = lat + (radius*0.72791) * np.sin(rad) / km_per_lat
        subcircles.append((lon_subcircle, lat_subcircle, radius_subcircle))
    return subcircles

def make_api_request(business_types: List[str], lat: float, lon: float, radius: float) -> Dict[str, Any]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.id,places.internationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,places.types"
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

    print(f"API Request Data: {json.dumps(data, indent=2)}")

    response = requests.post(BASE_URL, json=data, headers=headers)
    
    if response.status_code != 200:
        print(f"Error response from Google Maps API: {response.text}")
        return {}

    return response.json()

def search_area(business_types: List[str], lon: float, lat: float, radius: float, all_leads: Set[str], depth: int = 0, max_depth: int = 3):
    if depth > max_depth or len(all_leads) >= MAX_RESULTS_PER_QUERY * len(business_types):
        return

    result = make_api_request(business_types, lat, lon, radius)
    places = result.get("places", [])
    
    for place in places:
        all_leads.add(place['id'])

    if len(places) >= MAX_RESULTS_PER_QUERY and radius > MIN_RADIUS:
        subcircles = three_circle_tiling(lon, lat, radius)
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(search_area, business_types, sub_lon, sub_lat, sub_radius, all_leads, depth + 1, max_depth) 
                       for sub_lon, sub_lat, sub_radius in subcircles]
            concurrent.futures.wait(futures)
    elif len(places) >= MAX_RESULTS_PER_QUERY:
        new_radius = max(radius / 2, MIN_RADIUS)
        search_area(business_types, lon, lat, new_radius, all_leads, depth + 1, max_depth)

def fetch_leads_from_google_maps(business_types: List[str], location: str) -> List[Dict[str, Any]]:
    print(f"Fetching leads for {business_types} in {location}")
    
    bounding_box = get_bounding_box(location)
    if not bounding_box:
        print(f"Could not find bounding box for location: {location}")
        return []

    all_leads = set()
    sw_lat, sw_lng, ne_lat, ne_lng = bounding_box
    
    center_lat = (sw_lat + ne_lat) / 2
    center_lng = (sw_lng + ne_lng) / 2
    radius = min(haversine_distance(sw_lat, sw_lng, ne_lat, ne_lng) / 2, MAX_RADIUS)

    search_area(business_types, center_lng, center_lat, radius, all_leads)

    print(f"Total unique places found: {len(all_leads)}")
    
    detailed_leads = []
    for place_id in all_leads:
        place_details = fetch_place_details(place_id)
        if place_details:
            detailed_leads.append(place_details)

    return detailed_leads

def fetch_place_details(place_id: str) -> Dict[str, Any]:
    url = f"https://places.googleapis.com/v1/places/{place_id}"
    
    headers = {
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": "id,displayName,formattedAddress,internationalPhoneNumber,websiteUri,rating,userRatingCount"
    }

    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error fetching place details for ID {place_id}: {response.text}")
        return {}

    place_data = response.json()
    
    return {
        "name": place_data.get("displayName", {}).get("text", ""),
        "source": "Google Maps",
        "external_id": place_data.get("id", ""),
        "business_phone": place_data.get("internationalPhoneNumber", ""),
        "source_attributes": {
            "formatted_address": place_data.get("formattedAddress", ""),
            "website": place_data.get("websiteUri", ""),
            "rating": place_data.get("rating", 0),
            "user_ratings_total": place_data.get("userRatingCount", 0)
        }
    }