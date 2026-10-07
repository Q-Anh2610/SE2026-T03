# Dữ liệu — TV2 phối hợp TV5

| Thư mục | Nội dung | Đưa vào Git? |
|---|---|---|
| `manifests/` | Asset IDs, metadata/provenance và dataset snapshot manifest | Có, nếu nhỏ và không chứa secret |
| `samples/` | Mẫu nhỏ phục vụ phát triển/tests, có nguồn/license | Có |
| `benchmark/` | Query, nhãn relevance và split đã xác nhận | Có |
| `raw/` | Dataset/ảnh/mesh tải về | Không |
| `processed/` | Dữ liệu xử lý, embeddings trung gian | Không |
| `models/` | Model weights/checkpoints tải về | Không |
| `runtime/` | Storage local PostgreSQL/Qdrant và jobs khi cấu hình | Không |

Các thư mục local đã có trong workspace nhưng bị `.gitignore` loại trừ; bản clone khác tạo lại khi pipeline cần. Không coi mẫu rỗng là dataset đã thu thập. Không tải dataset/model trong bước tổ chức thư mục.
