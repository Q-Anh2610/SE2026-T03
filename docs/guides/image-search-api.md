# Image search API — #80

`POST /api/v1/search/image` dùng multipart của #79 và service CLIP của #76.
Ảnh được kiểm tra trước retrieval. API nhận tối đa 200 ứng viên sau filters/
dedup, đối chiếu toàn bộ IDs và filters với metadata PostgreSQL rồi chia trang.
Detail dùng cùng asset ID và metadata mapping.

## Request và response

| Trường multipart | Quy tắc |
| --- | --- |
| `image` | Bytes JPEG/PNG, tối đa 5 MiB, 4096 px mỗi chiều, decode được |
| `filters` | Chuỗi JSON, mặc định `{}`; category/license/format và cận face_count kết hợp AND |
| `page` | Integer từ 1, mặc định 1 |
| `limit` | Integer 1–50, mặc định 12 |

Frontend dùng FormData và để trình duyệt tự đặt boundary.
Ví dụ trên API đã cấu hình service:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/search/image -F 'image=@preview.jpg' -F 'page=1' -F 'limit=12'
```

Response dùng cấu trúc chung với text search W3. `mock` bằng `false`,
`retrieval_sources` bằng `["clip_image_to_preview"]`, score là cosine CLIP.
`query` bằng `sha256:<64 ký tự hex>` của bytes ảnh gốc. Đây là định danh
nội dung, không có cơ chế tải lại ảnh qua hash. `query_id` và
`search_event_id` là cùng một UUID đã commit.

`total` mô tả cửa sổ tối đa 200 ứng viên. Rank bắt đầu từ 1 trong mỗi trang.
Kết quả rỗng và trang vượt phạm vi trả 200 và vẫn tạo event.
Xem schema và ví dụ tại [OpenAPI image service](../openapi-image-search.json).
Spec này bật cả text và image service; spec mock và text service vẫn xuất riêng.

## Event và lỗi

Search event lưu `query_type=image`, `query_text=null`,
`query_image_ref=sha256:...`, filters cùng model/index/config/dataset versions
thực tế. File ảnh được xử lý trong bộ nhớ và UploadFile được đóng sau validation.
Mỗi request thành công, kể cả retry/phân trang, tạo event mới. Feedback persistence
được phát triển ở #81 dựa trên event này.

| HTTP | Quy tắc |
| --- | --- |
| 400 | Validation upload từ #79, filters JSON sai hoặc page/limit sai |
| 503 `SEARCH_UNAVAILABLE` | Adapter/index/model/Qdrant chưa sẵn sàng, candidate thiếu DB hoặc metadata lệch filters |
| 500 `INTERNAL_ERROR` | Retrieval bất ngờ lỗi, mapping response lỗi hoặc DB đọc/ghi thất bại |

Request validation và retrieval thực hiện trước khi mở DB session. Mapping và
serialization được kiểm tra trước commit. Persistence lỗi rollback; session được
đóng theo request. Error envelope chỉ chứa thông báo an toàn. Khi dependency lỗi,
API trả lỗi thay vì dùng kết quả fixture.

## Cấu hình và lifecycle

Chép các trường mẫu từ `.env.example` vào môi trường local rồi đặt đường dẫn
đúng máy. Các đường dẫn dưới đây là ví dụ cần thay.

```dotenv
APP_IMAGE_SEARCH_SOURCE=service
APP_IMAGE_INDEX_MANIFEST=C:/path/to/image-index-manifest.json
APP_IMAGE_INDEX_ROOT=C:/path/to/handoff-root
APP_IMAGE_QDRANT_LOCAL_PATH=C:/path/to/image-qdrant
```

Để dùng Qdrant server, bỏ local path và đặt `APP_IMAGE_QDRANT_URL` cùng API key
nếu cần. Chạy Uvicorn từ backend bằng `python -m uvicorn app.main:app`.
PostgreSQL phải có metadata khớp IDs/snapshot trong index.

App nạp model và manifest một lần lúc startup, xử lý retrieval CPU trong thread
pool và serialize access bằng lock. Client được đóng một lần lúc shutdown.
Cache/model/index thiếu vẫn giữ `/healthz` hoạt động, image search trả 503.
Sau khi sửa cấu hình/index, restart app để bootstrap lại.

Mỗi process chỉ mở một Qdrant local storage. Dùng storage ảnh riêng với text
nếu bật cả hai. Bootstrap nhận `ImageIndexManifest` của #76, kiểm source/ready
hashes, count, model/processor và chỉ dùng baseline CLIP. Cutoff diagnostic k10
trong manifest không đổi vectors; API truy xuất k200 và ghi config_version
`image-exact-all-filtered-rgb-v1-k200` của lần chạy thực tế.

## Chạy kiểm chứng

Unit tests từ backend:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit -q
```

