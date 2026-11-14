# Bài cá nhân 3 — VT-009 — Lê Thị Linh Chi, 23001836

Baseline `origin/develop`: `63122a3a05a920a847793253a4527a871d5aa6e8`.
Nhánh `test/76-vt009-config-harness`. Issue #76 là ngữ cảnh search của TV3,
không có ý nghĩa mở lại hoặc ghi đè kết quả đầu việc đã hoàn thành.

## Phạm vi và quyết định

Đọc `plan.md` trước. Thay đổi nghiệp vụ được chọn là giới hạn ứng viên retrieval:
quản trị viên đổi `candidate_limit` nguyên trong [1, 200] tại một file JSON.
Request tìm kiếm kế tiếp dùng snapshot mới, không sửa mã ở nhiều nơi. Giữ
RetrievalConfig và TextSearchService có sẵn. `ConfigurableSearch` là wrapper
tùy chọn, chưa được wire vào main.py. Không đổi contract top-200 của API sản phẩm.

Harness dùng FastAPI/TestClient, Qdrant thật trong bộ nhớ, 205 asset giả lập và
encoder trả vector đơn vị 3 chiều. Hai credential `fixture-admin`/`fixture-viewer`
là dữ liệu test cố định, không phải secret hay cơ chế đăng nhập production.
Role lấy từ map do server sở hữu, không lấy từ body hoặc header role tùy ý.
Không triển khai JWT/OAuth, không dựng lại PostgreSQL/UI và không tải model.

Các giả định [1,200], quyền admin và hành vi lỗi ghi cần owner review trước khi
tích hợp. Hai endpoint `/harness/config` và `/harness/search` chỉ tồn tại trong
app sandbox được tests dựng, không xuất hiện trong OpenAPI sản phẩm.

## Chạy lại (từ gốc repo, Python 3.13 và môi trường backend hiện có)

```powershell
python -m pytest backend/tests/harness/vt009/test_vt009.py -q --basetemp=work/vt009-pytest
python backend/tests/harness/vt009/load.py --output work/vt009-load.json --temp-root work/vt009-temp
$env:VT009_ORDER_SEED = '23'
python -m pytest backend/tests/harness/vt009/test_vt009.py -q --basetemp=work/vt009-order
Remove-Item Env:VT009_ORDER_SEED
```

`--basetemp` phải là thư mục scratch riêng: pytest có thể dọn nội dung thư mục đó.
Windows sandbox có thể chặn socketpair của asyncio dù không gọi Internet. Chạy
TestClient ở terminal local bình thường nếu gặp treo lúc khởi tạo event loop.

Coverage là công cụ đo tùy chọn, không thêm vào dependencies sản phẩm:

```powershell
python -m coverage run --branch --include='*/app/search/configurable_search.py,*/harness/vt009/support.py' -m pytest backend/tests/harness/vt009/test_vt009.py -q --basetemp=work/vt009-coverage
python -m coverage report -m
```

Kết quả local ngày 14/11/2026: 32 cases tham số hóa pass; shuffle seeds 7/23/101
đều pass. Wrapper: line 32/32 = 100%, branch 3/4 = 75%; nhánh chưa chạy là cleanup
khi chưa tạo được temporary file. Không suy từ coverage này ra chất lượng toàn repo.
Regression chọn lọc 215 pass, gồm 32 cases mới và 183 cases hiện có ở smoke,
text contract/API/runtime, filters, Qdrant và image search. Không xác nhận CI.

## RED, GREEN và mutation

RED scaffold mới xác thực input/quyền nhưng chưa persist đề xuất cấu hình.
TC02 với K=2 nhận 200 IDs, fail đúng outcome; đây là bước phát triển tính năng,
không phải tuyên bố baseline sản phẩm có bug này. Patch chỉ thêm ghi atomic
(temporary file cùng thư mục, flush/fsync, os.replace, cleanup). GREEN 32 pass.

Mutation được thực hiện trên nhánh tạm `test/76-vt009-mutation-local`:
đổi duy nhất `if role != "admin":` thành `if False:` trong `change_limit`.
TC04 chết ngay assertion file bất biến trước khi kiểm status: viewer đã thay được
file. Khôi phục byte-for-byte source rồi quay nhánh bài; không commit deliberate
bug. Recipe này chỉ để thực hiện lại trên nhánh tạm, không chạy trên repo chung.

## Tải và giới hạn kết luận

3 waves, mỗi wave có barrier cho 200 worker cùng phát POST tới app ASGI trong
process. 5 warmup không tính. 600 lượt đều được kiểm đủ IDs a000..a009 và
config_version K=10; không loại lỗi khỏi p95. Nearest rank ceil(0.95*600) = 570.
p50=0.942325s, p95=1.649788s, max=1.774747s, lỗi nghiệp vụ=0.
p95 riêng ba wave: 1.674235s / 1.530245s / 1.720301s.
Đạt ngưỡng 5s **trong harness**. Có tính hàng đợi RLock adapter hiện có, không
đo TCP/TLS, DB metadata/events, CLIP thật, dữ liệu thật hay tải kéo dài.
Không tuyên bố 200 người dùng production đạt SLA.

## Traceability rút gọn

| AC / risk | Test | Oracle |
|---|---|---|
| AC1 đổi cấu hình một nơi | TC02, TC09 | file, IDs, limit, config_version sau tái tạo wrapper |
| AC2 boundary / dữ liệu sai | TC02, TC03, TC13 | [1,2,199,200] đúng; 0/201/bool/string sai và không đổi file |
| AC3 authorization | TC04, TC05, TC12, TC15 | file/outcome bất biến khi thiếu quyền, mutation bị giết |
| AC4 hồi quy retrieval | TC01, TC06, TC07, TC11 | IDs, thứ tự, filter, rỗng và lỗi index/encoder |
| AC5 ghi thất bại / consistency | TC08, TC10, TC14 | giữ policy cũ; config hỏng 503; mỗi response có snapshot thống nhất |
| NFR tải 200 / p95 5s | load.py | 600 raw timings và oracle trên từng lượt |

Log/raw results nằm trong gói evidence kèm báo cáo, không commit runtime outputs.
Chưa review bởi thành viên khác, chưa merge. Người nộp phải đọc và giải thích
diff/test, tự xác nhận AI disclosure và phần phản tư trước khi nộp.
