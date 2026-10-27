# Dữ liệu — Trịnh Thị Thu Huyền (@TrinhHuyen05)

Trịnh Thị Thu Huyền (@TrinhHuyen05) chủ trì source reader, manifest và
pipeline ingestion; phối hợp Đoàn Thị Minh Khuê (@doanminhkhue25) về
chất lượng dữ liệu và nhãn benchmark.

## Thư mục dữ liệu

| Thư mục | Nội dung | Đưa vào Git? |
|---|---|---|
| `manifests/` | Asset IDs, metadata, provenance và dataset snapshot manifest | Có, nếu nhỏ và không chứa secret |
| `samples/` | Mẫu nhỏ phục vụ phát triển và kiểm thử, có nguồn/license | Có |
| `benchmark/` | Query, nhãn relevance và split đã xác nhận | Có |
| `raw/` | Dataset, preview và mesh tải về | Không |
| `processed/` | Dữ liệu xử lý và báo cáo pipeline local | Không |
| `models/` | Model weights/checkpoints tải về | Không |
| `runtime/` | Storage local PostgreSQL/Qdrant và dữ liệu runtime | Không |

Các thư mục dữ liệu local được `.gitignore` loại trừ và được tạo khi cần.
Không coi thư mục hoặc mẫu rỗng là dữ liệu đã thu thập.
Không commit dữ liệu thô hàng loạt, model weights, credentials hoặc runtime.

## Bàn giao source reader W1 — Issue #26

Người thực hiện: Trịnh Thị Thu Huyền (@TrinhHuyen05).

`manifests/objaverse_200.json` chứa 200 asset ID duy nhất lấy từ metadata
Objaverse 1.0 trên Hugging Face, revision
`556637099bf4fa79ea7b239d0d9c328b8a2e9ac8`,
shard `000-000` gồm 5.000 annotations.

Bộ manifest này thay manifest cũ chỉ có một bản ghi chưa có bằng chứng nguồn.
ID có dạng `objaverse_<uid>`; không tái sử dụng ID đánh số thứ tự
như `objaverse_001`.

### Các file nguồn

- `objaverse_200.json`: metadata chuẩn hóa của 200 asset.
- `objaverse_200.annotations.json`: annotation nguồn của các asset đã chọn.
- `objaverse_200.provenance.json`: URL/hash shard, hash manifest/annotations,
  thời điểm kiểm tra, hash/kích thước preview, số bản ghi bị loại
  và lỗi preview trong lần thu thập.

### Quy tắc lựa chọn và giới hạn dữ liệu

- Chọn theo UID tăng dần, lọc keyword trong name/category/tags,
  loại age-restricted, yêu cầu license nguồn và preview decode được.
- Đây là lọc tự động, chưa phải review ngữ nghĩa thủ công hoặc
  ground truth benchmark. Asset có thể là cảnh hoặc bộ đồ nội thất.
- Trong lần thu thập W1, 200 preview tải và kiểm tra thành công;
  11 ứng viên lỗi preview bị loại. Preview không lưu vào Git.
- Không tải mesh/model hoặc tạo index trong bước W1.
- Giữ nguyên token license nguồn: `by` (177), `by-nc` (11),
  `by-sa` (8), `by-nc-sa` (4). Không tự gán một phiên bản CC cụ thể.
- Tác giả và URL nguồn nằm trong từng record. Việc sử dụng hoặc
  phân phối tiếp theo phải tuân theo license của từng asset.
- `face_count` giữ giá trị `faceCount` nguồn; chưa xác nhận tương đương
  số tam giác trong file GLB.
- `formats` chỉ lấy archive có type tương ứng, bỏ nhãn `source`.
- Trong snapshot W1, `model_path`, `checksum`, `model_version`
  và `index_version` để null. Hash preview được lưu riêng trong provenance.
- Trạng thái manifest W1 là `PENDING`, chưa searchable.
  PostgreSQL hiện mặc định `pending`; mapping trạng thái khi tích hợp
  cần thống nhất với Vũ Nguyễn Quỳnh Anh (@Q-Anh2610).

### Tái tạo manifest W1

Chạy từ gốc repository sau khi cài dependencies backend:

```powershell
.\backend\.venv\Scripts\python.exe -m scripts.generate_objaverse_200
```

