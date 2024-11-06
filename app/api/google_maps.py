"""
Google Maps API Module (/leads/google_maps)

This module provides an API endpoint for fetching business leads from Google Maps
based on a search query. It uses Google Maps API for geocoding and search,
and also includes a fallback mechanism using Google Maps Scraper for complex queries.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
import logging
from app.utils.database import generate_business_hash

from app.models.google_maps_lead import GoogleMapsLead
from app.services.parse_service import parse_complex_query
from app.services.google_maps_service import fetch_leads_from_google_maps, VALID_FIELDS as API_VALID_FIELDS, FIELD_MAPPINGS
from app.services.gmaps_scraping_service import GoogleMapsScraper, VALID_SCRAPING_FIELDS
from app.utils.auth import get_current_user
from app.tasks import TaskManager
from app.utils.string_matching import find_exact_match, find_best_matches
from app.utils.config import VALID_BUSINESS_TYPES

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
task_manager = TaskManager()

class GoogleMapsLeadRequest(BaseModel):
    """
    Request model for Google Maps lead fetching.
    """
    query: str = Field(..., description="Search query for Google Maps")
    max_leads: int = Field(default=1000, ge=1, le=5000, description="Maximum number of leads to fetch (1-5000)")
    fields: Optional[List[str]] = Field(default=None, description="Fields to include in the response")

    @field_validator('query', mode='before')
    @classmethod
    def validate_query(cls, v):
        if not v.strip():
            raise ValueError('Query must not be empty')
        return v

    @field_validator('fields', mode='before')
    @classmethod
    def validate_fields(cls, v):
        if v is not None:
            # Get valid fields from FIELD_MAPPINGS
            valid_fields = set(FIELD_MAPPINGS.keys())
            invalid_fields = [field for field in v if field not in valid_fields]
            if invalid_fields:
                raise ValueError(
                    f"Invalid fields: {', '.join(invalid_fields)}. "
                    f"Valid fields are: {', '.join(valid_fields)}"
                )
        return v

@router.post("/", response_model=dict, summary="Queue a task to get leads from Google Maps")
async def queue_google_maps_leads(
    request: GoogleMapsLeadRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user)
):
    try:
        # Parse the query
        business_type, location, _ = parse_complex_query(request.query)
        
        if business_type:
            # Try to find exact match first
            exact_match = find_exact_match(business_type, VALID_BUSINESS_TYPES)
            if exact_match:
                logger.info(f"Found exact match for business type: {exact_match}")
                business_type = exact_match
            else:
                # Try fuzzy matching
                best_matches = find_best_matches(business_type)
                if best_matches:
                    logger.info(f"Found fuzzy match for business type: {best_matches[0]}")
                    business_type = best_matches[0]
                else:
                    logger.warning(f"No valid business type match found for '{business_type}', will use scraper")
                    business_type = None

        # Queue the task with the validated/matched business type
        task_id = await task_manager.fetch_leads(
            query=request.query,
            max_leads=request.max_leads,
            fields=request.fields,
            user_id=user_id,
            matched_business_type=business_type  # Pass the matched business type to the task
        )

        return {
            "task_id": task_id,
            "status": "queued",
            "message": "Task has been queued successfully. Use the /status/{task_id} endpoint to check the status."
        }

    except ValueError as ve:
        if "Insufficient tokens" in str(ve):
            raise HTTPException(status_code=402, detail=str(ve))
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error in queue_google_maps_leads: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred while processing your request: {str(e)}")

@router.get("/status/{task_id}", summary="Get task status")
async def get_task_status(task_id: str, user_id: str = Depends(get_current_user)):
    status = task_manager.get_task_status(task_id, user_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Task not found or unauthorized")
    return status

@router.get("/result/{task_id}", summary="Get task result")
async def get_task_result(task_id: str, user_id: str = Depends(get_current_user)):
    status = task_manager.get_task_status(task_id, user_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Task not found or unauthorized")
    if status["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task has not completed yet")
    return status["result"]
