# Tổng hợp kiểm chứng W4 — Issue #92

Snapshot: home-interior-354-v1. Báo cáo được chuẩn bị ngày 07/11/2026; chưa có PR, CI hoặc approval được xác minh trong phiên này.

## Bằng chứng đã có

| Kiểm tra | Kết quả | Nguồn bằng chứng |
|---|---|---|
| Snapshot metadata tests | 4 passed trong 0.39s | Terminal do người dùng cung cấp |
| ZIP SHA-256 | a12bc29e1d5638e25eda9aab766e9324afdda1263fb6fbd3c14d2f17c30d4d25 | Terminal do người dùng cung cấp |
| SHA256SUMS toàn gói | Tất cả OK, mã thoát 0; bỏ CR trên luồng đọc | Người dùng xác nhận; log local work/issue92/package-checksums-lf.log |
| Metadata gói/repo | Manifest và annotations khớp byte; provenance/curation khớp JSON, khác định dạng | Terminal do người dùng cung cấp |
| Preview decode và trùng checksum | 354 file, 354 decode được, 354 checksum duy nhất, không lỗi | Terminal/ảnh kết quả do người dùng cung cấp |
| Bản ảnh dùng cho rà AI | 354/354 khớp SHA-256 curation | Agent kiểm tra trực tiếp bản local thay thế; xem visual-review.md |
| IDs và quan hệ snapshot | 354 IDs và cặp source/source_id duy nhất; 200 records mốc được giữ nguyên, 154 IDs bổ sung | build_coverage.py đã chạy trên metadata trong repo |
| Độ phủ | 67 nhãn reviewed_category_vi, không thiếu nhãn; 30 nhãn có 1–2 asset | category-coverage.csv và coverage-summary.json |
| Tổng bảng | Tổng 354; các cột mốc/bổ sung có tổng 200/154; từng hàng cộng đúng | Agent kiểm tra lại CSV sinh ra |
| Rà nghi trùng AI | 12 cặp: 11 keep_both, 1 uncertain; không đề xuất loại | duplicate-review.csv, visual-review.md, pairs-1/2/3.jpg |

Hash byte của bốn file metadata trong repo được lưu tại manifest-sha256.txt. Không dùng hash repo thay cho hash provenance/curation được đóng gói khác định dạng.

## Cách kiểm tra gói trên Git Bash

Sau khi xác nhận hash ZIP, từ gốc thư mục home-interior-354-v1 đã giải nén:

```bash
set -o pipefail
tr -d '\r' < SHA256SUMS | sha256sum -c -
```

Ảnh trong provenance/curation và ready manifest tính từ gốc gói giải nén. Tên gói: home-interior-354-v1.zip; checksum kèm: home-interior-354-v1.zip.sha256. Nhận gói qua kênh bàn giao của nhóm và tuân thủ license từng asset; báo cáo không tạo đường dẫn tải công khai mới.

## Giới hạn và việc cần xác nhận

- Không thay đổi thành phần snapshot, IDs, annotations, phân loại hoặc cấu hình dataset mặc định. Không tạo version mới chỉ vì thêm báo cáo. Nếu sau review phải loại asset, tạo version/changelog mới, giữ v1 đã bàn giao.
- Rà ảnh là AI, không phải xác nhận human_reviewed; 0/354 bản ghi có human_reviewed=true.
- Cặp ghế da cam trong visual-review.md còn uncertain. Chưa có dedup mesh hoặc rà toàn bộ cặp.
- Chi: chờ xác nhận CLIP/SigLIP 2 cùng snapshot/IDs/checksum.
- Quỳnh Anh: chờ đối chiếu IDs và metadata PostgreSQL phục vụ image search.
- Khuê: chờ chốt candidate IDs, nhãn/nguồn/license và cách xử lý cặp nghi trùng/biến thể cho #89/#90.
- Giữ benchmark text bộ 200 độc lập; không tự đổi sang 354.
- Chưa có bằng chứng CI trên PR, review độc lập hoặc merge. Không đánh dấu Issue hoàn thành chỉ từ báo cáo này.

## Tái lập thống kê

Từ gốc repo, dùng Python hiện có:

```bash
./backend/.venv/Scripts/python.exe docs/reports/issue92/build_coverage.py --repo . --output work/issue92-reproduced
```

Thống kê dùng thư viện chuẩn, giữ nguyên nhãn reviewed_category_vi, không gom từ đồng nghĩa. Xem category-coverage.md cho cách diễn giải và đề xuất nhóm cần bổ sung. candidate-assets.csv giữ thông tin nguồn/license từ manifest và category nguồn riêng.
