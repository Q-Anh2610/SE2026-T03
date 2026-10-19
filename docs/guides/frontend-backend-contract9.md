# Kiểm chứng frontend–backend cho Issue #9

Kiểm tra local ngày 19/10/2026 trên Linux x86_64, Node 22.22.1, npm 9.2.0,
Python 3.13.15. Dependencies frontend dùng package-lock.json; backend dùng
requirements-dev.txt tại commit `575cee46150c76c34d1b080d099654ae07fb09fd` của PR #24.

| Lệnh | Kết quả local |
|---|---|
| `npm run lint` | Đạt |
| `npm run typecheck` | Đạt |
| `npm run test:coverage` | 222 tests đạt; từng file runtime >=95% lines/branches/functions/statements |
| `npm run test:e2e` | Build đạt và 28/28 E2E đạt |
| `BACKEND_CONTRACT_DIR=… BACKEND_PYTHON=… npm run test:integration` | 6/6 đạt, desktop/mobile gọi FastAPI thật |
| `python -m pytest` tại backend checkout đối chiếu | 52/52 đạt |

Coverage tổng: lines/statements/functions 100%, branches 98,20%; SearchPage branches
97,18%, contract branches 97,29%, mock và HTTP client 100%. Không hạ thresholds,
không skip test. Bootstrap/configs/type-only không tạo thêm hành vi API.

Frontend phân biệt validation 400/422 với lỗi dịch vụ 5xx và route 404, không hiển thị
body lỗi riêng tư. Validator bắt buộc pagination nhất quán với request, tổng và số
phần tử; rank bắt đầu lại từ 1. Bộ lọc API được gửi trước phân trang; nút trang giữ
request đã gửi và tìm kiếm mới về trang 1. Filter danh mục cục bộ ghi rõ phạm vi trang.

Tests HTTP thực xác nhận 400/retry không fallback, page/limit/rank, filter AND và
metadata null, trang vượt phạm vi, list/detail 404, image multipart hợp lệ/ảnh hỏng/
filters JSON hỏng, feedback true/false và từ chối số/chuỗi/asset ngoài event.
Ảnh PNG 2x2 tự tạo. Backend mock chỉ lưu feedback RAM; chưa có UI ảnh/feedback,
DB/index thật hoặc phép đo retrieval. Những kiểm tra này không xác nhận API production.

Workflow mới kiểm tra frontend và backend contract trên GitHub; kết quả CI phải xem
ở PR/run tương ứng, không suy ra từ bảng local này. Approval của thành viên khác và merge vẫn là các bước chờ review.

Đối chiếu/chốt phía frontend cho contract mock v1 đã hoàn tất, gồm feedback Boolean,
RAM và event/asset của đúng trang. Chạy lại riêng feedback và mất trạng thái giữa
process: 4/4 backend tests đạt; nhóm HTTP list/detail/upload/feedback: 2/2 integration
desktop/mobile đạt. Xem quy ước chốt trong `docs/contracts/frontend-api-v1.md`.
