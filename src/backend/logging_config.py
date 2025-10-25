"""Central logging configuration for the backend service."""
from __future__ import annotations

import logging
import logging.config
from typing import Any, Dict

from .config import get_settings


def configure_logging() -> None:
    """Configure structured logging for the application."""

    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            },
            "audit": {
                "format": "%(asctime)s AUDIT [%(name)s] user=%(user_id)s action=%(action)s %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "level": level,
            },
        },
        "loggers": {
            "": {"handlers": ["console"], "level": level},
            "backend.audit": {
                "handlers": ["console"],
                "level": level,
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(config)
