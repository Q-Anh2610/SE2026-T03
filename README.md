# SE2026-T03

Semantic Search cho thư viện 3D assets: tìm bằng văn bản/ảnh, sử dụng React + TypeScript, FastAPI, PostgreSQL và Qdrant.

## Thành viên nhóm

| STT | Họ và tên |
|---|---|
| 1 | Vũ Nguyễn Quỳnh Anh |
| 2 | Trịnh Thị Thu Huyền |
| 3 | Lê Thị Linh Chi |
| 4 | Nguyễn Văn Duy |
| 5 | Đoàn Thị Minh Khuê |

## Cấu trúc repository

| Đường dẫn | Nội dung | Người chủ trì |
|---|---|---|
| `frontend/` | Ứng dụng React + TypeScript | Nguyễn Văn Duy |
| `backend/` | API, nghiệp vụ, ingestion, embedding và search | Vũ Nguyễn Quỳnh Anh, Trịnh Thị Thu Huyền, Lê Thị Linh Chi |
| `evaluation/` | Benchmark, cấu hình thí nghiệm và kết quả nhỏ | Đoàn Thị Minh Khuê |
| `data/` | Manifest, mẫu, nhãn benchmark; dữ liệu lớn chỉ lưu local | Trịnh Thị Thu Huyền, phối hợp Đoàn Thị Minh Khuê cho nhãn |
| `scripts/` | Công cụ dùng chung; script riêng module đặt cạnh module | Theo module |
| `docs/` | Yêu cầu, kiến trúc, contract, ADR và đóng góp | Cả nhóm |
| `.github/` | CI và mẫu Issue/PR | Đoàn Thị Minh Khuê |
| `.env.example` | Mẫu cấu hình local, chỉ có giá trị giả | Vũ Nguyễn Quỳnh Anh, Đoàn Thị Minh Khuê |
| `.gitignore` | Loại secret, dữ liệu lớn và file sinh tự động | Đoàn Thị Minh Khuê |
| `README.md` | Giới thiệu và hướng dẫn chạy | Vũ Nguyễn Quỳnh Anh tổng hợp |

Xem [sơ đồ thư mục và ranh giới module](docs/STRUCTURE.md), [kế hoạch](ROADMAP.md) và [hướng dẫn Codex](AGENTS.md).

Backend FastAPI có assets PostgreSQL, text/image search chọn mock hoặc CLIP service,
feedback chọn RAM/PostgreSQL, jobs/status và reindex quản trị, cùng logging W6.
Xem [hướng dẫn cài đặt, chạy và kiểm thử backend](backend/README.md).
Xem [API contract hiện hành và bảng bốn OpenAPI profiles](docs/contracts/api-v1.md),
[hướng dẫn chạy/kiểm chứng API W7](docs/guides/api-reproducibility-w7.md).
`docs/openapi.json` là profile mặc định assets DB + search/feedback mock;
runtime `/openapi.json` trên origin backend phản ánh cấu hình server đang chạy.
`docker-compose.yml` khởi chạy frontend, backend, PostgreSQL, Qdrant và migration. Xem
[hướng dẫn ORM, Alembic và seed](docs/guides/database.md).
List/detail asset mặc định đọc PostgreSQL (Issues #47/#48); cấu hình mẫu giữ
search/feedback mock phát triển, chế độ service cần input/index/cache riêng.
Xem [bàn giao asset API](docs/guides/asset-api.md).
Đã có các module CLIP batch, Qdrant store và keyword baseline
của Issue #39; Search API có thể chọn service theo cấu hình/guide tương ứng. Xem
[hướng dẫn baseline W2](docs/guides/search-baseline-w2.md).
Xem [hướng dẫn frontend](frontend/README.md) cho giao diện hiện có.

## Dựng toàn bộ stack bằng Docker — W7 / Issue #148

Cần Git và Docker Engine đang chạy Linux containers, Docker Compose v2 có
`up --wait`. Không cần cài Python, Node hoặc PostgreSQL trên máy host để chạy stack.
Lần build đầu cần mạng và dung lượng cho images/dependencies; không tải model/dataset.
Lệnh kiểm chứng bên dưới dùng PowerShell 5.1/7; Linux/macOS dùng `pwsh` với script tương tự.

Từ gốc checkout mới, tạo cấu hình nếu chưa có (không ghi đè cấu hình đang dùng):

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Đổi `POSTGRES_PASSWORD` mẫu trong `.env` thành mật khẩu local riêng. Nếu cổng
đang bận, đổi `FRONTEND_PORT`, `BACKEND_PORT`, `POSTGRES_PORT`, `QDRANT_HTTP_PORT`.
Không dùng `DATABASE_URL` trỏ `localhost` khi chạy backend trong container.

```powershell
docker compose -p se2026-t03-w7 -f docker-compose.yml config --quiet
docker compose -p se2026-t03-w7 -f docker-compose.yml up --build -d --wait --wait-timeout 180
powershell -NoProfile -File scripts/verify_docker_stack.ps1 -ProjectName se2026-t03-w7
```

Mở UI tại <http://127.0.0.1:8080>, API docs tại <http://127.0.0.1:8000/docs>.
Compose chạy PostgreSQL → migration `upgrade head` → backend → frontend;
Qdrant cần ready trước backend. Migration thành công là container `Exited (0)`,
bốn dịch vụ còn lại cần `healthy`. Dữ liệu dùng volume riêng theo tên project.

**Mặc định search/feedback vẫn là mock phát triển như cấu hình mẫu**; list/detail
đọc DB thật và DB mới có thể rỗng. UI production gọi HTTP API qua nginx cùng origin.
Health/smoke này chỉ nghiệm thu hạ tầng, không chứng minh semantic retrieval,
E2E #149, benchmark #150 hoặc W7 đã hoàn tất. Không tự seed/đổi index/dữ liệu đã khóa.

Xem [runbook máy sạch, chế độ search thật và cách dừng/dọn an toàn](docs/guides/docker-clean-setup-w7.md).
Nếu Windows chặn verifier bằng Execution Policy, dùng [cách gọi PowerShell cho riêng tiến trình](docs/guides/docker-clean-setup-w7.md#script-powershell-bị-chặn-trên-windows).

## Quy trình Git

Chuẩn bị tích hợp W7/W8: [bảng đầu vào, phần còn chờ và checklist phát hành](docs/release/w7-integration-readiness.md),
[bằng chứng từng lượt kiểm chứng #146](docs/evidence/issue146-integration-readiness.md).
Đây là trạng thái chuẩn bị; không coi smoke hạ tầng/mock là nghiệm thu E2E,
benchmark hoặc quyết định phát hành.

Quy trình nhóm 5 thành viên: `nhánh nhiệm vụ → develop → main`.

- [Quy tắc nhánh, PR và release](docs/BRANCHING.md)
- [Hướng dẫn đóng góp](CONTRIBUTING.md)

Chỉ `main` và `develop` tồn tại lâu dài. Mỗi Issue dùng nhánh ngắn 1–3 ngày.
