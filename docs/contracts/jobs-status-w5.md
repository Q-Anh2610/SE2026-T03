# Jobs/status API W5 — Issue #115

Backend: Quỳnh Anh. Bên nhận Admin UI: Khuê tại #103 (tách từ #70).
Phạm vi #115 đã được Huyền/Chi/Khuê xác nhận tại
[PR #119](https://github.com/Q-Anh2610/SE2026-T03/pull/119), gồm giới hạn khóa
admin local/nội bộ. Phần mở rộng reindex #117 cần xác nhận riêng, xem
[contract reindex](reindex-w5.md).

Mở rộng #117 giữ routes/fields cũ, thêm các trường result nullable về
index/version/count. Chỉ job `reindex.clip_candidate200` sau xác minh đầy đủ
mới ghi progress 200/200. CLI indexing cũ vẫn có progress null như dưới đây.

## Route và quyền truy cập

| Method/route | Ý nghĩa |
|---|---|
| `GET /api/v1/admin/jobs` | Danh sách lịch sử job từ PostgreSQL |
| `GET /api/v1/admin/jobs/{job_id}` | Chi tiết job, `job_id` là UUID |

Chỉ đọc; không có HTTP tạo job, retry job hoặc kích hoạt reindex ở #115.
Các thao tác kích hoạt thuộc #117; UI reindex theo #104.

Cả hai route yêu cầu header `X-Admin-Key` khớp `APP_ADMIN_API_KEY`.
Backend dùng so sánh constant-time; thiếu/sai khóa trả cùng lỗi 403.
Chưa cấu hình khóa: 503, không mở quyền đọc và không kết nối DB.
Khóa là secret tối thiểu 32 ký tự; không đưa vào Git, URL, logs hoặc biến
`VITE_*`/bundle frontend. Swagger `/docs` có nút **Authorize** cho `AdminKey`.
Phương án này phục vụ admin nội bộ/local, chưa có tài khoản, role hay SSO.
Khi triển khai từ xa cần HTTPS và cấu hình truy cập nội bộ thích hợp.

## Query và sắp xếp

| Query | Kiểu/giới hạn | Mặc định |
|---|---|---|
| `kind` | `ingestion` hoặc `indexing` | Không lọc |
| `status` | `queued`, `running`, `succeeded`, `failed` | Không lọc |
| `page` | Số nguyên >= 1 | 1 |
| `limit` | Số nguyên 1–50 | 12 |

Filters kết hợp AND **trước** phân trang. Tham số lạ hoặc giá trị sai trả 400.
Sắp xếp `created_at DESC, job_id DESC`; UUID là tie breaker, không phải thứ tự
thời gian. Count/trang trong một request dùng cùng snapshot DB. Polling có thể
thêm job mới vào đầu danh sách; phân trang theo page không đóng băng snapshot
giữa nhiều request. Trang vượt phạm vi trả items rỗng, vẫn giữ total thật.

## Response

Danh sách (ví dụ minh họa, không phải số liệu benchmark):

```json
{
  "items": [{
    "job_id": "a0b674d2-1286-401f-b73b-72cae159fcad",
    "kind": "ingestion",
    "runner": "ingestion.run_batch",
    "status": "succeeded",
    "created_at": "2026-11-14T08:00:00Z",
    "updated_at": "2026-11-14T08:01:00Z",
    "started_at": "2026-11-14T08:00:01Z",
    "finished_at": "2026-11-14T08:01:00Z",
    "progress": {"unit": "assets", "processed": 2, "total": 2, "percent": 100.0},
    "result": {
      "persistence": "postgresql",
      "input_count": 2, "succeeded": 1, "failed": 0, "skipped": 1,
      "manifest_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "exit_code": null
    },
    "error": null
  }],
  "pagination": {"page": 1, "limit": 12, "total": 1, "pages": 1, "has_next": false},
  "mock": false
}
```

Detail: `{"job": <cùng object job bên trên>, "mock": false}`.
Empty list: `items=[]`, `total=0`, `pages=0`, `has_next=false`.

Các khóa trong object job luôn có mặt. Timestamp có timezone (UTC), chuỗi
ISO-8601; `started_at`, `finished_at`, `result`, `error` có thể null theo vòng đời.
`result` khác null luôn có các khóa trong ví dụ; giá trị chưa đo được là null.
Không trả đường dẫn local, command, stdout/stderr, SQL hoặc exception message.
`mock=false` nghĩa đọc lịch sử PostgreSQL; không khẳng định tất cả job đã dùng
dữ liệu production hoặc đã cập nhật index đang phục vụ search.

## Vòng đời, kết quả và progress

- `queued`: đã commit bản ghi, chưa bắt đầu operation. CLI hiện chạy ngay,
  không có hàng đợi/broker nên trạng thái này thường ngắn.
- `running`: đã commit thời điểm bắt đầu trước khi gọi runner thực tế.
- `succeeded`: runner hoàn tất và trạng thái cuối đã commit. Với ingestion,
  không có asset failed. `result.succeeded` đếm preview downloaded;
  `result.skipped` đếm preview cache được kiểm tra và tái sử dụng.
- `failed`: exception, gián đoạn bắt được hoặc có asset failed; partial failure
  vẫn giữ summary thật. Không đánh dấu thành công cho cả batch khi có lỗi asset.

`progress.unit="assets"`; processed là số asset đã xử lý, **bao gồm asset lỗi**,
không phải số asset thành công. `percent=round(processed/total*100,2)` khi biết
cả hai và total > 0. Không biết số đếm, hoặc total=0: percent=null.
Job failed có thể đã xử lý 100% input; UI phải đọc `status`/`error` để kết luận.

Runner ingestion hiện chỉ trả summary lúc kết thúc: khi running, cả processed,
total, percent là null; cuối lượt mới ghi số đếm. Không có tiến độ theo asset
trong thời gian chạy. Indexing hiện cũng không có callback số đếm: các trường
này giữ null, kể cả khi thành công; chỉ ghi exit_code thật.
UI nên hiển thị trạng thái chưa xác định tiến độ khi percent=null.

`result.persistence` cho ingestion: `postgresql` nếu dùng `--persist-db`,
`local_files_only` nếu chỉ tải preview/report. Thành công tải preview không
có nghĩa embedding/index hoặc toàn hệ thống đã searchable.

## Nguồn trạng thái thực tế

Nguồn API là bảng `jobs`, migration `0003`. Nguồn ghi là wrapper CLI
`app.services.job_runner`, tái sử dụng:

| kind/runner | Cách thực thi | Giới hạn |
|---|---|---|
| ingestion / `ingestion.run_batch` | Pipeline của Huyền; tùy chọn DatabaseWriter PostgreSQL | Không sửa pipeline hoặc suy diễn trạng thái từ từng dòng assets |
| indexing / `prepare_text_search_index` | Script CLIP standalone hiện có, tiến trình con cố định | Output UUID mới; không đổi active index; chưa bao phủ runner E5/SigLIP2 |

Chạy CLI ingestion cũ hoặc script indexing trực tiếp **không tự tạo job**.
Không nhập lại báo cáo cũ thành job giả hoặc tự tổng hợp lịch sử chưa được ghi.
Wrapper chưa có scheduler, cancel, retry endpoint, timeout/recovery tự động.
Nếu process bị kill/mất điện, job có thể giữ running; API không tự đoán failed.
Nếu DB lỗi trước ghi running, không chạy operation. Nếu operation đã chạy nhưng
ghi kết thúc lỗi, CLI báo lỗi và không xác nhận thành công; side effects của
runner có thể đã tồn tại. Jobs/asset writes và Qdrant không là một transaction
chung. Chạy lại tạo job UUID mới, giữ lịch sử lượt trước; ingestion cache/upsert
theo runner cũ. Không thêm unique theo manifest vì mỗi lượt là một job khác nhau.

## Lỗi và retry của UI

Envelope giống API hiện có:

```json
{"error":{"code":"JOB_NOT_FOUND","message":"Không tìm thấy job.","details":[]}}
```

| HTTP | code | UI xử lý |
|---|---|---|
| 400 | `INVALID_REQUEST` | Sửa tham số/UUID; details chỉ field và thông báo chung |
| 403 | `ADMIN_ACCESS_DENIED` | Yêu cầu khóa đúng; không retry liên tục |
| 404 | `JOB_NOT_FOUND` | Thông báo job không tồn tại |
| 500 | `INTERNAL_ERROR` | Có thể retry việc đọc sau; không fallback fixture |
| 503 | `ADMIN_API_UNAVAILABLE` | Backend cần cấu hình khóa; retry sau khi khắc phục |

Route không tồn tại: 404 `HTTP_404`, cùng envelope. Không trả 422.
Lỗi bên trong job là **dữ liệu của response 200** (`job.status=failed`),
khác với lỗi HTTP khi tải danh sách. Mã job: `RUNNER_FAILED`,
`BATCH_PARTIAL_FAILURE`, `INDEXING_FAILED`; thông báo an toàn, không đưa bí mật
từ exception/report ra API. Retry tải danh sách không chạy lại job.

## Điểm cần owner xác nhận trước nghiệm thu chung

- [x] Huyền: dùng `run_batch` qua wrapper và summary/status/persistence như trên;
  xác nhận giới hạn tiến độ chỉ có ở cuối lượt.
- [x] Chi: runner CLIP standalone là nguồn indexing ban đầu; xác nhận exit_code,
  giới hạn progress null, phạm vi runner khác và việc không đổi active index.
- [x] Khuê (#103): tiếp nhận route/DTO, auth header, null progress, pagination,
  job failed khác lỗi HTTP và không fallback fixture.
- [x] Khuê: xác nhận khóa admin cho local/nội bộ; chưa thay xác nhận triển khai từ xa.

Hướng dẫn migration/chạy/kiểm chứng: [jobs-status-api.md](../guides/jobs-status-api.md).
