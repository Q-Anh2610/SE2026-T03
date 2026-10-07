# SE2026-T03

Semantic Search cho thư viện 3D assets: tìm bằng văn bản/ảnh, sử dụng React + TypeScript, FastAPI, PostgreSQL và Qdrant.

## Cấu trúc repository

| Đường dẫn | Nội dung | Người chủ trì |
|---|---|---|
| `frontend/` | Ứng dụng React + TypeScript | TV4 |
| `backend/` | API, nghiệp vụ, ingestion, embedding và search | TV1, TV2, TV3 |
| `evaluation/` | Benchmark, cấu hình thí nghiệm và kết quả nhỏ | TV5 |
| `data/` | Manifest, mẫu, nhãn benchmark; dữ liệu lớn chỉ lưu local | TV2, phối hợp TV5 cho nhãn |
| `scripts/` | Công cụ dùng chung; script riêng module đặt cạnh module | Theo module |
| `docs/` | Yêu cầu, kiến trúc, contract, ADR và đóng góp | Cả nhóm |
| `.github/` | CI và mẫu Issue/PR | TV5 |
| `.env.example` | Mẫu cấu hình local, chỉ có giá trị giả | TV1, TV5 |
| `.gitignore` | Loại secret, dữ liệu lớn và file sinh tự động | TV5 |
| `README.md` | Giới thiệu và hướng dẫn chạy | TV1 tổng hợp |

Xem [sơ đồ thư mục và ranh giới module](docs/STRUCTURE.md), [kế hoạch](ROADMAP.md) và [hướng dẫn Codex](AGENTS.md).

Hiện repository mới có khung thư mục và quy trình Git; chưa có ứng dụng, dependencies hoặc lệnh chạy backend/frontend.
`compose.yaml` sẽ được bổ sung ở nhiệm vụ CI/Docker khi có cấu hình dịch vụ thực tế; không tạo file Compose rỗng để giả định hệ thống đã chạy được.

## Quy trình Git

Quy trình nhóm 5 thành viên: `nhánh nhiệm vụ → develop → main`.

- [Quy tắc nhánh, PR và release](docs/BRANCHING.md)
- [Hướng dẫn đóng góp](CONTRIBUTING.md)

Chỉ `main` và `develop` tồn tại lâu dài. Mỗi Issue dùng nhánh ngắn 1–3 ngày.
