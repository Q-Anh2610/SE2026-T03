# Bằng chứng kiểm chứng tích hợp W5 — Issue #118

Ngày 16/11/2026, nhánh `test/118-w5-api-integration`, base
`72b51ee2242c1cf63665a7efc828408342097ca1`, working tree dirty khi kiểm chứng.
Đây là kết quả local của tác giả; CI và review của thành viên khác là các bước
riêng. Lệnh tái lập và ma trận: [hướng dẫn W5](../guides/w5-api-integration.md).

## Phạm vi

Kiểm chứng các phần đã tích hợp: jobs/status #115 (PR #119), explanation #116
(PR #120), reindex #117 (PR #122), Admin UI #103/#104 (PR #121/#123) và hồi quy
text/image search, events, feedback PostgreSQL.

Bốn tests coexistence mới dùng một app/DB chung: search/feedback trước, trong,
sau reindex succeeded/failed; replay và 409; rollback feedback rồi phục hồi;
commit job cuối bị DB từ chối không báo thành công và không làm mất transaction
search/feedback độc lập. Retrieval/operation trong pytest là fixtures có nhãn.

## Môi trường

Windows 11 build 26200, Python 3.13.7 trong venv backend, PostgreSQL 17 Docker
local, Uvicorn HTTP localhost, Chrome headless qua Playwright của frontend.
DB test riêng tên `test_*`, mỗi lượt schema UUID và migrations tới 0004; không
ghi DB nghiệp vụ. CLIP CPU pinned dùng cache sẵn, Qdrant local.

Baseline search text/image: snapshot `home-interior-354-v1`, source SHA-256
`93f65237ca51060aad75f0f672b2b16f76c89a64dce64d7473791f428e944614`.
Reindex: frozen candidate 200 `home-interior-clear-200-v3`, source SHA-256
`9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`.

## Kết quả

### Tests hồi quy

- Nhóm backend trong hướng dẫn: **267 passed**, không skip, 86,05 giây,
  gồm bốn ca coexistence mới; PostgreSQL test riêng, migrations/check drift đạt.
- Frontend lint và typecheck đạt; build TypeScript/Vite đạt trong lượt E2E.
- Frontend `npm test -- --maxWorkers=2`: **580 passed / 26 files**, 44,85 giây.
  Giới hạn worker do máy 8 GB thiếu RAM; không thay assertions hoặc bỏ tests.
- E2E hiện có lần đầu: **45 passed, 1 failed**, 6,3 phút. Ca mock-desktop
  đổi theme/khôi phục query bị timeout tại thao tác `Khám phá asset` sau reload;
  đây là bộ fixtures, tách với smoke thật bên dưới.
- Chạy lại riêng ca đó, không sửa test/source:
  `npx playwright test --project=mock-desktop --grep "preserves the query" --workers=1`
  → **1 passed**, 28,9 giây (thao tác test 10,8 giây). Chưa có lượt chạy lại
  toàn bộ 46 ca đạt cùng lúc; ghi riêng hai kết quả để không che timeout đầu.
- `git diff --check` đạt.

### Smoke HTTP/browser/model thật

Smoke hoàn tất `2026-11-16T13:07:46.433899+00:00` (20:07 Asia/Bangkok),
status **passed**. Hai lượt browser không intercept/mock HTTP đều đạt.

| Kiểm chứng thật | Kết quả |
|---|---|
| Text/image search và explanation qua UI | 200, mock=false, cosine và nguồn retrieval đúng |
| Feedback qua UI | 5 phản hồi trả 201/storage=postgresql, đối chiếu lại event/feedback trong DB |
| Reindex từ UI | Hủy không POST; xác nhận gửi đúng một POST; trả 202/job ID |
| Replay và cạnh tranh | Cùng request ID trả 200/cùng job; ID khác lúc bận trả 409 |
| Jobs/status UI | Quan sát queued/running và progress chưa xác định, sau đó succeeded, versions/count/search_verified đúng |
| Search khi reindex chạy | Text search/feedback vẫn thành công; text/image search/feedback tiếp tục đạt sau terminal |
| Child runner lỗi | Cache rỗng có chủ đích → failed/INDEXING_FAILED, result=null; UI hiển thị lỗi, không báo thành công |
| Auth và lỗi | Khóa sai bị từ chối trên UI; job không tồn tại 404; query rỗng 400; feedback ngoài trang 400 |
| Transaction | DB từ chối INSERT feedback → 500/không thêm row; search/jobs reads còn hoạt động, gỡ constraint rồi ghi được 201 |
| Index unavailable | 503/không thêm search event, phục hồi xong search 200 |
| Index mới qua HTTP riêng | Search 200 và feedback 201, versions đúng output mới |
| Baseline | Versions trong kết quả/event giữ nguyên; hai fingerprint persisted không đổi |
| Admin key | Xóa khóa khỏi phiên, không còn trong local/session storage; reload input rỗng |

DB cuối lượt có **11 search events, 8 feedbacks**; gồm các lượt HTTP ngoài UI
và kiểm index mới. Verifier dọn schema/server/browser; launcher local dọn DB
test do chính nó tạo. Report runtime và output index nằm ngoài Git.

Job thành công `089675a5-debf-4c8c-8342-8eafc879d434`:

- 200 assets/200 points; succeeded=200, failed=0, skipped=0; progress 200/200.
- Index `reindex-clip-089675a5debf4c8c83428eafc879d434`.
- Manifest SHA-256 `46ebe5f47239e80637452fa473432d8c196ecafd1999d519239dfd50ad272ebf`.
- Model `openai/clip-vit-base-patch32@3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`,
  config `clip-text-exact-all-filtered-v1-k200`; snapshot/hash đúng candidate 200.
- Job lỗi có chủ đích `610abbe9-c0c2-4303-91e1-d55ec22721ba`.

Active baseline text `issue65-home-interior-354-v1-clip-v1`, image
`issue76-clip-build-16556914413d`; cấu hình image
`image-exact-all-filtered-rgb-v1-k200`. Cả hai vẫn dùng model pinned và snapshot
354 nêu trên. Fingerprints trước/sau:

- Text: `4ec8a57d3532cb126ebca29d818d6e85aa1c36231eb88b2d208f6101b559c687`.
- Image: `e17e9c523799dfa35bbe2a9ea50e7787e380031a24a35afec57e8d6812348f8f`.

Raw report `data/processed/issue118/w5-http-browser.json`, gồm module hashes,
versions và browser observations; SHA-256
`83c839e086365b7ab2d36d3139547105a02d90b8980c53b2ff6923e4c87bb71a`.
Output `data/processed/issue118/reindex/<job UUID>/`, không đưa ảnh/index/cache
vào PR. Các lượt thử trước đã gặp timeout startup và selector trùng trong
verifier; đã tăng hạn chờ riêng và scope selector, sau đó chạy lại trọn luồng đạt.

## Giới hạn và bàn giao

- Smoke ảnh dùng preview đã nằm trong index, chỉ kiểm upload/API/UI; không
  dùng làm benchmark quality/latency hoặc thay kết quả evaluation đã khóa.
- Reindex dựng output UUID mới cho candidate 200; app đang phục vụ tiếp tục
  dùng baseline 354. Không activate index hoặc thay thuật toán/contract.
- Khi DB từ chối cả commit terminal của job, job có thể giữ running; tests
  xác nhận không báo succeeded giả. Tự phục hồi worker/DB không thuộc #118.
- Duy đã review contract explanation ở PR #120; Khuê đã bàn giao Admin UI qua
  PR #121/#123. Các phản hồi trước không phải review kết quả mới #118.
- Bàn giao PR #118 cho Duy review search/feedback/explanation và Khuê review
  jobs/reindex/UI cùng bằng chứng này. Chưa tự tích xác nhận của hai người,
  CI hoặc merge; không tự đóng Issue hay đánh dấu toàn W5 hoàn thành.

Không thêm dependencies/migration, không sửa API/schema/index baseline hoặc
source frontend. Các file mới là tests, verifier và tài liệu; helper HTTP hiện
có nhận thêm hạn chờ tùy chọn, mặc định giữ nguyên.
