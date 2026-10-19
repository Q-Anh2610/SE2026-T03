# PostgreSQL, ORM models và Alembic - Issue #8

Quỳnh Anh phụ trách. Schema dưới đây phục vụ persistence. API mock của Issue #9
đã có nhưng chưa kết nối các bảng này; feedback mock vẫn lưu RAM. Chưa chốt
thay đổi contract frontend và không tạo index Qdrant.

## Cấu hình và khởi chạy

Từ gốc repository, tạo `.env` từ `.env.example` nếu chưa có. Nếu đã có `.env`,
bổ sung những khóa `POSTGRES_*` còn thiếu theo mẫu, giữ cấu hình khác của bạn.
Đổi `POSTGRES_PASSWORD` mẫu thành mật khẩu local riêng, không commit `.env`.

```powershell
docker compose -f docker-compose.yml up -d --wait postgres
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m app.db.seed
```

Mong đợi revision `0001`, không có schema drift và seed thêm 7 bản ghi lần đầu,
0 bản ghi lần sau. Các lệnh Alembic trên chạy từ `backend/`; từ gốc repo có thể dùng
`backend/.venv/Scripts/python.exe -m alembic -c backend/alembic.ini upgrade head`.

| Biến | Ý nghĩa |
|---|---|
| `POSTGRES_HOST` | Host cho Python local, mặc định localhost |
| `POSTGRES_PORT` | Cổng local/publish Compose, mặc định 5432 |
| `POSTGRES_DB` | Database, mặc định semantic_search |
| `POSTGRES_USER` | User local, mặc định semantic |
| `POSTGRES_PASSWORD` | Mật khẩu bắt buộc khi dùng DB; được che trong Settings repr |
| `DATABASE_URL` | Tùy chọn ưu tiên cao nhất, phải có driver postgresql+psycopg |

Trong container backend, Compose tự đặt host `postgres` và port `5432`.
`DATABASE_URL` nếu khai báo sẽ ưu tiên hơn các biến thành phần; URL dùng trong
container phải trỏ được tới DB từ container, không dùng localhost của máy Windows.
Ưu tiên các biến thành phần để URL.create xử lý đúng ký tự đặc biệt của mật khẩu.

PostgreSQL dùng volume `postgres_data` của project Compose, độc lập các container
PostgreSQL khác. Đổi password trong `.env` sau khi volume đã khởi tạo không tự đổi
password trong DB; cần thao tác quản trị có chủ đích. Không dùng `down -v` để xử lý
lỗi kết nối vì thao tác đó xóa dữ liệu.

## Chạy migration và seed trong container

Từ gốc repository, build lại backend để image có Alembic và driver mới:

```powershell
docker compose -f docker-compose.yml up --build -d --wait backend
docker compose -f docker-compose.yml exec backend python -m alembic upgrade head
docker compose -f docker-compose.yml exec backend python -m alembic check
docker compose -f docker-compose.yml exec backend python -m app.db.seed
```

Migration và seed là lệnh riêng, không tự chạy khi Uvicorn khởi động.
`GET /healthz` giữ nguyên liveness, không thay bằng DB readiness.

## Schema

### assets

- `asset_id`: PK chuỗi tối đa 128 ký tự; `source` và `source_id` bắt buộc,
  unique theo cặp để không nhập trùng cùng nguồn.
- Đủ các trường issue: source_url, author, license, name, description, tags,
  category, thumbnail_path, model_path, face_count, checksum, ingestion_status,
  created_at và updated_at.
- Bổ sung `formats`, `model_version`, `index_version` theo schema tối thiểu trong
  ROADMAP; không tạo thêm bảng cho tính năng chưa được giao.
- Metadata chưa biết để null. tags/formats là PostgreSQL text[], mặc định mảng
  rỗng, hỗ trợ thay đổi tại chỗ qua MutableList. Mảng rỗng nghĩa chưa có giá trị
  được ghi nhận, không phải bằng chứng asset không có thuộc tính đó.
- face_count là BIGINT, cho phép null hoặc số không âm. Ý nghĩa mặt/tam giác cần
  thống nhất với Huyền/Chi theo nguồn; DB không suy đoán từ ảnh.
- checksum là chuỗi tối đa 64 ký tự. Seed dùng SHA-256 của fixture tự tạo, không
  giả là checksum file mesh thật.
- ingestion_status là chuỗi, mặc định pending; chưa ép danh sách trạng thái cố
  định để không tự chốt workflow ingestion của Huyền.
