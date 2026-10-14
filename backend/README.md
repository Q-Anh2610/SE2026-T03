# Backend — Vũ Nguyễn Quỳnh Anh, Trịnh Thị Thu Huyền, Lê Thị Linh Chi

Định hướng Python + FastAPI; chưa thêm dependencies hoặc endpoint trong bước tổ chức thư mục.

| Thư mục | Trách nhiệm | Chủ trì |
|---|---|---|
| `app/api/` | Router, validation đầu vào, gọi nghiệp vụ | Vũ Nguyễn Quỳnh Anh |
| `app/schemas/` | Request/response DTO và contract | Vũ Nguyễn Quỳnh Anh |
| `app/core/` | Cấu hình dùng chung | Vũ Nguyễn Quỳnh Anh |
| `app/db/` | PostgreSQL models, kết nối và persistence | Vũ Nguyễn Quỳnh Anh |
| `app/services/` | Nghiệp vụ và điều phối | Vũ Nguyễn Quỳnh Anh |
| `app/ingestion/` | Source adapter, download, normalize, retry, dedup | Trịnh Thị Thu Huyền |
| `app/embedding/` | Encoder và preprocessing dùng chung | Lê Thị Linh Chi |
| `app/search/` | Vector store, retrieval, filters, fusion | Lê Thị Linh Chi |
| `migrations/` | Migrations có phiên bản; nằm ngoài `app/` | Vũ Nguyễn Quỳnh Anh |
| `tests/unit/`, `tests/integration/` | Tests module và tích hợp | Chủ module + Đoàn Thị Minh Khuê |

Ingestion và search tái sử dụng encoder trong `app/embedding/`. Router giữ mỏng; không thêm pipeline thứ hai vào API. Chưa có lệnh chạy/test cho tới khi manifest và code được triển khai.
