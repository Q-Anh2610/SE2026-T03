# Bằng chứng Docker W7 — Issue #148

## Môi trường local và giới hạn tại lượt đo ban đầu

- Người thực hiện: Đoàn Thị Minh Khuê, branch `chore/148-docker-clean-setup`.
- Base commit `3a0e601d84fd7ef95809fe998913b5a6868481ee`, **dirty=true**: thay đổi
  #148 chưa commit, checkout còn các file handoff #114 untracked có sẵn, được giữ nguyên.
- Windows NT 10.0.26300.0, PowerShell 5.1.26100.9818, Docker Engine 29.6.1
  (Linux containers), Compose 5.3.0, Docker Desktop 4.82.0.
- Project riêng `issue148-clean`, volumes PostgreSQL/Qdrant mới, không bind source
  hoặc môi trường Python/Node của host. Cổng host chỉ loopback: frontend 18149,
  backend 18148, PostgreSQL 15448, Qdrant 16348. `.env` local có mật khẩu ngẫu nhiên,
  không được đưa vào report/Git.
- Đây là môi trường container cô lập trên máy hiện có, **không phải** xác nhận một
  máy vật lý mới hoặc một thành viên khác đã tự tái lập. Base images/dependency
  cache của Docker trên máy có thể được tái sử dụng. Không tải model weights/dataset.
- Không gán commit tạo sau cho các lượt chạy dưới đây. Report lặp có SHA-256 các
  file Docker/Compose/verifier/lockfile và image IDs để đối chiếu source local.

## Thay đổi

Compose có frontend, backend, PostgreSQL, Qdrant và service migration chạy một lần.
Backend chờ PostgreSQL/Qdrant healthy và migration thành công; frontend chờ backend.
Nginx phục vụ build production và chuyển `/api/` tới backend qua cùng origin.
Build frontend giữ `tsc --noEmit` và đầy đủ tests/config mà tsconfig đang include.

Backend image CPU dùng torch `2.8.0+cpu`, bỏ các dependencies CUDA khỏi requirements
tạm trong Docker; host requirements/lock và config/model/index W6 không đổi.
`pip check` trong build đạt. Metadata phiên bản CPU không bằng chuỗi `2.8.0`
trong protocol #135; không dùng lượt này thay gate rebuild/benchmark.

Thêm overlay opt-in cho search service, bind handoff/model cache chỉ đọc, offline;
chỉ kiểm cấu hình overlay, chưa chạy retrieval bằng overlay. Thêm workflow Docker
smoke; tại lượt đo local ban đầu **chưa có kết quả CI trên GitHub**. Cập nhật sau bàn giao nằm ở phần dưới.

## Lệnh và kết quả thật

Các lệnh thực thi qua `rtk proxy`; bảng rút gọn phần prefix. Report JSON nhỏ được
giữ tại [initial](issue148-docker-clean-setup/initial.json),
[repeat](issue148-docker-clean-setup/repeat.json) và
[negative](issue148-docker-clean-setup/negative.json).

| Kiểm tra | Kết quả |
|---|---|
| `docker compose -p issue148-clean -f docker-compose.yml config --quiet` | Exit 0 |
| Parser PowerShell cho verifier | Không có parse errors |
| Compose base/overlay resolve trong bộ nhớ, không in secrets | Đủ 5 services, dependency gates, loopback bindings, overlay không mock và 2 mounts read-only/create_host_path=false |
| SHA-256 frozen config W6 | Giữ `1e1962058528e22b5235d989a3613b5077c02d479b8ac19e8dbc28fee0bd08d5` |
| Build đầu | Frontend fail do Dockerfile thiếu tests/setup.ts và các đầu vào tsconfig; đã sửa Docker context/COPY, giữ nguyên typecheck |
| `docker compose -p issue148-clean -f docker-compose.yml build` sau sửa | Exit 0; frontend `tsc --noEmit && vite build` đạt, backend `pip check` đạt |
| `docker compose ... up -d --wait --wait-timeout 120 postgres qdrant` | Exit 0; volumes/network mới, cả hai healthy |
| Verifier trước khi backend chạy | Exit 1 như mong đợi, report failed; kiểm đúng postgres/qdrant rồi dừng ở backend chưa running/healthy |
| `docker compose -p issue148-clean -f docker-compose.yml up --no-build -d --wait --wait-timeout 180` | Exit 0; migration Exited (0), bốn dịch vụ healthy |
| `powershell -NoProfile -File scripts/verify_docker_stack.ps1 -ProjectName issue148-clean` | Exit 0, `infrastructure_verified`; lượt đầu 2026-11-26T19:57:33Z–19:57:41Z |
| Chạy lại cùng `up --no-build ...` và verifier | Cả hai exit 0, migration chạy lại thành công với volumes cũ; verifier 2026-11-26T20:02:53Z–20:03:00Z |
| Browser mở UI production và chọn Danh sách asset | UI render được, danh sách 0 asset của DB mới, không seed fixture |

Smoke đầu/lặp cùng xác nhận revision DB `0004`, HTML có React root, `/healthz`
trực tiếp và qua proxy trả status=ok, list assets qua proxy trả HTTP 200/mock=false,
Qdrant `/readyz` HTTP 200 và collection count=0. Qdrant rỗng là bằng chứng hạ tầng
mới khởi tạo, **không phải** bằng chứng có index/semantic retrieval.

## Kiểm chứng độc lập của Chi — cập nhật 28/11/2026

