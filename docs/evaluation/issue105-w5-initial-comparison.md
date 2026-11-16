# Báo cáo so sánh ban đầu W5 — Issue #105

Refs [#105](https://github.com/Q-Anh2610/SE2026-T03/issues/105).
Trạng thái: đã kiểm chứng input/archive và staged diff; chờ commit/PR và review #105.

## Phạm vi và nguồn kết quả

Báo cáo tổng hợp các lần chạy validation thật của #91 để bàn giao kết quả ban đầu
W5. Không có lần chạy retrieval mới được thực hiện để tạo tài liệu này; #105 có
bước tính lại metric/latency từ archive, được ghi riêng ở phần kiểm chứng. Số liệu
bên dưới lấy từ [JSON evidence #91](../evidence/issue91-e5-rrf-validation-20261114.json),
không phải từ tests dùng fixtures. Chi tiết lần chạy nằm trong
[báo cáo gốc](issue91-e5-rrf-validation-20261114.md).

- [PR #109](https://github.com/Q-Anh2610/SE2026-T03/pull/109) đã đính chính
  canonical query artifact; merge tại 63122a3a05a920a847793253a4527a871d5aa6e8.
- [PR #110](https://github.com/Q-Anh2610/SE2026-T03/pull/110) đã được Khuê approve
  trên b11652dbba2f4a3fc6ca6e69bb44b8ef5ce74620, 5 checks passed, merge tại
  f36e9eff9d4f9a3dc77f5116d877db4d0aa65fdc.
- Bình luận xác nhận tiếp nhận cuối trên
  [#91](https://github.com/Q-Anh2610/SE2026-T03/issues/91) ghi Khuê đã kiểm ZIP,
  46 entry hashes, coverage, tính lại Recall@10/binary nDCG@10 và p50/p95 của
  chín tổ hợp run/cấu hình. Phần đối chiếu này không chạy lại weights, toàn bộ
  Fraction RRF, repeat DTO hoặc persisted index.
- [#90](https://github.com/Q-Anh2610/SE2026-T03/issues/90) đã khóa image test set;
  [PR #96](https://github.com/Q-Anh2610/SE2026-T03/pull/96) đã merge qrels/split ảnh.
- [#101](https://github.com/Q-Anh2610/SE2026-T03/issues/101) đã tiếp nhận audit
  metadata/payload qua PR #102; audit dùng DB test dựng từ frozen manifest,
  chưa chứng minh DB nghiệp vụ hiện hành đã được đồng bộ.

Các câu còn ghi chưa review/merge/tiếp nhận trong báo cáo #91 là trạng thái tại
thời điểm viết báo cáo gốc; trạng thái bàn giao mới hơn được ghi ở các Issue/PR
trên. Không sửa provenance hoặc raw results lịch sử để cập nhật tiến độ.

## Inputs, split và protocol text

| Thuộc tính | Giá trị dùng cho mọi cấu hình text |
|---|---|
| Benchmark | home-interior-text-v2 |
| Candidate snapshot | home-interior-clear-200-v3; đúng 200 asset IDs |
| Split dùng đo chất lượng | 28 validation query tiếng Anh |
| Split giữ ngoài tuning | 42 test query; không chạy retrieval/test metric trong grid W5 |
| Filters | {} |
| Source window / cutoff | 200 / 200 |
| Positive relevance | qrels >= 1; binary gain cho nDCG |
| Recall macro | 21 query có positive; loại 7 query không positive khỏi mẫu số |
| Hit/nDCG macro | đủ 28 query; query không positive nhận 0 |
| RRF | k=10/20/60; weights=1 mỗi nguồn; rank bắt đầu từ 1; thiếu nguồn góp 0 |
| Dedup/tie-break | mỗi asset tối đa một lần/nguồn; score giảm dần, hòa thì asset ID tăng dần |
| Latency | 5 warm-up/cấu hình, 10 lượt/query; 280 samples/cấu hình/run |

Config/protocol chi tiết ở
[confirmed config](../../evaluation/configs/issue91-e5-rrf-validation.confirmed.json).
Input confirmed chỉ xác nhận dữ liệu; không phải cấu hình model/k đã khóa.

| Artifact | SHA-256 raw bytes |
|---|---|
| [Text queries](../../data/benchmark/queries.csv) | e202a0dc62406826ec29a2946d489c359a222133e6c530a9954832760d965470 |
| [Text qrels](../../data/benchmark/qrels.csv) | cc1d42f6e3f41f92fab1b842c7a70ca68be4341cdd30e4262e13989f99019df5 |
| [Candidate metadata](../../data/manifests/objaverse_200.json) | 9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd |
| [Confirmed config](../../evaluation/configs/issue91-e5-rrf-validation.confirmed.json) lúc chạy | e420e67e7db041e6ae4624b77793c009149475f8d0805e008075dfc763081d42 |
| [Erratum record](../../data/benchmark/query-artifact-erratum-91.json) | cf6bbdf14eff1b9b2de201ddddcac0f461d1a7e138561e6b02f5103912cb5048 |
| Corpus E5, ngoài Git | 66efd87e34447c23b4171e13ac77d78a9c193519141d0dd6a31985c01e65b4f5 |

Query canonical là nguyên blob tại ff7b64abbbb21677fc2fc6f6ac7daf6f2025742a:
7.851 byte, UTF-8 có BOM, LF, không CR, giữ 4 LF cuối. Không xuất lại CSV hoặc
chuẩn hóa bytes để vượt gate. Baseline keyword/CLIP lịch sử có hash f627… chưa
tái lập không được ghép vào bảng như đối chứng tương đương W5; xem
[erratum](query-artifact-erratum-91.md).

## Chất lượng text trên validation

| Cấu hình | Recall@5 | Recall@10 | Hit@5 | Hit@10 | binary nDCG@10 |
|---|---:|---:|---:|---:|---:|
| CLIP-only | 0.32947 | 0.49300 | 0.67857 | 0.75000 | 0.46982 |
| E5-only | 0.16651 | 0.35016 | 0.57143 | 0.67857 | 0.36223 |
| RRF k=10 | 0.35006 | 0.56414 | 0.71429 | 0.75000 | 0.52589 |
| RRF k=20 | 0.35848 | 0.55620 | 0.71429 | 0.75000 | 0.53126 |
| RRF k=60 | 0.31933 | 0.53809 | 0.67857 | 0.75000 | 0.52149 |

CLIP/E5 standalone khớp giữa cả ba run. RRF k=20 có nDCG@10/Recall@5 cao nhất
trong grid; k=10 có Recall@10 cao nhất. So với CLIP mới cùng inputs, k=20 tăng
nDCG@10 khoảng 0,06143 và Recall@10 khoảng 0,06320. Đây là chênh lệch metric,
không phải độ chính xác của sản phẩm. k=60 giảm Recall@5 so với CLIP.
E5-only thấp hơn CLIP ở các quality metrics trong bảng.

Mẫu chỉ có 28 English queries và 200 curated candidates; chưa có kiểm định
ý nghĩa thống kê hoặc đánh giá khả năng tổng quát hóa. Không chọn metric thuận
lợi sau khi xem grid rồi mô tả như tiêu chí định trước. Chưa chọn winner/model/k.

## Latency text và chi phí

| Gói k | Cấu hình | Samples | p50 (ms) | p95 (ms) |
|---|---|---:|---:|---:|
| 10 | clip_only | 280 | 430.52 | 548.87 |
| 10 | e5_only | 280 | 375.71 | 449.99 |
| 10 | clip_e5_rrf | 280 | 821.35 | 897.60 |
| 20 | clip_only | 280 | 425.22 | 597.57 |
| 20 | e5_only | 280 | 388.80 | 488.27 |
| 20 | clip_e5_rrf | 280 | 911.91 | 1217.07 |
| 60 | clip_only | 280 | 489.89 | 684.14 |
| 60 | e5_only | 280 | 395.03 | 497.39 |
| 60 | clip_e5_rrf | 280 | 886.58 | 1139.00 |

Percentile dùng nearest-rank: phần tử thứ 140/266 trên 280 mẫu đã sort.
Timing gồm query encoding, retrieval, exact audits và fusion trong service;
loại model load, mở/build index, export/metrics và audit/reopen cuối. Không phải
HTTP/API latency; không trộn với số HTTP image của #88.

Trong gói k=20, RRF p50/p95 khoảng 2,14x/2,04x CLIP. RRF cần duy trì hai
encoder/index; RAM và chi phí vận hành tổng thể chưa được đo trong phép so sánh
này. Mỗi k chỉ có một run tuần tự, baseline CLIP cũng biến thiên giữa run;
không quy mọi chênh lệch latency cho k hoặc gộp samples để chọn số đẹp.

## Môi trường và phiên bản tại lần chạy gốc

- CPU, AMD64, Intel64 Family 6 Model 140 Stepping 2, GenuineIntel;
  Windows-11-10.0.26200-SP0; Python 3.13.7.
- Torch 2.8.0, transformers 4.57.1, qdrant-client 1.15.1, numpy 2.5.4,
  pydantic 2.14.1; torch intra-op/inter-op đều 4 threads.
- CLIP openai/clip-vit-base-patch32, revision
  3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268;
  index version issue89-clip-preflight-76d5d2c095b6;
  config version clip-text-exact-all-filtered-v1-k200.
- E5 intfloat/multilingual-e5-small, revision
  614241f622f53c4eeff9890bdc4f31cfecc418b3;
  index version issue91-e5-metadata-1588f4dc33fbe62609d8;
  config version e5-metadata-exact-all-filtered-maskmean512-l2-v1-k200;
  recipe e5-metadata-passage-v1-draft theo artifact đã được index pin.
- Lần đo ghi base 63122a3a05a920a847793253a4527a871d5aa6e8 và dirty=true.
  JSON evidence lưu raw hashes của 13 module tại lúc chạy; không gán ngược
  commit PR #110 hoặc commit #105 cho code thực tế của run cũ.
- Model/index/config manifests, persisted fingerprints, commands và hashes từng
  file/run nằm trong JSON evidence và raw bundle; giữ nguyên bytes khi đối chiếu.

## Phần ảnh: inputs đã khóa, chưa có so sánh chất lượng

[Image manifest](../../data/benchmark/image_benchmark_v1.yaml) ghi benchmark
home-interior-image-v1 trên cùng candidate 200: 20 similarity queries,
0 same_id, 4.000 qrels; split theo group là 8 validation / 12 test,
seed 8901. Image queries SHA-256
24a706ea4bdb5b2e4b61fc127fa73d50c0464e37bf2685ed625e1536b489fc09;
image qrels SHA-256
964b6d46e65c360c6a174bbe5af919069755b46554951b959a5bab9c45b9c109.

Preflight CLIP/SigLIP 2 trong [guide #89](../guides/image-index-preflight-89.md)
xác nhận index candidate 200 ở máy owner, chưa phải benchmark quality trên
8 validation queries. Báo cáo #105 hiện chưa có raw rankings và metric quality
ảnh tương đương để đưa vào bảng so sánh.

Phần còn thiếu để chạy so sánh ảnh: nhận đủ inputs/index/weights đúng pins tại
máy chạy, xác nhận protocol quality/latency với owner và chuẩn bị entrypoint
validation dùng cùng search implementation. CLI text tổng quát và script HTTP
image latency #88 không tự thay thế benchmark này. Không chạy 12 test queries để
tune; không dùng self-preview smoke, tốc độ HTTP hoặc kết quả text suy ra model
ảnh tốt hơn. Hit@K theo mục tiêu same-ID không áp dụng vì không có same_id query.
Nếu thực hiện so sánh ảnh sau đó, bổ sung version/protocol/raw và bằng chứng mới;
trước mắt giữ phần này là blocker đã ghi nhận, chờ reviewer xác nhận phạm vi.

## Raw artifacts và tái lập

Bundle Chi bàn giao ở [#91](https://github.com/Q-Anh2610/SE2026-T03/issues/91):
issue91-validation-20261114-review.zip, 2.543.329 byte, SHA-256
097a1b53ccc0751170d813f0e97407516dd63052bd8ca2c1481477fe46decb6a.
ZIP chứa ba gói run, raw rankings/latency samples, manifests/configs/erratum,
input/runtime snapshots và bảng SHA-256 từng entry. Không chứa model weights
hoặc Qdrant storage. ZIP/raw lớn giữ ngoài Git.

Lệnh chạy gốc từng k có trong JSON evidence; cách chạy mới với index/cache đúng
pins nằm ở [guide #91](../guides/e5-rrf-validation-results-91.md).
Auditor [audit_e5_rrf_validation_grid.py](../../scripts/audit_e5_rrf_validation_grid.py)
đọc raw packages, tính lại metric/percentiles và RRF; không nạp weights hoặc chạy
retrieval. Auditor kiểm module bytes của checkout so với run gốc, nên có thể báo
code/EOL drift dù đã nhận đủ ZIP. Khi đó đối chiếu archived runtime/input snapshots;
không sửa hashes, source hiện tại hoặc report lịch sử để ép passed.

Các bước kiểm chứng nhánh #105, điều kiện trước audit và lệnh xem ở
[hướng dẫn thực hiện](../guides/issue105-w5-evaluation-report.md).

## Kiểm chứng input trên nhánh #105

Nguồn: output terminal người dùng cung cấp trong phiên thực hiện #105; agent
không tự chạy lại hai lệnh dưới đây.

~~~powershell
rtk proxy ./backend/.venv/Scripts/python.exe -B scripts/verify_issue91_query_artifact.py --repo . --compare-source-commit
rtk proxy ./backend/.venv/Scripts/python.exe -B scripts/run_e5_rrf_validation.py --config evaluation/configs/issue91-e5-rrf-validation.confirmed.json --preflight-only
~~~

| Kiểm tra | Kết quả đã nhận |
|---|---|
| Artifact checker | status=passed; benchmark_run=false |
| Query bytes | SHA-256 e202a0dc…; 7.851 byte, BOM=true, LF, 4 LF cuối |
| Nguồn và dữ liệu lịch sử | source_commit_bytes_compared=true; head_query_blob_unchanged=true; historical_worktree_content_unchanged=true |
| Split | 70 query; 28 validation/42 test; groups_overlap=false |
| Confirmed preflight | status=inputs_verified; validation_queries=28; models_loaded=false |

Preflight khớp pins query/qrels/candidate/manifest/erratum trong evidence #91.
Config checkout hiện có raw SHA-256
921289a958d0f6b9d1ad2d9ba03ad0fd66018088e9f25de0f1209d4726f8e4e6,
khác config raw lúc đo gốc e420e67e… ở bảng trên. Đọc trực tiếp file hiện tại
cho thấy 2.249 byte và 62 CRLF; bản biến đổi LF chỉ dùng chẩn đoán cho hash
e420e67e7db041e6ae4624b77793c009149475f8d0805e008075dfc763081d42.
Đây là bằng chứng khác biệt EOL, không thay raw bytes hoặc pins để vượt audit.
Đã đối chiếu bản run-config nguyên bytes trong archive; chưa tuyên bố
checkout hiện tại tái lập byte-for-byte toàn bộ môi trường chạy gốc.

Trường runner_confirmation=pending trong artifact checker mô tả default runner;
lệnh thứ hai đã truyền config confirmed và đạt inputs_verified. Hai kết quả
không mâu thuẫn. Chưa chạy retrieval hoặc benchmark test mới cho #105.

## Trạng thái Git và nhận raw cho #105

Theo output terminal người dùng cung cấp:

- Nhánh test/105-w5-evaluation-report đang theo dõi origin cùng tên.
- HEAD 11e4435: Merge pull request #123 từ nhánh #104. Các commit #104 xuất hiện
  trong lịch sử qua merge này; không xem riêng sự xuất hiện của chúng là thay đổi
  ngoài phạm vi #105. Chưa fetch/đối chiếu tip develop mới nhất trong bước này.
- Người dùng đã stage đúng 5 file #105: mục lục docs, report, guide, evidence và
  helper shared. git diff --cached --check không báo lỗi; staged stat tại lần
  kiểm ghi 5 files changed, 739 insertions. Bản cập nhật trạng thái kiểm chứng này
  cần được stage lại trước commit; không thay code helper hoặc số liệu audit.
  Các relative links đã được agent kiểm tồn tại.
- Người dùng kiểm ZIP tại D:/Download/issue91-validation-20261114-review.zip:
  Get-Item trả 2.543.329 byte; Get-FileHash SHA256 trả đúng
  097a1b53ccc0751170d813f0e97407516dd63052bd8ca2c1481477fe46decb6a;
  tar -tf liệt kê đúng cấu trúc runs/inputs/measured-source/docs/auditor.
- Agent đọc ZIP trực tiếp bằng Node (không chạy terminal): 48 entries, không có
  duplicate/đường dẫn tuyệt đối/parent traversal; kiểm 46/46 payload SHA-256 khớp
  bundle-files-sha256.json; hai entry còn lại là README và bảng hash.
- Đối chiếu config archive với checkout: khác raw CRLF/LF, còn lại khớp bytes
  sau chuyển CRLF sang LF chỉ để chẩn đoán; không sửa file nguồn hoặc pins.
- Archive đã được giải nén trong data/processed/issue105/raw-review-1. Lệnh
  checksum inline đầu tiên thất bại do quoting. Người dùng sau đó chạy
  helper local check-review-bundle.ps1 bằng -File, nhận PASSED: 46/46 file hashes match.
  Đã xác nhận tính toàn vẹn file sau giải nén. Bước tính lại metric/latency bằng
  helper local cũng đã passed, xem mục kiểm chứng archive dưới đây.


## Kiểm chứng archive cho #105 — 16/11/2026

Người dùng đã chạy bản shared sẽ đưa vào PR bằng Node v24.18.1:

~~~powershell
rtk proxy node ./scripts/audit_issue105_review_bundle.mjs
~~~

Kết quả: PASSED: 9/9 combinations; 252 raw records; 2520 samples; metrics and
latency match. [JSON evidence #105](../evidence/issue105-archive-metrics-review-20261116.json)
lưu nguyên output lúc 2026-11-16T03:26:09.786Z, hash helper shared
12679addedb74cdf1e4f05cfd6747ec2f969c4137fb8a1d103beadc65868b212
và hash bảng checksum archive
f6c75aab3f90be33b0ab2d2c330e487d410ebf8f648841843d763bb73b665a75.
Agent đã đọc output và đối chiếu hash helper hiện tại với evidence: khớp.
Kết quả ban đầu từ helper local được giữ ở data/processed/issue105/metrics-review-1.json;
evidence chia sẻ dùng lần chạy bản shared metrics-review-2.json, không gán ngược
hash hay timestamp của lần local cho mã đã chuyển vị trí.

Đã kiểm lại 46 hashes, validation query membership, text/group/split, 200 candidate
IDs duy nhất/ranking, positive IDs khớp archived qrels và coverage 10 lượt/query.
Đã tính lại Recall@5/10, Hit@5/10, binary nDCG@10, p50/p95 từ raw và so cả run
records lẫn JSON evidence #91. Recall có mẫu số 21, Hit/nDCG là 28; p50/p95 lấy
vị trí 140/266 trong 280 mẫu mỗi tổ hợp.

So số metric dùng tolerance tuyệt đối 1e-12 cho sai số số thực; raw hashes vẫn
kiểm exact. Không chạy lại weights/retrieval, Fraction RRF, repeat DTO không xuất
hoặc live persisted index. Chỉ đọc split metadata để kiểm cấu trúc, không chạy
ranking hoặc tính quality trên test. Đây là audit kết quả đã có, không phải một
lần đo latency mới trên máy chạy Node.

Reviewer dùng [helper shared](../../scripts/audit_issue105_review_bundle.mjs)
với archive đúng hash theo guide #105; không cần models/index hoặc thay EOL/source
checkout. Helper chỉ đọc archive và ghi JSON mới, từ chối ghi đè output đã tồn tại.

## Checklist nghiệm thu #105

Các mục dưới đây theo dõi lần bàn giao #105; kết quả #91 đã review không tự tích
review/CI của PR #105.

- [x] Xác nhận inputs canonical trên nhánh #105 bằng artifact checker và confirmed preflight; output người dùng cung cấp ghi ở trên.
- [x] Đối chiếu raw bundle phục vụ #105 bằng checksum và audit metric local; lệnh/output/giới hạn và JSON evidence ghi ở trên.
- [x] Bảng text ghi snapshot/split/candidate/filter/metric/mẫu số và số liệu từ JSON evidence #91.
- [x] Ghi code/data/model/index/config provenance, môi trường, raw location và cách tái lập.
- [x] Tách giới hạn ảnh, baseline cũ, tiếng Việt, significance và production latency; không dùng test để tune.
- [x] Kiểm tra liên kết nội bộ và staged diff: người dùng chạy git diff --cached --check không báo lỗi, stat đúng 5 file #105.
- [ ] PR #105 vào develop, cập nhật liên kết/checklist Issue; chưa có URL PR của lần bàn giao này.
- [ ] Required checks của PR #105 đạt; có reviewer khác approve và xử lý trao đổi chặn.

Chưa nghiệm thu toàn W5; lựa chọn cuối, ADR/config freeze và benchmark test sau
khóa thuộc [#114](https://github.com/Q-Anh2610/SE2026-T03/issues/114) và bước bàn giao
W6 riêng. Thay đổi #105 gồm báo cáo, evidence nhỏ và helper audit archive; không đổi
API/schema/index/dependencies hoặc thuật toán retrieval sản phẩm.
