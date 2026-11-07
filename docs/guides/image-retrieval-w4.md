# CLIP image retrieval và adapter SigLIP 2 — #76

Xem [interface và các quyết định chờ TV1/TV2/TV5](../contracts/image-retrieval-w4.md).
Chưa đánh dấu Issue W4 hoàn thành; chưa đổi HTTP image route, DB hoặc UI.

## Môi trường và kiểm thử

Dùng Python của `backend/.venv`; không thêm dependency/lockfile. Adapter dùng
torch/transformers/Pillow/Qdrant đã được pin trong requirements của repo.
Các tests dùng model giả lập và Qdrant thật ở memory/thư mục tạm; không thay
thế smoke weights thật hoặc benchmark có nhãn.

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/unit -q
```

Runner luôn `local_files_only=True`, không tải weights/preview. CLIP cache
có pinned revision; SigLIP 2 chưa có trong cache ở lượt kiểm tra ngày 07/11/2026.
Chưa smoke SigLIP 2 thật; không tự tải checkpoint lớn hay sửa cache/dependencies.

## Smoke ngay với index W3 đã có

Từ gốc repo trên máy đã có gói W3 local được kiểm tra:

```powershell
backend\.venv\Scripts\python.exe scripts/verify_issue76_image_retrieval.py smoke --model clip --handoff-root data/processed/issue60/smoke-20261104T065700Z-6dcbc8/home-interior-354-v1 --index-manifest data/processed/issue60/smoke-20261104T065700Z-6dcbc8/index-manifest.json --qdrant-path data/processed/issue60/smoke-20261104T065700Z-6dcbc8/qdrant
```

Đây là diagnostic **self-preview** trên index W3, không phải image benchmark
độc lập hoặc bằng chứng đã build index W4. TV2 đã xác nhận dùng cùng snapshot
354 cho W4 tại bình luận bên dưới. K=10 vẫn chỉ là cutoff diagnostic.
Không build/upsert/rebuild index ở mode `smoke`. Không mở Qdrant local đồng
thời với API/script khác. Lệnh dùng index CLIP W3 hiện có; không dùng index
CLIP cho adapter SigLIP 2.

Runner đối chiếu source/ready hashes và từng preview SHA-256; audit IDs,
payload/version, dimension và normalization. Chạy ba ảnh self-preview cùng
category/license/format/face bounds/AND/empty; lặp từng ca và lưu raw top-K.
Thứ tự/IDs/versions phải bằng nhau, score dùng tolerance lặp `1e-12` của W3.
Không nới tolerance cosine hoặc thay thuật toán ranking để qua smoke.

Với Qdrant local 1.15.1, cosine chuẩn hóa mảng vectors trong RAM tại chỗ
(`qdrant_client/local/distances.py:cosine_similarity`). Có thể lệch vài ULP
sau truy vấn dù không có thao tác ghi. Report ghi riêng fingerprint RAM
trước/sau, rồi đóng/mở lại storage và yêu cầu **fingerprint persisted bằng
trước truy vấn**. Không khẳng định RAM bất biến khi report cho thấy khác.

Mỗi lần chạy tạo thư mục mới `data/processed/issue76/<model>-<mode>-<id>`;
report chứa machine/packages, code SHA/dirty/module hashes, lệnh, elapsed,
raw ranked results + lần lặp, input hashes và audit trước/sau/mở lại.
Lỗi có exit code 1 và stage/type/mã an toàn; không thay báo cáo cũ.

## Snapshot W4 đã được xác nhận

TV2 chốt `home-interior-354-v1` tại [bình luận #76](https://github.com/Q-Anh2610/SE2026-T03/issues/76#issuecomment-6702522644).
Source/ready SHA-256 khớp bộ local vừa smoke. Cần kiểm tra lại từng preview
trước build; không suy ra dedup mesh hoặc cân bằng danh mục từ checksum duy nhất.
Image queries/qrels và protocol TV5 vẫn đang chờ; không công bố metric chất lượng.

## Build CLIP W4 bằng Git Bash

Từ gốc checkout, sau khi kiểm tra input, chạy một lệnh sau. Runner nạp model
CLIP offline, encode đủ 354 ảnh, ghi index mới riêng rồi tự smoke/audit persisted.
Không ghi đè index W3. K=10 là diagnostic, chưa phải cutoff do TV5 chốt.

```bash
backend/.venv/Scripts/python.exe scripts/verify_issue76_image_retrieval.py build \
  --model clip \
  --handoff-root data/processed/issue60/smoke-20261104T065700Z-6dcbc8/home-interior-354-v1 \
  --source-manifest manifests/assets_354.json \
  --ready-manifest assets_354.ready.json \
  --source-sha256 93f65237ca51060aad75f0f672b2b16f76c89a64dce64d7473791f428e944614 \
  --ready-sha256 7d0a3e59f4d1c697cb37fd8b82decea3ba3efa95d8c84235bda73b5afb67474c \
  --asset-count 354 \
  --snapshot home-interior-354-v1 \
  --candidate-limit 10 \
  --snapshot-confirmation 'https://github.com/Q-Anh2610/SE2026-T03/issues/76#issuecomment-6702522644'
