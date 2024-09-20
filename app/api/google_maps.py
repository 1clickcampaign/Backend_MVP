# app/api/leads.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.parse_service import parse_query
from app.services.google_maps_service import fetch_leads_from_google_maps
from app.tasks.tasks import enrich_leads
from app.models.lead import LeadEnriched, LeadResponse

router = APIRouter()

class GoogleMapsLeadRequest(BaseModel):
    query: str

@router.post("/", response_model=LeadResponse, summary="Get leads from Google Maps")
async def get_google_maps_leads(request: GoogleMapsLeadRequest):
    query = request.query
    business_type, location = parse_query(query)
    if not business_type or not location:
        raise HTTPException(
            status_code=400,
            detail="Could not extract business type and location from query."
        )
    leads = fetch_leads_from_google_maps(business_type, location)
    enrich_leads.delay(leads)
    return {"leads": leads}
