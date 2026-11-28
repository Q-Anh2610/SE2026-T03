# W6 và W7 — Giao diện tìm kiếm của Nguyễn Văn Duy

Ngày kiểm tra 24/11/2026. Nhánh `fix/w6-search-navigation`, nền `develop`
tại `7becbde`.

| Tình huống | Hành vi đã kiểm tra |
| --- | --- |
| Bấm liên kết đến vùng tìm kiếm khi đã có kết quả | Giữ kết quả và bản nháp chưa gửi. Không gọi lại tìm kiếm. |
| Back/Forward giữa các địa chỉ chỉ khác anchor | Giữ kết quả và bản nháp. Thay đổi tham số tìm kiếm vẫn khôi phục trạng thái theo URL. |
| Bấm liên kết về tìm kiếm từ trang chi tiết | Đóng trang chi tiết và giữ danh sách kết quả. |
| Xóa tìm kiếm và bộ lọc từ trạng thái rỗng | Xóa giá trị bộ lọc, đóng vùng lọc và đưa focus về ô tìm kiếm. |

## Kiểm tra local

Từ `frontend/`:

- `npm run test`: 604 test đạt trên 26 file.
- `npm run typecheck`: đạt.
- `npm run test:e2e`: build đạt và 48 test Playwright đạt.
- `git diff --check`: đạt.

Component tests kiểm tra trạng thái và số lần gọi client. Playwright kiểm tra
liên kết và lịch sử trình duyệt trên desktop và mobile bằng dữ liệu fixture.
Hồ sơ này ghi kết quả kiểm tra kỹ thuật tại máy. Phản hồi user testing và
nghiệm thu của nhóm cần có bằng chứng riêng.

## Kiểm chứng lại W6 và bổ sung W7

Ngày 27/11/2026. Đối chiếu frontend của nền `7becbde` với
`origin/develop` tại `3a0e601`, hai phiên bản trùng nhau trong `frontend/`.

| Phạm vi | Kết quả |
| --- | --- |
| W6 điều hướng | Component test kiểm tra bản nháp, dữ liệu đã nhận và số lần gọi client. E2E kiểm tra anchor và Back/Forward. |
| W7 bàn phím | Nhấn Tab rồi Enter trên liên kết bỏ qua điều hướng đưa focus vào nội dung chính và giữ route tìm ảnh. Tab tiếp theo đưa focus đến ô chọn tệp với viền focus hiển thị. |
| W7 màn hình hẹp | Kết quả text và biểu mẫu bộ lọc ảnh ở 320 CSS px vừa chiều rộng viewport. |
| W7 tài liệu UI | [Hướng dẫn frontend](../../frontend/README.md#điều-hướng-bằng-bàn-phím-và-màn-hình-hẹp). |

Từ `frontend/`, `npm run lint` đạt. `npm run test:coverage` chạy 605/605 test
trên 26 file và đạt ngưỡng 95% cho từng file. `npm run test:e2e` build
thành công và chạy 52/52 test trên Chrome với fixture và HTTP giả lập.

## Kiểm tra bổ sung trên Chrome và Orca

- **W6:** Chạy luồng fixture trên Chrome 157 ở viewport 390 và 1280 CSS px.
  Tìm `glb` trả 6 kết quả. Chọn danh mục **Nội thất** còn 3. Sau khi mở chi
  tiết và quay lại, danh mục và thứ tự 3 kết quả được giữ. Sau khi nhập bản
  nháp chưa gửi, liên kết **Khám phá asset** và Back/Forward giữ kết quả,
  danh mục và bản nháp. Đây là kiểm tra kỹ thuật tự động. Chưa có phản hồi
  từ phiên thử với người dùng.
- **W7:** Chạy Chrome 157 có cửa sổ trên Fedora Wayland với Orca 51.1.
  Tab đầu tiên đọc “Đến nội dung chính”. Enter chuyển focus vào `main`
  trên trang tìm ảnh. Tab tiếp theo đọc nhãn ô chọn JPEG/PNG và giới hạn
  ảnh. Khi gửi PNG thử nghiệm, nhật ký Speech Dispatcher xác nhận Orca
  đọc “Đang tìm ảnh…” rồi đọc lỗi dịch vụ với HTTP 503 giả lập.
  Vùng thông báo trạng thái được giữ trong DOM và đặt ngoài vùng
  `aria-busy` để Orca đọc được cập nhật trong lúc tải.

## Chạy lại trước khi tạo PR

Ngày 28/11/2026, từ `frontend/`:

- `npm run lint`: đạt.
- `npm run typecheck`: đạt.
- `npm run test:coverage`: 605/605 tests trên 26 file; coverage statements
  99.24%, branches 98.49%, functions 99.22%, lines 99.88%.
- `npm run test:e2e`: build đạt và 52/52 Playwright tests đạt.
- Playwright dùng fixture/HTTP giả lập; đây không phải kiểm chứng tích hợp
  API/DB/index thật hoặc phiên thử với người dùng.
