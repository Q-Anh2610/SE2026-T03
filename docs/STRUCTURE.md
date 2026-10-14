# Cấu trúc repository

Khung ban đầu theo ROADMAP, phục vụ phân công nhóm; `.gitkeep` giữ thư mục chưa có file trong Git. Khi thêm file thật, có thể xóa `.gitkeep` cùng thư mục. Đây chưa phải milestone hoàn thành.

```text
SE2026-T03/
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/{search,assets,feedback,admin}/
│   │   ├── lib/api/
│   │   └── types/
│   └── tests/e2e/
├── backend/
│   ├── app/{api,schemas,core,db,services,ingestion,embedding,search}/
│   ├── migrations/
│   └── tests/{unit,integration}/
├── evaluation/{metrics,configs,results,tests}/
├── data/
│   ├── manifests/
│   ├── samples/
│   ├── benchmark/
│   └── {raw,processed,models,runtime}/  # chỉ local, không commit
├── scripts/
├── docs/{requirements,architecture,contracts,adr,guides,evaluation}/
├── .github/workflows/
├── .env.example
├── .gitignore
├── AGENTS.md
├── CONTRIBUTING.md
├── README.md
└── ROADMAP.md
```

Ký hiệu `{a,b}` trong sơ đồ là các thư mục riêng `a/`, `b/`, không phải tên thư mục có dấu ngoặc.

Frontend → HTTP API; API → services/persistence/search; ingestion và search → encoder chung. Evaluation dùng search của sản phẩm. Metadata nghiệp vụ nằm ở PostgreSQL, vector ở Qdrant; không dùng file trong `data/` thay thế persistence nghiệp vụ.

Không tạo sẵn entrypoints, endpoint giả, migration rỗng, package manifests hoặc lockfiles khi chưa triển khai module. `compose.yaml` ở gốc sẽ được Đoàn Thị Minh Khuê phối hợp Vũ Nguyễn Quỳnh Anh thêm khi có cấu hình khởi chạy thật. Reviewer cụ thể/CODEOWNERS cần GitHub usernames thật; không dùng họ tên thay cho GitHub username.