Script dùng Pillow đã có trong dependencies, không cần SDK Objaverse.
Script tải shard metadata chỉ định, cache tại `data/raw/objaverse/`,
kiểm tra tối đa sáu preview đồng thời, giới hạn 2 MiB/ảnh
và 4096 px mỗi chiều. Preview chỉ dùng HTTPS từ `media.sketchfab.com`.

Có thể dùng `--count`, `--output`, `--cache-dir`, `--revision`
và `--shards` để tạo subset khác. Nếu không đủ số asset hợp lệ,
CLI trả mã lỗi và giữ manifest cũ.

Metadata revision đã pin nhưng preview ngoài có thể thay đổi hoặc mất.
Chạy lại script có thể chọn ID khác nếu preview lỗi.
Để triển khai W2 trên snapshot đã bàn giao, dùng manifest hiện có;
không cần chạy lại bước lựa chọn subset.

File JSON dùng LF theo `.gitattributes` để giữ hash ổn định
qua các hệ điều hành.

### Source Adapter

Source Adapter:

- Trim chuỗi, chuẩn hóa tags/formats.
- Kiểm tra trường bắt buộc và kiểu dữ liệu.
- Phát hiện trùng `asset_id` và cặp `(source, source_id)`
  trong một lần gọi.
- Không để bản ghi lỗi chiếm ID của bản ghi hợp lệ phía sau.
- Không truy cập mạng hoặc thực hiện upsert PostgreSQL.

## Pipeline preview W2 — Issue #41

Người thực hiện: Trịnh Thị Thu Huyền (@TrinhHuyen05).

Phát triển từ Source Adapter và manifest W1 để xử lý preview theo batch.
Pipeline lưu preview và báo cáo local, đồng thời hỗ trợ ghi metadata vào
PostgreSQL bằng `--persist-db`. Đã kiểm chứng nhập và chạy lại 200 asset
trên PostgreSQL local; các quyết định tích hợp vẫn cần owner review.

### Các module

| File | Trách nhiệm |
|---|---|
| `backend/app/ingestion/source_adapter.py` | Đọc, chuẩn hóa và kiểm tra metadata |
| `backend/app/ingestion/objaverse.py` | Ánh xạ annotation Objaverse sang metadata |
| `backend/app/ingestion/downloader.py` | Tải, kiểm tra ảnh, tính checksum và retry |
| `backend/app/ingestion/cache.py` | Kiểm tra preview local trước khi tái sử dụng |
| `backend/app/ingestion/pipeline.py` | Điều phối batch và tổng hợp kết quả |
| `backend/app/ingestion/cli.py` | Nhận tham số và chạy pipeline từ terminal |
| `backend/app/ingestion/repository.py` | Upsert metadata, kiểm tra định danh và bảo vệ asset đã index |
| `backend/app/ingestion/db_writer.py` | Quản lý kết nối và transaction PostgreSQL cho từng asset |

### Chuẩn bị môi trường

Chạy từ gốc repository trên Windows PowerShell.

Nếu chưa có môi trường Python:

```powershell
py -3.13 -m venv backend/.venv
```

Cài dependencies:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
```

Chế độ preview local không cần Docker hoặc PostgreSQL.
Chế độ `--persist-db` cần PostgreSQL đang chạy và cấu hình kết nối hợp lệ.
Có thể dùng PostgreSQL cài trực tiếp trên Windows; không bắt buộc Docker Desktop.
Cần kết nối Internet khi tải preview mới.

### Xem tham số CLI

```powershell
.\backend\.venv\Scripts\python.exe -m backend.app.ingestion.cli --help
```

| Tham số | Ý nghĩa |
|---|---|
| `--manifest` | Manifest đầu vào; mặc định là manifest 200 asset |
| `--output-dir` | Thư mục lưu preview |
| `--report` | File báo cáo đầu ra; bắt buộc và phải chưa tồn tại |
| `--previous-report` | Báo cáo cũ dùng để kiểm tra và tái sử dụng preview |
| `--max-attempts` | Tổng số lần tải tối đa mỗi asset, bao gồm lần đầu; mặc định 3 |
| `--limit` | Chỉ xử lý số bản ghi đầu được chỉ định; bỏ qua để xử lý toàn manifest |
| `--persist-db` | Ghi metadata vào PostgreSQL theo cấu hình hiện tại; mặc định tắt |

### Chạy thử 5 asset

```powershell
.\backend\.venv\Scripts\python.exe -m backend.app.ingestion.cli `
  --manifest data/manifests/objaverse_200.json `
  --output-dir data/raw/objaverse/previews `
  --report data/processed/ingestion/example-005.json `
  --max-attempts 3 `
  --limit 5
```

