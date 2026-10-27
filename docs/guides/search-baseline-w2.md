# Baseline W2 — Issue #39

Trạng thái: baseline cấp module; chưa nghiệm thu index 200 ảnh thật.
Bằng chứng kiểm chứng ngày 27/10/2026.

## Phạm vi

- CLIP batch encoder dùng `openai/clip-vit-base-patch32`.
- Batch runner nhận metadata và ảnh local, trả kết quả theo asset.
- Qdrant store tạo collection, kiểm tra compatibility và upsert.
- Keyword baseline tìm trong name, description và tags.
- Chưa nối các module này vào HTTP Search API hoặc PostgreSQL.

## Modules

| Module | Cách dùng |
|---|---|
| `backend/app/embedding/clip_encoder.py` | Tạo một `CLIPEncoder`, tái sử dụng qua các batch |
| `backend/app/embedding/batch.py` | `embed_assets(assets, encoder, batch_size=8)` |
| `backend/app/search/qdrant_store.py` | `QdrantStore.ensure_collection()` và `upsert(report.embedded)` |
| `backend/app/search/keyword.py` | `KeywordBaseline(records).search(query, limit=12)` |

## Model và versioning

- Model: `openai/clip-vit-base-patch32`.
- Revision: `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`.
- Dimension: 512.
- Preprocessing version: `clip-slow-processor-rgb-l2-v1`.
- Processor: cùng checkpoint/revision, `use_fast=False`, ảnh chuyển RGB.
- Embeddings chuẩn hóa L2; Qdrant dùng cosine similarity.
- Model chỉ nạp khi khởi tạo encoder; runner tái sử dụng instance.
- Dependencies trực tiếp: torch 2.8.0, transformers 4.57.1,
  qdrant-client 1.15.1; dependencies gián tiếp được pin trong requirements.

`IndexConfig` gồm model/revision, dimension, preprocessing version,
dataset snapshot và index version. Tên named vector chứa fingerprint
cấu hình. Collection không tương thích bị từ chối, không tự xóa/rebuild.

Point ID được tạo ổn định từ asset ID. Chạy lại cập nhật cùng point.
Payload lưu metadata và thông tin cấu hình thực tế trong `_index`.

## Đầu vào batch

Mỗi `AssetImage` gồm:

- `metadata`: bản ghi đã chuẩn hóa từ ingestion, có asset ID ổn định.
- `image_path`: `Path` đến ảnh local đã được bàn giao.

Giữ nguyên URL/provenance trong metadata; đường dẫn ảnh local nằm riêng
trong `image_path`. Batch runner không tải URL.

Giới hạn ảnh: 2 MiB/file, tối đa 4096 px mỗi chiều; kiểm tra bằng Pillow.
Ảnh lỗi được ghi nhận riêng. Nếu inference một batch lỗi, runner thử
từng ảnh để giữ kết quả của các asset hợp lệ.

`BatchReport.summary` gồm embedded, failed, skipped. Embedded chỉ xác nhận
đã tạo vector. Runner/store chưa cập nhật trạng thái searchable trong DB.

## Keyword baseline

Config version: `keyword-token-overlap-v1`.

- Chuẩn hóa Unicode NFKC và casefold, giữ dấu.
- Khớp token trong name, description và tags.
- Score là số token truy vấn khác nhau khớp metadata.
- Xếp score giảm dần; đồng điểm xếp asset ID tăng dần.
- Mỗi asset xuất hiện tối đa một lần.
- Query sau trim: 1–500 ký tự; limit: số nguyên 1–50.
- Chưa tích hợp filters hoặc HTTP API trong W2.
- Không coi score là phần trăm chính xác hoặc chất lượng semantic.

## Chạy Qdrant local bằng Git Bash

Cần Docker Desktop với Linux Engine đang chạy.
Chạy từ gốc repository:

```bash
MSYS_NO_PATHCONV=1 docker run -d --name ai04-qdrant-issue39 -p 127.0.0.1:6333:6333 --mount type=volume,source=ai04-qdrant-issue39,target=/qdrant/storage qdrant/qdrant:v1.15.1
curl --fail --silent --show-error http://127.0.0.1:6333/
```

Lệnh `docker run` dành cho lần tạo container đầu tiên.
Những lần sau khởi động container đã tạo:

```bash
docker start ai04-qdrant-issue39
```

Dừng container, giữ dữ liệu trong volume:

```bash
docker stop ai04-qdrant-issue39
```

## Kiểm chứng đã thực hiện

Môi trường: Windows, Python 3.13.7, torch 2.8.0+cpu,
Qdrant server 1.15.1, Docker Linux Engine.

| Kiểm tra | Kết quả quan sát |
|---|---|
| Encoder unit tests | 15 passed |
| Batch runner unit tests | 16 passed |
| Qdrant local-mode tests | 22 passed |
| Keyword unit tests | 29 passed |
| Toàn bộ tests không có marker integration | 251 passed, 15 deselected |
| CLIP thật trên 2 ảnh tự tạo | 2 vector, 512 chiều, norm xấp xỉ 1 |
| CLIP → batch → Qdrant server | 2 embedded, 0 failed, 0 skipped |
| Upsert cùng 2 asset hai lần | Tổng point vẫn là 2 |
| Keyword fixture `red` | Trả `fixture-red` |
| Keyword `wooden chair` trên 200 metadata | Top 5 có score 2, 2, 1, 1, 1 |

Chạy tests từ gốc repository:

```bash
./backend/.venv/Scripts/python.exe -m pytest backend/tests -m "not integration"
```

Smoke server đã dùng collection riêng `issue39_clip_smoke_v1`,
dataset snapshot `fixture-red-blue-v1`, index version `smoke-v1`.
Đây là fixtures tự tạo, không phải bộ Objaverse đã index.

Kết quả keyword thật được lưu local tại
`data/processed/issue39/keyword_smoke.json`, gồm SHA-256 manifest,
config version, query và kết quả. Thư mục processed được Git ignore.

## Việc còn chờ

- Huyền bàn giao ảnh preview local và metadata đã xử lý cho 200 asset.
- Đối chiếu snapshot, ID, đường dẫn ảnh và provenance khi nhận dữ liệu.
- Index 200 asset thật, chạy lại và ghi counts/lỗi thực tế.
- Khuê phối hợp nhãn và đo Recall/nDCG bằng cùng implementation.
- Owner review payload/versioning và thay đổi dependencies.
- CI, review và merge được kiểm tra riêng trên GitHub.

Chưa có bằng chứng nghiệm thu embedding/index trên 200 asset thật.
Chưa đo Recall/nDCG hoặc kết luận chất lượng tìm kiếm.