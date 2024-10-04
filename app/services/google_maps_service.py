import math
import numpy as np
import concurrent.futures
from typing import List, Dict, Any, Set, Optional
import requests
import json
import time
from app.utils.config import GOOGLE_MAPS_API_KEY
from app.utils.location_utils import (
    get_bounding_box,
    haversine_distance,
)
from app.utils.string_matching import find_best_matches
from app.services.google_maps_service import search_area, make_api_request
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

BASE_URL = "https://places.googleapis.com/v1/places:searchNearby"
MAX_RESULTS_PER_QUERY = 20
MAX_RADIUS = 50000  # Maximum radius allowed by the API
MIN_RADIUS = 100  # Minimum radius to avoid too many small searches

API_REQUEST_COUNT = 0
request_timestamps = []

MAX_REQUESTS_PER_MINUTE = 590  # Setting it slightly below 600 for safety

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
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.internationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,places.types,places.businessStatus"
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

def search_area(business_types: List[str], lon: float, lat: float, radius: float, all_leads: List[Dict[str, Any]], depth: int = 0, max_depth: int = 3, max_leads: Optional[int] = None):
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
            "source_attributes": {
                "formatted_address": place.get("formattedAddress", ""),
                "website": place.get("websiteUri", ""),
                "rating": place.get("rating", 0),
                "user_ratings_total": place.get("userRatingCount", 0),
                "types": place.get("types", []),
                "business_status": place.get("businessStatus", "")
            }
        }
        if lead["external_id"] not in [l["external_id"] for l in all_leads]:
            all_leads.append(lead)
        
        # Check if the place types match the business types
        place_types = set(place.get("types", []))
        if not any(bt.lower() in place_types for bt in business_types):
            fully_matched = False

    if len(places) >= MAX_RESULTS_PER_QUERY and radius > MIN_RADIUS and (not max_leads or len(all_leads) < max_leads):
        subcircles = three_circle_tiling(lon, lat, radius)
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(search_area, business_types, sub_lon, sub_lat, sub_radius, all_leads, depth + 1, max_depth, max_leads) 
                       for sub_lon, sub_lat, sub_radius in subcircles]
            results = concurrent.futures.wait(futures)
            fully_matched = all(f.result() for f in futures)
    elif radius > MIN_RADIUS and (not max_leads or len(all_leads) < max_leads):
        new_radius = max(radius / 2, MIN_RADIUS)
        fully_matched = search_area(business_types, lon, lat, new_radius, all_leads, depth + 1, max_depth, max_leads)

    return fully_matched

def fetch_leads_from_google_maps(business_types: List[str], location: str, max_leads: Optional[int] = None) -> List[Dict[str, Any]]:
    print(f"Fetching leads for {business_types} in {location}")
    
    matched_types = find_best_matches(" ".join(business_types))
    all_leads = []

    if matched_types:
        bounding_box = get_bounding_box(location)
        if not bounding_box:
            print(f"Could not find bounding box for location: {location}")
            return []

        sw_lat, sw_lng, ne_lat, ne_lng = bounding_box
        center_lat = (sw_lat + ne_lat) / 2
        center_lng = (sw_lng + ne_lng) / 2
        radius = min(haversine_distance(sw_lat, sw_lng, ne_lat, ne_lng) / 2, MAX_RADIUS)

        search_area(matched_types, center_lng, center_lat, radius, all_leads, max_leads=max_leads)
    else:
        print(f"No matched business types found. Performing text search.")
        all_leads = text_search(business_types, location, max_leads)

    if max_leads:
        all_leads = all_leads[:max_leads]

    print(f"Total unique places found: {len(all_leads)}")
    
    calculate_cost(API_REQUEST_COUNT)
    return all_leads

COST_PER_REQUEST = 0.032  # $0.032 per request as of 2023

def calculate_cost(num_requests):
    total_cost = num_requests * COST_PER_REQUEST
    print(f"Total API requests made: {num_requests}")
    print(f"Estimated cost: ${total_cost:.2f}")

def text_search(business_types: List[str], location: str, max_leads: Optional[int] = None) -> List[Dict[str, Any]]:
    global API_REQUEST_COUNT
    all_leads = []
    query = f"{' '.join(business_types)} in {location}"
    
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": query,
        "key": GOOGLE_MAPS_API_KEY
    }
    
    while True:
        API_REQUEST_COUNT += 1
        response = requests.get(url, params=params)
        data = response.json()
        
        if data["status"] != "OK":
            print(f"Error in text search: {data['status']}")
            break
        
        for place in data["results"]:
            lead = {
                "name": place.get("name", ""),
                "source": "Google Maps",
                "external_id": place.get("place_id", ""),
                "business_phone": "",  # We need to make an additional request to get this
                "source_attributes": {
                    "formatted_address": place.get("formatted_address", ""),
                    "website": "",  # We need to make an additional request to get this
                    "rating": place.get("rating", 0),
                    "user_ratings_total": place.get("user_ratings_total", 0),
                    "types": place.get("types", []),
                    "business_status": place.get("business_status", "")
                }
            }
            all_leads.append(lead)
            
            if max_leads and len(all_leads) >= max_leads:
                return all_leads
        
        if "next_page_token" in data:
            params["pagetoken"] = data["next_page_token"]
            time.sleep(2)  # Wait for the next page token to become valid
        else:
            break
    
    return all_leads