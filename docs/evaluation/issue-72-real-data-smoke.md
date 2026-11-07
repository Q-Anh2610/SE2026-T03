# Checklist smoke UI text search bằng dữ liệu thật — Issue #72

Tài liệu này chuẩn bị ca chạy có thể lặp lại cho smoke UI trên web. Smoke này xác nhận đường đi từ trình duyệt qua API/index đang chạy tới asset detail; không đo chất lượng retrieval hay thay thế benchmark có nhãn.

## Điều kiện chạy trên môi trường dùng chung

Các ô trong phần này dành cho smoke trên staging/production (production chỉ khi được duyệt). Chúng vẫn để trống vì lần smoke đã chạy chỉ xác nhận local; không suy rộng kết quả local thành trạng thái của deployment dùng chung. Nếu thiếu API/index thực hoặc không xác định được phiên bản dữ liệu của môi trường đó, ghi blocker; không thay bằng mock.

- [ ] URL web và môi trường (local/staging), thời điểm chạy và trình duyệt/phiên bản.
- [ ] Commit/build frontend đang kiểm tra.
- [ ] API origin, health status và commit/version API; kiểm tra CORS từ đúng origin web.
- [ ] Dataset snapshot và index version mà API môi trường dùng chung trả về. Bằng chứng local bên dưới dùng snapshot `home-interior-354-v1` (354 asset), source manifest SHA-256 `93f65237ca51060aad75f0f672b2b16f76c89a64dce64d7473791f428e944614` và CLIP `openai/clip-vit-base-patch32`, revision `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`; các giá trị này chưa xác nhận staging/production. Manifest Objaverse 200 trong `data/manifests/` hiện là `PENDING`, không dùng làm bằng chứng index đã nạp.
- [ ] Model/preprocessing/config version và trạng thái index đồng bộ với dataset snapshot.
- [ ] Xác nhận các anchor asset trong bảng bên dưới đã searchable trong index thực. Manifest local hiện đánh dấu `PENDING`, vì vậy tự nó không chứng minh index đã được nạp.
- [ ] Dùng API thật trên môi trường cần kiểm tra: cấu hình web trỏ tới API bằng `VITE_API_BASE_URL`/origin môi trường. Ghi lại request URL và response status; xác nhận response không phải mock (`mock=true`, `source=fixture`, ID/version `mock-*`). Không lưu credentials, cookies hoặc token vào bằng chứng.

## Mẫu bàn giao để bắt đầu smoke thật

Owner API/retrieval và người quản lý môi trường có thể gửi một comment trên Issue #72 với các trường dưới đây. Chỉ gửi giá trị không nhạy cảm trong comment; nếu một trường chưa có, ghi `chưa có` và owner/thời điểm dự kiến thay vì tự suy đoán.

```text
Môi trường: staging / local dùng chung (không dùng production nếu chưa được duyệt)
URL web: https://<host>/
API origin: https://<api-host>
API health check: GET https://<api-host>/healthz (không kèm credentials)
Frontend commit/build đang được phục vụ: <full SHA hoặc build ID>
API/retrieval commit đang chạy: <full SHA>
CORS: cho phép chính xác origin web ở trên; methods/headers cần cho POST JSON và GET detail
Dataset: tên + snapshot/revision + manifest SHA-256 + số record đã searchable
Model: checkpoint + revision + dimension + preprocessing/processor
Vector index: Qdrant collection/index version + vector name/dimension/similarity + snapshot ID
Search config: config version/hash + top-K mặc định + filters được bật
Asset detail: xác nhận GET /api/v1/assets/{asset_id} dùng cùng database/snapshot
Query smoke và anchor asset ID đã xác nhận searchable: <query> -> <asset_id>
Cách mở web: URL và các bước cần thiết, không kèm token/password
Cách truy cập an toàn: VPN/SSO hoặc quy trình cấp quyền tạm thời bên dưới
Thời gian môi trường sẵn sàng và người phối hợp/on-call:
Ràng buộc: rate limit, dữ liệu không được truy cập, giờ bảo trì hoặc giới hạn request
```

### Hướng dẫn cấp quyền an toàn

- Ưu tiên staging/test environment với dataset/index snapshot đã nạp; chỉ cấp quyền tối thiểu cần để mở web và gọi API search/detail. Dùng VPN/SSO của nhóm nếu có.
- Nếu cần credential, cấp qua secret manager/password manager hoặc kênh nội bộ đã được nhóm duyệt; gửi hướng dẫn lấy credential riêng, không gửi giá trị secret trong GitHub Issue, chat này, file repo, URL query string, screenshot hay report.
- Ưu tiên tài khoản tạm có thời hạn và chỉ đọc. Không yêu cầu quyền shell/DB/Qdrant nếu browser smoke không cần; không cấp quyền ghi, xóa, reindex hay quản trị.
- CORS chỉ allowlist đúng origin web cần kiểm tra; không bật `*` để chữa lỗi. Không bật `Access-Control-Allow-Credentials` trừ khi flow đăng nhập thực sự cần và cấu hình origin cụ thể.
- Nêu rõ có thể chạy query tạo search event hay không, giới hạn request, và cách liên hệ owner trước khi thử lỗi/retry. Không làm thay đổi index, dữ liệu hoặc trạng thái dịch vụ dùng chung.
- Sau buổi smoke, thu hồi quyền tạm/credential theo quy trình và xác nhận đã thu hồi; report chỉ ghi tên cơ chế truy cập và thời điểm, không ghi secret.

