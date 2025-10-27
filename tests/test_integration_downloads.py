"""Integration-style tests that exercise the download endpoints end-to-end."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.auth import get_current_active_user
from backend.config import get_settings
from backend.database import get_session
from backend.main import app
from backend.models import JobStatus
from backend.storage import StorageManager


def _clear_overrides() -> None:
    """Remove dependency overrides registered during a test."""

    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_active_user, None)


def test_completed_job_download_flow(tmp_path, monkeypatch):
    """A completed job exposes JSON, DOCX and XLSX downloads through the API."""

    monkeypatch.setenv("PDFCONVERT_RESULTS_PATH", str(tmp_path / "results"))
    monkeypatch.setenv("PDFCONVERT_STORAGE_PATH", str(tmp_path / "storage"))
    get_settings.cache_clear()
    monkeypatch.setattr("backend.main.Base.metadata.create_all", lambda *_, **__: None)

    storage = StorageManager()

    job_id = uuid.uuid4()
    user_id = uuid.uuid4()

    result_path = storage.write_result(str(job_id), "{\"text\": \"converted\"}")
    docx_path = storage.write_binary_artifact(str(job_id), ".docx", b"docx-bytes")
    xlsx_path = storage.write_binary_artifact(str(job_id), ".xlsx", b"xlsx-bytes")

    payload = {
        "artifacts": {"docx": str(docx_path), "xlsx": str(xlsx_path)},
        "pages": ["converted"],
    }

    timestamp = datetime.now(timezone.utc)

    class DummyQuery:
        def __init__(self, job_obj):
            self._job = job_obj

        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):  # pragma: no cover - behaviour mirrors SQLAlchemy
            return self

        def all(self):
            return [self._job]

        def one_or_none(self):
            return self._job

    class DummySession:
        def __init__(self, job_obj):
            self._job = job_obj

        def query(self, model):  # pragma: no cover - mimic ORM session
            return DummyQuery(self._job)

    job = SimpleNamespace(
        id=job_id,
        user_id=user_id,
        status=JobStatus.COMPLETED,
        input_filename="invoice.pdf",
        created_at=timestamp,
        updated_at=timestamp,
        result_path=str(result_path),
        result_payload=payload,
        llm_options={},
        error_message=None,
        logs=[],
    )

    session = DummySession(job)
    user = SimpleNamespace(id=user_id, is_admin=False, is_active=True)

    try:
        app.dependency_overrides[get_session] = lambda: session
        app.dependency_overrides[get_current_active_user] = lambda: user

        with TestClient(app) as client:
            jobs_response = client.get("/api/v1/jobs")
            assert jobs_response.status_code == 200
            data = jobs_response.json()
            assert data[0]["result_payload"]["artifacts"] == {
                "docx": str(docx_path),
                "xlsx": str(xlsx_path),
            }

            result_response = client.get(f"/api/v1/jobs/{job_id}/result")
            assert result_response.status_code == 200
            assert result_response.headers["content-type"] == "application/json"
            assert result_response.content == b'{"text": "converted"}'

            docx_response = client.get(f"/api/v1/jobs/{job_id}/artifacts/docx")
            assert docx_response.status_code == 200
            assert docx_response.content == b"docx-bytes"

            xlsx_response = client.get(f"/api/v1/jobs/{job_id}/artifacts/xlsx")
            assert xlsx_response.status_code == 200
            assert xlsx_response.content == b"xlsx-bytes"
    finally:
        _clear_overrides()
        get_settings.cache_clear()
