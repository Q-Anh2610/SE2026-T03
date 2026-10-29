# Kiểm thử chốt UI tìm kiếm — Issue #6

## Rà soát trạng thái và detail W3 — Issue #54, 29/10/2026

Nhánh `feat/54-w3-text-search`, nền `develop` tại `65ce583`; thay đổi local chưa
commit. Kết quả khối 4 và giới hạn retrieval nằm trong [README](../README.md#kiểm-chứng-w3--issue-54).
Giữ bố cục hiện tại, không đổi API/schema/dependencies. Các kết quả lịch sử W1
bên dưới không phải bằng chứng nghiệm thu W3.

| Acceptance W3 | Hành vi và bằng chứng local |
|---|---|
| Loading/empty | UI có loading, `aria-busy`, nút gửi disabled; không hiện empty ở idle/loading. Test HTTP qua UI giữ response pending rồi trả empty thành công. |
| Error/retry | Lỗi HTTP, mạng, timeout hiện lỗi, không có kết quả giả. Test UI qua HTTP client kiểm tra retry giữ query đã trim, filters, page, limit dù bản nhập đã đổi. |
| Request race | Tests HTTP mô phỏng cả thành công và lỗi của request cũ đến sau request mới; trạng thái mới không bị ghi đè. |
| Detail | Tests có loading, 404, lỗi/retry, quay lại và response trễ; không lấy metadata search thay cho detail lỗi. |
| Nguồn thiếu | `source`, `author`, `license` rỗng/toàn khoảng trắng được hiển thị “Chưa có thông tin”; giữ placeholders null và nhãn fixture hiện có. Không suy URL tác giả/license từ tên. |
| Link nguồn | Dùng lại `isHttpUrl` trước khi render link HTTP(S), không có credentials; test từ chối javascript/file/relative/credentials. HTTP validator vẫn từ chối response sai contract, không nới schema. |
| Backend/index thật | Chưa nghiệm thu: API search vẫn gọi MockStore, chưa có contract retrieval thật đã được owner xác nhận hoặc môi trường smoke được bàn giao. |

File kiểm chứng: `src/features/search/SearchPage.test.tsx`,
`tests/components/SearchPage.http.test.tsx`, `src/lib/api/search.test.ts`,
`src/features/assets/AssetDetailView.test.tsx`. Tests HTTP mới dùng fetch giả lập;
không phải smoke retrieval thật. E2E giữ nguyên kịch bản hiện có; Minh Khuê có thể
review ảnh hưởng giới hạn ở placeholders nguồn và điều kiện tạo link detail.
Không tích checklist CI, owner review hoặc tích hợp thật từ kết quả local.

Kết quả sau sửa UI: `npm test` **276/276**, 13 files; `npm run lint` và
`npm run typecheck` đạt. `npm run test:e2e` chạy build production thành công và
**30/30 E2E** đạt, Chrome headless desktop/mobile. Lint ban đầu phát hiện cách
xuống dòng trong test mới, đã sửa và chạy lại đạt. Không sửa tests E2E, không chạy
smoke backend/index thật hoặc xác nhận CI remote. Môi trường: Linux, Node.js
22.22.1, npm 9.2.0, Vitest 4.1.11; dùng dependencies/lockfile hiện có.

Rà soát lại tests HTTP W3: sửa mock timeout từ trả chung một signal sang chỉ
giả lập signal của request đầu (`mockReturnValueOnce`). Trước sửa, assertion mới
phát hiện retry dùng signal đã abort nhưng fetch giả vẫn trả thành công (1/8 test
HTTP thất bại). Giữ assertion retry có signal chưa abort; không nới contract hoặc
đổi HTTP client để làm test đạt. Không phát hiện lỗi UI mới trong phạm vi rà soát.

Kiểm chứng sau sửa mock: `npm run lint`, `npm run typecheck` đạt;
`npm run test:coverage` chạy đủ **276/276 tests, 13 files** và đạt ngưỡng từng file
95% đã cấu hình. Tổng coverage: lines/functions 100%, statements 99,78%, branches
98,03%. `npm run test:e2e` build production đạt và **30/30 E2E** đạt (36,2 giây).
E2E dùng mock/HTTP interception; chưa kiểm chứng backend/index thật. Diff check
đạt; không đổi cấu hình test, không sửa E2E hoặc cập nhật GitHub.

### Bàn giao phần còn thiếu cho khối 2

Đầu vào frontend cần để nghiệm thu #54:

- Xác nhận contract retrieval thật với owner API/search: pagination/total, rank,
  vòng đời query/event IDs, versions và lỗi dependency chưa sẵn sàng.
- Nối `POST /api/v1/search/text` vào encoder text và retrieval/index thật, lưu
  search event theo quyết định đã chốt; search IDs phải mở được qua detail DB.
- Bàn giao origin API, cấu hình chạy, commit backend và manifest model/revision,
  preprocessing, dataset snapshot/index/config versions; xác nhận index sẵn sàng.
- Chuẩn bị smoke cùng Minh Khuê: query → response từ retrieval thật → detail →
  quay lại, ghi IDs/versions và bằng chứng phía backend về encoder/index đã dùng.

Đây là danh sách phụ thuộc để phối hợp, không tự mở rộng scope frontend hoặc
xác nhận owner đã chốt. Không dùng fixtures, HTTP 200 hoặc riêng cờ mock=false
để nghiệm thu. Không gửi tin nhắn/cập nhật GitHub trong lượt rà soát này.

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

## Ý nghĩa cảnh báo dependencies của bộ test

Audit đếm bốn package bị ảnh hưởng (`tinypool`, `@vitest/mocker`, `vitest`, `@vitest/coverage-v8`), không phải bốn lỗi độc lập. Hai package Vitest cấp trên bị đánh dấu theo cây phụ thuộc.

- Tinypool có hai advisory về prototype pollution dẫn đến thực thi mã trong worker. Cần một điểm gây prototype pollution từ trước và các điều kiện gọi worker liên quan; lỗi có thể ảnh hưởng máy phát triển/CI với quyền của tiến trình test. Xem [worker options](https://github.com/advisories/GHSA-5gmw-xhrv-c9v3) và [run options](https://github.com/advisories/GHSA-85c8-ppgw-ccpr).
- Mocker có lỗi đọc file ngoài phạm vi cho phép qua redirect mock. Khai thác từ xa không cần xác thực được mô tả cho server tích hợp plugin mock công khai và cho phép truy cập; không đồng nghĩa mọi lần chạy Vitest đều phơi nhiễm. Repo dùng jsdom và không đăng ký plugin mock đó trong Vite app. Xem [advisory và điều kiện khai thác](https://github.com/advisories/GHSA-82fw-gwwq-j7x9).

Các package này là dev dependencies; audit production sạch không đồng nghĩa môi trường phát triển/CI không cần vá. Vitest 4.1.11 là bản đã vá lỗi mocker; Vitest 4 bỏ phụ thuộc tinypool. Không dùng `npm audit fix --force` hoặc tắt ngưỡng coverage để xử lý cảnh báo.

## Kết quả sau bản vá tooling — 15/10/2026

- Pin đồng bộ `vitest` và `@vitest/coverage-v8` ở **4.1.11**, cập nhật lockfile tương ứng; không đổi phiên bản React, React DOM, Vite hoặc các direct dependencies còn lại. Không cần cài npm mới toàn cục.
- Npm 9/10 gặp lỗi nội bộ `edgesOut` khi cập nhật; lockfile được cập nhật trong thư mục tạm bằng npm 11.6.2 rồi xác nhận lại bằng `npm ci` thông thường của môi trường.
- `tinypool` không còn trong cây dependencies; `@vitest/mocker` đã ở 4.1.11.
- `npm ci`, lint, typecheck, build: đạt; `npm audit --json`: **0 lỗ hổng**, gồm cả dev dependencies.
- **194/194 unit/component**, **28/28 E2E** đạt. Bổ sung test kiểm tra không đăng ký listener khi host nền không có ref; giữ nguyên mã sản phẩm và các assertion hiện có.
- Coverage v4: lines/statements/functions **100%**, branches **99,07%**, từng file runtime đạt ngưỡng 95%. V8 remapping thay đổi giữa Vitest 3 và 4 nên không so sánh trực tiếp phần trăm branches giữa hai bản; không hạ threshold, không thêm loại trừ hay bỏ test.

Kết quả này thay thế tình trạng bốn cảnh báo dev dependencies trong lần kiểm tra UI trước đó. Không có thay đổi contract/API/schema/index hoặc hình thức UI.

## Rà soát PR #18 — 16/10/2026

- Bỏ hai component header/footer cũ không được `App` import, CSS và sáu test riêng của chúng; giữ nguyên header/footer đang hiển thị trong `App`.
- Bổ sung một test tích hợp trên `App` để kiểm tra header/footer thực tế, tên thư viện và link điều hướng. Không bỏ assertion hoặc thay coverage threshold để che lỗi.
- Bản hiện tại: **189/189 unit/component**, 10 file test; **28/28 E2E**. Số test giảm ròng năm do loại sáu test của code không dùng và thêm một test ứng dụng thật.
- Lint, typecheck, build đạt. Coverage lines/statements/functions **100%**, branches **99,06%**, từng file runtime đạt 95%. CI `branch-policy` được theo dõi riêng trên PR; chưa có approval của thành viên khác hoặc merge.
