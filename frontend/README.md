# Frontend — Nguyễn Văn Duy

React + TypeScript + Vite cho UI tìm kiếm W1. Bố cục responsive, ô tìm kiếm hỗ trợ Enter, trạng thái idle/loading/empty/error/retry, xóa truy vấn có trả focus, lọc danh mục cục bộ và thẻ asset với preview/metadata/nguồn.

Giao diện lấy cảm hứng từ Cosmos: nền sáng trung tính hoặc tối, header có tên thư viện bên trái và nút đổi theme bên phải; thanh tìm kiếm căn giữa. Font Be Vietnam Pro được self-hosted, nguồn/license tại [public/fonts](public/fonts/README.md). Không có slogan, hướng dẫn thường trực hoặc badge phát triển.

Màn đầu cao 100svh, có ảnh nền hồ và núi Alpine phong cách ảnh chụp, sinh bằng imagegen và thanh tìm kiếm ở chính giữa; gallery 6 ảnh bắt đầu ở phần trang phía dưới. Gallery dùng hai cột bằng nhau trên máy tính, một cột trên điện thoại; ảnh cùng kích thước trong mỗi hàng, không có độ lệch dọc, tiêu đề 22px. Gallery mở rộng gần sát hai mép màn hình, mỗi mục ưu tiên diện tích ảnh vuông bên trái, tên và mô tả hình ảnh ngắn bên phải căn theo chân ảnh, không dùng khung viền hoặc nhãn đè lên ảnh. Ảnh hiển thị trọn đồ vật. Chưa gửi request và chưa hiện khu vực kết quả hoặc bộ chọn số kết quả. Khi gửi truy vấn hợp lệ, nền/gallery được thay bằng loading/kết quả/lỗi. Xóa truy vấn đưa trang trở lại màn giới thiệu, giữ bộ lọc danh mục hiện tại cùng nút xóa bộ lọc. Gallery là hình trang trí độc lập với dữ liệu retrieval, không thay thế thumbnail thật hoặc fallback của AssetCard. Nguồn ảnh và prompt tại [public/images/discovery](public/images/discovery/README.md).

Nền có parallax nhẹ theo cuộn trang bằng listener passive và requestAnimationFrame, không cập nhật React state theo từng frame. Khung hình trôi/zoom rất chậm và ánh nước chuyển nhẹ bằng CSS trên ảnh tĩnh; dừng khi nền ra khỏi viewport. `prefers-reduced-motion` tắt mọi chuyển động nền. Đây không phải video hồ nước. Không có video, WebGL hoặc dependency mới.

Nút mặt trăng/mặt trời ở header bật/tắt chế độ tối; mặc định theo hệ thống khi chưa có lựa chọn, lưu trong `localStorage` (`connected-theme`) và khôi phục khi tải lại. Đổi giao diện không xóa truy vấn, kết quả hay bộ lọc. Nếu storage bị chặn, vẫn đổi được trong phiên; áp dụng theme trước render để tránh lóe nền sáng. Tìm kiếm giữ ô nhập/nút gửi trong cùng một khối; không thêm dependency UI.

Sau tìm kiếm, thanh nhập gọn được căn trái, tiêu đề và số lượng kết quả đi cùng nhau; bộ chọn số kết quả ở bên phải. Kết quả dùng lưới 3/2/1 cột theo màn hình, preview vuông không đệm ảnh, thẻ không có khung bao ngoài; metadata và nguồn nằm trong “Chi tiết”. Skeleton cùng tỷ lệ với preview. Không lấy ảnh gallery làm thumbnail khi API thiếu ảnh.

## Chạy local

Yêu cầu Node.js >= 22.12.0 và npm. Từ gốc repo:

```bash
cd frontend
npm ci
npm run dev
```

