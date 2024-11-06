import redis
import json
import os
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class RedisService:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'redis'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=0,
            decode_responses=True,
            socket_timeout=5,
            retry_on_timeout=True
        )
        self.cache_ttl = 86400  # 24 hours

    async def get_cached_leads(self, query: str, max_leads: int) -> Optional[List[Dict[str, Any]]]:
        try:
            cache_key = f"leads:gmaps:{self._normalize_query(query)}"
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                leads = json.loads(cached_data)
                return leads[:max_leads] if len(leads) >= max_leads else None
        except Exception as e:
            logger.error(f"Error getting cached leads: {e}")
        return None

    async def cache_leads(self, query: str, leads: List[Dict[str, Any]]):
        try:
            cache_key = f"leads:gmaps:{self._normalize_query(query)}"
            self.redis_client.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(leads)
            )
        except Exception as e:
            logger.error(f"Error caching leads: {e}")

    def _normalize_query(self, query: str) -> str:
        return query.lower().strip().replace(" ", "_")