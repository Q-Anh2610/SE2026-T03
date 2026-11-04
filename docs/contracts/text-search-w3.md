# Contract text search thật W3 — Issue #63

Quyết định ngày 02/11/2026 bởi TV1 — Vũ Nguyễn Quỳnh Anh, theo ủy quyền triển khai
trong phiên làm việc. Đây là bản bàn giao cho Chi (#60) và Duy (#54); không ghi
nhận hai thành viên đã review/xác nhận. Bản này chốt các điểm mở của
[rà soát W3](w3-text-search-review.md); giữ tài liệu rà soát làm lịch sử.

## Trạng thái triển khai

- #63 cung cấp schema request/response/service, persistence và tests PostgreSQL.
- `POST /api/v1/search/text` hiện vẫn là route mock W1; chưa gọi persistence này.
  `docs/openapi.json` vẫn mô tả đúng route đang chạy, không quảng cáo retrieval thật.
- Issue tiếp theo nối service #60, mapping DB và persistence vào route thật,
  cập nhật đồng bộ OpenAPI, frontend DTO/validator/mock và tests bị ảnh hưởng.
- Schema bàn giao riêng: [JSON Schema](text-search-w3.schema.json), sinh từ
  [Pydantic](../../backend/app/schemas/text_search.py). Không thay route image/feedback.

## Request và validation

Giữ URL `POST /api/v1/search/text`, JSON và shape hiện có:

```json
{"query":"wooden chair","filters":{"format":"glb"},"page":1,"limit":12}
```

- Query trim, 1–500 Unicode code points; không tự dịch/bỏ dấu. Chi ghi rõ policy
  token CLIP trong retrieval config; W3 chọn truncate theo tokenizer đúng checkpoint,
  không thay query echo bằng chuỗi đã cắt token. Revision và policy phải truy vết được.
- `page` integer >=1, mặc định 1; `limit` integer 1–50, mặc định 12.
  Không nhận boolean, chuỗi số hoặc float thay integer trong JSON.
- `filters` mặc định `{}`; `category`, `license` khớp chính xác sau trim;
  `format` thuộc mảng `formats`; `face_count_min/max` integer >=0, cận bao gồm,
  min<=max. `face_count` giữ nghĩa dữ liệu nguồn, không tự đổi mặt thành tam giác.
- Kết hợp AND, lọc trước chọn top ứng viên. Filter null/bỏ qua nghĩa không áp dụng;
  metadata null không khớp filter tương ứng. Cấm trường lạ, không âm thầm bỏ filter.
- Strict face counts chỉ áp dụng schema text search thật; query string của list
  API vẫn theo parser hiện có. Mock W1 không bị âm thầm đổi validator trong #63.

## Interface Chi → Quỳnh Anh

Interface cần triển khai ở #60 (chưa có service thật trong #63):

```python
search_text(query: str, filters: TextSearchFilters, *, candidate_limit: int = 200) -> TextSearchCandidates
```

`TextSearchCandidates` gồm `hits=[{asset_id,score},...]` và `versions`.
Service trả toàn bộ cửa sổ tối đa 200 ứng viên, chưa chia trang; API không gọi
service với `limit` riêng của trang. Dùng schema tại `app.schemas.text_search`.

- Encode text với CLIP cùng model/revision/preprocessing tương thích named vector.
  Score cosine hữu hạn [-1,1], lớn hơn tốt hơn; không đặt threshold W3, score âm
  vẫn hợp lệ. Không gọi score là xác suất hoặc phần trăm chính xác.
- Filters và dedup theo asset trước khi giới hạn cửa sổ. Sắp score giảm dần,
  hòa score theo `asset_id` tăng dần trước khi cắt 200. Chi cần xử lý hòa điểm ở
  biên cửa sổ để bảo đảm quy tắc này; không chỉ sort lại một tập top-K bất kỳ.
- `asset_id` dài 1–128, không khoảng trắng đầu/cuối, không `.`, `..` hoặc
  `/`, `\`, `?`, `#`, `%`; dùng được với cùng asset trong PostgreSQL/detail.
- Versions bắt buộc, không rỗng/không `mock-*`: `model_version`, `index_version`,
  `config_version`, `dataset_snapshot`. Phải lấy từ lần chạy thật, không default.
  Manifest truy ra checkpoint/revision, tokenizer/preprocessing, dimension,
  normalization/similarity, snapshot hash, collection/named vector và config.
- Thiếu collection/model, sai compatibility hoặc Qdrant chưa sẵn sàng: báo lỗi
  unavailable có kiểu ở service để API mapping 503, không trả danh sách rỗng giả.
  Service không ghi search event, không trả HTTP response, không tự rebuild index.

## Response và phân trang

Giữ top-level `query_id`, `search_event_id`, `query`, `results`, `versions`,
`pagination`; thêm yêu cầu `mock:false` bắt buộc cho đường thật.
`versions` có thêm `dataset_snapshot`; ba trường version cũ giữ nguyên tên.

- `total = len(hits)` của cửa sổ ứng viên sau filters/dedup, tối đa 200. Không phải
  count toàn collection hoặc số asset được con người đánh giá liên quan.
- API chia trang từ cửa sổ đó: offset=(page-1)*limit, pages=ceil(total/limit),
  has_next=page<pages. Trang phải đủ min(limit,max(0,total-offset)) kết quả.
  Total=0 => pages=0; vượt trang cuối => 200 với results rỗng.
- Rank bắt đầu 1 trên mỗi trang. Thứ tự/dedup ổn định khi dữ liệu/index/config
  không đổi; mỗi request tìm lại, không giữ snapshot kết quả giữa các request.
  Đổi snapshot có thể đổi total/thứ tự; W3 không hứa session pagination bất biến.
- Mapping metadata qua cùng quy ước DB với list/detail; không âm thầm bỏ candidate
  thiếu DB rồi vẫn giữ total cũ. Candidate thiếu DB => 503 `SEARCH_UNAVAILABLE`,
  ghi lỗi chẩn đoán an toàn để đồng bộ dữ liệu rồi retry.
- Metadata nullable vẫn trả đủ keys; name thiếu dùng asset_id, không sửa DB.
  URL nguồn/thumbnail chỉ HTTP(S) không credentials, sai/local thì null.
  Không thêm author_url/license_url, không đoán URL từ tên tác giả/license.
- Mỗi result có `score` cosine, `retrieval_sources:["clip_text_to_preview"]` và
  explanation mô tả xếp hạng bằng tương đồng CLIP text–preview. Không gắn nhãn
  metadata keyword/RRF nếu không thực sự chạy các luồng đó.

## Search event và transaction

- Mỗi HTTP search thành công tạo một UUID mới; `query_id == search_event_id`.
  Tìm mới, đổi trang và retry đều là request/event mới, không idempotency key.
  UI không tạo ID hoặc gửi lại ID trong request. Mất response sau commit rồi
  retry có thể tạo hai event; W3 chấp nhận và không gọi đó là chống trùng retry.
- Sau validation, retrieval, mapping và kiểm tra response template hợp lệ,
  gọi `persist_text_search_event(session, request, versions)`; dùng UUID trả về
  cho cả hai ID response. Chỉ trả 200 khi commit đã thành công.
- Thành công rỗng/trang vượt phạm vi vẫn tạo event với cấu hình thật. Request
  lỗi, retrieval lỗi hoặc mapping thất bại không tạo event thành công.
- Lưu query trim, query_type=text, query_image_ref=null, filters chuẩn hóa bỏ
  giá trị null và model/index/config/dataset thật. Tái sử dụng ORM/migration 0001.
  Event W3 là bản ghi truy vấn/cấu hình; chưa lưu page/limit, ranked results hay
  ảnh chụp response, không hứa tái dựng chính xác từng trang từ riêng event.
- Persistence tự commit/rollback, nhận session riêng theo request không có
  pending writes khác; caller/get_db_session đóng session. Không bao hàm một
  transaction phân tán PostgreSQL–Qdrant. Không gọi trong transaction nghiệp vụ khác.
- Lỗi ghi DB => rollback, 500 `INTERNAL_ERROR`, không trả 200 hoặc fallback RAM.
  Không log query, SQL, URL DB, credentials hay traceback. Không retry commit
  tự động vì có thể không biết chắc commit phía server đã hoàn tất hay chưa.
- Feedback hiện vẫn mock/RAM; không gửi event thật vào mock feedback rồi coi là
  feedback persistence thành công. Phần feedback thật thuộc W4.

## Lỗi HTTP đã chốt cho đường thật

Envelope luôn `{ "error": { "code": "...", "message": "...", "details": [] } }`.

| Status/code | Khi nào | Event |
|---|---|---|
| 400 INVALID_REQUEST | JSON/query/filter/page/limit không hợp lệ | Không |
| 503 SEARCH_UNAVAILABLE | Model/index/Qdrant chưa sẵn sàng, sai version hoặc ID không đồng bộ DB | Không |
| 500 INTERNAL_ERROR | Lỗi code/serialization hoặc ghi DB | Không có event thành công được xác nhận |
| 404 | Route/tài nguyên không có; tìm kiếm rỗng không phải 404 | Không |

503 cho phép người dùng retry khi dependency phục hồi; không hứa Retry-After.
Messages an toàn, details chỉ mô tả trường validation, không trả input nhạy cảm.
Error mapping 503 và route thật sẽ được triển khai ở issue API tiếp theo.

## Bàn giao và kiểm chứng #63

- **Chi (#60):** nhận interface/candidate window, tie-break/filter, versions,
  lỗi unavailable và index manifest. Index bộ W1 đã đo không tự xác nhận snapshot
  nội thất mới của PR #61; kiểm tra hash/ID và rebuild riêng khi cần.
- **Duy (#54):** giữ request, đọc mock boolean bắt buộc và dataset_snapshot,
  giữ số phần tử trang/rank hiện có; mọi event ID mới đến từ response. Không
  fallback mock khi lỗi; tiếp tục hiển thị 503/error và retry request đã chuẩn hóa.
- **Khuê:** nhận schemas/service để review tests và chuẩn bị smoke sau khi route
  thật được nối. Tests fixture/DB không chứng minh chất lượng semantic retrieval.
- Chưa có xác nhận tiếp nhận/review của các thành viên; không tích thay họ.

Từ gốc repo, unit tests và schema export:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_text_search_contract.py -q
```

Từ `backend/`:

```powershell
.venv\Scripts\python.exe -m app.export_text_search_contract
```

Integration tests `backend/tests/integration/test_search_events.py` chỉ dùng
`TEST_DATABASE_URL` là PostgreSQL riêng có tên `test_*`, không dùng DATABASE_URL
phát triển. Tests tạo schema tạm, chạy upgrade/check, rồi dọn đúng schema đó.
Kiểm tra commit qua session độc lập, UUID mới mỗi request, versions/filters,
rollback lỗi constraint, HTTP 400/500 an toàn và trả kết nối về pool.

### Kết quả local ngày 02/11/2026

- Nhóm contract/persistence và regression mock/OpenAPI: **84 passed**.
- Toàn bộ backend trên PostgreSQL test riêng: **369 passed**, không skip
  (161,66 giây ở lượt cuối). Lệnh trong `backend/`: `python -m pytest -q`,
  dùng Python của `.venv` và `TEST_DATABASE_URL` của database tạm `test_*`.
- Alembic upgrade/check đạt, không phát sinh migration; database/schema test
  do lượt kiểm chứng tạo đã được dọn. Không đổi dữ liệu phát triển.
- Đây là tests fixture/DB thật, không phải CLIP/Qdrant smoke, GitHub CI hoặc
  xác nhận tiếp nhận của Chi/Duy/Khuê. Chưa nối HTTP text search thật trong #63.
