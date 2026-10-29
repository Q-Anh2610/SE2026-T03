# Rà soát contract text search W3/M2 — Issue #54

Ngày rà soát: 27/10/2026. Người thực hiện: Nguyễn Văn Duy.
Phạm vi: [Issue #54](https://github.com/Q-Anh2610/SE2026-T03/issues/54).
Mốc code: `f9ebd61a82c095fad54e1f89c0af582b13cebbf1`, nhánh `feat/54-w3-text-search`.
**Bản đề xuất để review, chưa có xác nhận contract thật từ Quỳnh Anh/Linh Chi.**
Không thay đổi API/schema/DTO, không tích checklist owner review.

## Đối chiếu lại sau cập nhật develop ngày 29/10/2026

Mốc mới: `65ce5839576949dc5633c05c745887c20913d79a` trên nhánh W3,
fast-forward từ develop; các phần rà soát ngày 27/10 bên dưới giữ làm lịch sử.

- #48 đã đưa detail vào PostgreSQL, dùng cùng mapping với list; `AssetDetailResponse.mock`
  nay là boolean. URL nguồn/thumbnail sai hoặc local được đổi thành null. Nhận định
  bên dưới về detail luôn tra fixture và chưa có mapping DB đã được thay thế.
- Search vẫn đăng ký qua router mock và gọi `MockStore.search`; schema search vẫn
  `mock: Literal[True]`. Tắt mock không tạo route retrieval thật. ID search fixture
  không mặc nhiên tồn tại trong detail DB; cần cùng nguồn dữ liệu khi smoke.
- #39 đã có CLIP encode ảnh, batch và Qdrant ensure/upsert, cùng keyword baseline
  cấp module. Chưa có encode text/truy vấn vector hoặc service nối HTTP search;
  [báo cáo baseline](../guides/search-baseline-w2.md) chưa nghiệm thu index 200 ảnh thật.
- Issue #54 được đọc lại, chưa có bình luận xác nhận contract thật. Chưa có bằng
  chứng chốt pagination, event lifecycle hoặc API retrieval W3 thay thế bản đề xuất.
- Chưa chạy smoke retrieval thật; tests frontend với HTTP giả lập chỉ kiểm chứng
  xử lý giao diện/contract, kể cả detail 404 và quay lại giữ kết quả.

Các quyết định retrieval thật vẫn chờ owner xác nhận; không coi merge #39/#48
là bằng chứng hoàn thành W3 hoặc tự thay đổi contract search.

## Nguồn đối chiếu và trạng thái backend

- [API v1](api-v1.md), [nháp W1](search-text.md), [đối chiếu frontend mock v1](frontend-api-v1.md).
- [DTO](../../frontend/src/features/search/types.ts), [validators](../../frontend/src/features/search/contract.ts), [HTTP search client](../../frontend/src/lib/api/search.ts), [HTTP asset client dùng chung](../../frontend/src/lib/api/http.ts).
- [Router mock](../../backend/app/api/mock.py), [schema](../../backend/app/schemas/api.py), [error handlers](../../backend/app/core/errors.py), [đăng ký router](../../backend/app/main.py), [MockStore](../../backend/app/services/mock_api.py).
- [Exporter](../../backend/app/export_openapi.py), [OpenAPI đã lưu](../openapi.json), [tests OpenAPI](../../backend/tests/unit/test_openapi.py).

Text route gọi `store(request).search(...)`, tức `MockStore.search`: lọc 6 fixture, khớp token metadata sau chuẩn hóa dấu/chữ thường, phân trang rồi tạo IDs mock. Không gọi encoder, Qdrant hay service retrieval thật; không ghi SearchEvent vào PostgreSQL. Event được lưu trong RAM, tối đa 256 event/process, mất sau restart. Có [ORM SearchEvent](../../backend/app/models/search_event.py) không có nghĩa router đã dùng persistence đó.

`create_app` chỉ đăng ký search/detail mock khi bật mock và môi trường khác production. Tắt mock không chuyển sang retrieval thật: route search không tồn tại và trả 404. List mặc định đọc PostgreSQL, trả `mock=false`, nhưng có thể đọc bản ghi seed; detail vẫn tra fixture nên ID của list DB có thể trả 404. Không dùng list DB hoặc `/healthz` để kết luận search thật đã sẵn sàng.

## Bảng đối chiếu

Trong bảng, “khớp” chỉ nói hành vi hiện có; không xác nhận owner đã đồng ý áp dụng cho retrieval thật.

| Nội dung | Hiện có / đã khớp | Điểm lệch hoặc thiếu | Đề xuất tối thiểu chưa chốt / owner |
|---|---|---|---|
| Request text | POST JSON `query`, `filters`, `page`, `limit`; query trim 1–500 Unicode code points; page>=1, limit 1–50. Backend strict page/limit, mặc định 1/12; client luôn gửi sau validate. | Backend cho bỏ filters/limit, frontend type yêu cầu có; đây là client gửi tập con hợp lệ, không phải lỗi tương thích. | Giữ shape, defaults và giới hạn hiện có; Quỳnh Anh xác nhận áp dụng cho thật. |
| Filters | category/license so bằng chính xác, format thuộc mảng; số mặt bao gồm cận, min<=max; AND trước phân trang; null filter là không áp dụng, metadata null không khớp filter tương ứng. Unknown filter bị từ chối. | Backend `AssetFilters` không strict int ngoài kiểm tra bool: có khả năng ép chuỗi số/số thực nguyên về int; frontend chỉ nhận safe integer. OpenAPI không diễn tả đầy đủ runtime coercion. | Quỳnh Anh xác nhận có siết JSON face counts về integer strict hay giữ tương thích; Linh Chi xác nhận payload/filter và ý nghĩa face_count (mặt hay tam giác). Chưa đổi validator. |
| Response top-level | `query_id`, `search_event_id`, query echo, `results`, `pagination`, `versions`; không bọc `data`. | Backend schema chưa enforce query echo, ID không rỗng, uniqueness hoặc liên hệ pagination/results; client kiểm tra chặt hơn. MockStore hiện tạo đúng. | Quỳnh Anh cam kết các invariants cho adapter thật, bổ sung backend tests khi triển khai. |
| Pagination | Mock: total sau khớp/lọc, pages=ceil(total/limit), has_next=page<pages; total=0 => pages=0; vượt trang cuối => 200 + results rỗng. | Client yêu cầu **đúng số phần tử** `min(limit,max(0,total-(page-1)*limit))`. ANN top K/candidate cap/threshold hoặc loại asset thiếu metadata sau retrieval có thể không đáp ứng. Chưa có thuật toán/count thật để đối chiếu. | Quỳnh Anh + Linh Chi quyết định total là toàn bộ kết quả hay tập ứng viên có giới hạn, cách phân trang ổn định/tie-break và thay đổi dữ liệu giữa request. Không tự gọi count toàn collection là tổng kết quả liên quan. Giữ contract mock cho đến quyết định. |
| Rank / dedup | Mock rank 1..N mỗi trang, client bắt buộc đúng thứ tự và asset_id duy nhất trong trang, N<=limit. | Schema backend chỉ rank>=1; không enforce unique asset hoặc rank liên tiếp. Chưa có guarantee thật giữa các trang. | Linh Chi xác nhận gom theo asset trước phân trang, thứ tự ổn định; Quỳnh Anh giữ rank theo trang nếu dùng lại DTO. |
| Asset nullability | Cùng keys: asset_id/name/source string; description/category/author/license/source_url/thumbnail_url nullable; face_count integer>=0 hoặc null; tags/formats string arrays. Nullable keys phải có, không được bỏ. | Client từ chối name/asset_id rỗng; backend schema cho phép chuỗi rỗng. List DB dùng asset_id thay name thiếu; chưa có mapping search/detail DB. | Quỳnh Anh xác nhận mapping thống nhất search/list/detail, dùng ID làm nhãn khi name thiếu như list #47; không sửa dữ liệu gốc. |
| Source và URL | Detail đang hiển thị source, author, license; source_url nếu có là link nguồn. Client chỉ nhận HTTP(S) tuyệt đối không kèm credentials; URL null được chấp nhận. | Backend AssetMetadata chỉ khai báo str/null, chưa enforce URL cho source_url; list chỉ lọc URL thumbnail. Dữ liệu URL sai có thể bị client từ chối toàn response. Không có author_url/license_url trong DTO. | Quỳnh Anh xác nhận chuẩn URL và mapping thiếu/không hợp lệ thành null; author/license vẫn text. Nếu cần link tác giả/license riêng, owner quyết định fields mới; không suy URL từ chuỗi author/license. |
| Score | Backend float hữu hạn/null; client nhận số hữu hạn kể cả âm, bắt buộc key score; mock trả null. UI không gọi score là phần trăm. | Chưa có định nghĩa thật: cosine/distance/rank fusion, chiều tốt hơn, range, normalization hoặc threshold. Không thể suy nghĩa từ field number. | Linh Chi xác nhận metric và chiều sắp xếp, scope so sánh theo versions; đề xuất tiếp tục không hiển thị score cho tới khi định nghĩa. Score null khi không cung cấp được ý nghĩa phù hợp, không tự gắn cosine/RRF. |
| retrieval_sources / explanation | Mảng chuỗi và chuỗi; mock dùng `mock_metadata` và giải thích là minh họa. | Chưa chốt vocabulary/ý nghĩa thật; không thể gắn nhãn CLIP khi service chưa chạy. | Linh Chi cung cấp tên nguồn và explanation dựa trên tín hiệu thật; Quỳnh Anh xác nhận serialization. |
| IDs / event | Client chỉ coi IDs là chuỗi không rỗng; mock tạo query/event mới mỗi request, kể cả đổi trang/retry; event lưu response của trang. | ORM có UUID event, filters, versions và dataset_snapshot nhưng chưa nối router; chưa chốt event theo truy vấn hay theo trang, persistence, retry tạo mới hay dùng lại. | Quỳnh Anh quyết định lifecycle và quan hệ query_id/event/page/retry, thời điểm ghi event và xử lý lỗi ghi; không tự hứa idempotency. Không thêm feedback UI W4. |
| Versions | Cùng model_version/index_version/config_version dạng string; mock có defaults mock-*. | Client chấp nhận cả version rỗng, backend cũng chưa ràng buộc. Chưa chốt giá trị thật và cách truy ra checkpoint/revision/preprocessing/dataset snapshot. | Linh Chi cung cấp manifest/config version cụ thể; Quỳnh Anh bảo đảm IDs versions trỏ đúng cấu hình request và event. Đề xuất version không rỗng; chưa đổi schema. |
| Validation 400 / 422 | Runtime handler đổi RequestValidationError thành 400 INVALID_REQUEST, có details; OpenAPI bỏ 422. Client search coi cả 400/422 là invalid để tương thích lịch sử. | Nháp W1 ghi 422 nhưng đã đánh dấu lịch sử, không phải mâu thuẫn contract active. API v1 còn câu mô tả client chỉ xử lý 422 đã lỗi thời. | Giữ validation 400 theo API mock #9 đã đối chiếu; cập nhật mô tả client theo code. Không tự chuyển backend về 422. |
| Error 503 / 500 / 404 | Envelope `{error:{code,message,details}}`; 500 INTERNAL_ERROR, route tắt trả 404 HTTP_404. Search client dùng thông báo cố định theo status, không đọc body/code; asset client có đọc code. | Nháp W1 đề xuất 503 SEARCH_UNAVAILABLE; router/OpenAPI search hiện chỉ có 200/400/404/500, chưa có nhánh readiness/unavailable. Client nhận 503 nhưng đó không phải bằng chứng backend phát 503 đúng. | Quỳnh Anh + Linh Chi xác nhận lỗi model/index/Qdrant chưa sẵn sàng => 503, code nào, retry được khi nào; đề xuất SEARCH_UNAVAILABLE cùng envelope, lỗi nội bộ 500. Chưa có quyết định. |
| Mock / thật | Backend SearchResponse.mock là Literal[True]; mock source=fixture, IDs/versions mock-*. Frontend isMockMode chỉ chọn local mock hay HTTP. | SearchResponse TS không có mock và parseResponse không kiểm tra cờ; cờ sai/thiếu cũng không bị chặn. Backend schema hiện không thể trả mock=false hợp lệ cho search. `source` là provenance asset, không phải kiểu retrieval; list mock=false chỉ nghĩa đọc DB. | Quỳnh Anh xác nhận mock boolean bắt buộc và false cho đường thật (cần schema/backend/DTO thay đổi sau quyết định); Linh Chi cung cấp manifest và bằng chứng encoder/index thật. Không dùng riêng cờ false hay HTTP mode để chứng minh dữ liệu thật/chất lượng. |

## Nội dung chuẩn bị để Quỳnh Anh xác nhận

Đây là nội dung bàn giao local, chưa gửi tin nhắn/comment và chưa có câu trả lời:

1. Có giữ request/response top-level, validation 400, rank theo trang và metadata nullable như API mock #9 không? Có siết strict integer cho face_count filters và invariant ID/URL không?
2. Chọn semantics pagination/total cùng Linh Chi trước khi client thay đổi: tập kết quả nào được đếm, giới hạn ứng viên, threshold, thứ tự giữa các trang. Không trả total ước lượng mà vẫn yêu cầu validator hiện tại coi là count chính xác.
3. query_id và search_event_id tạo/ghi khi nào, theo query hay trang? Retry/đổi trang tạo event mới hay tái sử dụng? Ghi DB lỗi có làm request thất bại không? Event lưu versions/dataset snapshot nào?
4. Phân biệt mock/real bằng cờ nào, có bắt buộc `mock` boolean trên response không? Search route thật hoạt động khi tắt mock/production thế nào? Chưa dùng Literal[True] để trả false.
5. Xác nhận 503/code cho dependency chưa sẵn sàng, envelope và hành vi retry; 500 dành lỗi nội bộ. 404 route tắt cần phân biệt với kết quả rỗng 200.
6. Search và detail đọc cùng asset IDs/metadata nguồn nào? Bàn giao source_url/thumbnail HTTP(S) hoặc null; author/license text. Có cần URL tác giả/license riêng trong W3 không? Nếu có, chốt schema trước; không tự tạo URL từ tên.

## Nội dung chuẩn bị để Linh Chi xác nhận

1. Retrieval W3 dùng checkpoint/revision, similarity, normalization/preprocessing, dimension và index/dataset snapshot nào? Bàn giao manifest và điều kiện index/model tương thích.
2. Các filters nêu trong bảng có cùng semantics với metadata/index payload không, có áp dụng trước lấy top K và dedup asset không? face_count đếm mặt hay tam giác?
3. Cơ chế candidate limit/threshold/count/pagination/tie-break đáp ứng client hiện tại thế nào? Nếu không thể, cùng Quỳnh Anh đề xuất contract cụ thể thay vì tự nới validator.
4. `score`, `retrieval_sources`, `explanation` mang nghĩa gì trong baseline thật? Cung cấp ví dụ thật có version; không gắn phần trăm chính xác hoặc so chéo model không tương thích.
5. Model/index/Qdrant chưa sẵn sàng hoặc version mismatch được báo lỗi gì lên API? Cần phân biệt lỗi dependency với tập kết quả hợp lệ rỗng.

## Kiểm chứng và giới hạn

- Đã đọc tests backend [mock API](../../backend/tests/unit/test_mock_api.py), [OpenAPI](../../backend/tests/unit/test_openapi.py), frontend [contract](../../frontend/src/features/search/contract.test.ts), [HTTP client](../../frontend/src/lib/api/search.test.ts) và [integration](../../frontend/tests/integration/backend.spec.ts).
- Chạy từ frontend: `rtk npm test -- src/features/search/contract.test.ts src/lib/api/search.test.ts` => **160/160 đạt**, 2 file. Các test dùng fixtures/fetch giả lập, không chứng minh retrieval thật.
- Đọc JSON OpenAPI đã lưu: text search summary `[Mock]`, responses 200/400/404/500, SearchResponse.mock const=true. Schema và exporter được đối chiếu tĩnh với implementation.
- Từ backend: `rtk proxy python3 -m app.export_openapi` thất bại `ModuleNotFoundError: No module named 'pydantic'`; Python mặc định cũng thiếu FastAPI/pytest/uvicorn. Không tạo lại spec, không khẳng định file đã lưu bằng OpenAPI sinh runtime hiện tại, không chạy được tests backend trong lượt này. Không thêm dependency.
- Khi có môi trường backend đúng requirements đã pin, chạy exporter và `python -m pytest tests/unit/test_openapi.py tests/unit/test_mock_api.py`; review diff spec và kết quả trước chốt. Exporter dùng settings cố định: list DB, bật các route mock ở development; spec này không đại diện search thật production.
- Tests hiện chưa kiểm chứng readiness 503 thật, strict JSON số mặt, nhận biết mock search ở client hoặc pagination/dedup trên index thật. Smoke thật cần phối hợp Minh Khuê sau khi API/retrieval sẵn sàng.

## Điều kiện chuyển sang khối 4

**Chưa đủ điều kiện triển khai tích hợp W3 theo contract thật.** Còn thiếu xác nhận owner về các quyết định trong bảng, route retrieval thật và search event persistence, detail DB đồng bộ ID/metadata, manifest/index thật và môi trường kiểm chứng OpenAPI/backend.

Có thể review tài liệu này và chuẩn bị kế hoạch test độc lập. Chỉ sửa API/schema/DTO và triển khai luồng thật sau khi owner ghi nhận quyết định cụ thể; sau đó cập nhật đồng bộ OpenAPI, docs, types, mocks và tests bị ảnh hưởng. Không suy từ 160 tests mock đạt ra acceptance criteria dữ liệu thật hoặc owner approval đã đạt.