### Tiêu chí sẵn sàng

Chỉ bắt đầu khi mở được URL web và gọi health check API từ cùng môi trường người dùng; CORS cho phép origin đó; commit/version đang chạy được xác định; API trả được dataset/model/index/config version; ít nhất một query đã có anchor ID searchable; endpoint detail dùng cùng nguồn metadata; và người kiểm thử có quyền truy cập an toàn hợp lệ. Nếu thiếu điểm nào, ghi rõ owner/blocker trong Issue #72. Nếu origin không truy cập được từ browser được chia sẻ, người có quyền môi trường cần xác nhận VPN/allowlist hoặc chạy buổi smoke cùng người kiểm thử; không thay bằng request API mock.

## Trạng thái bàn giao — 2026-11-07

PR #78 đã merge vào `develop` tại merge commit `01f7056629425d5294d926c3938199047bc5ce28`; nhánh `test/72-smoke-text-search-web` đã được fetch/cập nhật tới cùng SHA.

Đã chuẩn bị local ngày 2026-11-07: CLIP `openai/clip-vit-base-patch32` revision `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268` có trong Hugging Face cache; index riêng tại `data/processed/issue65/index-8f92d4afd532` có 354/354 asset và 354/354 point, snapshot SHA khớp manifest runbook. Verifier dùng một PostgreSQL test riêng, tách khỏi database phát triển; thông tin kết nối và credential không được ghi vào tài liệu hoặc Git. Hãy cấu hình kết nối an toàn trong terminal hiện tại theo runbook/thiết lập local trước khi chạy.

Chạy verifier từ gốc repo bằng manifest/root/Qdrant path vừa dựng; verifier chỉ tạo và dọn schema tạm trong database test riêng:

```powershell
backend\.venv\Scripts\python.exe scripts/verify_text_search_api.py --index-manifest data/processed/issue65/index-8f92d4afd532/index-manifest.json --index-root data/processed/issue65/index-8f92d4afd532 --qdrant-local-path data/processed/issue65/index-8f92d4afd532/qdrant
```

### Bằng chứng chạy local — 2026-11-07

- API real-data verifier: `passed`; 354 asset/point, 5 HTTP search event, pagination/detail, AND filters, empty/out-of-range, validation, version/event persistence và fingerprint Qdrant không đổi. Query `wooden chair`, total candidate window 200. Report: `data/processed/issue65/http-00fc84d6bc73.json`.
- Phiên bản đã xác minh local: dataset snapshot `home-interior-354-v1-sha256:93f65237ca51060aad75f0f672b2b16f76c89a64dce64d7473791f428e944614`; model `openai/clip-vit-base-patch32@3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`; index `issue65-home-interior-354-v1-clip-v1`; config `clip-text-exact-all-filtered-v1-k200`; 354 asset và 354 Qdrant point.
- Browser integration verifier: `passed`; 8/8 Playwright cases (desktop/mobile), 14 HTTP request thành công từ UI được xác minh có event trong PostgreSQL; tổng 29 event sau các case lỗi/phục hồi. `GET /api/v1/assets/{asset_id}` trả asset trùng với hàng search; quay lại giữ query, page 2, limit 6 và filters. Query `wooden chair` trả 200 ứng viên; page 1 và 2 có ID duy nhất; page 35 rỗng. Query filter `chair` trả 1 asset và filter category không khớp trả empty. Report tổng hợp: `data/processed/issue72/issue72-local-integration-direct.json`; report Playwright: `data/processed/issue72/issue72-local-integration-direct.playwright.json`.
- Sáu kết quả đầu của `wooden chair` (page 1, limit 6; rank theo thứ tự response):

  | Rank | Asset ID |
  |---:|---|
  | 1 | `objaverse_0102b2c1449f448687d62ea66ae2a26a` |
  | 2 | `objaverse_a0fa677edd6a417f869d7dcf224484c4` |
  | 3 | `objaverse_a562af9c76a346faaad36773554c4c28` |
  | 4 | `objaverse_ab65da1fdec04cfcb583391ae883f6b0` |
  | 5 | `objaverse_3fc7e4dcddae42ca9d8f905ff4622fa7` |
  | 6 | `objaverse_f73b3dbebc434dcbb28678fad0c6bf49` |