### Chạy toàn bộ 200 asset

```powershell
.\backend\.venv\Scripts\python.exe -m backend.app.ingestion.cli `
  --manifest data/manifests/objaverse_200.json `
  --output-dir data/raw/objaverse/previews `
  --report data/processed/ingestion/example-200.json `
  --max-attempts 3
```

Không truyền `--limit` để xử lý toàn bộ manifest.
CLI hiện in tổng kết sau khi batch hoàn tất.

Mỗi lần chạy dùng tên báo cáo mới. Nếu file báo cáo đã tồn tại,
CLI từ chối ghi đè.

### Chạy lại và tái sử dụng preview

Sau khi chạy ví dụ toàn bộ 200 asset ở trên:

```powershell
.\backend\.venv\Scripts\python.exe -m backend.app.ingestion.cli `
  --manifest data/manifests/objaverse_200.json `
  --output-dir data/raw/objaverse/previews `
  --report data/processed/ingestion/example-200-repeat.json `
  --previous-report data/processed/ingestion/example-200.json `
  --max-attempts 3
```

Pipeline chỉ bỏ qua tải khi:

- Báo cáo trước có trạng thái `downloaded` hoặc `skipped`.
- `asset_id`, `source`, `source_id` và URL preview nguồn khớp.
- File nằm trong thư mục output được chỉ định.
- Dung lượng hợp lệ, SHA-256 khớp và ảnh vẫn decode được.

File thiếu, hỏng hoặc checksum không khớp sẽ được tải lại.
Asset lỗi ở lần trước được thử xử lý lại.

Nếu không truyền `--previous-report`, pipeline không sử dụng
báo cáo cũ để bỏ qua tải.

### Ghi metadata vào PostgreSQL

Chạy các lệnh từ gốc repository. Tạo `.env` nếu chưa có:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Mở `.env` và sửa các giá trị theo database local. Đây là nội dung file,
không phải lệnh PowerShell:

```dotenv
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=semantic_search
POSTGRES_USER=semantic
POSTGRES_PASSWORD="REPLACE_WITH_YOUR_LOCAL_PASSWORD"
```

Thay mật khẩu mẫu bằng mật khẩu của role `semantic`. Role và database
phải được tạo trước bằng tài khoản PostgreSQL có quyền phù hợp.
Giữ nguyên các cấu hình ứng dụng khác, không ghi đè `.env` đang dùng.
`DATABASE_URL` nếu được cấu hình sẽ ưu tiên hơn các biến `POSTGRES_*`;
comment biến đó nếu muốn sử dụng cấu hình thành phần phía trên.
Không commit `.env` hoặc chia sẻ mật khẩu.

Áp dụng và kiểm tra migration:

```powershell
.\backend\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\backend\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini current
.\backend\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check
```

Chỉ áp dụng migration trên database local đã xác nhận đúng cấu hình.
Không cần chạy seed để nhập Objaverse; seed tạo fixture riêng.

Sau khi có báo cáo local `example-200-repeat.json` từ các ví dụ trên:

```powershell
.\backend\.venv\Scripts\python.exe -m backend.app.ingestion.cli `
  --manifest data/manifests/objaverse_200.json `
  --output-dir data/raw/objaverse/previews `
  --report data/processed/ingestion/example-db-200.json `
  --previous-report data/processed/ingestion/example-200-repeat.json `
  --max-attempts 3 `
  --persist-db
```

Chạy lại có ghi DB:

```powershell
.\backend\.venv\Scripts\python.exe -m backend.app.ingestion.cli `
  --manifest data/manifests/objaverse_200.json `
  --output-dir data/raw/objaverse/previews `
  --report data/processed/ingestion/example-db-200-repeat.json `
  --previous-report data/processed/ingestion/example-db-200.json `
  --max-attempts 3 `
  --persist-db
