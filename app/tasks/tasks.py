from app.utils.celery_app import celery_app
from app.services.enrichment_service import enrich_lead
from app.models.lead import LeadCreate

@celery_app.task
def enrich_leads(leads):
    enriched_leads = []
    for lead in leads:
        enriched_lead = enrich_lead(lead)
        enriched_leads.append(LeadCreate(**enriched_lead))
    return [lead.dict() for lead in enriched_leads]
