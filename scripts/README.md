# Scripts dùng chung

Script được chia theo trách nhiệm bằng tên rõ ràng, không gom nghiệp vụ ingestion/search vào thư mục này.

- `new-task-branch.sh`: tạo nhánh nhiệm vụ từ `origin/develop`.

Nhánh `develop` đã được tạo trên GitHub; không cần script khởi tạo nhánh chung. Bản clone cần remote `origin` đúng repo và fetch được `origin/develop` trước khi tạo nhánh nhiệm vụ.

Script dựng dữ liệu, tạo index và smoke hệ thống chỉ thêm khi module tương ứng đã có implementation. Logic nghiệp vụ nằm trong backend; scripts chỉ gọi/điều phối. Xem `docs/BRANCHING.md` trước khi chạy các script Git.
