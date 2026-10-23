# Backend — Vũ Nguyễn Quỳnh Anh, Trịnh Thị Thu Huyền, Lê Thị Linh Chi

FastAPI skeleton dùng Python 3.13, Uvicorn, pydantic-settings và pytest.

## Chạy local trên Windows PowerShell

Từ gốc repository, tạo file cấu hình nếu chưa có, không ghi đè `.env` đang dùng:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Nếu đã có `.venv`, bỏ qua bước tạo lại. Không cần activate môi trường.
Linux/macOS: tạo bằng `python3.13 -m venv .venv`, dùng `.venv/bin/python`.

- `GET http://127.0.0.1:8000/healthz`: HTTP 200, `{"status":"ok"}`.
- `http://127.0.0.1:8000/docs`: Swagger UI.
- Nhấn Ctrl+C để dừng Uvicorn.

## API contract mock (Issue #9)

Swagger `/docs` có đủ GET assets/list-detail, POST search/text, search/image và
feedback dưới `/api/v1`. Xem [contract mock v1](../docs/contracts/api-v1.md) và
`docs/openapi.json`. Text chỉ khớp từ khóa fixture, ảnh trả dữ liệu mẫu cố định;
feedback lưu trong RAM, không ghi PostgreSQL. Các thay đổi contract chờ Duy review.

Mock chỉ bật khi `APP_MOCK_API_ENABLED=true` và `APP_ENV` khác `production`.
Mặc định CORS cho Vite localhost:5173; cấu hình `APP_CORS_ORIGINS` bằng mảng JSON.
Giữ `APP_DEBUG=false` để lỗi 500 dùng JSON chuẩn thay traceback debug.

Export lại spec sau khi sửa schemas/routes, từ backend/:

```powershell
.\.venv\Scripts\python.exe -m app.export_openapi
```

`/healthz` là liveness probe, không kết nối DB, Qdrant hoặc nạp model;
response thành công không có nghĩa các thành phần này đã sẵn sàng.

## Cấu hình

`app/core/config.py` dùng pydantic-settings, đọc `.env` ở gốc repository theo
đường dẫn tuyệt đối suy ra từ file Python, không phụ thuộc working directory.
Biến môi trường của tiến trình ưu tiên hơn file; không có file thì dùng defaults.
Các biến dành cho dịch vụ khác trong `.env` chung được bỏ qua.

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `APP_NAME` | `3D Asset Semantic Search API` | Tiêu đề FastAPI/OpenAPI |
| `APP_ENV` | `development` | `development`, `test` hoặc `production` |
| `APP_DEBUG` | `false` | Debug FastAPI, không bật ở production |
| `BACKEND_PORT` | `8000` | Cổng host của Compose, không thay cổng Uvicorn local |

`.env.example` là cấu hình mẫu; `.env` không được commit hay đưa vào image.
Ứng dụng từ chối giá trị `APP_ENV`/`APP_DEBUG` sai định dạng.

## Kiểm thử

Từ `backend/` sau khi cài requirements-dev:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Tests kiểm tra health status/body/content type, HTTP method không hỗ trợ,
OpenAPI và settings: dotenv UTF-8, thứ tự ưu tiên, default và validation.
Unit tests không cần DB/model; integration tests dùng PostgreSQL thật qua
`TEST_DATABASE_URL`. Xem [hướng dẫn database](../docs/guides/database.md).

## Docker

Yêu cầu Docker Desktop đang chạy với Linux Engine. Chạy các lệnh sau từ gốc
repository. Tạo `.env` từ mẫu chỉ khi chưa có; không ghi đè cấu hình local đang
dùng:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Nếu `.env` đã tồn tại, giữ nguyên các giá trị hiện có và bổ sung thủ công những
biến Compose còn thiếu từ `.env.example`. Đặt `POSTGRES_PASSWORD` thành mật khẩu
local giả; không dùng hoặc chia sẻ credentials thật. Sau đó xác minh cấu hình và
khởi chạy backend cùng PostgreSQL:

```powershell
docker compose -f docker-compose.yml config --quiet
docker compose -f docker-compose.yml up --build -d --wait backend
docker compose -f docker-compose.yml ps
Invoke-RestMethod http://127.0.0.1:8000/healthz
```

