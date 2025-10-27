from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _install_cv2_stub(monkeypatch) -> None:
    if "cv2" not in sys.modules:
        monkeypatch.setitem(sys.modules, "cv2", types.ModuleType("cv2"))
    if "fitz" not in sys.modules:
        monkeypatch.setitem(sys.modules, "fitz", types.ModuleType("fitz"))


def _install_paddle_stub(monkeypatch, captured_kwargs: dict[str, object]) -> None:
    module = types.ModuleType("paddleocr")

    class DummyPaddleOCR:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

        def ocr(self, *args, **kwargs):  # pragma: no cover - interface compatibility
            raise NotImplementedError

    module.PaddleOCR = DummyPaddleOCR  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "paddleocr", module)


def _install_paddle_processing_stub(
    monkeypatch,
    captured_kwargs: dict[str, object],
    call_details: dict[str, object],
    *,
    include_cls: bool,
) -> None:
    module = types.ModuleType("paddleocr")

    line = (
        [
            [0, 0],
            [1, 0],
            [1, 1],
            [0, 1],
        ],
        ("hello", 0.9),
    )

    class DummyPaddleOCR:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

        if include_cls:

            def ocr(self, image, cls=False):  # type: ignore[override]
                call_details["kwargs"] = {"cls": cls}
                call_details["args"] = (image,)
                return [[line]]

        else:

            def ocr(self, image):  # type: ignore[override]
                call_details["kwargs"] = {}
                call_details["args"] = (image,)
                return [[line]]

    module.PaddleOCR = DummyPaddleOCR  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "paddleocr", module)


def test_paddle_language_alias_applied(monkeypatch):
    captured_kwargs: dict[str, object] = {}
    _install_paddle_stub(monkeypatch, captured_kwargs)
    _install_cv2_stub(monkeypatch)

    from src.pdf_convert.ocr import OCRConfig, OCRProcessor

    processor = OCRProcessor(OCRConfig(language="vie"))
    engine = processor._load_paddle()

    assert captured_kwargs["lang"] == "vi"
    assert engine is processor._paddle_engine


def test_pipeline_builds_with_vie_language(monkeypatch):
    captured_kwargs: dict[str, object] = {}
    _install_paddle_stub(monkeypatch, captured_kwargs)
    monkeypatch.setenv("PDFCONVERT_OCR_LANGUAGE", "vie")
    _install_cv2_stub(monkeypatch)

    from src.backend.config import get_settings

    get_settings.cache_clear()

    from src.backend.pipeline import OCRPipeline

    pipeline = OCRPipeline()
    processor = pipeline._build_ocr()
    processor._load_paddle()

    assert captured_kwargs["lang"] == "vi"

    get_settings.cache_clear()


def test_paddle_cls_argument_forwarded_when_supported(monkeypatch):
    captured_kwargs: dict[str, object] = {}
    call_details: dict[str, object] = {}
    _install_paddle_processing_stub(
        monkeypatch, captured_kwargs, call_details, include_cls=True
    )

    from src.pdf_convert.ocr import OCRConfig, OCRProcessor

    processor = OCRProcessor(OCRConfig(enable_angle_class=True))
    image = np.zeros((2, 2, 3), dtype=np.uint8)

    result = processor._run_paddle(image)

    assert call_details["kwargs"] == {"cls": True}
    assert result.text == "hello"
    assert result.confidence == 0.9
    assert result.boxes == [[0, 0, 1, 0, 1, 1, 0, 1]]


def test_paddle_cls_argument_skipped_when_unsupported(monkeypatch):
    captured_kwargs: dict[str, object] = {}
    call_details: dict[str, object] = {}
    _install_paddle_processing_stub(
        monkeypatch, captured_kwargs, call_details, include_cls=False
    )

    from src.pdf_convert.ocr import OCRConfig, OCRProcessor

    processor = OCRProcessor(OCRConfig(enable_angle_class=True))
    image = np.zeros((2, 2, 3), dtype=np.uint8)

    result = processor._run_paddle(image)

    assert call_details["kwargs"] == {}
    assert result.text == "hello"
    assert result.confidence == 0.9
    assert result.boxes == [[0, 0, 1, 0, 1, 1, 0, 1]]