Integration tests cần `TEST_DATABASE_URL` dùng driver `postgresql+psycopg`
và database riêng tên `test_*`. Từ gốc repo:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_image_search_stack.py backend/tests/integration/test_text_search_stack.py backend/tests/integration/test_search_events.py -q
```

Tests trên dùng retrieval fixture và PostgreSQL thật. Verifier HTTP với CLIP thật
dùng các tham số từ lượt local bên dưới, thay bằng đường dẫn index của máy đang
chạy. Các tham số text phục vụ hồi quy HTTP text search trong cùng lượt.

```powershell
backend\.venv\Scripts\python.exe scripts/verify_image_search_api.py --index-manifest data/processed/issue65/index-1718ec3c49a0/index-manifest.json --index-root data/processed/issue65/index-1718ec3c49a0 --qdrant-local-path data/processed/issue65/index-1718ec3c49a0/qdrant --image-index-manifest data/processed/issue76/clip-build-16556914413d/index-manifest.json --image-index-root data/processed/issue80/inputs-cfd29f05b4 --image-qdrant-local-path data/processed/issue76/clip-build-16556914413d/qdrant --output data/processed/issue80/http-verification.json
```

Verifier tạo/xóa schema tự sinh trong DB test đã cung cấp. Nó seed metadata từ
cùng nguồn, chạy Uvicorn qua TCP localhost, so IDs/scores/rank/versions với service
CLIP, kiểm detail/events, lỗi index/ghi DB và phục hồi. Sau dừng server, verifier
mở lại hai storage để đối chiếu point count và fingerprint persisted.

Đầu vào local được đóng gói lại từ preview đã cache của #65, đối chiếu đủ 354
checksum với provenance snapshot Huyền chốt ở #76. Source SHA giữ nguyên
`93f65237ca51060aad75f0f672b2b16f76c89a64dce64d7473791f428e944614`.
Ready được dựng lại theo trường `preview_sha256` mà runner #76 nhận, hash riêng
`f302f58f2321b4a77a7ec25b37abf6571fd3221476d4e0f91dce67334f6ec3a6`.
Đây là gói local tái lập từ các ảnh cùng checksum. Máy khác có thể dùng nguyên
gói Huyền/Chi và source/ready hashes của gói đó khi dựng index riêng.

## Bàn giao

- Duy: dùng multipart #79 và response image service trong OpenAPI, giữ file/
  filters/page khi retry và hiển thị lỗi theo envelope. Detail lấy ID từ kết quả.
- Chi: API gọi đúng `search_image(image_bytes, filters, candidate_limit=200)`,
  nhận `TextSearchCandidates`, map lỗi ảnh sang 400 và readiness sang 503.
- Khuê: dùng verifier cùng snapshot/hash/versions để kiểm chứng; UI E2E và bộ
  image benchmark có nhãn được ghi nhận riêng theo phần việc của nhóm.

Kết quả local và giới hạn được ghi tại
[bằng chứng #80](../evidence/issue80-image-search-http.json).

Ngày 07/11/2026, 653 unit tests đạt (157,29 giây). Nhóm chọn lọc API/PostgreSQL
30 tests đạt (25,57 giây, gồm tests unit API và integration với retrieval fixture).
Lượt HTTP qua CLIP thật đã đối chiếu các trang 1/2/34/35, filters AND, empty,
detail và versions. Có 7 event ảnh và 5 event text đã commit trong schema test.
Lỗi 400/503/500 được kiểm chứng và request sau phục hồi thành công.
354 point và fingerprint persisted của index ảnh, cùng index text hồi quy,
không đổi. Server đã dừng và DB/schema test đã dọn.

Lượt này dùng ảnh preview đang có trong index làm query diagnostic. Frontend
image E2E, Qdrant server mode và image benchmark có nhãn cần kiểm chứng riêng.
CI, review và xác nhận tiếp nhận của Duy/Khuê được ghi theo kết quả GitHub thực tế.
