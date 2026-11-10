# Bàn giao frontend tìm ảnh và feedback W4

Phạm vi này ghép thay đổi local từ worktree image và feedback vào workspace chính. Không sửa backend contract; feedback dùng `POST /api/v1/feedback` đã triển khai ở #81.

## Luồng ảnh

- `/#image-search` gửi multipart `image`, filters JSON, page và limit theo contract #79/#80; browser tự tạo multipart boundary.
- UI kiểm tra JPEG/PNG bằng signature và decode, giới hạn 5 MiB/4096 px; API vẫn xác thực độc lập.
- Loading, empty, lỗi, retry, filters, pagination và versions hiển thị theo response. Khi API lỗi UI không chuyển sang mock.
- Detail gọi asset API thật và giữ lại state tìm kiếm khi quay về.
- Báo cáo HTTP/UI smoke thật và giới hạn self-match được ghi trong [hướng dẫn W4](../guides/frontend-image-w4.md).

## Feedback text và ảnh

- Mỗi kết quả truyền đúng `search_event_id` và `asset_id` từ response search. Mỗi lần tìm kiếm/trang mới tạo event mới; feedback gắn với event đang hiển thị.
- Gửi JSON `{search_event_id, asset_id, relevance}`; relevance là Boolean. Backend append một bản ghi cho mỗi lần gửi hợp lệ, kể cả gửi lại hoặc đổi đánh giá.
- Trước POST, client đọc OpenAPI và yêu cầu response schema tương ứng `FeedbackResponse` (mock) hoặc `LiveFeedbackResponse` (PostgreSQL). Điều này chặn event live khi API đang trỏ vào mock.
- Chỉ báo thành công sau HTTP 201 và khi feedback ID, event, asset, relevance, timestamp, `mock` và `storage` khớp contract. Lỗi có thể retry; API error code được chuyển thành hướng dẫn tìm lại phù hợp.
- Response #81 không trả model/index/config versions; versions được lưu trên `SearchEvent` mà feedback tham chiếu. PostgreSQL integration test kiểm tra query type, result snapshot và versions của event gắn với từng feedback.

## Bằng chứng và trạng thái

- Backend PostgreSQL integration: `backend/tests/integration/test_feedback_stack.py`.
- Frontend component/client tests và E2E ảnh: `frontend/src/features/search/Feedback*.test.tsx`, `frontend/tests/e2e/image-live.spec.ts`.
- UI ảnh thật, API thật, versions và snapshot event: [hướng dẫn W4](../guides/frontend-image-w4.md); E2E mock/interception không được tính là retrieval thật.
- Checklist task và acceptance của Issue #81 đã được đánh dấu theo test và contract đã kiểm tra; Issue vẫn mở. Review, CI GitHub và merge vẫn là bước riêng.
