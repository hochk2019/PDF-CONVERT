"""Backend service exposing FastAPI endpoints and Celery tasks."""

from .config import get_settings

__all__ = ["get_settings"]