- Lượt đầu qua `rtk proxy` in 8/8 case đạt nhưng wrapper báo verifier failed ở kiểm tra exit code của Playwright. Lượt chạy trực tiếp Python sau đó có report tổng hợp `passed`; chỉ dùng report direct làm kết quả cuối.
- Đây là API/frontend thật chạy local với HTTP, CLIP CPU, Qdrant persistent local và PostgreSQL schema test riêng. Không phải kiểm chứng staging/production, Qdrant server, CI, review của thành viên khác hay benchmark chất lượng retrieval. Deployment web/API lâu dài vẫn chưa được bàn giao. Verifier tự khởi chạy Uvicorn + Vite, cấu hình CORS đúng origin localhost và dừng dịch vụ sau lượt chạy.
- Smoke tự động đã thực hiện query và thao tác detail/back trên trình duyệt Playwright. Checklist thao tác bên dưới được cập nhật theo các case đã chạy; kết quả này không xác nhận một phiên smoke thủ công hay smoke trên staging/production.

## Query/case chuẩn bị sẵn

Chạy với `filters={}`, `page=1`, `limit=6`; query `wooden chair` là query đã dùng trong runbook tích hợp thật. Snapshot 354 có cửa sổ tối đa 200 candidates; báo cáo tích hợp ghi hai trang đầu có 24 asset ID duy nhất và detail khớp metadata. ID cụ thể phải lấy từ response/API và report của đúng snapshot/index trong lượt chạy; không gán một asset ID giả định làm nhãn relevance hoặc yêu cầu nó phải đứng hạng 1.

| ID | Query | Dữ liệu tham chiếu | Kiểm tra chính |
|---|---|---|---|
| TXT-01 | `wooden chair` | Snapshot `home-interior-354-v1`; lấy `asset_id` trực tiếp từ response của index đang chạy | So sánh IDs/scores/order/total/versions giữa UI và API; mở detail bằng một ID trả về, đối chiếu metadata nguồn và quay lại giữ query/page/limit/filters. Lưu event ID và IDs/ranks trong report. |

Nếu snapshot/index thực tế khác phiên bản tham chiếu, ghi đúng version đó và chọn query/asset đã xác nhận nằm trong index; không dùng kết quả của snapshot khác để kết luận.

## Checklist thao tác trên web — kết quả Playwright local

### Tìm kiếm và kết quả

- [x] Playwright mở web local và xác nhận UI gửi request HTTP thật tới API local, không mock response; cấu hình CORS cho origin localhost được verifier khởi chạy.
- [x] Chạy query `wooden chair` (TXT-01), filters rỗng, page 1/2, limit 6; report ghi response/event, versions và IDs/ranks. TXT-02…TXT-04 chưa được chạy.
- [x] Xác nhận loading kết thúc, query được giữ, IDs trên trang không trùng và số kết quả tuân theo limit; đã kiểm tra hai trang đầu.
- [x] Mở detail của asset trong kết quả; `GET /api/v1/assets/{asset_id}` trả asset metadata trùng với hàng search.
- [x] Quay lại danh sách và xác nhận query, filters, page 2 và limit 6 được giữ.

### Empty, validation, filters và pagination

- [ ] Để trống query và gửi: chưa có bằng chứng UI chặn request query rỗng trong bộ 8 case hiện ghi nhận.
- [x] Đã kiểm tra empty response thành công qua query/filter không có kết quả và page ngoài phạm vi (page 35); không suy luận empty từ chuỗi ngẫu nhiên.
- [x] Đã chạy AND filters với query `chair`; có một asset thỏa filter và một category không khớp trả empty.
- [x] Đã sang page 2 và kiểm tra detail/back giữ trang hiện tại; page 1/2 có IDs duy nhất.
- [x] Trong môi trường test local, đã kiểm tra lỗi HTTP 503 và 500 cùng thao tác retry sau khi service phục hồi. Không thử gây lỗi trên staging/production.

### Bằng chứng và kết luận

- [x] Lưu report local có môi trường, versions, case, IDs/ranks, status, detail/back: `data/processed/issue72/issue72-local-integration-direct.json` và `issue72-local-integration-direct.playwright.json` (report phát sinh, không commit).
- [ ] Screenshot: chưa đính kèm; không bắt buộc cho report tự động hiện tại.
- [x] Phân biệt `PASS` local với staging/production chưa xác nhận; CI và review cũng chưa được xác nhận.
- [x] Ghi rõ smoke dùng API thật, không mock; không dùng kết quả smoke để kết luận chất lượng semantic retrieval.

## Mẫu ghi lại mỗi lần chạy

```text
Ngày/giờ + timezone:
Môi trường / URL web:
Trình duyệt:
Frontend commit/build:
API origin + API commit/version:
Dataset snapshot / index version:
Model / preprocessing / config version:
Case ID + query + filters + page/limit:
HTTP status + query_id/search_event_id:
Asset IDs + ranks (top 12):
Anchor indexed? (yes/no/unknown) + rank nếu có:
Asset detail API/status + back state:
Kết quả: PASS / FAIL / BLOCKED / N/A
Bằng chứng (đường dẫn/screenshot đã lọc thông tin nhạy cảm):
Ghi chú / blocker / người cần phối hợp:
```

Lệnh khởi chạy local và `npm run test:e2e` hiện kiểm tra UI/API mock hoặc HTTP fixture theo cấu hình hiện có; các lệnh đó không tự tạo môi trường retrieval thật. Chỉ dùng URL/build đang nối tới API/index thực để hoàn tất các case của Issue #72.
