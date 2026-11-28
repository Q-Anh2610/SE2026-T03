# API v1 — trạng thái hiện hành và các chế độ chạy

Đối chiếu W7 / Issue #145 với backend/frontend đã merge. Đây là tài liệu đầu
mối cho API hiện có; các contract chuyên biệt bên dưới mô tả chi tiết hơn.
Không coi các ghi chú bàn giao W1/W3 trong tài liệu lịch sử là trạng thái hiện tại.

## Chọn đúng chế độ và OpenAPI

Base path nghiệp vụ `/api/v1`; JSON UTF-8, upload ảnh dùng multipart/form-data.
`GET /openapi.json` trên **origin backend** mô tả đúng routes/schemas của tiến
trình đang chạy; `/docs` là Swagger UI. Các file export trong Git là cấu hình
đối chiếu xác định, không tự cấu hình server hoặc chứng minh model/DB đã sẵn sàng.

| File trong docs/ | Text | Image | Feedback | Assets |
|---|---|---|---|---|
| [openapi.json](../openapi.json) | mock | mock | RAM/mock | PostgreSQL |
| [openapi-text-search.json](../openapi-text-search.json) | service | mock | RAM/mock | PostgreSQL |
| [openapi-image-search.json](../openapi-image-search.json) | service | service | RAM/mock | PostgreSQL |
| [openapi-feedback.json](../openapi-feedback.json) | service | service | PostgreSQL | PostgreSQL |

Các spec đều có health, jobs/status và reindex routes; route hiện diện không
đồng nghĩa quyền admin/reindex đã được bật. Exporter dùng development, bật mock
và không phụ thuộc file `.env`. Feedback thật cần chọn `APP_FEEDBACK_SOURCE=database`;
chỉ bật search service không tự đổi feedback RAM sang PostgreSQL.

- `APP_TEXT_SEARCH_SOURCE=service` / `APP_IMAGE_SEARCH_SOURCE=service` chọn
  retrieval CLIP thật và search event PostgreSQL; thiếu dependency trả lỗi,
  không fallback fixture. Cấu hình/index/cache phải được bàn giao riêng.
- Mock search/feedback chỉ đăng ký khi `APP_MOCK_API_ENABLED=true` và
  `APP_ENV` khác production. Chọn mock nhưng tắt mock/ở production làm route
  tương ứng vắng mặt (404), không tự bật service.
- Assets mặc định đọc DB. Fixture chỉ được chọn khi bật mock, chọn
  `APP_ASSET_LIST_SOURCE=fixture`, cả search đều không chọn service và feedback
  không chọn database. Production luôn đọc DB.
- Có thể cấu hình các mode độc lập, nhưng feedback cần khớp nguồn event.
  Để dùng feedback thật cho cả text/ảnh, chọn profile của openapi-feedback.json.
- Cấu hình fusion W6/E5/RRF đã khóa cho evaluation không tự thay baseline của
  HTTP API. API service hiện tại dùng CLIP, score_type=cosine.

## Endpoints và response

| Method / URL | Request | Thành công |
|---|---|---|
| GET /healthz | Không có | 200: `{"status":"ok"}`; chỉ liveness |
| GET /api/v1/assets | Query page, limit và filters | 200: items, pagination, mock |
| GET /api/v1/assets/{asset_id} | Asset ID | 200: asset, mock |
| POST /api/v1/search/text | JSON query, filters, page, limit | 200: query_id, search_event_id, query, results, versions, pagination, mock |
| POST /api/v1/search/image | Multipart image, filters, page, limit | 200: cấu trúc search chung |
| POST /api/v1/feedback | JSON search_event_id, asset_id, relevance | 201: feedback_id, search_event_id, asset_id, relevance, created_at, storage, mock |
| GET /api/v1/admin/jobs | Query kind, status, page, limit | 200: items, pagination, mock=false |
| GET /api/v1/admin/jobs/{job_id} | UUID job | 200: job, mock=false |
| POST /api/v1/admin/reindex | JSON request_id UUID, profile tùy chọn | 202: job_id, status, status_url, reused=false; replay 200/reused=true |

Assets giữ metadata nullable: description/category/face_count/thumbnail_url/
source_url/author/license có thể null; tags/formats là arrays. Name thiếu dùng
asset_id làm nhãn. Chỉ trả URL HTTP(S) không chứa credentials; path local trả
null. API không tải URL tùy ý và chưa có route phục vụ model/preview local.
List DB dùng asset_id ASC; không đồng nghĩa mọi asset đã searchable.
`mock=false` xác định nguồn DB/service, không chứng minh bản ghi seed là asset thật.

