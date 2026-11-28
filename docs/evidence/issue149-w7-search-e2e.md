# W7 E2E search — bằng chứng local Issue #149

Ngày chạy: 28/11/2026. Nhánh `test/149-w7-search-e2e`, base commit
`213472bdeff7b6eef9b9f7ac6c54c79099831589`, working tree **dirty=true**.
Các lượt đo được thực hiện trước commit, chưa có review tại thời điểm đo.
Đây là kết quả local của code chưa commit khi chạy; commit/PR bàn giao sau
không thay provenance của các lượt đo và không chứng minh CI xanh hoặc M6 đạt.

**Kết luận: chưa đạt đầy đủ #149.** Lượt cuối 10 passed / 6 failed / 0 skipped,
retries=0. Text/image search, filters, pagination, detail/back và feedback API
đã kiểm chứng; feedback UI qua nginx còn lỗi. Timeout ảnh đầu tiên ở lượt đầu
vẫn cần owner xử lý; kết quả cache nóng không thay thế quan sát này.

## Stack và đầu vào thật

- Project Docker riêng `issue149-w7`: frontend nginx/production build từ source
  hiện tại, backend FastAPI, migration head, PostgreSQL 17 và Qdrant server
  1.15.1. URL frontend `http://127.0.0.1:8249`, backend `:8149`, DB `:5549`,
  Qdrant `:6439`. Không dùng endpoint control, fixture retrieval hay HTTP interception.
- Backend dùng image CPU cache từ #148 (`issue148-clean-backend:latest`), bind
  source backend/alembic hiện tại chỉ đọc. Frontend build mới bằng Dockerfile
  hiện có. Model cache và handoff chỉ đọc trong backend. Không đổi compose
  dùng chung, source sản phẩm, dependencies, API/schema hoặc frozen index W6.
- DB riêng `test_issue149_w7_20261128`; collection mới
  `issue149_7419c6ca20524df5998c7f2d3e185935`; volumes project riêng. Không dùng
  container DB test cũ hoặc chuyển Qdrant SQLite reference sang server storage.
- Chuẩn bị bằng encoder/batch/store hiện có: CLIP offline CPU, batch 8,
  seed 0, 4 torch threads; 200 embedded, 0 failed/skipped. Source/ready/preview
  hashes và IDs được kiểm trước encode; preview gốc vẫn khớp hash sau chuẩn bị.
- Snapshot `home-interior-clear-200-v3`, source SHA-256
  `9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`.
  CLIP revision `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`, 512D/RGB/L2/Cosine.
  Index riêng `issue149-20261128T161923Z-e7bdf801`, text/image cutoff 200.
- Query text cố định `wooden chair`/`chair`; ảnh probe là preview có hash
  `703ab241bbc1800eb70ee9a08898954be0090655383e3a9263b3da840ca37358`.
  Ảnh trong index chỉ dùng smoke chức năng; không dùng để công bố relevance.
  Filters lấy metadata thật: category=`furniture-home`, license=`by`, format=`glb`,
  face_count_min=max=540642. Không đọc held-out benchmark để chọn đáp án.

Môi trường quan sát: Windows `10.0.26300`, Ryzen 7 5800HS, 16 logical CPUs,
RAM 7,41 GiB; Docker Engine 29.6.1, Compose 5.3.0. Host Python 3.13.15,
torch 2.8.0; backend container Python 3.13.18, torch 2.8.0+cpu. Cả hai dùng
transformers 4.57.1, qdrant-client 1.15.1, Pillow 13.0.0. Host Node 24.18.1,
Playwright 1.64.0; browser user agent HeadlessChrome 158.0.0.0. Frontend image
build Node 22.14.0/nginx 1.28 theo Dockerfile. Không coi môi trường CPU image
này là đã đạt version gate benchmark/rebuild #135.

## Lệnh và kết quả

Runbook tái lập cho máy khác: [E2E search W7](../guides/e2e-search-w7.md).
Các lệnh thực tế dùng `rtk proxy` vì RTK mode thường lỗi tìm Claude config.
Host Python/Chrome/Docker cần quyền môi trường ngoài sandbox; không đổi config
cá nhân để né lỗi. Runtime compose/env/scripts riêng nằm trong `data/runtime/issue149/`
và không commit; không có password trong tài liệu này.

