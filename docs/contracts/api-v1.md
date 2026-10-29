# API contract v1 - list/detail PostgreSQL và các API mock

## Cập nhật Issue #48

- `GET /api/v1/assets/{asset_id}` đọc cùng PostgreSQL và dùng cùng mapping metadata
  với list; response giữ `{asset, mock}` và trả `mock=false`.
- Asset không có trả 404 `ASSET_NOT_FOUND`; DB lỗi trả 500 chuẩn, không fallback
  fixture. ID dài hơn 128 ký tự trả 400 trước khi khởi tạo kết nối DB.
- `APP_ASSET_LIST_SOURCE` hiện chọn nguồn cho cả list/detail. Chế độ fixture chỉ
  có hiệu lực khi bật mock ở development/test; production luôn có cả hai API DB.
- thumbnail_path là HTTP(S) URL không chứa credentials thì dùng làm thumbnail_url;
  thiếu, sai định dạng, hoặc là đường dẫn file local thì trả null. source_url cũng
  chỉ trả HTTP(S) URL không kèm credentials để giữ contract Frontend và không lộ
  đường dẫn riêng. API không tải URL để kiểm tra ảnh và không phục vụ file local.
- Name null/rỗng vẫn hiển thị asset_id theo quy ước #47; các metadata thiếu khác
  giữ null. Không sửa thông tin nguồn, tác giả/license hay metadata gốc trong DB.
- Search/feedback còn mock, nên ID từ search fixture không mặc định có trong DB.
  Đối chiếu UI list → detail phải dùng cùng chế độ nguồn dữ liệu.
- Quy ước preview tái sử dụng #47, cần Huyền/Duy review khi bàn giao dữ liệu thật;
  kiểm thử tự động không thay cho xác nhận của hai thành viên.

Rà soát trước tích hợp thật W3: xem [bảng đối chiếu và đề xuất chờ owner xác nhận](w3-text-search-review.md).
Tài liệu này mô tả API hiện có; chưa phải contract retrieval thật đã chốt.

## Cập nhật Issue #47

- `GET /api/v1/assets` mặc định đọc PostgreSQL và trả `mock=false`; các keys
  `items`/`pagination` và filters giữ nguyên. Không fallback fixture khi DB lỗi.
- `APP_ASSET_LIST_SOURCE=fixture` chọn bộ fixture cũ một cách tường minh, chỉ có
  hiệu lực khi bật mock ở development/test. Production luôn dùng list DB.
- List DB lọc AND trước phân trang, ORDER BY asset_id ASC; count và items cùng
  transaction REPEATABLE READ. Các request khác nhau có thể thấy dữ liệu mới.
- List hiện liệt kê mọi ingestion_status, không đồng nghĩa asset đã searchable.
- Name null dùng asset_id làm nhãn hiển thị để tương thích frontend; không sửa
  metadata gốc trong DB. Các metadata nullable khác giữ null.
- thumbnail_url chỉ lấy từ thumbnail_path nếu là HTTP(S) URL không kèm credentials;
  đường dẫn local trả null. Chưa triển khai phục vụ file preview trong issue này.
- `mock=false` chỉ xác định nguồn đọc DB: bản ghi seed vẫn có source=mock.
- Detail trước đây còn mock ở #47; từ #48 đã đọc DB như phần cập nhật phía trên.
- OpenAPI xuất mặc định mô tả list DB và các route mock còn lại. Chế độ fixture
  có Swagger runtime riêng. Các quy ước mock bên dưới chỉ áp dụng khi dùng fixture.

## Contract mock gốc (Issue #9)

Trạng thái: backend đã có contract/mock để review; **chờ Nguyễn Văn Duy xác nhận**
request/response, lỗi và phân trang. Không coi tài liệu này là bằng chứng hai phía
đã thống nhất. OpenAPI thực thi được export tại `docs/openapi.json`.

## Phạm vi

- Base path `/api/v1`; JSON UTF-8, image upload dùng multipart/form-data.
- Chỉ phục vụ fixture cho frontend/Swagger. Text khớp từ khóa; ảnh trả tập fixture
  cố định sau validation. Không dùng để đánh giá semantic retrieval.
- Search giữ các trường frontend đang đọc: query_id, search_event_id, query,
  results, versions. Thêm pagination và mock=true; không bọc search trong data.
