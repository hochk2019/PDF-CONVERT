"""Glue code between the FastAPI backend and the OCR toolkit."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from .storage import StorageManager


class PipelineDependencyError(RuntimeError):
    """Raised when OCR dependencies are missing at runtime."""


@dataclass(slots=True)
class PipelineResult:
    text: str
    pages: List[str]
    output_path: Path
    metadata: Dict[str, object]


class OCRPipeline:
    """Execute the OCR pipeline using components from :mod:`pdf_convert`."""

    def __init__(self) -> None:
        self.storage = StorageManager()

    def _build_converter(self):
        try:
            from pdf_convert.pdf_to_image import PDFToImageConverter
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise PipelineDependencyError("pdf_to_image dependencies are not installed") from exc
        return PDFToImageConverter()

    def _build_ocr(self):
        try:
            from pdf_convert.ocr import OCRConfig, OCRProcessor
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise PipelineDependencyError("OCR dependencies are not installed") from exc
        return OCRProcessor(OCRConfig())

    def run(self, job_id: str, input_path: Path) -> PipelineResult:
        """Execute OCR on the provided PDF path."""

        converter = self._build_converter()
        ocr = self._build_ocr()

        results = ocr.run_on_pdf(input_path, converter)
        pages = [res.text for res in results]
        combined = "\n\n".join(page.strip() for page in pages if page)
        payload = {
            "pages": pages,
            "combined_text": combined,
            "average_confidence": float(
                sum(res.confidence or 0.0 for res in results) / max(len(results), 1)
            ),
        }

        output_path = self.storage.write_result(job_id, json.dumps(payload, ensure_ascii=False, indent=2))
        return PipelineResult(text=combined, pages=pages, output_path=output_path, metadata=payload)
