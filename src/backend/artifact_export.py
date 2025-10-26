"""Helpers to build DOCX/XLSX artifacts from OCR output."""
from __future__ import annotations

import io
import re
from typing import Iterable, List


def build_docx(pages: Iterable[str]) -> bytes:
    """Return a DOCX document containing one section per OCR page."""

    try:
        from docx import Document  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency guard
        raise ImportError("python-docx is required to export DOCX artifacts") from exc

    document = Document()
    first = True
    for page in pages:
        text = (page or "").strip()
        if not text:
            continue
        if not first:
            document.add_page_break()
        for paragraph in re.split(r"\n{2,}", text):
            document.add_paragraph(paragraph)
        first = False

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _split_table_line(line: str) -> List[str]:
    columns = [col.strip() for col in re.split(r"\s{2,}", line) if col.strip()]
    if not columns:
        columns = [line.strip()]
    return columns


def build_xlsx(pages: Iterable[str]) -> bytes:
    """Create a simple XLSX sheet by splitting rows on double spaces."""

    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - optional dependency guard
        raise ImportError("pandas is required to export XLSX artifacts") from exc

    rows: List[List[str]] = []
    max_cols = 0
    for page_index, page in enumerate(pages):
        text = (page or "").strip()
        if not text:
            continue
        for line in text.splitlines():
            if not line.strip():
                continue
            cells = _split_table_line(line)
            rows.append(cells)
            max_cols = max(max_cols, len(cells))
        if rows and page_index >= 0:
            rows.append(["--- Page Break ---"])

    if not rows:
        rows.append(["No data"])
        max_cols = max(max_cols, 1)

    # Remove trailing page break if it was the last entry collected
    if rows and rows[-1] == ["--- Page Break ---"]:
        rows.pop()

    normalised = [row + [""] * (max_cols - len(row)) for row in rows]
    columns = [f"Column {idx+1}" for idx in range(max_cols)]
    frame = pd.DataFrame(normalised, columns=columns)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name="OCR")
    return buffer.getvalue()
