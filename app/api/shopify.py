from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.parse_service import parse_query
from app.services.shopify_service import fetch_leads_from_shopify
from app.tasks.tasks import enrich_leads
from app.models.lead import LeadEnriched, LeadResponse

router = APIRouter()

class ShopifyLeadRequest(BaseModel):
    query: str

@router.post("/", response_model=LeadResponse, summary="Get leads from Shopify")
async def get_shopify_leads(request: ShopifyLeadRequest):
    query = request.query
    business_type, location = parse_query(query)
    if not business_type or not location:
        raise HTTPException(
            status_code=400,
            detail="Could not extract business type and location from query."
        )
    leads = fetch_leads_from_shopify(business_type, location)
    enrich_leads.delay(leads)
    return {"leads": leads}
