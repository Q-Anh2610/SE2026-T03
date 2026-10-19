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

Backend có FastAPI skeleton, `GET /healthz`, cấu hình `.env`, pytest và Dockerfile.
Xem [hướng dẫn cài đặt, chạy và kiểm thử backend](backend/README.md).
`docker-compose.yml` khởi chạy backend; PostgreSQL, Qdrant và API nghiệp vụ chưa nằm trong skeleton này.
Xem [hướng dẫn frontend](frontend/README.md) cho giao diện hiện có.

## Quy trình Git

Quy trình nhóm 5 thành viên: `nhánh nhiệm vụ → develop → main`.

- [Quy tắc nhánh, PR và release](docs/BRANCHING.md)
- [Hướng dẫn đóng góp](CONTRIBUTING.md)

Chỉ `main` và `develop` tồn tại lâu dài. Mỗi Issue dùng nhánh ngắn 1–3 ngày.
