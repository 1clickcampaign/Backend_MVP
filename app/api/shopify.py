from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from app.services.parse_service import parse_query
from app.services.shopify_service import fetch_leads_from_shopify
from app.models.lead import LeadCreate

router = APIRouter()

class ShopifyLeadRequest(BaseModel):
    query: str

@router.post("/", response_model=List[LeadCreate], summary="Get leads from Shopify")
async def get_shopify_leads(request: ShopifyLeadRequest):
    query = request.query
    business_type, location = parse_query(query)
    if not business_type or not location:
        raise HTTPException(
            status_code=400,
            detail="Could not extract business type and location from query."
        )
    leads = fetch_leads_from_shopify(business_type, location)
    return leads