- Asset metadata thống nhất giữa list/detail/search, giữ null khi thiếu thông tin.
- Các response mock thành công có mock=true, source=fixture và IDs/versions mock-.
- Feedback chỉ được ghi trong RAM, response storage=memory. Không ghi PostgreSQL,
  không tái sử dụng dữ liệu hoặc schema runtime của Issue #8.
- Các endpoint này chỉ đăng ký khi APP_ENV khác production và
  APP_MOCK_API_ENABLED=true. Tắt mock không tự fallback sang API giả.

## Endpoints

| Method | URL | Input | Response thành công |
|---|---|---|---|
| GET | /api/v1/assets | Query page, limit và filters | 200: items, pagination, mock |
| GET | /api/v1/assets/{asset_id} | ID fixture | 200: asset, mock |
| POST | /api/v1/search/text | JSON query, filters, page, limit | 200: shape search hiện có + pagination, mock |
| POST | /api/v1/search/image | Multipart image, filters, page, limit | 200: shape search, query là mock-image:<SHA-256> |
| POST | /api/v1/feedback | JSON search_event_id, asset_id, relevance | 201: feedback_id, event/asset/relevance, created_at, storage, mock |

Feedback phải dùng event ID từ search vừa chạy trong cùng tiến trình. ID trong
Swagger example chỉ minh họa, không phải event có sẵn. Event không tồn tại/đã
bị loại khỏi bộ nhớ trả 404; asset không tồn tại trả 404; asset không thuộc trang
kết quả của event trả 400. Mỗi lần gửi hợp lệ tạo một feedback mock mới; chưa
chốt nhận diện phiên hoặc idempotency của API thật.

Mock giữ tối đa 256 search events và 1000 feedback gần nhất, riêng từng process.
Restart sẽ mất dữ liệu; không dùng nhiều worker để thử luồng feedback mock này.

## Phân trang

- page bắt đầu từ 1, mặc định 1; limit từ 1 đến 50, mặc định 12.
- Áp dụng filter trước, sau đó phân trang theo thứ tự fixture ổn định.
- pagination gồm page, limit, total, pages, has_next.
- total là tổng kết quả sau lọc/khớp query, trước phân trang.
- pages=ceil(total/limit), bằng 0 khi không có kết quả.
- Trang vượt phạm vi trả mảng rỗng với HTTP 200, không trả lỗi 404.
- rank bắt đầu lại từ 1 trên mỗi trang để giữ tương thích validator frontend W1.

## Filters

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| category | string | Danh mục bằng chính xác giá trị metadata |
| license | string | License bằng chính xác; null không khớp giá trị có yêu cầu |
| format | string | Giá trị nằm trong mảng formats |
| face_count_min | integer >= 0 | Cận dưới bao gồm |
| face_count_max | integer >= 0 | Cận trên bao gồm |

Các điều kiện kết hợp AND, min không vượt max. Asset face_count=null bị loại khi
lọc số mặt. Không lọc thì null không tự làm asset bị loại. Unknown fields bị từ
chối 400, không âm thầm bỏ qua. Đây là contract đề xuất cụ thể của Issue #9,
cần Duy và owner search review trước ghép nối tính năng thật.

