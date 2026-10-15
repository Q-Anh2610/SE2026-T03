# Kiểm thử chốt UI tìm kiếm — Issue #6

Phạm vi: trang đầu, gallery và giao diện sau tìm kiếm của [Issue #6](https://github.com/Q-Anh2610/SE2026-T03/issues/6). API/encoder/index thật chưa được tích hợp; các phản hồi mạng trong E2E là fixture kiểm thử.

## Chạy bản kiểm tra

Trong `frontend/`, dùng Node.js >=22.12.0:

```bash
npm ci
npm run lint
npm run typecheck
npm run test:coverage
npm run test:e2e
```

Playwright dùng Chrome đã cài và các cổng 5193–5195; có thể chọn Chromium bằng `PLAYWRIGHT_BROWSER_CHANNEL=chromium`. Không chạy trùng cổng với phiên khác.

Xem trực tiếp bằng `npm run dev`. Mock chỉ tìm từ khóa metadata; thử `glb` để có sáu kết quả, `ghe go` để có một kết quả, một truy vấn không khớp để kiểm tra empty state. Kết quả mock không có thumbnail thật và phải hiện “Chưa có ảnh xem trước”. Ảnh gallery không được dùng thay cho dữ liệu thiếu.

## Tiêu chí giữ ổn định

| Vùng | Tiêu chí | Kiểm tra tự động |
|---|---|---|
| Trang đầu | Thanh tìm kiếm ở giữa màn hình; gallery bắt đầu bên dưới; chưa gọi search | `mock.spec.ts` |
| Gallery | Sáu ảnh vuông, cùng chiều rộng, các cặp ảnh thẳng hàng trên desktop; cùng mép trái trên mobile | `mock.spec.ts`, cả sáng/tối |
| Kết quả | Lưới 3/2/1 cột theo breakpoint; preview vuông cùng cỡ, cùng cao độ trong hàng; không tràn ngang | `mock.spec.ts` |
| Thông tin | Tiêu đề và số hiển thị/tổng đi cùng nhau; bộ chọn limit chừa khoảng cho mũi tên; chi tiết có thể mở bằng bàn phím | Component và E2E |
| Loading | Nút gửi bị vô hiệu hóa, vùng kết quả `aria-busy`, skeleton vuông; không giữ kết quả cũ như thành công mới | Component và `api.spec.ts` |
| Thumbnail | Ảnh API hiển thị trọn; thiếu/hỏng ảnh hiện fallback rõ ràng | `AssetCard.test.tsx`, `api.spec.ts` |
| Lọc/reset | Lọc cục bộ, cập nhật số lượng; xóa truy vấn giữ bộ lọc và trả focus; reset empty xóa cả hai | Component và E2E |
| Lỗi | Query trống/quá dài bị chặn; API 503/sai contract không giả thành công; retry hoạt động | Unit/component và E2E |
| Timeout/race | Timeout, abort và phản hồi trễ không ghi đè trạng thái hiện tại | Unit/component |
| Giao diện | Đổi theme giữ truy vấn/kết quả; giảm chuyển động tắt hiệu ứng nền | Component và E2E |

Các test kiểm tra hình học và snapshot accessibility nội tuyến, không khóa vào cấu trúc CSS cụ thể để tạo kết quả giả. E2E xuất ảnh chụp vào `test-results/` để review local: gallery sáng/tối, kết quả sáng/tối, loading và kết quả có ảnh API mô phỏng. Header cố định và skip-link được ẩn **chỉ trong ảnh chụp gallery** để không che nội dung cần đối chiếu. Không commit ảnh/report/trace sinh ra từ test. Đây chưa phải bộ so sánh pixel giữa các lần chạy.

## Kết quả thực tế ngày 15/10/2026

Môi trường: Linux, Node.js 22.22.1, React 19.2.x, Vite 7.3.7, Vitest 3.2.7, Playwright 1.64.x, Chrome 155.0.8059.39 headless local. Desktop 1280×900, mobile 390×844.

- `npm ci`: cài thành công từ lockfile.
- Lint, typecheck và build: đạt.
- Unit/component: **193/193**, 12 file test.
- Coverage: lines/statements/functions **100%**, branches **99,23%** tổng; từng file runtime đạt ngưỡng 95%. Type-only không có mã runtime để đo. CSS được kiểm tra qua browser, không tính vào coverage JS.
- E2E: **28/28**, gồm mock desktop/mobile, API desktop và production mobile dùng HTTP fixture.
- Smoke browser bổ sung ở 320/768/1920px: gallery thẳng hàng, không tràn ngang, kết quả đúng 1/2/3 cột.
- `npm audit --omit=dev`: **0** cảnh báo. Audit toàn bộ ghi nhận **4** cảnh báo trong cây dev dependencies Vitest/tinypool/mocker (2 moderate, 2 critical); chưa nâng major tooling trong thay đổi UI. Chưa coi đây là xác nhận môi trường test đã xử lý hết cảnh báo dependencies.

Đạt các kiểm tra UI nêu trên; không xác nhận backend integration, chất lượng semantic search, CI remote, review của thành viên hoặc quyền merge. PR nhiệm vụ nếu mở phải vào `develop` và được review theo quy trình nhóm.
