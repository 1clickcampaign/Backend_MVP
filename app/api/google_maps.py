"""
Google Maps API Module (/leads/google_maps)

This module provides an API endpoint for fetching business leads from Google Maps
based on a search query. It uses Google Maps API for geocoding and search,
and also includes a fallback mechanism using Google Maps Scraper for complex queries.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
import logging

from app.models.lead import LeadCreate
from app.services.parse_service import parse_complex_query
from app.services.google_maps_service import fetch_leads_from_google_maps
from app.utils.database import upload_leads_to_supabase
from app.utils.config import VALID_BUSINESS_TYPES
from app.services.gmaps_scraping_service import GoogleMapsScraper
from app.utils.string_matching import find_exact_match
from app.utils.auth import verify_api_key

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class GoogleMapsLeadRequest(BaseModel):
    """
    Request model for Google Maps lead fetching.
    """
    query: str = Field(..., description="Search query for Google Maps")
    max_leads: int = Field(default=1000, ge=1, le=5000, description="Maximum number of leads to fetch (1-5000)")

    @field_validator('query')
    @classmethod
    def query_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Query must not be empty')
        return v

@router.post("/", response_model=List[LeadCreate], summary="Get leads from Google Maps")
async def get_google_maps_leads(
    request: GoogleMapsLeadRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Fetch business leads from Google Maps based on the provided query.

    Args:
        request (GoogleMapsLeadRequest): The request containing the search query and max leads.
        api_key (str): API key for authentication (injected by dependency).

    Returns:
        List[LeadCreate]: A list of fetched leads.

    Raises:
        HTTPException: If there's an error in processing the request or fetching the data.
    """
    try:
        logger.info(f"Received query: {request.query}")
        logger.info(f"Max leads requested: {request.max_leads}")

        business_type, location, additional_keywords = parse_complex_query(request.query)
        logger.info(f"Parsed query - Business type: {business_type}, Location: {location}, Additional keywords: {additional_keywords}")

        if not business_type or not location:
            raise HTTPException(
                status_code=400,
                detail="Could not extract business type and location from query."
            )

        exact_match = find_exact_match(business_type, VALID_BUSINESS_TYPES)
        leads = []

        if exact_match:
            logger.info(f"Exact match found: {exact_match}")
            logger.info(f"Fetching leads from Google Maps API for {exact_match} in {location}")
            results = fetch_leads_from_google_maps([exact_match], location, request.max_leads)
            leads = [
                LeadCreate(
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
                for result in results[:request.max_leads]
            ]
        else:
            logger.info(f"No exact match found. Using Google Maps scraper for query: {request.query}")
            scraper = GoogleMapsScraper(headless=True, max_threads=4)
            url = scraper.generate_search_url(request.query)
            results = await scraper.scrape_google_maps_fast(url)
            scraper.close()
            
            leads = [
                LeadCreate(
                    name=result.get("name", ""),
                    source="Google Maps Scraper",
                    external_id=result.get("href", "").split("https://www.google.com/maps/place/", 1)[-1] or "unknown",
                    business_phone=result.get("phone", ""),
                    source_attributes={
                        "formatted_address": result.get("address", ""),
                        "website": result.get("website", ""),
                        "rating": result.get("rating"),
                        "user_ratings_total": result.get("total_reviews"),
                        "types": [result.get("business_type", "")],
                        "business_status": result.get("business_status", ""),
                        "href": result.get("href", ""),
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
                for result in results[:request.max_leads]
            ]

        logger.info(f"Number of leads fetched: {len(leads)}")

        logger.info("Uploading leads to Supabase")
        await upload_leads_to_supabase(leads)
        logger.info(f"Finished uploading {len(leads)} leads to Supabase")

        return leads

    except Exception as e:
        logger.error(f"Error in get_google_maps_leads: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred while processing your request: {str(e)}")
