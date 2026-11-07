# Feedback PostgreSQL — Issue #81

Backend kế thừa quy tắc đã chốt với frontend trong
[feedback mock v1](frontend-api-v1.md#chốt-feedback-mock-v1--19102026).
Phần persistence PostgreSQL và error cho event cũ được bàn giao để Duy review.

## Request và response

`POST /api/v1/feedback` nhận JSON:

```json
{
  "search_event_id": "00000000-0000-4000-8000-000000000080",
  "asset_id": "example-chair",
  "relevance": true
}
```

Thay IDs ví dụ bằng event và asset từ response text/image search thật. Event ID
phải là UUID, asset ID không rỗng và dài tối đa 128 ký tự. `relevance` chỉ nhận
JSON Boolean. Thành công trả HTTP 201 sau khi transaction đã commit:

```json
{
  "feedback_id": "00000000-0000-4000-8000-000000000081",
  "search_event_id": "00000000-0000-4000-8000-000000000080",
  "asset_id": "example-chair",
  "relevance": true,
  "created_at": "2026-11-07T00:00:00Z",
  "storage": "postgresql",
  "mock": false
}
```

Đây là ví dụ cấu trúc. ID và thời điểm trong response thực do DB/application cấp.
Schema cùng request/response examples ở [OpenAPI feedback](../openapi-feedback.json).

## Gửi lại và đổi đánh giá

- Mỗi request hợp lệ tạo một row mới với feedback ID mới.
- Gửi lại cùng event/asset/relevance tiếp tục tạo row mới.
- Đổi true sang false hoặc ngược lại ghi thêm phản hồi, giữ lịch sử trước đó.
- Không có idempotency key hoặc nhận diện người gửi trong contract hiện tại.
  Retry sau mất response có thể tạo thêm một row dù request trước đã commit.
- UI chỉ báo lưu thành công sau response 201 và có thể giữ lựa chọn để retry lỗi.

## Event và asset

Event mới của text/image search lưu `result_asset_ids` gồm đúng trang kết quả
đã trả, cùng query/filters và versions gốc. Các trang/retry search tạo event riêng.
Feedback tham chiếu event đó qua khóa ngoại; versions được truy vết từ event.
Asset ngoài trang trả về bị từ chối, kể cả nó có trong cửa sổ 200 ứng viên.

Migration `0002` giữ event cũ với `result_asset_ids=NULL`. Backend yêu cầu tìm
kiếm lại để tạo event có snapshot trước khi nhận feedback. Trang rỗng dùng
`[]`, nên không có asset hợp lệ để đánh giá cho event đó.

| HTTP | error.code | Khi nào |
| --- | --- | --- |
| 400 | `INVALID_REQUEST` | Payload/UUID/Boolean/asset ID không hợp lệ |
| 400 | `EVENT_ASSET_MISMATCH` | Asset tồn tại nhưng ngoài trang kết quả của event |
| 400 | `SEARCH_EVENT_RESULTS_UNAVAILABLE` | Event cũ chưa có snapshot, cần tìm kiếm lại |
| 404 | `SEARCH_EVENT_NOT_FOUND` | UUID hợp lệ nhưng event không tồn tại |
| 404 | `ASSET_NOT_FOUND` | Event tồn tại nhưng asset không tồn tại |
| 500 | `INTERNAL_ERROR` | Đọc/ghi DB thất bại, transaction rollback |

Envelope giữ `error.code/message/details`. Khi đồng thời thiếu event và asset,
backend kiểm event trước. Error nội bộ dùng thông báo cố định.

## Bàn giao Duy

- Payload và append semantics kế thừa contract cũ; response mới dùng UUID,
  `storage=postgresql`, `mock=false`.
- Dùng đúng cặp event ID và asset ID từ cùng response search. Khi đổi trang hoặc
  retry search thành công, gắn feedback với event mới của response đó.
- Với `SEARCH_EVENT_RESULTS_UNAVAILABLE`, hướng dẫn tìm kiếm lại. Với lỗi
  500/mạng, cho phép retry và lưu ý quy tắc tạo row mới.
- Chờ Duy xác nhận contract PostgreSQL và triển khai client/UI; image/text
  feedback E2E được ghi bằng chứng riêng sau khi giao diện sẵn sàng.
