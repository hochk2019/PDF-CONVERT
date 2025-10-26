"""Post-processing utilities including spell-check, dictionary normalisation and LLM orchestration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from .llm_postprocessing import LLMPostProcessor, LLMPostProcessorConfig, LayoutMetadata
from .ocr import OCRResult


@dataclass(slots=True)
class SpellCheckConfig:
    """Configuration for :class:`SpellChecker`."""

    language: str = "vi"
    custom_dictionary: Optional[Iterable[str]] = None
    use_languagetool: bool = True
    use_pyvi: bool = True


@dataclass(slots=True)
class SpellCheckResult:
    """Stores the corrected text and tokens."""

    original_text: str
    corrected_text: str
    corrections: List[str] = field(default_factory=list)


class SpellChecker:
    """Perform post-processing on OCR output using LanguageTool and PyVi."""

    def __init__(self, config: Optional[SpellCheckConfig] = None) -> None:
        self.config = config or SpellCheckConfig()
        self._language_tool = None
        self._custom_words = set(self.config.custom_dictionary or [])

    def _load_language_tool(self):
        if not self.config.use_languagetool:
            return None
        if self._language_tool is not None:
            return self._language_tool
        try:
            import language_tool_python
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise ImportError("language_tool_python is required for spell-checking.") from exc

        self._language_tool = language_tool_python.LanguageTool(self.config.language)
        return self._language_tool

    def _tokenize(self, text: str) -> List[str]:
        if not self.config.use_pyvi:
            return text.split()
        try:
            from pyvi import ViTokenizer
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise ImportError("pyvi is required for Vietnamese tokenisation.") from exc

        return ViTokenizer.tokenize(text).split()

    def correct(self, text: str) -> SpellCheckResult:
        tool = self._load_language_tool()
        tokens = self._tokenize(text)

        corrected_tokens = []
        corrections: List[str] = []
        for token in tokens:
            if token in self._custom_words:
                corrected_tokens.append(token)
                continue
            if tool is None:
                corrected_tokens.append(token)
                continue
            matches = tool.check(token)
            if matches:
                suggestion = matches[0].replacements[0] if matches[0].replacements else token
                corrections.append(f"{token} -> {suggestion}")
                corrected_tokens.append(suggestion)
            else:
                corrected_tokens.append(token)

        corrected_text = " ".join(corrected_tokens)
        return SpellCheckResult(original_text=text, corrected_text=corrected_text, corrections=corrections)


def apply_internal_dictionary(text: str, dictionary: dict[str, str]) -> str:
    """Apply a custom mapping dictionary for domain-specific terminology."""

    tokens = text.split()
    mapped_tokens = [dictionary.get(token, token) for token in tokens]
    return " ".join(mapped_tokens)


@dataclass(slots=True)
class PostProcessingConfig:
    """Configuration for :class:`OCRPostProcessor`."""

    spell_check: SpellCheckConfig = field(default_factory=SpellCheckConfig)
    confidence_threshold: float = 0.85
    enable_llm: bool = True
    llm: LLMPostProcessorConfig = field(default_factory=LLMPostProcessorConfig)
    custom_dictionary: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class PostProcessingResult:
    """Aggregated post-processing outputs."""

    original_text: str
    spell_checked_text: str
    llm_text: Optional[str]
    corrections: List[str]
    provider: Optional[str] = None

    @property
    def final_text(self) -> str:
        """Return the most refined text available."""

        return self.llm_text or self.spell_checked_text


class OCRPostProcessor:
    """Coordinate spell-check, dictionary mapping and optional LLM refinement."""

    def __init__(self, config: Optional[PostProcessingConfig] = None) -> None:
        self.config = config or PostProcessingConfig()
        self.spell_checker = SpellChecker(self.config.spell_check)
        self.llm_processor = (
            LLMPostProcessor(self.config.llm) if self.config.enable_llm else None
        )

    def _should_run_llm(self, ocr_result: OCRResult, layout_metadata: LayoutMetadata | None) -> bool:
        if not self.llm_processor:
            return False
        if ocr_result.confidence is None:
            return True
        if ocr_result.confidence < self.config.confidence_threshold:
            return True
        if layout_metadata:
            tables = layout_metadata.get("tables") if isinstance(layout_metadata, dict) else None
            if isinstance(tables, list):
                for table in tables:
                    if isinstance(table, dict) and (
                        table.get("missing_cells") or table.get("gaps") or table.get("needs_completion")
                    ):
                        return True
        return False

    def process_page(
        self,
        ocr_result: OCRResult,
        layout_metadata: LayoutMetadata | None = None,
        *,
        page_hash: str | bytes | None = None,
        llm_model: Optional[str] = None,
    ) -> PostProcessingResult:
        """Apply spell-check, dictionary and optionally LLM to a single OCR page result."""

        spell_result = self.spell_checker.correct(ocr_result.text)
        mapped_text = apply_internal_dictionary(
            spell_result.corrected_text, self.config.custom_dictionary
        )
        llm_text: Optional[str] = None
        provider: Optional[str] = None
        if self._should_run_llm(ocr_result, layout_metadata):
            llm_response = self.llm_processor.enrich(
                OCRResult(text=mapped_text, confidence=ocr_result.confidence, boxes=ocr_result.boxes),
                layout_metadata,
                model=llm_model,
                page_hash=page_hash,
            )
            if llm_response:
                llm_text = llm_response.text
                provider = llm_response.provider
        return PostProcessingResult(
            original_text=ocr_result.text,
            spell_checked_text=mapped_text,
            llm_text=llm_text,
            corrections=spell_result.corrections,
            provider=provider,
        )
