from app.utils.celery_app import celery_app
from app.services.enrichment_service import enrich_lead

@celery_app.task
def enrich_leads(leads):
    enriched_leads = []
    for lead in leads:
        enriched_lead = enrich_lead(lead)
        enriched_leads.append(enriched_lead)
    return enriched_leads