```

Thay đường dẫn báo cáo trước bằng báo cáo thực tế đang có nếu dùng tên khác.
Mỗi báo cáo đầu ra phải dùng tên mới.

Quy tắc persistence hiện tại:

- Không truyền `--persist-db`: chỉ xử lý file và báo cáo local.
- Có `--persist-db`: ghi cả asset vừa tải và asset tái sử dụng preview.
- Mỗi asset có transaction riêng; commit thành công mới ghi `database_status=saved`.
- Upsert theo `asset_id`; database bảo vệ unique theo `(source, source_id)`.
- Từ chối đổi định danh hoặc tự cập nhật asset đã có `index_version`.
- Asset ghi thành công có `ingestion_status=downloaded` theo quy ước triển khai
  hiện tại, còn chờ review contract từ Vũ Nguyễn Quỳnh Anh (@Q-Anh2610).
- `thumbnail_path` trong DB giữ URL preview nguồn; đường dẫn local và checksum
  preview nằm riêng trong báo cáo.
- Không ghi checksum preview đè lên `assets.checksum` và không ghi đè
  `model_path`, `model_version`, `index_version`.
- Lỗi ghi DB rollback transaction asset đó, ghi `stage=persistence`
  và tiếp tục asset kế tiếp. Báo cáo không đưa SQL hoặc credentials từ lỗi DB ra ngoài.
- Chưa lưu lịch sử lỗi/retry theo asset vào bảng PostgreSQL riêng.

Để đối chiếu trên database, có thể chạy các câu SQL sau bằng psql hoặc pgAdmin:

```sql
SELECT COUNT(*) AS total,
       COUNT(DISTINCT asset_id) AS unique_ids,
       COUNT(DISTINCT (source, source_id)) AS unique_sources
FROM assets
WHERE source = 'objaverse';

SELECT ingestion_status, COUNT(*)
FROM assets
WHERE source = 'objaverse'
GROUP BY ingestion_status;
```

Trong lần kiểm chứng với riêng bộ 200 asset này, cả ba số đếm đều là 200,
và trạng thái `downloaded` có 200 bản ghi sau khi chạy lại.

### Kiểm tra preview và checksum

- Chỉ chấp nhận URL HTTPS từ `media.sketchfab.com`.
- Timeout tải mỗi lần là 15 giây.
- Dung lượng tối đa 2 MiB/ảnh.
- Kích thước tối đa 4096 px mỗi chiều.
- Định dạng JPEG, PNG hoặc WEBP.
- Kiểm tra nội dung bằng Pillow, không chỉ dựa vào đuôi file.
- Kiểm tra ảnh trước khi ghi file cuối.
- Tên file dựa trên SHA-256 và định dạng ảnh decode được.

Checksum W2 được tính trên bytes preview đã lưu.
Báo cáo ghi `checksum_resource=preview`.
Không dùng giá trị này để khẳng định đã kiểm tra checksum model 3D.

URL nguồn và đường dẫn file local được lưu thành hai trường riêng:
`preview_source_url` và `preview_local_path`.

Pipeline không resize/crop preview cho encoder và không tự suy đoán
metadata còn thiếu. Tiền xử lý cho CLIP thuộc phần embedding
của Lê Thị Linh Chi (@LLC536).

### Retry và xử lý lỗi

- `max_attempts=3` nghĩa là tối đa ba lần tải, bao gồm lần đầu.
- Retry lỗi kết nối tạm thời, timeout và HTTP
  408, 429, 500, 502, 503, 504.
- Khoảng chờ tăng theo số lần thử.
- Không tự retry ảnh hỏng, metadata không hợp lệ hoặc HTTP 404.
- Lỗi từng asset được ghi vào báo cáo; các asset còn lại tiếp tục xử lý.
- Lỗi đọc manifest hoặc ghi báo cáo khiến lệnh thất bại.
- CLI trả mã thoát 1 nếu batch có bản ghi thất bại.

### Cách đọc báo cáo

Báo cáo gồm thời gian chạy, hash manifest nguồn, cấu hình,
kết quả tổng hợp và danh sách kết quả từng bản ghi.

| Trường tổng hợp | Ý nghĩa |
|---|---|
| `input_count` | Số bản ghi đầu vào được chọn xử lý |
| `succeeded` | Preview tải mới thành công; nếu bật DB thì bước ghi DB cũng thành công |
| `failed` | Số bản ghi lỗi validation, preview hoặc persistence |
| `skipped` | Preview được tái sử dụng; nếu bật DB thì bước ghi DB cũng thành công |

Quy tắc đối chiếu:

```text
input_count = succeeded + failed + skipped
```

Bản ghi trùng bị Source Adapter loại được tính vào nhóm `failed`,
không phải `skipped`.

| Trạng thái kết quả | Ý nghĩa |
|---|---|
| `downloaded` | Preview được tải và kiểm tra thành công |
| `failed` | Bản ghi lỗi; xem stage, error_type và error_message |
| `skipped` | Preview local được kiểm tra và tái sử dụng, attempts=0 |

`skipped` là kết quả tái sử dụng preview trong lần chạy, không phải trạng thái DB.
Khi bật persistence, asset `skipped` vẫn được upsert. Nếu ghi DB thất bại,
`status` chuyển thành `failed`; `preview_status` giữ kết quả xử lý preview.

Báo cáo ghi `persistence=postgresql` khi bật `--persist-db`, ngược lại là
`local_files_only`. `database_status` có giá trị `saved` hoặc `failed`
khi asset đã đi đến bước ghi DB. CLI hiển thị `Database saved` là số asset
đã ghi thành công, gồm cả upsert bản ghi có sẵn; đây không phải số dòng mới.

Xem các bản ghi lỗi bằng PowerShell, thay đường dẫn bằng báo cáo cần đọc:

```powershell
$report = Get-Content data\processed\ingestion\example-200.json -Raw -Encoding UTF8 | ConvertFrom-Json

