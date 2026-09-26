from celery import Celery
from app.config import settings

celery_app = Celery(
    "job_search_copilot",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
)

# Ensuree tasks module is registered
import app.tasks 
