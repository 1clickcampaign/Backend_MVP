from celery import Celery
from app.utils.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

celery_app = Celery(
    'lead_generation',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND
)

celery_app.autodiscover_tasks(['app.tasks'])