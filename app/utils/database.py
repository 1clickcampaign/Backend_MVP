from supabase import create_client
import os
from app.models.lead import LeadCreate
import json
import asyncio
from typing import List

class SupabaseClientSingleton:
    _instance = None

    @staticmethod
    def get_instance():
        if SupabaseClientSingleton._instance is None:
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")
            SupabaseClientSingleton._instance = create_client(url, key)
        return SupabaseClientSingleton._instance

def read_leads_from_json(file_path):
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                leads = json.load(file)
            print(f"Successfully read the file using {encoding} encoding.")
            return leads
        except UnicodeDecodeError:
            continue
        except json.JSONDecodeError:
            print(f"Failed to parse JSON with {encoding} encoding.")
            continue
    
    raise ValueError("Unable to read the JSON file with any of the attempted encodings.")

async def upload_leads_to_supabase(leads: List[LeadCreate]):
    supabase = SupabaseClientSingleton.get_instance()
    
    total_leads = len(leads)
    successful_uploads = 0
    failed_uploads = 0

    for lead in leads:
        result = await upload_lead_with_retry(lead)
        if result:
            successful_uploads += 1
        else:
            failed_uploads += 1

    print(f"Upload summary: Total leads: {total_leads}, Successful: {successful_uploads}, Failed: {failed_uploads}")

async def upload_lead_with_retry(lead: LeadCreate, max_retries=3):
    supabase = SupabaseClientSingleton.get_instance()

    for attempt in range(max_retries):
        try:
            lead_dict = lead.dict()
            print(f"Attempting to upsert lead: {lead.name}")
            print(f"Lead data: {lead_dict}")
            response = supabase.table("leads").upsert(lead_dict, on_conflict="source,external_id").execute()
            if response.data:
                print(f"Successfully upserted lead: {lead.name}")
                return True
            else:
                print(f"Failed to upsert lead: {lead.name}. Response: {response}")
        except Exception as e:
            print(f"Error upserting lead {lead.name}: {str(e)}")
        
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    print(f"Failed to upsert lead {lead.name} after {max_retries} attempts")
    return False
