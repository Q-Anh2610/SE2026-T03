# Frontend — TV4

Định hướng React + TypeScript + Vite; chưa scaffold ứng dụng hoặc chọn dependencies trong bước tổ chức thư mục.

- `src/app/`: router và layout.
- `src/features/search/`: query văn bản/ảnh, filters và kết quả.
- `src/features/assets/`: chi tiết asset.
- `src/features/feedback/`: phản hồi relevance.
- `src/features/admin/`: UI quản trị do TV5 phối hợp TV4.
- `src/components/`: thành phần giao diện dùng chung.
- `src/lib/api/`: HTTP client; phối hợp contract với TV1.
- `src/types/`: types dùng chung; kiểu riêng feature đặt trong feature đó.
- `tests/e2e/`: luồng tích hợp do TV5 chủ trì.

UI gọi HTTP API, không kết nối trực tiếp PostgreSQL/Qdrant. Chỉ thêm module và scripts chạy khi nhiệm vụ cần.