Mở URL Vite in trong terminal, mặc định `http://localhost:5173`. Chế độ development dùng mock động với 6 fixture tự tạo, độ trễ 450ms; kịch bản bình thường/rỗng/lỗi được kiểm tra trong tests. Mock chỉ khớp metadata keywords, không phải semantic search hoặc dữ liệu Objaverse thật.

```bash
npm run dev:api
```

Chế độ API gọi `POST /api/v1/search/text`, `GET /api/v1/assets` và `GET /api/v1/assets/{asset_id}` cùng origin, hoặc origin `VITE_API_BASE_URL` trong `.env.local` (xem `.env.example`). Backend khác origin cần CORS/reverse proxy. Không tự fallback mock khi HTTP lỗi.

`npm run build` luôn dùng HTTP API ở production; `npm run preview` chỉ phục vụ bản build đã tạo. Preview sẽ hiện lỗi nếu chưa có backend, thay vì giả kết quả thành công.

## Kiểm tra

```bash
npm run lint
npm run typecheck
npm test
npm run test:coverage
npm run test:e2e
```

`npm run test:watch` chạy Vitest khi phát triển. `test:e2e` build rồi chạy Playwright, tự khởi động/dừng ba server ở cổng 5193/5194/5195 (mock/API/production preview); cần các cổng này trống. Mặc định dùng Chrome đã cài; nếu dùng Chromium của Playwright:

```bash
npx playwright install chromium
PLAYWRIGHT_BROWSER_CHANNEL=chromium npm run test:e2e
```

Unit/component test kiểm tra validator, mock, HTTP client, loading/error/retry, timeout, request race, metadata null, ảnh lỗi, bộ lọc, danh sách asset, chi tiết asset (kể cả 404) và focus. E2E chạy desktop/mobile, giả lập HTTP để kiểm tra UI API và production; không chứng minh backend thật hoặc retrieval quality. Report/trace/coverage là output local, được ignore.

## Contract và phạm vi

- [Contract backend](../docs/contracts/api-v1.md) và [Draft contract canonical](../docs/contracts/search-text.md), DTO tại `src/features/search/types.ts`. `src/types/search.ts` chỉ re-export để các import cũ dùng cùng một nguồn.
- Query 1–500 Unicode code points sau trim; limit 1–50 (UI chọn 2/6/12/24). Không gửi query trống cho text search; nút “Danh sách asset” hoặc gửi bộ lọc khi chưa nhập query sẽ gọi `GET /api/v1/assets`.
- Nhóm danh mục trên kết quả chỉ lọc trang đã nhận; mục Bộ lọc gửi filters HTTP (`category`, `format`, `license`, `face_count_min`, `face_count_max`) theo contract #9 và có nút “Đặt lại bộ lọc API”. Nhãn đang lọc và số hiển thị/tổng kết quả thể hiện phạm vi này.
- Xóa truy vấn giữ danh mục cục bộ và trả focus về ô nhập. Nút “Xóa bộ lọc” xóa danh mục cục bộ độc lập. Reset ở empty state xóa cả truy vấn lẫn bộ lọc.
- Mở chi tiết asset từ thẻ trong danh sách hoặc kết quả tìm kiếm sẽ gọi `GET /api/v1/assets/{asset_id}`, hiển thị đầy đủ metadata thực tế, xử lý loading/404/lỗi mạng/retry/ảnh hỏng và quay lại giữ nguyên filters, `page` và `limit`.
- Preview thật dùng `thumbnail_url`, lazy loading và fallback khi lỗi; hình ghế ở intro là minh họa giao diện tự tạo. Metadata thiếu để null, không bịa license/tác giả/số mặt. `description`/`category` null hiện “Chưa có thông tin”.
- Chưa có UI tìm ảnh hoặc UI gửi feedback.

## Cấu trúc

