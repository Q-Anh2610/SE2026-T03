# Personal Assignment 3 - Trịnh Thị Thu Huyền - 23001889 - VT-011

Repository đọc: https://github.com/Q-Anh2610/SE2026-T03.git
Baseline: `63122a3a05a920a847793253a4527a871d5aa6e8` (develop, đọc ngày 14/11/2026).

**Bài BT3 riêng:** https://github.com/Q-Anh2610/SE2026-T03/issues/112
Nhánh nộp: https://github.com/Q-Anh2610/SE2026-T03/tree/test%2F112-vt011-export-metadata
Người dùng cho phép công bố source/test/docs sạch trên nhánh này; không mở PR,
không merge/push main/develop. Mutation chỉ giữ cục bộ. Các đoạn trạng thái cũ
bên dưới là lịch sử; xem GIT_EVIDENCE.md và PDF để biết bằng chứng hiện tại.

## Phạm vi

- Service `backend/app/ingestion/export_metadata.py`, đúng module ingestion của Huyền.
- FastAPI harness `backend/tests/vt011/api.py`, không đăng ký vào main.py.
- Dùng ORM Asset, schema/mapping public metadata và error handler hiện có.
- PostgreSQL thật với Alembic 0001 -> 0002; không mock Session/DB và không dùng SQLite.
- Quyền và scope là fixture do server cấp; source không phải tenant ownership.
  Chưa có auth production và chưa được owner phê duyệt policy source.
- Backend E2E dùng HTTP/TCP qua Uvicorn, tải file xuống tmp_path; không phải E2E UI/login.

## Chạy test (Python 3.13; từ gốc repository)

```powershell
python -m venv .venv-vt011
.\.venv-vt011\Scripts\python.exe -m pip install -r docs/reports/23001889-vt011/requirements.txt
$env:VT011_DATABASE_URL='postgresql+psycopg://vt011@127.0.0.1:55439/test_vt011_huyen'
.\.venv-vt011\Scripts\python.exe -m pytest backend/tests/vt011 -q
.\.venv-vt011\Scripts\python.exe scripts/vt011_experiments.py
```

Linux/macOS: dùng `.venv-vt011/bin/python` và `export VT011_DATABASE_URL=...`.
DB phải có tên bắt đầu `test_vt011_`, role có quyền tạo/xóa schema trong DB test
riêng. Nếu không đặt URL, các tests PG skip và không được báo đó là suite pass đầy đủ.

Mỗi test tạo schema ngẫu nhiên riêng, chạy migrations thật, commit fixtures,
sau đó xóa đúng schema test do chính fixture tạo. Không trỏ vào DB nhóm.
Schema random chỉ dùng isolation; logical test data/expected IDs không random.

## Tạo PostgreSQL test riêng trên Windows nếu chưa có DB

Cần PostgreSQL 18 đã cài. Các lệnh dưới tạo cluster mới trong thư mục TEMP mới,
chỉ listen loopback; không thay cấu hình service PostgreSQL đang có.

```powershell
$vtPgBin='C:\Program Files\PostgreSQL\18\bin'
$vtRuntime=Join-Path $env:TEMP ('vt011-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $vtRuntime | Out-Null
& "$vtPgBin\initdb.exe" -D "$vtRuntime\pgdata" -U vt011 --auth-local=trust --auth-host=trust --encoding=UTF8 --no-locale
& "$vtPgBin\pg_ctl.exe" -D "$vtRuntime\pgdata" -l "$vtRuntime\postgres.log" -o '-h 127.0.0.1 -p 55439' -w start
& "$vtPgBin\createdb.exe" -h 127.0.0.1 -p 55439 -U vt011 test_vt011_huyen
```

Chọn cổng trống khác nếu 55439 đang dùng và sửa URL tương ứng. Trust auth chỉ
dành cho cluster test mới, dùng local, không cho production hoặc dữ liệu thật.
Chạy xong dừng đúng cluster vừa tạo:

```powershell
& "$vtPgBin\pg_ctl.exe" -D "$vtRuntime\pgdata" -m fast -w stop
```

## Contract API trong harness

`POST /api/v1/exports/assets` với JSON `{"source":"objaverse","limit":1000}`,
Authorization `Bearer fixture-a` (chỉ fixture, không credential thật).

- Quyền được server cấu hình. fixture-a: export objaverse; fixture-b: export abo;
  fixture-reader: không có export; fixture-empty: export nguồn không có record.
