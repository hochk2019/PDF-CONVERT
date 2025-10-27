from __future__ import annotations

import os
import sys
import types
from enum import Enum
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("PDFCONVERT_DATABASE_URL", "sqlite:///:memory:")

if "src.backend.models" not in sys.modules:
    models_stub = types.ModuleType("src.backend.models")

    class JobStatus(Enum):
        PENDING = "pending"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"

    class LogLevel(Enum):
        INFO = "INFO"
        WARNING = "WARNING"
        ERROR = "ERROR"
        DEBUG = "DEBUG"

    class Job:  # pragma: no cover - placeholder for type checking
        pass

    class JobLog:  # pragma: no cover - placeholder
        pass

    class AuditLog:  # pragma: no cover - placeholder
        pass

    models_stub.JobStatus = JobStatus
    models_stub.LogLevel = LogLevel
    models_stub.Job = Job
    models_stub.JobLog = JobLog
    models_stub.AuditLog = AuditLog
    sys.modules["src.backend.models"] = models_stub

if "src.backend.database" not in sys.modules:
    database_stub = types.ModuleType("src.backend.database")

    class Base:  # pragma: no cover - placeholder
        pass

    def session_scope():  # pragma: no cover - replaced during tests
        raise RuntimeError("session_scope stub should be patched in tests")

    database_stub.Base = Base
    database_stub.session_scope = session_scope
    sys.modules["src.backend.database"] = database_stub

from src.backend.models import JobStatus, LogLevel
from src.backend.pipeline import LLMProcessingError, PipelineResult
from src.backend import tasks


class FakeSession:
    def __init__(self, job):
        self.job = job
        self.log_entries: list[dict[str, object]] = []
        self.added = []
        self.flush_called = False
        self.closed = False
        self.committed = False

    def add(self, obj):  # pragma: no cover - interface compatibility
        self.added.append(obj)

    def flush(self):  # pragma: no cover - interface compatibility
        self.flush_called = True

    def commit(self):  # pragma: no cover - interface compatibility
        self.committed = True

    def rollback(self):  # pragma: no cover - interface compatibility
        self.committed = False

    def close(self):  # pragma: no cover - interface compatibility
        self.closed = True

    def get(self, model, identifier):  # pragma: no cover - interface compatibility
        if identifier == self.job.id:
            return self.job
        return None


def fake_append_job_log(session, job, message, level=LogLevel.INFO, extra=None):
    session.log_entries.append({"message": message, "level": level, "extra": extra})


def _patch_infra(monkeypatch, job, pipeline=None):
    session = FakeSession(job)

    @contextmanager
    def fake_scope():
        try:
            yield session
        finally:
            session.commit()
            session.close()

    monkeypatch.setattr(tasks, "session_scope", fake_scope)
    monkeypatch.setattr(tasks, "append_job_log", fake_append_job_log)
    if pipeline is not None:
        monkeypatch.setattr(tasks, "OCRPipeline", lambda: pipeline)
    return session


def build_job(**overrides):
    defaults = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "input_path": "/tmp/input.pdf",
        "status": JobStatus.PENDING,
        "result_path": None,
        "result_payload": None,
        "llm_options": {},
        "error_message": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_process_pdf_logs_llm_usage(monkeypatch):
    metadata = {
        "raw_pages": ["raw"],
        "pages": ["corrected"],
        "combined_text": "corrected",
        "raw_combined_text": "raw",
        "average_confidence": 0.9,
        "page_details": [],
        "llm": {
            "enabled": True,
            "providers": ["primary", "fallback"],
            "provider_usage": {"1": "fallback"},
            "model": "llm-x",
            "fallback_configured": True,
            "fallback_used": True,
            "fallback_attempts": [
                {
                    "page": 1,
                    "attempts": [
                        {"provider": "primary", "status": "failed"},
                        {"provider": "fallback", "status": "success"},
                    ],
                }
            ],
            "artifacts": {"docx": "/tmp/result.docx"},
        },
    }

    class DummyPipeline:
        def run(self, job_id, input_path, llm_options=None):
            assert llm_options == job.llm_options
            return PipelineResult(
                text="corrected",
                pages=["corrected"],
                raw_pages=["raw"],
                output_path=Path("/tmp/result.json"),
                metadata=metadata,
                artifacts={"docx": Path("/tmp/result.docx")},
            )

    job = build_job(llm_options={"provider": "primary"})
    session = _patch_infra(monkeypatch, job, DummyPipeline())

    tasks.process_pdf(str(job.id))

    assert job.status == JobStatus.COMPLETED
    assert job.result_path == "/tmp/result.json"
    assert job.result_payload == metadata
    assert job.result_payload["artifacts"] == {"docx": "/tmp/result.docx"}

    messages = [entry["message"] for entry in session.log_entries]
    assert "Job picked up by worker." in messages
    assert "LLM post-processing applied." in messages
    assert "LLM fallback attempts recorded." in messages

    fallback_entry = next(
        entry for entry in session.log_entries if entry["message"] == "LLM fallback attempts recorded."
    )
    assert fallback_entry["level"] == LogLevel.WARNING
    assert fallback_entry["extra"] == {
        "attempts": metadata["llm"]["fallback_attempts"],
    }


