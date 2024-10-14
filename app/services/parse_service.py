"""
Parse Service Module

This module provides functions for parsing and extracting information from user queries,
including business types, locations, and additional keywords.
"""

import spacy
from typing import Tuple, List, Optional

# Load the spaCy model
nlp = spacy.load('en_core_web_sm')

# Constants
LOCATION_INDICATORS = ['in', 'at', 'near', 'around']

def parse_query(query: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse a query to extract business type and location using spaCy.

    Args:
        query (str): The input query string.

    Returns:
        Tuple[Optional[str], Optional[str]]: A tuple containing the business type and location.
    """
    doc = nlp(query)
    business_type = None
    location = None

    locations = [ent.text for ent in doc.ents if ent.label_ in ('GPE', 'LOC')]
    if locations:
        location = locations[0]

    business_phrases = [
        chunk.text for chunk in doc.noun_chunks
        if chunk.root.ent_type_ not in ('GPE', 'LOC') and chunk.root.pos_ != 'PRON'
    ]
    if business_phrases:
        business_type = business_phrases[0]

    return business_type, location

def parse_complex_query(query: str) -> Tuple[str, str, List[str]]:
    """
    Parse a complex query to extract business type, location, and additional keywords.

    Args:
        query (str): The input query string.

    Returns:
        Tuple[str, str, List[str]]: A tuple containing the business type, location, and a list of additional keywords.
    """
    query = query.lower()
    words = query.split()
    
    location_start = find_location_indicator(words)
    
    # If no location indicator is found, assume the last word is the location
    if location_start == -1:
        location_start = len(words) - 1
    
    business_type = ' '.join(words[:location_start])
    location = ' '.join(words[location_start+1:])
    
    additional_keywords = extract_additional_keywords(words, business_type, location)
    
    return business_type.strip(), location.strip(), additional_keywords

def find_location_indicator(words: List[str]) -> int:
    """
    Find the index of the location indicator in the list of words.

    Args:
        words (List[str]): List of words from the query.

    Returns:
        int: Index of the location indicator, or -1 if not found.
    """
    for indicator in LOCATION_INDICATORS:
        if indicator in words:
            return words.index(indicator)
    return -1

def extract_additional_keywords(words: List[str], business_type: str, location: str) -> List[str]:
    """
    Extract additional keywords from the query that are not part of the business type or location.

    Args:
        words (List[str]): List of words from the query.
        business_type (str): Extracted business type.
        location (str): Extracted location.

    Returns:
        List[str]: List of additional keywords.
    """
    business_words = set(business_type.split())
    location_words = set(location.split())
    indicator_words = set(LOCATION_INDICATORS)
    
    return [word for word in words if word not in business_words 
            and word not in location_words 
            and word not in indicator_words]

# Example usage:
# if __name__ == "__main__":
#     query = "Korean restaurants in San Francisco with outdoor seating"
#     business_type, location, additional_keywords = parse_complex_query(query)
#     print(f"Business Type: {business_type}")
#     print(f"Location: {location}")
#     print(f"Additional Keywords: {additional_keywords}")