- 401 thiếu/sai token, 403 thiếu quyền/sai scope, 400 input sai (limit integer strict
  1..2000; source trim không rỗng <=64; forbid extra fields).
- 200 attachment assets.json UTF-8, no-store; items đúng source, sort asset_id,
  dùng đúng 12 trường AssetMetadata hiện có, null/ARRAY/Unicode được giữ theo mapper.
- Nếu số dòng > limit: 413 trước attachment, không silent truncate.
- Nếu SQL/schema lỗi: 503 sanitized; không fallback fixture hoặc xuất file một phần.
- Validation body có thể chạy trước auth; mọi truy cập DB đều sau authorization.

## Bằng chứng

`red.txt`: route chưa có, 404 !=200. `red-reproduced.txt`: chạy lại scaffold đó.
`green.txt`, `coverage.txt/json`: suite sau patch/restore. `mutation.txt/diff`: bỏ
source authorization khiến T05 fail 200 !=403. File source luôn restore trong finally.
`concurrency-repeat-1..3.txt`, `reverse-order.txt`: checks flaky/order.
`load-before-optimization.json`, `load.json`: raw HTTP/TCP measurements trước/sau
projection, cùng workload 40x5, 2000 asset giả, 1000 records/request.
`integrity.json`: SHA-256 restore; PUBLICATION.json/GIT_EVIDENCE.md ghi trạng thái công bố hiện tại.

Chạy experiments sẽ ghi đè logs cục bộ; không chạy cùng lúc hoặc khi đang sửa code.
Không có lệnh Git remote write trong script. Script tái lập mutation bằng file tạm;
nhánh/commit mutation thật được thực hiện riêng và ghi tại GIT_EVIDENCE.md.

## Đối chiếu bài giảng

- Lecture 06: slide 9-14 (spec/plan/context/checkpoint), 17-19 (review/evidence/trust),
  21-23 (GitHub traceability, ownership). PLAN.md và báo cáo chỉ rõ assumptions bị bác bỏ.
- Lecture 07: slide 7-11 (risk/test levels/contracts), 17-23 (AAA, coverage, regression,
  real dependencies, flaky, AI-test traps, mutation), 26 (concurrency invariant).

Báo cáo/AI log do Codex hỗ trợ; sinh viên cần tự đọc, chạy và hiểu code trước khi
xác nhận cam kết. Người dùng đã cho phép nhánh/Draft PR liên quan Issue #92;
commit/push/PR theo AGENTS.md, không tự merge.

## Cập nhật cục bộ ngày 14 tháng 11 năm 2026

- 34 test BT3 pass; 153 test nền W1-W4 pass. Hai bộ có mục đích khác nhau.
- T17: manifest 200/354 -> SourceAdapter W1 -> writer W2 (hai vòng) -> export.
- Truy vấn mới select 12 cột và dùng Row với mapper public hiện có, không tạo
  tracked ORM entity. T16 giữ 1 SQL/export; T17 kiểm tra metadata thật.
- load-before-row-projection.json lưu lần cũ; load.json là 40x5 mẫu lần mới;
  load-confirmation.json là lượt xác nhận độc lập cùng cấu hình.
- Coverage chỉ service và harness API; auth là fixture, scope theo source.
- Xem W1_W4_REUSE.md cho attribution, evidence và giới hạn.
- Nếu pytest không ghi được TEMP, chọn --basetemp ở thư mục test cục bộ riêng;
  lỗi quyền thư mục không được tính là product red.


## Công bố phần mở rộng BT3 liên quan Issue 92

Refs #92. Issue W4 là công việc nền; phạm vi BT3 được người dùng yêu cầu riêng.
Không mở lại/sửa acceptance criteria Issue cũ. Các câu mô tả bàn giao chỉ đọc
phía trên là lịch sử; ủy quyền mới cho phép nhánh sạch/Draft PR, không merge.
Script experiments tái lập mutation bằng file tạm; mutation Git commit thật
của lần công bố được ghi riêng ở GIT_EVIDENCE.md, không push nhánh mutation.


## Issue riêng cho BT3

Refs #112. Issue #92 cùng các PR W1-W4 là công việc nền, không phải Issue BT3.
Người dùng đã cho phép tạo Issue/nhánh riêng và tải 19 file source/test/docs.
Không tiếp tục chính sách chỉ giữ cục bộ trước đây; không upload mutation.
