"""LLM based post-processing helpers for OCR output."""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Protocol

import httpx

logger = logging.getLogger(__name__)


LayoutMetadata = Dict[str, Any]


@dataclass(slots=True)
class LLMRequest:
    """Container for LLM prompt generation."""

    prompt: str
    model: Optional[str] = None
    metadata: LayoutMetadata = field(default_factory=dict)


@dataclass(slots=True)
class LLMResponse:
    """Normalised response returned by the LLM providers."""

    text: str
    raw: Dict[str, Any] | None = None
    provider: str | None = None


class LLMProvider(Protocol):
    """Protocol implemented by provider specific adapters."""

    name: str

    def generate(self, request: LLMRequest) -> LLMResponse:  # pragma: no cover - interface definition
        """Generate text for the supplied prompt."""


@dataclass(slots=True)
class OllamaProvider:
    """Adapter for the local Ollama REST API."""

    base_url: str = "http://localhost:11434/api/generate"
    default_model: str = "llama3"
    timeout: float = 30.0
    client: httpx.Client | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = httpx.Client(timeout=self.timeout)

    @property
    def name(self) -> str:  # pragma: no cover - trivial property
        return "ollama"

    def generate(self, request: LLMRequest) -> LLMResponse:
        payload = {
            "model": request.model or self.default_model,
            "prompt": request.prompt,
            "stream": False,
        }
        logger.debug("Calling Ollama with payload: %s", payload)
        response = self.client.post(self.base_url, json=payload)
        response.raise_for_status()
        data = response.json()
        text = data.get("response") or data.get("text") or ""
        return LLMResponse(text=text, raw=data, provider=self.name)


@dataclass(slots=True)
class RESTProvider:
    """Generic REST adapter for services such as OpenRouter or AgentRouter."""

    name: str
    base_url: str
    default_model: Optional[str] = None
    timeout: float = 30.0
    headers: Dict[str, str] = field(default_factory=dict)
    extra_payload: Dict[str, Any] = field(default_factory=dict)
    client: httpx.Client | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = httpx.Client(timeout=self.timeout)

    def generate(self, request: LLMRequest) -> LLMResponse:
        payload: Dict[str, Any] = {"prompt": request.prompt}
        if request.model or self.default_model:
            payload["model"] = request.model or self.default_model
        if self.extra_payload:
            payload.update(self.extra_payload)
        logger.debug("Calling %s provider with payload: %s", self.name, payload)
        response = self.client.post(self.base_url, json=payload, headers=self.headers or None)
        response.raise_for_status()
        data = response.json()
        text = (
            data.get("response")
            or data.get("text")
            or data.get("choices", [{}])[0].get("message", {}).get("content", "")
        )
        return LLMResponse(text=text, raw=data, provider=self.name)


@dataclass(slots=True)
class LLMPostProcessorConfig:
    """Configuration for :class:`LLMPostProcessor`."""

    providers: Iterable[LLMProvider] | None = None
    cache_enabled: bool = True


class LLMPostProcessor:
    """Handles prompt generation, caching and provider fallback for LLM calls."""

    def __init__(self, config: Optional[LLMPostProcessorConfig] = None) -> None:
        self.config = config or LLMPostProcessorConfig()
        if self.config.providers is None:
            self.providers: List[LLMProvider] = [OllamaProvider()]
        else:
            self.providers = list(self.config.providers)
        self._cache: Dict[str, LLMResponse] = {}

    def _prompt_from_context(
        self, ocr_result: "OCRResult", layout_metadata: LayoutMetadata | None
    ) -> str:
        metadata_str = json.dumps(layout_metadata or {}, ensure_ascii=False, sort_keys=True)
        prompt = (
            "Bạn là một trợ lý giúp chuẩn hóa kết quả OCR. "
            "Hãy cải thiện chính tả và điền vào các chỗ còn thiếu nếu có thể.\n"
            f"Nội dung OCR:\n{ocr_result.text}\n"
            f"Metadata bố cục:\n{metadata_str}\n"
        )
        logger.debug("Generated prompt: %s", prompt)
        return prompt

    def _cache_key(self, page_hash: str | bytes | None, model: Optional[str]) -> str:
        key_material = page_hash if page_hash is not None else ""
        if isinstance(key_material, str):
            key_material = key_material.encode("utf-8")
        digest = hashlib.sha256(key_material or b"no-hash").hexdigest()
        model_suffix = model or "default"
        return f"{digest}:{model_suffix}"

    def enrich(
        self,
        ocr_result: "OCRResult",
        layout_metadata: LayoutMetadata | None = None,
        *,
        model: Optional[str] = None,
        page_hash: str | bytes | None = None,
    ) -> Optional[LLMResponse]:
        prompt = self._prompt_from_context(ocr_result, layout_metadata)
        cache_key = self._cache_key(page_hash or prompt, model)
        if self.config.cache_enabled and cache_key in self._cache:
            logger.debug("Returning cached LLM response for key %s", cache_key)
            return self._cache[cache_key]

        request = LLMRequest(prompt=prompt, model=model, metadata=layout_metadata or {})
        last_error: Exception | None = None
        for provider in self.providers:
            try:
                logger.debug("Invoking provider %s", getattr(provider, "name", provider))
                response = provider.generate(request)
                if not response.text.strip():
                    logger.warning("Provider %s returned empty text", provider.name)
                    continue
                if self.config.cache_enabled:
                    self._cache[cache_key] = response
                return response
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Provider %s failed: %s", getattr(provider, "name", provider), exc)
                last_error = exc
                continue

        if last_error:
            raise last_error
        return None


# Import placed at the end to avoid circular dependency at type-check time.
from .ocr import OCRResult  # noqa: E402  pylint: disable=wrong-import-position