def test_process_pdf_handles_llm_failure(monkeypatch):
    class FailingPipeline:
        def run(self, job_id, input_path, llm_options=None):
            raise LLMProcessingError(
                "provider failed",
                attempts=[{"provider": "primary", "status": "failed", "error": "timeout"}],
            )

    job = build_job()
    session = _patch_infra(monkeypatch, job, FailingPipeline())

    tasks.process_pdf(str(job.id))

    assert job.status == JobStatus.FAILED
    assert job.error_message == "provider failed"
    assert job.result_path is None

    messages = [entry["message"] for entry in session.log_entries]
    assert "LLM processing failed." in messages
    failure_entry = next(
        entry for entry in session.log_entries if entry["message"] == "LLM processing failed."
    )
    assert failure_entry["level"] == LogLevel.ERROR
    assert failure_entry["extra"] == {
        "attempts": [{"provider": "primary", "status": "failed", "error": "timeout"}],
    }


def test_process_pdf_imports_pipeline_without_dependency_error(monkeypatch, tmp_path):
    from src.backend import config as backend_config

    backend_config.get_settings.cache_clear()

    monkeypatch.setenv("PDFCONVERT_STORAGE_PATH", str(tmp_path / "storage"))
    monkeypatch.setenv("PDFCONVERT_RESULTS_PATH", str(tmp_path / "results"))

    converter_stub_calls: list[str] = []
    ocr_stub_calls: list[Path] = []

    class DummyConverter:
        def convert(self, pdf_path):  # pragma: no cover - simple stub
            converter_stub_calls.append(str(pdf_path))
            return ["image-bytes"]

    class DummyOCR:
        def run_on_pdf(self, pdf_path, converter):  # pragma: no cover - simple stub
            ocr_stub_calls.append(Path(pdf_path))
            converter.convert(pdf_path)
            return [SimpleNamespace(text="dummy text", confidence=0.9)]

    converter_stub = DummyConverter()
    ocr_stub = DummyOCR()

    monkeypatch.setattr(tasks.OCRPipeline, "_build_converter", lambda self: converter_stub)
    monkeypatch.setattr(tasks.OCRPipeline, "_build_ocr", lambda self: ocr_stub)
    monkeypatch.setattr(
        tasks.OCRPipeline,
        "_build_postprocessor",
        lambda self, llm_options: (None, [], None, False),
    )
    monkeypatch.setattr(
        tasks.OCRPipeline,
        "_generate_office_artifacts",
        lambda self, job_id, pages: {},
    )

    input_pdf = tmp_path / "input.pdf"
    input_pdf.write_bytes(b"%PDF-1.4 test")

    job = build_job(input_path=str(input_pdf))
    session = _patch_infra(monkeypatch, job)

    try:
        tasks.process_pdf(str(job.id))
    finally:
        backend_config.get_settings.cache_clear()

    assert job.status == JobStatus.COMPLETED
    assert job.error_message is None
    assert job.result_path
    assert Path(job.result_path).exists()
    assert job.result_payload["combined_text"] == "dummy text"

    messages = [entry["message"] for entry in session.log_entries]
    assert "Missing OCR dependency" not in messages

    assert converter_stub_calls == [str(input_pdf)]
    assert ocr_stub_calls == [input_pdf]
