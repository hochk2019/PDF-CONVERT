"""FastAPI application exposing OCR job management endpoints."""
from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from . import get_settings
from .audit import append_job_log, record_audit
from .auth import (
    authenticate_user,
    create_access_token,
    get_current_active_admin,
    get_current_active_user,
    get_password_hash,
    get_user_from_token,
)
from .config import Settings
from .database import Base, SessionLocal, engine, get_session
from .logging_config import configure_logging
from .models import Job, JobStatus, User
from .schemas import (
    AuditLogOut,
    JobCreateResponse,
    JobOut,
    JobStatusResponse,
    OCRConfigOut,
    TokenResponse,
    UserCreate,
    UserOut,
)
from .storage import StorageManager
from .tasks import process_pdf

configure_logging()
settings: Settings = get_settings()
app = FastAPI(title="PDF Convert Backend", version="1.0.0")


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)

@app.post("/api/v1/auth/register", response_model=UserOut, status_code=201)
def register_user(payload: UserCreate, db: Session = Depends(get_session)) -> UserOut:
    existing = db.query(User).filter(User.email == payload.email).one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        is_admin=payload.is_admin,
    )
    db.add(user)
    db.flush()
    return UserOut.from_orm(user)


@app.post("/api/v1/auth/token", response_model=TokenResponse)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_session),
) -> TokenResponse:
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    access_token = create_access_token(
        {"sub": str(user.id), "email": user.email, "is_admin": user.is_admin},
        expires_delta=timedelta(minutes=settings.jwt_access_token_expires_minutes),
    )
    record_audit(
        db,
        user_id=user.id,
        action="auth.login",
        ip_address=None,
        user_agent=None,
        metadata={"email": user.email},
    )
    return TokenResponse(access_token=access_token)


@app.get("/api/v1/auth/me", response_model=UserOut)
def read_users_me(current_user: User = Depends(get_current_active_user)) -> UserOut:
    return UserOut.from_orm(current_user)


@app.post("/api/v1/jobs", response_model=JobCreateResponse)
async def create_job(
    request: Request,
    file: UploadFile = File(..., description="PDF file to process"),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> JobCreateResponse:
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    job = Job(user=current_user, input_filename=file.filename, input_path="")
    db.add(job)
    db.flush()

    storage = StorageManager()
    saved_path = storage.save_upload(str(job.id), file.filename, file.file)
    job.input_path = str(saved_path)
    append_job_log(db, job, "File uploaded")
    record_audit(
        db,
        user_id=current_user.id,
        action="job.create",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        metadata={"job_id": str(job.id), "filename": file.filename},
    )

    db.flush()

    process_pdf.delay(str(job.id))
    return JobCreateResponse(id=job.id, status=job.status, message="Job queued for processing")


@app.get("/api/v1/jobs", response_model=list[JobOut])
def list_jobs(
    db: Session = Depends(get_session), current_user: User = Depends(get_current_active_user)
) -> list[JobOut]:
    jobs = (
        db.query(Job)
        .filter(Job.user_id == current_user.id)
        .order_by(Job.created_at.desc())
        .all()
    )
    return [JobOut.from_orm(job) for job in jobs]


@app.get("/api/v1/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> JobOut:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to view this job")
    return JobOut.from_orm(job)


@app.get("/api/v1/jobs/{job_id}/status", response_model=JobStatusResponse)
def get_job_status(
    job_id: uuid.UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> JobStatusResponse:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to view this job")
    return JobStatusResponse.from_orm(job)


@app.get("/api/v1/jobs/{job_id}/result")
def download_result(
    job_id: uuid.UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> FileResponse:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.COMPLETED or not job.result_path:
        raise HTTPException(status_code=400, detail="Job not completed")
    if job.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to download this result")

    storage = StorageManager()
    path = storage.open_result(job.result_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Result not found")
    return FileResponse(path, media_type="application/json", filename=path.name)


@app.get("/api/v1/users/{user_id}/audits", response_model=list[AuditLogOut])
def list_audit_logs(
    user_id: uuid.UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> list[AuditLogOut]:
    user = db.query(User).filter(User.id == user_id).one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if current_user.id != user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to view audit logs")
    logs = [AuditLogOut.from_orm(entry) for entry in user.audit_logs]
    return logs


@app.get("/api/v1/admin/config", response_model=OCRConfigOut)
def get_admin_config(_: User = Depends(get_current_active_admin)) -> OCRConfigOut:
    return OCRConfigOut(
        storage_path=str(settings.storage_path),
        results_path=str(settings.results_path),
        redis_url=settings.redis_url,
        celery_task_queue=settings.celery_task_queue,
    )


@app.get("/api/v1/admin/audit-logs", response_model=list[AuditLogOut])
def get_admin_audit_logs(
    db: Session = Depends(get_session), _: User = Depends(get_current_active_admin)
) -> list[AuditLogOut]:
    logs = db.query(User).join(User.audit_logs).all()
    flattened: list[AuditLogOut] = []
    for user in logs:
        flattened.extend(AuditLogOut.from_orm(entry) for entry in user.audit_logs)
    flattened.sort(key=lambda log: log.created_at, reverse=True)
    return flattened[:200]


@app.websocket("/ws/jobs/{job_id}")
async def job_status_stream(websocket: WebSocket, job_id: uuid.UUID) -> None:
    await websocket.accept()
    last_status: Optional[str] = None
    try:
        while True:
            with SessionLocal() as session:
                token = websocket.query_params.get("token")
                user = get_user_from_token(token, session)
                job = session.query(Job).filter(Job.id == job_id).one_or_none()
                if not job:
                    await websocket.send_json({"error": "Job not found"})
                    await websocket.close(code=4404)
                    return
                if user and (job.user_id == user.id or user.is_admin):
                    payload = {
                        "id": str(job.id),
                        "status": job.status.value if isinstance(job.status, JobStatus) else str(job.status),
                        "error_message": job.error_message,
                        "updated_at": job.updated_at.isoformat(),
                    }
                    if payload["status"] != last_status:
                        await websocket.send_json(payload)
                        last_status = payload["status"]
                else:
                    await websocket.send_json({"error": "Unauthorized"})
                    await websocket.close(code=4403)
                    return
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return
