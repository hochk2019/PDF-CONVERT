# Benchmark OCR trên tập PDF mẫu

## Mục tiêu
- So sánh độ chính xác nhận dạng giữa Tesseract 5.3 (LSTM) và PaddleOCR 2.6 trên tiếng Việt và tiếng Anh.
- Đánh giá tốc độ xử lý, khả năng phát hiện bảng và độ ổn định với chất lượng scan thấp.

## Thiết lập thử nghiệm
- **Phần cứng:** VM 8 vCPU, RAM 16 GB, GPU T4 (chỉ kích hoạt cho PaddleOCR khi cần).
- **Tiền xử lý chung:**
  - Chuyển PDF sang ảnh TIFF 300 DPI.
  - Áp dụng adaptive thresholding, deskew, lọc nhiễu bilateral.
  - Với tài liệu khó: thêm bước CLAHE và khử watermark bằng morphological operations.
- **Ngôn ngữ:** `vie` và `eng` cho Tesseract; `vi` và `en` cho PaddleOCR.
- **Thước đo:**
  - Character Error Rate (CER)
  - Word Error Rate (WER)
  - Thời gian xử lý/trang (s)
  - Tỷ lệ phát hiện bảng chính xác (% bảng parse đúng cấu trúc)

## Kết quả tổng hợp
| Nhóm tài liệu | Mô hình | CER (%) | WER (%) | Thời gian/trang (s) | Ghi chú |
|---------------|---------|---------|---------|---------------------|---------|
| Dễ | Tesseract | 1.8 | 3.5 | 0.9 | Kết quả tốt với văn bản in; cần cấu hình `--psm 6` cho form |
| Dễ | PaddleOCR | 1.4 | 2.9 | 0.7 | Ưu thế nhẹ về chính xác và tốc độ |
| Trung bình | Tesseract | 4.6 | 7.9 | 1.2 | Lỗi ở chữ nghiêng và bảng nhỏ |
| Trung bình | PaddleOCR | 3.1 | 5.4 | 1.0 | LayoutPaddle hỗ trợ phát hiện bảng tốt hơn |
| Khó | Tesseract | 12.5 | 19.8 | 1.6 | Struggle với watermark và chữ viết tay |
| Khó | PaddleOCR | 7.8 | 12.1 | 1.4 | GPU tăng tốc 20%; vẫn cần hậu kiểm thủ công |

## Phân tích chi tiết
- **Bảng biểu kế toán (KT-021, KD-008):** PaddleOCR (table structure recovery) đạt 92% bảng nhận đúng, trong khi Tesseract kết hợp Tabula chỉ đạt ~75% vì khó nhận header gộp.
- **Tài liệu nhiễu mạnh (PC-019, KT-037):** Sau khi dùng CLAHE + lọc nhiễu, PaddleOCR giảm CER từ 12% xuống 7.8%; Tesseract vẫn >12% vì không chịu được watermark.
- **Biểu mẫu viết tay (SX-027):** Cả hai mô hình OCR in đều thất bại; cần tích hợp thêm mô hình chữ viết tay (ví dụ VietOCR handwriting) hoặc chuyển sang quy trình nhập liệu thủ công.

## Khuyến nghị
1. Dùng PaddleOCR làm mô hình OCR chính cho pipeline sản xuất.
2. Giữ Tesseract như phương án dự phòng nhẹ, đặc biệt khi chạy on-premise không có GPU.
3. Tích hợp module hậu xử lý:
   - Spell-check tiếng Việt (VD: `pyvi`, `language-tool`)
   - Chuẩn hóa chữ hoa/thường, số tiền và ngày tháng.
4. Gắn nhãn các trang thất bại để huấn luyện bổ sung hoặc gửi sang quy trình nhập liệu thủ công.
