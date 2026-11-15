# Reindex API W5 — Issue #117

Owner backend: Quỳnh Anh. Chi review runner/model/index, Huyền review frozen
input, Khuê tiếp nhận Admin Reindex UI #104. Đây là phạm vi được tác giả triển
khai theo yêu cầu #117; **chưa có xác nhận riêng cho #117 của ba owner**.

## Phạm vi cố định

- Một profile `clip-candidate200-v1`: CLIP text-to-preview trên đúng candidate
  200 của `home-interior-clear-200-v3`.
- Source: `data/manifests/objaverse_200.json`, SHA-256
  `9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`.
- Model `openai/clip-vit-base-patch32`, revision
  `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`, dimension 512, preprocessing
  `clip-slow-processor-rgb-l2-v1`, Cosine/L2; config
  `clip-text-exact-all-filtered-v1-k200`.
- Dựng index mới vào thư mục UUID riêng. Không rebuild đè collection/storage
  cũ, sửa assets PostgreSQL, đổi `.env` hoặc chuyển active index.
- Chưa tạo ImageIndexManifest riêng, chưa bật SigLIP2/E5/RRF hoặc mở rộng
  dataset. Search mới được smoke riêng trước khi nghiệm thu.
- Đọc preview cache do operator cấu hình, kiểm URL/checksum trước embedding;
  HTTP không tải URL tùy ý hoặc nhận path/command/model từ người dùng.

## Route và request

`POST /api/v1/admin/reindex`, header `X-Admin-Key` như jobs/status #115.
API mặc định tắt; phải cấu hình `APP_REINDEX_ENABLED=true` và cache phù hợp.

```json
{
  "request_id": "b0c674d2-1286-401f-b73b-72cae159fcad",
  "profile": "clip-candidate200-v1"
}
```

`request_id` UUID bắt buộc, frontend tạo một lần cho một ý định chạy reindex.
`profile` chỉ nhận giá trị trên, mặc định cũng là giá trị này. Tham số body lạ,
UUID sai, profile/model/snapshot/path/URL/command tùy ý trả 400. Không thay đổi
request/search/filter contract công khai.

## Thành công, retry và chạy đồng thời

Request mới hợp lệ: **202 Accepted**, sau khi job queued đã commit:

```json
{
  "job_id": "a0b674d2-1286-401f-b73b-72cae159fcad",
  "status": "queued",
  "status_url": "/api/v1/admin/jobs/a0b674d2-1286-401f-b73b-72cae159fcad",
  "reused": false
}
```

Worker chạy ngoài request HTTP. Status trong response là snapshot lúc nhận
request; UI lấy trạng thái mới nhất từ `status_url` hoặc jobs list #103.

- Gửi lại **cùng request_id**: **200**, `reused=true`, trả cùng job, kể cả job đã
  kết thúc; không chạy lại. Cần giữ ID khi retry do timeout/mất response.
- Request ID khác trong lúc cùng profile queued/running: **409**
  `REINDEX_IN_PROGRESS`, không tạo job mới. UI theo dõi jobs/status để biết lượt
  đang chạy, không tự gửi lặp liên tục.
- Sau terminal, người quản trị muốn chạy lượt mới phải tạo request_id mới.
  Replay một job failed vẫn trả job failed cũ; không ngầm retry operation.
- PostgreSQL advisory transaction lock serialize bước nhận request, unique
  request ID và partial unique index bảo vệ tài nguyên qua nhiều API process.
  Không dựa riêng vào biến lock trong RAM.

## Jobs/status và kết quả

Job có `kind=indexing`, `runner=reindex.clip_candidate200`, vòng đời
queued → running → succeeded/failed. Giữ GET `/api/v1/admin/jobs` và
`GET /api/v1/admin/jobs/{job_id}` cùng auth/envelope/pagination #115.

Khi running, progress chưa được đo theo batch nên processed/total/percent là
null. Chỉ sau khi xác minh đầy đủ mới ghi processed=200, total=200, percent=100.
Job failed không được gán succeeded hoặc số lượng đã xử lý giả.

Result của job succeeded có thêm các trường nullable sau (bên cạnh trường cũ):

