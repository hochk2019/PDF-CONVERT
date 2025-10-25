# Bộ sưu tập PDF mẫu

Tập PDF mẫu được thu thập từ các phòng ban nội bộ, phản ánh những trường hợp sử dụng phổ biến khi số hóa tài liệu. Mỗi tài liệu được phân loại theo độ khó dựa trên chất lượng scan, bố cục và số ngôn ngữ.

| Phòng ban | Tên tài liệu | Mô tả | Độ khó | Đặc điểm OCR đáng chú ý |
|-----------|--------------|-------|--------|--------------------------|
| Hành chính nhân sự | HDNS-001: Đơn nghỉ phép song ngữ | Scan sạch, bố cục form chuẩn, song ngữ Việt/Anh rõ ràng | Dễ | Văn bản in, nhiều ô điền tay nhưng chữ viết đọc rõ |
| Hành chính nhân sự | HDNS-014: Hợp đồng lao động 2018 | Scan từ bản photo, chữ hơi nhòe, có dấu đỏ chồng chữ | Trung bình | Phải xử lý làm sắc nét, tách vùng con dấu |
| Kế toán | KT-021: Báo cáo chi phí Q3 2023 | 12 trang, bảng biểu dày đặc, font nhỏ | Khó | Yêu cầu phát hiện bảng chính xác, nhiều ký hiệu kế toán |
| Kế toán | KT-037: Hóa đơn VAT scan camera | Ảnh chụp lệch góc, ánh sáng không đều | Khó | Cần hiệu chỉnh phối cảnh, khử nhiễu |
| Pháp chế | PC-005: Biên bản họp HĐQT | 6 trang, chữ in rõ, dấu nháy tay | Dễ | Văn bản đơn thuần, ít định dạng |
| Pháp chế | PC-019: Thông báo xử phạt đối tác | Scan từ bản fax, nhiễu mạnh, có watermark | Khó | Cần tăng tương phản, xử lý watermark |
| Kinh doanh | KD-008: Báo giá sản phẩm 2024 | PDF gốc, có bảng và hình ảnh | Dễ | Có thể trích xuất trực tiếp, cần phân loại vùng |
| Kinh doanh | KD-022: Hợp đồng khung song ngữ | 30 trang, nhiều mục lồng, chú thích song ngữ | Trung bình | Cần hỗ trợ tiếng Việt và tiếng Anh, nhận diện mục lục |
| Sản xuất | SX-011: Quy trình vận hành máy | Scan đen trắng, sơ đồ và bullet | Trung bình | Kết hợp OCR và vector hóa sơ đồ |
| Sản xuất | SX-027: Phiếu kiểm tra hiện trường viết tay | Viết tay trên biểu mẫu in, chữ viết khó đọc | Khó | Cần mô hình OCR chữ viết tay, hoặc nhập tay |

## Cách sử dụng bộ mẫu
1. Lưu trữ tài liệu trong kho `s3://pdf-convert-sample/<phòng-ban>/<mã-tài-liệu>.pdf`.
2. Gắn metadata trong cơ sở dữ liệu:
   - `department`
   - `difficulty`
   - `language`
   - `scan_quality`
3. Dùng để kiểm thử pipeline OCR, trích xuất dữ liệu và hiệu chỉnh UI.

## Kế hoạch mở rộng
- Bổ sung tài liệu tiếng Anh thuần (các hợp đồng đối tác) cho tập dễ.
- Bổ sung hóa đơn viết tay, biên bản hiện trường để huấn luyện mô hình chữ viết.
- Thu thập thêm tài liệu dạng PDF gốc (không scan) để đo hiệu năng trích xuất text-native.
