# Bằng chứng request/error logging W6 — Issue #137

Ngày 24/11/2026, nhánh `feat/137-request-error-logging`, base
`ea08c64504c41577d85cf4f5eefefc13002219f4` (merge PR #139 của #136),
working tree dirty khi chạy. Đây là kết quả local, chưa có PR/CI/review của
thay đổi #137. [Contract và hướng dẫn tra log](../contracts/request-logging-w6.md).

## Thay đổi và ranh giới

- Thêm middleware ASGI và app factory subclass nhỏ để giữ context/header
  ngoài cả ServerErrorMiddleware. CORS chuyển ra lớp ngoài error handler,
  giữ allowlist và expose header X-Request-ID cho origin đã cho phép.
- Server sinh UUID v4 riêng cho từng request, không nhận ID client; ContextVar
  được reset sau request và giữ đúng context qua dependency sync/thread.
- Mỗi request một JSON record tổng kết; log lỗi DB, events, feedback, retrieval
  và nhận reindex dùng cùng ID, code và stage an toàn.
- Không log body/query/raw path/header/ảnh/exception; không thay root logger.
  Các lỗi sau response hoặc stream abort được phân biệt, không ghi INFO thành
  công cho tác vụ đã lỗi; không đẩy raw exception nhạy cảm lên server.
- Không đổi response body/DTO/OpenAPI, DB schema/migration, dependencies,
  retrieval default/frozen config, model/index hoặc dữ liệu benchmark.
- Không sửa client/UI sản phẩm. Bổ sung một ca browser integration hiện có,
  chạy ở hai projects desktop/mobile, để xác nhận header thực sự đọc được qua CORS.

## Kết quả kiểm chứng

| Nhóm | Kết quả và phạm vi |
|---|---|
| Unit logging mới | 26 cases: ID server/ignore ID đầu vào, JSON allowlist, body/ảnh, status/stage, 12 requests đồng thời, sync thread, CORS, cancel/stream/lỗi sau body, handler không trùng |
| PostgreSQL commit-time | Mở rộng 3 tests #136: lỗi INSERT/COMMIT fault injection được rollback; log lỗi và response chung ID, request phục hồi có ID mới và không mang error context cũ |
| Uvicorn TCP thật | 1 test gửi 7 requests: 200/400/403/404/503/500 rồi 200; kiểm CORS/header/envelope/log, không có raw server traceback chứa fixture riêng tư |
| Nhóm hồi quy backend | **407 passed**, 0 errors/failures/skipped, **49,77 giây**; đã gồm các tests mới và PostgreSQL integration, không cộng số lại |
| Browser frontend–FastAPI | **10/10 passed**, **33,2 giây**, Chrome headless desktop/mobile, 1 worker; gồm hai lượt chạy ca header mới |
| Frontend typecheck | Đạt |
| Frontend lint | Đạt |
| Kiểm tra tĩnh | `git diff --check`, cú pháp Python, whitespace của cả file mới và các link tài liệu mới đều đạt |

Lượt backend bắt đầu theo JUnit `2026-11-24T14:35:50.045877+07:00`.
Browser gọi FastAPI/Uvicorn thật tại 5196 từ origin Vite 5197 và đọc được
`response.headers.get('X-Request-ID')` trên 200 và 400, hai ID khác nhau.
Backend browser chọn mock/fixtures tường minh; không coi đây là search model
thật, PostgreSQL feedback hoặc benchmark. Một ca cũ chỉ sửa request để kiểm
400 rồi retry; ca header mới không intercept response.

PostgreSQL integration dùng DB `test_issue137_<UUID>` do launcher local sở hữu,
mỗi test schema UUID với Alembic 0004 và tự dọn. Không ghi DB nghiệp vụ hoặc
Qdrant. Tests retrieval dùng fixtures, không nạp weights hoặc tải dataset.
Đã kiểm tra sau lượt chạy: không còn database `test_issue137_` do launcher tạo.
Tests thử nghiệm ban đầu phát hiện handler console/capture bị đăng ký lặp;
đã tách app.request khỏi root và bảo đảm capture chỉ đăng ký một lần, sau đó
chạy lại nhóm tests và hồi quy đạt, không bỏ assertion đếm record.

Môi trường: Windows 11 build 26200, Python 3.13.7/backend venv,
PostgreSQL 17.9 Docker local; FastAPI 0.143.3, Starlette 1.9.0,
SQLAlchemy 2.1.5, pytest 9.1.1. Frontend dùng Playwright/Chrome theo config repo.

JUnit local `data/processed/issue137/pytest-request-logging.xml`, SHA-256
`ecd9b68f0fc6c4a742e9d2a5520294677e94cddd85277b57ae3ef7f3f88fe22b`.
SHA-256 raw checkout `backend/app/core/request_logging.py` khi kiểm chứng:
`11edf725cbe57bc2bc64a46a29d415e7ebee6b19e51dd0e7f9d98a6227286874`.
JUnit, browser reports/traces và build output giữ ngoài Git.

## Lệnh tái lập

Đặt TEST_DATABASE_URL ngoài Git tới PostgreSQL test riêng có database bắt đầu
`test_`, driver `postgresql+psycopg`. Helpers chỉ dọn schema do test tạo, không
xóa DB operator cung cấp. Trên Windows dùng 127.0.0.1 nếu localhost phân giải
chậm. Từ `backend/`, nhóm tests tập trung:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_request_logging.py tests/integration/test_api_commit_recovery.py tests/integration/test_request_logging_http.py -q
```

Nhóm hồi quy đã chạy, cùng TEST_DATABASE_URL:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_request_logging.py tests/unit/test_api_error_envelope.py tests/unit/test_asset_list_errors.py tests/unit/test_asset_detail_errors.py tests/unit/test_health.py tests/unit/test_mock_api.py tests/unit/test_openapi.py tests/unit/test_text_search_contract.py tests/unit/test_text_search_api.py tests/unit/test_text_search_service.py tests/unit/test_text_search_runtime.py tests/unit/test_image_search_api.py tests/unit/test_feedback_api.py tests/unit/test_search_explanation.py tests/unit/test_jobs_api.py tests/unit/test_reindex_api.py tests/unit/test_reindex_builder.py tests/unit/test_config.py tests/unit/test_database_config.py tests/unit/test_asset_api_verification.py tests/integration -q --junitxml=../data/processed/issue137/pytest-request-logging.xml
```

Browser integration, từ `frontend/`, ở terminal test riêng; explicit mock cho
nguồn dữ liệu, không sửa .env hoặc gọi model/index đang phục vụ:

```powershell
$env:BACKEND_PYTHON = (Resolve-Path '..\backend\.venv\Scripts\python.exe').Path
$env:APP_TEXT_SEARCH_SOURCE = 'mock'
$env:APP_IMAGE_SEARCH_SOURCE = 'mock'
$env:APP_FEEDBACK_SOURCE = 'mock'
npm run test:integration
npm run typecheck
npm run lint
```

Playwright config đặt APP_ENV=test, asset fixture và CORS origin tương ứng;
cần cổng 5196/5197 trống. Sau tests, đóng terminal test hoặc khôi phục các biến
tiến trình nếu tiếp tục chạy API thật trong cùng terminal.

## Giới hạn và bàn giao

- Không chạy lại toàn bộ backend unit suite, 46 E2E tổng quát hoặc benchmark
  model; kiểm chứng header/browser và PostgreSQL được tách rõ ở trên.
- Không bổ sung UI hiển thị request ID, lưu ID vào DB hoặc đổi idempotency.
  Không tự propagate request ID sang worker reindex độc lập hoặc thêm recovery.
- Uvicorn/proxy/library logs do cấu hình riêng quản lý; xem lệnh --no-access-log
  trong contract để không ghi raw URL song song với structured app logs.
- Duy review contract response header/CORS và cách tiếp nhận ở frontend;
  Khuê review allowlist, tests, context isolation và bằng chứng.
- CI mới nhất, owner review/approval và merge còn chờ khi mở PR; không tự tích
  thay reviewer hoặc đóng Issue #137 từ kết quả local.
