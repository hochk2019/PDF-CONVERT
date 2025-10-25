# Phác thảo UI/UX (Figma)

## Mục tiêu trải nghiệm
- Đơn giản hóa quy trình tải PDF, theo dõi trạng thái xử lý, tải kết quả.
- Hỗ trợ nhân viên vận hành kiểm duyệt trang lỗi và gửi lại pipeline.
- Cung cấp dashboard trực quan về hiệu năng OCR và backlog job.

## Luồng chính
1. **Đăng nhập SSO** → chuyển tới Dashboard.
2. **Dashboard:**
   - Thẻ tổng quan: số job đang xử lý, hoàn tất, lỗi.
   - Biểu đồ line: thời gian xử lý trung bình 7 ngày.
   - Bảng job gần nhất với trạng thái, thời gian, người tạo.
3. **Tạo job mới:**
   - Modal kéo/thả PDF hoặc chọn từ kho S3.
   - Form chọn template, ngôn ngữ OCR, mức ưu tiên.
   - Sau khi gửi, chuyển tới trang chi tiết job.
4. **Trang chi tiết job:**
   - Timeline trạng thái (Queued → Processing → Completed/Failed).
   - Thẻ tóm tắt thông tin metadata.
   - Tabs: "Kết quả OCR" (hiển thị text + confidence), "Bảng" (preview bảng), "Log".
   - Button tải JSON, PDF đã xử lý, và nút "Gửi xử lý lại".
5. **Trung tâm kiểm duyệt:**
   - Grid hiển thị thumbnail trang lỗi.
   - Panel bên phải cho phép chỉnh sửa text, highlight vùng.
   - Action: đánh dấu hoàn tất, gán cho người khác.

## Thành phần Figma đề xuất
- **Trang Desktop (1440px width)** với Auto Layout cho dashboard.
- **Component library:**
  - Button (primary, secondary, danger)
  - Tag trạng thái (Queued, Processing, Completed, Failed, Manual Review)
  - Card job, Table row, Progress timeline
  - Modal upload, Drawer log
- **Design token:**
  - Màu chủ đạo: Xanh dương (#2563EB), accent cam (#F97316)
  - Font: Inter 14/16/20, Heading sử dụng 24/32 bold
  - Radius: 8px, Shadow: 0 10 25 rgba(15,23,42,0.1)

## Wireframe chi tiết
- **Dashboard:** 3 card KPI phía trên, dưới là 2 cột (bảng job & biểu đồ). Sidebar trái cho navigation (Dashboard, Job của tôi, Kiểm duyệt, Cấu hình).
- **Job detail:** Header chứa tên job + trạng thái badge + actions. Body chia 2 cột: trái (preview PDF), phải (tabs nội dung).
- **Kiểm duyệt:** Layout 3 cột (thumbnail list, viewer trung tâm, panel chi tiết).

## Handoff & Collaboration
- Tạo file Figma `PDF Convert Platform` với pages: `Design System`, `Dashboard`, `Job Detail`, `Review Center`.
- Liên kết Jira ticket vào từng frame.
- Xuất spec (Figma Inspect) cho dev, cung cấp token qua plugin (Design Tokens). 
