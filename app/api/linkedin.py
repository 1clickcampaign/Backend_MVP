from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List
import logging

from app.models.lead import LeadCreate
from app.services.parse_service import parse_query
from app.utils.auth import verify_api_key

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class LinkedInLeadRequest(BaseModel):
    query: str = Field(..., description="Search query for LinkedIn")
    max_leads: int = Field(default=100, ge=1, le=1000, description="Maximum number of leads to fetch (1-1000)")

@router.post("/", response_model=List[LeadCreate], summary="Get leads from LinkedIn")
async def get_linkedin_leads(
    request: LinkedInLeadRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Fetch business leads from LinkedIn based on the provided query.

    Args:
        request (LinkedInLeadRequest): The request containing the search query and max leads.
        api_key (str): API key for authentication (injected by dependency).

    Returns:
        List[LeadCreate]: A list of fetched leads.

    Raises:
        HTTPException: If there's an error in processing the request or fetching the data.
    """
    try:
        logger.info(f"Received query: {request.query}")
        logger.info(f"Max leads requested: {request.max_leads}")

        business_type, location = parse_query(request.query)
        if not business_type or not location:
            raise HTTPException(
                status_code=400,
                detail="Could not extract business type and location from query."
            )

        # TODO: Implement LinkedIn lead fetching logic
        # This is where you'll add the actual implementation later
        leads = []  # Placeholder for fetched leads

        logger.info(f"Number of leads fetched: {len(leads)}")

        return leads

    except Exception as e:
        logger.error(f"Error in get_linkedin_leads: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred while processing your request: {str(e)}")
