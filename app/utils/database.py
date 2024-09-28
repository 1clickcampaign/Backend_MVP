from supabase import create_client
import os
from app.models.lead import LeadCreate
import json
import asyncio

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

async def upload_leads_to_supabase(leads: list[dict], max_retries=3, retry_delay=5):
    supabase = SupabaseClientSingleton.get_instance()
    
    async def upload_lead_with_retry(lead_data):
        lead = LeadCreate(**lead_data)
        lead_dict = lead.dict()
        
        for attempt in range(max_retries):
            try:
                existing_lead = supabase.table('leads').select('*').eq('name', lead_dict['name']).eq('external_id', lead_dict['external_id']).execute()
                
                if not existing_lead.data:
                    supabase.table('leads').insert(lead_dict).execute()
                else:
                    lead_id = existing_lead.data[0]['id']
                    supabase.table('leads').update(lead_dict).eq('id', lead_id).execute()
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"Failed to upload lead after {max_retries} attempts: {str(e)}")
                else:
                    await asyncio.sleep(retry_delay)

    upload_tasks = [upload_lead_with_retry(lead) for lead in leads]
    await asyncio.gather(*upload_tasks)
    
    print(f"Uploaded/Updated {len(leads)} leads to Supabase")