# Review kỹ thuật của agent - không phải approval của sinh viên/nhóm

L06 slide 17: review theo 4 lớp.

1. Scope: một service ingestion mới; API nằm trong tests/harness. Không thay main.py,
   auth production, migrations, schema chung, dependency chung, search hoặc frontend.
2. Design: tái sử dụng Asset/AssetMetadata/asset_metadata và error handlers hiện có.
   Source là scope mẫu do server cấp; thiếu auth/ownership là lý do chọn harness.
3. Correctness: guard cả HTTP và service trước SQL; WHERE source trước LIMIT;
   strict input; giữ null/ARRAY; metadata public không model_path/checksum/local URLs;
   materialize trước attachment; overflow không cắt âm thầm; mỗi request Session riêng.
4. Evidence: red 404 đúng lý do; T10 phá cột ARRAY tags trong PostgreSQL đã migration;
   T11 trộn 40 success/denial requests; T15 TCP download; T05 giết mutation.

Review AI tests: bỏ U04 lặp lại assertion scope đã có ở U02/T05; không tăng số test
để tạo cảm giác bao phủ. Oracle scope dùng ID fixture độc lập, không gọi service
triển khai để tạo expected result.

Performance: phép đo đầu p95 3.2207s >1.5s. Thay select full Asset bằng load_only
12 thuộc tính mapper cần, raiseload=True để bắt thiếu projection, không đổi response.
Bổ sung T16 đảm bảo không lazy-load/N+1 queries. Giữ raw kết quả trước/sau, không
giảm dataset để biến số vượt ngưỡng thành pass.
Kết quả sau projection: p95 3.2583s, vẫn >1.5s và không nhanh hơn lần đầu 3.2207s.
Không khẳng định cải thiện hiệu năng; giữ projection vì giảm cột đọc và raiseload
giúp phát hiện contract mapper đổi. Cần profiling trước tối ưu tiếp.

Giới hạn chưa được xác minh: auth production, chính sách ownership, UI/login E2E,
ghi ingestion đồng thời, revocation, Internet/TLS/đa tiến trình và tải kéo dài.
Không dùng 100% coverage hay test pass để kết luận production an toàn.

GitHub chỉ đọc theo user steering; không tạo Issue, branch remote, commit push,
PR hoặc merge. Student/team review và thành phần Git của rubric chưa hoàn tất.


## Review bổ sung

Thay ORM entities bằng SQLAlchemy Row cho đường đọc export, vẫn dùng tên 12
thuộc tính mà asset_metadata truy cập. Không cập nhật mapper chung hoặc DTO;
Row không hỗ trợ relationship/lazy-load, nên T16 và T17 bảo vệ contract đó.
T17 dùng manifest độc lập làm oracle thay vì lấy expected từ mapper đang test.
153 test nền được chạy lại; không cộng kết quả cũ trong PR thành test mới.
34 test BT3 pass, 59/59 statements và 8/8 branches phạm vi đo. Mutation bị giết,
source được khôi phục nguyên bytes. Kết quả tải mới trong load.json/confirmation.
Chưa có review/approval của sinh viên hoặc nhóm; chưa có GitHub branch/PR BT3.


## Ủy quyền công bố liên quan Issue 92

Người dùng yêu cầu tạo nhánh BT3, commit mutation cục bộ và Draft PR.
Không tạo Issue mới, không sửa Issue #92, không merge main/develop.
Issue W4 là bằng chứng nền, không khẳng định export API đã hoàn thành trong W4.
Lịch sử chỉ đọc ở trên được thay bằng phạm vi hẹp này.


## Cập nhật phạm vi bàn giao Issue 112

Người dùng đã chọn Issue BT3 riêng #112 và nhánh test/112-vt011-export-metadata.
Được phép tải source/test/docs sạch; không mở PR/merge, mutation chỉ cục bộ.
Các mô tả chỉ đọc hoặc liên kết #92 trước đó là lịch sử. Baseline vẫn 63122a3.