Chi tiết: [asset API](../guides/asset-api.md),
[text service](text-search-w3.md), [image service](../guides/image-search-api.md),
[explanation](search-explanation-w5.md), [feedback](feedback-w4.md),
[jobs](jobs-status-w5.md), [reindex](reindex-w5.md).

## Filters, phân trang và search events

- `page` integer >=1, mặc định 1; `limit` 1–50, mặc định 12. JSON text page/
  limit phải là integer, không nhận bool hoặc chuỗi số; query/form được parse.
- Filters: category/license/format so khớp metadata, face_count_min/max >=0,
  min <= max; AND trước phân trang. Face count null không khớp cận số mặt.
  Không biết thuộc tính thì không suy đoán từ preview. DTO JSON/query dùng
  extra=forbid; dùng OpenAPI đúng endpoint/mode để kiểm kiểu. Multipart chỉ nên
  gửi các field đã công bố, không coi mọi field form dư đều được kiểm extra=forbid.
- List assets nhận filters qua query, text qua object `filters`, image qua
  **chuỗi JSON** tại multipart field `filters` (không phải nhiều field tùy ý).
- Pagination: page, limit, total, pages, has_next; pages=ceil(total/limit),
  total=0 thì pages=0. Trang vượt phạm vi trả mảng rỗng/200.
- Rank **bắt đầu từ 1 trên mỗi trang**, cả mock và service. Không đổi thành
  rank toàn cục. Kết quả mỗi trang không lặp asset ID.
- Service: total là số ứng viên sau lọc trong **cửa sổ tối đa 200**, không phải
  count toàn thư viện. Mỗi request thành công, kể cả retry, trang rỗng hoặc
  đổi trang, tạo event mới đã commit. query_id=search_event_id là cùng UUID.
  Event lưu đúng IDs của trang đã trả, filters và versions thực tế.
- Mock: total theo fixture; event/feedback giữ RAM từng process, mất khi restart.
  Không lấy ID event mock gửi sang feedback PostgreSQL.

## Text và image search

Text query được trim, dài 1–500 Unicode code points:

```json
{"query":"wooden chair","filters":{},"page":1,"limit":12}
```

Service text trả `retrieval_sources=["clip_text_to_preview"]`, image trả
`["clip_image_to_preview"]`; score_type=cosine, score hữu hạn trong [-1,1],
không phải phần trăm chính xác. Explanation là chuỗi giải thích tín hiệu
retrieval; không khẳng định mesh/license/thuộc tính chưa biết. Versions gồm
model_version, index_version, config_version, dataset_snapshot thực tế.
Không gán mock versions cho kết quả thật.

Mock text khớp metadata keywords, score có thể null và versions có tiền tố
mock-. Mock image trả fixture, không làm semantic retrieval.

Image: field `image` bắt buộc, JPEG/PNG theo nội dung decode được, file <=5 MiB,
mỗi chiều <=4096 px; filters="{}", page=1, limit=12 mặc định. Browser dùng
FormData và tự đặt Content-Type/boundary. API không nhận URL để tải ảnh.
Service query là `sha256:<64 ký tự hex>` của bytes ảnh; mock dùng mock-image:...
Hash không phải endpoint tải lại ảnh. File không được lưu làm kho ảnh upload;
search event thật giữ tham chiếu hash. Xem [upload contract](image-upload-w4.md).

## Feedback và retry

`relevance` chỉ nhận JSON Boolean; lấy đúng cặp event/asset từ cùng response:

```json
{"search_event_id":"00000000-0000-4000-8000-000000000080","asset_id":"example-chair","relevance":true}
```

Đây chỉ là ví dụ; thay IDs bằng kết quả vừa search, không dùng example như dữ
liệu đã tồn tại. PostgreSQL yêu cầu event UUID, asset ID 1–128 ký tự và asset
thuộc đúng trang kết quả event; trả storage=postgresql/mock=false sau commit.
Mock trả storage=memory/mock=true. Mỗi request hợp lệ tạo feedback mới, kể cả
gửi lại/đổi đánh giá. Không có idempotency cho feedback; mất response rồi retry
có thể thêm row. Event cũ thiếu result snapshot yêu cầu tìm kiếm lại.

