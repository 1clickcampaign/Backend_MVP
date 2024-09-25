# app/api/leads.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from app.services.parse_service import parse_complex_query
from app.services.google_maps_service import fetch_leads_from_google_maps
from app.tasks.tasks import enrich_leads
from app.models.lead import LeadCreate, LeadResponse
from app.utils.database import upload_leads_to_supabase
from app.utils.config import VALID_BUSINESS_TYPES
from app.utils.string_matching import find_best_matches

router = APIRouter()

class GoogleMapsLeadRequest(BaseModel):
    query: str

@router.post("/", response_model=List[LeadCreate], summary="Get leads from Google Maps")
async def get_google_maps_leads(request: GoogleMapsLeadRequest):
    query = request.query
    print(f"Received query: {query}")
    
    business_type, location, additional_keywords = parse_complex_query(query)
    print(f"Parsed business_type: {business_type}, location: {location}, additional_keywords: {additional_keywords}")
    
    if not business_type or not location:
        raise HTTPException(
            status_code=400,
            detail="Could not extract business type and location from query."
        )
    
    # Match business_type with VALID_BUSINESS_TYPES
    matched_business_types = find_best_matches(business_type)
    if not matched_business_types:
        raise HTTPException(
            status_code=400,
            detail=f"Could not match '{business_type}' with any valid business type."
        )
    
    print(f"Matched business types: {matched_business_types}")
    print(f"Fetching leads from Google Maps for {matched_business_types} in {location}")
    leads = fetch_leads_from_google_maps(matched_business_types, location)
    print(f"Number of leads fetched: {len(leads)}")

    # TODO: Use additional_keywords for further filtering or API queries in the future

    try:
        # Upload leads to Supabase
        print("Attempting to upload leads to Supabase")
        upload_leads_to_supabase(leads)
        print(f"Successfully uploaded {len(leads)} leads to Supabase")
    except Exception as e:
        print(f"Failed to upload leads to Supabase: {str(e)}")
    
    # Enrich leads asynchronously
    print("Enqueueing lead enrichment task")
    enrich_leads.delay(leads)
    
    print(f"Returning {len(leads)} leads")
    return leads
