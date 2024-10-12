import os
from fastapi import FastAPI
from app.api import google_maps, shopify

app = FastAPI(
    title="DataPull API",
    version="1.0.0",
    description="API for generating and enriching leads from multiple sources."
)

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")

app.include_router(google_maps.router, prefix="/leads/google_maps", tags=["Google Maps Leads"])
app.include_router(shopify.router, prefix="/leads/shopify", tags=["Shopify Leads"])

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
