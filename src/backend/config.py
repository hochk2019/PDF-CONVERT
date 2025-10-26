"""Application configuration utilities."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    """Runtime configuration for the backend service."""

    database_url: str = Field(
        "postgresql+psycopg://pdf_convert:pdf_convert@localhost:5432/pdf_convert",
        description="SQLAlchemy database URL for PostgreSQL.",
    )
    redis_url: str = Field("redis://localhost:6379/0", description="Redis connection string used by Celery.")
    celery_result_backend: Optional[str] = Field(
        None,
        description="Optional Celery result backend. Defaults to broker when omitted.",
    )
    celery_task_queue: str = Field("pdf_convert.jobs", description="Primary Celery queue for OCR jobs.")
    storage_path: Path = Field(Path("var/storage"), description="Path where uploaded files are persisted.")
    results_path: Path = Field(Path("var/results"), description="Directory storing processed outputs.")
    log_level: str = Field("INFO", description="Python logging level for the application.")
    audit_retention_days: int = Field(30, description="Number of days to retain audit trail entries.")
    jwt_secret_key: str = Field("change-me", description="Secret key used to sign JWT access tokens.")
    jwt_algorithm: str = Field("HS256", description="JWT signing algorithm.")
    jwt_access_token_expires_minutes: int = Field(60, description="Access token validity window in minutes.")
    llm_provider: Optional[str] = Field(
        None,
        description=(
            "Identifier of the primary LLM provider (e.g. ollama, openrouter, agentrouter)."
        ),
    )
    llm_model: Optional[str] = Field(
        None,
        description="Default model name to request from the configured LLM provider.",
    )
    llm_base_url: Optional[str] = Field(
        None,
        description="Override base URL for the configured LLM provider API.",
    )
    llm_api_key: Optional[str] = Field(
        None,
        description="API key used for authenticated LLM providers (stored only in settings).",
    )
    llm_fallback_enabled: bool = Field(
        False,
        description="Whether LLM provider fallback is enabled in the post-processing pipeline.",
    )

    class Config:
        env_file = ".env"
        env_prefix = "PDFCONVERT_"

    @validator("storage_path", "results_path", pre=True)
    def _expand_path(cls, value: Path | str) -> Path:  # type: ignore[override]
        path = Path(value).expanduser()
        return path


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings."""

    settings = Settings()
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    settings.results_path.mkdir(parents=True, exist_ok=True)
    return settings