Frontend hiện đọc **runtime** `/openapi.json` trước khi gửi feedback, kiểm schema
FeedbackResponse/LiveFeedbackResponse để tránh trộn nguồn; không đọc trực tiếp
file Git docs/openapi.json. Proxy cần chuyển đường dẫn này tới backend.

## Jobs và reindex quản trị

Header X-Admin-Key phải khớp APP_ADMIN_API_KEY (>=32 ký tự); Swagger dùng
Authorize/AdminKey. Chỉ dành cho local/nội bộ, chưa có tài khoản/role/SSO.
Không đưa key vào URL, logs, Git hoặc biến VITE_*.

Jobs lọc kind=ingestion/indexing và status=queued/running/succeeded/failed,
thứ tự created_at DESC rồi job_id DESC; progress null là chưa đo, không phải 0%.
GET trả 200 có thể chứa job failed; HTTP thành công không khẳng định operation
thành công. Lỗi commit cuối có thể để job queued/running, không tự suy diễn
terminal state từ log/artifact.

Reindex mặc định tắt; profile duy nhất clip-candidate200-v1. Cùng request_id
trả job cũ, kể cả failed, không chạy lại; request_id khác khi resource bận trả
409. 202 là đã nhận job, không phải đã dựng xong index. Output UUID riêng,
không activate index hay đổi cấu hình W6. Không có endpoint retry/cancel/resume.
Xem [chẩn đoán jobs W6](../guides/job-failure-diagnostics-w6.md).

## Lỗi và tracing

Envelope chung của API (không áp dụng cho lỗi do proxy/web server tạo):

```json
{"error":{"code":"INVALID_REQUEST","message":"Yêu cầu không hợp lệ.","details":[{"field":"body.query","message":"Giá trị không hợp lệ."}]}}
```

| HTTP | Mã thường gặp / tình huống |
|---|---|
| 400 | INVALID_REQUEST: validation/JSON/multipart parser; INVALID_FILTERS; INVALID_IMAGE/UNSUPPORTED_IMAGE/IMAGE_TOO_LARGE/IMAGE_DIMENSIONS_EXCEEDED |
| 400 | EVENT_ASSET_MISMATCH hoặc SEARCH_EVENT_RESULTS_UNAVAILABLE khi feedback |
| 403 | ADMIN_ACCESS_DENIED: thiếu/sai key; không dùng 401 trong contract admin này |
| 404 | ASSET_NOT_FOUND, SEARCH_EVENT_NOT_FOUND, JOB_NOT_FOUND; HTTP_404 cho route vắng mặt |
| 405 | HTTP_405: method không hỗ trợ |
| 409 | REINDEX_IN_PROGRESS: resource đang có queued/running |
| 500 | INTERNAL_ERROR: lỗi nội bộ/DB; không trả SQL/credentials/traceback |
| 503 | SEARCH_UNAVAILABLE hoặc ADMIN_API_UNAVAILABLE/REINDEX_UNAVAILABLE |

Validation backend trả **400**, spec loại 422 tự sinh. Text client còn nhận
422 để tương thích lịch sử, không có nghĩa backend hiện quảng bá 422. Image
client map mã upload 400 sang thông báo an toàn; text client xử lý chủ yếu theo
status; UI không nên hiển thị raw error body/exception.

Giữ APP_DEBUG=false. Server trả X-Request-ID UUID v4 riêng từng HTTP request,
bỏ qua ID client gửi và expose qua CORS cho origin được phép. Không thêm ID
vào body. Header này khác event/job/request_id reindex. CORS preflight là
response middleware riêng. Xem [logging/CORS](request-logging-w6.md).

## Chạy, export và kiểm chứng

Theo [hướng dẫn API tái lập W7](../guides/api-reproducibility-w7.md) để chọn
local/Compose, đúng persistence mode, gọi Swagger/curl và kiểm proxy/runtime
spec. Từ backend/, export **cả bốn** spec:

```powershell
.\.venv\Scripts\python.exe -m app.export_openapi
```

Examples trong Swagger/spec là minh họa, không phải benchmark hoặc IDs đã seed.
Exporter không mở lifespan/nạp model, không migrate/seed DB và không làm index
sẵn sàng. `/healthz`=200 cũng không chứng minh retrieval/feedback đã chạy thật.

Review #145 còn chờ Duy đối chiếu client và Khuê đối chiếu setup/evaluation.
Không dùng tests local để ghi nhận hai người đã xác nhận hoặc CI/merge đã đạt.
