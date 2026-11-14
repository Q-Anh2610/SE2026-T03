# Kế hoạch trước patch — VT-012, 23001894

## Baseline và phạm vi

- Repository: https://github.com/Q-Anh2610/SE2026-T03
- Dùng `origin/develop`, không dùng `main` (main chỉ có scaffold).
- Module gần nhất: `backend/app/search/qdrant_store.py`, phương thức `upsert`.
- Người làm bài: Đoàn Thị Minh Khuê; reviewer module cần phối hợp: Lê Thị Linh Chi.
- Chưa có Issue riêng: chưa tạo commit, chưa push và chưa có branch/PR nộp bài.

## Prompt chính

“Đọc code repository. Lập kế hoạch và nêu assumptions trước khi sinh patch.
VT-012: retry lỗi dịch vụ ngoài tạm thời, không lặp side effect; rủi ro partial
failure. Viết test fail trước; dùng state transition testing, đảo true/false một
business rule để đánh giá test, đo 120 tác vụ/p95 3.5 giây và ghi giới hạn.
Giữ patch nhỏ, không đổi API/schema/model hoặc tải dataset.”

## Assumptions cần kiểm chứng

- A1 (giả thuyết cần review, không dùng làm tiền đề triển khai): timeout đồng
  nghĩa dịch vụ chưa ghi, nên tạo ID mới khi retry. Người dùng phản hồi:
  “Chưa đủ căn cứ; cần kiểm tra hành vi timeout.” Chưa ghi nhận người dùng bác bỏ.
- A2: phải tạo cơ chế idempotency mới. Đối chiếu thấy module đã tạo UUID5 từ
  asset_id trước khi gửi. Sửa kế hoạch: tái sử dụng chính IDs/points đó.
- A3: retry cả pipeline sẽ đơn giản và an toàn. Đối chiếu thấy encoder và
  persistence có các ranh giới riêng; không cần chạy lại các bước đó. Sửa kế
  hoạch: chỉ retry lời gọi upsert cùng points, wait=True.
- A4: local-mode test có thể đại diện production p95. Bác bỏ trong review kỹ
  thuật: Docker chưa chạy, local/injected latency không đại diện Qdrant server,
  PostgreSQL, model hay UI thật. Ghi rõ harness và chỉ kết luận trong môi trường đo.

## Acceptance criteria đề xuất

AC1: 408/429/500/502/503/504 và lỗi transport HTTP được chọn sẽ retry tối đa
3 lần (tính lần đầu); lỗi hết lượt vẫn được ném ra.

AC2: cùng một lần gọi upsert dùng cùng ID/vector/payload cho mọi lần thử.
Timeout sau ghi và partial write rồi hồi phục phải hội tụ về đúng tập asset.
Không tuyên bố exactly-once cho số lần thực thi remote.

AC3: metadata/vector/index không hợp lệ hoặc HTTP 4xx vĩnh viễn không retry;
không thay dữ liệu cũ khi validation từ chối.

AC4: chỉ trả số point khi status COMPLETED; ACKNOWLEDGED và hết lượt retry
không được ghi nhận thành công hoặc cập nhật searchable giả.

AC5: bộ test có state transitions, negative/failure cases, mutation đảo rule,
log red/green; harness 120 tác vụ báo p95 và audit point IDs, không đánh đồng
với hiệu năng hệ thống thật.

NFC1: giới hạn attempts 1..3 và delay hữu hạn 0..0.5 giây; tránh retry vô hạn.
NFC2: không thêm runtime dependency; giữ API/schema và dữ liệu người dùng.
NFC3: ngưỡng tải đề bài 120 tác vụ/p95 <=3.5 giây; kết luận production còn chờ
chạy thật. Không dùng percentile riêng của request thành công để che lỗi.

## Các bước / file dự kiến

1. Chạy test Qdrant cũ; viết và chạy `test_retry.py` để lưu red log.
2. Kiểm chứng timeout-after-write bằng local Qdrant và fault adapter; bổ sung
   kiểm tra HTTP loopback thật để phân biệt transport timeout với lỗi parse.
3. Sửa riêng `qdrant_store.py`: validate retry config, phân loại lỗi, retry
   bounded/backoff, giữ points ngoài vòng lặp và giữ completed gate.
4. Chạy lại cả test cũ/mới, branch coverage; lưu logs.
5. Đảo điều kiện retry trên bản tạm, chạy test và phục hồi đúng bytes; lưu
   SHA trước/sau để chứng minh mutation không nằm trong code bàn giao.
6. Chạy load harness 120 tác vụ đồng thời và review time/shared-state/network.
7. Bàn giao README, diff, evidence và báo cáo LaTeX; chờ Issue, branch/PR,
   review của người dùng/nhóm, không tự merge.

## Bằng chứng review kế hoạch

R1: `QdrantStore.upsert` đã tạo `uuid5(NAMESPACE_URL, f"ai04/asset/{asset_id}")`.
Không tạo UUID mới mỗi attempt và không thêm idempotency table.

R2: `ensure_collection`/compatibility và `COMPLETED` gate đã có. Giữ nguyên,
chỉ retry thao tác upsert; không catch mọi Exception, không coi lỗi parse là
lỗi tạm thời. `ResponseHandlingException.source` chứa nguyên nhân cụ thể.

R3: `main` chỉ scaffold trong khi `develop` có implementation và 22 test cũ.
Chọn develop làm baseline, không xây harness tách rời thuật toán sản phẩm.

R4: Docker Desktop Linux Engine chưa hoạt động. Có harness local/network giả
lập; integration Qdrant server và E2E browser thật chưa được chứng minh.

## Cập nhật sau thực nghiệm (không thay lịch sử kế hoạch ban đầu)

- Người dùng cung cấp Issue #113; đã xác minh tiêu đề/phạm vi và tạo nhánh
  `test/113-vt012-retry-idempotency` từ baseline develop đã ghi nhận.
- Người dùng yêu cầu thêm căn cứ về A1; sau thông báo tóm tắt thí nghiệm vẫn
  trả lời “Chưa bác bỏ; tôi cần xem thêm bằng chứng.” Đã cung cấp raw HTTP log
  và giải thích; chưa được ghi tiêu chí tự bác bỏ assumption là hoàn thành.
- HTTP loopback thật: server ghi trước ReadTimeout; retry cùng body cho 2
  request/1 point. Server là fixture, data store là Qdrant local, không phải
  kiểm chứng production Qdrant server.
- Bộ cuối: 66 pass, chạy đảo thứ tự 66 pass. Mutation bỏ `not` ở business rule
  trên nhánh local tạm: 22 fail/7 pass; source khôi phục đúng SHA-256; suite sau
  khôi phục 66 pass. Logs/code được đóng gói riêng.
- 5 vòng tải đủ 120 tác vụ chồng lấp, 0 lỗi, audit đúng 240 point/vòng; p95
  0.1442–0.1700 giây trên fixture, chưa đo production.
- Người dùng đã cho phép commit và push riêng nhánh nhiệm vụ sau khi được cung
  cấp gói code/diff để review. Không được suy diễn thành review nhóm hoặc quyền merge.
