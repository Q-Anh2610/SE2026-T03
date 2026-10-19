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
│   ├── app/{api,schemas,core,models,db,services,ingestion,embedding,search}/
│   ├── alembic/versions/
│   ├── alembic.ini
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
├── docker-compose.yml
├── .gitignore
├── AGENTS.md
├── CONTRIBUTING.md
├── README.md
└── ROADMAP.md
```

Ký hiệu `{a,b}` trong sơ đồ là các thư mục riêng `a/`, `b/`, không phải tên thư mục có dấu ngoặc.

Frontend → HTTP API; API → services/persistence/search; ingestion và search → encoder chung. Evaluation dùng search của sản phẩm. Metadata nghiệp vụ nằm ở PostgreSQL, vector ở Qdrant; không dùng file trong `data/` thay thế persistence nghiệp vụ.

Backend có entrypoint `app/main.py`, router `/healthz`, settings, ORM models, Alembic, seed, tests và Dockerfile. `docker-compose.yml` khởi chạy backend và PostgreSQL. Alembic dùng `backend/alembic` theo Issue #8, thay khung `backend/migrations` ban đầu. Xem `docs/guides/database.md` để chạy migration/seed. Quỳnh Anh phối hợp Khuê khi thêm dịch vụ; reviewer cụ thể/CODEOWNERS cần GitHub usernames thật.