| Lệnh / kiểm tra | Kết quả |
|---|---|
| `docker compose --env-file data/runtime/issue149/stack.env -p issue149-w7 -f data/runtime/issue149/compose.yaml up -d --wait postgres qdrant migrate` | Exit 0, project mới, migration thành công |
| `backend/.venv/Scripts/python.exe -B scripts/prepare_w7_e2e.py --handoff data/processed/issue87-clip200-handoff-20261111-eebfc0b2/issue87-clip200-handoff-20261111-eebfc0b2 --qdrant-url http://127.0.0.1:6439` | Exit 0, 200/200 thật, output `20261128T161923Z-e7bdf801` |
| Compose `build frontend`, `up -d --wait backend`, `up -d --wait --no-build frontend` với cùng project/files | Exit 0, bốn dịch vụ healthy, migrate Exited 0 |
| Từ frontend: `npm.cmd run typecheck`, `npm.cmd run lint`, `npm.cmd run build` | Đạt; lint/typecheck chạy lại sau sửa harness cũng đạt |
| `backend/.venv/Scripts/python.exe -B -m pytest backend/tests/unit/test_w7_e2e_preparation.py -q -p no:cacheprovider` | 9 passed, 23,33 s; kiểm guard targets, không phải model smoke |
| Từ frontend, env URL/input của lượt chuẩn bị: `npm.cmd run test:stack` — lượt 1 | Exit 1; 9 passed / 7 failed / 0 skipped, 236,984 s, bắt đầu 16:23:02 UTC |
| Cùng lệnh — lượt 2 sau sửa harness requestfailed | Exit 1; 10 passed / 6 failed / 0 skipped, 134,216 s, bắt đầu 16:32:21 UTC |
| `scripts/audit_w7_e2e.py` cho từng report, kết nối PostgreSQL mới + Qdrant chỉ đọc | Hai lượt exit 0, `persistence_verified`; xem JSON bên dưới |
| Kiểm editor diagnostics và `git diff --check` | Không có lỗi ở code thêm; diff whitespace đạt |

Harness thay đổi giữa hai lượt: quan sát thêm `requestfailed`, dùng
Promise.race để báo request bị hủy thay vì chờ hết test timeout 90 s.
Không tăng timeout/retry, đổi assertion, skip/xfail hoặc warm-up để che lỗi.
Lượt 2 dùng backend đang chạy từ lượt 1, **không tái lập cold start**.

Audit lần đầu lỗi TypeError vì QdrantClient hiện tại không là context manager;
đã sửa thành `contextlib.closing` theo pattern repo rồi chạy lại cả hai report.
Không dùng các lần audit lỗi làm bằng chứng đạt. Các lỗi sandbox/config ban
đầu đã được chạy lại bằng đúng quyền; không tính là test sản phẩm thất bại.

| Nhóm ca | Desktop lượt 2 | Mobile lượt 2 |
|---|---|---|
| OpenAPI feedback qua nginx | Failed: HTML thay JSON | Failed: HTML thay JSON |
| Text/pagination/detail/back | Passed | Passed |
| Text filters AND/empty | Passed | Passed |
| Image/pagination/detail/back | Passed, lượt đầu timeout | Passed |
| Image filters AND/empty | Passed | Passed |
| Feedback từ text UI | Failed | Failed |
| Feedback từ image UI | Failed | Failed |
| Feedback API thật + invalid limit/ảnh hỏng | Passed | Passed |

## Persistence và bằng chứng nhỏ

- [Preparation](issue149/preparation.json), [suite input](issue149/suite-input.json),
  [text manifest](issue149/text-index-manifest.json), [image manifest](issue149/image-index-manifest.json)
  là bản sao nguyên bytes của output chuẩn bị, có hashes/module provenance.
- [Audit lượt 1](issue149/e2e-run-1-persistence.json): đối chiếu 20 event quan
  sát qua UI và 2 feedback receipts với PostgreSQL bằng kết nối mới.
- [Audit lượt 2](issue149/e2e-run-2-persistence.json): đối chiếu 22 event UI và
  2 feedback receipts; IDs/versions/query/result IDs và filters khớp.
  Database tại thời điểm cả hai audit: 200 assets, 47 events, 4 feedbacks.
  Counts là tổng hai lượt, có event từ request bị frontend hủy; không phải
  47 ca E2E hoặc 4 feedback UI thành công.
- Audit chỉ đọc xác nhận Qdrant đủ 200 IDs, named vector/dimension/Cosine và
  payload `_index` đúng manifest. Không tuyên bố vector fingerprint trước/sau
  giống tuyệt đối vì lượt này không lưu fingerprint trước test.
- [Kiểm tra artifacts và SHA-256](issue149/artifact-inspection.json): 13 trace
  lỗi của hai lượt; không thấy password DB test hoặc header Authorization,
  X-Admin-Key/Cookie có giá trị trong network records đã kiểm.
  Đây không phải bảo đảm loại mọi loại dữ liệu nhạy cảm chưa biết; raw trace
  chỉ giữ local, không commit.

Raw report và trace đã bảo toàn tại `data/runtime/issue149/e2e-run-1/` và
`e2e-run-2/`; JSON gốc vẫn có trong `frontend/test-results/stack-report.json`.
Ảnh/trace, preview, weights, Qdrant storage và private env không thuộc diff.
JSON manifests ở đây chỉ là evidence, không phải gói input/index chạy độc lập.
[Hashes source/harness cuối](issue149/module-sha256.json) phân biệt code bàn
giao với manifest chuẩn bị trước đó; không ghi đè hashes lịch sử trong manifest.

