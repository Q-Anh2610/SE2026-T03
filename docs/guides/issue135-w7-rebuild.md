# W7: rebuild CLIP/E5 và kiểm chứng search — Issue #135

## Phạm vi và trạng thái

Runner `scripts/verify_issue135_rebuild.py` dựng lại 200 CLIP preview vectors và
200 E5 passage vectors từ inputs đã khóa, bằng encoder/builder/store hiện có.
Đây là kiểm chứng module embedding/index/search; không phải benchmark chất
lượng, HTTP latency, Docker/E2E hoặc nghiệm thu toàn hệ thống.

Không đổi frozen config W6, loader, default API hoặc active index. Mapping mới
chỉ mô tả quan hệ với reference; không cấp quyền chạy benchmark trên rebuild.
Một thành viên khác vẫn cần tự chạy toàn bộ quy trình trên output riêng.

## Protocol ghi trước lượt kiểm chứng

Protocol: `docs/configs/issue135-rebuild-protocol-v1.json`, SHA-256
`01130a382181aed65ac461d7b6a8b55c35d6c301f3ce759b57c77e5baa40900a`.
Runner pin hash này và lưu nguyên bytes vào run directory trước khi nạp model
hoặc so vector. Muốn đổi protocol phải version hóa/review riêng, không sửa
tolerance sau khi thấy kết quả. Lượt fail giữ nguyên output, lượt sau dùng thư
mục mới. Test fixture thay protocol/hash chỉ trong thư mục tạm của pytest.

- CPU, seed 0, 4 torch intra/inter-op threads; CLIP batch 8, E5 batch 16.
- qdrant-client 1.15.1, torch 2.8.0, transformers 4.57.1; các package còn lại
  ghi phiên bản thực tế, không tự cài/nâng cấp môi trường.
- Audit hiện có kiểm đủ 200 IDs/point IDs, payload/filter fields, dimension,
  finite, L2 với abs tolerance 1e-5 và Cosine/named vector/version compatibility.
- Đối chiếu reference: IndexConfig và payload phải khớp, chỉ cho khác index_version
  và named vector suy ra từ version. Collection phải cùng tên nhưng storage
  riêng. Không bỏ metadata/corpus/preprocessing khỏi phép so.
- Manifest CLIP lịch sử dùng cutoff diagnostic k=10; manifest rebuild ghi k=200
  theo policy ảnh W6. Điều này không đổi vectors/input pins. So IndexConfig và
  payload riêng với query policy, không yêu cầu hai manifest có cùng bytes/hash.
- Vector: sai số tuyệt đối tối đa mỗi thành phần <= 1e-6, không dùng relative
  tolerance hoặc round vector/hash. Đây là ngưỡng nhỏ cố định cho phép sai số
  số học float32 khi thực thi lại model CPU; không khẳng định mọi môi trường
  đều tái lập trong ngưỡng này. Báo max delta và số vector khác ngay cả khi đạt.
- Persisted reopen: fingerprint phải khớp **chính xác** giữa hai lần mở trước
  query và lần mở sau smoke. Không áp tolerance vector vào phép kiểm này.
- Chỉ mở Qdrant reference trên bản sao đã đối chiếu file hashes. Lưu hashes
  storage gốc trước/sau, từ chối SQLite WAL/SHM/journal. Không dùng copy storage
  làm kết quả rebuild: hai builder luôn encode lại inputs bằng model thật.
- Smoke gọi TextSearchService qua CLIPTextSource, E5MetadataSearchService,
  ExperimentalFusionService và ImageSearchService hiện có. Text probe cố định
  `W7 index reproducibility check`; ảnh probe là preview của asset ID đầu trong
  ready đã pin. Đây là kiểm tra hành vi trên dữ liệu index, không đo relevance.
- Filters `{}` cần đúng 200 IDs duy nhất; filter category không tồn tại cần 0.
  Kiểm versions, sources, params, thứ tự và dedup. Fusion giữ k=20, weights 1/1,
  cửa sổ hai nguồn và cutoff 200. Tests fixture riêng bao phủ tie-break, filters
  có kết quả, errors và mismatch; không dùng expected ranking từ held-out test.
- Không so ranking giữa reference và rebuild ở protocol v1. Passed chỉ chứng
  minh vector/metadata tương thích trong giới hạn trên và các smoke properties,
  chưa chứng minh ranking giống tuyệt đối hoặc chất lượng benchmark tương đương.
- Loader W6 kiểm raw hashes cả các file query/qrels đã khóa; runner không parse
  hoặc chạy chúng, không đọc held-out rankings để chọn expected outputs.

