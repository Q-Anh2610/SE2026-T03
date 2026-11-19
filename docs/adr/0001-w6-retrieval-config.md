# ADR 0001: Khóa cấu hình đánh giá W6 — CLIP/E5 RRF k=20

Ngày: 19/11/2026. Issue: [#114](https://github.com/Q-Anh2610/SE2026-T03/issues/114).

**Quyết định lựa chọn đã được thống nhất; bản triển khai/config còn chờ kiểm chứng trên checkout, PR review và Khuê tiếp nhận trước benchmark test.** “Frozen” trong artifact mô tả lựa chọn/pins cố định, không phải chứng nhận CI, approval, merge hoặc quyền chạy test.

## Bối cảnh và thời điểm chốt tiêu chí

W5 đã có validation CLIP-only/E5-only/RRF k=10/20/60 qua [PR #110](https://github.com/Q-Anh2610/SE2026-T03/pull/110). [PR #124](https://github.com/Q-Anh2610/SE2026-T03/pull/124) đối chiếu archive/metrics, không chạy retrieval mới. Không làm lại W5 để chọn cấu hình.

Tiêu chí sau đây được chốt **ở W6 sau khi đã xem grid W5**, không phải tiêu chí định trước grid. [Khuê](https://github.com/Q-Anh2610/SE2026-T03/issues/114#issuecomment-7008957829) đồng ý binary nDCG@10 cho thứ hạng top 10, công khai đánh đổi và giữ CLIP ảnh. [Quỳnh Anh](https://github.com/Q-Anh2610/SE2026-T03/issues/114#issuecomment-7009717002) xác nhận chọn k=20, chấp nhận Recall@10 thấp hơn k=10, cách xét tie và cách xử lý điều kiện latency.

- Primary: binary nDCG@10. Báo cáo kèm Recall@5/10 và Hit@5/10.
- Xét tie bằng giá trị đầy đủ: primary, rồi Recall@10, rồi chi phí vận hành. Không đặt dải “gần bằng”, minimum improvement hoặc ngưỡng % không có căn cứ.
- Latency trong freeze benchmark là đánh đổi được công bố, **chưa dùng làm tiêu chí đạt/trượt định lượng**. Chưa có budget numeric, không khẳng định đạt yêu cầu demo/HTTP. Ngân sách và kiểm chứng HTTP/end-to-end trên máy demo chốt riêng trước nghiệm thu vận hành.

## Bằng chứng cùng input/protocol

Nguồn: [báo cáo #91](../evaluation/issue91-e5-rrf-validation-20261114.md), [grid evidence](../evidence/issue91-e5-rrf-validation-20261114.json) và [đối chiếu archive #105](../evidence/issue105-archive-metrics-review-20261116.json).

Text `home-interior-text-v2`, snapshot `home-interior-clear-200-v3`, 28 English validation queries, 200 candidates, source retrieval/limits/fused cutoff 200, filters `{}`. Positive relevance >=1, binary gain; Recall macro chia 21, Hit/nDCG chia 28 gồm 7 no-positive query ở 0. Không dùng 42 text test queries để chọn cấu hình. Metric K=5/10 không thay candidate cutoff 200.

| Phương án | Recall@5 | Recall@10 | Hit@5 | Hit@10 | binary nDCG@10 |
|---|---:|---:|---:|---:|---:|
| CLIP-only | 0,32947 | 0,49300 | 0,67857 | 0,75000 | 0,46982 |
| E5-only | 0,16651 | 0,35016 | 0,57143 | 0,67857 | 0,36223 |
| RRF k=10 | 0,35006 | 0,56414 | 0,71429 | 0,75000 | 0,52589 |
| RRF k=20 | 0,35848 | 0,55620 | 0,71429 | 0,75000 | 0,53126 |
| RRF k=60 | 0,31933 | 0,53809 | 0,67857 | 0,75000 | 0,52149 |

k=20 so với k=10 tăng nDCG@10 khoảng 0,00537 và Recall@5 khoảng 0,00842, giảm Recall@10 khoảng 0,00794. Nhóm chấp nhận đánh đổi này theo mục tiêu đã chốt, không kết luận significance hoặc tối ưu ngoài tập đã đo. Hit@10 bằng 21/28=0,75 ở CLIP/RRF không phân biệt được các phương án này.

| Run | Mode | p50 (ms) | p95 (ms) |
|---|---|---:|---:|
| k=10 | CLIP-only | 430,52 | 548,87 |
| k=10 | E5-only | 375,71 | 449,99 |
| k=10 | RRF | 821,35 | 897,60 |
| k=20 | CLIP-only | 425,22 | 597,57 |
| k=20 | E5-only | 388,80 | 488,27 |
| k=20 | RRF | 911,91 | 1.217,07 |
| k=60 | CLIP-only | 489,89 | 684,14 |
| k=60 | E5-only | 395,03 | 497,39 |
| k=60 | RRF | 886,58 | 1.139,00 |

CPU Windows 11 build 26200, Python 3.13.7, processor `Intel64 Family 6 Model 140 Stepping 2, GenuineIntel`, Torch intra-op/inter-op 4/4. Mỗi mode có 5 warm-up, 10 lượt/query, 280 measured samples; p50/p95 nearest-rank ở vị trí 140/266 sau sort.

Timing là lời gọi service gồm query encode/retrieval/exact audits/fusion, loại model load/index open/build/export/metrics/final reopen. Không phải HTTP/API latency. Mỗi k có một run tuần tự; CLIP control cũng dao động. Không quy chênh lệch giữa run cho riêng k, không gộp samples để chọn số thuận lợi. Peak RAM, CPU utilization và disk/cache footprint chưa có số đo tương đương; không suy ra các chi phí đó từ dimension hoặc latency.

## Quyết định theo từng luồng

**Text:** chọn CLIP text-to-preview + E5 text-to-metadata, RRF k=20, weights 1/1. Hai source cùng snapshot/candidate metadata và filters; query trim, 1–500 ký tự; source retrieval/limits và fused cutoff đều 200. Giữ implementation `ExperimentalFusionService` và `RRFConfig`, không tạo thuật toán evaluation khác.

Source cosine exact, không score threshold, ordering score giảm dần rồi asset_id tăng dần, dedup max score/asset. RRF rank từ 1, duplicate ở lần đầu rồi contiguous unique rank, missing source góp 0; dùng Fraction để giữ tie toán học, RRF score giảm dần rồi asset_id tăng dần. Không cộng cosine/vector khác model. Lỗi một dependency phải báo lỗi, không fallback âm thầm sang CLIP.

**Ảnh:** giữ CLIP, cùng model/revision/preprocessing và reference index candidate200 của #89 trong artifact đánh giá. Policy `image-exact-all-filtered-rgb-v1-k200` dùng implementation image service hiện có. `k10` trong manifest preflight cũ là smoke diagnostic; file manifest được giữ nguyên, không giả rằng đã đo quality với policy k200. Chốt model ảnh không dựa vào text W5.

Ảnh đã có query/qrels/split khóa: `home-interior-image-v1`, 20 similarity queries, 8 validation/12 test, 0 same-ID. Thiếu benchmark quality/latency tương đương với raw results để so CLIP/SigLIP 2; smoke 354 previews và preflight candidate200 không thay thế phép so sánh này. Không áp dụng Hit@K theo mục tiêu same-ID. Tiếng Việt, SigLIP text và multi-view chưa được chứng minh trong phép so sánh này.

Đây là freeze cho **đánh giá**, không xác nhận reference index là active HTTP index. Shared API/runtime/search events giữ nguyên. Nếu nối RRF vào API, cần review riêng score_type, provenance, versions và xử lý lỗi.

## Phương án không chọn và hệ quả

- CLIP-only: giữ làm đối chứng và default service hiện hành; không chọn cho text benchmark W6 vì nDCG/Recall thấp hơn fusion. Đổi lấy một encoder/preview index và latency thấp hơn RRF cùng run.
- E5-only: thấp hơn CLIP ở cả 5 quality metrics được báo cáo, chưa có căn cứ chọn thay baseline theo mục tiêu này. Nếu ảnh giữ CLIP, text E5-only vẫn cần CLIP cho ảnh.
- k=10: Recall@10 cao nhất; không chọn vì nhóm chốt primary nDCG@10 và chấp nhận đánh đổi. Không kết luận k=10 nhanh hơn do riêng k từ các run hiện có.
- k=60: không vượt k=10/20 trên các quality metrics; Recall@5 thấp hơn CLIP.
- SigLIP 2 ảnh và mở rộng: hoãn kết luận do thiếu phép so sánh tương đương, không chọn vì model mới hơn.

Fusion cần hai encoder/cache/index, corpus/recipe và kiểm tương thích hai nguồn. Đổi k với cùng vector pins không đòi rebuild embedding; thay model/preprocessing/corpus cần index version/rebuild thích hợp. Không ghi đè active index hoặc trộn vector.

## Artifact, pins và byte policy

[Artifact](../../evaluation/configs/issue114-w6-retrieval.frozen.json) version `w6-clip-e5-rrf-k20-candidate200-v1`; [checksum](../../evaluation/configs/issue114-w6-retrieval.frozen.sha256). Model/processor/tokenizer revisions, dimensions, preprocessing, query/qrels/candidate pins, index versions/manifests, corpus/recipe, filters, windows, cutoff và tie-break nằm trong artifact.

CLIP revision `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`, 512 chiều, `clip-slow-processor-rgb-l2-v1`. E5 revision/tokenizer `614241f622f53c4eeff9890bdc4f31cfecc418b3`, 384 chiều, fast tokenizer/right truncate512, masked mean FP32 và L2, prefixes `query: ` / `passage: `.

CLIP index `issue89-clip-preflight-76d5d2c095b6`; E5 index `issue91-e5-metadata-1588f4dc33fbe62609d8`. E5 recipe `e5-metadata-passage-v1-draft` và các snapshot manifests giữ nguyên tên/trạng thái/provenance lịch sử; việc lựa chọn chính xác bytes này được ghi riêng ở W6. Không sửa trạng thái draft lịch sử trong snapshot để làm giống config mới.

Artifact mới: UTF-8 không BOM, LF, một LF cuối; SHA-256 toàn raw bytes gồm LF cuối, sidecar tránh tự tham chiếu. Snapshot E5 index/corpus manifests là bản sao raw nguyên bytes, `.gitattributes -text` để không đổi EOL. Các rule input bổ sung giữ đúng EOL/hashes hiện có; không `renormalize` hoặc sửa inputs/hashes run W5.

Raw runner/config W5 trên checkout có hai khác biệt CRLF/LF đã được chẩn đoán; không cập nhật hash lịch sử để ép audit đạt. `input_confirmation.status=confirmed` của #91 chỉ xác nhận inputs, không phải freeze này. Baseline lịch sử `f627…` không được dùng làm control tương đương. Run W5 vẫn ghi base commit, dirty flag và module hashes đúng thời điểm, không gán commit W6 ngược cho run cũ.

## Kiểm chứng và gate trước benchmark test

[Loader](../../backend/app/search/frozen_retrieval_config.py) nhận expected SHA-256 do caller cung cấp; kiểm raw bytes, schema/version, chính sách source/fusion/image, tracked pins và tương thích manifest/model/corpus; tùy chọn kiểm local manifest/corpus/input bytes. Loader chỉ trả cấu hình và `RRFConfig` hiện có; không nạp weights, mở Qdrant hoặc chạy query. Local byte readiness không chứng minh weights/storage/live index hoặc approval GitHub.

[Hướng dẫn](../guides/issue114-w6-freeze.md) ghi lệnh kiểm và bàn giao. Unit tests dùng synthetic bindings cho local dependencies; không cần `data/processed`/weights/index thật trong CI và không tính quality từ benchmark test.

Trước test, cần commit/hash đã review, checks đạt phù hợp diff, Khuê đối chiếu và tiếp nhận artifact/lệnh/protocol/raw validation. CLI luôn báo `test_authorized=false`: nó không thay thế review/handoff. 21/28 là mẫu số validation; metric test phải tính mẫu số theo test riêng. Runner #91 vẫn chỉ validation, không đổi split hoặc dùng nó để tự chạy test thuộc phần Khuê.

Kết quả test sau khóa báo cáo riêng, không tune lại model/k/passage/filters/ngưỡng. Nếu phát hiện lỗi thật, ghi lỗi, version mới và ảnh hưởng đánh giá; không sửa âm thầm evidence. CI, PR approval, merge và tiếp nhận benchmark tiếp tục là các trạng thái riêng chưa được ADR này tự xác nhận.
