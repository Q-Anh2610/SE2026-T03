# W6 — Request ID và logging API (#137)

Contract triển khai local để bàn giao Duy/Khuê review. Response body, error
envelope, search events và idempotency reindex giữ nguyên.

## Header và cách dùng phía frontend

| Thuộc tính | Quy tắc |
|---|---|
| Header response | `X-Request-ID` |
| Định dạng | UUID v4 dạng chuỗi 36 ký tự, server tạo |
| Vòng đời | Mỗi HTTP request có ID mới, gồm cả retry, preflight và lỗi |
| Header client gửi | Không hỗ trợ nhận ID do client chọn; giá trị gửi vào bị bỏ qua, không phản chiếu vào response/log |
| Body response | Không thêm trường hoặc thay đổi cấu trúc hiện có |
| CORS | Giữ origins/methods/allowed headers hiện có; thêm `Access-Control-Expose-Headers: X-Request-ID` |

Frontend đọc `response.headers.get('X-Request-ID')` ở fetch response nhận được,
có thể dùng ID khi báo lỗi/hỗ trợ. Không cần thêm header vào request. Với lỗi
mạng không nhận được response, ID có thể không lấy được; không tự tạo ID rồi
coi là ID backend. Browser gửi X-Request-ID qua preflight chưa được cấp quyền.

Header có trên các response HTTP đi qua app, gồm validation, auth, 404/405,
dependency lỗi và 500. CORS bao ngoài cả error handler để origin hợp lệ có thể
đọc ID trên 500 không dự kiến. Origin ngoài allowlist vẫn không có quyền đọc;
không mở wildcard/credentials. Khi tắt CORS bằng origins rỗng, không tự cấp
quyền cross-origin. OpenAPI/DTO body không đổi; header hạ tầng được quy định ở đây.

**Phân biệt IDs:** X-Request-ID không phải query_id/search_event_id, job_id
hoặc `request_id` trong body reindex. Retry reindex vẫn giữ request_id nghiệp
vụ theo contract cũ, trong khi mỗi lần gửi HTTP có X-Request-ID mới. Không dùng
ID truy vết làm khóa phân quyền, idempotency hoặc bằng chứng transaction đã commit.

## Log có cấu trúc

`app.request` có một handler console JSON riêng (stderr), level INFO, không
propagate qua root để tránh in lặp. Không thay root logger hoặc cấu hình thư
viện khác. Mỗi request phát một record `request.completed` khi ASGI kết thúc.
Các logger lỗi API/DB hiện có phát JSON payload liên kết bằng cùng request ID;
console của chúng có thể có prefix theo formatter root hiện hành.

| Trường | Nội dung |
|---|---|
| timestamp | UTC ISO-8601 |
| level | INFO cho <400; WARNING cho 4xx; ERROR cho 5xx, stream abort hoặc lỗi sau khi gửi response |
| event/component | Loại record và logger/module |
| request_id | UUID của HTTP request; null nếu gọi helper ngoài request |
| method | HTTP method chuẩn; OTHER nếu không thuộc danh sách chuẩn |
| route | Template do router cung cấp, ví dụ `/api/v1/assets/{asset_id}`; `<unmatched>` nếu chưa match |
| status | Status thực sự đã bắt đầu gửi; có thể null ở log giai đoạn trước response |
| duration_ms | Thời gian từ đầu ASGI request đến record; record cuối gồm cleanup/background task, không phải latency benchmark/SLO |
| error_code/stage | Mã và giai đoạn an toàn; null khi không lỗi |
| outcome | Ở record cuối: completed, failed hoặc aborted |

Các stage hiện có: validation, authorization, retrieval, http, database,
text_retrieval, image_retrieval, search_event_persistence,
feedback_persistence, reindex_submission, unhandled, response_stream, cancelled.
`database` là biên session/request, không tự khẳng định nguyên nhân gốc thuộc DB.

Ví dụ minh họa, không phải số đo hiệu năng:

```json
{"timestamp":"2026-11-24T00:00:00+00:00","event":"request.completed","component":"app.request","request_id":"6bb1a8c2-184b-4be0-9c22-b9af6e352491","method":"POST","route":"/api/v1/search/text","status":503,"duration_ms":1.5,"error_code":"SEARCH_UNAVAILABLE","stage":"retrieval","outcome":"failed","level":"ERROR"}
```

Không đọc/copy request body để log. Allowlist không chứa query text/string,
ảnh/file name, raw path/asset ID, headers, admin key, Authorization/cookies,
DB URL/SQL/credentials hoặc exception text/traceback. Chỉ truyền event/code/stage
hằng vào helper lỗi; không truyền input hoặc exception message vào các trường đó.

ContextVar chứa context riêng mỗi request; cùng reference được truyền qua
worker thread của dependency sync. Reset ở finally sau cả success/error/cancel,
không dùng biến global để giữ ID request gần nhất. Không tự truyền context này
sang worker reindex độc lập; tracing job/background worker thuộc phạm vi riêng.

## Lỗi không dự kiến và stream

- Middleware truy vết bao ngoài stack FastAPI/ServerErrorMiddleware để thấy
  response 500 từ handler hiện có và gắn header. Không đổi body JSON 500.
- Khi response đã gửi xong mà framework tiếp tục raise exception, ghi ERROR
  có cấu trúc rồi không đẩy raw exception sang Uvicorn để in traceback nhạy cảm.
- Nếu đã gửi HTTP 200 rồi background task lỗi, không thể đổi status đã gửi:
  record vẫn có status=200 nhưng level=ERROR/outcome=failed.
- Stream chưa hoàn tất mà lỗi: outcome=aborted; raise lỗi chung không chứa
  exception gốc để server đóng kết nối, không gửi body 500 thứ hai hoặc báo
  thành công giả. Cancellation tiếp tục propagate, context vẫn được reset.
- Giữ APP_DEBUG=false khi kiểm chứng error envelope; debug response của
  framework là hành vi riêng, không phải cơ chế logging an toàn cho production.

## Tra log và tái hiện

Từ `backend/`, dùng logging ứng dụng thay access log chứa raw URL:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Ở terminal khác, xem response header:

```powershell
curl.exe -i http://127.0.0.1:8000/healthz
```

Lấy X-Request-ID, tìm cùng ID trong log đã lưu/console. Với container đã build
đúng phiên bản, có thể dùng `docker compose logs backend | Select-String -SimpleMatch '<ID vừa nhận>'`.
Uvicorn/reverse proxy access logs và log thư viện là cấu hình vận hành riêng;
nếu cần bảo đảm không lưu raw URL ở các lớp đó, phải tắt hoặc cấu hình riêng.

Tests và bằng chứng: [issue137-request-logging.md](../evidence/issue137-request-logging.md).
Chờ Duy review cách tiếp nhận header/CORS và Khuê review logging/tests. Không
tự ghi nhận họ đã xác nhận, CI đạt hoặc PR đã merge từ kết quả local.
