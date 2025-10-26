"""File storage helpers for input and output artifacts."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import BinaryIO

from .config import get_settings


class StorageManager:
    """Persist uploaded PDFs and generated outputs on local disk."""

    def __init__(self) -> None:
        settings = get_settings()
        self._input_dir = settings.storage_path
        self._result_dir = settings.results_path

    def input_path_for(self, job_id: str) -> Path:
        path = self._input_dir / job_id
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def result_path_for(self, job_id: str) -> Path:
        path = self._result_dir / f"{job_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def artifact_path_for(self, job_id: str, suffix: str) -> Path:
        suffix = suffix if suffix.startswith(".") else f".{suffix}"
        path = self._result_dir / f"{job_id}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def save_upload(self, job_id: str, filename: str, data: BinaryIO) -> Path:
        target_dir = self._input_dir / job_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename
        with target.open("wb") as fh:
            shutil.copyfileobj(data, fh)
        return target

    def write_result(self, job_id: str, content: str) -> Path:
        target = self.result_path_for(job_id)
        target.write_text(content, encoding="utf-8")
        return target

    def write_binary_artifact(self, job_id: str, suffix: str, data: bytes) -> Path:
        target = self.artifact_path_for(job_id, suffix)
        target.write_bytes(data)
        return target

    def open_result(self, path: str | Path) -> Path:
        return Path(path)
