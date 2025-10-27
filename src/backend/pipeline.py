"""Glue code between the FastAPI backend and the OCR toolkit."""
from __future__ import annotations

import base64
import binascii
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import get_settings
from .storage import StorageManager


class PipelineDependencyError(RuntimeError):
    """Raised when OCR dependencies are missing at runtime."""


class LLMProcessingError(RuntimeError):
    """Raised when the LLM post-processing stage fails."""

    def __init__(self, message: str, *, attempts: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(message)
        self.attempts: List[Dict[str, Any]] = attempts or []


@dataclass(slots=True)
class PipelineResult:
    text: str
    pages: List[str]
    raw_pages: List[str]
    output_path: Path
    metadata: Dict[str, object]
    artifacts: Dict[str, Path]


class OCRPipeline:
    """Execute the OCR pipeline using components from :mod:`pdf_convert`."""

    def __init__(self) -> None:
        self.storage = StorageManager()
        self._logger = logging.getLogger(__name__)

    def _build_converter(self):
        try:
            from pdf_convert.pdf_to_image import PDFToImageConverter
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise PipelineDependencyError("pdf_to_image dependencies are not installed") from exc
        return PDFToImageConverter()

    def _build_ocr(self):
        try:
            from pdf_convert.ocr import OCRBackend, OCRConfig, OCRProcessor
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise PipelineDependencyError("OCR dependencies are not installed") from exc
        settings = get_settings()
        backend_name = (settings.ocr_backend or "paddle").strip().lower()
        config = OCRConfig(language=settings.ocr_language)
        if backend_name == OCRBackend.TESSERACT.value:
            config.backend = OCRBackend.TESSERACT
        else:
            config.backend = OCRBackend.PADDLE

        try:
            return OCRProcessor(config)
        except ImportError as exc:
            if config.backend != OCRBackend.PADDLE:
                raise PipelineDependencyError("OCR backend dependencies are not installed") from exc
            fallback_config = OCRConfig(
                backend=OCRBackend.TESSERACT,
                language=settings.ocr_language,
                tesseract_psm=6,
                tesseract_oem=3,
            )
            try:
                return OCRProcessor(fallback_config)
            except ImportError as fallback_exc:
                raise PipelineDependencyError(
                    "Neither PaddleOCR nor Tesseract backends are available"
                ) from fallback_exc

    def _build_llm_providers(
        self,
        options: Dict[str, Any],
    ) -> Tuple[List[object], List[str]]:
        try:
            from pdf_convert.llm_postprocessing import OllamaProvider, RESTProvider
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise PipelineDependencyError("LLM post-processing dependencies are not installed") from exc

        settings = get_settings()
        enable_llm = options.get("enable_llm", True)
        if not enable_llm:
            return [], []

        provider_overrides: Dict[str, Any] = options.get("providers", {})
        primary = options.get("provider") or settings.llm_provider
        fallback_names: List[str] = []
        if options.get("fallback_providers"):
            fallback_names.extend(options.get("fallback_providers", []))
        elif options.get("fallback_enabled") is True or (
            options.get("fallback_enabled") is None and settings.llm_fallback_enabled
        ):
            fallback_names.extend(options.get("fallback_providers", []))
            if primary != "ollama":
                fallback_names.append("ollama")

        provider_sequence: List[str] = []
        if primary:
            provider_sequence.append(primary)
        for name in fallback_names:
            if name and name not in provider_sequence:
                provider_sequence.append(name)

        providers: List[object] = []
        resolved_names: List[str] = []
        selected_model = options.get("model") or settings.llm_model
        shared_base_url = options.get("base_url") or settings.llm_base_url
        shared_api_key = options.get("api_key") or settings.llm_api_key

        for name in provider_sequence:
            override = provider_overrides.get(name, {}) if isinstance(provider_overrides, dict) else {}
            if name == "ollama":
                base_url = override.get("base_url") or shared_base_url or OllamaProvider.base_url
                model = override.get("model") or selected_model or OllamaProvider.default_model
                providers.append(OllamaProvider(base_url=base_url, default_model=model))
                resolved_names.append("ollama")
                continue

            base_url = override.get("base_url") or shared_base_url
            if not base_url:
                if name == "openrouter":
                    base_url = "https://openrouter.ai/api/v1/chat/completions"
                elif name == "agentrouter":
                    base_url = "https://api.agentrouter.ai/v1"
            if not base_url:
                continue
            headers = dict(override.get("headers", {}))
            api_key = override.get("api_key") or shared_api_key
            if api_key and "Authorization" not in headers:
                headers["Authorization"] = f"Bearer {api_key}"
            extra_payload = dict(options.get("extra_payload", {}))
            extra_payload.update(override.get("extra_payload", {}))
            model = override.get("model") or selected_model
            providers.append(
                RESTProvider(
                    name=name,
                    base_url=base_url,
                    default_model=model,
                    headers=headers,
                    extra_payload=extra_payload,
                )
            )
            resolved_names.append(name)

        return providers, resolved_names

    def _build_postprocessor(
        self, llm_options: Optional[Dict[str, Any]]
    ) -> Tuple[Optional[object], List[str], Optional[str], bool]:
        try:
            from pdf_convert.postprocessing import OCRPostProcessor, PostProcessingConfig
            from pdf_convert.llm_postprocessing import LLMPostProcessorConfig
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise PipelineDependencyError("Post-processing dependencies are not installed") from exc

        options = llm_options or {}
        settings = get_settings()
        providers, provider_names = self._build_llm_providers(options)
        if not providers:
            return None, provider_names, options.get("model") or settings.llm_model, False

        llm_config = LLMPostProcessorConfig(
            providers=providers,
            cache_enabled=options.get("cache_enabled", True),
        )
        config = PostProcessingConfig(enable_llm=True, llm=llm_config)
        postprocessor = OCRPostProcessor(config)
        fallback_configured = len(provider_names) > 1
        selected_model = options.get("model") or settings.llm_model
        return postprocessor, provider_names, selected_model, fallback_configured

    def _decode_artifact(self, value: Any) -> Optional[bytes]:
        if value is None:
            return None
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):
            try:
                return base64.b64decode(value)
            except binascii.Error:
                return value.encode("utf-8")
        if isinstance(value, dict):
            content = value.get("content")
            encoding = value.get("encoding", "base64")
            if isinstance(content, bytes):
                return content
            if isinstance(content, str):
                if encoding == "base64":
                    try:
                        return base64.b64decode(content)
                    except binascii.Error:
                        return content.encode("utf-8")
                if encoding.lower() in {"utf-8", "text"}:
                    return content.encode("utf-8")
        return None

    def _extract_artifacts(self, raw: Optional[Dict[str, Any]]) -> List[Tuple[str, bytes]]:
        artifacts: List[Tuple[str, bytes]] = []
        if not isinstance(raw, dict):
            return artifacts
        candidates = [raw]
        extra = raw.get("artifacts")
        if isinstance(extra, dict):
            candidates.append(extra)
        for candidate in candidates:
            for key in ("docx", "xlsx"):
                if key in candidate and candidate[key] is not None:
                    data = self._decode_artifact(candidate[key])
                    if data is not None:
                        artifacts.append((key, data))
        return artifacts

    def _generate_office_artifacts(self, job_id: str, pages: List[str]) -> Dict[str, Path]:
        artifacts: Dict[str, Path] = {}
        try:
            from .artifact_export import build_docx, build_xlsx
        except ImportError:
            return artifacts

        try:
            docx_bytes = build_docx(pages)
        except ImportError:
            docx_bytes = None
        except Exception:  # pragma: no cover - diagnostic logging
            self._logger.exception("Failed to build DOCX artifact for job %s", job_id)
            docx_bytes = None
        if docx_bytes:
            artifacts["docx"] = self.storage.write_binary_artifact(job_id, ".docx", docx_bytes)

        try:
            xlsx_bytes = build_xlsx(pages)
        except ImportError:
            xlsx_bytes = None
        except Exception:  # pragma: no cover - diagnostic logging
            self._logger.exception("Failed to build XLSX artifact for job %s", job_id)
            xlsx_bytes = None
        if xlsx_bytes:
            artifacts["xlsx"] = self.storage.write_binary_artifact(job_id, ".xlsx", xlsx_bytes)

        return artifacts

    def run(
        self, job_id: str, input_path: Path, *, llm_options: Optional[Dict[str, Any]] = None
    ) -> PipelineResult:
        """Execute OCR on the provided PDF path."""

        converter = self._build_converter()
        ocr = self._build_ocr()

        results = ocr.run_on_pdf(input_path, converter)
        raw_pages = [res.text for res in results]
        average_confidence = float(
            sum(res.confidence or 0.0 for res in results) / max(len(results), 1)
        )

        postprocessor, provider_chain, llm_model, fallback_configured = self._build_postprocessor(
            llm_options
        )

        corrected_pages: List[str] = []
        page_details: List[Dict[str, Any]] = []
        provider_usage: Dict[int, Optional[str]] = {}
        fallback_attempts: List[Dict[str, Any]] = []
        artifacts: Dict[str, Path] = {}

        for index, result in enumerate(results, start=1):
            final_text = result.text
            spell_checked = result.text
            corrections: List[str] = []
            llm_text: Optional[str] = None
            provider_name: Optional[str] = None
            attempts: List[Dict[str, Any]] = []

            if postprocessor is not None:
                try:
                    post_result = postprocessor.process_page(
                        result,
                        {},
                        page_hash=f"{job_id}:{index}",
                        llm_model=llm_model,
                    )
                except Exception as exc:  # pragma: no cover - defensive guard
                    attempts = getattr(
                        getattr(postprocessor, "llm_processor", None), "last_attempts", []
                    )
                    raise LLMProcessingError(
                        "LLM post-processing failed",
                        attempts=[dict(item) for item in attempts],
                    ) from exc

                spell_checked = post_result.spell_checked_text
                corrections = post_result.corrections
                llm_text = post_result.llm_text
                provider_name = post_result.provider
                attempts = [dict(item) for item in post_result.attempts]
                final_text = post_result.final_text
                if post_result.llm_raw:
                    for kind, data in self._extract_artifacts(post_result.llm_raw):
                        if kind not in artifacts:
                            suffix = f".{kind}"
                            artifacts[kind] = self.storage.write_binary_artifact(
                                job_id, suffix, data
                            )
            corrected_pages.append(final_text)
            provider_usage[index] = provider_name
            page_info: Dict[str, Any] = {
                "page": index,
                "raw_text": result.text,
                "spell_checked_text": spell_checked,
                "llm_text": llm_text,
                "final_text": final_text,
                "confidence": result.confidence,
                "provider": provider_name,
                "corrections": corrections,
                "attempts": attempts,
            }
            page_details.append(page_info)
            if attempts:
                fallback_attempts.append({"page": index, "attempts": attempts})

        combined_corrected = "\n\n".join(page.strip() for page in corrected_pages if page)
        combined_raw = "\n\n".join(page.strip() for page in raw_pages if page)

        fallback_from_attempts = any(
            any(attempt.get("status") == "failed" for attempt in record.get("attempts", []))
            for record in fallback_attempts
        )
        fallback_from_provider = False
        if provider_chain:
            primary = provider_chain[0]
            for used in provider_usage.values():
                if used and used != primary:
                    fallback_from_provider = True
                    break

        llm_metadata = {
            "enabled": postprocessor is not None,
            "providers": provider_chain,
            "provider_usage": {str(k): v for k, v in provider_usage.items() if v},
            "model": llm_model,
            "fallback_configured": fallback_configured,
            "fallback_used": fallback_from_attempts or fallback_from_provider,
            "fallback_attempts": fallback_attempts,
            "artifacts": {kind: str(path) for kind, path in artifacts.items()},
        }

        payload: Dict[str, Any] = {
            "raw_pages": raw_pages,
            "pages": corrected_pages,
            "raw_combined_text": combined_raw,
            "combined_text": combined_corrected,
            "average_confidence": average_confidence,
            "page_details": page_details,
            "llm": llm_metadata,
        }

        office_artifacts = self._generate_office_artifacts(job_id, corrected_pages)
        for kind, path in office_artifacts.items():
            artifacts.setdefault(kind, path)

        artifact_metadata = {kind: str(path) for kind, path in artifacts.items()}
        llm_metadata["artifacts"] = artifact_metadata
        payload["llm"] = llm_metadata
        payload["artifacts"] = artifact_metadata

        output_path = self.storage.write_result(
            job_id, json.dumps(payload, ensure_ascii=False, indent=2)
        )

        return PipelineResult(
            text=combined_corrected,
            pages=corrected_pages,
            raw_pages=raw_pages,
            output_path=output_path,
            metadata=payload,
            artifacts=artifacts,
        )
