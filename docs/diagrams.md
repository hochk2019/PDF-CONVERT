# ERD và lưu đồ xử lý PDF

## Mô hình thực thể (ERD)
```mermaid
erDiagram
    USER ||--o{ JOB : submits
    JOB ||--|{ PAGE : contains
    JOB ||--o{ WEBHOOK : notifies
    JOB ||--o{ JOB_EVENT : logs
    PAGE ||--o{ PAGE_BLOCK : has
    PAGE_BLOCK ||--o{ OCR_RESULT : produces
    OCR_RESULT ||--o{ FIELD_VALUE : normalizes
    DOCUMENT_TEMPLATE ||--o{ FIELD_SCHEMA : defines
    FIELD_SCHEMA ||--o{ FIELD_VALUE : validates
    STORAGE_OBJECT ||--o{ JOB : stores

    USER {
        uuid id
        string email
        string department
    }
    JOB {
        uuid id
        string status
        timestamp submitted_at
        timestamp completed_at
        string source
    }
    PAGE {
        uuid id
        int page_number
        string image_path
    }
    PAGE_BLOCK {
        uuid id
        string type
        json bbox
    }
    OCR_RESULT {
        uuid id
        string ocr_engine
        float confidence
        text raw_text
    }
    FIELD_VALUE {
        uuid id
        string field_key
        text value
        json normalized
    }
    DOCUMENT_TEMPLATE {
        uuid id
        string name
        string version
    }
    FIELD_SCHEMA {
        uuid id
        string field_key
        string data_type
        json rules
    }
    STORAGE_OBJECT {
        uuid id
        string bucket
        string path
    }
    WEBHOOK {
        uuid id
        string target_url
        string secret
    }
    JOB_EVENT {
        uuid id
        string event_type
        json payload
        timestamp created_at
    }
```

## Lưu đồ xử lý PDF
```mermaid
flowchart TD
    A[Nhận file từ UI/API] --> B{Kiểm tra định dạng}
    B -->|PDF chuẩn| C[Đẩy vào S3/MinIO]
    B -->|Không hợp lệ| Z[Trả lỗi cho client]
    C --> D[Đăng ký job trong PostgreSQL]
    D --> E[Phát sự kiện lên hàng đợi Redis]
    E --> F[Worker lấy job]
    F --> G[Tiền xử lý ảnh (deskew, denoise)]
    G --> H{Loại tài liệu}
    H -->|Dễ/Trung bình| I[PaddleOCR Inference]
    H -->|Khó - cần GPU| J[PaddleOCR GPU Worker]
    H -->|Viết tay| K[Chuyển human-in-the-loop]
    I --> L[Trích xuất cấu trúc (bảng, form)]
    J --> L
    L --> M[Hậu xử lý (spell-check, chuẩn hóa)]
    M --> N[Mapping sang template]
    N --> O[Ghi kết quả OCR & field vào PostgreSQL]
    O --> P[Đẩy file kết quả (PDF + JSON) lên S3]
    P --> Q[Gửi webhook/thông báo]
    Q --> R[UI cập nhật trạng thái]
```