- Timestamp có timezone, created_at/updated_at mặc định giờ DB. updated_at tự cập
  nhật khi UPDATE qua SQLAlchemy ORM/Core; SQL thô ngoài ORM phải tự đặt timestamp.
- Có B-tree indexes cho category, license và face_count.

### search_events

- PK UUID `search_event_id` được Python sinh khi ORM insert.
- query_type là text/image. Text phải có query_text không rỗng; image phải có
  query_image_ref không rỗng, có thể kèm query_text bổ sung.
- query_image_ref là tham chiếu/hash, không bắt buộc lưu ảnh gốc hoặc quy định
  thời hạn lưu ảnh trong issue này.
- filters là JSONB, default {}, hỗ trợ cập nhật khóa trực tiếp qua MutableDict;
  khi sửa cấu trúc JSON lồng nhau cần gán object mới để ORM nhận diện thay đổi.
- model_version, index_version và config_version bắt buộc để gắn feedback đúng
  phiên bản tìm kiếm; dataset_snapshot tùy chọn, created_at có timezone và index.

### feedbacks

- PK UUID feedback_id, FK search_event_id và asset_id bắt buộc, có indexes.
- relevance là Boolean: true=phù hợp, false=không phù hợp. Đây không phải nhãn
  benchmark 0/1/2.
- FK dùng ON DELETE RESTRICT, không tự xóa lịch sử phản hồi khi xóa asset/event.
- Không tự đặt unique cho cặp event/asset: nhận diện người dùng/phiên, đổi lựa
  chọn và idempotency của feedback API là các quyết định cần chốt ở đầu việc API.
- FK bảo đảm event và asset tồn tại; việc asset có thuộc kết quả truy vấn hay
  không cần nghiệp vụ API kiểm tra khi luồng search/feedback được triển khai.

Schema này cần Huyền/Chi/Duy/Khuê review khi tích hợp theo module; không coi tài
liệu là xác nhận các owner đã approve contract.

## Migration

Alembic nằm tại `backend/alembic`, thay vị trí khung `backend/migrations` ban đầu.
`0001_initial_schema.py` tự chứa định nghĩa schema, không import ORM hiện hành
để tạo bảng. Không dùng metadata.create_all lúc startup và không dùng stamp thay
cho thực thi migration.

Sửa models ở các issue sau thì tạo revision mới, review SQL trước khi chạy:

```powershell
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe schema change"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
```

`downgrade base` của revision đầu xóa ba bảng và dữ liệu trong đó; chỉ kiểm thử
trên database test riêng, không chạy trên database phát triển/chung đang có dữ liệu.

## Seed

`python -m app.db.seed` thêm 7 fixture assets có source=mock, ID mock-asset-001
đến mock-asset-007. Dùng PostgreSQL ON CONFLICT DO NOTHING theo asset_id để chạy
lại không trùng, không ghi đè metadata đã được chỉnh. Giao dịch rollback nếu lỗi.
Seed không tự tạo bảng; cần upgrade trước. License, face_count, đường dẫn mesh và
preview chưa biết giữ null; ingestion_status=pending, không tuyên bố searchable.
Không tạo feedback/search event giả làm bằng chứng người dùng đã tìm kiếm.

## Kiểm thử

Unit tests không cần DB:

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not integration"
```

Integration tests dùng PostgreSQL thật, chỉ nhận `TEST_DATABASE_URL` với tên DB
bắt đầu bằng `test_`, tuyệt đối không fallback sang DATABASE_URL hoặc database
phát triển. Ví dụ tạo database test riêng bằng công cụ quản trị, cấp URL cho
phiên PowerShell (thay credentials bằng giá trị local, không commit chúng):

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/test_semantic_search'
.\.venv\Scripts\python.exe -m pytest
Remove-Item Env:TEST_DATABASE_URL
```

Không đặt URL có mật khẩu thật trong tài liệu/commit; percent-encode ký tự đặc
biệt nếu nhập URL. Mỗi test chạy migration trong transaction và rollback sau test.
Không cấu hình TEST_DATABASE_URL thì các integration tests được báo skipped;
điều đó không phải bằng chứng migration PostgreSQL đã qua.

Tests kiểm tra upgrade/downgrade/upgrade, metadata drift, FK, source dedup,
face_count âm, seed chạy lại, null metadata, mutable array/JSON, timestamps,
text/image query và cả hai lựa chọn feedback.
