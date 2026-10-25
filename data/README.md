# Dữ liệu — Trịnh Thị Thu Huyền phối hợp Đoàn Thị Minh Khuê

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

## Bàn giao source reader W1 — Issue #26

`manifests/objaverse_200.json` chứa **200 asset ID duy nhất** lấy từ metadata
Objaverse 1.0 trên Hugging Face, revision
`556637099bf4fa79ea7b239d0d9c328b8a2e9ac8`, shard `000-000` (5.000 annotations).
Thay manifest cũ một bản ghi chưa có bằng chứng nguồn. ID mới có dạng
`objaverse_<uid>`; không tái sử dụng ID đánh số thứ tự `objaverse_001`.

- `objaverse_200.annotations.json`: giữ nguyên annotation nguồn của 200 asset đã chọn.
- `objaverse_200.provenance.json`: URL/hash shard, hash manifest/annotations,
  thời điểm kiểm tra, hash/kích thước preview, số bản ghi bị loại và lỗi preview.
- Chọn theo UID tăng dần, keyword từ name/category/tags, loại age-restricted,
  yêu cầu license nguồn và preview decode được. Đây là **lọc tự động**, chưa phải
  review ngữ nghĩa thủ công hoặc ground truth benchmark. Một asset có thể là
  cảnh/bộ đồ nội thất; cần rà soát thủ công trước khi chốt tập benchmark.
- Có 200 preview tải/kiểm tra thành công; 11 ứng viên lỗi preview bị loại trong lần
  thu thập này. Preview không lưu vào Git. Không tải mesh/model hoặc tạo index.
- Giữ nguyên token license nguồn: `by` (177), `by-nc` (11), `by-sa` (8),
  `by-nc-sa` (4). Không tự gán một phiên bản CC cụ thể. Attribution tác giả và URL
  nguồn nằm trong từng record; mọi sử dụng/phân phối tiếp theo theo license từng asset.
- `face_count` giữ giá trị `faceCount` nguồn; chưa xác nhận tương đương số tam giác
  trong file GLB. `formats` chỉ lấy archive có type tương ứng, bỏ nhãn `source`.
- `model_path`, `checksum`, model/index version để null vì chưa tải model/lập index.
  Hash **preview** nằm riêng trong provenance, không dùng thay checksum model.
- Trạng thái manifest vẫn là `PENDING` theo reader W1, chưa searchable. DB hiện mặc
  định `pending`; cần thống nhất mapping trạng thái với Quỳnh Anh khi nối DB ở W2.

### Tái tạo và kiểm tra

Chạy từ gốc repository, trong môi trường đã cài dependencies backend và pytest.
Script dùng Pillow đã có trong dependencies, không cần cài SDK Objaverse.

```powershell
python -m scripts.generate_objaverse_200
python -m pytest backend/tests/unit/ingestion -q
```

CLI chỉ tải shard metadata chỉ định, cache tại `data/raw/objaverse/`, tối đa sáu
preview đồng thời, giới hạn 2 MiB/ảnh và 4096 px/chiều. Chỉ dùng preview HTTPS từ
`media.sketchfab.com`; kiểm tra nội dung bằng Pillow. Không truy cập mạng khi
import module hoặc chạy unit tests. Có thể dùng `--count`, `--output`,
`--cache-dir`, `--revision` (commit SHA), `--shards` để tạo subset khác.
Không đủ số asset hợp lệ thì CLI trả mã lỗi và giữ manifest cũ.

Metadata revision đã pin, nhưng preview là tài nguyên ngoài có thể đổi/mất;
chạy lại có thể chọn ID khác nếu preview hỏng. Dùng bộ manifest/annotation/provenance
đã bàn giao để đối chiếu snapshot; không coi chạy lại mạng là snapshot bất biến.
File JSON dùng LF theo `.gitattributes` để hash giữ ổn định qua các hệ điều hành.

Reader trim chuỗi, chuẩn hóa tags/formats và lọc trùng theo cả `asset_id` lẫn
`(source, source_id)` trong một lần gọi; bản ghi lỗi không chiếm ID. Reader không
gọi mạng và không thực hiện idempotent upsert DB. Download/cleaning batch, retry,
checksum model và persistence thuộc W2.