Sau kiểm chứng đã chạy Compose `stop` cho riêng project `issue149-w7`, exit 0;
giữ volumes, input/model và mọi report/trace. Không dừng container DB test có
sẵn trước nhiệm vụ. Muốn xem lại UI cần `up` cùng runtime compose/env hoặc
dựng project riêng theo runbook; không cần xóa volumes.

## Lỗi còn chờ owner — chưa tạo Issue GitHub mới

### A. Proxy OpenAPI chặn feedback UI — blocking #149

**Owner chính: Đoàn Thị Minh Khuê**, phụ trách nginx/Docker theo phân công repo.
**Phối hợp: Nguyễn Văn Duy** kiểm tra feedback client và nghiệm thu UI sau sửa;
**Vũ Nguyễn Quỳnh Anh** review runtime contract nếu cần. Đây là owner cần
tiếp nhận/review, chưa phải xác nhận đã nhận việc. Tài liệu #145 đã ghi rủi ro
này; lần này có repro thực tế, không chỉ phân tích tĩnh.

1. Với stack thật đang chạy, GET `http://127.0.0.1:8149/openapi.json`:
   HTTP 200, application/json, feedback schema `LiveFeedbackResponse`.
2. GET cùng path qua `http://127.0.0.1:8249/openapi.json`:
   HTTP 200, **text/html**, body SPA.
3. Trên UI tìm text hoặc ảnh, nhấn **Phù hợp** ở kết quả đầu.
   Mong đợi POST `/api/v1/feedback` → 201/storage=postgresql và UI báo đã lưu.
   Thực tế client lỗi đọc JSON từ OpenAPI, hiển thị lỗi; không gửi POST feedback.
4. Ca API trực tiếp qua nginx vẫn POST feedback được, receipt khớp DB.

Root cause đã đối chiếu: nginx chỉ proxy `/api/` và `/healthz`; `/openapi.json`
rơi vào SPA fallback, trong khi feedback client đọc spec trước POST. Giữ
6 assertions fail trên hai viewport. Không sửa nginx/client trong scope test;
cần owner sửa và chạy lại đủ sáu ca, sau đó xác nhận persistence UI.

### B. Request ảnh đầu vượt timeout frontend — còn mở

**Owner chính chẩn đoán: Vũ Nguyễn Quỳnh Anh**, phụ trách backend/services và
runtime API. **Phối hợp: Lê Thị Linh Chi** kiểm tra encoder/inference/readiness,
**Nguyễn Văn Duy** kiểm tra timeout/hành vi UI, **Đoàn Thị Minh Khuê** tái lập
trên cùng CPU/memory/Docker. Chưa xác định root cause cuối hoặc có xác nhận
owner đã tiếp nhận. Không tự tăng timeout hoặc tối ưu model ngoài scope #149.

Trong lượt 1, request ảnh đầu sau bootstrap bị frontend hủy sau 15 s, UI báo
không kết nối được dịch vụ. Nginx ghi 499 lúc 16:23:47 UTC. Backend hoàn tất
request ID `4c712df6-0e42-47fa-968f-f62b09bf6e4e` lúc 16:23:52,925 UTC,
status 200, duration **20600,825 ms**. [Quan sát đã trích](issue149/cold-image-request.json).

Repro cần backend vừa bootstrap, chưa gọi image search, cùng manifest/ảnh và
điều kiện máy; mở ảnh rồi gửi lần đầu. Đây là quan sát một lượt, chưa xác
định được độ lặp hoặc nguyên nhân tài nguyên sâu hơn; không công bố benchmark
p95 hay kết luận thuật toán lỗi. Ảnh lượt 2 đạt trên cache nóng không đóng lỗi.

## Checklist bàn giao

- [x] Có suite/harness và chạy UI/API trên PostgreSQL/Qdrant/CLIP thật.
- [x] Có kết quả desktop/mobile, versions, durable receipts, logs/trace local và repro.
- [x] Giữ test lỗi, không che bằng mock/retry/skip; ghi owner và giới hạn.
- [ ] Tất cả luồng chính thành công: feedback UI và ảnh cold-start còn chờ.
- [ ] Owner xác nhận tiếp nhận/sửa lỗi và chạy lại các ca bị ảnh hưởng.
- [ ] Owner review/CI/merge hoàn tất; theo dõi trạng thái thật trên GitHub.

Không tích acceptance criteria đầu của Issue #149 hoặc đóng Issue/M6 chỉ từ
suite/report này. Bàn giao bằng Draft PR vào `develop`, kèm report/repro và
owner nêu trên; cập nhật checklist Issue theo trạng thái thật, không tự đóng Issue.
