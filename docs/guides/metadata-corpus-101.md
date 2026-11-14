# Tái lập corpus metadata E5 — Issue #101

## 1. Phạm vi và trạng thái xác nhận

Recipe `e5-metadata-passage-v1-draft` đã được
[Lê Thị Linh Chi](https://github.com/LLC536) review và xác nhận
tại commit `a85c8fa` của PR #102. Corpus đã được tiếp nhận
để làm đầu vào cho bước build index E5.

[Bằng chứng xác nhận tại #91](https://github.com/Q-Anh2610/SE2026-T03/issues/91#issuecomment-6848528349).

Tên recipe version được giữ nguyên để truy vết bản đã tiếp nhận.
Trạng thái xác nhận dùng cho exporter là `recipe_confirmed`.

Script không tải weights, build index, đọc queries/qrels
hoặc cập nhật PostgreSQL/Qdrant.

## 2. Input

- Snapshot: `home-interior-clear-200-v3`.
- Manifest: `data/manifests/objaverse_200.json`.
- Số lượng: 200 asset.
- Source manifest SHA-256:
  `9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`.

Script đọc bytes của manifest từ Git HEAD để kiểm tra source hash,
đồng thời đối chiếu nội dung JSON với file checkout.

Hash bytes của checkout có thể khác do BOM/newline, nhưng nội dung
JSON phải khớp bản đã commit. Metadata thực sự khác sẽ bị từ chối.

## 3. Recipe được xác nhận

Recipe version: `e5-metadata-passage-v1-draft`.

- Thứ tự trường: `name` → `description` → `tags` → `category`.
- Chuỗi được gom whitespace thành một dấu cách, giữ nguyên
  hoa/thường và ngôn ngữ nguồn.
- Tags bỏ rỗng, dedup chính xác sau chuẩn hóa, giữ thứ tự
  xuất hiện đầu tiên và nối bằng `, `.
- Bỏ qua trường thiếu/null/rỗng.
- Từ chối sai kiểu dữ liệu hoặc passage hoàn toàn rỗng.
- Nối các phần bằng LF, không có newline cuối passage.
- Corpus chưa chứa prefix; encoder thêm `passage: ` đúng một lần.
- Asset ID nằm riêng với semantic passage.
- Không sử dụng nhãn curation, qrels, test queries hoặc caption
  sinh thêm để tạo passage.

## 4. Cách chạy

Cần Python và Git có trong PATH.
Exporter chỉ sử dụng thư viện chuẩn Python.

Từ gốc repository, trên nhánh chứa implementation:

```bash
python scripts/build_metadata_corpus.py \
  --repo . \
  --output work/issue101-corpus-review
```

Script dừng nếu source hash không khớp, checkout metadata thay đổi,
số lượng không đúng 200, ID không hợp lệ/trùng hoặc passage rỗng.

## 5. Output

Thư mục output gồm:

- `corpus.jsonl`: mỗi record gồm `asset_id` và `passage`.
- `manifest.json`: nguồn, recipe, IDs, coverage, serialization,
  trạng thái và corpus hash.

Quy ước corpus:

- JSONL UTF-8 không BOM.
- Record sắp theo `asset_id` tăng dần.
- JSON keys được sắp xếp; `ensure_ascii=False`;
  separators là `(",", ":")`.
- Mỗi record kết thúc bằng LF, có LF cuối file.
- Prefix E5 không nằm trong corpus.

Output được giữ local trong `work/`, không mặc định đưa vào Git.

## 6. Corpus đã được tiếp nhận

Bằng chứng tại commit `a85c8fa`:

- 200 asset IDs duy nhất.
- 200 passage không rỗng.
- Hai lần xuất corpus và manifest khớp bytes.
- Bên nhận đã chạy tái lập và xác nhận cùng corpus hash.

Corpus SHA-256:

`66efd87e34447c23b4171e13ac77d78a9c193519141d0dd6a31985c01e65b4f5`

Cập nhật trạng thái sang `recipe_confirmed` không thay đổi
recipe version hoặc nội dung corpus.

Manifest mới có thể khác bytes so với bản trước vì trạng thái
và source commit thay đổi. Corpus JSONL phải giữ nguyên hash trên.

## 7. Kiểm tra tính tái lập sau cập nhật trạng thái

Từ gốc repository:

```bash
python scripts/build_metadata_corpus.py \
  --repo . \
  --output work/issue101-confirmed-run1

python scripts/build_metadata_corpus.py \
  --repo . \
  --output work/issue101-confirmed-run2
```

Đối chiếu output:

```bash
cmp work/issue101-confirmed-run1/corpus.jsonl \
    work/issue101-confirmed-run2/corpus.jsonl

cmp work/issue101-confirmed-run1/manifest.json \
    work/issue101-confirmed-run2/manifest.json

sha256sum work/issue101-confirmed-run1/corpus.jsonl
```

Điều kiện đạt:

- Mỗi lần xuất có 200 asset và 200 passage không rỗng.
- Trạng thái là `recipe_confirmed`.
- Hai lệnh `cmp` có exit code 0.
- Corpus hash khớp mục 6.

So sánh manifest theo bytes áp dụng cho hai lần chạy trên cùng
revision và kiểu checkout. Không mặc định manifest giữ nguyên bytes
giữa các revision hoặc môi trường checkout khác nhau.

## 8. Kiểm thử

### Kết quả đã ghi nhận trước cập nhật trạng thái

- 16 corpus test cases local đạt.
- Toàn bộ unit tests ingestion: 164 passed trong 1,20 giây,
  exit code 0; đã bao gồm 16 corpus tests.
- Bên nhận chạy lại 16 corpus tests và xác nhận hash tại #91.
- CI trên commit `a85c8fa`: 5/5 checks đạt tại PR #102.

Các kết quả trên không tự chứng minh tests/CI của commit mới đã đạt.

### Chạy hồi quy sau khi sửa script/tests

Trong Git Bash tại gốc repository, dùng môi trường backend đã cài
dependencies:

```bash
source backend/.venv/Scripts/activate
mkdir -p work

corpus_test_tmp="$(mktemp -d "$PWD/work/pytest-confirmed-XXXXXX")"

python -m pytest backend/tests/unit/ingestion \
  --basetemp="$(cygpath -w "$corpus_test_tmp")" \
  --tb=short -q
```

Thư mục tạm riêng trong `work/` giúp tránh lỗi quyền truy cập
thư mục pytest mặc định đã gặp trên máy Windows.

### Kết quả sau cập nhật trạng thái

Đã kiểm chứng local sau khi sửa script/tests, trước commit cập nhật:

- Toàn bộ unit tests ingestion: 164 passed trong 1,45 giây;
  đã bao gồm 16 corpus tests.
- Hai lần export đều có 200 IDs duy nhất và 200 passage không rỗng.
- Trạng thái exporter: `recipe_confirmed`.
- Recipe version giữ nguyên: `e5-metadata-passage-v1-draft`.
- Hai lệnh `cmp` xác nhận corpus và manifest của hai lần export
  khớp bytes.
- SHA-256 corpus được kiểm tra độc lập bằng `sha256sum`, giữ nguyên:
  `66efd87e34447c23b4171e13ac77d78a9c193519141d0dd6a31985c01e65b4f5`.

Kết quả này không thay thế CI của commit cập nhật.
Không commit thư mục tạm hoặc log kiểm thử.

Các tests dùng fixture không thay thế kiểm chứng PostgreSQL/Qdrant thật.
Kết quả local, kiểm chứng của bên nhận và CI là các bằng chứng riêng.

### Môi trường kiểm chứng local

- Hệ điều hành: Windows.
- Terminal: Git Bash.
- Môi trường Python: `backend/.venv`.
- Python: `3.13.17`.
- pytest: `9.1.1`.
- Git: `2.56.0.windows.4`.

## 9. Phần còn lại của W5

- Đối chiếu metadata PostgreSQL/payload theo phạm vi thống nhất tại #101.
- Ghi nhận snapshot, database/schema và collection/named vector thực tế.
- Báo cáo IDs thiếu/thừa, metadata lệch và compatibility theo từng index.
- Phối hợp xử lý sai lệch nếu có.
- Hoàn tất CI mới nhất, review và tích hợp PR theo quy trình nhóm.

Phối hợp PostgreSQL:
[Vũ Nguyễn Quỳnh Anh](https://github.com/Q-Anh2610).

Phối hợp retrieval/index:
[Lê Thị Linh Chi](https://github.com/LLC536).

Xác nhận corpus không thay thế E5 weights smoke, index build
hoặc benchmark. Mâu thuẫn canonical query hash tại #91 được xử lý riêng.

Nếu recipe hoặc nội dung thay đổi về sau, cần version hóa phù hợp, cập nhật hashes/tests và xác nhận lại bên nhận.