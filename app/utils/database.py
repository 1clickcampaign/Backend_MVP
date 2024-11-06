"""
Database Utilities

This module provides functions for interacting with the Supabase database,
including reading leads from JSON files and uploading leads to Supabase.
"""

import os
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from geopy.distance import geodesic
import hashlib

from app.models.google_maps_lead import GoogleMapsLead

# Configure logging
logger = logging.getLogger(__name__)

# Constants
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
ENCODINGS = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']

class SupabaseClientSingleton:
    _instance: Optional[Client] = None

    @classmethod
    def get_instance(cls) -> Client:
        if cls._instance is None:
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")
            if not url or not key:
                raise ValueError("Supabase URL or key is not set in environment variables")
            cls._instance = create_client(url, key)
        return cls._instance

def read_leads_from_json(file_path: str) -> List[Dict[str, Any]]:
    """
    Read leads from a JSON file, trying multiple encodings.

    Args:
        file_path (str): Path to the JSON file.

    Returns:
        List[Dict[str, Any]]: List of lead dictionaries.

    Raises:
        ValueError: If unable to read the file with any of the attempted encodings.
    """
    for encoding in ENCODINGS:
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                leads = json.load(file)
            logger.info(f"Successfully read the file using {encoding} encoding.")
            return leads
        except UnicodeDecodeError:
            continue
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON with {encoding} encoding.")
            continue
    
    raise ValueError("Unable to read the JSON file with any of the attempted encodings.")

def get_existing_leads(business_type: str, latitude: float, longitude: float, radius_km: float = 5.0) -> List[GoogleMapsLead]:
    """
    Check the database for existing leads that match the business type and are within a certain radius of the location.

    Args:
        business_type (str): The type of business to search for.
        latitude (float): Latitude of the location.
        longitude (float): Longitude of the location.
        radius_km (float): Radius in kilometers to search within.

    Returns:
        List[GoogleMapsLead]: A list of existing Google Maps leads.
    """
    supabase = SupabaseClientSingleton.get_instance()
    try:
        response = supabase.table("google_maps_leads").select("*").execute()
        logger.debug(f"Supabase response: {response}")

        if response.data:
            leads = []
            for lead in response.data:
                lead_lat = lead.get('latitude')
                lead_lng = lead.get('longitude')
                lead_business_type = lead.get('types')

                if lead_lat and lead_lng and lead_business_type:
                    distance = geodesic((latitude, longitude), (lead_lat, lead_lng)).kilometers
                    if distance <= radius_km and business_type in lead_business_type:
                        leads.append(GoogleMapsLead(**lead))

            logger.info(f"Found {len(leads)} leads matching the criteria.")
            return leads
        else:
            logger.info("No leads found matching the criteria.")
    except Exception as e:
        logger.error(f"Error querying existing leads: {str(e)}")
    return []

async def upload_google_maps_leads_to_supabase(leads: List[GoogleMapsLead]) -> None:
    """
    Upload a list of Google Maps leads to Supabase.

    Args:
        leads (List[GoogleMapsLead]): List of leads to upload.
    """
    total_leads = len(leads)
    successful_uploads = 0
    failed_uploads = 0

    for lead in leads:
        result = await upload_google_maps_lead_with_retry(lead)
        if result:
            successful_uploads += 1
        else:
            failed_uploads += 1

    logger.info(f"Upload summary: Total leads: {total_leads}, Successful: {successful_uploads}, Failed: {failed_uploads}")

async def upload_google_maps_lead_with_retry(lead: GoogleMapsLead, max_retries: int = MAX_RETRIES) -> bool:
    """
    Upload a single Google Maps lead to Supabase with retry logic.

    Args:
        lead (GoogleMapsLead): The lead to upload.
        max_retries (int): Maximum number of retry attempts.

    Returns:
        bool: True if upload was successful, False otherwise.
    """
    supabase = SupabaseClientSingleton.get_instance()

    # Generate a hash for the lead
    lead_hash = generate_business_hash(lead.name, lead.latitude, lead.longitude)
    lead.id = lead_hash  # Set the hash as the id

    for attempt in range(max_retries):
        try:
            lead_dict = lead.dict()
            logger.debug(f"Attempting to upsert lead: {lead.name}")
            logger.debug(f"Lead data: {lead_dict}")
            # Use upsert to handle duplicates based on the id
            response = supabase.table("google_maps_leads").upsert(
                lead_dict, on_conflict="id"
            ).execute()
            if response.data:
                logger.info(f"Successfully upserted lead: {lead.name}")
                return True
            else:
                logger.warning(f"Failed to upsert lead: {lead.name}. Response: {response}")
        except Exception as e:
            logger.error(f"Error upserting lead {lead.name}: {str(e)}")
        
        if attempt < max_retries - 1:
            await asyncio.sleep(RETRY_DELAY * (2 ** attempt))  # Exponential backoff

    logger.error(f"Failed to upsert lead {lead.name} after {max_retries} attempts")
    return False

def generate_business_hash(name: str, latitude: float, longitude: float) -> str:
    """
    Generate a hash for a business based on its name and coordinates.

    Args:
        name (str): The name of the business.
        latitude (float): The latitude coordinate.
        longitude (float): The longitude coordinate.

    Returns:
        str: A hash string representing the business.
    """
    # Format coordinates to 6 decimal places for consistency
    hash_input = f"{name.lower()}|{latitude:.6f}|{longitude:.6f}"
    return hashlib.sha256(hash_input.encode('utf-8')).hexdigest()

async def get_user_tokens(user_id: str) -> int:
    supabase = SupabaseClientSingleton.get_instance()
    response = supabase.table("users").select("credits").eq("id", user_id).execute()
    if response.data:
        return response.data[0]["credits"]
    raise ValueError("User not found")

async def update_user_tokens(user_id: str, credit_change: int) -> int:
    supabase = SupabaseClientSingleton.get_instance()
    response = supabase.rpc("update_user_tokens", {
        "user_id": user_id, 
        "token_change": credit_change
    }).execute()
    if response.data is not None:
        return response.data
    raise ValueError("Failed to update user credits")