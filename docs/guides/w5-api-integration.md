# Kiểm chứng nghiệp vụ và tích hợp API W5 — Issue #118

Owner: Quỳnh Anh. Mục tiêu kiểm chứng các tính năng #115/#116/#117 trên cùng
checkout đã tích hợp với search/feedback và frontend hiện hành. Không bổ sung
API, đổi contract, migration, dependencies hoặc thuật toán retrieval.

## Khoảng trống được bổ sung

Tests từng tính năng đã tồn tại; #118 bổ sung
`backend/tests/integration/test_w5_api_coexistence.py`:

- Text/image search, explanation và feedback PostgreSQL dùng chung app với
  reindex; kiểm trước/trong/sau khi reindex succeeded hoặc failed.
- Replay/collision không làm đổi active search versions hoặc tạo job trùng.
- Feedback rollback không làm hỏng image search/jobs reads, sau sửa lỗi ghi
  được lại feedback của event cũ.
- Commit job cuối thất bại không báo succeeded và không rollback các request
  search/feedback độc lập; test ghi rõ job có thể giữ running.

Các tests trên dùng retrieval/reindex fixtures và PostgreSQL thật trong schema
UUID. Đây là bằng chứng nghiệp vụ, không chứng minh chạy model/index thật.
Concurrency qua nhiều app managers, timeout, cache, migration/drift và các lỗi
khác được kế thừa từ tests #117, không tạo lại mọi test chỉ để tăng số lượng.

## Ma trận bằng chứng

| Yêu cầu | Tests/kiểm chứng |
|---|---|
| Runner → job → GET API | verify_w5_api.py, browser gửi POST và theo dõi worker CLIP thật |
| Thành công/lỗi/concurrency | test_reindex_stack.py; smoke replay/409 trong lúc chạy và child lỗi cache |
| Auth/envelope/transaction | test_jobs_api.py, test_reindex_api.py, test_feedback_stack.py, tests coexistence |
| Search/image/feedback/explanation | Tests cũ + coexistence; browser/API thật cùng app/DB |
| Index cũ tiếp tục phục vụ | Versions giữ nguyên trước/trong/sau reindex; persisted fingerprints trước/sau |
| Index mới dùng được | Mở app HTTP test riêng trỏ index mới, search và feedback đúng versions |
| Frontend | E2E hiện có có fixtures/interception; smoke browser mới không intercept HTTP |
| Phối hợp | Duy Approve contract #116 tại PR #120; Khuê jobs/reindex UI #103/#104 qua PR #121/#123; kết quả mới #118 bàn giao review riêng |

## Chạy tests trên DB test riêng

Đặt TEST_DATABASE_URL trỏ PostgreSQL riêng có tên bắt đầu bằng `test_`, giữ URL/
credentials ngoài Git. Trên Windows dùng host 127.0.0.1 nếu localhost bị phân
giải IPv6 chậm. Các helpers chỉ tạo/dọn schema UUID của lượt chạy, không dùng
DB nghiệp vụ `semantic_search`.

Từ `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_w5_api_coexistence.py -q
```

