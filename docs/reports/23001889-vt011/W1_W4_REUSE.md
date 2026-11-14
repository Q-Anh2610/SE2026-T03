# Tái sử dụng đóng góp W1 đến W4 cho VT 011

Tài khoản đã đối chiếu: TrinhHuyen05, Trịnh Thị Thu Huyền.
Baseline develop 63122a3a05a920a847793253a4527a871d5aa6e8.
Các PR dưới đều có merged_at; đây là bằng chứng nền, không phải PR BT3.

| Tuần | Issue và PR | Commit chính | Tái sử dụng có kiểm chứng |
|---|---|---|---|
| W1 | #26; PR #30, #40 | 0500610f98125e7d2158378568c2464e156cadc9 | SourceAdapter chuẩn hóa 18 trường, validate manifest |
| W2 | #41; PR #52, #61 | 550ad3b3a04c0af09927320a302d31e42af35183 | upsert_downloaded_asset, PostgreSQL thật, ghi lại không trùng |
| W3 | #62; PR #74 | 164c2eca3569aea091ab4b88facd3880bc99a9cb; c43478ebb66cfaca29e79993b3b6b1ed0e9735a9 | snapshot 354 = baseline 200 + 154, hồi quy lỗi preview/cache |
| W4 | #92; PR #94 | 4d318d67a96ca6becfca9a05cac76b243ccc978b | checksum/provenance, audit, báo cáo CSV/JSON |

Issue: https://github.com/Q-Anh2610/SE2026-T03/issues/<number>
PR: https://github.com/Q-Anh2610/SE2026-T03/pull/<number>
Commit: https://github.com/Q-Anh2610/SE2026-T03/commit/<sha>

## Bằng chứng mới trong lần rà soát

1. w1w4-regression.txt: 153 passed (148 ingestion unit + 5 integration persistence).
2. T17 trong test_w1w4_reuse.py có hai dataset: 200 và 354. W1 reader ->
   W2 upsert hai vòng -> PostgreSQL migration thật -> API export. Exact IDs,
   name/tags/formats/license/author/source_url đối chiếu manifest độc lập; giữ
   một asset abo ngoài phạm vi để phát hiện rò dữ liệu; test overflow và read-only.
3. Bộ snapshot test cũ kiểm tra annotations, 200+154, SHA/provenance và curation;
   không phải lần tải/giải mã lại ảnh hay xác nhận con người đã duyệt ảnh.
4. Preview của T17 là fixture checksum, không tuyên bố tải lại preview thật.
5. build_coverage.py W4 đo độ phủ danh mục, không phải code coverage.

## Phạm vi và giới hạn

BT3 dùng quyền theo source do server cấp. Không có tenant/owner contract trong
baseline; không coi objaverse grant là quyền chỉ đọc snapshot 200 hoặc 354.
T17 seed từng snapshot vào schema test riêng và chứng minh đúng tập dữ liệu đó;
không chứng minh hai snapshot cùng source được phân quyền tách biệt.
Production route/auth không được thay đổi. Harness là vertical slice chạy được
theo ngoại lệ repository chưa đủ điều kiện tích hợp của đề.

Các Issue/PR W1-W4 không thay thế link branch/PR chứa patch BT3. GitHub chỉ đọc.
Chưa tạo branch/commit mutation hợp lệ; cần Issue riêng và bước Git khi được giao.


## Cập nhật phạm vi bàn giao Issue 112

Người dùng đã chọn Issue BT3 riêng #112 và nhánh test/112-vt011-export-metadata.
Được phép tải source/test/docs sạch; không mở PR/merge, mutation chỉ cục bộ.
Các mô tả chỉ đọc hoặc liên kết #92 trước đó là lịch sử. Baseline vẫn 63122a3.
