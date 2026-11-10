# Bàn giao image search W4 — Nguyễn Văn Duy

Ngày kiểm chứng: 10/11/2026. Phần image và feedback từ hai worktree đã được ghép
vào workspace chính `SE2026-T03`; implementation và kiểm chứng được chia thành
các commit theo khối image, feedback và tài liệu. PR #97 đã mở vào `develop`;
đã xin review Quỳnh Anh/Khuê, đang chờ required checks và nghiệm thu.

## Acceptance đã rà soát

| Tiêu chí phần ảnh | Trạng thái và bằng chứng |
|---|---|
| Chọn/thay/xóa JPEG/PNG, preview, signature/decode, 5 MiB/4096 px | Đạt unit/component và E2E; validation backend vẫn là kiểm tra cuối |
| Multipart image/filters/page/limit | Đạt client tests và HTTP thật; browser tự đặt boundary |
| Loading/results/empty/error/retry, không fallback mock | Đạt component và 4 E2E interception; HTTP thật kiểm lỗi 400/503/500 và phục hồi |
| Filters AND, bounds, áp dụng/xóa; retry/page giữ request đã gửi | Đạt unit/component; HTTP thật kiểm category/license/format/face bounds AND; UI thật kiểm format=glb và empty |
| Page mới/retry tạo event mới; giới hạn cửa sổ 200, rank theo trang | HTTP thật kiểm trang 1/2/34/35, IDs/score/versions và event DB; UI thật kiểm trang 2 |
| Detail dùng đúng ID/API, quay lại giữ ảnh/filter/page/kết quả | Đạt UI thật desktop/mobile và component; detail dùng createHttpAssetClient trực tiếp, không chọn mock client theo Vite mode |
| Detail lỗi/404/retry/back; response muộn sau back/unmount | Đạt component; metadata/detail mapping đối chiếu HTTP thật |
| UUID/query-image hash, metadata, retrieval source, cosine và versions | Client kiểm contract; UI hiển thị IDs/hash/model/index/config/snapshot từ API; DB đối chiếu events |
| Responsive/accessibility cơ bản | E2E desktop/mobile không overflow; label, aria mô tả lỗi, keyboard xóa ảnh/focus và detail/back có tests |
| Feedback persistence và toàn W4 | Đã nối feedback UI text/ảnh với #81: kiểm tra OpenAPI mode, gửi đúng event/asset/relevance, xác nhận response PostgreSQL và hiển thị lỗi/retry; test backend xác minh feedback gắn với event có versions và result snapshot | 

## Thay đổi bổ sung trong lượt hoàn thiện

- Đổi detail ảnh sang HTTP asset client, tránh API ảnh thật nhưng detail đọc mock ở Vite mặc định.
- Bổ sung tests detail thành công, lỗi, not-found, retry, giữ trạng thái và hủy response muộn.
- Thêm `frontend/tests/e2e/image-live.spec.ts` dùng được với interception hoặc API thật.
- Thêm config **riêng** `frontend/playwright.image.config.ts`, cổng 5294, một worker;
  không sửa config E2E chung để tránh ảnh hưởng terminal feedback.
- Các sửa frontend/feedback/README có sẵn từ baseline được giữ nguyên. Không sửa backend,
  API/schema, shared contract/types, dependency/lockfile hoặc model mặc định.

## Kiểm tra thực chạy

Từ `frontend/`:

| Lệnh | Kết quả |
|---|---|
| `rtk npm run lint` | Đạt |
| `rtk npm run typecheck` | Đạt |
| `rtk npm run build` | Đạt |
| `rtk npm run test:coverage` | 365/365 tests, 17 files; ngưỡng 95% từng file đạt. Statements 99,69%, branches 98,29%, functions/lines 100% |
| `rtk npx playwright test --config playwright.image.config.ts` | 4/4 ca desktop/mobile với HTTP interception, 0 lỗi |
| Cùng config với API thật, `--grep 'image upload, filters'` | 2/2 ca desktop/mobile, 0 skip/flaky, 6,1 giây |

Không chạy Playwright config chung trong lượt này; cần chạy hồi quy chung sau ghép
hai worktree. Không dùng interception làm bằng chứng retrieval thật.

## Smoke HTTP và UI ảnh thật

- Dùng Python 3.13.18 và requirements đã pin, CLIP CPU revision
  `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`, PostgreSQL 17 test riêng qua localhost.
- Preview tận dụng từ bộ W3: đủ 354 ảnh; source SHA
  `93f65237ca51060aad75f0f672b2b16f76c89a64dce64d7473791f428e944614`.
  Ready chuyển tên trường checksum sang preview_sha256 theo runner #76; SHA
  `f302f58f2321b4a77a7ec25b37abf6571fd3221476d4e0f91dce67334f6ec3a6`.
- Dựng storage ảnh **mới riêng**, không thay index text hoặc storage dùng chung:
  `data/processed/issue76/clip-build-14aac9862d77/`. 354 point, smoke module 10/10.
- HTTP dùng `scripts/verify_image_search_api.py`: PASS, 7 event ảnh và 5 event text,
  detail/IDs/rank/scores/versions khớp service; invalid image 400, thiếu index 503,
  lỗi ghi DB 500 và recovery đạt. Fingerprint persisted của cả hai index giữ nguyên.
