# Đối chiếu frontend–backend: Issue #9

Frontend triển khai theo backend PR [#24](https://github.com/Q-Anh2610/SE2026-T03/pull/24),
commit `575cee46150c76c34d1b080d099654ae07fb09fd`.
[Contract backend và OpenAPI](https://github.com/Q-Anh2610/SE2026-T03/blob/575cee46150c76c34d1b080d099654ae07fb09fd/docs/contracts/api-v1.md)
là nguồn đối chiếu. Các lựa chọn dưới đây đã được triển khai/kiểm thử từ phía frontend;
**còn chờ Quỳnh Anh và reviewer xác nhận**, không thay thế approval của nhóm.

| Nội dung | Quy ước triển khai |
|---|---|
| Text | JSON `query`, `filters`, `page`, `limit`; query trim 1–500 Unicode code points |
| Phân trang | page nguyên >=1, mặc định 1; limit nguyên 1–50, mặc định 12 |
| Response | Giữ `query_id`, `search_event_id`, `query`, `results`, `versions`; bắt buộc `pagination` |
| pagination | `page`, `limit`, `total`, `pages=ceil(total/limit)`, `has_next`; total sau lọc, trước phân trang |
| Trang rỗng | HTTP 200; total=0 thì pages=0; vượt trang cuối trả results=[] |
| Rank | Bắt đầu lại từ 1 mỗi trang; asset ID không trùng trong trang |
| Filters | category/license bằng chính xác; format nằm trong formats; face_count_min/max là số nguyên >=0, bao gồm cận; AND, min<=max |
| Metadata null | Không khớp filter tương ứng; không lọc thì giữ asset thiếu metadata |
| Ảnh | Multipart `image` (file, không nhận URL), `filters` là JSON string, `page`/`limit` là trường form |
| Giới hạn ảnh | JPEG/PNG decode được, <=5 MiB, mỗi chiều <=4096 pixel; backend kiểm tra nội dung |
| Feedback | JSON event ID, asset ID, relevance Boolean nghiêm ngặt; 0/1/chuỗi không hợp lệ |
| Feedback mock | 201, storage=memory; event cùng process và asset thuộc đúng trang kết quả; restart mất feedback |
| Lỗi | JSON `{error:{code,message,details}}`; validation 400, tài nguyên thiếu 404, nội bộ 500 |

Client hiện ánh xạ status sang thông báo tiếng Việt cố định, không đưa nguyên văn lỗi server
hoặc dữ liệu nội bộ lên UI. 422 chỉ được giữ như nhánh tương thích với backend cũ;
contract mới sử dụng 400. Mạng/timeout/HTTP lỗi không tự fallback sang mock.

## Hành vi UI

- Bộ lọc trong disclosure **Bộ lọc** được gửi lên API trước phân trang; bỏ trường trống,
  trim chuỗi, giữ giá trị số 0. Áp dụng bộ lọc/tìm kiếm mới luôn về trang 1.
- Nút Trang trước/sau dùng query, filters và limit của request đã gửi, không dùng bản nhập
  đang sửa. Đổi limit áp dụng ở lần tìm kiếm tiếp theo; retry giữ nguyên request bị lỗi.
- Nhóm danh mục trên kết quả là bộ lọc cục bộ **trong trang đã nhận**, có nhãn phạm vi rõ;
  không thay thế bộ lọc API. Xóa query giữ lựa chọn, reset kết quả rỗng xóa các filters.
- UI upload ảnh và UI feedback chưa được thêm trong thay đổi này. Contract các endpoint
  được kiểm tra trực tiếp bằng HTTP trong bộ tích hợp; không giả thao tác UI đã tồn tại.
- Dữ liệu vẫn là fixture backend, chưa có encoder/index/semantic retrieval thật.

## Kiểm chứng và CI

`frontend/tests/integration/backend.spec.ts` chạy trình duyệt gọi FastAPI thật trên cổng
5196, UI API mode trên 5197; không `route.fulfill` phản hồi backend. Bài lỗi chỉ thay page
trong request để FastAPI tự trả 400. Kiểm tra hai viewport 1280x900 và 390x844.
Ảnh fixture là PNG 2x2 tự tạo, inline; không dùng asset tải ngoài.

Workflow `.github/workflows/frontend-contract.yml` có job lint/typecheck/coverage/build/E2E
và job backend tests + frontend–backend integration. Vì PR #24 chưa merge, job tích hợp
checkout **commit backend cố định** ở trên; không chạy code từ ref PR tùy ý, không dùng
`pull_request_target` hoặc secret. Sau khi backend merge/cập nhật contract, cần cập nhật
commit đối chiếu hoặc chuyển sang backend/ của nhánh tích hợp và chạy lại tests.

Checklist PR/Issue phân biệt kiểm thử local, CI trên GitHub, xác nhận contract, approval
và merge; không tích thay các việc chờ thành viên khác.
