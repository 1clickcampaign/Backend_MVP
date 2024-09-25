from app.utils.supabase_client import supabase
from app.models.lead import LeadCreate
import requests
from app.utils.config import GOOGLE_MAPS_API_KEY

def enrich_lead(lead):
    # Existing enrichment logic
    lead = enrich_business_contact(lead)
    lead = enrich_decision_maker(lead)
    
    # Create a LeadEnriched instance
    enriched_lead = LeadCreate(**lead)
    
    # Save enriched lead to Supabase
    save_enriched_lead(enriched_lead)
    
    return enriched_lead.dict()

def enrich_business_contact(lead):
    if lead['source'] == 'google_maps':
        place_id = lead.get('external_id')
        if place_id:
            url = "https://maps.googleapis.com/maps/api/place/details/json"
            params = {
                'place_id': place_id,
                'fields': 'formatted_phone_number,website',
                'key': GOOGLE_MAPS_API_KEY
            }
            response = requests.get(url, params=params)
            data = response.json().get('result', {})
            lead['business_phone'] = data.get('formatted_phone_number')
            website = data.get('website')
            if website:
                lead['business_email'] = extract_email_from_website(website)
    elif lead['source'] == 'shopify':
        # Implement logic to get business contact info from Shopify
        pass
    return lead

def enrich_decision_maker(lead):
    # Placeholder implementation
    lead['decision_maker_name'] = 'Jane Doe'
    lead['decision_maker_linkedin'] = 'https://www.linkedin.com/in/janedoe'
    lead['decision_maker_email'] = 'janedoe@example.com'
    lead['decision_maker_phone'] = '+1-555-6789'
    return lead

def extract_email_from_website(website_url):
    # Implement web scraping to find email on the website
    return 'contact@example.com'

def save_enriched_lead(enriched_lead):
    """
    Saves the enriched lead to the Supabase database.
    
    Args:
        enriched_lead (LeadEnriched): The enriched lead data.
    """
    lead_data = enriched_lead.dict()
    # Extract additional attributes
    additional_attributes = lead_data.pop('additional_attributes', {})
    
    # Prepare data for insertion
    lead_data['additional_attributes'] = additional_attributes
    
    # Insert or update the lead in Supabase
    response = supabase.table('leads').upsert(lead_data).execute()
    if response.error:
        # Handle error (e.g., logging)
        print(f"Error saving lead to Supabase: {response.error}")