Nhóm hồi quy W5 (API/mock/schema/OpenAPI/jobs/reindex/transactions/runtime):

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_reindex_api.py tests/unit/test_reindex_builder.py tests/unit/test_jobs_api.py tests/unit/test_search_explanation.py tests/unit/test_text_search_contract.py tests/unit/test_text_search_api.py tests/unit/test_image_search_api.py tests/unit/test_feedback_api.py tests/unit/test_mock_api.py tests/unit/test_openapi.py tests/unit/test_text_search_runtime.py tests/unit/test_config.py tests/unit/test_database_config.py tests/integration/test_w5_api_coexistence.py tests/integration/test_reindex_stack.py tests/integration/test_jobs_stack.py tests/integration/test_database.py tests/integration/test_search_explanation_stack.py tests/integration/test_text_search_stack.py tests/integration/test_image_search_stack.py tests/integration/test_text_search_bootstrap.py tests/integration/test_feedback_stack.py tests/integration/test_search_events.py -q
```

Frontend, từ `frontend/`:

```powershell
npm test
npm run lint
npm run typecheck
npm run test:e2e
```

Máy ít RAM có thể dùng `npm test -- --maxWorkers=2`; vẫn chạy toàn bộ tests.

Theo góp ý tại PR #125, chạy lại toàn bộ E2E với một worker từ `frontend/`:

```powershell
npm run test:e2e -- --workers=1
```

Lệnh vẫn build và chạy cả bốn projects, không lọc test hoặc bật retry. Lượt
ngày 17/11/2026 đạt 46/46; xem [bằng chứng chạy lại đầy đủ](../evidence/issue118-w5-integration.md#chạy-lại-toàn-bộ-e2e-theo-review--17112026).

E2E hiện có gồm các response fixtures/interception, không gọi đó là live backend
smoke. Script bên dưới chạy browser thật với API thật, không page.route/mock.

## Smoke cùng app/DB và frontend thật

Cần PostgreSQL test riêng, dependencies backend/frontend đã cài, Chrome (hoặc
channel đã cài qua PLAYWRIGHT_BROWSER_CHANNEL), model CLIP pinned trong cache,
hai index local và source/ready/preview đầy đủ đúng hashes. Không tải lại
weights/dataset hoặc build lại baseline chỉ để chạy tests.

Từ gốc repo, thay các đường dẫn theo bộ index thực sự nhận trên máy:

```powershell
.\backend\.venv\Scripts\python.exe scripts/verify_w5_api.py --text-index-root data/processed/issue65/index-1718ec3c49a0 --image-index-root data/processed/issue76/clip-build-16556914413d --image-input-root data/processed/issue80/inputs-cfd29f05b4
```

Hai baseline inputs phải cùng source hash. Verifier kiểm manifest/hashes, lấy
fingerprint khi storage chưa được app khác mở, chuẩn bị schema test với metadata
baseline và khởi chạy Uvicorn cùng Vite trên cổng localhost tự chọn.

`scripts/verify_w5_browser.mjs` dùng Playwright có sẵn trong frontend, không
thêm dependency. Khóa admin ngẫu nhiên chỉ truyền vào tiến trình browser qua
biến W5_ADMIN_KEY; không dùng VITE_* cho secret, không lưu header/key vào report.
Browser kiểm text/image/explanation/feedback, admin sai/đúng khóa, hủy xác nhận
không POST, gửi reindex, theo dõi job, replay/409 và search/feedback trong lúc
worker đang chạy; sau terminal vẫn kiểm public search/feedback. Browser lượt
sau kiểm UI của job failed do verifier chủ động cung cấp cache fixture rỗng.

Python đối chiếu event/feedback từ browser với PostgreSQL, kiểm rollback lỗi
feedback, 503 khi index unavailable không ghi event, phục hồi, job failed và
search tiếp tục giữ baseline versions. Fault injection chỉ gắn trên app test
do verifier tự tạo, không thêm route điều khiển hoặc cấu hình fixture vào sản phẩm.

Sau đóng app baseline, verifier mở app text search test riêng trỏ output mới,
gửi search/feedback và kiểm versions mới; không activate index của app đang phục
vụ. Cuối cùng reopen cả baseline storage để so fingerprint. Server/Vite/browser/
schema được dọn; output reindex và runtime report ở
`data/processed/issue118/`, không commit ảnh/cache/storage/reports runtime.

Hạn chờ startup/shutdown cho app có hai encoder là 180 giây; thời gian nạp
model không được diễn giải thành API latency hoặc benchmark. Khi chạy trên
máy hạn chế RAM, nên chạy smoke model và bộ E2E thành các lượt riêng.

## Phạm vi snapshot và giới hạn

- Baseline text/image kiểm trên `home-interior-354-v1`, đúng hai manifest/hash
  đã bàn giao W4; profile reindex vẫn chỉ frozen candidate 200
  `home-interior-clear-200-v3` theo #117. Không dùng bộ 354 thay candidate 200
  hoặc đổi benchmark đã khóa.
- Query ảnh lấy từ indexed preview, chuyển PNG chỉ để chạy diagnostic upload;
  không phải image benchmark độc lập hoặc phép đo quality/latency.
- Không activate index, bổ sung image manifest, bật E5/RRF/SigLIP2 hoặc triển
  khai Docker/worker recovery ngoài phạm vi #118.
- Các xác nhận contract/PR trước không tự là approval hoặc xác nhận chạy lại
  #118. Nhờ Duy review luồng search/feedback/explanation và Khuê review admin/
  reindex/bằng chứng browser của PR #125 (Issue #118); không tự tích thay hai người.

Báo cáo kết quả thực tế: [issue118-w5-integration.md](../evidence/issue118-w5-integration.md).
