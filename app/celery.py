from celery import Celery
import os

REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

celery_app = Celery(
    'app',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['app.tasks']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True
)