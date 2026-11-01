# Baseline W2 — Issue #39

Trạng thái: đã kiểm chứng embedding/index 200 asset thật ở cấp module;
chưa tích hợp HTTP Search API hoặc cập nhật trạng thái PostgreSQL.
Bằng chứng smoke ngày 27/10/2026; bổ sung dữ liệu thật ngày 29/10/2026 (UTC+7).

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

## Kiểm chứng 200 asset thật - bổ sung Issue #39

Lê Thị Linh Chi đã nhận bộ preview/metadata của TV2 và kiểm tra trên máy bên nhận.
Gói `objaverse200-handoff-20261029-231353.zip` có SHA-256
`6f7b5dcccbf2d942569016883bcb7f75c7563ef0602233470e4ce2fc0dfd53e5`.
Có đủ 200 asset ID duy nhất, 200 preview riêng biệt và decode được;
checksum khớp snapshot W1. Ready manifest được đối chiếu metadata, đường dẫn
ảnh và checksum với manifest/provenance và báo cáo ingestion nguồn.
Xác nhận tiếp nhận đã được đăng ở [Issue #41](https://github.com/Q-Anh2610/SE2026-T03/issues/41);
kết quả chi tiết được bổ sung ở [Issue #39](https://github.com/Q-Anh2610/SE2026-T03/issues/39).

### Kết quả

Hai lần chạy ngày 29/10/2026, khoảng 23:55-23:56 (UTC+7).

| Chỉ số | Lần đầu | Chạy lại toàn bộ |
|---|---:|---:|
| Asset đầu vào | 200 | 200 |
| Embedding thành công | 200 | 200 |
| Embedding lỗi / bỏ qua / chưa xử lý | 0 / 0 / 0 | 0 / 0 / 0 |
| Point được xác nhận upsert | 200 | 200 |
| Point trước -> sau (exact count) | 0 -> 200 | 200 -> 200 |
| Point ID duy nhất sau chạy | 200 | 200 |
| Asset ID duy nhất trong payload | 200 | 200 |
| Asset ID trùng | 0 | 0 |
| Point ID hoặc payload không hợp lệ | 0 | 0 |
| Acceptance | passed | passed |

Chạy lại tạo lại embedding cho cả 200 ảnh rồi upsert. Ngoài exact count,
script scroll toàn bộ point và đối chiếu UUID ổn định, metadata và `_index`
với đầu vào. SHA-256 tập point ID sau cả hai lần đều là
`3a601d261c8b21c70496bac3cfd720ef3b28efdac8d7e22863f430e3d997baf1`.
Vector norm quan sát: khoảng 0.99999977-1.00000019.

### Cấu hình và môi trường của lần đo

Model/revision, processor RGB/L2 và dimension 512 giữ cấu hình ở mục
Model và versioning phía trên. Processor revision trùng model revision.

| Thuộc tính | Giá trị |
|---|---|
| Collection | `issue39_objaverse200_clip_v1` |
| Named vector | `clip_c243769d0cc6846b` |
| Index version | `issue39-objaverse200-clip-v1` |
| Device / batch size / seed | CPU / 8 / 0 |
| Similarity | Cosine |
| Python / OS | 3.13.7 / Windows 11 |
| torch build / transformers | 2.8.0+cpu / 4.57.1 |
| qdrant-client / Qdrant server | 1.15.1 / 1.15.1 |
| Pillow thực tế | 13.0.0 |

Dataset snapshot:
`objaverse200-w1-sha256:b37947fd1f2201dacf92e657d0580981315dd6252ad785e60657f4c1fe595e4a`.

Commit nền: `65ce5839576949dc5633c05c745887c20913d79a`.
Script bổ sung chưa nằm trong commit nền; nội dung đã chạy được định danh bằng
SHA-256 `299335ba4be1a5d54154631044a75b77b3562b0b09463e3f37a251ce2546aafd`.
Hash của ba module được dùng nằm trong bằng chứng JSON.

### Bằng chứng và cách chạy

- Script: `scripts/verify_issue39_real_assets.py`.
- Bằng chứng gọn để review: [issue39-real-assets.json](../evidence/issue39-real-assets.json).
- Báo cáo runtime local: `data/processed/issue39/real-assets-first.json`
  và `data/processed/issue39/real-assets-repeat.json`.
- Ảnh, vectors, model weights và hai báo cáo runtime giữ ngoài Git.

Các lệnh đã dùng từ gốc repository (cần dependencies backend, model đã pin,
Docker/Qdrant sẵn sàng và gói TV2 đã giải nén):

```bash
./backend/.venv/Scripts/python.exe -u scripts/verify_issue39_real_assets.py --handoff-root work/received-objaverse200-20261029-231353 --phase first
./backend/.venv/Scripts/python.exe -u scripts/verify_issue39_real_assets.py --handoff-root work/received-objaverse200-20261029-231353 --phase repeat
```

Đường dẫn ảnh trong ready manifest được tính từ thư mục gói đã giải nén.
Script kiểm tra hash manifest với bản W1 trong repository trước khi chạy.
Lần đầu yêu cầu collection rỗng; lần repeat yêu cầu báo cáo lần đầu đạt và
collection/config/đầu vào còn khớp. Script không ghi đè báo cáo đã có.

Để tái lập trên collection mới và giữ nguyên các bằng chứng cũ:

```bash
./backend/.venv/Scripts/python.exe -u scripts/verify_issue39_real_assets.py --handoff-root work/received-objaverse200-20261029-231353 --phase first --collection issue39_objaverse200_clip_v1_rebuild --report data/processed/issue39/rebuild-first.json
./backend/.venv/Scripts/python.exe -u scripts/verify_issue39_real_assets.py --handoff-root work/received-objaverse200-20261029-231353 --phase repeat --collection issue39_objaverse200_clip_v1_rebuild --previous-report data/processed/issue39/rebuild-first.json --report data/processed/issue39/rebuild-repeat.json
```

Nếu giải nén dưới `work/`, thêm đúng thư mục gói vào `.git/info/exclude`
trên máy nhận; các pattern `/data/raw/` chỉ áp dụng dưới `data/` ở gốc repo.

Các unit tests kiểm tra helper audit nằm trong
`backend/tests/unit/test_real_assets_verification.py`, dùng Qdrant in-memory
và vector fixture; đây là kiểm tra logic, tách khỏi bằng chứng CLIP/server thật ở trên:

```bash
./backend/.venv/Scripts/python.exe -m pytest backend/tests/unit/test_real_assets_verification.py -q
```

Kết quả chỉ xác nhận embedding/index và chạy lại không trùng trên snapshot này.
Script không cập nhật PostgreSQL/searchable state, không tích hợp HTTP Search API;
chưa đo Recall/nDCG hoặc chất lượng retrieval. CI, review và merge theo PR riêng.

## Việc còn chờ

- Khuê phối hợp nhãn và đo Recall/nDCG bằng cùng implementation.
- Owner review payload/versioning và thay đổi dependencies.
- CI, review và merge được kiểm tra riêng trên GitHub.

Chưa đo Recall/nDCG hoặc kết luận chất lượng tìm kiếm.