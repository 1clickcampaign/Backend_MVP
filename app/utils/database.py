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

from app.models.lead import LeadCreate

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

async def upload_leads_to_supabase(leads: List[LeadCreate]) -> None:
    """
    Upload a list of leads to Supabase.

    Args:
        leads (List[LeadCreate]): List of leads to upload.
    """
    total_leads = len(leads)
    successful_uploads = 0
    failed_uploads = 0

    for lead in leads:
        result = await upload_lead_with_retry(lead)
        if result:
            successful_uploads += 1
        else:
            failed_uploads += 1

    logger.info(f"Upload summary: Total leads: {total_leads}, Successful: {successful_uploads}, Failed: {failed_uploads}")

async def upload_lead_with_retry(lead: LeadCreate, max_retries: int = MAX_RETRIES) -> bool:
    """
    Upload a single lead to Supabase with retry logic.

    Args:
        lead (LeadCreate): The lead to upload.
        max_retries (int): Maximum number of retry attempts.

    Returns:
        bool: True if upload was successful, False otherwise.
    """
    supabase = SupabaseClientSingleton.get_instance()

    for attempt in range(max_retries):
        try:
            lead_dict = lead.dict()
            logger.debug(f"Attempting to upsert lead: {lead.name}")
            logger.debug(f"Lead data: {lead_dict}")
            response = supabase.table("leads").upsert(lead_dict, on_conflict="source,external_id").execute()
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
