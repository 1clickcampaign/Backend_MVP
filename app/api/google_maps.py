# app/api/leads.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from app.models.lead import LeadCreate
from app.services.parse_service import parse_complex_query
from app.services.google_maps_service import fetch_leads_from_google_maps
from app.utils.database import upload_leads_to_supabase
from app.utils.config import VALID_BUSINESS_TYPES, API_KEY
from app.services.gmaps_scraping_service import GoogleMapsScraper
from app.utils.string_matching import find_exact_match

router = APIRouter()

class GoogleMapsLeadRequest(BaseModel):
    query: str
    max_leads: int = Field(default=1000, ge=1, le=5000, description="Maximum number of leads to fetch (1-1000)")
    
@router.post("/", response_model=List[LeadCreate], summary="Get leads from Google Maps")
async def get_google_maps_leads(request: GoogleMapsLeadRequest):
    query = request.query
    max_leads = request.max_leads
    key = request.key
    if not key or key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key."
        )
    
    print(f"Received query: {query}")
    print(f"Max leads requested: {max_leads}")
    
    business_type, location, additional_keywords = parse_complex_query(query)
    print(f"Parsed business_type: {business_type}, location: {location}, additional_keywords: {additional_keywords}")
    
    if not business_type or not location:
        raise HTTPException(
            status_code=400,
            detail="Could not extract business type and location from query."
        )
    
    exact_match = find_exact_match(business_type, VALID_BUSINESS_TYPES)
    
    if exact_match:
        print(f"Exact match found: {exact_match}")
        print(f"Fetching leads from Google Maps API for {exact_match} in {location}")
        results = fetch_leads_from_google_maps([exact_match], location, max_leads)
        leads = []
        for result in results[:max_leads]:
            lead = LeadCreate(
                name=result.get("name", ""),
                source="Google Maps API",
                external_id=result.get("external_id", ""),
                business_phone=result.get("formatted_phone_number", ""),
                source_attributes={
                    "formatted_address": result.get("formatted_address", ""),
                    "website": result.get("website", ""),
                    "rating": result.get("rating"),
                    "user_ratings_total": result.get("user_ratings_total"),
                    "types": result.get("types", []),
                    "business_status": result.get("business_status", ""),
                    "latitude": result.get("latitude", {}),
                    "longitude": result.get("longitude", {})
                }
            )
            leads.append(lead)
    else:
        print(f"No exact match found. Using Google Maps scraper for query: {query}")
        scraper = GoogleMapsScraper(headless=True, max_threads=4)
        url = scraper.generate_search_url(query)
        results = await scraper.scrape_google_maps_fast(url)
        scraper.close()
        
        leads = []
        for result in results[:max_leads]:
            href = result.get("href", "")
            external_id = href.split("https://www.google.com/maps/place/", 1)[-1] if href else result.get("external_id", "")
            
            lead = LeadCreate(
                name=result.get("name", ""),
                source="Google Maps Scraper",
                external_id=external_id or "unknown",
                business_phone=result.get("phone", ""),
                source_attributes={
                    "formatted_address": result.get("address", ""),
                    "website": result.get("website", ""),
                    "rating": result.get("rating"),
                    "user_ratings_total": result.get("total_reviews"),
                    "types": [result.get("business_type", "")],
                    "business_status": result.get("business_status", ""),
                    "href": href,
                    "num_reviews": result.get("num_reviews", ""),
                    "business_type": result.get("business_type", ""),
                    "address": result.get("address", ""),
                    "latitude": result.get("latitude"),
                    "longitude": result.get("longitude"),
                    "total_reviews": result.get("total_reviews"),
                    "wheelchair_accessible": result.get("wheelchair_accessible"),
                    "hours": result.get("hours", {}),
                    "region": result.get("region", ""),
                    "additional_properties": result.get("additional_properties", []),
                    "images": result.get("images", []),
                    "reviews": result.get("reviews", [])
                }
            )
            leads.append(lead)

    print(f"Number of leads fetched: {len(leads)}")

    print("Attempting to upload leads to Supabase")
    await upload_leads_to_supabase(leads)
    print(f"Finished uploading {len(leads)} leads to Supabase")

    print(f"Returning {len(leads)} leads")
    return leads
