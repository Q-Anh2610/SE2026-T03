# Kiểm chứng text search xuyên suốt — Issue #66

Phạm vi: HTTP → CLIP text-to-preview của #60 → Qdrant → metadata PostgreSQL
→ search event, cùng luồng trình duyệt. Tái sử dụng API #63/#65; không thay API,
schema DB, model, thuật toán retrieval hoặc mã giao diện sản phẩm.

## Những kiểm tra được bổ sung

Tests #63/#65 đã kiểm validation, mapping, transactions, rollback, lifecycle,
OpenAPI và bootstrap bằng encoder/retrieval fixture. #66 tái sử dụng các tests
đó; bổ sung đối chiếu với model/index thật và UI qua HTTP, không giả response.

| Ca | Kiểm chứng |
|---|---|
| Query `wooden chair` | IDs, scores (sai số ≤ 1e-6), thứ tự, total, versions bằng kết quả gọi trực tiếp cùng search service |
| Trang 1/2 và biên 34/35, limit 6 | Không trùng ID giữa trang; cửa sổ 200, rank bắt đầu lại từ 1, trang vượt cửa sổ rỗng |
| Filters AND | category/license/format và hai cận face_count bằng nhau; metadata DB cùng snapshot |
| Category không tồn tại | HTTP 200, total 0, không fallback fixture; vẫn lưu event |
| Query/page/limit/face_count sai | 400 `INVALID_REQUEST`, không tạo event |
| Collection thiếu / revision không tương thích | 503 `SEARCH_UNAVAILABLE`, không tạo event, phục hồi request thành công |
| Lỗi đọc metadata / lỗi ghi event | 500 `INTERNAL_ERROR`, rollback, không tạo event; request sau phục hồi ghi được |
| UI desktop/mobile | Query, đổi limit, trang 2, detail/back giữ query/page/limit và filters; kết quả rỗng; lỗi 503/500 rồi retry cùng payload |
| Event từ UI | Lấy ID thật từ response trình duyệt, đối chiếu query/filters/versions với row PostgreSQL đã commit |
| Index | Point count và SHA-256 của toàn bộ IDs/payload/vectors lưu bền không đổi sau lượt chạy |

Các ca lỗi nằm trong **app kiểm chứng riêng**, dùng schema tạm trong database
`test_*`. Controller có URL ngẫu nhiên trên localhost, không nằm trong OpenAPI
hoặc `app.main` của sản phẩm. Collection thiếu/revision sai chỉ đổi tham chiếu
trong bộ nhớ; không sửa index. Lỗi DB được tạo bằng rename bảng assets hoặc
CHECK constraint chặn insert event trong schema tạm, rồi khôi phục sau từng ca.
Đây là fault injection có kiểm soát; chưa kiểm outage mạng tới Qdrant server.

## Dữ liệu và môi trường

- Model: `openai/clip-vit-base-patch32`, revision
  `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`; CPU, weights có sẵn trong cache.
- Snapshot: `home-interior-354-v1`, source manifest SHA-256
  `93f65237ca51060aad75f0f672b2b16f76c89a64dce64d7473791f428e944614`.
- 354 asset/preview/vector; verifier kiểm source/ready hashes, metadata, IDs
  và checksum từng ảnh trước khi nhập vào PostgreSQL test.