$report.results |
  Where-Object status -eq "failed" |
  Select-Object asset_id, attempts, error_type, error_message |
  Format-List
```

### Kiểm thử

Chạy từ gốc repository:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/ingestion/ -q
```

Tests downloader, cache, pipeline và CLI dùng ảnh tự tạo, thư mục tạm
và lời gọi giả lập; không tải dataset/model từ Internet.

Phạm vi đã kiểm tra gồm:

- Tải thành công và checksum khớp.
- Ảnh hỏng và giới hạn dung lượng.
- URL ngoài nguồn cho phép.
- Lỗi mạng, retry và giới hạn số lần thử.
- Metadata không hợp lệ và ID trùng trong batch.
- Một asset lỗi không làm dừng các asset còn lại.
- Báo cáo được ghi và manifest nguồn giữ nguyên.
- Tái sử dụng file hợp lệ mà không gọi downloader.
- Cache từ chối file mất, nội dung thay đổi hoặc ảnh hỏng.
- Không tái sử dụng file ngoài output directory.
- CLI truyền đúng tham số, từ chối ghi đè báo cáo và báo mã thoát lỗi.
- CLI chỉ mở DatabaseWriter khi có `--persist-db`.
- Pipeline ghi DB cho cả preview mới và preview tái sử dụng.
- Một lỗi persistence không làm dừng xử lý các asset còn lại.

### Kiểm thử PostgreSQL

Integration tests dùng PostgreSQL thật qua `TEST_DATABASE_URL`.
Database test phải riêng biệt và có tên bắt đầu bằng `test_`, ví dụ
`test_semantic_search`. Không dùng database phát triển `semantic_search`.
Database test cần được tạo trước, với quyền phù hợp cho role chạy tests.

Nhập mật khẩu ẩn để cấu hình cho phiên PowerShell hiện tại:

```powershell
$testPassword = Read-Host "Nhap mat khau cua tai khoan semantic" -AsSecureString
$testCredential = [System.Net.NetworkCredential]::new("", $testPassword)
$encodedTestPassword = [System.Uri]::EscapeDataString($testCredential.Password)
$env:TEST_DATABASE_URL = "postgresql+psycopg://semantic:${encodedTestPassword}@localhost:5432/test_semantic_search"
Remove-Variable testPassword, testCredential, encodedTestPassword
```

Chạy tests tích hợp và dọn biến kết nối:

```powershell
try {
    .\backend\.venv\Scripts\python.exe -m pytest -c backend/pytest.ini backend/tests/integration/ -q
}
finally {
    Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
}
```

Không cấu hình kết nối test thì integration tests có thể bị skip;
skip không phải bằng chứng kiểm chứng DB đạt.

`test_ingestion_repository.py` kiểm tra nhập lại không tăng số record,
cập nhật metadata nhưng giữ trường model, xung đột định danh theo hai chiều
và từ chối ghi đè asset đã index. Tests sử dụng transaction rollback
trên database test qua fixture `migrated_database`.

### Bằng chứng kiểm chứng local

Kết quả đã ghi nhận từ các lần chạy trên máy của Trịnh Thị Thu Huyền (@TrinhHuyen05):

