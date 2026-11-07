# W4 — Contract upload ảnh (#79)

`POST /api/v1/search/image` nhận `multipart/form-data`.

| Trường | Kiểu | Quy tắc |
| --- | --- | --- |
| `image` | File, bắt buộc | JPEG hoặc PNG theo nội dung, tối đa 5 MiB và 4096 px mỗi chiều, giải mã được |
| `filters` | Chuỗi JSON | Object theo schema filters hiện có, mặc định `{}` |
| `page` | Số nguyên | Từ 1, mặc định 1 |
| `limit` | Số nguyên | Từ 1 đến 50, mặc định 12 |

Ví dụ thử bằng PowerShell với API bật mock và một file ảnh local:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/search/image -F 'image=@preview.png' -F 'page=1' -F 'limit=12'
```

Frontend dùng `FormData`, thêm ảnh vào `image` và thêm
`JSON.stringify(filters)` vào `filters` nếu có. Trình duyệt tự đặt multipart
boundary. Chế độ mặc định trả `SearchResponse` với `mock: true` và kết quả fixture.
Chế độ `APP_IMAGE_SEARCH_SOURCE=service` của #80 dùng
[contract HTTP ảnh thật](../guides/image-search-api.md).
Xem [ví dụ request/response trong OpenAPI](../openapi.json).

| HTTP | `error.code` | Khi nào |
| --- | --- | --- |
| 400 | `INVALID_REQUEST` | Thiếu file hoặc phân trang không hợp lệ |
| 400 | `INVALID_FILTERS` | JSON hoặc dữ liệu filters sai |
| 400 | `IMAGE_TOO_LARGE` | File lớn hơn 5 MiB |
| 400 | `IMAGE_DIMENSIONS_EXCEEDED` | Chiều ảnh vượt 4096 px |
| 400 | `UNSUPPORTED_IMAGE` | Nhận diện được định dạng khác JPEG/PNG |
| 400 | `INVALID_IMAGE` | Nội dung hỏng hoặc Pillow không thể giải mã an toàn |

Giới hạn dung lượng áp dụng cho file ảnh, không phải toàn bộ multipart body.
Backend đọc tối đa 5 MiB + 1 byte từ file đã được multipart parser tiếp nhận.

## Bàn giao

- Duy: giữ trường multipart và giới hạn đang dùng ở PR #68. Dùng bảng lỗi
  trên để đối chiếu UI. Chờ xác nhận contract/error mapping.
- Chi: helper `read_validated_image` trả bytes gốc của JPEG/PNG đã kiểm tra
  và giải mã thử. Đề xuất #80 nhận bytes này ở biên API rồi chuyển đổi theo
  interface/preprocessing được bàn giao ở #76. Chờ Chi xác nhận interface.
- #80 phụ trách retrieval thật và lưu search event PostgreSQL cho truy vấn ảnh.
