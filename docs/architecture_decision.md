# Đề xuất kiến trúc hệ thống PDF Convert

## Yêu cầu chính
- Nhận file PDF từ web portal hoặc API đối tác.
- Xử lý OCR, trích xuất bảng, chuẩn hóa dữ liệu và trả kết quả JSON + file đã xử lý.
- Quản lý hàng đợi xử lý và cho phép mở rộng theo lô lớn.
- Tích hợp với hệ thống hiện tại (SSO, lưu trữ S3, Webhook thông báo).

## Phương án so sánh
| Tiêu chí | Python FastAPI + Node.js Gateway | Monolithic FastAPI |
|----------|----------------------------------|--------------------|
| Mô tả | Node.js làm API Gateway + auth, điều phối sang microservice FastAPI xử lý | Một ứng dụng FastAPI xử lý cả gateway lẫn OCR |
| Hiệu năng | Gateway non-blocking, scale độc lập; overhead network tăng | Đơn giản, ít hop; phải tối ưu asyncio để tránh nghẽn |
| Đội ngũ | Cần dev Node & Python | Chỉ cần Python |
| DevOps | Phức tạp hơn (2 repo/container) | Dễ vận hành |
| Tích hợp | Dễ thêm service mới sau này | Tính linh hoạt hạn chế |
| Rủi ro | Đồng bộ schema auth giữa 2 service | Ứng dụng phình to, khó bảo trì |

## Lựa chọn đề xuất: **Python FastAPI + Node.js Gateway**

### Lý do
1. **Tách biệt mối quan tâm:** Node.js gateway đảm nhiệm xác thực, rate limit, multi-tenant routing; microservice FastAPI tập trung vào pipeline OCR, dễ mở rộng bằng Celery/Redis.
2. **Khả năng mở rộng:** Có thể nhân bản service xử lý theo số lượng tài liệu, trong khi gateway vẫn nhẹ, cân bằng tải tốt.
3. **Tích hợp:** Gateway dễ dàng tích hợp SSO, logging tập trung (Winston) và forward request sang các service khác (ví dụ trích xuất dữ liệu nâng cao trong tương lai).

### Kiến trúc tổng quan
```
[Client/UI] --HTTPS--> [Node.js API Gateway] --gRPC/REST--> [FastAPI OCR Service]
                                              |--> [Celery Worker + Redis Queue]
                                              |--> [MinIO/S3 Storage]
                                              |--> [PostgreSQL Metadata]
                                              |--> [Webhook Dispatcher]
```

### Thành phần chính
- **Gateway (Node.js + NestJS/Express):**
  - Modules: Auth (SSO, JWT), Upload, Job status, Webhook
  - Kết nối FastAPI qua REST nội bộ hoặc gRPC
  - Rate limiting (Redis) và request logging (ELK stack)
- **FastAPI OCR Service:**
  - Endpoints nhận job, truy vấn trạng thái, tải xuống kết quả
  - Pipeline xử lý bất đồng bộ (Celery)
  - Tích hợp PaddleOCR, PDFPlumber, layoutparser
- **Hàng đợi & Worker:**
  - Redis (celery broker) + PostgreSQL (result backend) hoặc sử dụng Flower để theo dõi job
  - Worker GPU cho tài liệu khó
- **Kho dữ liệu:**
  - Object storage (S3/MinIO) lưu file gốc và kết quả
  - PostgreSQL lưu metadata job, kết quả OCR, mapping trường dữ liệu

### Kế hoạch triển khai
1. Thiết lập repo riêng cho gateway và OCR service; dùng Docker Compose để local dev.
2. Xây dựng CI/CD (GitHub Actions) lint/test/build image.
3. Tạo Helm chart để triển khai lên Kubernetes nội bộ.
4. Áp dụng observability: Prometheus metrics, Grafana dashboard, centralized logging.
