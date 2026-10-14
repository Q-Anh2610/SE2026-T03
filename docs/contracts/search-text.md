# Contract nháp: tìm kiếm văn bản W1

Trạng thái: **đề xuất cho mock frontend của Issue [#6](https://github.com/Q-Anh2610/SE2026-T03/issues/6)**. Nguyễn Văn Duy triển khai mock; Vũ Nguyễn Quỳnh Anh cần review trước khi chốt schema/OpenAPI backend. Chưa có endpoint backend, encoder hoặc index thật. Contract này không thay thế OpenAPI khi backend được triển khai.

## Request

Đề xuất `POST /api/v1/search/text`, `Content-Type: application/json`:

```json
{
  "query": "ghế gỗ",
  "filters": {},
  "limit": 12
}
```

| Trường | Quy ước nháp |
|---|---|
| `query` | Chuỗi được trim, 1–500 ký tự; giới hạn tính bằng Unicode code points. |
| `filters` | Object, W1 chỉ chấp nhận `{}`; UI filters thuộc W2/W4, chưa chốt schema. Không bỏ qua filter không hỗ trợ. |
| `limit` | Số nguyên 1–50; UI W1 cho chọn 6, 12 hoặc 24, mặc định 12. |

## Response thành công

HTTP 200, gồm `query_id`, `search_event_id`, `query` đã chuẩn hóa, `results`, `versions`.

```json
{
  "query_id": "mock-query-example",
  "search_event_id": "mock-event-example",
  "query": "ghế gỗ",
  "results": [
    {
      "rank": 1,
      "asset": {
        "asset_id": "mock-chair-01",
        "name": "Ghế gỗ đơn giản",
        "description": "Bản ghi minh họa tự tạo cho giao diện tuần 1.",
        "category": "Nội thất",
        "tags": ["ghế", "gỗ", "chair", "wood"],
        "formats": ["glb"],
        "face_count": null,
        "thumbnail_url": null,
        "source": "fixture",
        "source_url": null,
        "author": null,
        "license": null
      },
      "retrieval_sources": ["mock_metadata"],
      "explanation": "Minh họa khớp từ khóa trong metadata; chưa chạy semantic search.",
      "score": null
    }
  ],
  "versions": {
    "model_version": "mock-no-encoder",
    "index_version": "mock-w1",
    "config_version": "mock-text-v1"
  }
}
```

- `rank`: số nguyên bắt đầu từ 1, liên tiếp theo thứ tự response. `asset_id` duy nhất; số kết quả không vượt `limit`.
- `name`, `description`, `category`, `source`, IDs và các version là chuỗi; `tags`, `formats`, `retrieval_sources` là mảng chuỗi. `explanation` là chuỗi.
- `author`, `license`, `source_url`, `thumbnail_url`: chuỗi hoặc null; `face_count`: số nguyên không âm hoặc null. Thiếu thuộc tính phải trả null, không bịa dữ liệu. Hai URL nếu có chỉ dùng HTTP(S).
- Mock ghi `source=fixture`, các IDs/versions có tiền tố `mock-`, `score=null`. Đây là metadata minh họa, không có file mesh/preview để tải, không có provenance/license của dataset thật. Tile CSS chỉ là biểu tượng thay thế khi thiếu ảnh.
- `score`: số hữu hạn hoặc null. Backend cần chốt ý nghĩa score theo nguồn retrieval; UI W1 không hiển thị score hoặc phần trăm chính xác.
- `results=[]` là thành công không có kết quả. Không dùng lỗi HTTP cho trường hợp này.
- API client kiểm tra shape, query echo, rank/ID/limit và URL trước khi hiển thị; response sai contract thành trạng thái lỗi.

## Response lỗi đề xuất

HTTP 422 cho request không hợp lệ, 503 khi search chưa sẵn sàng:

```json
{
  "error": {
    "code": "SEARCH_UNAVAILABLE",
    "message": "Dịch vụ tìm kiếm chưa sẵn sàng."
  }
}
```

Client W1 xử lý mọi HTTP không thành công, timeout, lỗi mạng và response hỏng bằng thông báo tiếng Việt cố định phù hợp; không in nội dung lỗi server hoặc request vào logs/UI. Không tự fallback sang mock khi API lỗi.

## Cách dùng mock

`npm run dev`: mock phát triển với độ trễ 450 ms, khớp từ khóa metadata tiếng Việt/Anh trong fixtures tự tạo. Không dùng để đánh giá retrieval. Bộ chọn kịch bản phát triển cho phép thử thành công, rỗng và lỗi; thử lại lỗi chuyển về kịch bản bình thường.

`npm run dev:api` hoặc `VITE_SEARCH_MODE=api npm run dev`: gọi API cùng origin. `npm run build` luôn dùng HTTP API; mock không được bật ở production. `VITE_API_BASE_URL` tùy chọn là HTTP(S) origin backend, không chứa credentials/query/fragment. Mặc định API cùng origin; Vite dev server không cấu hình backend proxy khi chưa có backend. CORS hoặc reverse proxy là phần phối hợp API khi tích hợp.

## Bàn giao cho API

Các file dùng chung cần review: tài liệu này và `frontend/src/features/search/types.ts`. Trước W3, thống nhất schema filters/error, metadata nullability, rank, IDs và versions; cập nhật tài liệu, frontend types, mock và OpenAPI/schema backend trong cùng thay đổi contract đã được chốt.
