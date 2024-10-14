"""
Configuration Module

This module loads and manages configuration settings for the application,
including API keys, database credentials, and business type mappings.
"""

import os
from typing import Dict, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Helper function to get required environment variables
def get_env_var(var_name: str) -> str:
    """
    Get a required environment variable or raise an error if it's not set.

    Args:
        var_name (str): Name of the environment variable.

    Returns:
        str: Value of the environment variable.

    Raises:
        ValueError: If the environment variable is not set.
    """
    value = os.getenv(var_name)
    if not value:
        raise ValueError(f"{var_name} is not set in environment variables.")
    return value

# Application settings
API_KEY = get_env_var('API_KEY')
GOOGLE_MAPS_API_KEY = get_env_var('GOOGLE_MAPS_API_KEY')
BASE_URL = get_env_var('BASE_URL')

# Database settings
SUPABASE_URL = get_env_var('SUPABASE_URL')
SUPABASE_KEY = get_env_var('SUPABASE_KEY')

# Business types and keywords
VALID_BUSINESS_TYPES: List[str] = [
    "accounting", "airport", "amusement_park", "aquarium", "art_gallery", "atm", "bakery",
    "bank", "bar", "beauty_salon", "bicycle_store", "book_store", "bowling_alley",
    "bus_station", "cafe", "campground", "car_dealer", "car_rental", "car_repair",
    "car_wash", "casino", "cemetery", "church", "city_hall", "clothing_store",
    "convenience_store", "courthouse", "dentist", "department_store", "doctor",
    "drugstore", "electrician", "electronics_store", "embassy", "fire_station",
    "florist", "funeral_home", "furniture_store", "gas_station", "gym", "hair_care",
    "hardware_store", "hindu_temple", "home_goods_store", "hospital", "insurance_agency",
    "jewelry_store", "laundry", "lawyer", "library", "light_rail_station", "liquor_store",
    "local_government_office", "locksmith", "lodging", "meal_delivery", "meal_takeaway",
    "mosque", "movie_rental", "movie_theater", "moving_company", "museum", "night_club",
    "painter", "park", "parking", "pet_store", "pharmacy", "physiotherapist", "plumber",
    "police", "post_office", "primary_school", "real_estate_agency", "restaurant",
    "roofing_contractor", "rv_park", "school", "secondary_school", "shoe_store",
    "shopping_mall", "spa", "stadium", "storage", "store", "subway_station", "supermarket",
    "synagogue", "taxi_stand", "tourist_attraction", "train_station", "transit_station",
    "travel_agency", "university", "veterinary_care", "zoo"
]

BUSINESS_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "restaurant": ["restaurant", "cafe", "bar", "meal_takeaway"],
    "cafe": ["cafe", "restaurant", "bakery"],
    "bar": ["bar", "night_club"],
    "shop": ["store", "shopping_mall", "supermarket", "clothing_store", "electronics_store"],
    "store": ["store", "supermarket", "convenience_store"],
    "supermarket": ["supermarket", "grocery_or_supermarket", "store"],
    "hotel": ["lodging"],
    "school": ["school", "primary_school", "secondary_school", "university"],
    "hospital": ["hospital", "doctor"],
    "park": ["park", "amusement_park"],
    "gym": ["gym"],
    "bank": ["bank", "atm"],
    "gas": ["gas_station"],
    "parking": ["parking"],
    "pharmacy": ["pharmacy", "drugstore"],
    "police": ["police"],
    "post": ["post_office"],
    "library": ["library"],
    "museum": ["museum"],
    "airport": ["airport"],
    "train": ["train_station", "transit_station"],
    "bus": ["bus_station", "transit_station"],
    "movie": ["movie_theater"],
    "hair": ["hair_care", "beauty_salon"],
    "dentist": ["dentist"],
    "doctor": ["doctor", "hospital"],
    "lawyer": ["lawyer"],
    "real estate": ["real_estate_agency"],
    "insurance": ["insurance_agency"],
    "car": ["car_repair", "car_wash", "car_dealer"],
    "factory": ["storage", "store"],
    "industry": ["storage", "store"],
    "manufacturing": ["storage", "store"],
    "industrial": ["storage", "store"],
    "warehouse": ["storage", "store"],
}
