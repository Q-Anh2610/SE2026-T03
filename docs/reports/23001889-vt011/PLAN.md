# Plan trước implementation - 23001889 / VT-011

Ngày 14/11/2026. Repository: https://github.com/Q-Anh2610/SE2026-T03.git
Baseline origin/develop: `63122a3a05a920a847793253a4527a871d5aa6e8`.

## Input và assumptions

Người dùng yêu cầu hoàn thành Personal Assignment 3 cho Trịnh Thị Thu Huyền
dựa trên repository và hai bài giảng Lecture 06/07. Biến thể VT-011: export API,
authorization/scope, risk mock che contract sai, concurrency, mutation bỏ validation,
40 concurrent / p95 <=1.5s; hai phương án AI và quyết định có evidence.

Prompt thực thi do agent lập (không phải trích nguyên văn người dùng):
"Đọc rules/model/API/migrations trước code. Đề xuất hai cách export metadata.
Chọn vertical slice có thể chạy, không tự thêm auth/tenant vào production.
Viết tests trước patch; chạy red đúng lý do; dùng PostgreSQL migration thật.
Test cấp quyền và phạm vi xen kẽ 40 tác vụ; bỏ validation source để giết mutation.
Đo tải qua TCP, giữ raw samples, ghi trung thực mọi giới hạn. Review theo scope,
design, correctness, evidence. Không merge hoặc bịa branch/PR."

Assumptions cần owner review: `source` là đơn vị phạm vi mẫu; không đồng nghĩa
tenant/owner. Principal do fixture server cấp; không phải auth production.
Chỉ xuất metadata công khai, không tải mesh/URL. Bounded JSON, limit 1..2000.

## Hai phương án và review bằng repository

A. Production API + JWT/tenant schema + CSV streaming. Loại trong slice này:
`backend/app/models/asset.py` không có tenant_id/owner_id; API asset hiện không
có dependency xác thực. Thêm IAM/migration làm thay đổi contract chung.

B. Service export metadata nhỏ trong module ingestion của Huyền + executable
FastAPI harness, principal fixture tin cậy, PostgreSQL thật qua migrations có sẵn.
Chọn B: đề cho phép harness khi repo chưa đủ điều kiện; giữ boundary production.

Sửa/bác bỏ ít nhất hai đề xuất ban đầu:
1. Không nhận X-Role/X-Source làm quyền: chưa có trust boundary cho header
   client (`api/assets.py`). Dùng server-side immutable principal và deny default.
2. Không dùng mock Session hoặc SQLite để chứng minh PG contract: model dùng
   ARRAY(Text), migration dùng JSONB, integration conftest có PostgreSQL test_*.
   Chạy DB 18 thật, Alembic thật, failure-path rename column thật trong schema test.
3. Không sinh CSV streaming ngay: lỗi DB giữa stream có thể trả file một phần.
   Reuse `services/assets.asset_metadata` và `schemas/api.AssetMetadata`, materialize
   limit+1 trước attachment; overflow 413, DB lỗi sanitized 503.

## Files và checkpoints dự kiến

- `backend/app/ingestion/export_metadata.py`: authorization thuần + SQL service.
- `backend/tests/vt011/{__init__,api,conftest,test_unit,test_api,test_e2e,load}.py`:
  harness/API contract, fixtures PG riêng, unit/API/TCP E2E/concurrency/load.
- `docs/reports/23001889-vt011/`: spec, test plan, AI log, README, evidence index.
- `scripts/vt011_experiments.py`: red/green/mutation/load và integrity evidence.

Trình tự: scaffold app chưa có route -> T01 red 404 !=200 -> nhỏ patch/service
và router -> suite green -> remove source authorization -> test unit giết mutation
-> restore -> coverage + order/concurrency repeats -> TCP 40x5 performance.
Không test model/encoder/Qdrant vì export không gọi chúng. Không tự merge.

Đối chiếu bài giảng: L06 slide 9-14,17-19,21-23; L07 slide 7-11,17-23,26.
Branch/commit/push chỉ sau khi có nhánh/Issue hợp lệ theo rules hoặc user xác nhận
ngoại lệ; bản clone này riêng, không tác động workspace bài nháp cũ.

## Steering sau khi bắt đầu

Người dùng yêu cầu GitHub chỉ đọc, không sửa bất cứ thứ gì trên đó. Không tạo
Issue, push branch, mở PR hoặc merge. Thiếu Issue riêng hợp lệ nên không tạo
commit trên develop hoặc bịa số Issue. Các phần code/evidence/PDF hoàn thiện
cục bộ và ghi rõ thành phần Git còn thiếu; không tự coi patch là link PR.


## Tổng hợp kế hoạch và review bổ sung ngày 14 tháng 11 năm 2026

Giữ lịch sử plan/test-first ban đầu. Tái sử dụng W1 SourceAdapter, W2 writer,
W3 snapshot và W4 provenance trong T17; chạy hồi quy cũ. Không chuyển source
scope thành snapshot ownership khi không có policy. Đọc cột cần thiết qua Row
thay tracked entities là giả thuyết tối ưu; giữ mapper public, không sửa schema.
Sau thay đổi phải chạy contract/real snapshot/mutation/coverage/reverse order,
40x5 TCP load và một lượt xác nhận. Không thay dataset hoặc ngưỡng theo kết quả.
Không tạo Issue/branch/commit/push/PR trong lần hoàn thiện cục bộ này.


## Ủy quyền công bố liên quan Issue 92

Người dùng yêu cầu tạo nhánh BT3, commit mutation cục bộ và Draft PR.
Không tạo Issue mới, không sửa Issue #92, không merge main/develop.
Issue W4 là bằng chứng nền, không khẳng định export API đã hoàn thành trong W4.
Lịch sử chỉ đọc ở trên được thay bằng phạm vi hẹp này.


## Cập nhật phạm vi bàn giao Issue 112

Người dùng đã chọn Issue BT3 riêng #112 và nhánh test/112-vt011-export-metadata.
Được phép tải source/test/docs sạch; không mở PR/merge, mutation chỉ cục bộ.
Các mô tả chỉ đọc hoặc liên kết #92 trước đó là lịch sử. Baseline vẫn 63122a3.
