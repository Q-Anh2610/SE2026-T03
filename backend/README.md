# Backend — TV1, TV2, TV3

Định hướng Python + FastAPI; chưa thêm dependencies hoặc endpoint trong bước tổ chức thư mục.

| Thư mục | Trách nhiệm | Chủ trì |
|---|---|---|
| `app/api/` | Router, validation đầu vào, gọi nghiệp vụ | TV1 |
| `app/schemas/` | Request/response DTO và contract | TV1 |
| `app/core/` | Cấu hình dùng chung | TV1 |
| `app/db/` | PostgreSQL models, kết nối và persistence | TV1 |
| `app/services/` | Nghiệp vụ và điều phối | TV1 |
| `app/ingestion/` | Source adapter, download, normalize, retry, dedup | TV2 |
| `app/embedding/` | Encoder và preprocessing dùng chung | TV3 |
| `app/search/` | Vector store, retrieval, filters, fusion | TV3 |
| `migrations/` | Migrations có phiên bản; nằm ngoài `app/` | TV1 |
| `tests/unit/`, `tests/integration/` | Tests module và tích hợp | Chủ module + TV5 |

Ingestion và search tái sử dụng encoder trong `app/embedding/`. Router giữ mỏng; không thêm pipeline thứ hai vào API. Chưa có lệnh chạy/test cho tới khi manifest và code được triển khai.