## Inputs và prerequisites

Frozen config SHA-256:
`1e1962058528e22b5235d989a3613b5077c02d479b8ac19e8dbc28fee0bd08d5`.
Snapshot: `home-interior-clear-200-v3`, source SHA-256:
`9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`.

- CLIP `openai/clip-vit-base-patch32` revision
  `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`, 512D, slow processor/RGB/L2.
- E5 `intfloat/multilingual-e5-small` revision
  `614241f622f53c4eeff9890bdc4f31cfecc418b3`, 384D, fast tokenizer, right
  padding/truncate512, mask-mean float32, query/passage prefixes và L2.
- Corpus SHA-256:
  `66efd87e34447c23b4171e13ac77d78a9c193519141d0dd6a31985c01e65b4f5`,
  recipe `e5-metadata-passage-v1-draft`; không xuất lại recipe khác.
- Paths lấy từ frozen config: input CLIP
  `data/processed/issue89/inputs-1d75f15977be`; reference CLIP
  `data/processed/issue89/clip-preflight-76d5d2c095b6`; reference E5/corpus
  `data/processed/issue91/e5-index-20261113-2`.
- Gói inputs/reference đã bàn giao tại #114 và guide
  `docs/guides/issue114-w6-freeze.md`. ZIP không chứa weights; cần cache offline
  đúng revisions. Sample 5 asset của #142 không thay thế inputs này.
- Dùng backend virtualenv theo requirements của repo; không cần PostgreSQL,
  API key hoặc Qdrant server. Dừng writer giữ reference storage trước khi copy;
  không dừng/xóa dữ liệu của thành viên khác để vượt kiểm tra.

Checker dependency đã đạt tại #114 chỉ chứng minh phạm vi checker. Không dùng
kết quả đó thay cho rebuild/smoke W7 hoặc xác nhận từ thành viên khác.

## Commands từ repo root — Git Bash trên Windows

Git do người thực hiện thao tác từng lệnh theo quy trình nhóm. Trước khi chạy,
ghi branch/commit và working tree status thực tế. Runner chỉ đọc Git để ghi
provenance; không commit, push, fetch hoặc thay branch/index Git.

Kiểm pins và local inputs, không nạp model hoặc mở Qdrant:

```bash
backend/.venv/Scripts/python.exe -B scripts/verify_issue114_frozen_config.py --expected-sha256 1e1962058528e22b5235d989a3613b5077c02d479b8ac19e8dbc28fee0bd08d5 --local-inputs
```

Exit 0, `frozen_config_verified`, `local_inputs_verified=true` là điều kiện
đầu vào; `test_authorized=false` vẫn đúng chức năng của checker.

Tests bằng fixtures, không nạp model/đọc benchmark để chọn đáp án:

```bash
backend/.venv/Scripts/python.exe -B -m pytest backend/tests/unit/test_issue135_rebuild.py backend/tests/unit/test_experimental_text_search.py backend/tests/unit/test_image_search.py backend/tests/unit/test_text_search_service.py backend/tests/unit/test_search_filters.py backend/tests/unit/test_rrf.py backend/tests/unit/test_e5_index.py backend/tests/unit/test_image_index_manifest.py -q
```

Rebuild và smoke bằng model thật; runner tự tạo run directory mới dưới
`data/processed/issue135/`. Lệnh không có tùy chọn tải weights hoặc đổi model:

```bash
backend/.venv/Scripts/python.exe -B scripts/verify_issue135_rebuild.py
```

Cần exit 0, `status=rebuild_and_service_smoke_verified`, `stage=complete`.
Thiếu cache/input, mismatch hoặc bất kỳ bước thất bại: exit 2, status blocked;
không tích nghiệm thu. Output đã tồn tại bị từ chối. Đường dẫn report in cuối
lệnh. Với PowerShell dùng `backend\.venv\Scripts\python.exe` tương ứng.

## Artifacts và cách đọc kết quả

Mỗi run gồm `protocol.json`, `input-inventory.json`, `report.json`,
`reference-map.json`, `CHECKSUMS.sha256`, index CLIP/E5 mới và reference copies.
Run ID, thời gian, manifest hashes mới là provenance riêng. CLIP có index
version mới. E5 giữ index_version xác định từ corpus+corpus manifest theo
implementation hiện có; cùng version không có nghĩa đây là cùng lượt encode
hoặc cùng artifact manifest. Root/run ID, timestamps, code/module hashes và
manifest SHA-256 phân biệt các lượt. Không sửa frozen artifacts để nhận chúng.

