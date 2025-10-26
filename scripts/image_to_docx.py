"""Utility script to OCR an image and export the result as a DOCX file.

This helper keeps the implementation minimal so it can run inside the
evaluation container without requiring the full backend stack.  It relies on
Tesseract for OCR and ``python-docx`` for writing the DOCX document.
"""

from __future__ import annotations

import argparse
import base64
import tempfile
from pathlib import Path

from PIL import Image
import pytesseract
from docx import Document


def ocr_image_to_docx(image_path: Path, output_path: Path, lang: str = "vie+eng") -> None:
    """Run OCR on *image_path* and save a DOCX with the extracted text.

    Parameters
    ----------
    image_path:
        Path to the input image. Any format supported by Pillow is accepted.
    output_path:
        Destination path for the generated DOCX document.
    lang:
        Language hint for Tesseract. ``vie+eng`` works well for Vietnamese
        documents that might include English words.
    """

    image = Image.open(image_path)

    # Tesseract works best with grayscale input. ``convert("L")`` keeps the
    # script lightweight without introducing additional dependencies.
    grayscale = image.convert("L")

    text = pytesseract.image_to_string(grayscale, lang=lang)

    document = Document()
    for paragraph in text.strip().splitlines():
        document.add_paragraph(paragraph)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.suffix == ".b64":
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            document.save(tmp_path)
            data = tmp_path.read_bytes()
            output_path.write_text(base64.b64encode(data).decode("ascii"))
        finally:
            tmp_path.unlink(missing_ok=True)
    else:
        document.save(output_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Input image to OCR")
    parser.add_argument("output", type=Path, help="Destination DOCX path")
    parser.add_argument(
        "--lang",
        default="vie+eng",
        help="Language codes for Tesseract (default: vie+eng)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    ocr_image_to_docx(args.image, args.output, lang=args.lang)


if __name__ == "__main__":
    main()
