# app/api/leads.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.models.lead import LeadCreate
from app.services.parse_service import parse_complex_query
from app.services.google_maps_service import fetch_leads_from_google_maps
from app.utils.database import upload_leads_to_supabase
from app.utils.config import VALID_BUSINESS_TYPES
from app.utils.string_matching import find_exact_match
from app.services.gmaps_scraping_service import GoogleMapsScraper

router = APIRouter()

class GoogleMapsLeadRequest(BaseModel):
    query: str
    max_leads: Optional[int] = None

@router.post("/", response_model=List[LeadCreate], summary="Get leads from Google Maps")
async def get_google_maps_leads(request: GoogleMapsLeadRequest):
    query = request.query
    max_leads = request.max_leads
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
    
    if exact_match: #dev note: user should have a choice if exact match is not found, to proceed with advanced scraping or not
        print(f"Exact match found: {exact_match}")
        print(f"Fetching leads from Google Maps API for {exact_match} in {location}")
        leads = fetch_leads_from_google_maps([exact_match], location, max_leads)
    else:
        print(f"No exact match found. Using Google Maps scraper for query: {query}")
        scraper = GoogleMapsScraper(headless=True, max_threads=4)
        url = scraper.generate_search_url(query)
        results = await scraper.scrape_google_maps_fast(url)
        
        leads = []
        for result in results[:max_leads] if max_leads else results:
            href = result.get("href", "")
            external_id = href.split("https://www.google.com/maps/place/", 1)[-1] if href else ""
            
            lead = LeadCreate(
                name=result.get("name", ""),
                source="Google Maps Scraper",
                external_id=external_id,
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
        scraper.close()
    
    print(f"Number of leads fetched: {len(leads)}")

    print("Attempting to upload leads to Supabase")
    await upload_leads_to_supabase(leads)
    print(f"Finished uploading {len(leads)} leads to Supabase")
    
    print(f"Returning {len(leads)} leads")
    return leads