- UI thật dùng `data/processed/run_image_ui_smoke.py` gọi verifier có sẵn và Playwright
  qua callback; không intercept response. Hai viewport 1280×900 và 390×844.
  6 response UI thành công có event image đã commit, hash ảnh, versions và
  result_asset_ids khớp DB. Query là preview đã index: diagnostic self-match,
  không phải benchmark relevance độc lập.
- Đã chạy lại UI smoke sau khi ghép, dùng frontend workspace chính cùng runner/index
  ảnh riêng. 2/2 viewport đạt; 6 event ảnh và 2 feedback POST thật được đối chiếu
  PostgreSQL. Hai feedback lưu đúng event ảnh, asset, relevance và versions của event.
  API chạy với `feedback_source=database`, không mock/interception.
- Schema test được dọn, Uvicorn/Vite và container test dừng sau chạy; index/model/preview
  và reports giữ local dưới đường dẫn Git ignore để tái lập.

Raw reports local (không đưa bulk index/test output vào Git):

- `data/processed/w4-image-http.json`
- `data/processed/w4-image-ui-smoke.json`
- `data/processed/issue76/clip-build-14aac9862d77/report.json`

UI report SHA-256 sau lần chạy lại: `4a395ec83c31acbf188ea7687e4ce443b16a3c5cc079a96bc703e73f1d52c7e2`.
Trường callback tên `feedback` trong raw report do tái sử dụng hook verifier;
**nội dung là image UI smoke**, không phải feedback endpoint/persistence.

## Source identity và chạy lại

HEAD nền: `657ed397d4116a484c72f30d3e8f19b2dd5c9fb5`. Bằng chứng smoke dùng source
W4 trong task branch; các hash dưới đây cùng raw report xác định implementation
được kiểm tra. Raw UI report cũng ghi hash toàn bộ `frontend/src`.

| File | SHA-256 khi chạy |
|---|---|
| `frontend/src/features/search/image/ImageSearchPage.tsx` | `4cbd6957e82bd268f69e6f6f71362cf90d150e52b26b37709d077af7837ffcbf` |
| `frontend/src/features/search/image/client.ts` | `cf92a711ad8bf4b5991d22348566106edc4afa941e4c03d55934285747e5cbdc` |
| `frontend/tests/e2e/image-live.spec.ts` | `88bc78bc368788db2039da7f53d90b526c7364b9a3eb40d1fc7a979971afa386` |
| `frontend/playwright.image.config.ts` | `7d9a72d9091a52ad751cad7d2f8bf5861061bc1386f2be9f20eeb039bc807cfa` |

Backend verification modules có hashes trong `w4-image-http.json`; script local
orchestration có hash trong `w4-image-ui-smoke.json`.

Để chạy lại interception, dùng lệnh ở bảng trên. Để chạy UI thật cần khởi động
PostgreSQL test riêng, đặt `TEST_DATABASE_URL` (không ghi credentials vào docs),
đóng mọi process đang giữ hai Qdrant local storage, rồi từ gốc worktree chạy:

```bash
OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 /home/nguyenduy/Documents/Projects/SE2026-T03/backend/.venv/bin/python data/processed/run_image_ui_smoke.py
```

Script này tận dụng index text local đã có ở workspace gốc và image index riêng
của worktree, seed schema test tự sinh, chạy HTTP/UI rồi đối chiếu event và dọn schema.
Máy khác cần dựng/nhận inputs theo [runbook image API](image-search-api.md), thay
đường dẫn local và Python tương ứng. API origin chỉ sống trong lượt verifier.

## Kiểm chứng sau ghép

| Lệnh | Kết quả trên workspace đã ghép |
|---|---|
| `npm run lint` | Đạt |
| `npm run build` | Đạt; gồm TypeScript typecheck |
| `npm run test:coverage` | 371/371 tests, 17 files; statements 99,55%, branches 98,24%, functions/lines 100%; ngưỡng từng file đạt |
| `npx playwright test --config playwright.image.config.ts` | 4/4 image E2E với HTTP interception |
| `npm run test:e2e` | 36/36 E2E chung, desktop/mobile, mock/API/production preview |
| `BACKEND_PYTHON=... npm run test:integration` | 8/8 browser/API tests với FastAPI mock backend, desktop/mobile; có upload ảnh và feedback HTTP mock |
| UI smoke với API/CLIP/index/PostgreSQL thật | 2/2 viewport; 6 event ảnh và 2 feedback gửi từ UI khớp bản ghi, event/version/result IDs trong PostgreSQL; không interception |
| `pytest backend/tests/integration/test_feedback_stack.py -q` với PostgreSQL test riêng | 8/8; text/image, event+asset, versions/snapshot, lưu bền sau restart, retry/đổi rating, lỗi và phục hồi |
| `pytest backend/tests/unit/test_feedback_api.py backend/tests/unit/test_mock_api.py -q` | 49/49; validation, OpenAPI, mock contract và error envelope |

E2E frontend và image config dùng fixture/interception; `test:integration` chạy
browser với FastAPI nhưng feedback store là mock. Các lệnh này không thay thế
retrieval thật. HTTP/UI image smoke thật sau khi ghép dùng frontend workspace chính
và raw reports ở các mục trên; feedback chạy trên PostgreSQL test riêng. CI, review
và merge chưa được thực hiện.