List nhận filter qua query parameters; text search qua object filters; image
search qua **JSON string** ở field filters trong form.
Tại thời điểm mock W1, frontend chỉ gửi filters={}. Frontend hiện có DTO và
validator cho các filters ở trên; xem [đối chiếu Issue #9](frontend-api-v1.md).

## Text search

query được trim, 1-500 Unicode code points. limit/page trong JSON phải là số
nguyên, không nhận boolean hoặc chuỗi số. Ví dụ:

```json
{"query":"ghế gỗ","filters":{},"page":1,"limit":12}
```

Response giữ query đã trim, IDs mock duy nhất, results không trùng asset_id,
score=null, explanation nêu rõ chỉ khớp metadata. Metadata/versions dùng đúng
shape đang có ở `frontend/src/features/search/types.ts`.

## Image search

Trong Swagger chọn file tại field image; filters mặc định `{}`, page=1, limit=12.
Mock kiểm tra ảnh JPEG/PNG thực sự decode được, không tin đuôi file hay MIME.
Giới hạn cho contract mock: <=5 MiB, mỗi chiều <=4096 pixel. Đây là lựa chọn
triển khai của Issue #9, không tuyên bố là ngưỡng đã được PDF/SRS chốt.

Không tải URL do người dùng nhập. Không giữ ảnh sau request; event chỉ giữ chuỗi
tham chiếu hash và response mock. Không coi hash là kết quả nhận diện nội dung.

## Lỗi thống nhất

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Yêu cầu không hợp lệ.",
    "details": [{"field":"body.query","message":"Giá trị không hợp lệ."}]
  }
}
```

| HTTP | code | Khi nào |
|---|---|---|
| 400 | INVALID_REQUEST | Validation query/body/form, JSON hỏng, unknown fields |
| 400 | INVALID_FILTERS | Field filters trong image form không phải JSON filter hợp lệ |
| 400 | INVALID_IMAGE / UNSUPPORTED_IMAGE | Ảnh hỏng hoặc ngoài JPEG/PNG |
| 400 | IMAGE_TOO_LARGE / IMAGE_DIMENSIONS_EXCEEDED | Vượt giới hạn ảnh |
| 400 | EVENT_ASSET_MISMATCH | Feedback asset không thuộc kết quả event |
| 404 | ASSET_NOT_FOUND / SEARCH_EVENT_NOT_FOUND | Resource không tồn tại |
| 404 | HTTP_404 | Đường dẫn không tồn tại hoặc mock routes bị tắt |
| 405 | HTTP_405 | Method không được hỗ trợ |
| 500 | INTERNAL_ERROR | Lỗi nội bộ, không trả exception message/stack trace |

Validation trả **400 theo Issue #9**, thay 422 trong nháp W1. Swagger/OpenAPI
không quảng bá response 422 tự sinh. Client search hiện xử lý 400 và 422 bằng
thông báo invalid cố định; 422 được giữ cho tương thích lịch sử. Client search
không đọc error.code/message từ body; client asset có đọc code để phân biệt
ASSET_NOT_FOUND với route không tồn tại. 503 cho search thật còn chờ owner xác nhận,
chưa được router/OpenAPI search hiện tại khai báo.

Giữ APP_DEBUG=false khi kiểm tra contract lỗi 500; chế độ debug của framework có
thể trả traceback thay handler 500. CORS preflight là phản hồi middleware riêng,
không phải response nghiệp vụ trong bảng trên.

## Swagger và frontend local

Từ backend/, cài requirements-dev rồi chạy:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Mở http://127.0.0.1:8000/docs. Chạy text/image search trước, copy search_event_id
và asset_id trong results sang POST feedback. Dữ liệu cố định có 6 fixture:
mock-chair-01/02, mock-table-01, mock-lamp-01, mock-vase-01, mock-box-01.

CORS mặc định cho http://localhost:5173 và http://127.0.0.1:5173. Có thể cấu hình
APP_CORS_ORIGINS bằng mảng JSON; không dùng wildcard hoặc credentials mặc định.
Từ frontend/:

```powershell
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000'
npm run dev:api
```

Giao diện lúc đó dùng HTTP client gọi backend mock, không dùng fixture client
trong trình duyệt. Nếu cổng Vite khác 5173, bổ sung origin chính xác vào cấu hình.

## Export và kiểm tra

Từ backend/:

```powershell
.\.venv\Scripts\python.exe -m app.export_openapi
.\.venv\Scripts\python.exe -m pytest
```

Exporter dùng settings mock xác định, không phụ thuộc APP_NAME/APP_ENV của máy,
ghi UTF-8 vào docs/openapi.json. Tests đối chiếu file export với app.openapi(),
kiểm tra refs/examples, validation, pagination, upload và feedback.

## Checklist review với Duy

- [ ] Đồng ý giữ search payload top-level, thêm pagination/mock.
- [ ] Xác nhận 400 thay cho 422 và cách UI đọc error.code/message.
- [ ] Xác nhận page/limit, empty page và rank theo trang.
- [ ] Review filters, multipart field image và giới hạn ảnh.
- [ ] Review feedback Boolean và storage=memory trong giai đoạn mock.

Các ô này chưa tích vì chưa có xác nhận từ Duy; việc code/test thành công không
thay cho thỏa thuận API của nhóm.
