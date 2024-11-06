from app.celery import celery_app
from celery import states
from app.services.google_maps_service import fetch_leads_from_google_maps
from app.services.gmaps_scraping_service import GoogleMapsScraper
from app.models.google_maps_lead import GoogleMapsLead
from app.utils.database import upload_google_maps_leads_to_supabase, get_user_tokens, update_user_tokens, generate_business_hash
from app.services.parse_service import parse_complex_query
from app.services.redis_service import RedisService
import asyncio
from typing import List, Optional
import logging
import traceback

logger = logging.getLogger(__name__)

def calculate_max_tokens(max_leads: int, fields: list) -> int:
    """Calculate maximum possible token cost"""
    base_cost = max_leads  # 1 token per lead
    field_multiplier = len(fields) * 0.1 if fields else 1  # 10% extra per field
    return int(base_cost * max(1, field_multiplier) * 1.2)  # Add 20% buffer

@celery_app.task(bind=True)
def fetch_leads_task(self, query, max_leads, fields, user_id, matched_business_type=None):
    """Celery task for fetching Google Maps leads"""
    self.update_state(state=states.STARTED)
    redis_service = RedisService()
    
    try:
        # Create an event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Hold maximum possible tokens
        max_tokens = calculate_max_tokens(max_leads, fields or [])
        user_tokens = loop.run_until_complete(get_user_tokens(user_id))
        
        if user_tokens < max_tokens:
            raise ValueError(f"Insufficient tokens. Maximum required: {max_tokens}, Available: {user_tokens}")

        # Check Redis cache first
        cached_leads = loop.run_until_complete(redis_service.get_cached_leads(query, max_leads))
        if cached_leads:
            loop.close()
            return {
                "status": "completed",
                "progress": 100,
                "total_leads": len(cached_leads),
                "result": cached_leads,
                "source": "cache"
            }

        # If not in cache, proceed with scraping
        if matched_business_type:
            business_type = matched_business_type
            _, location, _ = parse_complex_query(query)
        else:
            business_type, location, _ = parse_complex_query(query)
        
        if business_type and location:
            results = fetch_leads_from_google_maps([business_type], location, max_leads, fields)
            logger.debug(f"Results from fetch_leads_from_google_maps: {results}")
            
            # Check if we need to use scraper instead
            if isinstance(results, dict) and results.get("requires_scraper"):
                logger.info("Switching to scraper due to requested fields")
                scraper = GoogleMapsScraper(headless=True, max_threads=4)
                url = scraper.generate_search_url(query)
                results = loop.run_until_complete(scraper.scrape(url, fields))
                scraper.close()
            elif isinstance(results, dict):
                results = results.get("leads", [])
        else:
            scraper = GoogleMapsScraper(headless=True, max_threads=4)
            url = scraper.generate_search_url(query)
            results = loop.run_until_complete(scraper.scrape(url, fields))
            scraper.close()
        
        if results and isinstance(results, list):
            google_maps_leads = []
            google_maps_leads_dict = []
            for result in results:
                if isinstance(result, dict):
                    try:
                        # Log the result for debugging
                        logger.info(f"Processing result: {result}")
                        
                        # Ensure coordinates exist
                        if 'latitude' not in result or 'longitude' not in result:
                            logger.error(f"Missing coordinates for business: {result.get('name')}")
                            continue
                        
                        # Generate hash using name and coordinates
                        result['id'] = generate_business_hash(
                            result['name'],
                            result['latitude'],  # Remove .get() since we verified they exist
                            result['longitude']
                        )
                        lead = GoogleMapsLead(**result)
                        google_maps_leads.append(lead)
                        google_maps_leads_dict.append(lead.dict())
                    except Exception as e:
                        logger.error(f"Error creating GoogleMapsLead from result: {result}")
                        logger.error(f"Error details: {str(e)}")
                else:
                    logger.error(f"Invalid result type: {type(result)}, expected dict. Value: {result}")
        else:
            logger.error(f"Invalid results type: {type(results)}, expected list. Value: {results}")
            google_maps_leads = []
            google_maps_leads_dict = []

        # Prepare response data
        response_data = {
            "status": "completed",
            "progress": 100,
            "total_leads": len(google_maps_leads_dict),
            "result": google_maps_leads_dict,
            "source": "scraper"
        }

        # Only deduct tokens for actual leads found
        actual_cost = len(google_maps_leads_dict)
        if fields:
            actual_cost = int(actual_cost * (1 + len(fields) * 0.1))

        # Queue background task with actual cost
        if google_maps_leads:
            process_google_maps_leads_background.delay(
                query=query, 
                google_maps_leads_dict=google_maps_leads_dict, 
                user_id=user_id,
                token_cost=actual_cost  # Pass actual cost
            )

        loop.close()
        return response_data
    except Exception as e:
        if 'loop' in locals():
            loop.close()
        logger.error(f"Error in fetch_leads_task: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            "status": "failed",
            "error": str(e)
        }

@celery_app.task
def process_google_maps_leads_background(query: str, google_maps_leads_dict: List[dict], user_id: str, token_cost: int):
    """Background task for processing Google Maps leads after they've been returned to the user"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        google_maps_leads = [GoogleMapsLead(**lead) for lead in google_maps_leads_dict]
        
        # Run all background operations with actual token cost
        loop.run_until_complete(asyncio.gather(
            RedisService().cache_leads(query, google_maps_leads_dict),
            upload_google_maps_leads_to_supabase(google_maps_leads),
            update_user_tokens(user_id, -token_cost)  # Use actual cost
        ))
        
        loop.close()
        return True
    except Exception as e:
        if 'loop' in locals():
            loop.close()
        logger.error(f"Error in process_google_maps_leads_background: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

class TaskManager:
    async def fetch_leads(self, query: str, max_leads: int, fields: Optional[List[str]], user_id: str, matched_business_type: Optional[str] = None):
        # Create Celery task with the matched business type
        task = fetch_leads_task.delay(query, max_leads, fields, user_id, matched_business_type)
        return str(task.id)

    def get_task_status(self, task_id, user_id):
        task = fetch_leads_task.AsyncResult(task_id)
        if task.state == states.PENDING:
            return {
                "status": "pending",
                "user_id": user_id
            }
        elif task.state == states.STARTED:
            return {
                "status": "running",
                "user_id": user_id
            }
        elif task.state == states.SUCCESS:
            return task.result
        elif task.state == states.FAILURE:
            return {
                "status": "failed",
                "error": str(task.result),
                "user_id": user_id
            }

task_manager = TaskManager()
