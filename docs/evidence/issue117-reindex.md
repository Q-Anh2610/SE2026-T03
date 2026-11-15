# Bằng chứng local reindex API — Issue #117

Ngày 15/11/2026, nhánh `feat/117-reindex-api`. Base
`ae3f33a1f8231a5aeea49170c1f168a1cb04b153`, working tree dirty khi đo.
Đây là bằng chứng local của tác giả, không phải CI/review hay xác nhận tiếp
nhận của Chi/Huyền/Khuê.

Contract/lệnh chạy: [reindex-w5.md](../contracts/reindex-w5.md),
[hướng dẫn vận hành](../guides/reindex-api.md).

## Kiểm thử

- 263 tests backend liên quan đạt, không skip, 33,81 giây: reindex API/builder,
  jobs/status, migration/database/config và hồi quy text/image search,
  explanation, events, feedback, mock/OpenAPI/runtime.
- 106 tests frontend Admin contract/client/JobStatusCard hiện có đạt trên ba
  files, 8,28 giây. Không thay frontend source, chưa nghiệm thu UI reindex #104.
- Export cả bốn OpenAPI thành công; các tests spec/examples đạt.
- `git diff --check` đạt. Không chạy lại toàn bộ backend suite hoặc benchmark.

Backend chạy với TEST_DATABASE_URL tới PostgreSQL test_* riêng. Tests fixture
worker không dùng model thật; kiểm chứng CLIP thật được ghi riêng bên dưới.

Các trường hợp chính: auth và validation trước DB, reindex disabled, chỉ một
request tạo job khi bốn request trùng qua hai app managers, 409 cho request ID
khác khi bận, replay sau terminal/restart không chạy lại, lỗi runner/timeout/
artifact, DB reject trước thực thi, commit cuối lỗi không báo succeeded, khóa
unique tài nguyên và migration 0003→0004 giữ nguyên lịch sử job.

Tests builder kiểm cache checksum/URL/path/ID trùng/thiếu, không download trong
chế độ cache, không ghi đè output đã tồn tại, và giữ flow download CLI cũ.

## Smoke HTTP + CLIP/Qdrant/PostgreSQL thật

Report quan sát `2026-11-15T01:42:50.884749+00:00` (08:42:50 Asia/Bangkok),
status **passed**. Python 3.13.7, PostgreSQL 17 Docker local, Uvicorn qua TCP
localhost, CLIP CPU offline từ cache.

Đầu vào cố định: candidate 200 `home-interior-clear-200-v3`, source SHA-256
`9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`.
Cache 354 có đủ 200 IDs/thumbnail URL cần dùng; từng ảnh kiểm SHA-256 rồi copy
vào output mới, metadata index mới lấy từ frozen source 200.

- POST hợp lệ trả 202/job queued; poll quan sát running rồi succeeded.
- Job `f393025b-c94f-4cb3-924e-0127422678e8` dựng đủ 200 asset/200 points;
  result input_count=200, succeeded=200, failed=0, skipped=0; progress 200/200.
- Index version `reindex-clip-f393025bc94f4cb3924e0127422678e8`.
- Model `openai/clip-vit-base-patch32@3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`,
  config `clip-text-exact-all-filtered-v1-k200`, snapshot/hash đúng frozen input.
- Index manifest SHA-256
  `5f06be85ae94c2740aab40340f26a961f73764e4d1fe4e204407b9e91d72b98e`.
- Child direct search và parent reopen kiểm chứng count/config/version đạt.
- Gửi lại request ID trả 200/cùng job, không tạo thêm lượt dựng; request ID khác
  khi đang chạy trả 409. Thiếu khóa trả 403, profile sai trả 400.
- Tạo một lượt lỗi bằng cache fixture rỗng trên app smoke riêng: child runner
  thật từ chối cache, job ghi failed/INDEXING_FAILED, không có result giả.
- Mở API text search riêng trỏ index mới và DB test có đúng frozen 200 metadata:
  HTTP 200, 12 kết quả, score_type=cosine, versions khớp index mới. Luồng này
  lưu event theo API hiện có; không chuyển cấu hình của app reindex/active API.
- Fingerprint index baseline trước/sau giữ nguyên:
  `4ec8a57d3532cb126ebca29d818d6e85aa1c36231eb88b2d208f6101b559c687`.

Schema/DB test do launcher local sở hữu đã dọn; server dừng. Index mới giữ ở
`data/processed/reindex/<job UUID>` và report đầy đủ/module hashes ở
`data/processed/issue117/reindex-http.json`, đều là runtime data ngoài Git.
Script chia sẻ dùng database test có sẵn và chỉ dọn schema riêng; không xóa DB
do operator cung cấp. Không ghi vào DB nghiệp vụ hoặc sửa source/index cũ.

## Giới hạn bàn giao

- Chưa có xác nhận riêng #117 của Chi/Huyền/Khuê; checklist trong contract giữ
  chưa tích. UI kích hoạt reindex thuộc #104; tests frontend hiện có không thay
  smoke UI của endpoint mới.
- Chỉ hỗ trợ local Uvicorn với scripts/source/cache/model sẵn; Docker image
  khung chưa đóng gói đủ các tài nguyên reindex, tính năng mặc định tắt.
- Không activate index, không tạo image manifest riêng hoặc tích hợp E5/RRF/
  SigLIP2. Không có benchmark chất lượng/latency mới.
- Worker local không phải hàng đợi phân tán. Kill process/commit cuối lỗi có
  thể để queued/running và giữ guard tài nguyên; không auto-resume/force-unlock.
- Retry/replay API là chống gửi trùng theo request ID, không phải cơ chế đồng
  bộ nghiệp vụ hoặc retry operation bị lỗi một cách tự động.