```

Lưu đường dẫn report JSON cuối lệnh. Chưa chạy/verify xong thì chưa ghi nhận build
đạt. Weights SigLIP 2 chưa sẵn sàng nên chưa build được index model thứ hai.

## Quy tắc build và so sánh

Chỉ chạy khi có link TV2 chốt snapshot W4 và bộ preview đã đối chiếu. Cần:
`handoff-root`, source/ready paths tương đối, hai SHA-256 đã chốt, số asset,
snapshot name, preview directory, link xác nhận và K diagnostic/protocol.
Xem đầy đủ tham số bằng lệnh chỉ đọc:

```powershell
backend\.venv\Scripts\python.exe scripts/verify_issue76_image_retrieval.py --help
```

Mode `build --model clip` yêu cầu `--snapshot-confirmation` cùng các input
trên. Không suy ra confirmation từ việc đã nhận snapshot W3. Script kiểm tra
tất cả ảnh/checksum/ID/metadata trước embedding, chỉ ghi vào index mới riêng;
ảnh index vẫn qua batch guard 2 MiB/4096 px của W2, tách với upload 5 MiB.
Có ảnh batch không chấp nhận thì dừng, không tuyên bố index đầy đủ.

Build SigLIP 2 với cùng input và `--reference-manifest` trỏ manifest ảnh
CLIP vừa tạo. Runner kiểm tra snapshot/source/ready/count/cutoff bằng nhau
**trước** khi build. Không tái sử dụng manifest text W3 làm reference so sánh
W4. Mỗi model có storage, index version, named vector và manifest riêng.
Sau build, tự smoke và audit persisted. Weights phải được chuẩn bị đúng
revision trước, không tải tự động trong runner.

Kết quả hiện chỉ là smoke/raw retrieval. TV5 chốt image queries/qrels/split,
same-ID vs similar, self-match policy, filters/cutoff, warmup/timing và format
ranked results trước benchmark so sánh. Không chọn cấu hình theo test đã khóa.

## Kết quả build CLIP W4 ngày 07/11/2026

Chi chạy runner trên snapshot do TV2 xác nhận. Run local:
`data/processed/issue76/clip-build-1ce976722ab7`.

- 354 preview/source/ready đã đối chiếu checksum; embedding 354 thành công,
  0 failed, 0 skipped. Qdrant persistent local có 354 point/asset ID duy nhất.
- Index version `issue76-clip-build-1ce976722ab7`, named vector
  `clip_d4a2b0ba8f1c521e`; storage mới riêng, không thay index W3.
- Smoke 10/10 ca, K=10 diagnostic, hai lần mỗi ca có cùng IDs/thứ tự/versions
  và scores trong tolerance W3. Fingerprint persisted giữ nguyên sau đóng/mở lại:
  `7c28ecfef509e1f456f0b8c7572d8c91380ef511fa2bee85da6a182f18f7b77b`.
- Embedding 23.948s; tổng runner
  37.464s. Không dùng thời gian diagnostic làm latency benchmark.
- Raw ranked results, command, packages, machine, source hashes và audit:
  [report](../evidence/issue76-clip-image-smoke.json).
  [Manifest ảnh CLIP W4](../evidence/issue76-clip-image-index-manifest.json)
  ghi pinned checkpoint/processor/preprocessing, snapshot confirmation và code hashes.
- Unit backend do Chi chạy: 638 passed in 16.76s. Đây là local, không phải CI.

Chưa có smoke/index SigLIP 2 thật, image benchmark có nhãn hoặc HTTP image E2E.
Interface TV1 và protocol TV5 vẫn cần xác nhận; không đánh dấu toàn bộ #76 đạt.

## Handoff hiện tại

- Có thể tích hợp thử ở module: bytes JPEG/PNG → CLIP → Qdrant tương thích
  → candidates/versions; tests ảnh lỗi/filter/dedup/tie-break/empty/version.
- Có adapter SigLIP 2 và manifest/runner riêng; tests fixture đạt, chưa có
  weights/cache và index SigLIP 2 thật để nghiệm thu.
- TV2 đã xác nhận snapshot W4; đang chờ TV1 xác nhận interface #76 → #80
  và TV5 image benchmark/protocol.
  Không tự sửa checklist/review GitHub, commit, push hoặc mở PR trong phiên này.
