# Kế hoạch kiểm thử UX nội bộ

Để đảm bảo giao diện mới đáp ứng nhu cầu của các nhóm vận hành tài liệu, chúng tôi lập kế hoạch kiểm thử UX nội bộ gồm ba vòng:

1. **Khảo sát định tính nhanh**
   - Đối tượng: 5 nhân viên vận hành tài liệu.
   - Mục tiêu: Kiểm tra khả năng tìm chức năng tải lên, xem trạng thái job và truy cập cấu hình OCR.
   - Công cụ: Figma prototype và môi trường staging của ứng dụng Next.js.

2. **Phiên thử nghiệm theo kịch bản**
   - Đối tượng: 8 người dùng nội bộ, chia thành hai nhóm (chuyên viên OCR và quản trị viên).
   - Kịch bản chính: tạo job mới, giám sát trạng thái qua WebSocket, tải kết quả JSON, xem audit logs.
   - Thu thập dữ liệu: ghi màn hình, ghi chú thời gian hoàn thành nhiệm vụ, bảng khảo sát SUS.

3. **Phân tích & cải tiến**
   - Tổng hợp phản hồi trong bảng tổng hợp Notion, phân loại theo mức độ nghiêm trọng.
   - Lặp lại cải tiến UI trong sprint kế tiếp, ưu tiên vấn đề ảnh hưởng đến khả năng nhận biết trạng thái và luồng tải xuống.

Mỗi vòng kiểm thử được gắn với một sprint phát triển, thời lượng 1 tuần, có checklist hoàn thành và báo cáo đính kèm trong thư mục `/docs` của dự án.
