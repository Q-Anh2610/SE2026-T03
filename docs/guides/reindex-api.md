# Vận hành và kiểm chứng reindex — Issue #117

Contract: [reindex-w5.md](../contracts/reindex-w5.md).

Chẩn đoán lỗi runner/artifact/commit và job queued/running bất thường:
[runbook W6 #138](job-failure-diagnostics-w6.md).

## Cấu hình và migration

Giữ `.env` local ngoài Git, bổ sung khóa admin riêng như #115 và các biến:

```dotenv
APP_REINDEX_ENABLED=true
APP_REINDEX_CACHE_READY=C:/path/to/checked-inputs/ready.json
APP_REINDEX_OUTPUT_ROOT=C:/path/to/new-reindex-outputs
APP_REINDEX_TIMEOUT_SECONDS=1800
```

Output root không chứa index đang phục vụ. Cache ready là mảng các record
metadata/image_path/checksum (hoặc preview_sha256), đường dẫn ảnh tương đối
so với thư mục chứa ready.json. Có thể dùng cache 354 đã có nếu đủ candidate
200, cùng thumbnail URL và checksum được xác minh; metadata dùng cho index
mới luôn lấy từ frozen manifest 200, không thay bằng metadata cache 354.

Từ `backend/`:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Revision mới `0004`: thêm jobs.request_id/resource_key nullable và hai unique
indexes. Giữ nguyên jobs cũ và các bảng assets/search_events/feedbacks. Không
tự chạy migration khi startup. Downgrade chỉ trên DB test riêng; xóa các cột
này làm mất thông tin chống trùng của reindex, không dùng để xử lý lỗi vận hành.

Mở `/docs`, Authorize bằng X-Admin-Key, gọi POST `/api/v1/admin/reindex` với UUID
request_id mới. Theo status_url đến terminal. Trong lúc chạy, app vẫn phục vụ
GET jobs/status; không reload/kill process chỉ vì progress đang null.
`succeeded` xác nhận index riêng đã dựng và kiểm tra; không xác nhận active
index đã chuyển. Muốn vận hành index mới cần bước lựa chọn/kiểm chứng cấu hình
riêng, không sửa `.env` tự động trong endpoint.

Các đường dẫn/scripts phải tồn tại trong môi trường chạy. Hướng dẫn này dùng
Uvicorn local; Docker image hiện hành chưa có runner và dữ liệu/cache/model
cần cho reindex, nên mặc định tính năng vẫn tắt ở đó.

## Tests

Đặt TEST_DATABASE_URL tới PostgreSQL riêng tên test_*, dùng host 127.0.0.1 trên
Windows nếu localhost bị phân giải IPv6. Không commit URL/credentials.
Từ backend/:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_reindex_api.py tests/unit/test_reindex_builder.py tests/unit/test_jobs_api.py tests/integration/test_reindex_stack.py tests/integration/test_jobs_stack.py tests/integration/test_database.py -q
.\.venv\Scripts\python.exe -m app.export_openapi
```

Tests worker fixture không thay smoke CLIP thật. Bao phủ duplicate/replay,
request khác khi bận, hai app managers đồng thời, DB reject trước chạy, runner
lỗi và commit cuối thất bại, migration round-trip/drift/giữ job cũ, cache URL/
checksum/path/duplicate/missing và flow download CLI cũ.

## Smoke HTTP thật, candidate 200

Model pinned phải có sẵn trong cache, không tự tải weights. TEST_DATABASE_URL
phải là DB test riêng. Từ gốc repo, thay đường dẫn bằng bộ đã có trên máy:

```powershell
.\backend\.venv\Scripts\python.exe scripts/verify_reindex_api.py --cache-ready data/processed/issue65/index-1718ec3c49a0/ready.json --baseline-index-root data/processed/issue65/index-1718ec3c49a0
```

Verifier tạo schema UUID, nạp frozen metadata 200 vào DB test, khởi chạy
Uvicorn/HTTP, POST reindex thật, kiểm replay/conflict, poll terminal, tạo một
lượt lỗi bằng cache fixture không hợp lệ, rồi mở API text search riêng trên
index mới và kiểm versions/score_type/event. Fingerprint index baseline trước/
sau phải không đổi. Không seed vào semantic_search hoặc chạy benchmark.
Server và schema test tự sinh được dọn, database test do operator cung cấp vẫn
được giữ lại theo helper; index mới và runtime report
giữ ngoài Git tại data/processed/reindex/<job UUID> và
data/processed/issue117/reindex-http.json.

Việc mở API test riêng trên index mới là kiểm chứng sau rebuild; endpoint
reindex không chuyển active index của ứng dụng đang phục vụ.

Kết quả thực tế được ghi tại [bằng chứng #117](../evidence/issue117-reindex.md).
