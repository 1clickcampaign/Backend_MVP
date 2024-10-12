import os
from dotenv import load_dotenv

load_dotenv()

# Print the current working directory and .env file path for debugging
#print(f"Current working directory: {os.getcwd()}")
#print(f".env file path: {os.path.join(os.getcwd(), '.env')}")

GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
if not GOOGLE_MAPS_API_KEY:
    raise ValueError("GOOGLE_MAPS_API_KEY is not set in environment variables.")

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials are not set in environment variables.")

BASE_URL = os.getenv('BASE_URL')
if not BASE_URL:
    raise ValueError("BASE_URL is not set in environment variables.")


VALID_BUSINESS_TYPES = [
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

# Update BUSINESS_TYPE_KEYWORDS with more mappings
BUSINESS_TYPE_KEYWORDS = {
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