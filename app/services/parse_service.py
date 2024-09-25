import spacy
import re
from typing import Tuple, List

nlp = spacy.load('en_core_web_sm')

def parse_query(query):
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
    # Convert query to lowercase for easier matching
    query = query.lower()
    
    # Define location indicators
    location_indicators = ['in', 'at', 'near', 'around']
    
    # Split the query into words
    words = query.split()
    
    # Find the location indicator
    location_start = -1
    for indicator in location_indicators:
        if indicator in words:
            location_start = words.index(indicator)
            break
    
    # If no location indicator is found, assume the last word is the location
    if location_start == -1:
        location_start = len(words) - 1
    
    # Extract business type and location
    business_type = ' '.join(words[:location_start])
    location = ' '.join(words[location_start+1:])
    
    # Extract additional keywords (for future use)
    additional_keywords = [word for word in words if word not in business_type.split() and word not in location.split() and word not in location_indicators]
    
    return business_type.strip(), location.strip(), additional_keywords

# Example usage:
# business_type, location, additional_keywords = parse_complex_query("Korean restaurants in San Francisco with outdoor seating")
# print(f"Business Type: {business_type}")
# print(f"Location: {location}")
# print(f"Additional Keywords: {additional_keywords}")