Nguồn: [phản hồi và ảnh UI của Lê Thị Linh Chi (@LLC536)](https://github.com/Q-Anh2610/SE2026-T03/issues/148#issuecomment-7224043872).
Chi không phải tác giả thay đổi Docker. Hai report được tải từ comment và đọc/đối
chiếu ngày 28/11; đây là kết quả Chi đã chạy, không phải lượt chạy lại của Khuê.

| Thuộc tính | Giá trị Chi ghi nhận |
|---|---|
| Commit | `b85a79375f21c1c0d73e5a46f68166ea38e3bd00`, `dirty=false` ở cả hai report |
| Máy/runtime | Windows NT 10.0.26200.0; PowerShell 5.1.26100.9818; Docker Desktop 4.95.0 / Engine 29.8.2 Linux containers; Compose 5.6.0 |
| Cô lập | Checkout sạch trong repo hiện có, project `issue148-chi`; lượt đầu tạo volumes mới, lượt hai dùng lại volumes; build có thể dùng cache |
| Cổng host | Backend 18000, frontend 18080, PostgreSQL 15432, Qdrant 16333 |
| Lượt đầu (UTC) | 2026-11-27T16:47:11Z–16:47:18Z, `infrastructure_verified` |
| Lượt lặp (UTC) | 2026-11-27T16:50:05Z–16:50:10Z, `infrastructure_verified` |
| Kết quả chung | Bốn dịch vụ `running_healthy`; migration `exited_0`, revision `0004`; UI có React root; API trực tiếp/proxy HTTP 200; assets qua proxy `mock=false`; Qdrant ready, 0 collections |
| Smoke UI do Chi quan sát | Trang chủ và danh sách render được; 0/0 asset, trạng thái rỗng bình thường, không có lỗi tải dữ liệu |

Reports gốc giữ nguyên tại attachments của Chi; SHA-256 dưới đây tính trên bytes
đã tải, không chuẩn hóa hoặc sửa report:

| Report | SHA-256 |
|---|---|
| [Lần đầu — 20261127T164718296Z.json](https://github.com/user-attachments/files/35523091/20261127T164718296Z.json) | `da8305fe0fe4e7ed1cb991fece1bbf5e58c0582eb9cd85dc56eae5cc2e986f0e` |
| [Lần hai — 20261127T165010636Z.json](https://github.com/user-attachments/files/35523117/20261127T165010636Z.json) | `ce1c70797f331f87ad1e136a38935a53becf728fbf2826b8b099e053065a92bf` |

`checks`, `source_sha256` và `image_ids` trùng giữa hai reports. Đối chiếu 11 file
source với checkout Khuê tại cùng commit: 5 raw hashes khớp trực tiếp; 6 file
còn lại khớp nội dung sau quy đổi LF/CRLF (`docker-compose.search.yml`, frontend
Dockerfile/.dockerignore/nginx.conf, verifier và workflow Docker). Không thay
hash lịch sử để che khác biệt EOL; image IDs chỉ đối chiếu giữa hai lượt của Chi.

Windows đã chặn verifier bằng Execution Policy trước khi chạy. Chi gọi lại bằng
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_docker_stack.ps1 -ProjectName issue148-chi`
cho riêng tiến trình; hai report thành công ở trên được tạo sau khi xử lý lỗi này.
[Runbook Windows](../guides/docker-clean-setup-w7.md#script-powershell-bị-chặn-trên-windows)
đã bổ sung bước đó, cùng liên kết từ README và hướng dẫn scripts.

Phạm vi xác nhận là hạ tầng và smoke UI cơ bản trên containers/volumes cô lập,
không phải máy vừa cài mới hay build không cache. Search/feedback giữ mock mặc
định; cả hai report ghi retrieval/E2E/benchmark chưa kiểm chứng. Không nghiệm thu
overlay search thật, #135, #149, #150 hoặc toàn W7 từ các kết quả này.

## CI và review

Trước bản sửa tài liệu này, [PR #152](https://github.com/Q-Anh2610/SE2026-T03/pull/152)
ở head `b85a793` có 6/6 checks thành công: [Docker smoke](https://github.com/Q-Anh2610/SE2026-T03/actions/runs/46028985051),
[backend/health + frontend](https://github.com/Q-Anh2610/SE2026-T03/actions/runs/46028985080),
[API contract + frontend](https://github.com/Q-Anh2610/SE2026-T03/actions/runs/46028985272)
và [branch policy](https://github.com/Q-Anh2610/SE2026-T03/actions/runs/46028985107).
Sau commit tài liệu, đối chiếu CI của head mới trên PR; không chuyển trạng thái
xanh của commit cũ sang commit mới. Formal approval và merge chưa được xác nhận.

## Checklist bàn giao

- [x] Build và chạy được stack trên containers/volumes riêng; không dùng host venv/node_modules.
- [x] Migration, health và đường UI → proxy → API → PostgreSQL đã kiểm chứng.
- [x] Khởi động lặp với volumes cũ đạt; verifier có kiểm tra âm tính báo failed.
- [x] Có README/runbook, cấu hình mẫu, hướng dẫn dừng và cảnh báo xóa đúng volumes.
- [x] Có reports nhỏ, base commit/dirty status, source hashes và giới hạn thực tế.
- [x] Chi tự chạy hai lượt tại `b85a793`, có reports và UI; đã bổ sung bước Execution Policy còn thiếu vào runbook.
- [x] Đã quan sát CI GitHub 6/6 tại `b85a793`; CI sau commit tài liệu cần được kiểm tra riêng trên PR.
- [ ] Review/tích hợp: Quỳnh Anh xem compose/migration/env, Duy xem packaging/proxy UI.

Không tích E2E #149, hiệu năng #150 hoặc milestone W7 từ bằng chứng này. `.env`,
runtime data, Docker volumes, model/index lớn và các file handoff cá nhân ở ngoài Git.
