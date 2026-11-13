# Index metadata E5 — phần tiếp theo của #91

Phạm vi: nhận corpus #101 đã được Chi kiểm chứng, build index local riêng và
audit compatibility/persistence. Service E5-only/RRF thử nghiệm được bổ sung
ở [guide service](e5-rrf-service-91.md). Chưa nối HTTP API hoặc chạy benchmark
validation; CLIP vẫn là mặc định.

## Đầu vào đã tiếp nhận

[PR #102](https://github.com/Q-Anh2610/SE2026-T03/pull/102), commit
`a85c8fafa475eecfeaace9a66d3f4ed1d6c4bbc9` cung cấp exporter của Huyền.
Chi đã chạy riêng 16 corpus tests đạt, xuất hai lần và dùng `cmp` đối chiếu cả
corpus/manifest khớp bytes, rồi xác nhận tại
[#91](https://github.com/Q-Anh2610/SE2026-T03/issues/91#issuecomment-6848528349).
PR dữ liệu chưa merge không ngăn việc đọc artifact đã pin; không chép exporter
hoặc hiện thực lại passage recipe trong module index.

- Snapshot `home-interior-clear-200-v3`, đúng 200 asset IDs duy nhất, không bỏ lỗi.
- Source Git blob `data/manifests/objaverse_200.json`, SHA-256
  `9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`.
- Recipe tiếp nhận `e5-metadata-passage-v1-draft`; giữ nguyên tên version của
  artifact, không tự đổi thành bản final. Các trường name/description/tags/category,
  whitespace, tags dedup/order, null/empty và serialization theo corpus manifest.
- Corpus SHA-256
  `66efd87e34447c23b4171e13ac77d78a9c193519141d0dd6a31985c01e65b4f5`.
- Corpus chưa chứa prefix. `E5Encoder.encode_passages` thêm `passage: ` đúng
  một lần; index builder truyền nguyên nội dung đã kiểm hash.

Script từ chối input khác pin/recipe/serialization/IDs hoặc có errors. Nếu Huyền
đổi version/artifact, cần đối chiếu lại và cập nhật pin có review trước build.
Không dùng queries/qrels, caption mới hoặc DB thay đổi để dựng corpus này.

## Build bằng cache thật

Từ gốc repo, sau khi có corpus đã tái lập và cache E5 đúng revision:

```bash
backend/.venv/Scripts/python.exe -B scripts/build_e5_metadata_index.py --corpus-root work/issue101-corpus-review-1 --output data/processed/issue91/e5-index-new-run --device cpu --batch-size 16
```

Output bắt buộc là thư mục mới. Script đọc Git blob theo source_commit trong
corpus manifest, kiểm pin SHA-256 đã tiếp nhận rồi mới nạp model offline.
Không tải weights hoặc đọc `.env`/PostgreSQL. Dùng một encoder cho toàn batch.
Không tạo collection server hoặc mở storage CLIP/SigLIP.

Gói mới gồm `source.json`, `corpus.jsonl`, `corpus-manifest.json`, `qdrant/`,
`index-manifest.json`, `audit.json`, `persistence-audit.json` và `build-report.json`.
Chỉ khi audit cả persisted data thành công mới ghi index manifest. Build lỗi có thể để lại output
dở dang; giữ để chẩn đoán và chọn thư mục khác khi chạy lại. Report `passed`
chỉ xuất sau khi đối chiếu chính xác persisted IDs/payload/vectors với các giá trị
đã submit, rồi mở lại storage thêm lần nữa và đối chiếu fingerprint ổn định.

## Compatibility và payload

- Model/tokenizer `intfloat/multilingual-e5-small` revision
  `614241f622f53c4eeff9890bdc4f31cfecc418b3`, 384 chiều, fast tokenizer right
  padding/truncation, tối đa 512 token, mask mean float32 và L2/Cosine.
- Collection `issue91_e5_metadata` nằm trong storage riêng của mỗi gói build.
  Named vector `e5_<fingerprint>`; `IndexConfig` giữ pin embedding/snapshot.
  Index version bind cả corpus bytes và toàn bộ corpus manifest, gồm recipe.
  Không dùng chung named vector với CLIP hoặc SigLIP 2.
- Payload giữ nguyên metadata nguồn cho các filter hiện có, không thay metadata
  bằng passage đã normalize. `_corpus` truy vết corpus/manifest hash và recipe;
  `_index`, `model_version`, `index_version` do QdrantStore chung ghi.
- Manifest riêng ghi input hashes/IDs, recipe/source commit, model/tokenizer,
  dimension/token/prefix policies, code commit/dirty flag, source hashes và packages.
- `verify_inputs` kiểm checksum, serialization, source/corpus/manifest IDs và
  version binding. `check_encoder` từ chối pin/tokenizer/token policy sai.
- `audit_metadata_index` chỉ đọc collection/named vector/count, toàn bộ IDs,
  UUID mapping, payload/provenance và vector finite/L2; tạo fingerprint. Nó không
  tạo/upsert/rebuild index khi mở một gói đã có.

Giữ `source_manifest_sha256` của candidate snapshot riêng với `corpus_sha256`.
Đổi corpus/recipe dẫn tới index version và named vector khác; không mặc định
vector ảnh 354 hoặc tên collection giống nhau là cùng một phép đánh giá.

## Persistence của Qdrant local

qdrant-client 1.15.1 local chuẩn hóa float32 trong RAM khi upsert, nhưng
`storage.persist(point)` giữ vector đầu vào; `load_vectors` đọc lại các giá trị đó.
Vì vậy fingerprint ngay sau upsert có thể khác sau reopen dù dữ liệu đã lưu đúng.
Build đối chiếu persisted IDs/payload/vectors **chính xác** với giá trị đã submit;
`audit.json` lấy baseline sau reopen. CLI mở lại thêm lần nữa và yêu cầu hash
khớp baseline. `persistence-audit.json` giữ riêng hash RAM ban đầu, expected input
và persisted data. Không làm tròn vector/hash, không nới L2 tolerance để cho qua.

Lượt build đầu ngày 13/11/2026 đã thất bại ở so hash RAM với persisted data:
71/200 vector khác tối đa `1.4901161193847656e-08`. Đã tái tạo đúng hash RAM bằng
phép normalize float32 của thư viện. Hai lần reopen của index lỗi có hash giống
nhau. Giữ gói đầu làm diagnostic; chưa coi đó là build passed. Test hồi quy
vector float32 không nằm trên trục đã tái hiện lỗi trước bản sửa.

## Kiểm chứng

Fixture tests dùng encoder giả có nhãn rõ và Qdrant local thật trong thư mục tạm:

```bash
backend/.venv/Scripts/python.exe -B -m pytest -c backend/pytest.ini backend/tests/unit/test_e5_index.py backend/tests/unit/test_qdrant_store.py backend/tests/unit/test_index_manifest.py -q -p no:cacheprovider
```

Các tests này kiểm artifact drift, ID coverage, namespace/compatibility, input
và index corruption, giữ metadata thiếu, encode thiếu batch, từ chối ghi đè và
persistence sau reopen. Chúng không thay thế build bằng weights thật hoặc đo
quality/latency retrieval. Kết quả local/CI và build thật phải ghi riêng sau chạy.
[Quỳnh Anh đã xác nhận contract fusion thử nghiệm](https://github.com/Q-Anh2610/SE2026-T03/issues/91#issuecomment-6849816002).
E5-only/orchestration/DTO thử nghiệm được ghi ở [guide service](e5-rrf-service-91.md);
shared API/runtime/search event cần review trước tích hợp, CLIP vẫn mặc định.
Hash query canonical vẫn chưa chốt; chưa chạy benchmark.

Kiểm chứng local ngày 13/11/2026, Windows/Python 3.13.7:

- Trước bản sửa persistence: nhóm E5/Qdrant/manifest 125 passed; toàn unit 829
  passed. Lượt weights thật đầu tiên vẫn thất bại ở fingerprint, không coi là đạt.
- Test hồi quy mới đã tái hiện lỗi: 1 failed trước sửa. Sau sửa, riêng index E5
  **43 passed, 42,91 s**; toàn bộ backend unit **831 passed, 52,60 s**.
- Build weights E5 thật từ cache CPU, batch 16, 4 intra-op/4 inter-op threads:
  **passed** trên 200 passages/points. Gói `data/processed/issue91/e5-index-20261113-2`.
  Persisted data khớp chính xác input; lượt reopen tiếp theo có cùng fingerprint.
- Collection `issue91_e5_metadata`, vector `e5_0c0cbdfd79bca607`, index version
  `issue91-e5-metadata-1588f4dc33fbe62609d8`. Load 0,965736 s; encode/build/audit
  9,831393 s. Các số này không phải p50/p95 retrieval latency.
- [Bằng chứng portable](../evidence/issue91-e5-index-build-20261113.json) ghi
  hashes, machine/packages/threads, command, code dirty flag và tests. Gói index,
  corpus và vectors vẫn ở local, ngoài Git. PR #106 đã có 5 checks passed, Khuê
  approve trên `ebbdb98` và merge vào `develop` tại `2c18b1d`; review service
  thử nghiệm là bước riêng.
