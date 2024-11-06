"""
Google Maps Service

This module provides functionality to fetch business leads from Google Maps API.
It includes methods for searching areas, making API requests, and handling rate limiting.
"""

import logging
import math
import time
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, wait
import requests
import numpy as np

from app.utils.config import GOOGLE_MAPS_API_KEY
from app.utils.location_utils import get_bounding_box, haversine_distance

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
BASE_URL_NEARBY_SEARCH = "https://places.googleapis.com/v1/places:searchNearby"
BASE_URL_PLACE_DETAILS = "https://places.googleapis.com/v1/places/"  # Place ID will be appended

# Constants for field mapping across all services
FIELD_MAPPINGS = {
    # Basic fields available in both nearby search and place details
    "name": {
        "api": {
            "nearby": "places.displayName",
            "details": "displayName"
        },
        "scraper": "name",
        "response": "name"
    },
    "formatted_address": {
        "api": {
            "nearby": "places.formattedAddress",
            "details": "formattedAddress"
        },
        "scraper": "address",
        "response": "formatted_address"
    },
    "business_status": {
        "api": {
            "nearby": "places.businessStatus",
            "details": "businessStatus"
        },
        "scraper": "business_type",
        "response": "business_status"
    },
    "location": {
        "api": {
            "nearby": "places.location",
            "details": "location"
        },
        "scraper": "location",
        "response": "location"
    },
    "types": {
        "api": {
            "nearby": "places.types",
            "details": "types"
        },
        "scraper": "types",
        "response": "types"
    },

    # Advanced fields
    "formatted_phone_number": {
        "api": {
            "nearby": "places.nationalPhoneNumber",
            "details": "nationalPhoneNumber"
        },
        "scraper": "phone",
        "response": "formatted_phone_number"
    },
    "international_phone_number": {
        "api": {
            "nearby": "places.internationalPhoneNumber",
            "details": "internationalPhoneNumber"
        },
        "scraper": "international_phone",
        "response": "international_phone_number"
    },
    "website": {
        "api": {
            "nearby": "places.websiteUri",
            "details": "websiteUri"
        },
        "scraper": "website",
        "response": "website"
    },
    "rating": {
        "api": {
            "nearby": "places.rating",
            "details": "rating"
        },
        "scraper": "rating",
        "response": "rating"
    },
    "user_ratings_total": {
        "api": {
            "nearby": "places.userRatingCount",
            "details": "userRatingCount"
        },
        "scraper": "num_reviews",
        "response": "user_ratings_total"
    },
    "opening_hours": {
        "api": {
            "nearby": "places.regularOpeningHours",
            "details": "regularOpeningHours"
        },
        "scraper": "hours",
        "response": "opening_hours"
    },

    # Preferred fields
    "dine_in": {
        "api": {
            "nearby": "places.dineIn",
            "details": "dineIn"
        },
        "scraper": "dine_in",
        "response": "dine_in"
    },
    "takeout": {
        "api": {
            "nearby": "places.takeout",
            "details": "takeout"
        },
        "scraper": "takeout",
        "response": "takeout"
    }
}

# At the top with other constants
API_FIELDS = set(FIELD_MAPPINGS.keys())
SCRAPER_ONLY_FIELDS = {
    "images",
    "reviews",
    "similar_businesses",
    "about",
    "additional_properties"
}

# All valid fields combined
VALID_FIELDS = API_FIELDS | SCRAPER_ONLY_FIELDS

# SKU groupings for place details
PLACE_DETAILS_SKUS = {
    "ids_only": {"id", "name", "photos"},
    "location": {
        "addressComponents", "formattedAddress", "location",
        "plusCode", "viewport", "types"
    },
    "basic": {
        "businessStatus", "displayName", "primaryType",
        "primaryTypeDisplayName"
    },
    "advanced": {
        "nationalPhoneNumber", "internationalPhoneNumber",
        "websiteUri", "rating", "userRatingCount",
        "regularOpeningHours", "priceLevel"
    },
    "preferred": {
        "dineIn", "takeout", "delivery", "curbsidePickup",
        "outdoorSeating", "reservable"
    }
}

# Fields that require detailed scraping
DETAILED_SCRAPING_FIELDS = {
    "images", "reviews", "similar_businesses", "about", "additional_properties"
}

# Fields available in the API
API_VALID_FIELDS = {
    field for field, mapping in FIELD_MAPPINGS.items() 
    if "api" in mapping
}

MAX_RESULTS_PER_QUERY = 20
MAX_RADIUS = 50000  # Maximum radius allowed by the API
MIN_RADIUS = 100  # Minimum radius to avoid too many small searches
MAX_REQUESTS_PER_MINUTE = 590  # Setting it slightly below 600 for safety
COST_PER_REQUEST = 0.032  # $0.032 per request as of 2023

