# Chẩn đoán runner/jobs/reindex W6 — Issue #138

Áp dụng cho wrapper CLI `app.services.job_runner` và worker reindex #117.
Giữ route, DTO, bốn trạng thái và idempotency hiện có. Không thêm retry/resume,
cancel, force-unlock, activate index hoặc tự sửa trạng thái trong DB.

## Xác định kết quả

- HTTP 202 chỉ xác nhận job đã được tiếp nhận; chưa xác nhận runner thành công.
- Đọc `GET /api/v1/admin/jobs/{job_id}` bằng khóa admin như contract W5.
  `queued → running → succeeded/failed`; progress null là chưa đo, không phải 0%.
- Chỉ tin trạng thái terminal đã đọc từ DB. Artifact có mặt, child exit 0,
  log dự định succeeded hoặc operation trả kết quả chưa thay thế commit cuối.
- Nếu DB không lưu được terminal state, job có thể còn queued/running,
  result/error chưa được ghi và guard tài nguyên vẫn giữ. Không hiển thị hoặc
  tự suy diễn thành succeeded/failed ở UI dựa trên log.

## Mã lỗi và log

Tìm JSON `event=job.failure` theo `job_id` trong log của
`app.services.reindex` hoặc `app.services.job_runner`. Formatter root có thể
thêm prefix; không đổi root logger. Các record này ở level ERROR.

| Trường | Ý nghĩa |
|---|---|
| timestamp, component | UTC ISO-8601 và module phát log |
| job_id | UUID job; null nếu create transaction chưa cung cấp ID đã xác nhận |
| request_id | ID từ context #137 khi còn trong HTTP request; null ở worker/CLI độc lập |
| stage | Giai đoạn đã thất bại, xem bảng dưới |
| error_code | Mã lỗi an toàn; không chứa exception text |
| operation_error_code | Giữ nguyên mã lỗi operation khi việc lưu failed cũng thất bại |
| intended_status | Trạng thái đang cố ghi; **không xác nhận đã commit** |

Không gửi exception, SQL, DB URL, command, path, query/ảnh hoặc khóa admin vào
log này. HTTP X-Request-ID, job_id và request_id nghiệp vụ chống trùng là ba
loại ID riêng. Worker dùng job_id để tra cứu, không tự truyền HTTP context.

| Stage | Mã điển hình | Cách hiểu |
|---|---|---|
| create_state | JOB_STATE_UNAVAILABLE | Không xác nhận tạo job; CLI không chạy operation |
| start_state | JOB_STATE_UNAVAILABLE | Không commit running; không chạy operation |
| scheduling | REINDEX_SCHEDULING_FAILED | Executor không nhận tác vụ; thử ghi failed theo lifecycle hiện có |
| input | REINDEX_INPUT_INVALID | Đầu vào/config không còn hợp lệ khi worker bắt đầu |
| runner_timeout | REINDEX_TIMEOUT | Child vượt timeout cấu hình; artifact có thể chưa hoàn tất |
| runner_exit | INDEXING_FAILED | Child thoát khác 0 |
| artifact | REINDEX_OUTPUT_INVALID | Manifest/hash/profile/search-check/store/count không đạt kiểm chứng |
| runner_output | RUNNER_OUTPUT_INVALID | Outcome thiếu/sai, progress không hợp lệ hoặc báo thành công trái với failed count/exit code/search_verified |
| operation | RUNNER_FAILED hoặc mã runner đã cho phép | Operation lỗi hoặc batch có lỗi; xem report riêng đã kiểm soát quyền |
| failure_state | JOB_STATE_UNAVAILABLE | Operation/scheduling đã lỗi nhưng chưa lưu được failed |
| final_state | JOB_STATE_UNAVAILABLE | Chưa lưu được kết quả cuối; không xác nhận succeeded |

`JOB_STATE_UNAVAILABLE` là mã **chẩn đoán log**, không phải trạng thái mới hoặc
trường mới trong DTO. Runner error code ngoài allowlist được thay bằng
RUNNER_FAILED; message trả API là thông báo cố định an toàn. Kết quả Outcome
không hợp lệ được ghi failed/RUNNER_OUTPUT_INVALID nếu DB còn ghi được;
không đưa result không hợp lệ vào DB. CLI vẫn propagate lỗi persistence để
caller/exit code không báo thành công.

## Job queued/running lâu bất thường

