# Dataset card — Objaverse interior subset

## 1. Mục đích và phạm vi

Dataset phục vụ semantic search cho thư viện 3D assets nội thất và
đồ gia dụng, sử dụng preview ảnh và metadata.

Không mặc định toàn bộ mesh/model 3D đã được tải hoặc kiểm chứng.

Người phụ trách:
[Trịnh Thị Thu Huyền](https://github.com/TrinhHuyen05).

Issue W5: #101.
Bằng chứng kiểm chứng dữ liệu W4: #92 và PR #94.

## 2. Nguồn dữ liệu và license

Nguồn dữ liệu là Objaverse, kèm metadata và liên kết nguồn của từng asset.

Thông tin truy vết được lưu trong:

- `asset_id`: định danh trong hệ thống.
- `source`, `source_id`: nguồn và định danh gốc.
- `source_url`: liên kết trang nguồn.
- `author`, `license`: tác giả và license theo metadata nguồn.

Các file annotations giữ metadata nguồn; manifest chứa record đã chuẩn hóa.
Provenance và curation đi kèm ghi thông tin chuẩn bị dữ liệu, preview,
checksum và quyết định giữ asset.

License của repository không mặc định áp dụng cho mọi asset.
Khi sử dụng hoặc phân phối lại, cần kiểm tra license và yêu cầu
attribution của từng asset tại nguồn tương ứng.

## 3. Các snapshot

### home-interior-clear-200-v3

- Số lượng: 200 asset.
- Manifest: `data/manifests/objaverse_200.json`.
- Phạm vi: candidate cho benchmark text hiện có, benchmark ảnh v1
  và thử nghiệm text E5/RRF tại #91.

SHA-256 bytes của manifest:

`9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`

### home-interior-354-v1

- Số lượng: 354 asset.
- Manifest: `data/manifests/home-interior-354-v1/assets_354.json`.
- Thành phần: giữ nguyên 200 record mốc và bổ sung 154 asset.
- Phạm vi: snapshot mở rộng phục vụ retrieval W4.

SHA-256 bytes của manifest:

`93f65237ca51060aad75f0f672b2b16f76c89a64dce64d7473791f428e944614`

### Quy tắc sử dụng

Hai snapshot không thay thế nhau trong cùng một phép đánh giá.
Không dùng index 354 để báo kết quả benchmark có candidate universe 200.

Không ghi đè snapshot đã bàn giao. Nếu thay đổi thành phần hoặc nội dung
dữ liệu, cần version mới, changelog và đối chiếu lại các bên sử dụng.

Hash bytes phụ thuộc nội dung và định dạng file. Không tự coi các file
khớp nội dung JSON nhưng khác serialization là có cùng SHA-256.

## 4. Metadata và giá trị thiếu

Manifest gồm 18 trường:

| Nhóm | Trường |
|---|---|
| Định danh và provenance | `asset_id`, `source`, `source_id`, `source_url`, `author`, `license` |
| Nội dung | `name`, `description`, `tags`, `category` |
| Tài nguyên và thuộc tính | `thumbnail_path`, `model_path`, `formats`, `face_count`, `checksum` |
| Trạng thái và version | `ingestion_status`, `model_version`, `index_version` |

Giá trị thiếu được giữ theo schema hiện có. Không tự tạo mô tả,
license, category hoặc thuộc tính hình học để lấp dữ liệu thiếu.

`category` từ nguồn được phân biệt với nhãn curation.
Không tự dùng `reviewed_category_vi` thay cho category của filters.

Các trường trạng thái trong source manifest không tự chứng minh
trạng thái hiện tại của PostgreSQL hoặc Qdrant.

### Coverage metadata của bộ 200

| Trường | Số asset có nội dung |
|---|---:|
| `name` | 200/200 |
| `description` | 120/200 |
| `tags` | 135/200 |
| `category` | 130/200 |

Coverage trên được tính từ manifest nguồn, không phải kết quả đánh giá
chất lượng passage hoặc retrieval.

## 5. Kiểm tra chất lượng và giới hạn

Bằng chứng W4 tại #92/PR #94 ghi nhận:

- Bộ 354 có asset ID và cặp source/source_id duy nhất.
- Có 354 preview decode được và 354 checksum ảnh duy nhất.
- Có 67 nhãn `reviewed_category_vi`, không thiếu nhãn.
- Có 30 nhãn chỉ chứa 1–2 asset.
- Nhãn có độ chi tiết khác nhau; chưa coi là 67 lớp độc lập.
- Dữ liệu chưa cân bằng danh mục.

Rà preview bằng AI ghi nhận 12 cặp được xem phóng lớn:
11 `keep_both`, 1 `uncertain`; chưa đề xuất loại asset.

Rà bằng AI không phải xác nhận human review.
Không trùng checksum ảnh không chứng minh các mesh độc lập.

Chi tiết cặp uncertain, biến thể và giới hạn:
`docs/reports/issue92/visual-review.md`.

Thống kê độ phủ:
`docs/reports/issue92/category-coverage.md`.

Báo cáo tổng hợp:
`docs/reports/issue92/audit.md`.

## 6. Dữ liệu đánh giá

### Benchmark ảnh

- Version: `home-interior-image-v1`.
- Candidate snapshot: `home-interior-clear-200-v3`, 200 asset.
- Query: 20 `similarity`, 0 `same_id`.
- Split: 8 validation, 12 test, chia theo query group.
- Qrels: 4.000 cặp query–asset.

Cấu hình, hashes và trạng thái khóa:
`data/benchmark/image_benchmark_v1.yaml`.

Không suy ra khả năng tìm đúng cùng asset ID từ bộ chỉ có similarity.
Preflight index, nhãn và split không tự thay thế kết quả benchmark.

### Benchmark text

Benchmark text có cấu hình riêng:
`data/benchmark/manifest.yaml`.

Theo protocol đang trao đổi tại #91, thử nghiệm W5 chỉ dùng
28 validation query tiếng Anh trên candidate 200.
Không dùng 42 test query để chọn passage, model hoặc tham số fusion.

Mâu thuẫn hash query canonical đã được ghi tại #91 và cần xác nhận riêng.
Dataset card này không giải quyết hoặc thay đổi hash đang khóa.

### Nguyên tắc

- Không sửa queries/qrels/test đã khóa để phù hợp kết quả mô hình.
- Không dùng nhãn hoặc test queries để tạo metadata passage.
- Không coi category hoặc thứ hạng model là relevance ground truth.
- Ghi rõ snapshot, filters, versions và giới hạn của từng phép đánh giá.

## 7. Corpus metadata E5 — công việc W5

### Nguồn và recipe đã được xác nhận

Corpus sử dụng manifest cố định của snapshot
`home-interior-clear-200-v3`:

`data/manifests/objaverse_200.json`

Source manifest SHA-256:

`9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`

[Lê Thị Linh Chi](https://github.com/LLC536) đã review, chạy tái lập
tại commit `a85c8fa` của PR #102, xác nhận recipe và tiếp nhận corpus.

[Bằng chứng xác nhận tại #91](https://github.com/Q-Anh2610/SE2026-T03/issues/91#issuecomment-6848528349).

Recipe version giữ nguyên: `e5-metadata-passage-v1-draft`.
Tên version chứa `draft` được giữ để truy vết đúng bản đã tiếp nhận.

### Quy tắc tạo passage

- Thứ tự trường: `name` → `description` → `tags` → `category`.
- Chuỗi được bỏ khoảng trắng đầu/cuối và gom mỗi dãy whitespace
  thành một dấu cách; giữ nguyên hoa/thường và ngôn ngữ nguồn.
- Tags được chuẩn hóa, bỏ rỗng, dedup chính xác sau chuẩn hóa,
  giữ thứ tự xuất hiện đầu tiên và nối bằng `, `.
- Bỏ qua trường thiếu/null/rỗng; từ chối sai kiểu dữ liệu
  hoặc passage hoàn toàn rỗng.
- Các phần có nội dung được nối bằng LF, không có newline cuối passage.
- Corpus chưa chứa prefix; encoder thêm `passage: ` đúng một lần.
- Không đưa asset ID, license, formats, nhãn curation, qrels
  hoặc caption sinh thêm vào semantic passage.
- Asset ID được lưu riêng để mapping và truy provenance.

Không âm thầm loại asset có metadata lỗi hoặc passage rỗng.
Hash manifest nguồn không phải hash corpus.

### Corpus được tiếp nhận

- Recipe: `e5-metadata-passage-v1-draft`.
- Commit triển khai được bên nhận kiểm chứng: `a85c8fa`.
- Có 200 record, 200 asset IDs duy nhất và 200 passage không rỗng.
- JSONL dùng UTF-8 không BOM, sắp xếp theo asset ID tăng dần,
  có LF cuối file.
- Hai lần export trên cùng revision và môi trường đã tạo corpus
  và manifest khớp bytes.
- Corpus SHA-256:
  `66efd87e34447c23b4171e13ac77d78a9c193519141d0dd6a31985c01e65b4f5`.
- Script: `scripts/build_metadata_corpus.py`.
- Output kiểm chứng nằm trong `work/`, không đưa vào Git.

Trạng thái xác nhận dùng cho exporter là `recipe_confirmed`.
Việc cập nhật trạng thái không thay đổi recipe version,
serialization hoặc nội dung corpus.

Manifest có thể khác bytes so với bản trước do trạng thái và source
commit thay đổi; corpus JSONL phải giữ nguyên SHA-256 nêu trên.

### Kiểm thử và bằng chứng

Các kết quả đã ghi nhận trước lần cập nhật trạng thái:

- 16 corpus test cases đạt trên môi trường local.
- Toàn bộ unit tests ingestion: 164 passed trong 1,20 giây,
  exit code 0; số này đã bao gồm 16 corpus tests.
- Bao phủ thứ tự trường, whitespace, tags/dedup, null/rỗng,
  sai kiểu dữ liệu, ID trùng/không hợp lệ, sai số lượng,
  source hash sai và checkout metadata bị thay đổi.
- Kiểm tra đúng IDs, UTF-8 không BOM, LF, corpus hash
  và tính độc lập với thứ tự input.
- Pytest dùng thư mục tạm riêng trong `work/` vì thư mục
  pytest mặc định của Windows bị lỗi quyền truy cập.
- Bên nhận đã chạy lại 16 corpus tests và xác nhận hash tại #91.

### Kiểm chứng sau cập nhật trạng thái

- Toàn bộ unit tests ingestion: 164 passed trong 1,45 giây;
  số này đã bao gồm 16 corpus tests.
- Hai lần export đều có 200 IDs duy nhất và 200 passage không rỗng.
- Trạng thái exporter: `recipe_confirmed`.
- Corpus và manifest của hai lần export khớp bytes qua `cmp`.
- Recipe version giữ nguyên: `e5-metadata-passage-v1-draft`.
- SHA-256 corpus được kiểm tra độc lập bằng `sha256sum`, giữ nguyên:
  `66efd87e34447c23b4171e13ac77d78a9c193519141d0dd6a31985c01e65b4f5`.
- Kết quả này được ghi nhận sau khi sửa trạng thái trong script/tests,
  trước commit cập nhật; chưa thay thế CI của commit mới.

Kết quả local, kiểm chứng của bên nhận và CI được ghi nhận riêng.

### Phạm vi xác nhận và phần còn lại

Xác nhận tại #91 chỉ áp dụng cho recipe/corpus.
Không chứng minh PostgreSQL/Qdrant đã được đối chiếu,
index E5 đã được build hoặc benchmark đã chạy.

Phần đối chiếu metadata/payload tiếp tục theo #101.
Nếu recipe hoặc nội dung thay đổi, cần version hóa phù hợp,
cập nhật hashes/tests và xác nhận lại bên nhận.

Hướng dẫn tái lập và bằng chứng kiểm chứng:
[metadata-corpus-101.md](guides/metadata-corpus-101.md).

## 8. PostgreSQL và payload index — công việc W5

PostgreSQL lưu metadata nghiệp vụ; payload Qdrant phục vụ retrieval
và filters. Source manifest là input có phiên bản để đối chiếu,
không tự chứng minh hai hệ lưu trữ đang đồng bộ.

Trước khi cập nhật cần thống nhất:

- Snapshot và index cần đối chiếu.
- Các trường phải đồng bộ và nguồn dữ liệu có thẩm quyền.
- Cách xử lý bản ghi thiếu/thừa hoặc giá trị sai lệch.
- Quy tắc retry, idempotency và ghi nhận lỗi.

Chưa có báo cáo reconciliation W5 được xác nhận trong dataset card này.
Không tự ghi đè index dùng chung hoặc đánh dấu đồng bộ thành công
khi một bước thất bại.

Phối hợp PostgreSQL:
[Vũ Nguyễn Quỳnh Anh](https://github.com/Q-Anh2610).

Phối hợp payload/index:
[Lê Thị Linh Chi](https://github.com/LLC536).

## 9. Nhận dữ liệu và tái lập

Preview bulk và ZIP được nhận qua kênh bàn giao của nhóm,
không lưu toàn bộ trong Git.

Với gói snapshot, kiểm tra checksum ZIP và từng file theo provenance
và `SHA256SUMS`. Đường dẫn preview tính từ gốc gói đã giải nén.

### Kiểm tra hash manifest

Từ gốc repository, chạy trong Git Bash:

    sha256sum data/manifests/objaverse_200.json
    sha256sum data/manifests/home-interior-354-v1/assets_354.json

Đối chiếu kết quả với hash ở mục 3.

Nếu không khớp, kiểm tra đúng revision và quy ước checkout/newline;
không tự sửa hash tham chiếu để cho qua kiểm tra.

### Tái lập thống kê bộ 354

Từ gốc repository:

    python docs/reports/issue92/build_coverage.py --repo . --output work/issue92-reproduced

Đối chiếu output với các báo cáo trong:
`docs/reports/issue92/`.

Lệnh trên kiểm tra và thống kê metadata; không tự kiểm chứng preview
local, trạng thái PostgreSQL hoặc payload Qdrant.

Output trong `work/` phục vụ kiểm tra local, không mặc định đưa vào PR.

## 10. Lưu trữ và thay đổi

Không commit secret, bulk preview, ZIP dữ liệu, model weights,
embedding dumps hoặc Qdrant storage.

Mỗi thay đổi dữ liệu cần ghi phạm vi, lý do, version và ảnh hưởng
đến corpus/index/benchmark. Không chỉnh dữ liệu đã khóa theo kết quả test.

Phối hợp tính tái lập và inputs benchmark:
[Đoàn Thị Minh Khuê](https://github.com/doanminhkhue25).