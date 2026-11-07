# API text search — tích hợp service thật Issue #65

Ngày 05/11/2026, nhánh `feat/65-text-search-api`. Contract:
[W3 / #63](../contracts/text-search-w3.md). Nối implementation #60 đã merge qua
PR #75; review/CI/merge và smoke web với Duy/Khuê được ghi nhận riêng.

## Triển khai backend

- Router sync `POST /api/v1/search/text`, validation theo schemas #63.
- Biên service nhận query trim, filters, `candidate_limit=200`; revalidate output.
- Missing adapter hoặc `SearchUnavailable` → 503 `SEARCH_UNAVAILABLE` trước
  khi mở DB. Lỗi adapter/contract output → 500 an toàn; không trả exception text.
- Toàn bộ candidate IDs được đối chiếu PostgreSQL, kể cả ngoài trang đang xem;
  metadata được kiểm tra lại với filters. Thiếu ID hoặc lệch filters → 503,
  không âm thầm bỏ candidate rồi trả total không khớp.
- Chia trang cửa sổ tối đa 200 asset; giữ thứ tự service, rank 1 trên từng trang.
  Metadata cùng mapping list/detail; trường thiếu/null và URL được xử lý như #48.
- Kiểm tra response/serialization trước khi commit event. Sau commit dùng UUID
  đã lưu cho cả query_id/search_event_id. Empty/trang vượt phạm vi vẫn có event.
- Lỗi read/commit DB → 500 chuẩn; rollback và đóng session, không fallback RAM.
- Một service instance được cấp cho mỗi app và tái sử dụng qua các request;
  shutdown gọi `close()` nếu adapter cung cấp, luôn dispose DB engine.
- Startup đọc/validate `IndexManifest`, kiểm tra SHA-256 source/ready, cấu hình
  collection/named vector/count, rồi nạp CLIP CPU từ cache đúng revision một lần.
  Adapter chuyển `SearchUnavailableError` của Chi sang `SearchUnavailable` để
  API trả 503. Không bootstrap lại hoặc tải weights ở mỗi request.
- Cấu hình/cache/index lỗi thì app giữ liveness, text search trả 503. Sau khi
  sửa cần restart app. Bootstrap chỉ đọc index, không tự create/upsert/rebuild.

## Cấu hình và chạy

Trong PowerShell, từ gốc repo, dùng đường dẫn tuyệt đối của bộ index đã dựng:

```powershell
$env:APP_TEXT_SEARCH_SOURCE = "service"
$env:APP_TEXT_INDEX_MANIFEST = "C:/path/to/index-manifest.json"
$env:APP_TEXT_INDEX_ROOT = "C:/path/to/handoff-root"
$env:APP_TEXT_QDRANT_LOCAL_PATH = "C:/path/to/existing-qdrant"
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend
```

Mở `/docs`, gửi `{"query":"wooden chair","filters":{},"page":1,"limit":12}`
đến `/api/v1/search/text`. Chỉ cấu hình `service` mà chưa có manifest/root/cache/
index sẽ trả 503, không phải kết quả rỗng. Query rỗng/sai kiểu trả 400 trước dependency.
`/healthz` vẫn là liveness, không chứng minh search ready.

Với Qdrant server, bỏ `APP_TEXT_QDRANT_LOCAL_PATH`, đặt `APP_TEXT_QDRANT_URL`
thành HTTP(S) origin (mặc định `http://127.0.0.1:6333`); API key nếu có đặt riêng
ở `APP_TEXT_QDRANT_API_KEY`. Local storage chỉ mở bởi một process/worker; adapter
serialize các request để an toàn với CPU và SQLite. Không mở index cùng lúc với
script khác. Đây là baseline subset nhỏ, chưa đánh giá tải đồng thời/latency.

Quay lại mock cho tiến trình mới: đặt `APP_TEXT_SEARCH_SOURCE=mock`; mock text
chỉ bật ngoài production với `APP_MOCK_API_ENABLED=true`. Image/feedback giữ
quy tắc mock hiện có, không nhận event live để giả lập feedback đã lưu thật.
Trong production muốn có text route service phải chọn `service` rõ ràng;
default `mock` không tự tạo route live hay chuyển fallback.

Chế độ `service` luôn dùng list/detail PostgreSQL kể cả khi
`APP_ASSET_LIST_SOURCE=fixture`, để cùng nguồn metadata với kết quả text search.

Không thêm service fixture bằng env hoặc route công khai. Fixture retrieval chỉ
nằm trong tests. `mock:false` trong các test này nói nhánh service/DB đang được
kiểm thử, không xác nhận encoder/index thật hoặc chất lượng retrieval.

## Adapter và vòng đời

`create_app(settings, text_search_service=service)` nhận instance có method sync:

```python
search_text(query, filters, *, candidate_limit=200) -> TextSearchCandidates
```

Protocol và `SearchUnavailable` tại `app.services.text_search`. Adapter thật ở
`app.services.text_search_runtime` chuyển lỗi readiness của #60 sang 503, lỗi
bất ngờ là 500. Không instantiate encoder/client trong router hoặc mỗi request.

`app.main:app` bootstrap trong lifespan với model cache offline. Không truyền
instance khi chạy Uvicorn bình thường; `create_app(..., text_search_service=...)`
chỉ dành cho tích hợp/test đã quản lý service. Liveness không tải model, nhưng
startup của chế độ service có thời gian đọc cache; không dùng liveness thay readiness.

## Chuẩn bị index riêng và chạy lại kiểm chứng

Nếu chưa nhận được index/preview, có thể tải đúng subset đã chọn và dựng index
riêng từ source manifest. Không ghi đè collection dùng chung, không ghi DB nghiệp vụ:

```powershell
backend\.venv\Scripts\python.exe scripts/prepare_text_search_index.py --manifest data/manifests/home-interior-354-v1/assets_354.json --snapshot home-interior-354-v1 --download-previews
```

Lệnh in thư mục mới dưới `data/processed/issue65/index-*`, gồm source/ready,
preview checksums, index local và `index-manifest.json`. Chỉ tải preview từ
manifest này; CLIP phải có sẵn trong cache. Không gọi trên toàn bộ dataset.

Để smoke HTTP thật, cấu hình `TEST_DATABASE_URL` trỏ PostgreSQL riêng có tên
`test_*`, rồi chạy từ gốc repo với đường dẫn thư mục được in ở bước trên:

```powershell
backend\.venv\Scripts\python.exe scripts/verify_text_search_api.py --index-manifest data/processed/issue65/index-<id>/index-manifest.json --index-root data/processed/issue65/index-<id> --qdrant-local-path data/processed/issue65/index-<id>/qdrant
```

Verifier tạo schema tạm, nhập metadata từ cùng bộ ready/source đã kiểm checksum,
khởi chạy Uvicorn qua TCP localhost và gọi HTTP thật. Nó đối chiếu versions,
events trong DB, pagination/filters/detail, kết quả rỗng và fingerprint index
trước/sau; dừng server và dọn schema của lượt chạy. Report runtime nằm trong
`data/processed/issue65/http-*.json`. Không dùng DATABASE_URL phát triển để ghi dữ liệu.

## OpenAPI và Frontend

- [docs/openapi.json](../openapi.json): chế độ mock mặc định hiện có.
- [docs/openapi-text-search.json](../openapi-text-search.json): text router service,
  request/response #63, ví dụ cấu trúc minh họa và lỗi 400/500/503. Chế độ
  development của spec này vẫn có image/feedback mock.
- `python -m app.export_openapi` từ `backend/` xuất lại cả hai spec; `/openapi.json`
  runtime phản ánh chế độ app đang chạy, không gộp hai text route cùng URL.
- Frontend không được sửa trong lượt tích hợp backend này. Duy/Khuê dùng
  contract #63 và cấu hình API để kiểm chứng web ở #66/#72; backend smoke
  không thay cho UI E2E hoặc xác nhận tiếp nhận của các thành viên.

## Tests và giới hạn

Nhóm unit: `backend/tests/unit/test_text_search_api.py`, `test_text_search_runtime.py`.
Nhóm HTTP + PostgreSQL: `backend/tests/integration/test_text_search_stack.py`,
`test_text_search_bootstrap.py`. Tái sử dụng tests #63.

Từ gốc repo (cần PostgreSQL test riêng tên `test_*` cho integration):

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_text_search_api.py backend/tests/unit/test_text_search_contract.py backend/tests/unit/test_mock_api.py backend/tests/unit/test_openapi.py backend/tests/integration/test_text_search_stack.py backend/tests/integration/test_search_events.py -q
```

Tests integration dùng engine/session/commit thật trong schema tạm do test tạo;
retrieval trả candidates fixture cố định. Kiểm tra pagination, filters được
truyền đúng và đối chiếu DB, metadata/detail, event/versions, empty, ID thiếu
ngoài trang, lỗi mapping/read/commit và phục hồi. Test bootstrap chạy service #60
với Qdrant persistent local thật và encoder fixture 3D; tách khỏi smoke CLIP thật.

Kết quả local ngày 02/11/2026: **116 passed**, không skip, 10,17 giây, khi chạy
nhóm tests trong lệnh trên cùng `tests/unit/test_config.py` và
`tests/unit/test_database_config.py` với PostgreSQL test riêng. Đã dọn database
và schema tạm; không sửa dữ liệu phát triển. OpenAPI hai chế độ xuất thành công,
examples service hợp lệ; tests OpenAPI mặc định và API mock cũ vẫn đạt.
Kết quả này không thay cho GitHub CI, review hoặc nghiệm thu retrieval thật.

### Kết quả tích hợp ngày 05/11/2026

- Nhóm tests API/runtime/contract/mock/OpenAPI/config và PostgreSQL integration:
  **123 passed**, không skip (40,76 giây). Bao gồm service #60 + Qdrant local
  thật với encoder fixture, kiểm tra startup, lifecycle, lỗi readiness 503.
- Lượt Uvicorn qua TCP HTTP dùng CLIP thật từ cache, cùng snapshot
  `home-interior-354-v1` và manifest SHA-256
  `93f65237ca51060aad75f0f672b2b16f76c89a64dce64d7473791f428e944614` đã đạt.
  Tải/decode 354 preview, tạo 354 embedding và index riêng 354 point.
- Query `wooden chair` trả cửa sổ 200 ứng viên; hai trang đầu có 24 ID duy nhất,
  detail khớp metadata. Filters AND gồm category/license/format/cận face_count
  đạt; filter không khớp và trang vượt phạm vi trả rỗng đúng contract.
- 5 request thành công lưu 5 event riêng; query/filters/model/index/config/dataset
  khớp DB. Query invalid trả 400. Fingerprint 354 point trước/sau không đổi.
- Database/schema test được dọn, Uvicorn dừng và Qdrant local đóng. Bộ preview/
  index riêng được giữ trong `data/processed/issue65/index-1718ec3c49a0` (Git ignore)
  để chạy lại; không thay dữ liệu phát triển hoặc index dùng chung.
- [Bằng chứng gọn](../evidence/issue65-text-search-http.json) có hashes/provenance.
  Báo cáo runtime: `data/processed/issue65/http-8ab50d647139.json`. Kết quả là
  backend HTTP + CLIP + PostgreSQL + Qdrant persistent local; chưa phải Qdrant
  server mode, quality benchmark hay UI E2E. Không nhận thay phần việc #66/#72.

## Theo dõi bàn giao

Bộ kiểm chứng HTTP + retrieval thật + UI của #66 và kết quả local riêng nằm ở
[hướng dẫn tích hợp text search](text-search-integration.md). Xác nhận tiếp nhận
của Duy/Khuê vẫn cần được ghi trên Issue/PR, tách khỏi kết quả chạy tự động.

- [x] Adapter text retrieval #60, model/index/config manifest và bootstrap.
- [x] Index riêng đúng snapshot 354, đối chiếu source/ready hashes và IDs.
- [x] Smoke API thật với query/filters/pagination/empty/detail và durable events.
- [ ] Duy/Khuê tiếp nhận và kiểm chứng UI/smoke theo phần việc #66.
- [ ] CI, review và tích hợp; ghi theo kết quả GitHub thực tế.

Không đóng #65 thay reviewer hoặc dùng backend smoke để tích UI E2E. Chuyển PR
sang review sau khi đã cập nhật bằng chứng; merge/CI được xác nhận trên GitHub.
