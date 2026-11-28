# Chạy và kiểm chứng API — W7 / Issue #145

Contract đầu mối: [API v1](../contracts/api-v1.md). Chọn rõ mục đích trước khi
chạy: fixtures không cần DB/model, Docker mặc định với assets DB, hoặc semantic
service có đầu vào thật. Không dùng kết quả của một mode để nghiệm thu mode khác.

## 1. Docker mặc định: hạ tầng và API phát triển

Theo [README gốc](../../README.md#dựng-toàn-bộ-stack-bằng-docker--w7--issue-148)
và [runbook Docker](docker-clean-setup-w7.md) để tạo .env riêng, chọn project,
build/start/migrate và chạy scripts/verify_docker_stack.ps1. Không ghi đè .env
hoặc dùng volumes/DB chung để thử. Không in `docker compose config` đã nội suy;
dùng `config --quiet`.

Với ports mặc định, mở UI http://127.0.0.1:8080 và Swagger backend
http://127.0.0.1:8000/docs. Assets đọc PostgreSQL, DB mới có thể rỗng; search/
feedback mặc định vẫn mock. Đổi ports trong .env thì thay URLs tương ứng.
Kiểm tra trực tiếp backend từ terminal PowerShell:

```powershell
$apiOrigin = 'http://127.0.0.1:8000'
Invoke-RestMethod "$apiOrigin/healthz"
Invoke-RestMethod "$apiOrigin/api/v1/assets?page=1&limit=12"
$apiSpec = Invoke-RestMethod "$apiOrigin/openapi.json"
$apiSpec.paths.'/api/v1/feedback'.post.responses.'201'.content.'application/json'.schema.'$ref'
```

Mặc định mong đợi health status=ok, assets mock=false/items có thể rỗng,
feedback schema `#/components/schemas/FeedbackResponse`. API không tự seed;
seed fixture không phải asset thật và không tự đưa metadata vào Qdrant.
Không gọi reindex để thử kết nối hoặc tự chạy migration trên DB dùng chung.

### Giới hạn proxy feedback cần theo dõi

Tại base #145 `1a2a86f`, frontend feedback client đọc `/openapi.json` từ cùng
API base trước POST. `frontend/nginx.conf` chỉ proxy `/api/` và `/healthz`;
đường `/openapi.json` rơi vào SPA fallback. Vì vậy không suy ra feedback UI
Docker đã hoạt động từ việc API trực tiếp hoặc hạ tầng healthy. Đối chiếu code
này là bằng chứng tĩnh; lỗi UI thực tế cần ghi nhận bằng smoke riêng.

Cách kiểm tra response của proxy, không gửi feedback hoặc thay DB:

```powershell
curl.exe -i http://127.0.0.1:8080/openapi.json
```

Nếu trả HTML/SPA thay JSON OpenAPI thì client không xác minh được persistence
mode. Bàn giao cho #147/#149 và owner Docker/UI xử lý sau repro/review; #145
không tự sửa nginx hoặc đổi client/contract. Kiểm tra API qua port 8000 ở trên
vẫn là kiểm tra trực tiếp, không phải bằng chứng đã sửa proxy.

## 2. Uvicorn: smoke fixture riêng, không cần DB/model

Prerequisites: Python 3.13 và requirements-dev theo [backend README](../../backend/README.md).
Nếu đã có venv thì dùng lại. Chạy từ backend/ trong **terminal test riêng**:

```powershell
$env:APP_ENV = 'test'
$env:APP_DEBUG = 'false'
$env:APP_MOCK_API_ENABLED = 'true'
$env:APP_ASSET_LIST_SOURCE = 'fixture'
$env:APP_TEXT_SEARCH_SOURCE = 'mock'
$env:APP_IMAGE_SEARCH_SOURCE = 'mock'
$env:APP_FEEDBACK_SOURCE = 'mock'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8015 --no-access-log
```

Cổng 8015 phải trống. Đây là profile fixture tường minh, **khác** exporter mặc
định ở assets DB. Biến tiến trình ưu tiên .env; không sửa .env cho smoke này.
Ở terminal khác, gọi:

```powershell
$apiOrigin = 'http://127.0.0.1:8015'
curl.exe -i "$apiOrigin/healthz"
Invoke-RestMethod "$apiOrigin/api/v1/assets?limit=2"
$searchBody = @{ query = 'chair'; filters = @{}; page = 1; limit = 12 } | ConvertTo-Json
$search = Invoke-RestMethod "$apiOrigin/api/v1/search/text" -Method Post -ContentType 'application/json' -Body $searchBody
$search
$feedbackBody = @{ search_event_id = $search.search_event_id; asset_id = $search.results[0].asset.asset_id; relevance = $true } | ConvertTo-Json
Invoke-RestMethod "$apiOrigin/api/v1/feedback" -Method Post -ContentType 'application/json' -Body $feedbackBody
```

Mong đợi search 200/mock=true, có kết quả fixture; feedback 201/storage=memory/
mock=true. Dùng IDs vừa nhận trong cùng process, không dùng Swagger example
hoặc event từ process đã restart. Curl health có X-Request-ID UUID v4.

Thử ảnh JPEG/PNG của bạn (thay đường dẫn trước khi chạy):

```powershell
curl.exe -i "$apiOrigin/api/v1/search/image" -F 'image=@C:/path/to/preview.png' -F 'page=1' -F 'limit=12'
curl.exe -i "$apiOrigin/api/v1/search/text" -H 'Content-Type: application/json' --data '{}'
curl.exe -i "$apiOrigin/api/v1/not-a-route"
```

Ảnh hợp lệ trả 200/mock=true; body text thiếu query trả 400 INVALID_REQUEST;
route không tồn tại trả 404 HTTP_404. Đối chiếu body error và X-Request-ID,
không chỉ HTTP status. Image filters là chuỗi JSON; browser không tự đặt
Content-Type khi gửi FormData để giữ boundary đúng.

Ctrl+C dừng Uvicorn; đóng terminal test để bỏ các env override. Không dùng
tiếp terminal đó để chạy service thật mà quên phục hồi cấu hình.

### Frontend gọi HTTP backend này

Từ frontend/, terminal riêng:

```powershell
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8015'
npm ci
npm run dev:api
```

Node >=22.12, dùng npm theo lockfile. Giữ localhost/127.0.0.1:5173 để khớp
CORS mặc định; port/origin khác cần APP_CORS_ORIGINS tương ứng trên backend.
`npm run dev` mặc định dùng mock client trong browser; `dev:api` chọn HTTP.
VITE_API_BASE_URL không chứa `/api/v1` và không chứa key/credentials.
Feedback đọc `/openapi.json` từ base 8015 nên không qua nginx ở mục 1.

## 3. Service thật: chuẩn bị đúng metadata/index/cache

Không dùng lệnh fixture ở mục 2 rồi tuyên bố semantic search. Cần metadata
PostgreSQL khớp IDs/filters, migration head, manifests/input hashes, Qdrant
collection đúng phiên bản và model cache đúng pin. Liveness 200 không kiểm
những điều kiện này. Thiếu/mismatch dependency trả 503 hoặc lỗi phù hợp,
không fallback mock.

- [DB/migration](database.md): không tự seed/ghi vào DB đang dùng để thử.
- [Text bootstrap](text-search-api.md) và [image bootstrap](image-search-api.md):
  chọn APP_TEXT_SEARCH_SOURCE=service và APP_IMAGE_SEARCH_SOURCE=service,
  đúng manifest/root/storage/cache. Không tự đổi model/index/config đã khóa.
- [Feedback PostgreSQL](feedback-api.md): APP_FEEDBACK_SOURCE=database, dùng
  event thật từ cùng API/DB; chỉ nhận thành công sau commit.
- [Docker search overlay](docker-clean-setup-w7.md#chế-độ-semantic-search-thật--tùy-chọn-có-đầu-vào):
  server Qdrant cần collection đã được chuẩn bị/đối chiếu riêng; không mount
  storage SQLite local như server snapshot. Không coi overlay là đã smoke thật.
- [Jobs/status](jobs-status-api.md), [reindex](reindex-api.md): admin key riêng,
  profile/output cố định; không dùng để activate index hoặc tự retry job lỗi.

API service hiện là CLIP/cosine. Frozen E5/RRF evaluation/rebuild #135 không tự
đổi default HTTP API. Reproduction benchmark và kiểm binding thuộc owner
search/evaluation, xem [ROADMAP](../../ROADMAP.md); không lấy API smoke thay benchmark.

## 4. Export và hồi quy contract

Từ backend/, exporter không nạp model, không mở lifespan, migrate hoặc seed:

```powershell
.\.venv\Scripts\python.exe -m app.export_openapi
.\.venv\Scripts\python.exe -m pytest tests/unit/test_openapi.py tests/unit/test_openapi_profiles.py tests/unit/test_mock_api.py tests/unit/test_text_search_contract.py tests/unit/test_text_search_api.py tests/unit/test_image_search_api.py tests/unit/test_feedback_api.py tests/unit/test_jobs_api.py tests/unit/test_reindex_api.py tests/unit/test_api_error_envelope.py tests/unit/test_request_logging.py -q
```

Xuất đúng bốn file theo [bảng mode](../contracts/api-v1.md#chọn-đúng-chế-độ-và-openapi).
File đã khớp thì Git có thể không có diff JSON, không sửa để tạo diff giả.
Tests fixture không xác nhận DB/model thực; integration PostgreSQL cần DB test
riêng theo guides hiện có. Swagger runtime phải được lấy từ đúng server/origin.

Bằng chứng #145: [issue145-api-documentation.md](../evidence/issue145-api-documentation.md).
Chờ Duy review mapping client và Khuê review setup/evaluation; không coi tests
local là xác nhận review/CI hoặc nghiệm thu toàn W7.
