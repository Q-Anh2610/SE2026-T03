# Kiểm tra prototype frontend W1 — Issue #6

Ngày chạy: 14/10/2026. Nhánh: `feat/6-w1-search-mock`, base `8dbdfbc` từ `origin/develop`, chưa merge. Scaffold đã được push ở `82e5b11`; bộ regression test được bổ sung trên cùng nhánh. Chưa có CI hoặc backend thật. Báo cáo chỉ áp dụng prototype của Nguyễn Văn Duy, không đánh dấu toàn milestone M0 hoàn thành.

## Môi trường và cấu hình

- Node.js `v22.22.1`, npm `9.2.0`; React/React DOM `19.3.0`, TypeScript `5.9.3`, Vite `8.3.4`.
- Dependencies tái lập bằng `frontend/package-lock.json`; không cần weights, dataset hoặc dịch vụ trả phí.
- Vitest/coverage-v8 `5.0.4`, jsdom `29.1.1`, React Testing Library `16.3.3`; cấu hình trong `frontend/vitest.config.ts`.
- Mock `mock-text-v1`, index `mock-w1`, model `mock-no-encoder`; 6 bản ghi metadata tự tạo, độ trễ giả 450 ms. Khớp từ khóa, không có encoder hoặc điểm chất lượng retrieval.
- Không dùng random seed; thứ tự fixture cố định, query/event IDs dùng UUID ngẫu nhiên để phân biệt phiên.
- Chrome headless có sẵn trên máy; desktop 1440×1000, mobile 390×844.

## Kết quả thật

| Kiểm tra | Kết quả |
|---|---|
| `npm run lint` | Đạt, 0 warnings. |
| `npm run typecheck` | Đạt. |
| `npm run build` | Đạt. |
| `npm audit --json` | Đạt, 0 lỗ hổng tại thời điểm chạy. |
| `npm ci` | Đạt, cài sạch từ lockfile. |
| `npm run test:coverage` | Đạt: 5 file test, 137 tests. 100% statements/lines/functions, 98,79% branches; từng file đo đều đạt ít nhất 95%. |
| `git diff --check` | Đạt. |
| Smoke Node cho contract/mock | Đạt: trim, query trống/quá giới hạn, Unicode code points, limit/filter không hợp lệ, có/rỗng/lỗi, abort trước/trong request, rank/ID/limit, score/metadata/URL sai contract. |
| Smoke Chrome development | Đạt: idle, validation và focus, loading, kết quả, Enter từ nút submit, rỗng tự nhiên/mô phỏng, lỗi/retry, request mới thay request cũ, desktop/mobile không tràn ngang, không có page error. |
| Smoke Chrome production | Đạt: không có banner/controls mock; POST đúng request; 503, response sai shape và lỗi mạng thành lỗi UI; response hợp lệ rỗng thành empty; không fallback mock. |
| Kiểm tra bundle production | Không chứa IDs fixture `mock-chair-01`, `mock-table-01` hoặc thông báo lỗi mock. |

Unit/component regression tests đã được lưu trong repo bằng Vitest/Testing Library. Smoke Node/Chrome trước đó được chạy bằng scripts tạm ngoài repository, dùng assertions và Playwright Core với Chrome có sẵn; không thêm browser binaries vào repo. Các phản hồi API trong smoke production và unit tests được chặn/mô phỏng để kiểm tra client; đây không phải integration test backend, E2E với dữ liệu thật hoặc benchmark.

### Coverage từng file

| File source | Lines | Branches | Functions | Statements |
|---|---|---|---|---|
| `src/app/App.tsx` | 100% | 100% | 100% | 100% |
| `src/features/search/AssetCard.tsx` | 100% | 100% | 100% | 100% |
| `src/features/search/SearchPage.tsx` | 100% | 96% | 100% | 100% |
| `src/features/search/contract.ts` | 100% | 100% | 100% | 100% |
| `src/features/search/mock.ts` | 100% | 100% | 100% | 100% |
| `src/lib/api/search.ts` | 100% | 100% | 100% | 100% |

Đường dẫn tính từ `frontend/`. Không đo bootstrap `main.tsx`, types, CSS, config và mã kiểm thử. Hai nhánh chưa chạy trong `SearchPage` là fallback khi validator ném giá trị không phải `Error` và retry khi chưa có request; không đổi mã sản phẩm chỉ để đạt 100% coverage. Báo cáo JSON sinh tại `frontend/coverage/coverage-summary.json`, được ignore.

## Tái kiểm tra thủ công

1. Theo [README frontend](../../frontend/README.md), `npm ci`, rồi chạy lint/typecheck/build, `npm test` và `npm run test:coverage`.
2. `npm run dev`: thử query trống, `ghế gỗ`, `gỗ`, `chair`, chuỗi không tồn tại; xem loading, metadata null và phiên tìm kiếm.
3. Mở **Thử trạng thái giao diện**, chọn rỗng/lỗi; sau lỗi chọn **Thử lại**, xác nhận query cũ được dùng và kịch bản về bình thường.
4. Click nhanh hai gợi ý; chỉ kết quả của gợi ý cuối được hiển thị. Tab qua form, dùng Enter từ nút tìm kiếm; kiểm tra labels/focus/live status.
5. Xem ở viewport 390 px và desktop; kiểm tra nội dung, select và cards không tràn ngang.
6. `npm run build && npm run preview`: mock không hiện, API chưa có phải báo lỗi; kiểm tra Network có POST `/api/v1/search/text`, không có dữ liệu fixture thay thế.

## Giới hạn và bàn giao

- Cần Vũ Nguyễn Quỳnh Anh review [contract nháp](../contracts/search-text.md) trước khi nối backend ở W3. Chưa có schema/OpenAPI thực thi, API thật, proxy/CORS hoặc integration test.
- Đã có unit/component regression suite trong repo. jsdom không đo layout thực; cần suite E2E trình duyệt và tích hợp backend khi nhóm triển khai tooling/API.
- Chưa triển khai image search, filters UI, asset detail/download, feedback hoặc admin; các phần này thuộc tuần sau.
- Review/merge là bước riêng; không tuyên bố CI xanh, PR được approve hoặc release.
