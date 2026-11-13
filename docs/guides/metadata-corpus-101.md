# Tái lập corpus metadata draft — Issue #101

## Phạm vi

Corpus phục vụ thử nghiệm E5/RRF tại #91.
Recipe hiện là `e5-metadata-passage-v1-draft`, chờ xác nhận.

Script không tải weights, build index, đọc queries/qrels
hoặc cập nhật PostgreSQL/Qdrant.

## Input

- Snapshot: `home-interior-clear-200-v3`.
- Manifest: `data/manifests/objaverse_200.json`.
- Số lượng: 200 asset.
- Source manifest SHA-256:
  `9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`.

Script kiểm tra bytes của manifest trong Git HEAD và đối chiếu
nội dung JSON với checkout. Hash checkout có thể khác do newline;
metadata thực sự thay đổi sẽ bị từ chối.

## Cách chạy

Từ gốc repository, trên nhánh chứa implementation:

```bash
python scripts/build_metadata_corpus.py \
  --repo . \
  --output work/issue101-corpus-review
```

Script dùng thư viện chuẩn Python và cần Git có trong PATH.

## Output

- `corpus.jsonl`: mỗi record gồm `asset_id` và `passage`.
- `manifest.json`: nguồn, recipe, IDs, coverage, serialization và hash.
- Corpus không chứa prefix; encoder thêm `passage: ` đúng một lần.
- Output giữ local trong `work/`.

Kết quả đã ghi nhận trên commit `a85c8fa`:

- 200 IDs duy nhất.
- 200 passage không rỗng.
- Corpus SHA-256:
  `66efd87e34447c23b4171e13ac77d78a9c193519141d0dd6a31985c01e65b4f5`.

## Kiểm tra tính tái lập

Chạy exporter với hai thư mục output khác nhau, sau đó:

```bash
cmp work/issue101-corpus-run1/corpus.jsonl work/issue101-corpus-run2/corpus.jsonl
cmp work/issue101-corpus-run1/manifest.json work/issue101-corpus-run2/manifest.json
```

Hai lần kiểm chứng đã khớp bytes trên cùng revision và môi trường.
Manifest chứa source commit và checkout hash, nên không mặc định
manifest có cùng bytes giữa các revision hoặc kiểu checkout khác nhau.

## Bằng chứng kiểm thử

- Corpus unit tests: 16 passed.
- Toàn bộ unit tests ingestion: 164 passed trong 1,20 giây,
  exit code 0.
- CI trên commit `a85c8fa`: 5/5 checks đạt tại PR #102.

Các tests dùng fixture không thay thế kiểm chứng PostgreSQL/Qdrant thật.
CI và kết quả local là hai nguồn bằng chứng riêng.

## Trạng thái bàn giao

- Recipe chưa được xác nhận.
- Bên nhận chưa xác nhận tái lập/tiếp nhận corpus.
- Chưa hoàn thành đối chiếu PostgreSQL/payload thuộc #101.
- Chưa có E5 weights smoke, index E5 hoặc benchmark từ phần việc này.

Nếu recipe thay đổi, cần cập nhật version, corpus hash, tests và tài liệu tương ứng.