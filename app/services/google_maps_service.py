import requests
import time
from app.utils.config import GOOGLE_MAPS_API_KEY
from app.models.lead import LeadEnriched

def fetch_leads_from_google_maps(business_type, location):
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        'query': f"{business_type} in {location}",
        'key': GOOGLE_MAPS_API_KEY
    }
    results = []
    response = requests.get(url, params=params)
    data = response.json()
    results.extend(data.get('results', []))

    while 'next_page_token' in data and len(results) < 60:
        next_page_token = data['next_page_token']
        time.sleep(2)
        params['pagetoken'] = next_page_token
        response = requests.get(url, params=params)
        data = response.json()
        results.extend(data.get('results', []))

    leads = []
    for business in results:
        lead = LeadEnriched(
            name=business['name'],
            source='google_maps',
            external_id=business['place_id']
        )
        leads.append(lead.dict())
    return leads
