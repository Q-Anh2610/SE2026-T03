# Config confirmed và validation thật — #91

## Căn cứ đầu vào

Khuê chốt artifact tại [bình luận #91](https://github.com/Q-Anh2610/SE2026-T03/issues/91#issuecomment-6859981671).
[PR #109](https://github.com/Q-Anh2610/SE2026-T03/pull/109) đã được Khuê approve
trên `5472abea7fcd6a9b279be30f236b3e6305ebb16c` và merge vào develop tại
`63122a3a05a920a847793253a4527a871d5aa6e8`.

Config `evaluation/configs/issue91-e5-rrf-validation.confirmed.json` ghi:

- Query nguồn: `ff7b64abbbb21677fc2fc6f6ac7daf6f2025742a:data/benchmark/queries.csv`.
- Query SHA-256 raw: `e202a0dc62406826ec29a2946d489c359a222133e6c530a9954832760d965470`.
- 7.851 byte, UTF-8 có BOM, LF, không CR, giữ 4 LF cuối file.
- PR, commit head và commit merge của erratum; đường dẫn/hash raw của bản ghi erratum hiện dùng.
- Qrels, candidate metadata và protocol giữ nguyên các pins đã review.

Schema config v2 thêm `artifact_provenance`; v1 vẫn được hỗ trợ để giữ tương thích
fixtures/config cũ. Default CLI vẫn dùng file `pending` v1, không tự bật benchmark.
Không thay bản ghi erratum, query, qrels hoặc kết quả baseline lịch sử.

Preflight v2 đối chiếu hash bản ghi và toàn bộ mô tả source với query bytes thật,
bao gồm BOM, kích thước và số LF cuối file. Đây là kiểm tra offline: các commit và
liên kết ghi lại căn cứ review/merge đã quan sát; validator không tự xác thực quyền
review hoặc trạng thái GitHub. Không thêm kết nối mạng hay chuẩn hóa bytes để khớp hash.

## Preflight trước khi nạp models

Từ gốc repo, chạy từng lệnh:

```bash
backend/.venv/Scripts/python.exe -B scripts/verify_issue91_query_artifact.py --repo . --compare-source-commit
backend/.venv/Scripts/python.exe -B scripts/run_e5_rrf_validation.py --config evaluation/configs/issue91-e5-rrf-validation.confirmed.json --preflight-only
```

Cần `passed` cho artifact và `inputs_verified`, 28 validation query,
`models_loaded=false` cho confirmed preflight. Default không truyền `--config`
tiếp tục trả `blocked`, exit 2. Pending checker không có nghĩa config confirmed bị chặn.

## Grid và gói kết quả

Theo [protocol của Khuê](https://github.com/Q-Anh2610/SE2026-T03/issues/91#issuecomment-6829347357),
chạy tuần tự k=10,20,60 thành ba gói output mới. Mỗi gói chạy mới CLIP-only,
E5-only và RRF trên cùng 28 validation query, candidate/source window/cutoff 200,
filters `{}`. Không dùng 42 query test để tune hoặc dùng baseline cũ làm control mới.

Ví dụ gói đầu (nếu đường dẫn output đã tồn tại thì dùng tên mới):

```bash
backend/.venv/Scripts/python.exe -B scripts/run_e5_rrf_validation.py --config evaluation/configs/issue91-e5-rrf-validation.confirmed.json --rrf-k 10 --clip-index-root data/processed/issue89/clip-preflight-76d5d2c095b6 --clip-input-root data/processed/issue89/inputs-1d75f15977be --e5-index-root data/processed/issue91/e5-index-20261113-2 --output data/processed/issue91/validation-20261114-k10-1 --device cpu
```

Hai gói tiếp thay k và output tương ứng; giữ cùng models/indexes/config. Dùng cache
offline hiện có; không tải weights hoặc rebuild index. Không chạy job nặng khác
trong lúc đo. Mỗi cấu hình có 5 warm-up và 280 samples; mỗi gói có 84 raw records,
840 measured samples. Recall mẫu số 21, Hit/nDCG mẫu số 28; p50/p95 nearest-rank.
Chi tiết phạm vi timing, DTO và failure bookkeeping nằm trong
[guide runner](e5-rrf-validation-runner-91.md).

Gói v2 thêm `query-artifact-erratum.json` nguyên bytes và provenance trong `run.json`,
đồng thời kiểm hash bản ghi trước mở factory và sau toàn run. Chỉ dùng metrics khi
toàn run passed, errors rỗng, không skipped query và persisted fingerprints giữ nguyên
sau đóng/mở lại. Raw lớn ở `data/processed/`, không stage vào Git.

## Trạng thái bàn giao

Ba run k=10/20/60 đã passed ngày 14/11/2026, raw/metrics/latency đã audit lại.
Xem [báo cáo validation](../evaluation/issue91-e5-rrf-validation-20261114.md) và
[bằng chứng](../evidence/issue91-e5-rrf-validation-20261114.json). Chưa khóa k;
nhờ Khuê review đánh đổi và chốt lựa chọn có căn cứ. CI/review/merge của PR kết quả
vẫn là bước riêng. CLIP vẫn mặc định; không nối shared API/runtime/search events
hoặc kết luận model cuối trước W6.

Kiểm thử thay đổi loader/provenance bằng fixtures (không nạp model):

```bash
backend/.venv/Scripts/python.exe -B -m pytest -c backend/pytest.ini backend/tests/unit/test_e5_rrf_validation.py backend/tests/unit/test_issue91_confirmed_inputs.py backend/tests/unit/test_issue91_query_artifact.py -q -p no:cacheprovider
```

## Kiểm chứng local — 14/11/2026

- Runner, confirmed provenance và artifact suites: **112 passed, 60,31 s** bằng fixtures.
- Confirmed preflight thật: `inputs_verified`, 28 validation queries, `models_loaded=false`.
- Default preflight: `blocked`, `canonical_query_artifact_not_confirmed`, `models_loaded=false`.
- Artifact checker có `--compare-source-commit`: `passed`; query/source bytes và
  các input/result lịch sử giữ nguyên.
- Ba gói model thật đã passed, tổng 252 raw records/2.520 measured samples;
  audit đọc lại raw đạt, tính lại metrics/percentiles khớp. Chưa chọn/khóa k.
