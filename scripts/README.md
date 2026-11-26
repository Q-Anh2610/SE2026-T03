# Scripts dùng chung

Script được chia theo trách nhiệm bằng tên rõ ràng, không gom nghiệp vụ ingestion/search vào thư mục này.

- `new-task-branch.sh`: tạo nhánh nhiệm vụ từ `origin/develop`.
- `python -m scripts.generate_objaverse_200`: tạo manifest subset Objaverse W1,
  kiểm tra preview và ghi provenance. Chạy từ gốc repo; cần kết nối mạng và Pillow.
  Mapping metadata nằm tại `backend/app/ingestion/objaverse.py`.
  Xem [hướng dẫn dữ liệu](../data/README.md#bàn-giao-source-reader-w1--issue-26).

Nhánh `develop` đã được tạo trên GitHub; không cần script khởi tạo nhánh chung. Bản clone cần remote `origin` đúng repo và fetch được `origin/develop` trước khi tạo nhánh nhiệm vụ.

Script dựng dữ liệu, tạo index và smoke hệ thống chỉ thêm khi module tương ứng đã có implementation. Logic nghiệp vụ nằm trong backend; scripts chỉ gọi/điều phối. Xem `docs/BRANCHING.md` trước khi chạy các script Git.

## Docker infrastructure smoke — Issue #148

`powershell -NoProfile -File scripts/verify_docker_stack.ps1 -ProjectName issue148-clean`
kiểm stack đã khởi chạy, revision migration, UI/proxy/API/PostgreSQL và Qdrant
readiness; ghi report nhỏ ngoài Git. Không seed, tải model, rebuild, benchmark hoặc
xác nhận retrieval thật. Xem [runbook máy sạch](../docs/guides/docker-clean-setup-w7.md).
