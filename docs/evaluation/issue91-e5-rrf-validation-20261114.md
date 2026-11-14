# Validation CLIP/E5/RRF — #91, ngày 14/11/2026

## Kết quả và giới hạn quyết định

Ba gói weights thật CPU k=10,20,60 đều passed. Audit sau chạy xác nhận
**252 raw records, 2.520 measured samples, 45 warm-up calls**, không lỗi/skipped query.
Recall/nDCG của RRF cải thiện so với CLIP-only mới trên cùng input; E5-only thấp hơn
CLIP trên các metrics đang báo cáo. RRF có latency cao hơn CLIP trong cả ba gói.
CLIP tiếp tục là mặc định; không đổi shared API/runtime/search events hoặc chọn model cuối W6.

**Chưa khóa k hoặc tự chọn winner.** k=20 có nDCG@10 và Recall@5 cao nhất trong grid;
k=10 có Recall@10 cao nhất và p50/p95 RRF thấp nhất trong các lần đo này.
Không có primary selection metric được khóa trước grid, nên bàn giao đầy đủ đánh đổi
để Khuê review/chốt tiêu chí lựa chọn trước khi khóa cấu hình hay chạy test.

## Đầu vào và protocol

- Theo [protocol Khuê](https://github.com/Q-Anh2610/SE2026-T03/issues/91#issuecomment-6829347357)
  và [contract Quỳnh Anh](https://github.com/Q-Anh2610/SE2026-T03/issues/91#issuecomment-6849816002).
- Artifact được chốt qua [PR #109](https://github.com/Q-Anh2610/SE2026-T03/pull/109),
  merge `63122a3a05a920a847793253a4527a871d5aa6e8`; nguồn
  `ff7b64abbbb21677fc2fc6f6ac7daf6f2025742a:data/benchmark/queries.csv`.
- Query SHA-256 raw `e202a0dc62406826ec29a2946d489c359a222133e6c530a9954832760d965470`:
  7.851 byte, UTF-8 BOM, LF, 4 LF cuối. Qrels raw
  `cc1d42f6e3f41f92fab1b842c7a70ca68be4341cdd30e4262e13989f99019df5`.
- Snapshot `home-interior-clear-200-v3`, metadata SHA-256
  `9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`;
  đúng 200 asset, source windows/cutoff 200, filters `{}`, weights RRF bằng 1.
- Chỉ 28 validation query tiếng Anh; không dùng 42 test query để search/tính quality/tune.
  Qrels positive >=1, binary gain. Recall macro có mẫu số 21; Hit/nDCG có mẫu số 28,
  giữ 7 query không positive ở điểm 0. Hit@10 tối đa 21/28=0,75 theo tập nhãn này.
- Mỗi gói đo mới cả CLIP-only/E5-only/RRF: 5 warm-up rồi 10 lượt/query/cấu hình,
  tuần tự theo CSV. Raw là lượt đo đầu, đủ 200 hit/source/fused.
- Metric dùng nguyên `evaluation.run_keyword_baseline.compute_metrics`;
  không dùng baseline lịch sử có hash `f627…` chưa tái lập làm control tương đương.

## Chất lượng validation

| Cấu hình | Recall@5 | Recall@10 | Hit@5 | Hit@10 | binary nDCG@10 |
|---|---:|---:|---:|---:|---:|
| CLIP-only | 0.32947 | 0.49300 | 0.67857 | 0.75000 | 0.46982 |
| E5-only | 0.16651 | 0.35016 | 0.57143 | 0.67857 | 0.36223 |
| RRF k=10 | 0.35006 | 0.56414 | 0.71429 | 0.75000 | 0.52589 |
| RRF k=20 | 0.35848 | 0.55620 | 0.71429 | 0.75000 | 0.53126 |
| RRF k=60 | 0.31933 | 0.53809 | 0.67857 | 0.75000 | 0.52149 |

Các số CLIP/E5 trong bảng khớp **chính xác trên cả ba gói**; source ranks,
provenance và raw cosine của từng query cũng khớp giữa grid (max delta 0,0).

So với CLIP cùng gói, RRF k=20 tăng nDCG@10 **0.06143** và Recall@10
**6.32 điểm phần trăm**. Hit@5 tăng từ 19/28 lên 20/28;
Hit@10 giữ 21/28. k=10 tăng Recall@10 hơn k=20 nhưng nDCG@10 thấp hơn.
k=60 không vượt k=10/20 trên các quality metrics được báo cáo; Recall@5 của k=60
thấp hơn CLIP. Không kết luận mức cải thiện có ý nghĩa thống kê từ phép đo này.

## Latency CPU

| Gói | Cấu hình | Samples | p50 (ms) | p95 (ms) |
|---|---|---:|---:|---:|
| k=10 | clip_only | 280 | 430.52 | 548.87 |
| k=10 | e5_only | 280 | 375.71 | 449.99 |
| k=10 | clip_e5_rrf | 280 | 821.35 | 897.60 |
| k=20 | clip_only | 280 | 425.22 | 597.57 |
| k=20 | e5_only | 280 | 388.80 | 488.27 |
| k=20 | clip_e5_rrf | 280 | 911.91 | 1217.07 |
| k=60 | clip_only | 280 | 489.89 | 684.14 |
| k=60 | e5_only | 280 | 395.03 | 497.39 |
| k=60 | clip_e5_rrf | 280 | 886.58 | 1139.00 |

p50/p95 nearest-rank trên 280 samples/cấu hình: phần tử thứ 140/266 sau sort,
không interpolate và không gộp samples của ba gói để chọn số đẹp.
Phạm vi là lời gọi service: query encoding + retrieval + exact audits + fusion;
không gồm model load, index open/build, serialize/export/metrics hoặc audit/reopen cuối.
Đây không phải HTTP/API latency hay riêng thời gian tính công thức RRF.

Trong gói k=20, p50/p95 RRF tương ứng **2.14x/2.04x** CLIP.
Ngay cả baseline CLIP có p50 thay đổi 425,22–489,89 ms giữa các gói, nên không quy
mọi chênh lệch latency giữa k=10/20/60 cho tham số k. Mỗi k chỉ có một run, thứ tự
không random hóa, chưa có lặp toàn grid hoặc confidence intervals.

## Môi trường, provenance và tính toàn vẹn

- CPU, Windows 11 build 26200, Python 3.13.7; processor ghi nhận
  `Intel64 Family 6 Model 140 Stepping 2, GenuineIntel`, machine AMD64.
- Torch intra-op/inter-op đều 4 threads. Packages: torch 2.8.0, transformers 4.57.1,
  qdrant-client 1.15.1, numpy 2.5.4, pydantic 2.14.1.
- CLIP `openai/clip-vit-base-patch32` revision
  `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`; E5 `intfloat/multilingual-e5-small`
  revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`, cache offline.
- Corpus recipe `e5-metadata-passage-v1-draft`, SHA-256
  `66efd87e34447c23b4171e13ac77d78a9c193519141d0dd6a31985c01e65b4f5`.
- Đo từ base `63122a3a05a920a847793253a4527a871d5aa6e8`, **dirty=true**:
  loader/config confirmed được chạy từ working tree trên nhánh
  `test/91-e5-rrf-validation-results`. Không gán ngược commit tạo sau cho run cũ.
  Hash raw bytes của 13 module, config, manifests và từng raw file nằm trong bằng chứng.
- CLIP/E5 persisted fingerprints trước và sau close/reopen khớp chính xác trong cả ba gói.
  Exact RAM transition audit vẫn chạy; không làm tròn vector hoặc nới tolerance.
  Repeat cosine diagnostic <=1e-12; actual maxima và standalone/fusion deltas ghi theo từng gói.
- Auditor đọc lại file hashes, kiểm coverage/order/IDs/filters/provenance, tính độc lập
  RRF bằng Fraction từ raw source ranks, tính lại metrics và p50/p95 từ JSONL; tất cả khớp.
  Mọi repeat do runner kiểm; auditor chỉ bind hash DTO của lượt đầu vì các DTO repeat
  sau không xuất toàn bộ, đồng thời kiểm counts/order/timing diagnostics của cả 2.520 samples.

## Artifacts và cách tái lập

[Bằng chứng JSON](../evidence/issue91-e5-rrf-validation-20261114.json) chứa hashes,
runtime/source provenance, commands, metrics, latency và kết quả audit từng gói.
Raw local ở:

- `data/processed/issue91/validation-20261114-k10-1/`
- `data/processed/issue91/validation-20261114-k20-1/`
- `data/processed/issue91/validation-20261114-k60-1/`

Mỗi gói có run.json, run-config.json, raw-rankings.jsonl, latency-samples.jsonl,
hai index manifests và query-artifact-erratum.json. Raw lớn giữ ngoài Git;
review bundle ZIP được chuẩn bị riêng để Chi bàn giao Khuê, không chứa weights/index storage.
Các input/config/module hashes là **raw bytes** tại thời điểm chạy trên Windows;
khác EOL sẽ khác hash dù nội dung parse giống. Giữ bản gốc khi audit run đã ghi nhận.

Kiểm lại cả grid trên checkout và các raw packages hiện tại, dùng output mới:

```bash
backend/.venv/Scripts/python.exe -B scripts/audit_e5_rrf_validation_grid.py --repo . --output data/processed/issue91/grid-audit-review-1.json
```

Auditor không nạp weights, không chạy retrieval và không ghi đè gói benchmark.
Nó kiểm raw module/input bytes hiện tại so với lúc đo; nếu checkout đã đổi bytes,
đối chiếu archived input/runtime snapshots trước, không sửa hashes report để vượt kiểm tra.
Để **chạy benchmark mới**, dùng [guide confirmed/results](../guides/e5-rrf-validation-results-91.md),
cache và hai index đã pin; mỗi k phải có output mới. Không dùng tập test để chốt lại k.

## Bàn giao và phần còn lại

- Local raw validation và báo cáo đã có; nhờ Khuê review raw/bằng chứng và trade-off k.
- Chưa có approval/CI/merge cho PR kết quả này; không coi tests local hoặc các PR cũ là bằng chứng thay thế.
- Chờ chốt lựa chọn k có căn cứ, khóa cấu hình rồi mới xem xét bước test riêng theo kế hoạch nhóm.
- Giới hạn: 28 English queries, candidate curated 200, nhãn relevance hiện có;
  chưa chứng minh chất lượng tiếng Việt, khả năng tổng quát hóa hoặc production latency.
- Không tự nghiệm thu toàn W5, đóng issue hoặc chọn model cuối W6.
