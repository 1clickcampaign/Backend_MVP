"""
Main FastAPI Application

This module initializes and configures the main FastAPI application.
It sets up routers, middleware, and global exception handlers.
"""

import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from dotenv import load_dotenv

from app.api import google_maps, shopify
from app.utils.config import get_settings
from app.utils.database import initialize_supabase_client

# Load environment variables
load_dotenv()

# Initialize settings
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="DataPull API",
    version="1.0.0",
    description="API for generating and enriching leads from multiple sources.",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase client
supabase_client = initialize_supabase_client()

# Include routers
app.include_router(google_maps.router, prefix="/leads/google_maps", tags=["Google Maps Leads"])
app.include_router(shopify.router, prefix="/leads/shopify", tags=["Shopify Leads"])

@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify the API is running.

    Returns:
        dict: A dictionary with the status of the API.
    """
    return {"status": "healthy"}

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Global exception handler for HTTPExceptions.

    Args:
        request (Request): The incoming request.
        exc (HTTPException): The raised HTTP exception.

    Returns:
        JSONResponse: A JSON response containing the error details.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled exceptions.

    Args:
        request (Request): The incoming request.
        exc (Exception): The raised exception.

    Returns:
        JSONResponse: A JSON response containing the error details.
    """
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )

def custom_openapi():
    """
    Customize the OpenAPI schema for the API documentation.

    Returns:
        dict: The customized OpenAPI schema.
    """
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="DataPull API",
        version="1.0.0",
        description="API for generating and enriching leads from multiple sources.",
        routes=app.routes,
    )
    openapi_schema["info"]["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
