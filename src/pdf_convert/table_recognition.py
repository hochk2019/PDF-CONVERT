"""Table detection and structure recognition utilities."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

import numpy as np


class TableModel(str, Enum):
    """Supported table recognition models."""

    TABLENET = "tablenet"
    DEEP_DESRT = "deep_desrt"


@dataclass(slots=True)
class TableDetection:
    """Stores table bounding box data."""

    bbox: List[int]
    confidence: float


@dataclass(slots=True)
class TableStructure:
    """Stores recognised table structure information."""

    rows: int
    cols: int
    cells: List[List[str]]


@dataclass(slots=True)
class TableRecognitionConfig:
    """Configuration for :class:`TableRecognizer`."""

    model: TableModel = TableModel.TABLENET
    confidence_threshold: float = 0.5
    model_weights: Optional[Path | str] = None


class TableRecognizer:
    """Detect and extract tables using deep-learning models."""

    def __init__(self, config: Optional[TableRecognitionConfig] = None) -> None:
        self.config = config or TableRecognitionConfig()
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return self._model

        try:
            import torch
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise ImportError("PyTorch is required for table recognition models.") from exc

        if self.config.model == TableModel.TABLENET:
            self._model = self._load_tablenet(torch)
        elif self.config.model == TableModel.DEEP_DESRT:
            self._model = self._load_deep_desrt(torch)
        else:  # pragma: no cover - defensive branch
            raise ValueError(f"Unsupported model: {self.config.model}")
        return self._model

    def _load_tablenet(self, torch):
        try:
            from torchvision import transforms
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise ImportError("torchvision is required to run TableNet.") from exc

        class _TableNetWrapper(torch.nn.Module):
            def __init__(self, weights_path: Optional[Path | str]):
                super().__init__()
                from tablenet import TableNet  # type: ignore

                self.model = TableNet(pretrained=True)
                if weights_path:
                    state = torch.load(weights_path, map_location="cpu")
                    self.model.load_state_dict(state)
                self.model.eval()
                self.transform = transforms.Compose(
                    [
                        transforms.ToPILImage(),
                        transforms.Resize((512, 512)),
                        transforms.ToTensor(),
                    ]
                )

            def forward(self, image: np.ndarray):
                tensor = self.transform(image)
                with torch.no_grad():
                    table_mask, column_mask = self.model(tensor.unsqueeze(0))
                return table_mask.sigmoid()[0, 0].numpy(), column_mask.sigmoid()[0, 0].numpy()

        return _TableNetWrapper(self.config.model_weights)

    def _load_deep_desrt(self, torch):
        try:
            from deep_desrt.model import DeepDeSRT  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise ImportError(
                "deep_desrt is not installed. Install it or provide your own implementation for DeepDeSRT."
            ) from exc

        class _DeepDeSRTWrapper(torch.nn.Module):
            def __init__(self, weights_path: Optional[Path | str]):
                super().__init__()
                self.model = DeepDeSRT()
                if weights_path:
                    state = torch.load(weights_path, map_location="cpu")
                    self.model.load_state_dict(state)
                self.model.eval()

            def forward(self, image: np.ndarray):
                tensor = torch.from_numpy(image).permute(2, 0, 1).unsqueeze(0).float() / 255.0
                with torch.no_grad():
                    preds = self.model(tensor)
                return preds

        return _DeepDeSRTWrapper(self.config.model_weights)

    def detect(self, image: np.ndarray) -> List[TableDetection]:
        """Run table detection on an image."""

        model = self._load_model()
        outputs = model(image)

        detections: List[TableDetection] = []
        if isinstance(outputs, tuple):
            table_mask = outputs[0]
            detections = self._mask_to_detections(table_mask)
        else:
            detections = self._raw_predictions_to_detections(outputs)
        return [det for det in detections if det.confidence >= self.config.confidence_threshold]

    def extract_structure(self, image: np.ndarray) -> TableStructure:
        """Placeholder structure extraction using connected components on the table mask."""

        detections = self.detect(image)
        if not detections:
            return TableStructure(rows=0, cols=0, cells=[])

        try:
            import cv2
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise ImportError("OpenCV is required for table structure post-processing.") from exc

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((1, 30), np.uint8))
        vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((30, 1), np.uint8))
        table_mask = cv2.add(horizontal, vertical)

        contours, _ = cv2.findContours(table_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        cells: List[List[str]] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w * h < 100:  # skip small noise
                continue
            cells.append([str(x), str(y), str(x + w), str(y + h)])

        rows = max(1, len(cells))
        cols = max(1, len(cells[0])) if cells else 0
        return TableStructure(rows=rows, cols=cols, cells=cells)

    def detect_from_pdf(self, pdf_path: Path | str, converter: "PDFToImageConverter") -> List[List[TableDetection]]:
        """Run table detection on each page of a PDF."""

        images = converter.convert(pdf_path)
        return [self.detect(image) for image in images]

    def _mask_to_detections(self, mask: np.ndarray) -> List[TableDetection]:
        import cv2

        mask_uint8 = (mask * 255).astype("uint8")
        contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: List[TableDetection] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            confidence = min(1.0, area / (mask.shape[0] * mask.shape[1]))
            detections.append(TableDetection(bbox=[x, y, x + w, y + h], confidence=confidence))
        return detections

    def _raw_predictions_to_detections(self, preds) -> List[TableDetection]:
        detections: List[TableDetection] = []
        if isinstance(preds, list):
            for pred in preds:
                boxes = pred.get("boxes", [])
                scores = pred.get("scores", [])
                for bbox, score in zip(boxes, scores):
                    detections.append(TableDetection(bbox=[int(v) for v in bbox], confidence=float(score)))
        return detections
