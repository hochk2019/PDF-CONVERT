"""Post-processing utilities including spell-check and dictionary normalisation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional


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
