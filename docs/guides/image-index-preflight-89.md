# Preflight index ảnh — Issue #89

Runner: `scripts/verify_issue89_image_preflight.py`. Đây là bước chuẩn bị index
cho benchmark ảnh, dùng service retrieval của sản phẩm. Chưa xác nhận index
model thật sẵn sàng cho đến khi cả hai lượt build và bước compare thành công.

## Input đã xác nhận

- Candidate snapshot: `home-interior-clear-200-v3`, đúng 200 asset.
- Nguồn: `data/manifests/objaverse_200.json`, SHA-256
  `9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`.
- Đối chiếu ID/checksum với `data/benchmark/candidate_assets.csv` và
  `data/manifests/objaverse_200.provenance.json`.
- [Xác nhận snapshot](https://github.com/Q-Anh2610/SE2026-T03/issues/89#issuecomment-6705482003).
- [Filters đã chốt](https://github.com/Q-Anh2610/SE2026-T03/issues/89#issuecomment-6705967217):
  `filters={}` cho cả CLIP và SigLIP 2.
- Preview được chọn từ gói W4 đã nhận; metadata nguồn và checksum từng ảnh phải
  khớp cả candidate CSV, provenance và ready manifest của gói nhận.

Gói W4 có 354 asset, còn index #89 phải có đúng 200 candidate IDs. Runner tạo
gói input mới chỉ chứa 200 preview được chọn, giữ nguyên bytes source manifest,
metadata và bytes ảnh. Mỗi lượt prepare/build sinh thư mục mới, không ghi đè
input/index W3/W4 hoặc các lượt trước. Không tải model hoặc dataset.

## Thao tác trong Git Bash từ repo root

Dùng nhánh nhiệm vụ `test/89-image-index-preflight`. Không chạy lại lệnh tạo
nhánh nếu đã ở nhánh này. Không mở cùng storage Qdrant bằng hai process.

### 1. Kiểm tra và đóng gói đúng 200 preview

```bash
backend/.venv/Scripts/python.exe scripts/verify_issue89_image_preflight.py prepare \
  --received-root data/processed/issue60/smoke-20261104T065700Z-6dcbc8/home-interior-354-v1
```

Kết quả thành công có `prepared: true`, `asset_count: 200`, `input_root` và
SHA-256 của `ready.json`. Lưu đường dẫn `input_root` trả về. Chỉ bước này chưa
tạo index và chưa xác nhận readiness của model. Nếu thiếu/sai ảnh hoặc metadata,
đối chiếu lại gói nhận; không sửa checksum để bỏ qua lỗi.

Gói mới chứa `source.json`, `ready.json`, `candidate_assets.csv`,
`preview-provenance.json`, `input-receipt.json` và 200 preview.

### 2. Build CLIP và smoke trên input vừa tạo

Thay đường dẫn ví dụ `inputs-<id>` bằng `input_root` thực tế:

```bash
backend/.venv/Scripts/python.exe scripts/verify_issue89_image_preflight.py build \
  --model clip \
  --input-root data/processed/issue89/inputs-<id>
```

CLI dùng model offline trong cache CLIP đã có. Kết quả ghi đường dẫn
`clip-preflight-<id>/report.json`. Chỉ tiếp tục khi `preflight_ready: true`.
Manifest tham chiếu nằm cùng thư mục với report: `index-manifest.json`.

### 3. Build SigLIP 2 với cùng input và tham chiếu CLIP

```bash
HF_HUB_OFFLINE=1 HF_HUB_CACHE=data/models/huggingface \
backend/.venv/Scripts/python.exe scripts/verify_issue89_image_preflight.py build \
  --model siglip2 \
  --input-root data/processed/issue89/inputs-<id> \
  --reference-manifest data/processed/issue89/clip-preflight-<id>/index-manifest.json
```

Thay cả hai đường dẫn bằng kết quả thực tế. Cache SigLIP 2 phải có đủ config,
processor và weights của revision đã pin. Khi cache thiếu, runner báo thất bại;
không tải lại model trong bước này. Trước khi nạp model, runner đối chiếu nguồn,
ready hash, số asset và cấu hình retrieval với manifest CLIP.

### 4. Đối chiếu hai report

```bash
backend/.venv/Scripts/python.exe scripts/verify_issue89_image_preflight.py compare \
  --clip-report data/processed/issue89/clip-preflight-<id>/report.json \
  --siglip2-report data/processed/issue89/siglip2-preflight-<id>/report.json
```

Kết quả thành công ghi `preflight-comparison-<id>.json`. Summary gồm per-model
index/version, model revision, preprocessing, dimension, L2/cosine, processor,
named vector, storage/manifest/report paths và hashes, audit count/fingerprint.
Hai manifest phải có cùng input/cutoff và storage/named vector riêng.

## Phép kiểm tra và giới hạn

- Mỗi lượt build kiểm tra lại toàn bộ input/checksum; batch phải có 200 embedded,
  0 failed/skipped. Audit đối chiếu đủ ID, point count, payload metadata/version,
  vector hợp lệ và normalization.
- Smoke dùng ba preview đã index (hai ID đầu và ID cuối sau khi sắp xếp), mỗi
  ảnh truy vấn hai lần với `filters={}` qua `ImageSearchService.search_image`.
  Kiểm tra đủ kết quả duy nhất thuộc candidate set, đúng execution versions và
  thứ tự/score lặp lại. Sai số tuyệt đối score cho phép là `1e-12` như runner W4.
- K=10 mặc định là cửa sổ diagnostic; không tự chốt cutoff benchmark. Không so
  cosine giữa model, không chọn model theo self-preview hoặc thời gian runner.
- Audit persisted fingerprint trước truy vấn và sau đóng/mở lại phải bằng nhau.
  RAM fingerprint được ghi riêng vì Qdrant local có thể chuẩn hóa lại float.
- `benchmark: false`: không đọc/chạy 20 query độc lập, không đọc qrels, không
  tính metric hay điều chỉnh cấu hình theo test. Benchmark vẫn cần chủ trì
  đánh giá chốt qrels, split và protocol/manifest trước khi chạy.
- Nếu bất kỳ model/build/audit/smoke/compare thất bại, giữ trạng thái pending.
  Report build lỗi có stage/type và safe error code nếu có.

Report ghi code commit, dirty flag, module hashes và môi trường thực tế. Lượt
chạy local trước commit sẽ có dirty flag; không sửa cờ này thành clean.
Chỉ đưa JSON bằng chứng nhỏ đã kiểm tra vào `docs/evidence/` khi bàn giao;
không commit preview, weights, cache hoặc Qdrant storage trong `data/processed/`.

## Kiểm thử script bằng fixture

```bash
backend/.venv/Scripts/python.exe -m pytest \
  backend/tests/unit/test_image_index_preflight.py \
  backend/tests/unit/test_image_index_manifest.py -q
```

Tests dùng ảnh nhỏ và encoder giả, gồm reject input/checksum/metadata sai,
chống ghi đè gói, hai index Qdrant tạm, audit/reopen, repeat smoke, đối chiếu
report và reject tham chiếu không tương thích trước khi nạp model.
Tests fixture không thay thế build/smoke bằng model thật.

Runner tái sử dụng `build_index` trong script #76, chỉ thêm tùy chọn prefix,
collection và danh sách module hashes; mặc định của runner #76 được giữ nguyên.


## Bằng chứng model thật ngày 08/11/2026

Hai model đã build trên đúng gói input 200 `inputs-1d75f15977be`.
Ready SHA-256: `050ebe41f3a33dec671a879b165ee3ecf68b914c20f5f1b62051a643d11143b3`.
Mỗi model có 200 embedded, 0 failed/skipped, 200 point/asset ID duy nhất,
ba query diagnostic K=10 chạy lặp lại với `filters={}` đều đạt; persisted
fingerprint trước và sau đóng/mở lại bằng nhau. Bước compare đã đạt.

| Model | Index version | Dimension | Model revision |
|---|---|---|---|
| CLIP | `issue89-clip-preflight-76d5d2c095b6` | 512 | `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268` |
| SigLIP 2 | `issue89-siglip2-preflight-8a07361d2081` | 768 | `75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2` |

Preprocessing lần lượt là `clip-slow-processor-rgb-l2-v1` và
`siglip2-fixres-slow-processor-rgb-l2-v1`; cả hai L2 + Cosine, processor chậm
đúng checkpoint. Storage và named vector riêng. Manifest ghi đầy đủ processor
config/revision, collection, model/config/index versions và hashes.

Các bản sao JSON giữ nguyên bytes của output gốc:

- [Đối chiếu hai model](../evidence/issue89-image-index-preflight-comparison.json).
- [Input receipt](../evidence/issue89-image-input-receipt.json).
- [CLIP report](../evidence/issue89-clip-image-index-preflight.json) và
  [CLIP manifest](../evidence/issue89-clip-image-index-manifest.json).
- [SigLIP 2 report](../evidence/issue89-siglip2-image-index-preflight.json) và
  [SigLIP 2 manifest](../evidence/issue89-siglip2-image-index-manifest.json).

Report/manifest ghi base commit `05895389ae62133ac6144ebcbdc4b59702eca82e`
và `working_tree_dirty: true` vì script chưa commit lúc chạy. Đã đối chiếu
module hashes với source local tại thời điểm xuất bằng chứng; không sửa cờ
dirty hoặc SHA để coi như chạy từ commit sạch. SHA-256 là hash bytes thực tế,
bao gồm line endings. `.gitattributes` giữ LF cho các JSON bằng chứng #89.

Các path trong JSON gốc chỉ nơi lưu runtime trên máy đã chạy, không có nghĩa
Qdrant/input/weights đã được commit hoặc chuyển sang máy người đánh giá. Lệnh
compare ở trên dùng report gốc cùng manifest và gói input local. Thành viên
khác có thể prepare/build bằng runner này với cùng preview/checksum để tái lập;
index version của lần build mới sẽ khác và cần ghi lại bằng chứng mới.

Đây là readiness của module retrieval cho candidate set 200, chưa xác nhận
benchmark end-to-end hay chất lượng tìm kiếm. Chưa dùng 20 query độc lập,
chưa tính metric; chủ trì đánh giá tiếp tục chốt qrels/split/protocol và môi
trường benchmark. Không đóng #89 chỉ vì preflight này đạt.

Kiểm thử local trước các lượt model thật: 44 test input/manifest đạt; toàn bộ
`backend/tests/unit` có 674 test đạt. Đây là kết quả local, không thay CI PR.
