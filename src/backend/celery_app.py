"""Celery application instance."""
from __future__ import annotations

from celery import Celery

from .config import get_settings


settings = get_settings()
celery_app = Celery("pdf_convert")
celery_app.conf.broker_url = settings.redis_url
celery_app.conf.result_backend = settings.celery_result_backend or settings.redis_url
celery_app.conf.task_default_queue = settings.celery_task_queue
celery_app.conf.task_routes = {"backend.tasks.*": {"queue": settings.celery_task_queue}}
celery_app.conf.task_track_started = True
celery_app.conf.result_extended = True