- 138 unit tests ingestion pass.
- 20 integration tests PostgreSQL pass, gồm 5 tests repository ingestion.
- Đã xử lý toàn manifest 200 asset và đối chiếu SHA-256 preview khớp 200/200.
- Chạy lại local: `input_count=200`, `succeeded=0`, `failed=0`, `skipped=200`.
- Đã nhập và chạy lại với PostgreSQL: 200 kết quả `database_status=saved`.
- SQL xác nhận `total=200`, `unique_ids=200`, `unique_sources=200`.
- Cả 200 bản ghi PostgreSQL có `ingestion_status=downloaded`.
- CLI với `--persist-db`: `failed=0`, `skipped=200`, `Database saved: 200`.
- Migration local ở `0001 (head)`; lần kiểm tra schema đã ghi nhận
  `No new upgrade operations detected.`

Báo cáo local đã dùng:

- `data/processed/ingestion/run-200-repeat.json`.
- `data/processed/ingestion/run-db-200-repeat.json`.
- `data/processed/ingestion/run-db-cli-200.json`.

Các số tests là kết quả của hai bộ lệnh riêng; không phải tổng tests toàn backend.
Toàn bộ backend tests đã chạy sau tích hợp: 227 passed, không có test bị skip.
Báo cáo runtime và preview không được commit. Bằng chứng local không thay thế
CI, approval hoặc nghiệm thu toàn bộ Issue #41.

### Bàn giao dữ liệu

Lê Thị Linh Chi (@LLC536) tiếp nhận preview sạch và metadata
để triển khai batch embedding, Qdrant và keyword baseline.

Bộ bàn giao cần gồm:

- Manifest với asset ID ổn định và metadata nguồn.
- URL preview nguồn và đường dẫn preview local.
- File preview tương ứng và SHA-256 preview.
- Thông tin tác giả, nguồn và license.
- Báo cáo asset thành công, lỗi hoặc bị loại.
- Hash manifest nguồn để xác định snapshot.

Đã tạo manifest bàn giao local tại
`data/processed/ingestion/objaverse_200.ready.json` và đối chiếu
checksum preview khớp cho 200/200 asset. Việc này chưa xác nhận
Lê Thị Linh Chi (@LLC536) đã nhận hoặc kiểm thử bộ bàn giao.
Không ghi đè manifest W1.

Khi chuyển dữ liệu, giữ cấu trúc thư mục tương ứng với đường dẫn
trong manifest. Không commit preview hàng loạt.
Tuân thủ license từng asset khi chia sẻ hoặc phân phối dữ liệu.

### Phối hợp tích hợp

| Thành viên | Nội dung phối hợp |
|---|---|
| Trịnh Thị Thu Huyền (@TrinhHuyen05) | Pipeline ingestion, manifest, preview và batch tests |
| Vũ Nguyễn Quỳnh Anh (@Q-Anh2610) | Schema, ingestion status, checksum và persistence PostgreSQL |
| Lê Thị Linh Chi (@LLC536) | Nhận dữ liệu sạch để embedding/index và baseline |
| Nguyễn Văn Duy (@nvndy27) | Cách hiển thị preview qua API và giao diện |
| Đoàn Thị Minh Khuê (@doanminhkhue25) | Chất lượng dữ liệu, nhãn benchmark và kiểm thử tích hợp |

### Giới hạn và việc còn lại

- `downloaded` chỉ xác nhận preview đã xử lý, chưa xác nhận asset searchable.
- Lỗi từng asset và số lần thử hiện lưu trong báo cáo local; chưa có persistence
  riêng cho lịch sử lỗi/retry trong PostgreSQL.
- Quy ước ingestion status, ý nghĩa checksum và thumbnail_path cần được
  Vũ Nguyễn Quỳnh Anh (@Q-Anh2610) review trước khi tích hợp vào nhánh chung.
- Chưa triển khai phục vụ preview local qua HTTP; phối hợp
  Vũ Nguyễn Quỳnh Anh (@Q-Anh2610) và Nguyễn Văn Duy (@nvndy27) khi tích hợp API/UI.
- Chưa tạo embedding hoặc index Qdrant.
- Cần Lê Thị Linh Chi (@LLC536) xác nhận tiếp nhận và dùng được bộ bàn giao.
- Cần kiểm tra CI, review và merge PR sau khi push thay đổi mới nhất.
- Chưa coi toàn bộ Issue #41 hoàn thành khi các tiêu chí còn lại chưa có bằng chứng.