# Constants for pricing (prices are in USD)
BASIC_DATA_COST = 0.00
CONTACT_DATA_COST = 0.003
ATMOSPHERE_DATA_COST = 0.005
NEARBY_SEARCH_COST = 0.032
PLACE_DETAILS_COST = 0.017

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

def get_place_details(place_id: str, fields: List[str]) -> Dict[str, Any]:
    """Get detailed information about a place using the Places API v1."""
    try:
        api_fields = []
        for field in fields:
            if field in FIELD_MAPPINGS:
                api_fields.append(FIELD_MAPPINGS[field]["api"]["details"])
        
        if not api_fields:
            logger.warning(f"No valid API fields found for requested fields: {fields}")
            return {}
            
        headers = {
            "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
            "X-Goog-FieldMask": ",".join(api_fields)
        }
        
        url = f"{BASE_URL_PLACE_DETAILS}{place_id}"
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        result = response.json()
        
        # Map the response back to our standard format
        mapped_result = {}
        for field in fields:
            if field in FIELD_MAPPINGS:
                api_field = FIELD_MAPPINGS[field]["api"]["details"]
                value = result.get(api_field)
                if value:
                    if api_field == "displayName":
                        value = value.get("text", "")
                    mapped_result[FIELD_MAPPINGS[field]["response"]] = value
        
        if not mapped_result:
            logger.warning(f"No data mapped for place_id {place_id} with fields {fields}")
            
        return mapped_result
    except Exception as e:
        logger.error(f"Error in get_place_details for {place_id}: {str(e)}")
        return {}
    
def requires_scraper(fields: List[str]) -> bool:
    """Check if any of the requested fields require using the scraper"""
    return bool(set(fields) & SCRAPER_ONLY_FIELDS)

def make_api_request(business_types: List[str], lat: float, lon: float, radius: float, fields: Optional[List[str]] = None) -> Dict[str, Any]:
    """Make a request to the Google Maps API with rate limiting."""
    try:
        data = {
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": lat,
                        "longitude": lon
                    },
                    "radius": float(radius)  # Ensure radius is float
                }
            },
            "includedTypes": business_types,  # Make sure business types are in correct format
            "maxResultCount": MAX_RESULTS_PER_QUERY
        }

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.types,places.businessStatus,places.location"
        }

        response = requests.post(BASE_URL_NEARBY_SEARCH, json=data, headers=headers)
        response.raise_for_status()
        
        if response.status_code != 200:
            logger.error(f"API Error: {response.status_code} - {response.text}")
            return {}
            
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error in make_api_request: {str(e)}\nResponse: {e.response.text if hasattr(e, 'response') else 'No response'}")
        return {}

