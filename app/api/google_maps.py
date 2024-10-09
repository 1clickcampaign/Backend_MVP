# app/api/leads.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.models.lead import LeadCreate
from app.services.parse_service import parse_complex_query
from app.services.google_maps_service import fetch_leads_from_google_maps
from app.tasks.tasks import enrich_leads
from app.utils.database import upload_leads_to_supabase
from app.utils.config import VALID_BUSINESS_TYPES
from app.utils.string_matching import find_best_matches
import asyncio
from app.services.gmaps_scraping_service import scrape_google_maps, setup_selenium, generate_search_url

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
    
    matched_business_types = find_best_matches(business_type)
    
    if matched_business_types:
        print(f"Matched business types: {matched_business_types}")
        print(f"Fetching leads from Google Maps API for {matched_business_types} in {location}")
        leads = fetch_leads_from_google_maps(matched_business_types, location, max_leads)
    else:
        print(f"No matched business types found. Using Google Maps scraper for query: {query}")
        driver = setup_selenium(headless=True)
        try:
            url = generate_search_url(query)
            leads = scrape_google_maps(driver, url)
            if max_leads:
                leads = leads[:max_leads]
        finally:
            driver.quit()
    
    print(f"Number of leads fetched: {len(leads)}")

    # Convert scraped results to LeadCreate format if necessary
    if leads and isinstance(leads[0], dict):
        leads = [LeadCreate(
            name=lead['name'],
            source="Google Maps",
            external_id=lead.get('external_id', ''),
            business_phone=lead.get('phone', ''),
            source_attributes={
                'formatted_address': lead.get('address', ''),
                'website': lead.get('website', ''),
                'rating': lead.get('rating', ''),
                'user_ratings_total': lead.get('num_reviews', '')
            }
        ) for lead in leads]

    print("Attempting to upload leads to Supabase")
    await upload_leads_to_supabase(leads)
    print(f"Finished uploading {len(leads)} leads to Supabase")

    # Enrich leads asynchronously
    print("Enqueueing lead enrichment task")
    enrich_leads.delay(leads)
    
    print(f"Returning {len(leads)} leads")
    return leads
