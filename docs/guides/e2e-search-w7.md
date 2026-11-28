# E2E search trên stack thật — Issue #149

Owner E2E: Đoàn Thị Minh Khuê. Phạm vi: text/image search, filters AND,
pagination, detail/quay lại và feedback. Chạy desktop 1280×900 và mobile
390×844 qua frontend production/nginx → FastAPI → PostgreSQL + Qdrant server.
Không chạy admin/reindex, benchmark hoặc thay frozen config W6.

## Điều kiện đầu vào

- Checkout nhánh nhiệm vụ và lưu commit/dirty status thực tế.
- Stack local **riêng**, không dùng DB/index của thành viên khác. Theo
  [runbook Docker](docker-clean-setup-w7.md), chuẩn bị `.env` riêng trong checkout
  test; chọn ports trống, PostgreSQL database tên `test_issue149_*`, password
  local riêng. Không in `.env` hoặc Compose config đã nội suy.
- Backend virtualenv theo requirements đã khóa, Node >=22.12 và dependencies
  frontend theo package-lock; Chrome theo cấu hình Playwright hiện có.
- Gói #87 có `input/source.json`, `input/ready.json`, previews và
  `index/index-manifest.json`, snapshot `home-interior-clear-200-v3`.
  Cache CLIP đúng revision `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`.
  Không cần tải weights/previews hoặc mở Qdrant SQLite reference.

## Chuẩn bị data/index riêng

Từ repo root, sau khi đã cấu hình `.env` của checkout test:

```powershell
rtk proxy docker compose -p issue149-local -f docker-compose.yml up -d --wait postgres qdrant migrate
```

