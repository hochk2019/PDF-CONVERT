import pandas as pd
from docx import Document

from backend.config import get_settings
from backend.pipeline import OCRPipeline
from backend.artifact_export import build_docx, build_xlsx


def test_build_docx_roundtrip(tmp_path):
    pages = ["Hello World", "Second page with\nmultiple paragraphs"]
    data = build_docx(pages)
    assert data[:2] == b"PK"

    target = tmp_path / "result.docx"
    target.write_bytes(data)

    document = Document(target)
    texts = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
    assert "Hello World" in texts
    assert any("Second page" in text for text in texts)


def test_build_xlsx_roundtrip(tmp_path):
    pages = ["A  B  C\n1  2  3", "Only text"]
    data = build_xlsx(pages)

    target = tmp_path / "result.xlsx"
    target.write_bytes(data)

    frame = pd.read_excel(target)
    assert list(frame.columns[:3]) == ["Column 1", "Column 2", "Column 3"]
    assert frame.iloc[0, 0] == "A"
    assert frame.iloc[1, 0] == "1"


def test_pipeline_generates_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("PDFCONVERT_RESULTS_PATH", str(tmp_path / "results"))
    monkeypatch.setenv("PDFCONVERT_STORAGE_PATH", str(tmp_path / "storage"))
    get_settings.cache_clear()

    pipeline = OCRPipeline()
    artifacts = pipeline._generate_office_artifacts("job-123", ["Col1  Col2", "Row2  Value2"])

    assert "docx" in artifacts
    assert "xlsx" in artifacts
    for path in artifacts.values():
        assert path.exists()

    get_settings.cache_clear()
