from __future__ import annotations

import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.auth import get_current_active_user
from backend.config import get_settings
from backend.database import get_session
from backend.main import app
from backend.models import Job, JobStatus
from backend.storage import StorageManager


def _clear_overrides() -> None:
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_active_user, None)


def test_download_artifact_streams_file(tmp_path, monkeypatch):
    monkeypatch.setenv("PDFCONVERT_RESULTS_PATH", str(tmp_path / "results"))
    monkeypatch.setenv("PDFCONVERT_STORAGE_PATH", str(tmp_path / "storage"))
    get_settings.cache_clear()
    monkeypatch.setattr("backend.main.Base.metadata.create_all", lambda *_, **__: None)

    storage = StorageManager()

    job_id = uuid.uuid4()
    user_id = uuid.uuid4()
    docx_path = storage.write_binary_artifact(str(job_id), ".docx", b"document")

    payload = {"artifacts": {"docx": str(docx_path)}}

    class DummyQuery:
        def __init__(self, job_obj):
            self._job = job_obj

        def filter(self, *_args, **_kwargs):
            return self

        def one_or_none(self):
            return self._job

    class DummySession:
        def __init__(self, job_obj):
            self._job = job_obj

        def query(self, model):
            assert model is Job
            return DummyQuery(self._job)

    job = SimpleNamespace(
        id=job_id,
        user_id=user_id,
        status=JobStatus.COMPLETED,
        result_payload=payload,
    )

    session = DummySession(job)
    user = SimpleNamespace(id=user_id, is_admin=False)

    try:
        app.dependency_overrides[get_session] = lambda: session
        app.dependency_overrides[get_current_active_user] = lambda: user

        with TestClient(app) as client:
            response = client.get(f"/api/v1/jobs/{job_id}/artifacts/docx")

            assert response.status_code == 200
            assert (
                response.headers["content-type"]
                == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            assert response.content == b"document"
    finally:
        _clear_overrides()
        get_settings.cache_clear()


def test_download_artifact_requires_ownership(tmp_path, monkeypatch):
    monkeypatch.setenv("PDFCONVERT_RESULTS_PATH", str(tmp_path / "results"))
    monkeypatch.setenv("PDFCONVERT_STORAGE_PATH", str(tmp_path / "storage"))
    get_settings.cache_clear()
    monkeypatch.setattr("backend.main.Base.metadata.create_all", lambda *_, **__: None)

    storage = StorageManager()

    job_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    docx_path = storage.write_binary_artifact(str(job_id), ".docx", b"document")
    payload = {"artifacts": {"docx": str(docx_path)}}

    class DummyQuery:
        def __init__(self, job_obj):
            self._job = job_obj

        def filter(self, *_args, **_kwargs):
            return self

        def one_or_none(self):
            return self._job

    class DummySession:
        def __init__(self, job_obj):
            self._job = job_obj

        def query(self, model):
            assert model is Job
            return DummyQuery(self._job)

    job = SimpleNamespace(
        id=job_id,
        user_id=owner_id,
        status=JobStatus.COMPLETED,
        result_payload=payload,
    )

    session = DummySession(job)
    other_user = SimpleNamespace(id=uuid.uuid4(), is_admin=False)

    try:
        app.dependency_overrides[get_session] = lambda: session
        app.dependency_overrides[get_current_active_user] = lambda: other_user

        with TestClient(app) as client:
            response = client.get(f"/api/v1/jobs/{job_id}/artifacts/docx")

            assert response.status_code == 403
    finally:
        _clear_overrides()
        get_settings.cache_clear()