| Trường | Giá trị/ý nghĩa |
|---|---|
| index_version | `reindex-clip-<job UUID hex>`, riêng cho từng lượt |
| model_version | Model ID@revision thực tế |
| dataset_snapshot | Snapshot kèm SHA-256 source |
| asset_count / point_count | Đều 200, kiểm manifest và storage sau reopen |
| input_count / succeeded / failed / skipped | 200 / 200 / 0 / 0 khi toàn bộ index đã xác minh |
| index_ref | `reindex-<job UUID hex>`, tham chiếu opaque, không phải đường dẫn/URL tải file |
| index_manifest_sha256 | Hash manifest đầu ra thực tế |
| manifest_sha256 | Giữ nghĩa cũ: hash manifest nguồn |
| search_verified | true sau direct service search trên index mới đạt |
| exit_code | 0 từ child runner, chưa đủ để tự kết luận succeeded |

Những khóa mới là null cho job cũ/ingestion/CLI cũ chưa cung cấp dữ liệu.
Không trả path local, command, SQL, stdout/stderr hoặc exception text.
Client #103 hiện chấp nhận thuộc tính result bổ sung; Khuê cần bổ sung type và
hiển thị index/version/count cho #104 nếu muốn sử dụng các trường mới.

## Điều kiện succeeded

Tái dùng `scripts/prepare_text_search_index.py` và modules embedding/store của
dự án. Lệnh child cố định, timeout mặc định 1800 giây. Cache hợp lệ, đủ 200
embedding/upsert, manifest mới đúng source/model/config/version, storage đủ
200 points và direct text search trả đủ 200 candidates cùng versions mới
đều phải đạt. Chỉ sau commit trạng thái cuối vào DB mới thấy succeeded qua API.
Index không được tự đưa vào luồng search đang phục vụ.

## Lỗi

HTTP dùng envelope `{"error":{"code":"...","message":"...","details":[]}}`:

| HTTP | code | Ý nghĩa |
|---|---|---|
| 400 | INVALID_REQUEST | Body/UUID/profile không hợp lệ |
| 403 | ADMIN_ACCESS_DENIED | Thiếu/sai khóa quản trị |
| 409 | REINDEX_IN_PROGRESS | Có lượt khác đang giữ tài nguyên |
| 500 | INTERNAL_ERROR | Không ghi được yêu cầu; không giả trả 202 |
| 503 | ADMIN_API_UNAVAILABLE | Chưa cấu hình khóa admin |
| 503 | REINDEX_UNAVAILABLE | Reindex tắt hoặc cache/source/worker chưa sẵn sàng |

Sau khi đã nhận 202, lỗi operation được đọc qua GET job response 200 với
status=failed và error.code: INDEXING_FAILED, REINDEX_TIMEOUT,
REINDEX_OUTPUT_INVALID, RUNNER_FAILED hoặc REINDEX_SCHEDULING_FAILED.
Không coi 202 hay GET thành công là job đã succeeded.

## Giới hạn vận hành

Worker local một thread/app, không có broker/Redis/Celery. Chạy bằng Python
Uvicorn có quyền đọc repo scripts/source/cache và ghi output root. Đóng app
bình thường chờ worker kết thúc rồi mới dispose engine. Docker image khung
chưa đóng gói scripts/data/cache/model cho reindex; không bật tính năng trong
container thiếu các tài nguyên đó. Bàn giao Docker đầy đủ là phần vận hành riêng.

Không có auto-resume/cancel/force-unlock. Nếu process bị kill hoặc DB không ghi
được trạng thái cuối, job có thể giữ queued/running và chặn request mới. Cần
operator xác minh worker đã dừng và kết quả trước khi sửa trạng thái bằng một
thao tác quản trị có chủ đích; không xóa khóa tự động khi chưa biết process khác
còn chạy không. Không báo operation đã rollback nếu chỉ transaction job lỗi.

## Bàn giao cần xác nhận

- [ ] Chi: runner mở rộng dùng cache, pinned CLIP/config, index version riêng,
  kiểm manifest/count/search và phạm vi không activate/không image/E5/RRF.
- [ ] Huyền: frozen candidate 200 và quy tắc URL/checksum cache, không ghi lại
  metadata/ingestion_status/searchable trong DB nghiệp vụ.
- [ ] Khuê (#104): POST body/request_id, 202/200/409, auth, polling jobs/status,
  trường result mới và phân biệt dựng index với activate index.

Hướng dẫn chạy và bằng chứng: [reindex-api.md](../guides/reindex-api.md).
