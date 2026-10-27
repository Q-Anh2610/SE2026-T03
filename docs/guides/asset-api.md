# Bàn giao list/detail asset — Issues #47 và #48

Kiểm chứng tổng thể: [Migration, lỗi và Frontend/PostgreSQL — Issue #49](asset-api-verification.md).

## Chạy và thử API

Theo [backend README](../../backend/README.md), cấu hình PostgreSQL và chạy migration.
Giữ `APP_ASSET_LIST_SOURCE=database` (mặc định). Có thể dùng seed để thử mà không
cần chờ pipeline 200 asset của Huyền. Từ thư mục `backend/`:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.db.seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Trong terminal khác:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/assets?page=1&limit=2'
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/assets/mock-asset-001'
```

ID trên thuộc seed thử nghiệm; có thể thay bằng asset_id từ response list.
Cả hai API trả `mock=false` vì đọc DB, nhưng bản ghi seed vẫn có `source=mock`.
Điều này không xác nhận asset là dữ liệu thật hoặc đã được index/searchable.

## Quy ước metadata và preview

- List/detail trả cùng metadata cho cùng asset, giữ các key nullable hiện có.
- Tên null/rỗng hiển thị bằng asset_id theo contract #47; tên gốc trong DB không đổi.
- thumbnail_path là HTTP(S) URL không kèm username/password thì ánh xạ sang
  thumbnail_url; thiếu, sai URL hoặc đường dẫn file local thì trả null.
- source_url không phải HTTP(S) hoặc có credentials cũng trả null; nguồn gốc,
  tác giả và license đã có vẫn lấy từ DB, không tự suy đoán thông tin thiếu.
- API không tải thumbnail, không kiểm chứng URL truy cập được và chưa phục vụ
  ảnh local. Frontend giữ fallback khi ảnh thiếu hoặc tải lỗi.
- Asset không có trả 404 `ASSET_NOT_FOUND`; DB lỗi trả 500 `INTERNAL_ERROR`.
  Không tự chuyển sang fixture để che lỗi. Xem [contract](../contracts/api-v1.md).

## Kiểm chứng với Frontend

Chạy `npm run dev:api` trong `frontend/`, đặt `VITE_API_BASE_URL` theo hướng dẫn
Frontend nếu backend khác origin. CORS backend mặc định cho localhost:5173.

1. Chọn **Danh sách asset** để nhận dữ liệu từ PostgreSQL.
2. Thử filters và chuyển trang; mở **Xem chi tiết** ở một asset.
3. Kiểm tra metadata, ảnh hoặc fallback; bấm **Quay lại danh sách**.
4. Kiểm tra filters/page/limit vẫn giữ nguyên.

`APP_ASSET_LIST_SOURCE=fixture` cùng mock bật chỉ dành cho development/test:
list/detail đều dùng cùng fixture, trả `mock=true`; không có DB fallback tự động.
Search/feedback vẫn mock ở chế độ phát triển, chưa ghép với dữ liệu DB.

## Phối hợp còn chờ

- Huyền review ý nghĩa metadata và cách bàn giao thumbnail_path khi pipeline #41
  sẵn sàng; chưa tự thêm endpoint phục vụ file hoặc sửa pipeline ingestion.
- Duy review quy ước preview và kiểm chứng luồng list/detail/quay lại trên UI.
  Tests tự động là bằng chứng kỹ thuật, không phải xác nhận review của Duy.
- Không có migration hoặc dependencies mới trong Issue #48.
