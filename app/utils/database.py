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
    
    upload_tasks = []
    for lead in leads:
        upload_tasks.append(upload_lead_with_retry(lead))
    await asyncio.gather(*upload_tasks)

async def upload_lead_with_retry(lead: LeadCreate, max_retries=3):
    supabase = SupabaseClientSingleton.get_instance()

    for attempt in range(max_retries):
        try:
            response = await supabase.table("leads").insert(lead.dict()).execute()
            if response.data:
                print(f"Successfully uploaded lead: {lead.name}")
                return
        except Exception as e:
            print(f"Error uploading lead {lead.name}: {str(e)}")
            if attempt == max_retries - 1:
                print(f"Failed to upload lead {lead.name} after {max_retries} attempts")
            else:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