1. Ghi lại job_id, request_id nghiệp vụ đã gửi, timestamps, status và profile.
   Dùng GET detail/list để đọc lại, không POST request mới để thử trạng thái.
   Không đính kèm X-Admin-Key hoặc thông tin đăng nhập vào issue/log chia sẻ.
2. Đối chiếu process Uvicorn/CLI, worker, child runner và timeout. Không kết
   luận job kẹt chỉ dựa trên progress null hoặc thời gian không đổi.
3. Tìm log theo job_id. Phân biệt operation lỗi với start/final/failure state
   không lưu được. Hai record operation + failure_state mô tả cùng một job,
   không phải hai operation đã chạy.
4. Kiểm tra DB có truy cập được và migration đã ở 0004/head bằng môi trường
   được cấp quyền. Chỉ đọc job và resource guard trước khi quyết định xử lý.

   SQL minh họa chỉ đọc, thay UUID bằng job đang kiểm tra:

   ```sql
   SELECT job_id, status, resource_key, created_at, updated_at,
          started_at, finished_at, error->>'code' AS error_code
   FROM jobs
   WHERE job_id = '00000000-0000-0000-0000-000000000000'::uuid;

   SELECT job_id, status, created_at, updated_at
   FROM jobs
   WHERE resource_key = 'clip-candidate200-v1'
     AND status IN ('queued', 'running');
   ```

5. Đối chiếu output riêng `<APP_REINDEX_OUTPUT_ROOT>/<job_id>/`: source/ready,
   index-manifest.json, search-check.json và storage Qdrant. Không coi thư mục
   tồn tại hoặc search-check đơn lẻ là bằng chứng index hoàn chỉnh. Giữ output
   lỗi để chẩn đoán; không ghi đè bằng lần chạy khác hoặc sửa manifest/hash.
   Không mở Qdrant local đang bị process khác giữ để cố lấy quyền ghi.
6. Khi DB phục hồi, GET lại cùng job. Replay cùng request_id chỉ đọc job cũ,
   kể cả failed; không chạy lại. Request_id khác bị 409 khi guard còn active.
   Không sinh request_id mới để né guard khi chưa rõ operation cũ còn chạy.
7. Nếu phải can thiệp, dừng ở bàn giao có bằng chứng cho backend owner,
   Chi (artifact/index) và Khuê (vận hành/UI). Xác định process sở hữu đã dừng,
   tình trạng DB, artifact và tác động guard trước khi thống nhất phương án
   riêng. Issue #138 không cung cấp lệnh UPDATE/DELETE, unlock hoặc chạy lại.

Reindex vẫn dùng profile CLIP candidate 200 của #117, output UUID riêng;
không tự chuyển active index, không thay cấu hình/model/fusion W6 đã khóa.
Timeout không tự resume và không biến artifact dở dang thành index phục vụ.

## Tái hiện trên PostgreSQL test riêng

Đặt TEST_DATABASE_URL tới database `test_*` riêng, driver postgresql+psycopg;
không dùng DB nghiệp vụ. Từ backend/, chạy:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_job_failures.py tests/unit/test_reindex_api.py tests/unit/test_reindex_builder.py tests/unit/test_jobs_api.py tests/integration/test_reindex_stack.py tests/integration/test_jobs_stack.py tests/integration/test_w5_api_coexistence.py -q
```

Tests integration tạo/dọn schema UUID của chính chúng, inject CHECK constraints
trong schema đó để từ chối start/terminal commit. Tests đồng thời dùng Events,
hai app managers và PostgreSQL thật, không dựa vào sleep để đoán kết quả.
Runner/store fixtures được ghi rõ; tests này không thay smoke model thật.

Smoke CLIP thật dùng verifier hiện có, cache/weights đã có, output root mới:

```powershell
.\backend\.venv\Scripts\python.exe scripts/verify_reindex_api.py --cache-ready <cache-ready.json> --baseline-index-root <baseline-root> --output-root <output-riêng> --output <report-riêng.json>
```

Thay placeholder trước khi chạy. Không tải weights/dataset hoặc ghi đè baseline.
Verifier kiểm success/failed child, replay/409, API search trên index mới và
fingerprint baseline; không activate index, không đo benchmark. Báo cáo vẫn
ghi issue 117 do tái sử dụng verifier, phải ghi rõ lượt chạy/bối cảnh #138.

Bằng chứng và giới hạn: [issue138-job-failures.md](../evidence/issue138-job-failures.md).
Contract gốc: [reindex W5](../contracts/reindex-w5.md),
[jobs/status W5](../contracts/jobs-status-w5.md).
