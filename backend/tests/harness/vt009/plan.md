# VT-009 — plan trước code, 14/11/2026

Baseline: 63122a3a05a920a847793253a4527a871d5aa6e8 (`origin/develop`).
Issue #76 là ngữ cảnh module đã làm; đây là thí nghiệm cá nhân mới, không mở lại Issue.
Nhánh: `test/76-vt009-config-harness`, chưa merge.

## Prompt tác vụ cho coding agent

Đọc Lecture 06/07, PDF kế hoạch, AGENTS.md và code search của TV3. Tạo
vertical slice nhỏ cho VT-009: thay đổi một business configuration tại một nơi,
kiểm tra authorization và outcome thay vì chỉ status. Giữ framework/dependencies.
Viết test trước, chạy fail đúng lý do, patch nhỏ, mutation bỏ authorization,
coverage, flaky review và harness tải 200 tác vụ / p95 <= 5 giây. Không tuyên bố
harness là hệ thống production; không sửa code/nhánh đang làm của thành viên khác.

## Phương án AI ban đầu và review bằng repo

1. Đề xuất: thay TEXT_CANDIDATE_LIMIT từ 200 sang một biến runtime ở API/schema.
   Bác bỏ: `schemas/text_search.py` ràng buộc max_length/pagination top-200;
   `api/text_search.py:retrieve_candidates` truyền 200; bootstrap runtime chỉ
   chấp nhận manifest top-200. Đổi đồng loạt tạo scope rộng và phá contract TV1.
   Chọn wrapper tùy chọn + API harness riêng, không wire vào app production.
2. Đề xuất: đổi một file JSON là đủ; test PUT chỉ cần status 200.
   Bác bỏ: `text_search.py:search_text` tự tạo RetrievalConfig.for_limit ở mỗi call,
   không đọc JSON trên. Phải nạp config và truyền candidate_limit thực sự; test
   kiểm tra ID/số lượng/filter/config_version, file sau ghi và sau lỗi từ chối.
3. Không có auth framework hiện hành trong app đã kiểm tra. Không thêm JWT,
   OAuth hay endpoint quản trị production. Harness dùng map credential giả ở
   server để kiểm chứng authorization; không nhận role trực tiếp từ request.

## Scope đã sửa

- `backend/app/search/configurable_search.py`: wrapper đọc config JSON tập trung,
  write atomic với quyền admin, gọi service hiện có với snapshot limit.
- `backend/tests/harness/vt009/`: API sandbox, fixtures, tests, tải, README.
- Không đổi main.py, DTO/HTTP sản phẩm, schema DB, model/index hay dependency files.

## Assumptions cần chủ dự án review

- Business config được chọn: candidate_limit nguyên trong [1, 200], mặc định
  fixture 200. 200 là trần contract hiện có, không nhầm với mức concurrency 200.
- Quản trị mới có quyền sửa, tìm kiếm công khai. Credential giả chỉ ở harness.
- Lỗi ghi trả 503, file cũ và hành vi cũ phải giữ nguyên. Config hỏng không fallback.
- Baseline RED là scaffold mới chưa persist config, không phải bug được tìm thấy
  trong code sản phẩm ở commit baseline.
