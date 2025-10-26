"""Manual pipeline test that emulates converting scanned PDFs to Word/Excel."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

import matplotlib.pyplot as plt
import pandas as pd
from docx import Document

from backend.config import get_settings
from backend.pipeline import OCRPipeline

SAMPLES_DIR = Path("docs/samples")
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)


def _create_table_pdf(target: Path) -> None:
    headers = [
        "Chỉ tiêu",
        "Năm 2021",
        "Năm 2022",
        "Năm 2023",
        "Năm 2024",
        "Năm 2025",
        "Ghi chú",
    ]
    data = [
        [
            "1 Số lượng tổ chức đảng bộ cấp cơ sở",
            "1.133",
            "1.117",
            "1.095",
            "1.081",
            "1.073",
            "Ổn định",
        ],
        [
            "2 Số lượng đảng viên",
            "149.085",
            "150.666",
            "152.743",
            "154.320",
            "156.100",
            "Tăng đều",
        ],
        [
            "3 Tỷ lệ tổ chức cơ sở đảng hoàn thành tốt nhiệm vụ",
            "89%",
            "90%",
            "91%",
            "92%",
            "93%",
            "Duy trì",
        ],
    ]
    frame = pd.DataFrame(data, columns=headers)
    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    ax.axis("off")
    table = ax.table(cellText=frame.values, colLabels=frame.columns, loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1.2, 2.0)
    fig.tight_layout()
    fig.savefig(target, format="pdf", bbox_inches="tight")
    plt.close(fig)


def _create_report_pdf(target: Path) -> None:
    text = (
        "TỈNH ỦY BẮC NINH\n"
        "ĐẢNG CỘNG SẢN VIỆT NAM\n\n"
        "BÁO CÁO CHÍNH TRỊ\n"
        "CỦA BAN CHẤP HÀNH ĐẢNG BỘ TỈNH NHIỆM KỲ 2020 - 2025\n"
        "TẠI ĐẠI HỘI ĐẠI BIỂU ĐẢNG BỘ TỈNH LẦN THỨ I, NHIỆM KỲ 2025 - 2030\n\n"
        "Xây dựng Đảng bộ tỉnh Bắc Ninh thực sự trong sạch, vững mạnh; phát huy hiệu quả\n"
        "các nguồn lực, xây dựng Bắc Ninh trở thành thành phố trực thuộc Trung ương trước năm 2030.\n\n"
        "Bắc Ninh phấn đấu trở thành một trong những trung tâm công nghiệp công nghệ cao của cả nước."
    )
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    ax.axis("off")
    ax.text(0.02, 0.98, text, fontsize=14, ha="left", va="top", wrap=True)
    fig.tight_layout()
    fig.savefig(target, format="pdf", bbox_inches="tight")
    plt.close(fig)


def _render_docx_preview(docx_path: Path, target: Path) -> None:
    document = Document(docx_path)
    content = "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text)
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    ax.axis("off")
    ax.text(0.02, 0.98, content, fontsize=14, ha="left", va="top", wrap=True)
    fig.tight_layout()
    fig.savefig(target, format="svg", bbox_inches="tight")
    plt.close(fig)


def _render_xlsx_preview(xlsx_path: Path, target: Path) -> None:
    frame = pd.read_excel(xlsx_path)
    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    ax.axis("off")
    table = ax.table(cellText=frame.values, colLabels=frame.columns, loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1.2, 2.0)
    fig.tight_layout()
    fig.savefig(target, format="svg", bbox_inches="tight")
    plt.close(fig)


def run_manual_test() -> Dict[str, Dict[str, Path]]:
    pdfs = {
        "table": SAMPLES_DIR / "table_sample.pdf",
        "report": SAMPLES_DIR / "report_sample.pdf",
    }

    _create_table_pdf(pdfs["table"])
    _create_report_pdf(pdfs["report"])

    storage_dir = SAMPLES_DIR / "storage"
    results_dir = SAMPLES_DIR / "results"
    storage_dir.mkdir(exist_ok=True)
    results_dir.mkdir(exist_ok=True)

    os.environ["PDFCONVERT_STORAGE_PATH"] = str(storage_dir)
    os.environ["PDFCONVERT_RESULTS_PATH"] = str(results_dir)
    os.environ["PDFCONVERT_OCR_BACKEND"] = "tesseract"
    os.environ["PDFCONVERT_OCR_LANGUAGE"] = "vie"
    get_settings.cache_clear()

    pipeline = OCRPipeline()
    outputs: Dict[str, Dict[str, Path]] = {}
    for name, pdf_path in pdfs.items():
        job_id = f"manual-{name}"
        result = pipeline.run(job_id, pdf_path, llm_options={"enable_llm": False})
        outputs[name] = {
            "result_json": result.output_path,
            **result.artifacts,
        }

    for name, artifact_map in outputs.items():
        docx_path = artifact_map.get("docx")
        if docx_path:
            _render_docx_preview(docx_path, SAMPLES_DIR / f"{name}_docx_preview.svg")
        xlsx_path = artifact_map.get("xlsx")
        if xlsx_path:
            _render_xlsx_preview(xlsx_path, SAMPLES_DIR / f"{name}_xlsx_preview.svg")

    return outputs


if __name__ == "__main__":
    results = run_manual_test()
    for name, artifacts in results.items():
        print(f"Sample: {name}")
        for kind, path in artifacts.items():
            print(f"  {kind}: {path}")
