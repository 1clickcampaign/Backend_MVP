from difflib import SequenceMatcher
import re
from app.utils.config import VALID_BUSINESS_TYPES

def stem_word(word):
    word = word.lower()
    word = re.sub(r'(es|s)$', '', word)
    word = re.sub(r'ing$', '', word)
    return word

# Expanded keyword mapping
KEYWORD_TO_TYPES = {
    "restaurant": ["restaurant", "cafe", "bar", "meal_takeaway"],
    "cafe": ["cafe", "restaurant", "bakery"],
    "bar": ["bar", "night_club"],
    "shop": ["store", "shopping_mall", "supermarket", "clothing_store", "electronics_store"],
    "store": ["store", "supermarket", "convenience_store"],
    "supermarket": ["supermarket", "grocery_or_supermarket", "store"],
    "hotel": ["lodging", "hotel"],
    "school": ["school", "primary_school", "secondary_school", "university"],
    "hospital": ["hospital", "doctor", "health"],
    "park": ["park", "amusement_park"],
    "gym": ["gym", "health"],
    "bank": ["bank", "atm", "finance"],
    "gas": ["gas_station"],
    "parking": ["parking"],
    "pharmacy": ["pharmacy", "drugstore"],
    "police": ["police"],
    "post_office": ["post_office"],
    "library": ["library"],
    "museum": ["museum"],
    "airport": ["airport"],
    "train_station": ["train_station", "transit_station"],
    "bus_station": ["bus_station", "transit_station"],
    "movie_theater": ["movie_theater"],
    "hair_salon": ["hair_care", "beauty_salon"],
    "dentist": ["dentist"],
    "doctor": ["doctor", "hospital"],
    "lawyer": ["lawyer"],
    "real_estate": ["real_estate_agency"],
    "insurance": ["insurance_agency"],
    "car_repair": ["car_repair"],
    "car_wash": ["car_wash"],
    "car_dealer": ["car_dealer"],
    "factory": ["industrial_park", "storage", "warehouse"],
}

def find_best_matches(input_type: str, threshold: float = 0.6, max_matches: int = 3):
    input_words = input_type.lower().split()
    matches = []

    # First, check for direct matches in KEYWORD_TO_TYPES
    for key, types in KEYWORD_TO_TYPES.items():
        if all(word in key.lower().split() for word in input_words):
            matches.extend(types)

    # If we don't have enough matches, use sequence matcher
    if len(matches) < max_matches:
        for valid_type in VALID_BUSINESS_TYPES:
            valid_stem = stem_word(valid_type)
            score = max(SequenceMatcher(None, word, valid_stem).ratio() for word in input_words)
            
            if score >= threshold:
                matches.append(valid_type)

    # Remove duplicates and limit to max_matches
    matches = list(dict.fromkeys(matches))[:max_matches]

    if not matches:
        # If no matches found, return the closest match from VALID_BUSINESS_TYPES
        closest_match = max(VALID_BUSINESS_TYPES, key=lambda x: max(SequenceMatcher(None, word, stem_word(x)).ratio() for word in input_words))
        matches = [closest_match]

    return matches