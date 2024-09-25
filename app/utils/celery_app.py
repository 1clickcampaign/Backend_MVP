from celery import Celery
from app.utils.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

celery_app = Celery(
    'lead_generation',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

celery_app.autodiscover_tasks(['app.tasks'])