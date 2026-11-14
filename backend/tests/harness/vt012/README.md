# VT-012 — Retry Qdrant upsert không tạo bản ghi logic trùng

Đoàn Thị Minh Khuê — 23001894 — AI-04 — SE2026-T03. Refs #113.

## Phạm vi

Patch dùng trực tiếp `app.search.qdrant_store.QdrantStore`, không cài một bản
search implementation riêng. Module đã có UUID5 ổn định; bổ sung retry HTTP
tạm thời cho đúng lời gọi upsert, giữ nguyên points giữa các lần thử.

Chỉ `COMPLETED` mới trả số point. Hết lượt vẫn ném lỗi; timeout không chứng minh
remote đã rollback. Cam kết chỉ là không thêm bản ghi logic khi retry cùng yêu
cầu bất biến, không phải remote chỉ ghi vật lý một lần. Không retry cả pipeline.

## Môi trường và cài đặt

Repository dùng Python 3.13. Thực nghiệm trong gói được chạy bằng Python 3.12.14
trong môi trường riêng; chạy lại trên Python 3.13 của nhóm trước merge.

Nếu đã cài `backend/requirements-dev.txt`, dùng môi trường đó. Để chỉ chạy lát
cắt nhẹ này mà không tải torch/model, có thể tạo venv **bên ngoài repo**:

```powershell
python -m venv ../vt012-venv
../vt012-venv/Scripts/python.exe -m pip install qdrant-client==1.15.1 pytest==9.2.0 pytest-cov==7.1.0
```

Linux/macOS thay executable bằng `../vt012-venv/bin/python`. Môi trường đo còn
có httpx 0.28.1, coverage 7.17.3; gói bằng chứng có danh sách versions đầy đủ.
Không cần Qdrant server, PostgreSQL hoặc model để chạy harness này.

## Các lệnh từ root repository

```powershell
../vt012-venv/Scripts/python.exe -m pytest backend/tests/unit/test_qdrant_store.py backend/tests/harness/vt012 -q
../vt012-venv/Scripts/python.exe -m pytest backend/tests/unit/test_qdrant_store.py backend/tests/harness/vt012 -q --vt012-reverse
../vt012-venv/Scripts/python.exe -m pytest backend/tests/harness/vt012/test_http_timeout.py -q -s
../vt012-venv/Scripts/python.exe -m pytest backend/tests/unit/test_qdrant_store.py backend/tests/harness/vt012 --cov=app.search.qdrant_store --cov-branch --cov-report=term-missing
../vt012-venv/Scripts/python.exe backend/tests/harness/vt012/load.py --output work/vt012-load.json
```

Các file sinh ra như `.coverage`, raw logs, JSON samples giữ ngoài commit.

`test_retry.py`: T01–T18, 29 cases khi parametrization. `test_http_timeout.py`:
T19, HTTP client thật qua loopback fixture, server ghi bằng Qdrant local thật
rồi giữ phản hồi để client nhận ReadTimeout thật. `test_retry_config.py`:
T20–T23, 14 cases. Cộng 22 test module cũ: 66 cases.

## Mutation đảo true/false của business rule

Chỉ chạy khi đang ở nhánh nhiệm vụ gắn với Issue thật và đã tự review diff:

```powershell
../vt012-venv/Scripts/python.exe backend/tests/harness/vt012/mutation.py --output-dir ../vt012-evidence
```

Script tạo nhánh **local tạm** mang Issue ID, bỏ `not` ở điều kiện retry,
chạy T01–T18, lưu kết quả, khôi phục đúng bytes source trong `finally` và trở về
nhánh ban đầu. Không commit/push mutation. Log có SHA-256 trước/sau và exit code.
Kiểm tra working tree sau chạy; chạy lại suite bình thường để xác nhận green.
Không dùng script để chuyển nhánh trong checkout đang chứa thay đổi người khác.

## Load harness và giới hạn

Mỗi vòng tạo một local Qdrant store riêng, 120 tác vụ đồng thời, hai point mỗi
tác vụ. Barrier trong first-upsert đảm bảo 120 lời gọi overlap. Độ trễ 20 ms/lần
và lỗi ở 20% lượt đầu được chủ động đưa vào: 10% partial write, 10% write xong
mất phản hồi. Retry delay 10 ms. Qdrant local state được bảo vệ bằng lock.

p95 tính nearest-rank trên tất cả tác vụ kết thúc, tính cả backoff/chờ trong
harness; báo riêng errors, max-active, tổng attempts và đối chiếu tập asset ID.
Không đo thời gian tạo 120 threads trước barrier. Dữ liệu tổng hợp tự tạo,
vector 3 chiều, không phải Objaverse hoặc benchmark retrieval.

Đây **không phải** bằng chứng năng lực 120 người dùng của production. Chưa đo
server Qdrant thật, model, PostgreSQL, UI, replication, process restart, gRPC
hoặc hai payload khác nhau cạnh tranh cùng asset. Cần môi trường riêng và contract
để thực hiện các kiểm tra đó; không dùng index chung của nhóm cho fault injection.

## Bằng chứng và review

Baseline: `4ceee3c4dd69d7126928b59dba582a0633e1d795` trên develop.
Các raw logs/report thực nghiệm được giao cùng báo cáo, không tự nhận chúng là CI
hoặc approval. Hãy đọc `plan.md`, kiểm tra assumptions, diff và test oracle.
Nhánh/PR nộp bài phải được publish riêng và có reviewer khác tác giả trước merge.
