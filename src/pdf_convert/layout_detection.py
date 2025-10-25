"""Layout detection utilities using LayoutParser."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np


@dataclass(slots=True)
class LayoutRegion:
    """Representation of a detected layout block."""

    label: str
    score: float
    bbox: List[float]


@dataclass(slots=True)
class LayoutConfig:
    """Configuration for :class:`LayoutDetector`."""

    model_name: str = "lp://PubLayNet/faster_rcnn_R_50_FPN_3x/config"
    extra_config: Optional[dict] = None


class LayoutDetector:
    """Detect document layout regions using LayoutParser."""

    def __init__(self, config: Optional[LayoutConfig] = None) -> None:
        self.config = config or LayoutConfig()
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return self._model

        try:
            import layoutparser as lp
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise ImportError(
                "layoutparser is required for layout detection. Install layoutparser[layoutmodels] for deep-learning models."
            ) from exc

        extra = self.config.extra_config or {}
        self._model = lp.Detectron2LayoutModel(self.config.model_name, **extra)
        return self._model

    def detect(self, image: np.ndarray) -> List[LayoutRegion]:
        """Run layout detection on an image."""

        model = self._load_model()
        layout = model.detect(image)

        regions = [
            LayoutRegion(label=block.type, score=float(block.score), bbox=list(map(float, block.block.bbox)))
            for block in layout
        ]
        return regions

    def detect_from_pdf(self, pdf_path: Path | str, converter: "PDFToImageConverter") -> List[List[LayoutRegion]]:
        """Run layout detection on every page in a PDF."""

        images = converter.convert(pdf_path)
        return [self.detect(image) for image in images]
