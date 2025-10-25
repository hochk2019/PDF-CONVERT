# PDF-CONVERT

Bộ tài liệu định hướng cho dự án xây dựng nền tảng xử lý PDF sử dụng OCR.

## Thư viện Python

Toàn bộ các module Python phục vụ pipeline chuyển PDF sang văn bản nằm trong thư mục `src/pdf_convert`:

- `pdf_to_image.py`: Chuyển đổi PDF sang ảnh OpenCV với các bước tiền xử lý (grayscale, threshold, denoise, deskew).
- `ocr.py`: Tích hợp PaddleOCR và Tesseract, cung cấp cấu hình chung và trả về kết quả OCR tiêu chuẩn.
- `layout_detection.py`: Phát hiện layout tài liệu bằng LayoutParser (Detectron2 backend).
- `table_recognition.py`: Khung nhận dạng bảng với mô hình TableNet hoặc DeepDeSRT và hậu xử lý cấu trúc.
- `vietnamese_finetune.py`: Công cụ chuẩn bị dữ liệu và sinh cấu hình fine-tune OCR tiếng Việt.
- `postprocessing.py`: Hậu xử lý văn bản (spell-check bằng LanguageTool/PyVi, áp dụng từ điển nội bộ).

Để sử dụng, cài đặt các phụ thuộc cần thiết (PyMuPDF, OpenCV, PaddleOCR, pytesseract, layoutparser, torch, LanguageTool, pyvi...). Ví dụ:

```bash
pip install opencv-python pymupdf paddleocr pytesseract layoutparser torch torchvision language-tool-python pyvi
```

## Tài liệu tham khảo

- `docs/sample_dataset.md`: Bộ sưu tập PDF mẫu phân loại theo phòng ban và độ khó.
- `docs/ocr_benchmark.md`: Kết quả benchmark Tesseract vs PaddleOCR trên tập mẫu.
- `docs/architecture_decision.md`: Phân tích và lựa chọn kiến trúc FastAPI + Node.js Gateway.
- `docs/diagrams.md`: ERD và lưu đồ xử lý PDF (Mermaid).
- `docs/ui_ux_outline.md`: Phác thảo UI/UX và kế hoạch thiết kế Figma.


## Backend service

Thư mục `src/backend` chứa FastAPI service, Celery worker và cấu hình lưu trữ.

### Chạy API cục bộ

```bash
uvicorn backend.main:app --reload --port 8000
```

### Chạy worker Celery

```bash
celery -A backend.celery_app.celery_app worker -Q pdf_convert.jobs --loglevel=info
```

Service cần PostgreSQL và Redis (cấu hình qua biến môi trường `PDFCONVERT_DATABASE_URL`, `PDFCONVERT_REDIS_URL`).

Đặt biến môi trường `PYTHONPATH=src` khi chạy cục bộ để Python nhận diện module backend.
