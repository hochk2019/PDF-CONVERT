# Use Case Chính Cho Nền Tảng PDF-CONVERT

Dựa trên các tài liệu dự án hiện có (kiến trúc backend FastAPI + Celery, giao diện Next.js quản lý Jobs, tài liệu sample dataset và benchmark OCR), danh sách use case nghiệp vụ trọng tâm được tổng hợp như sau.

## 1. Tiếp nhận và phân loại lô tài liệu PDF
- **Mục tiêu:** Người dùng nội bộ hoặc khách hàng tải lên các tập PDF cần xử lý.
- **Tác nhân chính:** Nhân viên vận hành, khách hàng B2B.
- **Mô tả ngắn:** Hệ thống nhận file qua giao diện web/API, gắn nhãn phòng ban/loại tài liệu, lưu trữ vào hàng đợi Celery.
- **Điều kiện thành công:** Tập tin được kiểm tra định dạng, ghi nhận metadata (độ ưu tiên, SLA) và tạo job OCR tương ứng.

## 2. Cấu hình và theo dõi pipeline OCR
- **Mục tiêu:** Điều chỉnh các tham số OCR (chọn PaddleOCR/Tesseract, thiết lập layout detection, table recognition).
- **Tác nhân chính:** Quản trị hệ thống OCR.
- **Mô tả ngắn:** Thông qua bảng điều khiển, quản trị viên áp dụng cấu hình phù hợp với từng loại tài liệu hoặc chiến dịch.
- **Điều kiện thành công:** Cấu hình được lưu, kích hoạt cho các job mới và ghi nhận lịch sử thay đổi.

## 3. Xử lý và giám sát job chuyển đổi
- **Mục tiêu:** Thực thi pipeline chuyển PDF → ảnh → OCR → hậu xử lý.
- **Tác nhân chính:** Worker Celery, nhân viên vận hành.
- **Mô tả ngắn:** Worker nhận job, chạy các bước tiền xử lý (grayscale, denoise, deskew), OCR, nhận dạng bảng, hậu xử lý tiếng Việt và cập nhật trạng thái.
- **Điều kiện thành công:** Job hoàn tất trong SLA, lưu log chi tiết và kết quả trung gian để debug khi cần.

## 4. Rà soát và hiệu chỉnh kết quả OCR
- **Mục tiêu:** Đảm bảo văn bản trích xuất chính xác cho các tài liệu quan trọng.
- **Tác nhân chính:** Nhân viên kiểm duyệt chất lượng.
- **Mô tả ngắn:** Người dùng so sánh văn bản OCR với ảnh/pdf, sửa lỗi chính tả, xác nhận bảng và lưu phiên bản đã chuẩn hóa.
- **Điều kiện thành công:** Tỉ lệ lỗi ở mức chấp nhận được, phiên bản đã duyệt được khóa và gửi trả cho khách hàng/hệ thống downstream.

## 5. Quản lý dữ liệu huấn luyện và fine-tune tiếng Việt
- **Mục tiêu:** Thu thập, phân loại tập dữ liệu để fine-tune OCR tiếng Việt.
- **Tác nhân chính:** Nhóm R&D.
- **Mô tả ngắn:** Tạo bộ mẫu có nhãn từ các nguồn (nội bộ, khách hàng, public), chuẩn hóa annotation và sinh cấu hình fine-tune theo `vietnamese_finetune.py`.
- **Điều kiện thành công:** Bộ dữ liệu đạt chuẩn, có metadata nguồn/ quyền sử dụng, sẵn sàng cho huấn luyện bổ sung.

## 6. Tích hợp kết quả vào hệ thống nghiệp vụ
- **Mục tiêu:** Đồng bộ văn bản OCR với các hệ thống ERP/ECM hiện hữu.
- **Tác nhân chính:** API backend, hệ thống đối tác.
- **Mô tả ngắn:** Backend FastAPI cung cấp API trả kết quả, webhooks hoặc xuất file theo định dạng chuẩn (JSON/CSV), đồng thời ghi audit log.
- **Điều kiện thành công:** Dữ liệu được đồng bộ chính xác, có kiểm soát truy cập và nhật ký đầy đủ cho mục đích kiểm toán.

## 7. Theo dõi hiệu năng và báo cáo chất lượng
- **Mục tiêu:** Đánh giá KPI (độ chính xác OCR, thời gian xử lý, tỉ lệ lỗi) theo từng tập tài liệu.
- **Tác nhân chính:** Quản trị dự án, nhóm vận hành.
- **Mô tả ngắn:** Sử dụng dashboard thống kê (từ benchmark OCR, log job) để phát hiện bottleneck và lên kế hoạch cải tiến.
- **Điều kiện thành công:** Báo cáo định kỳ được tạo, nêu rõ khu vực cần tối ưu và đề xuất hành động tiếp theo.
