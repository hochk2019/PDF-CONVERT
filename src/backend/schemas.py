"""Pydantic models for API requests and responses."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .models import JobStatus, LogLevel


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: datetime

    class Config:
        orm_mode = True


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: Optional[str] = None
    is_admin: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: uuid.UUID
    email: str
    is_admin: bool = False
    exp: Optional[int] = None


class OCRConfigOut(BaseModel):
    storage_path: str
    results_path: str
    redis_url: str
    celery_task_queue: str


class JobLogOut(BaseModel):
    created_at: datetime
    level: LogLevel
    message: str
    extra: Optional[Dict[str, Any]] = None

    class Config:
        orm_mode = True


class JobOut(BaseModel):
    id: uuid.UUID
    status: JobStatus
    input_filename: str
    created_at: datetime
    updated_at: datetime
    result_payload: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    logs: List[JobLogOut] = Field(default_factory=list)

    class Config:
        orm_mode = True


class JobStatusResponse(BaseModel):
    id: uuid.UUID
    status: JobStatus
    error_message: Optional[str] = None

    class Config:
        orm_mode = True


class JobCreateResponse(BaseModel):
    id: uuid.UUID
    status: JobStatus
    message: str


class AuditLogOut(BaseModel):
    action: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    metadata: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        orm_mode = True
