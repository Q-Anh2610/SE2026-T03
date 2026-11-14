# Chạy và bàn giao jobs/status — Issue #115

Contract/JSON/lỗi: [jobs-status-w5.md](../contracts/jobs-status-w5.md).
OpenAPI được xuất vào cả bốn spec hiện có bởi `app.export_openapi`.
Không thay contract search/feedback hoặc dependencies; thêm bảng `jobs`
và migration `0003` sau `0002`. Không tự chạy migration lúc startup.

## Khởi chạy local

Từ gốc repo, giữ cấu hình `.env` hiện có. Thêm `APP_ADMIN_API_KEY` bằng khóa
local riêng >=32 ký tự. Có thể sinh bằng:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
docker compose -f docker-compose.yml up -d --wait postgres
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Migration chỉ tạo bảng/index/constraints mới, không sửa assets/search_events/
feedbacks. `downgrade 0002` xóa lịch sử jobs, chỉ làm trên DB test riêng khi cần
kiểm chứng rollback; không tự hạ schema ở DB dùng chung.

Mở `/docs`, **Authorize → AdminKey** rồi thử hai GET tại tag `admin jobs`.
Danh sách ban đầu rỗng là hợp lệ. Không cấu hình khóa: 503; thiếu/sai khóa: 403.
`GET /healthz` vẫn công khai và không chứng minh jobs/DB đã sẵn sàng.

## Chạy ingestion có ghi lịch sử job

Chạy từ thư mục `backend/`, dùng tên report mới mỗi lượt:

```powershell
.\.venv\Scripts\python.exe -m app.services.job_runner ingestion --manifest ../data/manifests/objaverse_200.json --output-dir ../data/raw/issue115/previews --report ../data/processed/issue115/batch-1.json --limit 1 --persist-db
.\.venv\Scripts\python.exe -m app.services.job_runner ingestion --manifest ../data/manifests/objaverse_200.json --output-dir ../data/raw/issue115/previews --report ../data/processed/issue115/batch-2.json --previous-report ../data/processed/issue115/batch-1.json --limit 1 --persist-db
```

Lệnh tải đúng subset được chọn. Lượt sau dùng cache được kiểm tra checksum,
không tạo trùng asset theo cơ chế upsert hiện có; mỗi lượt có job_id mới.
Bỏ `--persist-db` nếu chỉ muốn tải preview/report, kết quả ghi rõ
`persistence=local_files_only`. CLI in job_id/status, exit 0 khi succeeded,
exit 1 khi job failed hoặc DB không ghi được trạng thái. Có thể mở Swagger
ở terminal khác để xem running, sau đó xem kết quả kết thúc.

## Chạy indexing có ghi lịch sử job

Từ `backend/`, sau khi chuẩn bị model cache theo hướng dẫn text search:

```powershell
.\.venv\Scripts\python.exe -m app.services.job_runner indexing --manifest ../data/manifests/objaverse_200.json --snapshot home-interior-clear-200-v3 --download-previews
```

Đây là script CLIP standalone đã có; bắt buộc xác nhận tải preview.
Script tạo output mới tại `data/processed/issue65/index-<uuid>`, không chuyển
active index của service. Không tự chạy lệnh này chỉ để thử UI nếu chưa cần
dựng index. Indexing progress giữ null; exit_code 0 mới là succeeded.
Việc kích hoạt/reindex qua HTTP và quản lý active index thuộc #117.

## Kiểm thử và smoke tái lập

Đặt `TEST_DATABASE_URL` tới PostgreSQL riêng có tên `test_*` và host
`127.0.0.1` trên Windows. Không dùng DATABASE_URL phát triển làm URL test.
URL chứa credentials chỉ để trong môi trường terminal, không ghi vào tài liệu.
Các tests và smoke tạo schema UUID riêng rồi xóa đúng schema đó.

Từ `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_jobs_api.py tests/integration/test_jobs_stack.py tests/integration/test_database.py -q
.\.venv\Scripts\python.exe -m app.export_openapi
```

Smoke từ gốc repo, đồng ý tải **1 preview thật**:

```powershell
.\backend\.venv\Scripts\python.exe scripts/verify_jobs_api.py --live-ingestion 1
```

Smoke chạy Uvicorn/HTTP thật, migration/check, ingestion/DatabaseWriter thật,
kiểm tra trạng thái running từ request khác, tải/cache/upsert khi chạy lại,
failed khi manifest thiếu, auth/filter/pagination và lịch sử sau restart API.
Không dùng model, Qdrant hoặc Admin UI trong smoke này. Report local:
`data/processed/issue115/jobs-api-report.json` (không commit runtime data).
Tests cache dùng ảnh fixture tự tạo và pipeline thật; không gọi chúng là
bằng chứng tải Objaverse thật. Tests indexing dùng subprocess stub, không
chứng minh đã chạy CLIP indexing thật.

## Bàn giao

Kiểm chứng local ngày 14/11/2026, Python 3.13.7, PostgreSQL 17 (Docker):

- 68 tests liên quan API/OpenAPI/jobs/migration đạt, không skip; bao gồm upgrade
  từ 0002 giữ nguyên asset, round-trip migration và kiểm tra schema drift.
- Smoke Uvicorn/HTTP với manifest `objaverse_200.json`, giới hạn 1 asset thật:
  lượt đầu downloaded=1, failed=0; lượt sau skipped=1, failed=0; PostgreSQL vẫn
  chỉ có một asset. Hai lượt đều quan sát được running qua HTTP.
- Một lượt manifest không tồn tại được ghi failed với lỗi an toàn;
  khởi động lại API vẫn đọc được đủ ba lượt từ PostgreSQL.
- Chưa có bằng chứng CLIP indexing thật hoặc Admin UI thật trong #115;
  không dùng tests stub để thay các xác nhận đó.
- Hồi quy toàn backend: lượt đầu 1091 passed/8 failed; 5 tests OpenAPI đã đạt
  khi chạy lại với spec/schema cuối cùng. Còn 3 tests tại
  `test_issue91_query_artifact.py` lỗi byte/hash của bản checkout local:
  `queries.csv` có 7925 bytes/74 CRLF, trong khi artifact khóa yêu cầu 7851
  bytes/LF. Blob `HEAD:data/benchmark/queries.csv` khớp hash khóa
  `e202a0dc62406826ec29a2946d489c359a222133e6c530a9954832760d965470`.
  Không sửa query, qrels, manifest hoặc test benchmark trong #115; đây chưa
  phải kết quả toàn suite xanh trên bản checkout Windows hiện tại.

Các thay đổi local phục vụ #115; review và xác nhận owner vẫn riêng:

- Huyền/Chi: xem bảng nguồn runner và các giới hạn tại contract, xác nhận hoặc
  góp ý cách ghi vòng đời; chưa sửa module ingestion/search của hai người.
- Khuê: nối UI tại #103 theo OpenAPI/DTO, dùng khóa admin lúc chạy nội bộ,
  xử lý null progress và job failed; xác nhận tiếp nhận contract.
- Không tick xác nhận owner hoặc đóng #115 chỉ từ việc tests local đạt.
- #117 triển khai kích hoạt reindex riêng; không cần chờ #117 để đọc các job
  do CLI wrapper đã ghi vào PostgreSQL.
