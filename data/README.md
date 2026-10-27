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
Pipeline hiện lưu file và báo cáo local; chưa tích hợp persistence PostgreSQL.

### Các module

| File | Trách nhiệm |
|---|---|
| `backend/app/ingestion/source_adapter.py` | Đọc, chuẩn hóa và kiểm tra metadata |
| `backend/app/ingestion/objaverse.py` | Ánh xạ annotation Objaverse sang metadata |
| `backend/app/ingestion/downloader.py` | Tải, kiểm tra ảnh, tính checksum và retry |
| `backend/app/ingestion/cache.py` | Kiểm tra preview local trước khi tái sử dụng |
| `backend/app/ingestion/pipeline.py` | Điều phối batch và tổng hợp kết quả |
| `backend/app/ingestion/cli.py` | Nhận tham số và chạy pipeline từ terminal |

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

Pipeline preview local không cần Docker hoặc PostgreSQL.
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
| `succeeded` | Số asset tải và kiểm tra preview thành công trong lần chạy |
| `failed` | Số bản ghi thất bại |
| `skipped` | Số asset tái sử dụng preview local hợp lệ |

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

`skipped` là kết quả của lần chạy, không phải trạng thái DB đã thống nhất.

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

### Bằng chứng kiểm chứng local

Kết quả đã ghi nhận trong quá trình triển khai:

- Bộ tests ingestion: 133 passed.
- Đã xử lý toàn manifest 200 asset.
- Đã đối chiếu SHA-256 preview: 200/200 asset khớp.
- Lần chạy lại: input_count=200, succeeded=0, failed=0, skipped=200.
- Báo cáo local lần chạy lại:
  `data/processed/ingestion/run-200-repeat.json`.

Báo cáo runtime và preview không được commit.
Kết quả trên là bằng chứng local, không thay thế trạng thái CI
hoặc kiểm chứng PostgreSQL.

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

- Persistence hiện là `local_files_only`.
- Chưa ghi metadata/trạng thái vào PostgreSQL.
- Chưa kiểm chứng chạy lại không tạo bản ghi PostgreSQL trùng.
- Cần thống nhất ingestion status, ý nghĩa checksum và thumbnail_path
  với Vũ Nguyễn Quỳnh Anh (@Q-Anh2610).
- API hiện chưa phục vụ file preview local; cần phối hợp
  Vũ Nguyễn Quỳnh Anh (@Q-Anh2610) và Nguyễn Văn Duy (@nvndy27) để tích hợp.
- Chưa tạo embedding hoặc index Qdrant.
- Không đánh dấu asset searchable trước khi index thành công.
- Chưa coi toàn bộ Issue #41 hoàn thành khi phần PostgreSQL
  và các tiêu chí tích hợp còn chưa được kiểm chứng.