- `src/app/`: App/layout và CSS.
- `src/features/search/`: page/card, DTO, validation và mock development.
- `src/features/assets/`: màn hình chi tiết asset (`AssetDetailView`).
- `src/lib/api/`: HTTP client dùng chung (`http.ts`), client search/asset (`search.ts`), timeout và kiểm tra response.
- `src/features/feedback/`, `admin/`, `src/components/`: vị trí module theo phân công; chỉ triển khai khi nhiệm vụ cần.
- Tests nằm cạnh source và tại `tests/`; E2E dùng Page Object trong `tests/e2e/`.

Source HTTP/contract và các test tương ứng được tái sử dụng từ nhánh `feat/6-w1-search-mock`, kết hợp với bố cục và thiết kế mới. Xem [kế hoạch kiểm thử UI](tests/UI_ACCEPTANCE.md).

Thanh tìm kiếm giới hạn 640px, gồm ô nhập, nút tìm và biểu tượng xóa khi có query. Không hiển thị gợi ý mẫu, hướng dẫn độ dài hoặc bộ chọn trạng thái phát triển; lỗi validation chỉ xuất hiện khi nhập không hợp lệ. Bộ chọn số kết quả xuất hiện cạnh tiêu đề khi duyệt danh sách hoặc kết quả tìm kiếm.
# Tích hợp contract Issue #9 & W2/M1

Issue #49 bổ sung kiểm thử giao diện với PostgreSQL thật bằng
`python -m scripts.verify_asset_api --ui` từ gốc repo. Xem
[hướng dẫn kiểm chứng](../docs/guides/asset-api-verification.md).
Lệnh chuẩn bị DB/server rồi gọi `npm run test:database`; không dùng MockStore.

Client hỗ trợ `POST /api/v1/search/text`, `GET /api/v1/assets` và `GET /api/v1/assets/{asset_id}`, validation HTTP 400 (422 chỉ tương thích bản cũ), 404 `ASSET_NOT_FOUND`, `page`/`limit` và `pagination`. Bộ lọc trong mục **Bộ lọc** gửi `category`, `format`, `license` và khoảng số mặt lên API; các trường trống được bỏ. Thay bộ lọc, đặt lại bộ lọc hoặc đổi `limit` khi duyệt danh sách đều đưa về trang 1. Rank trong kết quả tìm kiếm bắt đầu từ 1 mỗi trang. Nút chuyển trang giữ request đã gửi; quay lại từ màn chi tiết giữ nguyên `filters`, `page` và `limit`. Nhóm danh mục trên kết quả chỉ lọc cục bộ trong trang; muốn lọc toàn bộ tập dữ liệu dùng mục Bộ lọc.
Chi tiết và giới hạn: [đối chiếu contract](../docs/contracts/frontend-api-v1.md).

## Kiểm thử với backend FastAPI trong repo

Backend mock của PR #24 đã merge vào `develop`; bộ tích hợp dùng `../backend` của
chính commit đang kiểm tra, không checkout commit backend riêng. Cài
`backend/requirements-dev.txt` vào virtualenv Python 3.13. Từ frontend/:

```bash
BACKEND_PYTHON=/duong-dan/venv/bin/python npm run test:integration
```

`BACKEND_PYTHON` mặc định `python3`; `BACKEND_CONTRACT_DIR` chỉ dùng khi cần ghi đè
thư mục backend lúc gỡ lỗi local. Bộ test tự khởi động/dừng FastAPI
và Vite trên 5196/5197, không dùng dịch vụ chia sẻ. Dùng
`PLAYWRIGHT_BROWSER_CHANNEL=chromium` nếu cài Chromium qua Playwright.
Tests chạy frontend–FastAPI HTTP thật nhưng backend trả fixture; không đo semantic
retrieval. Upload và feedback được kiểm tra qua HTTP, chưa có UI cho hai tính năng.

## Kiểm chứng W3 — Issue #54

