"""OCR integration utilities supporting PaddleOCR and Tesseract.

The PaddleOCR SDK occasionally changes the signature of ``engine.ocr``/
``engine.predict`` regarding the ``cls`` keyword.  We inspect the callable at
runtime and only forward ``cls`` when it is supported so that both older and
newer versions stay compatible without user intervention.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


LANGUAGE_ALIASES: Dict[str, str] = {
    "vie": "vi",
    "eng": "en",
}


class OCRBackend(str, Enum):
    """Supported OCR engines."""

    PADDLE = "paddle"
    TESSERACT = "tesseract"


@dataclass(slots=True)
class OCRResult:
    """Container for OCR output."""

    text: str
    confidence: float | None = None
    boxes: Optional[List[List[int]]] = None
    raw_output: Optional[Any] = None


@dataclass(slots=True)
class OCRConfig:
    """Configuration for OCR processing."""

    backend: OCRBackend = OCRBackend.PADDLE
    language: str = "vi"  # default to Vietnamese
    enable_angle_class: bool = False  # PaddleOCR specific
    tesseract_psm: int = 6
    tesseract_oem: int = 3
    paddle_kwargs: Optional[Dict[str, Any]] = None


class OCRProcessor:
    """Wrap PaddleOCR and Tesseract engines behind a consistent interface."""

    def __init__(self, config: Optional[OCRConfig] = None) -> None:
        self.config = config or OCRConfig()
        self._paddle_engine = None

    @staticmethod
    def _supports_keyword(func: Any, keyword: str) -> bool:
        """Return ``True`` when ``func`` accepts ``keyword`` as a kwarg."""

        try:
            signature = inspect.signature(func)
        except (TypeError, ValueError):  # pragma: no cover - C extensions etc.
            return False

        if keyword in signature.parameters:
            param = signature.parameters[keyword]
            return param.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )

        return any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in signature.parameters.values()
        )

    def _invoke_paddle(self, engine: Any, image: np.ndarray) -> Any:
        """Call the Paddle engine while handling ``cls`` compatibility."""

        cls_value = self.config.enable_angle_class
        for method_name in ("ocr", "predict"):
            method = getattr(engine, method_name, None)
            if method is None:
                continue
            if self._supports_keyword(method, "cls"):
                return method(image, cls=cls_value)
            return method(image)

        raise AttributeError("PaddleOCR engine exposes neither 'ocr' nor 'predict'.")

    def _load_paddle(self) -> Any:
        if self._paddle_engine is not None:
            return self._paddle_engine
        try:
            from paddleocr import PaddleOCR  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise ImportError(
                "PaddleOCR is not installed. Install paddleocr>=2.6.0 to use the Paddle backend."
            ) from exc

        normalized_language = self.config.language.strip()
        language_key = normalized_language.lower()
        resolved_language = LANGUAGE_ALIASES.get(language_key, normalized_language)
        kwargs = {
            "lang": resolved_language,
            "use_angle_cls": self.config.enable_angle_class,
        }
        if self.config.paddle_kwargs:
            kwargs.update(self.config.paddle_kwargs)

        self._paddle_engine = PaddleOCR(**kwargs)
        return self._paddle_engine

    def _run_paddle(self, image: np.ndarray) -> OCRResult:
        engine = self._load_paddle()
        result = self._invoke_paddle(engine, image)

        text_parts: List[str] = []
        confidences: List[float] = []
        boxes: List[List[int]] = []
        for line in result[0]:
            boxes.append([int(num) for point in line[0] for num in point])
            text_parts.append(line[1][0])
            confidences.append(float(line[1][1]))

        text = "\n".join(text_parts)
        confidence = float(np.mean(confidences)) if confidences else None
        return OCRResult(text=text, confidence=confidence, boxes=boxes, raw_output=result)

    def _run_tesseract(self, image: np.ndarray) -> OCRResult:
        try:
            import pytesseract
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise ImportError(
                "pytesseract is required to run the Tesseract backend. Install pytesseract and ensure tesseract-ocr is available."
            ) from exc

        if image.ndim == 2:
            processed = image
        else:
            import cv2

            processed = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        config = f"--oem {self.config.tesseract_oem} --psm {self.config.tesseract_psm} -l {self.config.language}"
        text = pytesseract.image_to_string(processed, config=config)
        data = pytesseract.image_to_data(processed, config=config, output_type=pytesseract.Output.DICT)

        confidences = [float(conf) for conf in data.get("conf", []) if conf not in ("-1", None)]
        confidence = float(np.mean(confidences)) if confidences else None
        boxes = []
        for idx in range(len(data.get("level", []))):
            left = data["left"][idx]
            top = data["top"][idx]
            width = data["width"][idx]
            height = data["height"][idx]
            boxes.append([left, top, left + width, top + height])

        return OCRResult(text=text, confidence=confidence, boxes=boxes, raw_output=data)

    def run(self, image: np.ndarray) -> OCRResult:
        """Run OCR using the configured backend."""

        if self.config.backend == OCRBackend.PADDLE:
            return self._run_paddle(image)
        if self.config.backend == OCRBackend.TESSERACT:
            return self._run_tesseract(image)
        raise ValueError(f"Unsupported backend: {self.config.backend}")

    def run_on_images(self, images: List[np.ndarray]) -> List[OCRResult]:
        """Perform OCR on multiple images."""

        return [self.run(img) for img in images]

    def run_on_pdf(self, pdf_path: Path | str, converter: "PDFToImageConverter") -> List[OCRResult]:
        """Helper to run OCR directly on a PDF by delegating to :class:`PDFToImageConverter`."""

        images = converter.convert(pdf_path)
        return self.run_on_images(images)
