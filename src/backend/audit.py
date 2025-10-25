"""Utilities for persisting audit and job logs."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from .models import AuditLog, Job, JobLog, LogLevel

LOGGER = logging.getLogger("backend.audit")


def record_audit(
    session: Session,
    *,
    user_id,
    action: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist an audit trail entry and emit a structured log."""

    audit = AuditLog(
        user_id=user_id,
        action=action,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata=metadata or {},
    )
    session.add(audit)
    LOGGER.info("audit log created", extra={"user_id": str(user_id), "action": action, "metadata": metadata or {}})


def append_job_log(
    session: Session,
    job: Job,
    message: str,
    level: LogLevel = LogLevel.INFO,
    extra: Optional[Dict[str, Any]] = None,
) -> JobLog:
    """Add a job log entry and attach it to the job."""

    log = JobLog(job=job, message=message, level=level, extra=extra or {})
    session.add(log)
    LOGGER.info(
        "job log",
        extra={
            "user_id": str(job.user_id),
            "action": f"job.{level.value.lower()}",
            "metadata": {"job_id": str(job.id), "message": message, "extra": extra or {}},
        },
    )
    return log
