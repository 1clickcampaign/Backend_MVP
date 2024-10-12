from difflib import SequenceMatcher
import re
from typing import List, Optional
from fuzzywuzzy import process, fuzz
from app.utils.config import VALID_BUSINESS_TYPES, BUSINESS_TYPE_KEYWORDS

def simple_stem(word: str) -> str:
    """A simple stemming function."""
    word = word.lower()
    word = re.sub(r'(es|s)$', '', word)  # Remove 'es' or 's' from the end
    word = re.sub(r'ing$', '', word)     # Remove 'ing' from the end
    return word

def stem_phrase(phrase: str) -> str:
    """Stem each word in a phrase."""
    return ' '.join(simple_stem(word) for word in phrase.split())

def calculate_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def find_exact_match(query: str, valid_types: List[str]) -> Optional[str]:
    """
    Find an exact match for the query in the list of valid types,
    considering simple grammatical variations.
    
    Args:
    query (str): The business type to match.
    valid_types (List[str]): List of valid business types.
    
    Returns:
    Optional[str]: The matched business type if found, None otherwise.
    """
    query_stemmed = stem_phrase(query)
    
    for valid_type in valid_types:
        valid_type_stemmed = stem_phrase(valid_type)
        if query_stemmed == valid_type_stemmed:
            return valid_type
    
    # If no exact match found, try partial matching
    for valid_type in valid_types:
        valid_type_stemmed = stem_phrase(valid_type)
        if query_stemmed in valid_type_stemmed or valid_type_stemmed in query_stemmed:
            return valid_type
    
    return None

def find_best_matches(query: str, threshold: int = 80) -> List[str]:
    """
    Find the best matching business types for a given query.
    
    Args:
    query (str): The user's input query.
    threshold (int): The minimum similarity score to consider a match.
    
    Returns:
    List[str]: A list of matched business types.
    """
    query_words = query.lower().split()
    matched_types = set()

    for word in query_words:
        for business_type, keywords in BUSINESS_TYPE_KEYWORDS.items():
            if any(fuzz.partial_ratio(word, keyword.lower()) >= threshold for keyword in keywords):
                matched_types.add(business_type)

    if not matched_types:
        # If no matches found using keywords, try fuzzy matching with business types
        matches = process.extractBests(query, VALID_BUSINESS_TYPES, scorer=fuzz.token_set_ratio, score_cutoff=threshold)
        matched_types = set(match[0] for match in matches)

    return list(matched_types)
