# W6 — Rà lỗi API và transaction PostgreSQL (#136)

Ngày 24/11/2026; Quỳnh Anh thực hiện trên `fix/136-api-db-error-handling`.
Base `a821314` (PR #134 đã merge), working tree dirty khi kiểm chứng. Kết quả
dưới đây là local, không thay CI, review hoặc merge của PR chưa mở.

## Lỗi tái hiện và bản sửa

Contract text search yêu cầu JSON không hợp lệ trả `400 INVALID_REQUEST`;
validation DTO đã dùng mã này. Tuy nhiên, lỗi parser của FastAPI/Starlette có
thể đi qua HTTPException thay vì RequestValidationError:

| Request | Trước sửa | Sau sửa |
|---|---|---|
| JSON chứa byte `FF` không giải mã được, gửi search/text hoặc feedback | 400 HTTP_400 | 400 INVALID_REQUEST |
| JSON không giải mã được, gửi admin/reindex với khóa fixture hợp lệ | 400 HTTP_400 | 400 INVALID_REQUEST |
| Upload search/image với Content-Type multipart/form-data nhưng thiếu boundary | 400 HTTP_400 | 400 INVALID_REQUEST |

Tám regression cases (bốn tình huống × mock/service) trong
`backend/tests/unit/test_api_error_envelope.py` đều thất bại trước sửa;
ca giữ nguyên lỗi 404/405/500 đạt: **8 failed, 1 passed**. Sau sửa: **9 passed**.

Bản sửa ở `backend/app/core/errors.py` chỉ chuẩn hóa HTTPException status 400
có detail không phải dictionary thành envelope sẵn có:

```json
{"error":{"code":"INVALID_REQUEST","message":"Yêu cầu không hợp lệ.","details":[]}}
```

Không trả thông báo parser/input gốc. Detail dictionary có mã nghiệp vụ riêng
vẫn được giữ; status và headers không đổi. Các lỗi 404/405/500 giữ envelope
cũ, gồm header Allow của 405. Không đổi DTO/OpenAPI, endpoint, migration,
dependencies, default model hoặc frozen config. Tests OpenAPI hiện có vẫn đạt.

## Ma trận rà soát

Tận dụng tests đã có thay vì tạo lại từng tình huống; nhóm hồi quy bên dưới
bao gồm các files được dẫn. Với DB, dùng PostgreSQL thật; retrieval/preview
trong tests là fixtures, không phải model/Qdrant thật.

| Phần | Phạm vi kiểm chứng | Tests chính |
|---|---|---|
| Assets list/detail | Validation trước DB, 404, lỗi đọc DB an toàn, không fallback fixture, đóng session và phục hồi | test_asset_list_errors, test_asset_detail_errors; integration test_asset_api_stack/list/detail |
| Text/image search | 400, 503 dependency/metadata mismatch, 500 DB/mapping, không tạo event thành công khi lỗi; versions/rank/pagination | test_text_search_api, test_image_search_api; integration test_text_search_stack, test_image_search_stack |
| Feedback | Validation, event/asset không có hoặc không thuộc trang, lỗi ghi/đọc DB, rollback và retry | test_feedback_api; integration test_feedback_stack |
| Jobs/status | 403/503 cấu hình quản trị, validation, 404, lỗi DB, read snapshot và phục hồi | test_jobs_api; integration test_jobs_stack |
| Reindex | Validation/auth, 409 cạnh tranh, replay, lỗi nhận job/runner/artifact/commit, không báo succeeded giả | test_reindex_api/builder; integration test_reindex_stack |
| Các API dùng chung app | Search/feedback vẫn hoạt động khi reindex thành công/lỗi; giữ baseline versions | integration test_w5_api_coexistence |
| Parser/envelope | JSON không giải mã được, multipart thiếu boundary, 404/405/500 an toàn | test_api_error_envelope (mới) |
| Commit-time failure | INSERT đã đạt nhưng COMMIT bị DB từ chối; rollback và request tiếp theo phục hồi | integration test_api_commit_recovery (mới) |

Ngoài lỗi mã parser nêu trên, không phát hiện lỗi mới cần sửa ở DB/service
trong phạm vi các tests đã chạy. Không tuyên bố lỗi production từ fault injection.

## Kiểm chứng lỗi tại COMMIT

Ba ca mới trong `backend/tests/integration/test_api_commit_recovery.py`:

- Text search, image search và feedback chạy qua API/ASGI với session thật.
- Mỗi test tạo schema UUID riêng, migration tới head 0004 và asset fixture nhỏ.
- Tạo constraint trigger `DEFERRABLE INITIALLY DEFERRED` chỉ trong schema test.
  PostgreSQL xác nhận trigger là deferred; listener xác nhận INSERT đã chạy
  thành công trước khi trigger từ chối tại COMMIT.
- API trả 500 INTERNAL_ERROR; session đọc độc lập xác nhận số events/feedback
  không tăng. Chi tiết riêng của lỗi SQL không xuất hiện trong response/log
  của các logger được kiểm tra; kết nối trả về pool (checkedout=0).
- Asset detail và jobs/status vẫn đọc được trong lúc trigger còn bật.
- Gỡ trigger rồi gửi lại bằng cùng TestClient: text/image trả 200, feedback
  trả 201; đúng một row mới được lưu, mock=false và versions fixture đúng.
- Function/trigger/schema test được dọn sau test, không tác động DB nghiệp vụ.

Đây là kiểm chứng bổ sung cho thời điểm commit, không phải triển khai cơ chế
retry commit tự động hoặc transaction phân tán PostgreSQL–Qdrant.

## Môi trường và kết quả

Windows 11 build 26200, Python 3.13.7 (backend venv), PostgreSQL 17.9 Docker
local; FastAPI 0.143.3, Starlette 1.9.0, Pydantic 2.14.1, SQLAlchemy 2.1.5,
psycopg 3.3.6, pytest 9.1.1.

- Nhóm backend: **380 passed**, 0 failures/errors/skipped; pytest báo
  **100,37 giây**. Bắt đầu theo JUnit `2026-11-24T11:30:15.234129+07:00`.
  Tổng này đã gồm 9 unit và 3 integration tests mới, không cộng thêm lần nữa.
- Bốn files API client frontend: **141 passed**, 6,93 giây. Đây là tests
  HTTP client có fixtures, không phải E2E/browser hoặc backend/model thật.
- `git diff --check`, kiểm tra cú pháp hai file tests mới, whitespace và liên
  kết tài liệu local đều đạt; xác nhận không còn DB tạm `test_issue136_*`.
- Docker PostgreSQL được khởi động để kiểm chứng. Launcher local tạo một DB
  `test_issue136_<UUID>` riêng và dọn đúng DB do nó sở hữu sau mỗi lượt;
  helpers trong repo tạo/dọn schema UUID, không xóa DB do operator cung cấp.
- JUnit local: `data/processed/issue136/pytest-api-db.xml`, SHA-256
  `5527ebaf95626460f64114650d5709138db3ec3e9ee92a048932207c56ad78d6`.
  Output này nằm ngoài Git; không commit credentials, DB dump hoặc runtime data.
- SHA-256 raw checkout của `backend/app/core/errors.py` khi đo:
  `16a1c67481a6ed82129dc396df45b7776878e4401d4ee10307de3cb8a5e0f253`.

## Lệnh tái lập

Chuẩn bị PostgreSQL test riêng theo [hướng dẫn database](../guides/database.md),
đặt TEST_DATABASE_URL ngoài Git tới database tên bắt đầu `test_`, driver
`postgresql+psycopg`; không trỏ DB nghiệp vụ. Trên Windows có thể dùng host
127.0.0.1. Giữ APP_DEBUG=false để kiểm chứng JSON 500.

Từ `backend/`, chạy riêng các tests mới:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_api_error_envelope.py tests/integration/test_api_commit_recovery.py -q
```

Để tái hiện lỗi parser trước bản sửa, dùng file regression mới trên code base
`a821314`; tám ca parser sẽ nhận HTTP_400. Không cần DB hoặc model cho nhóm unit.

Nhóm hồi quy đã chạy (từ `backend/`, cùng TEST_DATABASE_URL):

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_api_error_envelope.py tests/unit/test_asset_list_errors.py tests/unit/test_asset_detail_errors.py tests/unit/test_health.py tests/unit/test_mock_api.py tests/unit/test_openapi.py tests/unit/test_text_search_contract.py tests/unit/test_text_search_api.py tests/unit/test_text_search_service.py tests/unit/test_text_search_runtime.py tests/unit/test_image_search_api.py tests/unit/test_feedback_api.py tests/unit/test_search_explanation.py tests/unit/test_jobs_api.py tests/unit/test_reindex_api.py tests/unit/test_reindex_builder.py tests/unit/test_config.py tests/unit/test_database_config.py tests/unit/test_asset_api_verification.py tests/integration -q --junitxml=../data/processed/issue136/pytest-api-db.xml
```

Từ `frontend/`:

```powershell
npm test -- src/lib/api/search.test.ts src/features/search/image/client.test.ts src/features/admin/client.test.ts src/features/admin/reindex-client.test.ts --maxWorkers=2
```

## Giới hạn và bàn giao

- Không chạy lại toàn bộ backend unit suite, frontend E2E hoặc benchmark/model
  smoke trong #136. Không dùng kết quả test để thay frozen config hoặc tune.
- Logging request ID và cải tiến worker recovery thuộc các issue W6 riêng;
  không thêm middleware logging, endpoint retry hoặc auto-resume ở đây.
- Việc map lỗi parser về INVALID_REQUEST đưa hành vi về contract 400 hiện có;
  frontend không cần đổi payload hoặc xử lý một mã mới.
- Nhờ Khuê review ma trận/tests và fault injection; Duy đối chiếu ảnh hưởng
  HTTP 400 nếu cần. Không thay module ingestion/retrieval của Huyền/Chi.
- PR/CI/approval/merge còn theo dõi riêng; không tự đóng #136 từ kết quả local.
