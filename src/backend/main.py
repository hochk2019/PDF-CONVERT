"""FastAPI application exposing OCR job management endpoints."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from . import get_settings
from .audit import append_job_log, record_audit
from .config import Settings
from .database import Base, engine, get_session
from .logging_config import configure_logging
from .models import Job, JobStatus, User
from .schemas import AuditLogOut, JobCreateResponse, JobOut, JobStatusResponse
from .storage import StorageManager
from .tasks import process_pdf

configure_logging()
settings: Settings = get_settings()
app = FastAPI(title="PDF Convert Backend", version="1.0.0")


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


def _get_or_create_user(session: Session, email: str) -> User:
    user = session.query(User).filter(User.email == email).one_or_none()
    if user:
        return user
    user = User(email=email, hashed_password=None, full_name=None)
    session.add(user)
    session.flush()
    return user


@app.post("/api/v1/jobs", response_model=JobCreateResponse)
async def create_job(
    request: Request,
    file: UploadFile = File(..., description="PDF file to process"),
    db: Session = Depends(get_session),
    x_user_email: Optional[str] = Header(default="anonymous@example.com", alias="X-User-Email"),
) -> JobCreateResponse:
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    user = _get_or_create_user(db, x_user_email)
    job = Job(user=user, input_filename=file.filename, input_path="")
    db.add(job)
    db.flush()

    storage = StorageManager()
    saved_path = storage.save_upload(str(job.id), file.filename, file.file)
    job.input_path = str(saved_path)
    append_job_log(db, job, "File uploaded")
    record_audit(
        db,
        user_id=user.id,
        action="job.create",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        metadata={"job_id": str(job.id), "filename": file.filename},
    )

    db.flush()

    process_pdf.delay(str(job.id))
    return JobCreateResponse(id=job.id, status=job.status, message="Job queued for processing")


@app.get("/api/v1/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_session)) -> JobOut:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobOut.from_orm(job)


@app.get("/api/v1/jobs/{job_id}/status", response_model=JobStatusResponse)
def get_job_status(job_id: uuid.UUID, db: Session = Depends(get_session)) -> JobStatusResponse:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse.from_orm(job)


@app.get("/api/v1/jobs/{job_id}/result")
def download_result(job_id: uuid.UUID, db: Session = Depends(get_session)) -> FileResponse:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.COMPLETED or not job.result_path:
        raise HTTPException(status_code=400, detail="Job not completed")

    storage = StorageManager()
    path = storage.open_result(job.result_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Result not found")
    return FileResponse(path, media_type="application/json", filename=path.name)


@app.get("/api/v1/users/{user_id}/audits", response_model=list[AuditLogOut])
def list_audit_logs(user_id: uuid.UUID, db: Session = Depends(get_session)) -> list[AuditLogOut]:
    user = db.query(User).filter(User.id == user_id).one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    logs = [AuditLogOut.from_orm(entry) for entry in user.audit_logs]
    return logs
