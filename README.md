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

### Cài đặt phụ thuộc backend

Service hiện dùng JWT authentication, cần bổ sung các thư viện sau (ngoài FastAPI, SQLAlchemy, Celery):

```bash
pip install "passlib[bcrypt]" python-jose[cryptography] "httpx>=0.25"
```

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

### Cấu hình LLM hậu xử lý

Các tùy chọn LLM được lấy từ biến môi trường (tự động đọc với tiền tố `PDFCONVERT_`). Các khóa được hỗ trợ:

- `PDFCONVERT_LLM_PROVIDER`: định danh nhà cung cấp chính (`ollama`, `openrouter`, `agentrouter`...).
- `PDFCONVERT_LLM_MODEL`: tên mô hình mặc định gửi lên nhà cung cấp.
- `PDFCONVERT_LLM_BASE_URL`: URL API tùy chỉnh (ví dụ `http://localhost:11434/api/generate` cho Ollama).
- `PDFCONVERT_LLM_API_KEY`: khóa truy cập cho các dịch vụ SaaS (không trả về trong API).
- `PDFCONVERT_LLM_FALLBACK_ENABLED`: `true/false` để bật/tắt fallback qua nhiều nhà cung cấp.

Ví dụ cấu hình `.env`:

```env
# Ollama cục bộ
PDFCONVERT_LLM_PROVIDER=ollama
PDFCONVERT_LLM_MODEL=llama3
PDFCONVERT_LLM_BASE_URL=http://localhost:11434/api/generate
PDFCONVERT_LLM_FALLBACK_ENABLED=false

# OpenRouter
# PDFCONVERT_LLM_PROVIDER=openrouter
# PDFCONVERT_LLM_MODEL=meta-llama/llama-3-70b-instruct
# PDFCONVERT_LLM_BASE_URL=https://openrouter.ai/api/v1/chat/completions
# PDFCONVERT_LLM_API_KEY=sk-or-...

# AgentRouter
# PDFCONVERT_LLM_PROVIDER=agentrouter
# PDFCONVERT_LLM_MODEL=gpt-4o-mini
# PDFCONVERT_LLM_BASE_URL=https://api.agentrouter.ai/v1
# PDFCONVERT_LLM_API_KEY=ar-...
```

## Frontend (Next.js)

Giao diện React/Next.js nằm trong thư mục `src/frontend` với các module chính: trang đăng nhập, bảng điều khiển Jobs, trang quản trị cấu hình OCR và audit logs.

### Chạy UI cục bộ

```bash
cd src/frontend
npm install
npm run dev
```

Biến môi trường `NEXT_PUBLIC_API_BASE_URL` cho phép cấu hình endpoint backend (mặc định `http://localhost:8000`).
