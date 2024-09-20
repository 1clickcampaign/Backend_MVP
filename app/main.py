from fastapi import FastAPI
from app.api import google_maps, shopify

app = FastAPI(
    title="DataPull API",
    version="1.0.0",
    description="API for generating and enriching leads from multiple sources."
)

app.include_router(google_maps.router, prefix="/leads/google_maps", tags=["Google Maps Leads"])
app.include_router(shopify.router, prefix="/leads/shopify", tags=["Shopify Leads"])