- Bộ index local tái sử dụng từ #65:
  `data/processed/issue65/index-1718ec3c49a0/` (Git ignore).
  Máy khác dựng bằng [hướng dẫn #65](text-search-api.md), không cần tải lại
  trên máy đã có bộ này; không trỏ tới index đang được process khác mở.
- PostgreSQL 17; Qdrant **persistent local** qua Python client, không phải
  Qdrant server. Chi tiết Python/OS/versions/fingerprint ở bằng chứng JSON.

## Chạy lại

Cần dependencies backend/search đã khóa trong repo, frontend `npm ci`, Chrome
hoặc browser channel đã cài cho Playwright, PostgreSQL và database test riêng.
`TEST_DATABASE_URL` phải dùng driver `postgresql+psycopg`, database tên `test_*`.
Đặt URL trong môi trường terminal; không ghi credentials vào tài liệu/Git.
Verifier chỉ tạo/xóa schema tự sinh, không tự tạo/xóa database được cung cấp.

Từ gốc repo, sau khi cấu hình `TEST_DATABASE_URL`:

```powershell
backend\.venv\Scripts\python.exe scripts/verify_text_search_integration.py --index-manifest data/processed/issue65/index-1718ec3c49a0/index-manifest.json --index-root data/processed/issue65/index-1718ec3c49a0 --qdrant-local-path data/processed/issue65/index-1718ec3c49a0/qdrant --frontend-revision b889f40cdc548980a94e70bed8a104040afcd471 --output data/processed/issue66/develop.json
```

`--frontend-revision` là SHA của **source UI đang kiểm**, không tự thay bằng HEAD
nếu UI đã đổi. Verifier đối chiếu src/public/build inputs với Git archive của SHA
đó, kiểm dependencies, rồi mới chạy. Tests/config mới của #66 nằm ngoài source
sản phẩm được đối chiếu. Backend base commit và hashes code kiểm chứng được ghi
riêng, vì thay đổi #66 chưa commit khi chạy local.

Verifier khởi động Uvicorn và Vite ở hai cổng localhost trống, cấu hình CORS đúng
origin Vite và truyền `VITE_API_BASE_URL` cho UI. Playwright chạy 4 ca × desktop/
mobile, workers=1. Không chạy các test fault này song song lên một server chung.
Sau chạy: dừng server, đóng Qdrant, dọn schema test. API origin trong report chỉ
có hiệu lực trong lượt chạy, **không phải địa chỉ dịch vụ bàn giao chạy lâu dài**.

`npm run test:semantic` là entrypoint Playwright do verifier gọi; không chạy độc
lập với API phát triển vì thiếu controller lỗi và dữ liệu test tương ứng.
Raw report mạng, traces khi lỗi và screenshots nằm ở `data/processed/issue66/`
và `frontend/playwright-report/semantic/` (Git ignore).

## Bản UI của Duy chưa merge

Để kiểm PR #68 mà không mang code chưa merge vào nhánh #66, có thể xuất nguyên
thư mục frontend từ SHA PR ra thư mục riêng nằm trong `data/processed/issue66/`,
cài dependencies theo lockfile của bản xuất. Chạy cùng lệnh trên, thêm:

```text
--frontend-dir data/processed/issue66/pr68/frontend
--frontend-revision 3008f1981a68ea1988595fcb655145459b4050c1
--output data/processed/issue66/pr68.json
```

Không sao chép source PR vào frontend đang làm việc. Kết quả bản xuất chỉ áp
dụng SHA đã ghi; không chứng minh PR đã được approve/merge hoặc các thay đổi
khác trong PR đều được kiểm thử.

## Kết quả và bàn giao

Kết quả thực chạy lưu tại [bằng chứng #66](../evidence/issue66-text-search-integration.json).
Không dùng test local để xác nhận CI, review hoặc benchmark chất lượng retrieval.

Ngày 05/11/2026, trên Windows 11 / Python 3.13.7:

- 70 tests backend API/contract/runtime/PostgreSQL: đạt, không skip, 8,65 giây.
  Danh sách sáu file test có trong JSON bằng chứng.
- UI hiện có ở develop `b889f40`: 8/8 ca đạt, 59,3 giây.
- UI xuất riêng từ PR #68 `3008f19`: 8/8 ca đạt, 54,1 giây.
- Mỗi lượt: 14 request UI thành công có event tương ứng đã commit;
  tổng 29 event gồm base smoke và các ca HTTP/UI mở rộng. Lỗi 400/503/500
  không tạo event; phục hồi thành công. Hai lượt dùng schema/database test riêng.
- 354 point và fingerprint toàn bộ index không đổi; backend/server đã dừng,
  tài nguyên DB test đã dọn. Lint, typecheck và build frontend đều đạt.
- Đã xem screenshot mobile. Preview dùng URL bên ngoài và lazy loading;
  bộ này không xác nhận mọi ảnh đã tải hoặc chất lượng xếp hạng semantic.

- Duy: dùng [contract #63](../contracts/text-search-w3.md),
  [OpenAPI service](../openapi-text-search.json), cấu hình origin/CORS ở trên;
  payload filters và các query/IDs/scores/versions cụ thể có trong JSON bằng chứng.
  Asset detail dùng đúng ID trả về từ search. Empty là 200; lỗi readiness 503,
  DB 500 dùng error envelope; retry tạo event mới sau khi phục hồi.
- Khuê: tái chạy verifier trên snapshot/hash đã ghi, đối chiếu event trong DB
  trước khi schema được dọn; tests tự làm bước này từ response mạng của UI.
  Bộ này phục vụ #66, không thay xác nhận smoke riêng của #72 hoặc benchmark #71.
- Chi: phần đối chiếu dùng chính `TextSearchService.search_text(...,
  candidate_limit=200)` và runtime adapter hiện có; không có thuật toán thay thế.

Chờ Duy/Khuê xác nhận tiếp nhận/kết quả trên Issue/PR. Giữ tiêu chí xác nhận
con người chưa tick; không tự ghi nhận approval hoặc đóng #66 thay reviewer.
