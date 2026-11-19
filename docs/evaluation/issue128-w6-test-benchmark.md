# Issue #128 — W6 benchmark trên test set

## Trạng thái

- Trạng thái chạy: benchmark hoàn tất trên 42 text và 12 image test queries theo frozen config; không query lỗi. Preflight model/storage đã qua, Qdrant chỉ mở bản sao tạm, storage gốc không đổi. Readiness checker báo `test_authorized=false` vì nó không xác minh approval/handoff GitHub; owner đã chủ động chạy runner với cờ xác nhận held-out test.
- Cấu hình: `w6-clip-e5-rrf-k20-candidate200-v1`.
- Config commit đã merge: `f1c65e8f6d2795eafd7dfd7034da3d6f497fe1f7` (PR #130).
- Config SHA-256 kỳ vọng: `1e1962058528e22b5235d989a3613b5077c02d479b8ac19e8dbc28fee0bd08d5`.
- Handoff: Khuê đã xác nhận tiếp nhận artifact tại Issue #114; xác nhận này không chứng minh local inputs, weights, Qdrant hay benchmark đã sẵn sàng.
- Đối chiếu trao đổi #114: Chi đã bàn giao quyết định, ADR/config frozen, revision/pin và hash. Comment bàn giao mới bổ sung `issue114-local-inputs-pinned-v1.zip` (144,330 bytes; SHA-256 `289b3b9b0851a92a14ee2181257e794cf5b8fe757b3e4cdd9b4675c6e015e371`) cùng manifest cho 7 file local. Các hash từng file trong manifest khớp các bindings ở config frozen. Gói không gồm model weights hoặc live Qdrant storage.

## Protocol cố định

- Snapshot: `home-interior-clear-200-v3`, 200 candidates.
- Text: test split gồm 42 query tiếng Anh; CLIP text-to-preview + E5 text-to-metadata, RRF k=20, weights 1/1, source window/cutoff 200, filters `{}`.
- Image: test split gồm 12 query similarity, CLIP image-to-preview, candidate limit 200; không có same-ID query.
- Giữ nguyên query, qrels, candidate universe, model/index/corpus pins và preprocessing trong config frozen.
- Metric primary: binary nDCG@10. Báo cáo thêm Recall@5/10 và Hit@5/10 theo đúng định nghĩa, mẫu số test split và loại query tương ứng trong artifact.
- Latency là tradeoff có ghi phạm vi đo; không có budget định lượng hoặc tiêu chí pass/fail đã khóa.

## Preflight

| Kiểm tra | Kết quả |
|---|---|
| Branch | `test/128-run-benchmark` |
| Config commit/hash đã review | Đã xác minh frozen artifact trên checkout với SHA-256 `1e1962058528e22b5235d989a3613b5077c02d479b8ac19e8dbc28fee0bd08d5`; commit PR #130 |
| Tracked input pins | Verifier qua config, query/qrels, manifests và các pin đã bàn giao |
| Local manifests/index inputs | Đã xác minh bằng verifier và dependency checker: `local_inputs_verified=true` |
| Weights/cache và Qdrant readiness | Đã xác minh offline: CLIP/E5 nạp đúng pinned revisions; mỗi storage có 200 point và fingerprint khớp handoff. Checker chỉ mở bản sao tạm; storage gốc không đổi |
| Runner | `scripts/run_issue128_w6_benchmark.py`, dùng service CLIP/E5/RRF và image hiện có; xác thực frozen config/local pins, chỉ đọc bản sao Qdrant tạm |
| Benchmark | Lượt hoàn chỉnh mới nhất `evaluation/results/issue128-w6-20261119-rerun1/`: 42/42 text và 12/12 image queries thành công, không lỗi; raw rankings và report đã được lưu. Lượt partial trước đó chỉ là lịch sử lỗi runner, không dùng metric của lượt đó |

Lệnh verifier đã chạy trên máy thực hiện: `backend\\.venv\\Scripts\\python.exe -B scripts\\verify_issue114_frozen_config.py --repo . --expected-sha256 1e1962058528e22b5235d989a3613b5077c02d479b8ac19e8dbc28fee0bd08d5 --local-inputs`.
Kết quả: `status=blocked`, `reason=missing_dependency:data/processed/issue89/clip-preflight-76d5d2c095b6/index-manifest.json`, `models_loaded=false`, `benchmark_executed=false`, `test_authorized=false`.
Lệnh `Test-Path` trước khi Chi gửi package xác nhận `False` cho toàn bộ 7 file local được yêu cầu:

- `data/processed/issue89/clip-preflight-76d5d2c095b6/index-manifest.json`
- `data/processed/issue89/inputs-1d75f15977be/source.json`
- `data/processed/issue89/inputs-1d75f15977be/ready.json`
- `data/processed/issue91/e5-index-20261113-2/index-manifest.json`
- `data/processed/issue91/e5-index-20261113-2/source.json`
- `data/processed/issue91/e5-index-20261113-2/corpus-manifest.json`
- `data/processed/issue91/e5-index-20261113-2/corpus.jsonl`

Comment mới của Chi cung cấp link tải package và hướng dẫn giải nén vào repository root. Người chạy đã kiểm SHA-256 ZIP input trước giải nén, giữ nguyên các đường dẫn `data/processed/...`, rồi chạy verifier thành công. Output xác nhận config SHA khớp, `local_inputs_verified=true`, nhưng cũng ghi `models_loaded=false`, `live_qdrant_verified=false`, `benchmark_executed=false`, `test_authorized=false`. Package input chỉ có manifests/input/corpus metadata, không có Qdrant storage hay model weights.

Kiểm tra `Test-Path` trước khi nhận gói Qdrant cho kết quả `False` với cả hai file `qdrant/meta.json` dưới CLIP index root và E5 index root. Gói `issue114-qdrant-storage-handoff-v1.zip` có SHA-256 `9bf6cfa67179387e249d9089af54e66564de81b201f9f60f4238a1b387235ee4`; người chạy xác nhận ZIP và từng file trong manifest đều khớp. Sau khi khôi phục storage và tải đúng model snapshots, người chạy thực hiện checker offline. Kết quả: `status=dependencies_verified_without_queries`, `stage=complete`, `models_loaded=true`, `retrieval_queries_executed=0`, `benchmark_executed=false`, `test_authorized=false`, `network_downloads_enabled=false`, `qdrant_opened_on_temporary_copies_only=true`, `local_inputs_verified=true`, `original_storage_bytes_unchanged=true`. CLIP và E5 đều resolve đúng revisions đã pin; mỗi storage có 200 points/assets duy nhất và fingerprint SHA-256 khớp handoff. Đây chỉ là dependency/storage preflight: checker không chứng minh approval/handoff GitHub và không chạy truy vấn. Không ghi nhận benchmark hay quality metric từ bước này.

Lệnh checker trên máy owner trả về `status=dependencies_verified_without_queries`, `stage=complete`, `models_loaded=true`, `retrieval_queries_executed=0`, `benchmark_executed=false`, `test_authorized=false`, `network_downloads_enabled=false`, `qdrant_opened_on_temporary_copies_only=true`, `local_inputs_verified=true`, `original_storage_bytes_unchanged=true`. CLIP/E5 resolve đúng revision đã pin; cả hai storage có 200 point và fingerprint khớp handoff. `test_authorized=false` là giới hạn của checker (không xác minh GitHub), không phải lỗi readiness. Handoff #114 đã được owner Khuê xác nhận trong phiên này; người chạy cần chủ động xác nhận held-out test bằng cờ CLI của runner.

Đã chạy lại checker theo yêu cầu bàn giao của Chi; kết quả vẫn là `status=dependencies_verified_without_queries`, `stage=complete`, các model/storage audit khớp như trên và `EXIT_CODE=0`. Toàn bộ JSON output cùng exit code đã được gửi trong comment trên Issue #114. Bước này không chạy retrieval query hoặc benchmark.

Lượt chạy đầu của runner dừng trước model loading và trước retrieval với `text_test_query_has_no_positive_qrel`; không output benchmark được tạo. Đây là trường hợp hợp lệ của qrels, không sửa nhãn. Runner đã được sửa: query không có positive qrel được giữ với binary nDCG/Hit bằng 0; Recall chỉ lấy mẫu số từ query có positive, đồng thời raw/report liệt kê số lượng và ID query đó.

Lượt chạy kế tiếp ban đầu ghi `status=partial`, output `evaluation/results/issue128-w6-20261119/`: 12/12 image queries hoàn tất; 42 text queries bị ghi lỗi `AttributeError` sau khi gọi service vì runner đọc nhầm thuộc tính provenance `snapshot` trên `FusionSearchResult`. Các lời gọi retrieval text đã thực thi, nhưng ranking IDs không được lưu nên không thể tính metric text. Raw image metrics được giữ làm evidence của partial run, không coi là báo cáo hoàn tất. Lỗi serialize đã được sửa theo các trường thực có (`candidate_snapshot`, `source_manifest_sha256`, `sources`, ...). Sau đó lượt chạy lại `evaluation/results/issue128-w6-20261119-rerun1/` hoàn tất cả 42 text và 12 image queries như ghi ở phần Bằng chứng chạy. Storage gốc giữ nguyên.

Runner `scripts/run_issue128_w6_benchmark.py` gọi trực tiếp `ExperimentalFusionService` và `ImageSearchService`; kiểm tra hash/split/count trước khi truy vấn, nạp model offline, chỉ mở Qdrant trên bản sao tạm, ghi raw results và report vào output mới, từ chối ghi đè. Nó không đổi frozen config, query, qrels hoặc shared runtime. Lượt chạy lại chỉ nhằm khắc phục lỗi serialize và lưu rankings; không dùng kết quả để chọn/tune cấu hình. Lệnh của lượt hoàn chỉnh:

```powershell
backend\.venv\Scripts\python.exe -B scripts\run_issue128_w6_benchmark.py --repo . --expected-sha256 1e1962058528e22b5235d989a3613b5077c02d479b8ac19e8dbc28fee0bd08d5 --output evaluation/results/issue128-w6-20261119-rerun1 --work-root (Join-Path $env:TEMP "issue128-benchmark-work") --acknowledge-held-out-test
```

## Bằng chứng chạy

Dữ liệu dưới đây được ghi nhận từ lượt benchmark hoàn chỉnh. Không dùng test results để thay đổi lựa chọn hoặc protocol.

- Commit code chạy: chưa commit; runner, báo cáo và kết quả đang ở working tree của nhánh `test/128-run-benchmark`.
- Thời gian truy vấn: `2026-11-19T16:50:16.884682Z` đến `2026-11-19T16:51:39.735871Z` (23:50–23:51, Asia/Bangkok).
- Máy / OS / Python / package versions: AMD64, Windows 11 `10.0.26200-SP0`, Python `3.13.15`, torch `2.8.0`, transformers `4.57.1`, qdrant-client `1.15.1`, numpy `2.5.4`, Pillow `13.0.0`; CPU, offline.
- Lệnh tái lập: `backend\.venv\Scripts\python.exe -B scripts\run_issue128_w6_benchmark.py --repo . --expected-sha256 1e1962058528e22b5235d989a3613b5077c02d479b8ac19e8dbc28fee0bd08d5 --output evaluation/results/issue128-w6-20261119-rerun1 --work-root (Join-Path $env:TEMP "issue128-benchmark-work") --acknowledge-held-out-test`.
- Search service/model/index versions: text `experimental-fusion-v1-4f51ac0f1b059492`, RRF `rrf-v1-60eb3c31b7172bdc`; CLIP `openai/clip-vit-base-patch32@3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`, index `issue89-clip-preflight-76d5d2c095b6`; E5 `intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3`, index `issue91-e5-metadata-1588f4dc33fbe62609d8`; image service config `image-exact-all-filtered-rgb-v1-k200` on the CLIP index.
- Query thành công / lỗi / bỏ qua: text `42/42/0`; image `12/12/0`. Qrels có 4 text query không positive (`q0031`, `q0053`, `q0057`, `q0066`); nDCG/Hit tính 0 trên toàn bộ 42 query, Recall lấy mẫu số 38 positive query.
- Raw results file: `evaluation/results/issue128-w6-20261119-rerun1/raw-results.json`.
- Metric report file: `evaluation/results/issue128-w6-20261119-rerun1/report.json`.
- Giới hạn và sai lệch protocol: một lượt/query, không warmup; latency đo wall time của service call, gồm query encoding, audit, local Qdrant và fusion (image còn gồm đọc/giải mã ảnh). p95 nearest-rank trên 12 image samples là giá trị lớn nhất trong 12 mẫu; không phải cam kết steady-state/HTTP API latency. Qdrant chỉ mở bản sao tạm; hash storage gốc trước/sau không đổi.

### Kết quả

| Split / loại query | Số query | Binary nDCG@10 | Recall@5 | Recall@10 | Hit@5 | Hit@10 | Latency p50/p95 |
|---|---:|---:|---:|---:|---:|---:|---|
| Text test | 42 (38 positive cho Recall) | 0.6683 | 0.3429 | 0.5798 | 0.7857 | 0.8810 | 1,573.75 / 2,270.06 ms |
| Image similarity test | 12 | 0.6646 | 0.4846 | 0.5935 | N/A (similarity, không phải same-ID) | N/A (similarity, không phải same-ID) | 216.88 / 8,163.30 ms |

## Ghi chú

- Verifier của frozen config chỉ xác nhận hash và file pins (với `--local-inputs`); không xác thực GitHub approval/handoff, không mở weights/Qdrant và không cấp quyền chạy test.
- Lượt benchmark hoàn chỉnh là thư mục `evaluation/results/issue128-w6-20261119-rerun1`; lệnh lặp lại cùng output bị runner từ chối vì output đã tồn tại, không ghi đè và không chạy thêm query.
- Kết quả test chỉ dùng báo cáo theo frozen protocol; không dùng để đổi model/RRF/filters hoặc nhãn.
- Reviewer đối chiếu kết quả vẫn đang chờ; benchmark hoàn tất local không tự hoàn tất review/tích hợp Issue. Cần đưa runner, báo cáo và artifacts của lượt hoàn chỉnh vào PR tới `develop`, rồi nhờ một thành viên khác review raw results và bằng chứng chạy.
- Nếu preflight/runtime không đạt, ghi blocker cụ thể và không gọi đó là benchmark hoàn tất.
