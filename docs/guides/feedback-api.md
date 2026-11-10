# Lưu feedback — #81

API kiểm tra event/asset trong PostgreSQL, xác nhận asset thuộc đúng trang kết
quả đã lưu, rồi flush/validate response và commit feedback trước HTTP 201.
Mỗi request dùng session riêng. Gửi lại/đổi đánh giá tạo phản hồi mới theo
[contract feedback W4](../contracts/feedback-w4.md).

## Migration và cấu hình

Từ backend, sau khi cấu hình kết nối DB local:

```powershell
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic check
```

Migration `0002_search_event_results.py` bổ sung JSONB nullable
`search_events.result_asset_ids` và check constraint dạng array. Event mới lưu
IDs của đúng trang trả về. Dữ liệu event/feedback đã có được giữ lại, event cũ
chưa biết snapshot dùng NULL và trả 400 khi gửi feedback mới, yêu cầu search lại.

Migration đã được kiểm chứng upgrade từ DB test ở revision 0001 có dữ liệu,
upgrade DB test mới và downgrade/upgrade round trip. Lượt triển khai này áp dụng
migration trên DB test riêng; database phát triển cần chạy lệnh trên trước bật API.

Downgrade về `0001` bỏ cột snapshot. Các row feedback/event vẫn còn; sau upgrade
lại, event chưa có snapshot cần search lại để nhận feedback mới. Khi rollback
code, dùng revision tương ứng với code đang chạy.

Đặt trong `.env` ở gốc repo:

```dotenv
APP_FEEDBACK_SOURCE=database
```

Để tạo event thật, bật text/image service theo hướng dẫn
[text search](text-search-api.md) và [image search](image-search-api.md).
Production có route feedback khi chọn database. Chế độ mock tiếp tục được chọn
bằng `APP_FEEDBACK_SOURCE=mock` trong môi trường phát triển.

Từ backend chạy `python -m uvicorn app.main:app`; Swagger tại `/docs`.
Spec bàn giao đủ ba API thật ở `docs/openapi-feedback.json`. Các spec mock,
text và image vẫn được xuất theo cấu hình tương ứng.

## Kiểm thử và dữ liệu riêng

Unit tests:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit -q
```

Tests PostgreSQL cần `TEST_DATABASE_URL` dùng driver `postgresql+psycopg`
và database riêng tên `test_*`. Chạy từ gốc repo:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_feedback_stack.py backend/tests/integration/test_database.py backend/tests/integration/test_search_events.py backend/tests/integration/test_text_search_stack.py backend/tests/integration/test_image_search_stack.py -q
```

Tests tích hợp dùng retrieval fixture để kiểm transaction, event text/image,
asset ngoài trang, unknown IDs, event cũ, append/retry/đổi đánh giá, concurrency,
rollback/phục hồi và đóng session. Test migration giữ dữ liệu 0001 trước upgrade.

Verifier HTTP dùng CLIP thật, PostgreSQL và hai index text/image đã có. Từ gốc
repo với cùng TEST_DATABASE_URL, thay đường dẫn bằng bộ index trên máy kiểm tra:

```powershell
backend\.venv\Scripts\python.exe scripts/verify_feedback_api.py --index-manifest data/processed/issue65/index-1718ec3c49a0/index-manifest.json --index-root data/processed/issue65/index-1718ec3c49a0 --qdrant-local-path data/processed/issue65/index-1718ec3c49a0/qdrant --image-index-manifest data/processed/issue76/clip-build-16556914413d/index-manifest.json --image-index-root data/processed/issue80/inputs-cfd29f05b4 --image-qdrant-local-path data/processed/issue76/clip-build-16556914413d/qdrant --output data/processed/issue81/http-verification.json
```

Verifier tái sử dụng smoke #65/#80, rồi gửi feedback trên cả event text và image
đã tạo. Nó đọc row feedback/event từ session khác để xác minh commit và versions,
kiểm asset ngoài trang, lỗi 400/404/500 và phục hồi sau lỗi ghi. Hash ảnh trong
event là SHA-256 của bytes gốc; ảnh query là preview đã có trong index để diagnostic.

Verifier tạo và dọn schema tạm trong DB test đã cấp, dừng Uvicorn và đóng Qdrant.
Point count/fingerprint persisted được so sánh sau đóng/mở lại storage. Gói ảnh/
index/weights và raw reports nằm ngoài Git. Chạy lại bước index/input theo
hướng dẫn #80 nếu máy chưa có bộ local này.

## Bằng chứng và review

Kết quả local ở [bằng chứng #81](../evidence/issue81-feedback-http.json).
Chi tiết môi trường/model/index/config/dataset và query/event/feedback IDs được
ghi trong JSON. Duy review contract và tiếp nhận API để xây UI. Khuê review
migration/tests và kiểm chứng UI sau khi client sẵn sàng. CI và approvals cập
nhật theo trạng thái GitHub thực tế khi mở PR.

Kết quả local ngày 07/11/2026:

- 660 unit tests đạt, 182,16 giây.
- 45 tests API/PostgreSQL chọn lọc đạt, 64,13 giây, gồm tests unit API và
  integration với retrieval fixture.
- HTTP thật dùng CLIP và hai index 354 point: feedback trên text/image events,
  gửi lại và đổi đánh giá đã commit 7 row; versions truy vết đúng qua event.
- Asset ngoài trang, ID thiếu, Boolean sai và event cũ được từ chối đúng mã.
  Lỗi ghi DB rollback và request sau phục hồi trả 201.
- Revision 0002 được áp dụng trong schema test, upgrade giữ row cũ và
  downgrade/upgrade round trip đã qua kiểm tra. Database phát triển chưa nâng
  migration trong lượt này.
- Fingerprint persisted và point count của cả hai index giữ nguyên.
  Server dừng và database/schema test được dọn sau lượt chạy.
