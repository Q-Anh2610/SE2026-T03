# API text search — phần chuẩn bị Issue #65

Ngày 02/11/2026, nhánh `feat/65-text-search-api`. Contract:
[W3 / #63](../contracts/text-search-w3.md). Đây là bàn giao một phần #65,
chưa nghiệm thu tìm kiếm semantic thật và chưa đóng issue.

## Đã chuẩn bị

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

## Chọn chế độ và thử khi chưa có Chi

Trong PowerShell, từ `backend/`, chọn chế độ cho tiến trình hiện tại:

```powershell
$env:APP_TEXT_SEARCH_SOURCE = "service"
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Mở `/docs`, gửi `{"query":"wooden chair","filters":{},"page":1,"limit":12}`
đến `/api/v1/search/text`. Bản chuẩn bị chưa có adapter nên **503 là đúng**,
không phải kết quả rỗng. Query rỗng/sai kiểu tham số trả 400 trước dependency.
`/healthz` vẫn là liveness, không chứng minh search ready.

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

## Cách nối adapter khi #60 sẵn sàng

`create_app(settings, text_search_service=service)` nhận instance có method sync:

```python
search_text(query, filters, *, candidate_limit=200) -> TextSearchCandidates
```

Protocol và `SearchUnavailable` tại `app.services.text_search`. Chi hoặc adapter
tích hợp cần chuyển lỗi model/index/Qdrant chưa sẵn sàng/không tương thích thành
`SearchUnavailable` mà không lộ nội dung exception trong response. Lỗi bất ngờ
khác là 500. Không instantiate encoder/client trong router hoặc mỗi lần gọi.

Sau khi có code #60 mới thêm app factory/bootstrap nạp cấu hình index và cấp
service thật. Hiện `app.main:app` chưa thực hiện bootstrap này; chỉ đổi env không
làm xuất hiện model/index. Không có cấu hình đường dẫn class tùy ý hay tải model
trong phần chuẩn bị này.

## OpenAPI và Frontend

- [docs/openapi.json](../openapi.json): chế độ mock mặc định hiện có.
- [docs/openapi-text-search.json](../openapi-text-search.json): text router service,
  request/response #63, ví dụ cấu trúc minh họa và lỗi 400/500/503. Chế độ
  development của spec này vẫn có image/feedback mock.
- `python -m app.export_openapi` từ `backend/` xuất lại cả hai spec; `/openapi.json`
  runtime phản ánh chế độ app đang chạy, không gộp hai text route cùng URL.
- Frontend DTO/mock không thay đổi trong phần chuẩn bị này. Duy dùng contract
  #63 để cập nhật mock boolean/dataset_snapshot và xác nhận API sau khi adapter
  thật được bàn giao. Chưa tuyên bố UI text search thật hoạt động.

## Tests và giới hạn

Nhóm unit: `backend/tests/unit/test_text_search_api.py`. Nhóm HTTP + PostgreSQL:
`backend/tests/integration/test_text_search_stack.py`. Tái sử dụng tests #63.

Từ gốc repo (cần PostgreSQL test riêng tên `test_*` cho integration):

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_text_search_api.py backend/tests/unit/test_text_search_contract.py backend/tests/unit/test_mock_api.py backend/tests/unit/test_openapi.py backend/tests/integration/test_text_search_stack.py backend/tests/integration/test_search_events.py -q
```

Tests integration dùng engine/session/commit thật trong schema tạm do test tạo;
retrieval trả candidates fixture cố định. Kiểm tra pagination, filters được
truyền đúng và đối chiếu DB, metadata/detail, event/versions, empty, ID thiếu
ngoài trang, lỗi mapping/read/commit và phục hồi. Không gọi Internet/CLIP/Qdrant.

Kết quả local ngày 02/11/2026: **116 passed**, không skip, 10,17 giây, khi chạy
nhóm tests trong lệnh trên cùng `tests/unit/test_config.py` và
`tests/unit/test_database_config.py` với PostgreSQL test riêng. Đã dọn database
và schema tạm; không sửa dữ liệu phát triển. OpenAPI hai chế độ xuất thành công,
examples service hợp lệ; tests OpenAPI mặc định và API mock cũ vẫn đạt.
Kết quả này không thay cho GitHub CI, review hoặc nghiệm thu retrieval thật.

## Còn chờ để hoàn thành #65

- [ ] Adapter text retrieval #60, model/index/config manifest và bootstrap thật.
- [ ] Index tương thích snapshot nội thất hiện tại; không dùng bằng chứng index
  W1 của #57 để xác nhận snapshot mới trong #61.
- [ ] Đối chiếu snapshot/hash, ID và metadata giữa DB và index thật.
- [ ] Smoke API dùng CLIP/Qdrant thật, kèm query/filter/empty và versions.
- [ ] Duy/Khuê tiếp nhận và kiểm chứng UI/smoke theo phần việc #66.
- [ ] CI, review và tích hợp; ghi theo kết quả GitHub thực tế.

Có thể mở Draft PR cho phần chuẩn bị; không tick nghiệm thu retrieval thật
hoặc đóng #65 từ các tests fixture/DB này.
