# Kiểm chứng tích hợp asset API — Issue #49

## Phạm vi

Kiểm chứng phần đã tích hợp từ #47/#48: migration/seed, list/detail PostgreSQL,
filters, pagination, lỗi 400/404/500 và Frontend. Tái sử dụng error handlers hiện
có; không tạo handler, migration hoặc thuật toán search thứ hai.

List/detail đọc DB; search/feedback vẫn mock. `mock=false` xác định nguồn đọc DB,
không chứng minh dữ liệu là asset thật hoặc đã searchable.

## Chuẩn bị và an toàn dữ liệu

- Cài `backend/requirements-dev.txt` vào môi trường backend, `npm ci` ở frontend.
- PostgreSQL đang chạy; tạo database **test_*** riêng và cấp quyền tạo schema.
- Khai báo `TEST_DATABASE_URL` cho phiên terminal. Không dùng DB phát triển;
  không commit URL có mật khẩu vào Git. Percent-encode ký tự đặc biệt khi cần.
- Lệnh kiểm chứng tạo schema có UUID rồi chỉ xóa đúng schema do lần chạy tạo.
  Không chạy downgrade, drop database hoặc xóa volume phát triển.

Ví dụ PowerShell, thay USER/PASSWORD bằng cấu hình test local:

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/test_asset_api'
```

## Backend: tests với PostgreSQL thật

Từ gốc repo:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests -q
```

`test_asset_api_stack.py` kiểm tra:

- Schema trống → Alembic upgrade/check → seed 7 bản ghi, chạy lại thêm 0.
- Request qua router/service và **DB session thật**, không override session.
- Filters, phân trang và metadata list/detail nhất quán.
- Lỗi DB thật do bảng test tạm thời không khả dụng: trả 500 an toàn, session
  được trả về pool; request kế tiếp hoạt động khi khôi phục bảng.
- Pipeline ingestion #41 → preview decode/checksum → upsert PostgreSQL → API.
  Tests offline chỉ giả transport HTTP, dùng PNG và metadata tự tạo; không coi
  đó là bằng chứng tải Objaverse thật. Chạy lại không tải hoặc tạo asset trùng.

Tests #47/#48 tiếp tục bao phủ metadata null, preview an toàn, 400/404 và seed.
Không cấu hình TEST_DATABASE_URL thì tests integration bị skip; đó không phải
bằng chứng kiểm thử PostgreSQL đạt.

## Frontend → Uvicorn → PostgreSQL

Từ gốc repo:

```powershell
backend\.venv\Scripts\python.exe -m scripts.verify_asset_api --ui
```

Lệnh tạo schema test, chạy migration/seed, khởi động Uvicorn ở cổng trống rồi
chạy Playwright desktop/mobile qua `npm run test:database`:

- List → filters/page/limit → detail → quay lại giữ trạng thái.
- Asset không tồn tại trả HTTP 404 thật, UI hiển thị lỗi phù hợp.
- Request list sai trả HTTP 400 thật, UI không fallback sang fixture.

Hai tests lỗi thay đổi request gửi tới backend, không dựng response giả.
Dữ liệu UI là fixture **lưu trong PostgreSQL**, khác bộ MockStore trong RAM.
Mặc định dùng Chrome local; nếu dùng Chromium của Playwright:

```powershell
$env:PLAYWRIGHT_BROWSER_CHANNEL = 'chromium'
```

Cần cài browser tương ứng qua Playwright trước. Không chạy trực tiếp
`npm run test:database` nếu chưa có server/schema do lệnh Python chuẩn bị.

## Kiểm chứng thêm subset ingestion thật

Tùy chọn, không chạy mạng ngoài trong CI:

```powershell
backend\.venv\Scripts\python.exe -m scripts.verify_asset_api --ui --live-ingestion 3
```

Lệnh dùng manifest đã bàn giao, tải tối đa 5 preview qua downloader #41, ghi
vào DB test, chạy lại để kiểm tra cache/chống trùng rồi đọc các ID qua API.
Ảnh/báo cáo pipeline nằm trong thư mục tạm và được dọn khi kết thúc.
Kết quả chỉ xác nhận subset đã chạy; không xác nhận 200 asset, Qdrant hay chất
lượng semantic search. Lỗi mạng/preview phải được ghi nhận, không chuyển sang
fixture để coi lần kiểm chứng live là thành công.

## Báo cáo và CI

- Báo cáo JSON mặc định ở `data/processed/asset-api-<timestamp>.json` (gitignore).
  Có thể dùng `--report <đường-dẫn-mới>`; lệnh không ghi đè báo cáo đã có.
- Báo cáo nêu checks, fixture/live subset và manifest hash nếu chạy live.
  Không chứa URL PostgreSQL hoặc credentials.
- Workflow `Frontend and API contract` bổ sung PostgreSQL test service và bước
  kiểm chứng UI DB. CI không tải preview live hoặc model để chạy bước này.
- Kết quả local và CI GitHub là hai bằng chứng riêng; chỉ xác nhận CI sau khi
  workflow thực sự chạy trên commit của PR.

## Review/bàn giao

### Bằng chứng local — 27/10/2026

| Kiểm tra | Kết quả | Phạm vi |
|---|---|---|
| `python -m pytest` từ backend, có TEST_DATABASE_URL | **324 passed**, không skip | Toàn bộ tests backend, gồm migration/seed và tests stack mới |
| `npm run lint`, `npm run typecheck` | Đạt | Gồm mã kiểm thử Frontend mới |
| `python -m scripts.verify_asset_api --ui --live-ingestion 3` | Đạt, exit 0 | Uvicorn/PostgreSQL thật; schema test riêng |
| Playwright database desktop/mobile | **6 passed** | List/detail/quay lại giữ trạng thái, HTTP 400/404 thật; UI dùng fixture trong DB |
| Seed | Lần đầu 7, lần sau 0 | Không tạo bản ghi seed trùng |
| Subset Objaverse live | Lần đầu 3 thành công; lần sau 3 skipped, 0 failed | Preview tải thật, lưu DB và đọc được các ID qua API; số bản ghi không tăng |
| OpenAPI export | Đã chạy lại; không đổi spec | Không có endpoint hoặc response schema mới |

Manifest của lần kiểm chứng live có SHA-256
`b37947fd1f2201dacf92e657d0580981315dd6252ad785e60657f4c1fe595e4a`.
Report local: `data/processed/issue49-verification-ab37cd67cc.json` (gitignore).
Schema, ảnh tạm và server của lần kiểm chứng đã dọn; không thay dữ liệu phát triển.
Đây không phải nghiệm thu toàn bộ 200 asset hoặc xác nhận review/CI của nhóm.

### Các xác nhận còn chờ

- Duy review cách UI hiển thị lỗi và giữ trạng thái list/detail.
- Huyền review kết quả nối pipeline #41 → DB → API và giới hạn subset.
- Khuê review tests, schema test và thay đổi workflow.

Tests tự động không thay cho xác nhận review của từng người. Không tự đóng M1
hoặc đánh dấu phần người khác đã nghiệm thu chỉ từ báo cáo này.

Sau khi thử, xóa biến khỏi phiên PowerShell nếu không dùng tiếp:

```powershell
Remove-Item Env:TEST_DATABASE_URL
```
