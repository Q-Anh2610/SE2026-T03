# Runner validation E5/CLIP/RRF — #91

Runner dùng service thử nghiệm đã merge qua [PR #107](https://github.com/Q-Anh2610/SE2026-T03/pull/107),
theo [protocol Khuê đề xuất](https://github.com/Q-Anh2610/SE2026-T03/issues/91#issuecomment-6829347357)
và [contract Quỳnh Anh xác nhận](https://github.com/Q-Anh2610/SE2026-T03/issues/91#issuecomment-6849816002).
CLIP vẫn mặc định; runner không nối API/runtime/search events hoặc thay index.

## Gate canonical inputs

Config `evaluation/configs/issue91-e5-rrf-validation.pending.json` cố ý giữ
`input_confirmation.status="pending"`, evidence URL và byte policy là `null`.
Hash query khóa `f627…` chưa khớp artifact đã tìm được; không tự thay bằng
`e202…` hoặc `80e7…` để vượt gate. Xem [đối chiếu query](e5-rrf-validation-91.md).

Kiểm tra gate hiện tại từ gốc repo:

```bash
backend/.venv/Scripts/python.exe -B scripts/run_e5_rrf_validation.py --preflight-only
```

Kết quả mong đợi hiện tại: `status="blocked"`,
`reason="canonical_query_artifact_not_confirmed"`, `models_loaded=false`, exit 2.
Chưa đọc CSV benchmark, nạp weights, mở index hoặc tạo output khi config pending.
`--help` chỉ in hướng dẫn. Không có cờ force/bỏ kiểm tra hash.

Để chạy thật cần một config confirmed **được review**, ghi:

- Xác nhận của owner về artifact/commit queries và SHA-256 raw bytes tái lập.
- Liên kết issue comment/PR xác nhận canonical inputs; xác nhận contract fusion
  không thay xác nhận query artifact.
- Byte policy cụ thể: `bom` boolean, `newline` là `LF`/`CRLF`,
  `final_newline` boolean. Runner không chuyển bytes trước hash.
- Các pins query/qrels/candidate metadata khớp manifest benchmark và file thật.
  Nếu hash khóa sai, cập nhật benchmark cần review; giữ nguyên query/qrels/test.

Sau confirmation, preflight còn kiểm 70 query, split 28/42, query group không
giao nhau, 200 candidate IDs duy nhất và đủ 200 judgments/query. Chỉ trả 28
validation query tiếng Anh cùng relevant IDs (`relevance >=1`). Test rows chỉ
dùng IDs/split/group để kiểm toàn vẹn; text/test relevance không dùng để search,
tính metric, ghi raw output hoặc chọn cấu hình. Cần đúng 7 query validation
không positive, mẫu số Recall 21; không âm thầm đổi protocol nếu số này khác.

## Cách gọi sau khi input đã được xác nhận

Ví dụ dưới đây yêu cầu file confirmed sau review; file đó **chưa được tạo**
trong nhánh chuẩn bị runner này:

```bash
backend/.venv/Scripts/python.exe -B scripts/run_e5_rrf_validation.py --config evaluation/configs/issue91-e5-rrf-validation.confirmed.json --preflight-only
```

Sau preflight thành công, chọn một k tường minh và thư mục output mới:

```bash
backend/.venv/Scripts/python.exe -B scripts/run_e5_rrf_validation.py --config evaluation/configs/issue91-e5-rrf-validation.confirmed.json --rrf-k 60 --clip-index-root data/processed/issue89/clip-preflight-76d5d2c095b6 --clip-input-root data/processed/issue89/inputs-1d75f15977be --e5-index-root data/processed/issue91/e5-index-20261113-2 --output data/processed/issue91/validation-k60-new-run --device cpu
```

Một run so CLIP-only, E5-only, RRF với cùng inputs và k đã truyền. Grid đã đề
xuất `{10,20,60}` chạy thành các gói riêng, mỗi gói có baseline/timing của cả
ba cấu hình; runner không tự chọn k hoặc tuyên bố model tốt hơn. `60` trong ví
dụ là tham số tường minh, chưa là lựa chọn validation. Cùng service, models,
index pins, filters `{}` và source/cutoff 200 cho mọi phép so sánh.

Caller tạo encoder/client một lần, chỉ lấy weights từ cache offline và mở
storage đã có. Gói E5 và CLIP phải có cùng snapshot/source hash/IDs/metadata.
Không create/upsert/rebuild, tải model hoặc fallback sang nguồn khác. Trước/sau
query, service vẫn kiểm exact RAM transitions; cuối run đóng/mở client và yêu
cầu persisted fingerprints khớp lúc đầu. Không sửa shared retrieval/fusion.

## Raw, metrics và latency

`evaluation.e5_rrf_validation` điều phối, còn retrieval/fusion gọi trực tiếp
`CLIPTextSource`, `E5MetadataSearchService`, `ExperimentalFusionService` hiện có.
Metric gọi nguyên `evaluation.run_keyword_baseline.compute_metrics`, cùng
cách xử lý no-positive đã dùng W3; không gọi metric runner tổng quát vốn từ
chối query không có relevant IDs.

Mỗi cấu hình chạy tuần tự:

1. 5 warm-up request dùng 5 validation query đầu theo thứ tự CSV; không đo.
2. Theo thứ tự CSV, đo 10 lần/query, tổng 280 samples/cấu hình.
3. Lấy ranking lần đo đầu của mỗi query để xuất raw/tính quality. Không thêm
   lượt quality riêng hoặc dùng cached ranking thay call service trong timing.
4. Mỗi lượt vẫn yêu cầu đúng 200 asset duy nhất, rank liên tục và provenance
   ổn định. Repeat giữ source order/RRF scores/contributions chính xác;
   raw cosine chỉ cho roundoff diagnostic tối đa `1e-12`, ghi delta thực tế.
5. So nguồn raw trong RRF với ranking standalone cùng query, rồi kiểm lại
   hashes input/config và persisted indexes sau tất cả lượt gọi.

Timing từ ngay trước gọi service đến khi service trả DTO: gồm encode,
retrieval, audits và fusion. Kiểm/serialize/export raw, metric, model load,
index open/build và audit/reopen cuối không tính vào request latency. p50/p95
dùng nearest-rank: với 280 samples, lấy phần tử thứ 140/266 sau sort, không
interpolate. Run record ghi device, actual threads/packages/machine/module
hashes và dirty flag. Số timing của fixtures không phải latency mô hình thật.

Gói chạy thật thành công gồm:

| File | Nội dung |
|---|---|
| `run.json` | Status, protocol, input/config hashes/confirmation, parameters, provenance, metrics/per-query, latency summary và errors/skipped |
| `run-config.json` | Nguyên bytes config đã dùng |
| `raw-rankings.jsonl` | 84 query/config records: query ID/text/group, validation split, relevant IDs, raw ranked DTO; 200 hits có asset/rank/score, sources/contributions/filters/versions |
| `latency-samples.jsonl` | 840 measured samples: config/query/repetition, ms, count/config version, raw-result hash và cosine delta |
| `clip-index-manifest.json`, `e5-index-manifest.json` | Bản manifest đúng reference/hash trong raw provenance |

Raw RRF DTO chứa cả 200 hit của mỗi nguồn và 200 hit fused; thứ tự/rank nguồn
và contribution giữ nguyên từ service. Raw là JSONL theo query/config với
mảng ranked hits, không phải một dòng mỗi hit. `run.json` ghi hash các file
trong gói (không tự hash chính nó). Giữ raw lớn ở local/ngoài Git; commit report
summary nhỏ khi có kết quả thật và review.

Preflight bị chặn trả exit 2 và không tạo run. Lỗi sau khi bắt đầu trả exit 1,
giữ partial raw/latency và `run.json` với phase/config/query/repetition lỗi,
completed sample count và danh sách query chưa hoàn tất. Metrics chỉ được dùng
khi **toàn run `status="passed"`**, không diễn giải partial output thành run
đạt hoặc bỏ query lỗi khỏi mẫu số. Output đã tồn tại luôn bị từ chối.

## Kiểm chứng runner

```bash
backend/.venv/Scripts/python.exe -B -m pytest -c backend/pytest.ini backend/tests/unit/test_e5_rrf_validation.py -q -p no:cacheprovider -o faulthandler_timeout=30
```

Fixtures tự tạo 70 query/200 assets, dùng provider/clock có nhãn fixture và hàm
orchestration/RRF thật. Một test tích hợp DTO dùng encoder fixture + Qdrant
thật từ tests service; không nạp weights hoặc mở benchmark query/qrels thật.
Fixture outputs luôn ghi `execution_kind="fixture"`, `benchmark=false`.

Việc có runner/tests không hoàn thành tiêu chí 5/6 của #91. Canonical input
confirmation, raw validation thật, quality/latency report và bàn giao cuối vẫn
còn chờ. Phần `evaluation/` và protocol cần Khuê review trong PR riêng.


## Kết quả local — 13/11/2026

- Riêng runner **56 passed, 28,23 s**; toàn backend unit **930 passed, 182,22 s**;
  suite evaluation hiện có **23 passed, 9,10 s**.
- CLI help đạt. Preflight mặc định trả đúng `blocked`, exit 2,
  `canonical_query_artifact_not_confirmed`, `models_loaded=false`.
- Các assertions về 84 raw records/840 samples, mẫu số 21/28, nearest-rank,
  repeat/source comparison, failure bookkeeping và CLI lifecycle đã đạt với
  fixtures. Không coi các số metric/timing fixture là kết quả mô hình thật.
- [Bằng chứng local](../evidence/issue91-validation-runner-fixtures-20261113.json)
  ghi commands, log/module hashes, base `8d6eb3d` và dirty=true theo lúc chạy.
  CI/review/merge cho nhánh runner được theo dõi riêng; canonical inputs còn
  pending, chưa chạy validation weights thật hoặc chọn k.
