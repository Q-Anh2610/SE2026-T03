# Smoke Admin Reindex UI — Issue #104

Ngày 15/11/2026. Smoke do người dùng thao tác trên trình duyệt local và cung cấp
ảnh UI; agent đọc artifact trên đĩa để đối chiếu. Tách khỏi E2E HTTP interception.

## Môi trường và source

- Frontend: nhánh `feat/104-admin-reindex-ui`, base
  `ae3f33a1f8231a5aeea49170c1f168a1cb04b153`, code #104 chưa commit khi smoke.
- Backend: worktree riêng tại commit
  `7a43d79a9af1545c7a9ebd4900671c311bec420e`; manifest ghi working_tree_dirty=false.
- Frontend origin `http://127.0.0.1:5173`; Uvicorn backend
  `http://127.0.0.1:8001`. Backend startup thành công do người dùng xác nhận.
- Python 3.13.15, torch 2.8.0+cpu, transformers 4.57.1; model/cache sẵn trên máy,
  cấu hình Hugging Face offline. PostgreSQL 17 local, DB riêng
  `test_issue104_reindex`. Migration/check chạy, check báo không schema drift;
  truy vấn trực tiếp `alembic_version` sau đó xác nhận revision `0004`.
- Khóa admin và cấu hình chỉ trong file env local được Git ignore; không đưa vào
  bằng chứng. Output riêng trong `data/processed/issue104/reindex-output/`.

## Kết quả quan sát

Ảnh người dùng cung cấp: trang **Theo dõi job đã chọn** hiển thị:

- Job `b1125421-c1c3-48b3-96fb-2e97d09bbe65`, trạng thái **Thành công**.
- Progress 100%, processed/total = 200/200, mã thoát runner 0.
- Index `reindex-clip-b1125421c1c348b396fb2e97d09bbe65` và model CLIP đúng revision.
- UI ghi thời điểm tạo/bắt đầu/kết thúc lúc 12:57 ngày 15/11/2026.

Agent đọc `index-manifest.json` và `search-check.json` trong output của đúng UUID:

| Kiểm tra | Kết quả |
|---|---|
| asset_count / point_count trong manifest | 200 / 200 |
| Model | openai/clip-vit-base-patch32 |
| Model/processor/tokenizer revision | 3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268 |
| Dimension / preprocessing / similarity | 512 / clip-slow-processor-rgb-l2-v1 / Cosine, L2 |
| Snapshot | home-interior-clear-200-v3 |
| Source SHA-256 | 9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd |
| Retrieval config | clip-text-exact-all-filtered-v1-k200 |
| Search check | passed=true, hit_count=200; versions khớp manifest |
| Hash source.json và ready.json | Tính lại bằng SHA-256 và khớp manifest |
| SHA-256 index-manifest.json | 3f638461c4511abaa775513f4837baabf5b0ec47bbde892b927044f40d773572 |

Manifest created_at_utc `2026-11-15T05:57:45.050043Z`. Không copy weights, ảnh,
Qdrant storage hoặc runtime reports vào Git. Screenshot trong hội thoại không
được sao chép vào repo.

## Đối chiếu PostgreSQL và xác thực

- Người dùng đã chạy SELECT trực tiếp trong DB test và cung cấp output: UUID
  khớp UI, status=succeeded, processed=total=200, input_count=succeeded=200,
  failed=skipped=0, asset_count=point_count=200, exit_code=0, error=null và
  search_verified=true. Index/model/snapshot và cả hai manifest hashes khớp
  artifact đã đọc; revision Alembic `0004`.
- Hai ảnh UI bổ sung xác nhận reset/nhập khóa sai báo lỗi quản trị; nhập lại
  khóa đúng xem lại được cùng job succeeded, không cần yêu cầu operation mới.

## Hồi quy sau tích hợp backend

Nhánh #104 đã đồng bộ tới `89c2ba6`, gồm merge PR #122 tại `66d60f8` và backend
`7a43d79`, không có conflict. Agent đối chiếu 10 file contract/API/schema/runner
với worktree đã smoke, nội dung giống nhau; xem hướng dẫn bàn giao.

Output người dùng cung cấp ngày 15/11/2026, lượt 23:03:

- Admin/App: 225/225 tests trên 11 files đạt.
- Production build/typecheck: đạt, Vite 7.3.7.
- Backend unit: reindex API/builder, jobs API và OpenAPI đạt 38/38, 13,16 giây.
- Sau khi chuyển backend sang checkout đã tích hợp, UI ban đầu báo không thể tải
  job khi PostgreSQL dừng. Người dùng khởi động lại PostgreSQL và cung cấp output
  container `healthy`; tải lại UI sau đó hiển thị đúng job cũ succeeded, progress
  100%, 200/200, exit_code=0, index/model/snapshot và hash khớp bằng chứng trên.
  Đây là kiểm tra đọc lại job đã lưu và phục hồi sau gián đoạn DB; không phải
  một lượt POST/reindex mới trên checkout đã tích hợp.

## Giới hạn và việc còn kiểm chứng

- Chưa có bằng chứng smoke thật riêng cho hủy xác nhận, progress null khi running,
  mất kết nối/retry, replay/409 hoặc failed operation của lượt #104 này;
  các hành vi đó có tests component/contract/E2E giả lập. Không dùng tests giả
  lập để ghi nhận đã smoke thật từng trường hợp.
- Search check là direct service search trên index mới, không phải HTTP search
  đang phục vụ hoặc benchmark chất lượng. Không có bước activate index.
- Không chạy lại fingerprint baseline độc lập trong lượt UI này; phạm vi không
  ghi đè dựa trên output riêng/cấu hình và code backend đã đối chiếu.
- UI đã commit/push tại `ff77f0a`, có [Draft PR #123](https://github.com/Q-Anh2610/SE2026-T03/pull/123)
  vào develop; nhánh sau đó đồng bộ `89c2ba6`. Bản cập nhật tài liệu này chưa commit.
  Lượt CI 5/5 trước tích hợp đã được quan sát; chưa xác minh lại CI/review hiện tại
  sau tích hợp, không coi kiểm thử local là bằng chứng approve hoặc merge PR #123.