`/healthz` trả `{"status":"ok"}` là liveness check; nó không xác nhận migration,
search hoặc Qdrant hoạt động. Nếu `docker compose up` báo cổng 8000 đã được sử
dụng, kiểm tra tiến trình/container đang giữ cổng trước khi dừng nó, hoặc đặt
`BACKEND_PORT` thành cổng host còn trống trong `.env`. Khi đổi cổng, dùng cổng
đó trong URL health check, ví dụ `http://127.0.0.1:<BACKEND_PORT>/healthz`.

Compose khởi chạy backend và PostgreSQL 17; backend chờ PostgreSQL healthy.
Container chạy user non-root, có healthcheck và chỉ publish lên localhost.
Migration và seed chạy riêng theo [hướng dẫn database](../docs/guides/database.md).

```powershell
docker compose -f docker-compose.yml logs backend
docker compose -f docker-compose.yml stop
```

Lệnh `stop` dừng backend và PostgreSQL, giữ nguyên volume/database. Không dùng
`down -v` hoặc lệnh prune khi chỉ cần dừng stack.

Để build/run Dockerfile riêng, cũng chạy từ gốc repository:

```powershell
docker build -t se-backend ./backend
docker run --rm --env-file .env -p 127.0.0.1:8000:8000 se-backend
```

## Dependencies

- `requirements.in`: dependencies runtime trực tiếp.
- `requirements.txt`: runtime và dependencies gián tiếp được pin.
- `requirements-dev.in`: runtime cùng pytest/httpx2 cho TestClient của Starlette.
- `requirements-dev.txt`: toàn bộ dependencies phát triển đã pin.

Docker chỉ cài requirements runtime. Dùng requirements theo yêu cầu issue;
chưa thêm một manifest `pyproject.toml` khai báo dependencies trùng lặp.
Thay dependencies cần phối hợp owner, sửa `.in` rồi generate lại `.txt`.
uv là công cụ tùy chọn cho bước generate, không bắt buộc để chạy ứng dụng:

```powershell
uv pip compile backend/requirements.in --python-version 3.13 --universal --no-header -o backend/requirements.txt
uv pip compile backend/requirements-dev.in --python-version 3.13 --universal --no-header -o backend/requirements-dev.txt
```

Hai lệnh generate chạy từ gốc repository. Evaluation có thể dùng cùng môi trường
khi được triển khai; không cài thêm dependencies ML chỉ để chạy health check.

## Ranh giới thư mục

| Thư mục | Trách nhiệm | Chủ trì |
|---|---|---|
| `app/api/` | Router, validation đầu vào, gọi nghiệp vụ | Vũ Nguyễn Quỳnh Anh |
| `app/schemas/` | Request/response DTO và contract | Vũ Nguyễn Quỳnh Anh |
| `app/core/` | Cấu hình dùng chung | Vũ Nguyễn Quỳnh Anh |
| `app/models/` | ORM Asset, SearchEvent, Feedback | Vũ Nguyễn Quỳnh Anh |
| `app/db/` | Kết nối PostgreSQL và persistence | Vũ Nguyễn Quỳnh Anh |
| `app/services/` | Nghiệp vụ và điều phối | Vũ Nguyễn Quỳnh Anh |
| `app/ingestion/` | Source adapter, download, normalize, retry, dedup | Trịnh Thị Thu Huyền |
| `app/embedding/` | Encoder và preprocessing dùng chung | Lê Thị Linh Chi |
| `app/search/` | Vector store, retrieval, filters, fusion | Lê Thị Linh Chi |
| `alembic/` | Migrations có phiên bản; cấu hình tại alembic.ini | Vũ Nguyễn Quỳnh Anh |
| `tests/unit/`, `tests/integration/` | Tests module và tích hợp | Chủ module + Đoàn Thị Minh Khuê |

Ingestion và search tái sử dụng encoder trong `app/embedding/`. Router giữ mỏng;
không thêm pipeline thứ hai vào API. Schema PostgreSQL, migration đầu và seed
được mô tả tại [hướng dẫn database](../docs/guides/database.md). Chưa triển khai
authentication hoặc tìm kiếm semantic thật; API mock của Issue #9 chưa ghi
PostgreSQL. Giữ code có sẵn của các thành viên.
