# Contract nháp W1 (đã có bản đối chiếu Issue #9)

> Khi tích hợp backend PR #24, dùng [đối chiếu frontend–backend v1](frontend-api-v1.md).
> Bản nháp dưới đây giữ làm tham chiếu W1; quy ước filters chỉ `{}`, thiếu pagination
> và lỗi 422 đã được thay bằng filters có kiểu, pagination và validation 400 trong #9.

> Bản W1 bên dưới được giữ để đối chiếu frontend hiện có. Backend mock Issue #9
> triển khai tại [API contract v1](api-v1.md) và `docs/openapi.json`: validation
> dùng 400 thay 422, bổ sung pagination/mock và filters tùy chọn. Các điểm thay đổi
> đang chờ Nguyễn Văn Duy review; phần ghi "chưa có endpoint" bên dưới mô tả thời
> điểm lập nháp W1, không phải trạng thái backend mock hiện tại.

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
- `name`, `source`, IDs và các version là chuỗi; `description` và `category` là chuỗi hoặc null khi thiếu dữ liệu; `tags`, `formats`, `retrieval_sources` là mảng chuỗi. `explanation` là chuỗi.
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

`npm run dev`: mock phát triển với độ trễ 450 ms, khớp từ khóa metadata tiếng Việt/Anh trong fixtures tự tạo. Không dùng để đánh giá retrieval. Giao diện chỉ dùng tìm kiếm thông thường; kịch bản thành công/rỗng/lỗi được kiểm tra trong tests, không có bộ chọn kịch bản trên trang.

`npm run dev:api` hoặc `VITE_SEARCH_MODE=api npm run dev`: gọi API cùng origin. `npm run build` luôn dùng HTTP API; mock không được bật ở production. `VITE_API_BASE_URL` tùy chọn là HTTP(S) origin backend, không chứa credentials/query/fragment. Mặc định API cùng origin; Vite dev server không cấu hình backend proxy khi chưa có backend. CORS hoặc reverse proxy là phần phối hợp API khi tích hợp.

## Bàn giao cho API

Các file dùng chung cần review: tài liệu này và `frontend/src/features/search/types.ts`. Trước W3, thống nhất schema filters/error, metadata nullability, rank, IDs và versions; cập nhật tài liệu, frontend types, mock và OpenAPI/schema backend trong cùng thay đổi contract đã được chốt.

## Quy ước tích hợp frontend

Bản local tái sử dụng DTO/validator/client từ nhánh `feat/6-w1-search-mock` tại SHA `eb003b9855fd0dd242b06a5a55187fc0771d91f1`; DTO/client được tái sử dụng trong bản UI và kiểm thử của cùng Issue #6. Giao diện mới dùng cùng `results`/`versions`, không giữ contract `items` cũ. `frontend/src/types/search.ts` chỉ re-export DTO canonical, không định nghĩa schema thứ hai.

Draft cho phép `description`/`category` null và UI hiển thị “Chưa có thông tin”. Thay đổi này mở rộng DTO/validator, cần Quỳnh Anh đối chiếu khi triển khai OpenAPI; chưa xác nhận backend owner đã review.

Bộ lọc danh mục UI chỉ lọc kết quả đã nhận, không gửi filters tới API và không tìm trong toàn bộ index. Nhãn “Đang lọc” và số hiển thị/tổng kết quả giúp phân biệt phạm vi. Xóa truy vấn giữ danh mục; “Xóa bộ lọc” độc lập; reset ở empty state xóa cả truy vấn/danh mục.

Trạng thái khởi đầu là idle, chưa có request; query trống bị chặn thay vì gửi search. Input HTML giới hạn 1000 UTF-16 code units để nhận tối đa 500 Unicode code points; validator kiểm tra 1–500 code points sau trim.