Rà soát UI W3: loading/empty/error/retry giữ hành vi hiện có; bổ sung kiểm chứng
HTTP qua UI cho timeout/mạng và retry giữ nguyên request khi bản nhập đã thay đổi.
Detail hiển thị “Chưa có thông tin” cho nguồn/tác giả/license rỗng hoặc toàn khoảng
trắng; chỉ tạo link nguồn qua validator HTTP(S) hiện có. Không đổi metadata gốc
hoặc tự tạo URL tác giả/license. Xem [acceptance UI W3](tests/UI_ACCEPTANCE.md).
Sau sửa UI: `npm test` đạt 276/276; lint, typecheck, build đạt và E2E giữ nguyên
đạt 30/30 (29/10/2026). Đây là kiểm chứng mock/HTTP giả lập, chưa phải smoke thật.

Luồng text hiện có gửi query đã trim, filters, page và limit qua HTTP client;
giữ thứ tự kết quả, IDs và versions từ response. Detail gọi API theo asset ID;
quay lại giữ kết quả và trang đã nhận. Không fallback mock khi API lỗi.
`tests/components/SearchPage.http.test.tsx` kiểm tra xuyên UI → HTTP client →
validator với **fetch giả lập**, gồm phân trang, thứ tự, IDs/versions, detail/quay
lại, retry/empty và response cũ thành công hoặc lỗi đến sau response mới.

Tại lần rà soát W3 này, [khối 3](../docs/contracts/w3-text-search-review.md)
vẫn ghi các quyết định đang chờ xác nhận; chưa có contract retrieval thật đã chốt.
Sau cập nhật `develop` tại `65ce583` (29/10/2026), list/detail đọc PostgreSQL
theo #48; search vẫn gọi `MockStore` và không đăng ký khi tắt mock. ID từ search
fixture có thể không tồn tại trong detail DB: UI hiện lỗi 404, không dùng metadata
search thay cho detail thành công; quay lại vẫn giữ kết quả. Test HTTP mô phỏng
kiểm tra riêng trường hợp này. Module CLIP batch/Qdrant mới của #39 chưa nối vào
HTTP search; chưa có encode text/truy vấn vector trong các module đó.
List/detail đọc PostgreSQL không làm search trở thành retrieval thật.
Chạy `dev:api` chỉ chọn HTTP, không xác nhận backend dùng encoder/index thật.
Chưa nghiệm thu acceptance criteria tìm kiếm dữ liệu/index thật của Issue #54.

Kiểm tra lại ngày 29/10/2026 sau fast-forward: `npm test` đạt 267 tests/13 files;
`npm run lint`, `npm run typecheck` và build đạt. `npm run test:e2e` đạt 30 tests
trên desktop/mobile (bao gồm build production). E2E dùng mock development hoặc
HTTP interception, không dùng retrieval/index thật.

Khi owner bàn giao contract và môi trường retrieval thật, chạy smoke riêng:

1. Chạy `npm run dev:api` với origin API được bàn giao qua `VITE_API_BASE_URL`;
   kiểm tra CORS/reverse proxy theo hướng dẫn ở trên.
2. Nhập query trên web, kiểm tra request `POST /api/v1/search/text` trong Network,
   đối chiếu thứ tự asset IDs, pagination, query/event IDs và versions với response.
3. Mở một asset, đối chiếu ID/metadata/nguồn với detail response rồi quay lại;
   kiểm tra trang/kết quả vẫn được giữ.
4. Ghi query, thời điểm, commit frontend/backend, IDs, versions và manifest
   checkpoint/revision/preprocessing/dataset/index tương ứng. Đối chiếu bằng chứng
   phía backend rằng request đi qua encoder và index thật; HTTP 200, cờ `mock=false`
   hoặc tên version riêng lẻ chưa đủ chứng minh semantic retrieval.

Không dùng bộ `test:integration` hiện tại làm smoke thật vì nó chủ động bật
backend fixture. Không tải model/dataset hoặc rebuild index dùng chung để chạy
smoke frontend.
