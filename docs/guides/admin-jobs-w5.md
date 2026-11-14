# Bàn giao Admin jobs/status W5 — Issue #103

Owner UI: Đoàn Thị Minh Khuê. Backend: PR #119, base local `112df08`.
Bằng chứng local được thu thập trên nhánh `feat/103-admin-jobs-status-api`.
Trạng thái PR, CI và review được theo dõi riêng trên GitHub của Issue #103.

## Hành vi và phạm vi

- Route chính `/#admin-status` dùng jobs API thật; fixtures chỉ ở route preview
  development và tests, không fallback khi HTTP thất bại.
- Dùng DTO jobs, `X-Admin-Key`, filters kind/status, page/limit và error envelope
  đã bàn giao. Mỗi trang 12 job, giữ thứ tự backend; retry chỉ gọi GET.
- Khóa được nhập lúc chạy, giữ trong React state và xóa khi rời/reset trang;
  không lưu vào Web Storage, URL, biến Vite hoặc bundle.
- Hủy request khi thay trang/filter/khóa hoặc unmount; bỏ kết quả/lỗi cũ.
- Progress null không suy ra 0%; job failed ở 100% vẫn hiển thị thất bại.
- Không đổi API/schema/index/dependencies. Không triển khai #104/#117, HTTP
  tạo/retry job hoặc tự chạy CLIP indexing để thử UI.

## Bằng chứng đã có

Các kết quả sau do người dùng chạy và cung cấp output/ảnh trong phiên làm việc
ngày 15/11/2026; không phải lượt agent tự chạy lại:

| Kiểm tra | Kết quả quan sát |
|---|---|
| Migration và drift | `0003 (head)`; `No new upgrade operations detected.` |
| Swagger GET jobs | HTTP 200; items rỗng, pagination hợp lệ, mock=false |
| UI khóa đúng / xóa phiên | Danh sách rỗng; xóa phiên quay lại yêu cầu nhập khóa |
| Khóa sai rồi nhập đúng | Hiện lỗi xác thực; kết nối lại thành công, không có fixtures |
| Dừng API / khởi động lại / retry | Hiện lỗi kết nối; retry đọc được dữ liệu, không cần nhập lại khóa |
| Ingestion thật, limit 1, persist-db | UI hiển thị succeeded, processed=1/1, 100%, downloaded=1, failed=0, skipped=0, PostgreSQL |
| Manifest cố ý không tồn tại | CLI status=failed; UI hiện RUNNER_FAILED và progress chưa xác định |
| Bộ lọc UI | Hiển thị danh sách/lọc failed/kết hợp ingestion hoặc indexing/empty; Tải lại giữ bộ lọc |
| Unit/component + coverage | 501 passed / 21 files; statements 99,27%, branches 98,34%, functions và lines 100%; ngưỡng 95% từng file đạt |
| Typecheck và lint | Đạt sau lượt 501 tests |
| Build production | `tsc --noEmit && vite build` đạt; Vite 7.3.7 |
| E2E toàn frontend | 42 passed, gồm 6 ca Admin trên api-desktop và production-mobile; HTTP interception, không phải backend thật |

Job ingestion thành công: `961dba3b-965a-4d73-ab79-94c58e6665ea` (ID từ ảnh UI).
Job thất bại: `7dbb31c5-475a-4990-85ac-e38d25af3266` (ID khớp CLI và UI).
Report/preview local ở `data/processed/issue103/` và `data/raw/issue103/`, không
đưa runtime data hoặc khóa vào Git. Đây là smoke chức năng, không phải benchmark.

## Tái lập E2E và giới hạn

- E2E đã đạt trên desktop và production mobile bằng HTTP interception. Chạy lại
  từ frontend khi thay đổi luồng bị ảnh hưởng:

  ```powershell
  $env:VITE_API_BASE_URL = ''
  rtk proxy npm.cmd run test:e2e
  ```

- E2E gồm kiểm tra auth, loading/empty/error, pagination/filters, failed 100%,
  indexing null progress, retry và reset phiên; kiểm tra route preview bị tắt ở
  production. Đây là dữ liệu giả lập, tách khỏi smoke runner ở bảng trên.
- Chưa có smoke CLIP indexing thật, live running/progress hoặc phân trang thật
  với hơn 12 job; null/indexing/pagination/race được kiểm tra bằng tests giả lập.
- Review/CI/merge chưa được xác nhận. Không dùng kết quả local để tự đóng Issue.

## Checklist bàn giao

- [x] Trang chính đọc jobs API thật theo contract W5; preview tách riêng.
- [x] Loading, empty, dữ liệu, lỗi/retry, phân trang và filters có tests.
- [x] Có smoke UI/API với lịch sử runner ingestion thật; ghi rõ giới hạn ở trên.
- [x] Unit/component, coverage, lint, typecheck, build và E2E local đạt.
- [x] Hướng dẫn sử dụng và bằng chứng được cập nhật; không đổi API/schema/index.
- Khi bàn giao, commit/push nhánh #103 và mở PR vào develop theo template chung;
  cập nhật checklist Issue/PR theo bằng chứng, SHA và liên kết PR thực tế.
- [ ] CI trên PR đạt, reviewer khác approve và xử lý trao đổi chặn.
- [ ] Người được giao merge vào develop; sau đó mới nghiệm thu/đóng Issue.

## Tái lập smoke nhỏ

Chạy backend theo [hướng dẫn jobs API](jobs-status-api.md), dùng DB local và khóa
riêng. Chạy frontend với `VITE_API_BASE_URL` trỏ origin backend rồi nhập khóa vào
UI. Dùng wrapper ingestion với `--limit 1 --persist-db`, đặt tên report mới mỗi
lượt, sau đó nhấn **Tải lại** và đối chiếu ID/status với CLI hoặc detail API.
Ca lỗi dùng manifest không tồn tại; kiểm tra lỗi của job không làm hỏng danh sách.
Không tải lại toàn dataset, tạo job giả trong DB hoặc dựng index chỉ để thử UI.

Contract: [jobs-status-w5.md](../contracts/jobs-status-w5.md).
Hướng dẫn frontend: [README](../../frontend/README.md#admin-job-status--issue-103-tiếp-nối-70).
