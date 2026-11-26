# Bằng chứng local Docker W7 — Issue #148

## Môi trường và giới hạn

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
smoke nhưng **chưa có kết quả chạy CI trên GitHub**.

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

## Checklist bàn giao

- [x] Build và chạy được stack trên containers/volumes riêng; không dùng host venv/node_modules.
- [x] Migration, health và đường UI → proxy → API → PostgreSQL đã kiểm chứng.
- [x] Khởi động lặp với volumes cũ đạt; verifier có kiểm tra âm tính báo failed.
- [x] Có README/runbook, cấu hình mẫu, hướng dẫn dừng và cảnh báo xóa đúng volumes.
- [x] Có reports nhỏ, base commit/dirty status, source hashes và giới hạn thực tế.
- [ ] Một thành viên khác tự chạy hướng dẫn và phản hồi kết quả; chưa xác nhận.
- [ ] CI GitHub trên head của PR; chưa push/mở PR hoặc quan sát checks.
- [ ] Review/tích hợp: Quỳnh Anh xem compose/migration/env, Duy xem packaging/proxy UI.

Không tích E2E #149, hiệu năng #150 hoặc milestone W7 từ bằng chứng này. `.env`,
runtime data, Docker volumes, model/index lớn và các file handoff cá nhân ở ngoài Git.