Report ghi commit/dirty status thực tế, module hashes, packages, máy/device,
model revisions, counts/errors/skipped, comparison deltas, persisted audits,
smoke properties và việc bảo toàn inputs/storage. Lượt chạy từ code chưa commit
phải ghi dirty=true. Không gán commit tạo sau cho lượt kiểm chứng trước.

`reference-map.json` có schema riêng, review_status=pending,
benchmark_binding_reviewed=false. Mapping **không phải** consumer binding cho
loader W6 và không chứng minh approval. Nếu cần benchmark trên rebuild, phối
hợp Khuê/Quỳnh Anh để version hóa/review binding riêng; không đổi pins W6.

Kiểm checksum trong đúng run directory được in ra, ví dụ sau khi thay path:

```bash
cd data/processed/issue135/<run-id>
sha256sum -c CHECKSUMS.sha256
```

Chỉ bàn giao JSON/checksums nhỏ đã kiểm tra và báo cáo giới hạn. Giữ weights,
previews, storage, reference copies và raw output lớn ngoài Git. Các paths trong
inventory tính từ repo; không gửi `.env` hoặc credentials. Không xóa run lỗi để
che kết quả. Nếu cần dọn, xác định chính xác run của mình sau khi lưu evidence.

## Khi blocked và xác nhận độc lập

- `protocol_hash_mismatch`: đối chiếu code/protocol/EOL với bản được review;
  không đổi expected hash theo file chưa xác minh.
- `dependency_version_mismatch`: ghi versions hiện có, dựng môi trường đúng
  requirements; không nới version gate để chạy với local Qdrant khác.
- stage dependencies/input: kiểm gói local inputs/reference và nguyên bytes;
  không tải lại preview rồi tự thay checksum. FrozenConfigError chỉ ra pin thiếu.
- stage offline_models: cache thiếu/sai revision hoặc model config không khớp;
  chuẩn bị đúng cache đã pin theo hướng dẫn, không tự đổi model.
- storage sidecar/lock hoặc reference đổi: dừng lượt kiểm chứng, phối hợp owner
  xác định writer; không xóa WAL/lock hoặc mở storage gốc bằng Qdrant để sửa.
- `reference_rebuild_vector_tolerance_exceeded`: giữ run/report và phân tích
  môi trường, preprocessing, inputs và max delta theo protocol; không nới ngưỡng.
- lỗi smoke/reopen: giữ stage/type/code, manifests và report; không dùng index
  dở dang cho benchmark/API. Lỗi lặp vẫn dùng output mới để bảo toàn lịch sử.

Thành viên tái lập chạy guide trên checkout/môi trường của mình, output mới,
rồi gửi commit/dirty status, môi trường, commands/exit codes, report/hash,
reference mapping, max deltas, persisted audits và blockers thực tế. Không cần
làm lại W5 hoặc dùng 42 text/12 image test queries. Phản hồi chỉ đọc guide,
khôi phục ZIP storage hoặc chạy dependency checker chưa đủ tích mục tái lập W7.

## Checklist bàn giao — chưa tích trước

- [x] Rebuild thật và smoke đạt; run `20261126T140828Z-c593def6`, có report/checksums.
- [x] Persisted reopen chính xác; CLIP/E5 max component delta=0.0 theo protocol trước đo.
- [ ] Review mapping và các giới hạn; chưa chuyển benchmark/runtime sang rebuild.
- [ ] Một thành viên khác chạy lại embedding/index/search trên output riêng.
- [ ] Local regression, CI head mới nhất, review/approval và merge ghi riêng.
- [ ] Checklist Issue #135/PR cập nhật đúng bằng chứng trước PR tiếp theo.

## Bằng chứng local ngày 26/11/2026

[Báo cáo, giới hạn và lịch sử tests](../evidence/issue135-w7-rebuild-20261126.md).
Local regression: 310 passed trên checkout thật. Model thật: CLIP/E5 200/200,
0 failed/skipped, vectors khớp reference từng thành phần, persisted reopen đạt.
Lượt đo chạy ở base bff65ac với dirty=true; không gán commit tạo sau cho lượt này.
Mapping còn pending; chưa có xác nhận thành viên khác/CI/approval/merge cho W7.

Trên Windows, dùng đường dẫn pytest temp ngắn. Lượt test đầu từ terminal dùng
thư mục temp dài khiến đường dẫn copy E5 storage.sqlite đạt 260 ký tự (WinError
206); cùng code/assertions đạt 310/310 sau khi đổi sang temp ngắn, không đổi
protocol/tolerance. Giữ JUnit cũ, mỗi lần chạy dùng output/JUnit mới.
