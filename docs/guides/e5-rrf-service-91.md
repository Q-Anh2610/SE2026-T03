# Service E5/CLIP/RRF thử nghiệm — #91

Phần tiếp theo sau [PR #106](https://github.com/Q-Anh2610/SE2026-T03/pull/106)
(index đã merge tại `2c18b1d`). Contract thử nghiệm được Quỳnh Anh
[xác nhận](https://github.com/Q-Anh2610/SE2026-T03/issues/91#issuecomment-6849816002).
CLIP vẫn mặc định; không thay shared schema, HTTP API/runtime hoặc search events.

## Implementation dùng chung

`app.search.experimental_text_search` cung cấp:

- `E5MetadataSearchService`: E5 query → metadata bằng chính `search_by_vector`
  đang dùng cho CLIP/image; exact cosine, cùng `build_qdrant_filter`, không threshold.
  Caller tạo encoder/client một lần và quản lý vòng đời; search không nạp lại model.
- `CLIPTextSource`: gọi nguyên `TextSearchService` W3, thêm provenance và kiểm
  snapshot. Nhận manifest text hoặc manifest preview CLIP cùng model/revision;
  policy query text ghi version riêng với policy image trong manifest gốc.
- `ExperimentalFusionService`: kiểm hai nguồn có cùng source hash/snapshot,
  đúng 200 IDs và metadata; truyền cùng query đã trim và filters đã validate.
  Retrieve đủ cửa sổ 200 mỗi nguồn trước khi gọi `reciprocal_rank_fusion` hiện có.

Không có thuật toán retrieval/fusion thứ hai trong runner. Dùng lại core exact
retrieval và hàm RRF; giới hạn candidate/cutoff của fusion áp dụng sau dedup.
Source window 200 là policy tường minh, có trong orchestration config version.
`RRFConfig` vẫn phải truyền đầy đủ, không tự chọn rank constant bằng default.

Dataset nhỏ cố định: trước mỗi search, service audit index chỉ đọc để từ chối
manifest/input/payload/vector thay tại chỗ. Audit kiểm compatibility, toàn bộ
IDs/metadata và fingerprint của trạng thái đã chấp nhận trước đó. Với Qdrant
local 1.15.1, cosine chuẩn hóa ma trận RAM tại chỗ mỗi khi query không rỗng.
Service dự đoán chính xác hash sau phép chuẩn hóa NumPy trên bản sao, kiểm
hash thật sau query, rồi mới nhận trạng thái mới; query bị skip vì filter rỗng
phải giữ nguyên hash. Không round hash hoặc nới tolerance để che vector drift.
Smoke còn đóng/mở client để đối chiếu fingerprint dữ liệu trên đĩa với lúc đầu.

Phạm vi hiện tại là chạy tuần tự với client/encoder do caller giữ một lần;
index local trên đĩa phải được mở lại sau build. Chưa nối request concurrent
của HTTP runtime. Chi phí toàn bộ audit nằm trong thời gian gọi service; không
loại nó khỏi latency nếu sau này đo protocol. Không tự create/upsert/rebuild
hoặc fallback khi readiness lỗi.

## DTO thử nghiệm và provenance

DTO nằm riêng trong module search, chưa thay `app.schemas` hoặc contract HTTP.

- `SourceRanking`: `score_type="cosine"`, source, hits có asset ID/rank/raw
  cosine theo output service, filters thực tế và `SourceProvenance`.
- Provenance nguồn ghi model/revision/index/config, candidate snapshot/source
  hash, collection/named vector, manifest reference/hash và candidate limit.
  E5 thêm corpus hash/recipe/corpus manifest hash. Cả hai ghi audit policy.
- `FusionSearchResult`: `score_type="rrf"`, RRF hits/contributions, filters,
  fusion parameters/weights/window/cutoff, config version và provenance cả hai
  nguồn. Kèm raw source rankings để exporter evaluation có thể ghi đối chiếu.
- Source names: `clip_text_to_preview`, `e5_text_to_metadata`.
- Fusion giữ score thực, có thể >1 với rank constant 0; không đưa vào DTO cosine.
  Rank nguồn sau dedup từ 1, missing source góp 0, tie theo asset ID tăng dần.
  Hàm RRF dùng Fraction để giữ tie toán học ổn định.

Input sai được validate trước audit/retrieval. Một nguồn unavailable/index
không tương thích làm cả fusion `SearchUnavailableError`; thông báo an toàn.
Luồng chạy thành công nhưng rỗng là hợp lệ, kể cả cả hai nguồn rỗng. Lỗi nội bộ
bất ngờ tiếp tục propagate để adapter tương lai map 500; unavailable map 503.
Không có HTTP adapter hoặc ghi search event trong nhánh này.

## Smoke trên index thật đã có

Đầu vào đã có trên máy Chi:

- CLIP preview candidate 200 từ preflight #89, pinned model/revision, storage
  `data/processed/issue89/clip-preflight-76d5d2c095b6/qdrant` và input root riêng
  `data/processed/issue89/inputs-1d75f15977be`.
- E5 metadata từ build #91 đã passed, gói
  `data/processed/issue91/e5-index-20261113-2`.

Hai nguồn phải cùng source hash/candidate 200. Không dùng index 354 làm phép
so sánh này. CLIP text query dùng cùng không gian CLIP preview đã dựng; không
encode lại preview hoặc tạo manifest text giả để che loại artifact đang dùng.

Từ gốc repo, chọn thư mục output mới và rank constant tường minh:

```bash
backend/.venv/Scripts/python.exe -B scripts/smoke_e5_rrf_service.py --clip-index-root data/processed/issue89/clip-preflight-76d5d2c095b6 --clip-input-root data/processed/issue89/inputs-1d75f15977be --e5-index-root data/processed/issue91/e5-index-20261113-2 --output data/processed/issue91/service-smoke-new-run --rank-constant 60
```

`60` ở lệnh trên là cấu hình diagnostic tường minh, chưa được validation chọn.
Script chỉ nạp cache offline, mở storage đã tồn tại; từ chối đường dẫn index
thiếu và output đã có. Dùng query tiếng Anh/Việt tự tạo; kiểm AND filters,
metadata nullable, kết quả rỗng, IDs đầy đủ, repeat, E5-only khớp nguồn E5 của
fusion và fingerprints persisted trước/sau reopen. Thứ tự nguồn, RRF scores,
contributions và provenance phải khớp chính xác. Raw cosine có thể lệch float
ở lần chuẩn hóa RAM kế tiếp; diagnostic ghi delta và giới hạn riêng `1e-12`,
không sửa raw scores hoặc thuật toán xếp hạng. Không đọc queries/qrels hoặc
chạy benchmark.

Output local gồm `report.json`, `raw-rankings.jsonl` và bản sao hai index
manifests được tham chiếu. Raw output giữ cosine/rank từng nguồn cùng RRF
contributions, filters/versions và candidate counts. Đây là raw **diagnostic**,
không thay raw validation results của tiêu chí 5. Không đưa index/vector dumps
hoặc toàn raw diagnostic vào Git; chọn summary evidence nhỏ để review.

## Tests và phần còn lại

```bash
backend/.venv/Scripts/python.exe -B -m pytest -c backend/pytest.ini backend/tests/unit/test_experimental_text_search.py -q -p no:cacheprovider -o faulthandler_timeout=30
```

Encoder fixtures và Qdrant thật kiểm exact cosine/filter trước top-K, stable
ties/dedup, missing/empty sources, score RRF >1, null metadata, version drift,
index/dependency lỗi, query/filter validation và read-only reuse. Kết quả local,
smoke weights thật, CI và review được ghi riêng sau khi thực sự chạy.

Canonical query artifact/hash vẫn chờ xác nhận theo #91. Chưa chạy/chọn cấu
hình trên benchmark, chưa có báo cáo quality/latency validation hoặc kết luận
model/tiếng Việt. Shared API/runtime/search event cần review riêng trước tích hợp.

## Kết quả local — 13/11/2026

- Test hồi quy dense đã tái hiện lỗi trước sửa: 1 failed ở lần search thứ hai.
  Sau sửa: **43 service tests passed, 71,89 s**; toàn backend unit
  **874 passed, 119,96 s**, gồm các luồng CLIP text/image hiện có.
- Smoke weights thật offline CPU **passed**, gói
  `data/processed/issue91/service-smoke-20261113-2`, rank constant tường minh 60.
  Hai nguồn/fused cùng 200 ứng viên không filter; AND category/license/format
  giữ 57; face-count 0 và category không tồn tại trả rỗng hợp lệ.
- Repeat giữ chính xác source IDs/ranks, RRF scores/contributions và provenance.
  Raw cosine lệch tối đa CLIP `1.1102230246251565e-16`, E5
  `2.220446049250313e-16`; E5-only giữ cùng thứ tự/provenance với nguồn E5
  của orchestration, raw delta `2.220446049250313e-16`, dưới giới hạn diagnostic.
- Mọi chuyển trạng thái RAM được kiểm đúng hash dự đoán. Fingerprint persisted
  CLIP `5db69a3156a6b1a428d1f0c1f7d2d891c9ec99266d55ebc7d93a7926fb2093e9`
  và E5 `91a0cb9729333d90b38677fa740832a424be57e9d029f896a2c42eb0fdc1be1f`
  giữ nguyên sau đóng/mở client; không rebuild hoặc ghi đè index.
- [Bằng chứng portable](../evidence/issue91-e5-rrf-service-smoke-20261113.json)
  ghi command, pins/versions, hashes, threads và kết quả tests. Base lúc chạy
  `2c18b1da0d0353f2d4bb75e06eb6beb4407d8bb8`, dirty=true; không gán ngược
  commit tương lai cho lượt chạy này. Raw diagnostic local có hash truy vết.
- Các kiểm chứng chạy từ working tree chưa commit trên `feat/91-e5-rrf-service`.
  CI/review/merge của phần service theo dõi riêng. Tổng thời gian diagnostic
  không phải p50/p95 retrieval latency; benchmark validation còn chờ input hash.
