from difflib import SequenceMatcher
import re
from typing import List
from app.utils.config import VALID_BUSINESS_TYPES

def stem_word(word: str) -> str:
    word = word.lower()
    word = re.sub(r'(es|s)$', '', word)
    word = re.sub(r'ing$', '', word)
    return word

def calculate_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def find_best_matches(input_type: str, threshold: float = 0.6, max_matches: int = 3) -> List[str]:
    input_words = re.findall(r'\w+', input_type.lower())
    matches = set()

    for word in input_words:
        stemmed_word = stem_word(word)
        
        # Direct match in KEYWORD_TO_TYPES
        if stemmed_word in KEYWORD_TO_TYPES:
            matches.update(KEYWORD_TO_TYPES[stemmed_word])
            continue

        # Partial match in KEYWORD_TO_TYPES
        for key, types in KEYWORD_TO_TYPES.items():
            if stemmed_word in key:
                matches.update(types)

        # Similarity match with VALID_BUSINESS_TYPES
        for valid_type in VALID_BUSINESS_TYPES:
            similarity = calculate_similarity(stemmed_word, valid_type)
            if similarity >= threshold:
                matches.add(valid_type)

    # If no matches found, use the closest match from VALID_BUSINESS_TYPES
    if not matches:
        closest_match = max(VALID_BUSINESS_TYPES, key=lambda x: max(calculate_similarity(word, x) for word in input_words))
        matches.add(closest_match)

    return list(matches)[:max_matches]

# Update KEYWORD_TO_TYPES with more mappings
KEYWORD_TO_TYPES = {
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