Đặt `TEST_DATABASE_URL` trong terminal bằng URL `postgresql+psycopg` của DB
local **rỗng, đã migrate** ở trên; password cần percent-encode nếu có ký tự
đặc biệt. Không đưa URL này vào logs/report/Git. Thay handoff và port Qdrant
trong lệnh dưới bằng paths/ports thật của lượt chạy:

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
rtk proxy backend/.venv/Scripts/python.exe -B scripts/prepare_w7_e2e.py --handoff <handoff-root> --qdrant-url http://127.0.0.1:6333
```

Script kiểm source/ready/preview checksums và metadata, từ chối DB không phải
local `test_issue149_*` hoặc DB có dữ liệu; encode lại đúng 200 preview bằng
encoder/batch hiện có, tạo collection UUID/version mới rồi nhập metadata vào
DB test. Không tải dữ liệu, sửa metadata nguồn hoặc mở/ghi index reference.
Hai manifest text/image dùng chung vector space CLIP, cutoff 200, có versions
riêng theo từng API. Đây là index riêng cho kiểm thử hành vi API, không activate
index sản phẩm hoặc thay binding benchmark W6/E5/RRF.

Output mới trong `data/runtime/issue149/<run-id>/` gồm:

- `preparation.json`: counts, hashes, packages, commit/dirty status.
- `text-index-manifest.json`, `image-index-manifest.json`, source/ready/previews.
- `suite-input.json`: ảnh/hash, versions mong đợi và filters lấy từ metadata thật.

Script không xóa dữ liệu khi lỗi. Sau lỗi, kiểm output và dùng DB/project mới;
không gọi lại trên DB không rỗng hoặc xóa dữ liệu để che lỗi.

Đặt trong `.env` riêng của checkout test: `SEARCH_HANDOFF_ROOT` bằng output
directory vừa in, `SEARCH_MODEL_CACHE` bằng cache Hugging Face, và hai paths
container `SEARCH_TEXT_MANIFEST=/handoff/text-index-manifest.json`,
`SEARCH_IMAGE_MANIFEST=/handoff/image-index-manifest.json`. Bỏ local-Qdrant
paths/DATABASE_URL host nếu có theo runbook; backend dùng PostgreSQL/Qdrant
server của cùng project.

```powershell
rtk proxy docker compose -p issue149-local -f docker-compose.yml -f docker-compose.search.yml config --quiet
rtk proxy docker compose -p issue149-local -f docker-compose.yml -f docker-compose.search.yml up --build -d --wait --wait-timeout 180
```

## Chạy E2E

Từ `frontend/`, thay paths/port theo lượt chuẩn bị. `E2E_STACK_URL` là origin
frontend nginx, không phải backend trực tiếp. `E2E_STACK_INPUT` là path tuyệt
đối tới `suite-input.json` vừa tạo, không phải manifest benchmark.

```powershell
$env:E2E_STACK_URL = 'http://127.0.0.1:8080'
$env:E2E_STACK_INPUT = '<absolute-run-directory>/suite-input.json'
rtk proxy npm.cmd run test:stack
```

Config không tự dựng server, không fallback fixture, một worker và retries=0.
Thiếu URL/input hoặc checksum ảnh lệch thì fail trước chạy. Suite dùng HTTP
thật qua nginx và đối chiếu response, UI, IDs/rank/dedup/versions, filters,
phân trang và trạng thái sau detail/back. Có ca riêng kiểm `/openapi.json`
và feedback UI text/ảnh; feedback API trực tiếp là ca riêng, không thay thế
feedback UI. Invalid text limit và bytes ảnh hỏng gọi endpoint thật.

## Evidence và bàn giao lỗi

JSON report: `frontend/test-results/stack-report.json`. Failure có screenshot,
trace và error context trong `frontend/test-results/stack/`. Attachment
`stack-http-observations` chỉ ghi path/method/status/content type và body công
khai của search/detail/feedback; không ghi headers, cookies, multipart bytes
hay credentials. Ca API đính kèm `direct-feedback-receipt` để đối chiếu DB.

Đối chiếu search events và feedback receipts với PostgreSQL từ connection mới;
kiểm event/asset IDs, relevance, versions, result IDs và filters. HTTP 201 riêng
lẻ chưa phải kiểm chứng durable persistence. Đối chiếu collection config/count
trước/sau để chứng minh test chỉ query index.

Từ repo root, giữ `TEST_DATABASE_URL` trỏ đúng DB test của lượt chạy; audit chỉ
đọc bằng transaction `READ ONLY`, kiểm receipts/event/result IDs/versions/filters
và Qdrant IDs/count/payload versions. Output phải là file mới:

```powershell
rtk proxy backend/.venv/Scripts/python.exe -B scripts/audit_w7_e2e.py --report frontend/test-results/stack-report.json --input <absolute-run-directory>/suite-input.json --qdrant-url http://127.0.0.1:6333 --output data/runtime/issue149/persistence-new.json
```

`persistence_verified` chỉ xác nhận dữ liệu đã quan sát được lưu đúng, kể cả
khi có ca UI khác thất bại; không đổi verdict E2E sang passed.

Giữ report/trace của lượt lỗi trước khi chạy lại (Playwright có thể thay output),
kiểm log/trace không chứa bí mật trước chia sẻ. Raw output/previews/storage chỉ
ở paths đã ignore, không commit screenshot/trace. Chỉ bàn giao báo cáo gọn và
hashes/bằng chứng đã kiểm tra. Mở trace local:

```powershell
rtk proxy npx.cmd playwright show-trace <path-to-trace.zip>
```

Lỗi selector/timing/harness: sửa trong phạm vi E2E rồi chạy lại phần bị ảnh
hưởng. Lỗi sản phẩm: giữ assertion fail, ghi expected/actual, bước tái hiện,
owner và trạng thái; không skip/xfail, tăng retry hoặc sửa contract để đạt test.
UI/API phối hợp Duy, backend/persistence phối hợp Quỳnh Anh, proxy/Docker phối
hợp Khuê. Tài liệu [API W7](api-reproducibility-w7.md) đã ghi rủi ro proxy
`/openapi.json`; chỉ kết luận lỗi sau khi quan sát runtime.

Kết quả local, lịch sử lỗi và giới hạn: [bằng chứng #149](../evidence/issue149-w7-search-e2e.md).
Chưa đủ luồng chính hoặc còn lỗi blocking thì chưa tích nghiệm thu Issue/M6.
CI/review/merge và việc mở/cập nhật PR là bước riêng theo quyền đã giao.