def search_area(business_types: List[str], lon: float, lat: float, radius: float, 
                all_leads: List[Dict[str, Any]], depth: int = 0, max_depth: int = 3, 
                max_leads: Optional[int] = None, fields: Optional[List[str]] = None) -> bool:
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
        fields (Optional[List[str]]): Fields to include in the detailed search.

    Returns:
        bool: True if all places match the business types, False otherwise.
    """
    if depth > max_depth or (max_leads and len(all_leads) >= max_leads):
        return True

    result = make_api_request(business_types, lat, lon, radius, fields)
    places = result.get("places", [])
    
    fully_matched = True
    for place in places:
        if max_leads and len(all_leads) >= max_leads:
            return fully_matched
            
        # Create lead dictionary matching GoogleMapsLead model
        lead = {
            "id": place.get("id", ""),  # Required by GoogleMapsLead
            "name": place.get("displayName", {}).get("text", ""),
            "business_phone": place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber", ""),
            "formatted_address": place.get("formattedAddress", ""),
            "website": str(place.get("websiteUri", "")) if place.get("websiteUri") else None,
            "rating": float(place.get("rating", 0)) if place.get("rating") else None,
            "user_ratings_total": int(place.get("userRatingCount", 0)) if place.get("userRatingCount") else None,
            "types": place.get("types", []),
            "business_status": place.get("businessStatus", ""),
            "latitude": float(place.get("location", {}).get("latitude", 0)) if place.get("location") else None,
            "longitude": float(place.get("location", {}).get("longitude", 0)) if place.get("location") else None,
            "additional_properties": {},
            "images": None,
            "reviews": None,
            "similar_businesses": None,
            "about": None
        }
        if lead["id"] not in [l["id"] for l in all_leads]:
            all_leads.append(lead)
        
        place_types = set(place.get("types", []))
        if not any(bt.lower() in place_types for bt in business_types):
            fully_matched = False

    if len(places) >= MAX_RESULTS_PER_QUERY and radius > MIN_RADIUS and (not max_leads or len(all_leads) < max_leads):
        subcircles = three_circle_tiling(lon, lat, radius)
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(search_area, business_types, sub_lon, sub_lat, sub_radius, all_leads, depth + 1, max_depth, max_leads, fields) 
                       for sub_lon, sub_lat, sub_radius in subcircles]
            wait(futures)
            fully_matched = all(f.result() for f in futures)
    elif radius > MIN_RADIUS and (not max_leads or len(all_leads) < max_leads):
        new_radius = max(radius / 2, MIN_RADIUS)
        fully_matched = search_area(business_types, lon, lat, new_radius, all_leads, depth + 1, max_depth, max_leads, fields)

    return fully_matched

def fetch_leads_from_google_maps(business_types: List[str], location: str, max_leads: Optional[int] = None,
                               fields: Optional[List[str]] = None) -> Dict[str, Any]:
    """Fetch business leads from Google Maps."""
    logger.info(f"Fetching leads for {business_types} in {location}")
    
    if fields:
        invalid_fields = [field for field in fields if field not in VALID_FIELDS]
        if invalid_fields:
            raise ValueError(f"Invalid fields requested: {', '.join(invalid_fields)}. Valid fields are: {', '.join(VALID_FIELDS)}")
        
        # If any requested field requires scraper, return early
        if requires_scraper(fields):
            logger.info("Requested fields require scraper, skipping API call")
            return {
                "leads": [],
                "incomplete_leads": [],
                "requires_scraper": True
            }

    all_leads = []
    incomplete_leads = []

    bounding_box = get_bounding_box(location)
    if not bounding_box:
        logger.warning(f"Could not find bounding box for location: {location}")
        return []

    sw_lat, sw_lng, ne_lat, ne_lng = bounding_box
    center_lat = (sw_lat + ne_lat) / 2
    center_lng = (sw_lng + ne_lng) / 2
    radius = min(haversine_distance(sw_lat, sw_lng, ne_lat, ne_lng) / 2, MAX_RADIUS)

    # Track API calls during search
    api_calls = {
        'nearby_search': 0,
        'place_details': 0
    }
    
    api_calls['nearby_search'] += 1
    search_area(business_types, center_lng, center_lat, radius, all_leads, max_leads=max_leads, fields=fields)

    if fields:
        api_calls['place_details'] += len(all_leads)
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_place_details, lead['id'], fields) for lead in all_leads]
            wait(futures)
            for i, future in enumerate(futures):
                details = future.result()
                if isinstance(details, dict):  # Ensure details is a dictionary
                    all_leads[i].update(details)

    if max_leads:
        all_leads = all_leads[:max_leads]

    # Filter out any non-dictionary entries
    all_leads = [lead for lead in all_leads if isinstance(lead, dict)]
    
    logger.info(f"Total unique places found: {len(all_leads)}")
    calculate_cost(api_calls, fields or [])
    
    return {
        "leads": all_leads,
        "incomplete_leads": incomplete_leads
    }

def calculate_cost(api_calls: Dict[str, int], fields: List[str]) -> None:
    """
    Calculate and print the estimated cost of API requests based on the SKUs used.

    Args:
        api_calls (Dict[str, int]): Dictionary containing the count of each type of API call.
        fields (List[str]): List of fields requested in Place Details calls.
    """
    total_cost = 0.0
    
    # Calculate cost for Nearby Search calls
    nearby_search_count = api_calls.get('nearby_search', 0)
    nearby_search_cost = nearby_search_count * NEARBY_SEARCH_COST
    total_cost += nearby_search_cost
    
    # Calculate cost for Place Details calls
    place_details_count = api_calls.get('place_details', 0)
    place_details_cost = place_details_count * PLACE_DETAILS_COST
    total_cost += place_details_cost
    
    # Calculate additional costs based on fields requested
    if fields:
        basic_fields = {'name', 'formatted_address', 'business_status', 'geometry', 'icon', 'types', 'vicinity'}
        contact_fields = {'formatted_phone_number', 'international_phone_number', 'opening_hours', 'website'}
        atmosphere_fields = {'price_level', 'rating', 'user_ratings_total', 'reviews'}
        
        if any(field in contact_fields for field in fields):
            total_cost += place_details_count * CONTACT_DATA_COST
        
        if any(field in atmosphere_fields for field in fields):
            total_cost += place_details_count * ATMOSPHERE_DATA_COST
    
    # Print the cost breakdown
    print(f"Cost breakdown:")
    print(f"  Nearby Search: {nearby_search_count} calls, ${nearby_search_cost:.2f}")
    print(f"  Place Details: {place_details_count} calls, ${place_details_cost:.2f}")
    if fields:
        print(f"  Additional data costs: ${total_cost - nearby_search_cost - place_details_cost:.2f}")
    print(f"Total estimated cost: ${total_cost:.2f}")


# Usage example:
# api_calls = {'nearby_search': 100, 'place_details': 500}
# fields = ['name', 'formatted_address', 'formatted_phone_number', 'rating']
# calculate_cost(api_calls, fields)
