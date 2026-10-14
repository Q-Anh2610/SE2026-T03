# Frontend — Nguyễn Văn Duy

React + TypeScript + Vite. Prototype tìm kiếm văn bản W1 thuộc [Issue #6](https://github.com/Q-Anh2610/SE2026-T03/issues/6), theo [contract nháp](../docs/contracts/search-text.md). Chưa có backend/index/encoder thật; cần Vũ Nguyễn Quỳnh Anh review contract trước khi tích hợp API.

## Chạy local

Node.js 22.13+ và npm; khuyến nghị Node 22 LTS. Từ gốc repository:

```bash
cd frontend
npm ci
npm run dev
```

Mở URL Vite in trong terminal (mặc định `http://localhost:5173`). Mock chỉ bật trong development, có banner dữ liệu minh họa. Không cần tài khoản, API key, backend, dataset hoặc model.

- Thử `ghế gỗ`, `chair`, `đèn bàn`, `thùng gỗ`; mock khớp từ khóa metadata, không đo chất lượng semantic search.
- Tìm chuỗi không có trong fixtures để xem trạng thái rỗng; mở **Thử trạng thái giao diện** để chọn rỗng/lỗi. Nút **Thử lại** sau lỗi mô phỏng chạy mock bình thường với request trước đó.
- Truy vấn trống hoặc quá 500 Unicode code points bị chặn; limit mặc định 12, tối đa contract 50. UI chọn 6/12/24.
- Fixtures là 6 bản ghi tự tạo; `source=fixture`, license/author/số mặt/ảnh/source URL chưa có thì null. Không có asset thật để tải. Tile hình khối CSS là placeholder, không phải ảnh preview của asset.
- Có idle/loading/success/empty/error, retry, labels và focus bàn phím, live status, layout mobile. Không hiển thị score như độ chính xác.

## Chế độ API và build

```bash
npm run dev:api
npm run build
npm run preview
```

`dev:api` bỏ mock và POST đến `/api/v1/search/text` cùng origin. `.env.example` chỉ là mẫu: sao chép thành `.env.local` nếu muốn cấu hình `VITE_SEARCH_MODE=api` và HTTP(S) origin backend bằng `VITE_API_BASE_URL`; không đặt secret trong biến Vite vì chúng xuất hiện trong bundle. Chưa có proxy backend; CORS hoặc reverse proxy cần được chốt khi tích hợp.

Production build luôn gọi HTTP API, không bật mock dù đặt `VITE_SEARCH_MODE=mock`. Khi backend chưa tồn tại, kết quả đúng là trạng thái lỗi; không tự đổi sang dữ liệu giả. API client timeout 15 giây, hỗ trợ abort và kiểm tra response theo contract nháp.

## Kiểm tra

```bash
npm run lint
npm run typecheck
npm run build
```

Repo chưa có test runner component/E2E; nhiệm vụ này không thêm framework kiểm thử riêng. Kiểm tra thủ công thêm: truy vấn trống, có kết quả, rỗng, lỗi và retry; chuyển query nhanh bằng gợi ý; bàn phím; mobile; production không fallback mock khi API lỗi. Không coi mock smoke là benchmark hoặc CI đã xanh.

Xem [báo cáo kiểm tra W1](../docs/guides/frontend-w1-verification.md) để biết môi trường, smoke đã chạy và giới hạn.

## Vùng module

- `src/app/`: router và layout.
- `src/features/search/`: query văn bản/ảnh, filters và kết quả.
- `src/features/assets/`: chi tiết asset.
- `src/features/feedback/`: phản hồi relevance.
- `src/features/admin/`: UI quản trị do Đoàn Thị Minh Khuê phối hợp Nguyễn Văn Duy.
- `src/components/`: thành phần giao diện dùng chung.
- `src/lib/api/`: HTTP client; phối hợp contract với Vũ Nguyễn Quỳnh Anh.
- `src/types/`: types dùng chung; kiểu riêng feature đặt trong feature đó.
- `tests/e2e/`: luồng tích hợp do Đoàn Thị Minh Khuê chủ trì.

`src/features/search/`: UI, types, validator và mock. `src/lib/api/search.ts`: boundary HTTP API; mock được import riêng trong development. `src/app/`: entry/layout/styles. Không thêm router/global store/UI kit khi hiện chỉ có một trang.

UI gọi HTTP API, không kết nối trực tiếp PostgreSQL/Qdrant. Chỉ thêm module và scripts chạy khi nhiệm vụ cần.
