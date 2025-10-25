"""Utilities for converting PDF pages to OpenCV images with preprocessing."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import numpy as np

try:
    import cv2
except ImportError as exc:  # pragma: no cover - optional dependency guard
    raise ImportError("The OpenCV package (cv2) is required for PDF image preprocessing.") from exc

try:
    import fitz  # PyMuPDF
except ImportError as exc:  # pragma: no cover - optional dependency guard
    raise ImportError("The PyMuPDF package is required for converting PDF pages to images.") from exc


@dataclass(slots=True)
class PDFToImageConfig:
    """Configuration options for :class:`PDFToImageConverter`.

    Attributes
    ----------
    dpi:
        Resolution used when rasterising pages. A value between 200-300 generally
        gives good OCR results without oversized images.
    grayscale:
        Convert the rasterised image to grayscale. Tesseract and PaddleOCR work best
        with grayscale or binary images.
    adaptive_threshold:
        Apply adaptive thresholding to emphasise text. Disabling this keeps the
        grayscale image intact.
    denoise:
        Apply a denoising filter. Helps on scanned documents with speckles.
    deskew:
        Automatically estimate and correct skew using image moments. This is a
        lightweight alternative to Hough-line based approaches and works well for
        small rotations (±10°).
    """

    dpi: int = 300
    grayscale: bool = True
    adaptive_threshold: bool = True
    denoise: bool = True
    deskew: bool = True


class PDFToImageConverter:
    """Convert PDF files to preprocessed OpenCV images."""

    def __init__(self, config: Optional[PDFToImageConfig] = None) -> None:
        self.config = config or PDFToImageConfig()

    def convert(self, pdf_path: Path | str) -> List[np.ndarray]:
        """Convert a PDF into a list of preprocessed images.

        Parameters
        ----------
        pdf_path:
            Path to the PDF document.

        Returns
        -------
        list of numpy.ndarray
            Each array is a preprocessed OpenCV BGR/grayscale image ready for OCR.
        """

        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {path}")

        zoom = self.config.dpi / 72  # 72 dpi is the default resolution in PDFs
        mat = fitz.Matrix(zoom, zoom)

        images: List[np.ndarray] = []
        with fitz.open(path) as doc:
            for page_index, page in enumerate(doc):
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)

                if pix.n == 4:  # Convert RGBA -> RGB
                    img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
                elif pix.n == 1:
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

                preprocessed = self._preprocess(img)
                images.append(preprocessed)

        return images

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """Apply grayscale, denoising, thresholding, and deskewing steps."""

        processed = image.copy()

        if self.config.grayscale:
            processed = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)

        if self.config.denoise:
            if processed.ndim == 2:
                processed = cv2.fastNlMeansDenoising(processed, h=10, templateWindowSize=7, searchWindowSize=21)
            else:
                processed = cv2.fastNlMeansDenoisingColored(processed, None, 10, 10, 7, 21)

        if self.config.adaptive_threshold:
            if processed.ndim == 3:
                processed = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
            processed = cv2.adaptiveThreshold(
                processed,
                maxValue=255,
                adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                thresholdType=cv2.THRESH_BINARY,
                blockSize=35,
                C=11,
            )

        if self.config.deskew:
            processed = self._deskew(processed)

        return processed

    def _deskew(self, image: np.ndarray) -> np.ndarray:
        """Deskew an image using the minimum-area rectangle over non-zero pixels."""

        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        coords = np.column_stack(np.where(gray > 0))
        if coords.size == 0:
            return image

        rect = cv2.minAreaRect(coords[:, ::-1])
        angle = rect[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        if abs(angle) < 0.1:
            return image

        (h, w) = gray.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(gray if image.ndim == 2 else image, matrix, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        return rotated

    def convert_from_bytes(self, data: bytes) -> List[np.ndarray]:
        """Convert a PDF provided as bytes into images."""

        with fitz.open(stream=data, filetype="pdf") as doc:
            zoom = self.config.dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            images: List[np.ndarray] = []
            for page in doc:
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                if pix.n == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
                elif pix.n == 1:
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
                images.append(self._preprocess(img))
        return images

    def batch_convert(self, pdf_paths: Iterable[Path | str]) -> List[List[np.ndarray]]:
        """Batch convert multiple PDFs."""

        return [self.convert(path) for path in pdf_paths]
