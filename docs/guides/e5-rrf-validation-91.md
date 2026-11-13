# E5/RRF validation — phần độc lập của #91

Trạng thái: encoder và fusion nội bộ đã có trong [PR #100](https://github.com/Q-Anh2610/SE2026-T03/pull/100)
đang Draft, chưa merge.
Đã có smoke encoder E5 bằng weights thật ngày 13/11/2026; chưa có E5
corpus/index hoặc raw validation results. Chưa nghiệm thu toàn bộ #91. Giữ
CLIP mặc định; không đổi shared schema/API/runtime.

## Encoder

- `app.embedding.e5_encoder.E5Encoder`, tái sử dụng instance trong process.
- `intfloat/multilingual-e5-small`, model/tokenizer cùng revision
  `614241f622f53c4eeff9890bdc4f31cfecc418b3`, dimension 384.
- Fast tokenizer, padding/truncation bên phải, `max_length=512` bao gồm prefix
  và special tokens; không tự dịch hoặc bỏ dấu. Query trim 1–500 Unicode code
  points, nội dung passage trim và phải không rỗng.
- `encode_text(query)` thêm `query: `; `encode_passages(texts)` thêm `passage: `.
  Caller truyền nội dung chưa có prefix. Chưa chọn trường/thứ tự ghép metadata;
  không encode asset ID hoặc caption bịa thay passage rỗng.
- Average pooling có attention mask, float32 rồi L2; từ chối shape sai,
  vector zero/non-finite. Không nhân score với 100.
- Preprocessing: `e5-fast-right-truncate512-mask-mean-fp32-l2-v1`.
- Mặc định `local_files_only=True`, chỉ đọc safetensors/cache có sẵn. Không có
  cache đúng revision thì loader báo lỗi; không trả embedding giả.
- Tái sử dụng torch/transformers/tokenizers/safetensors hiện có; không đổi
  requirements. Dependencies thực dùng phải ghi lại khi chạy weights thật.

Nguồn: [model card chính thức](https://huggingface.co/intfloat/multilingual-e5-small),
[revision](https://huggingface.co/intfloat/multilingual-e5-small/commit/614241f622f53c4eeff9890bdc4f31cfecc418b3),
[tokenizer config đã pin](https://huggingface.co/intfloat/multilingual-e5-small/blob/614241f622f53c4eeff9890bdc4f31cfecc418b3/tokenizer_config.json).

## RRF nội bộ

`app.search.rrf.reciprocal_rank_fusion` nhận hai sequence asset ID theo thứ tự
retrieval và `RRFConfig` tường minh. Output là kiểu nội bộ, chưa phải interface
đã được Quỳnh Anh chấp thuận. Chưa có service orchestration hoặc adapter HTTP.

Mỗi asset nhận `sum(1 / (rank_constant + rank))` từ những luồng có asset đó;
rank bắt đầu 1, weights bằng nhau. Không nhận/cộng cosine hoặc embedding.
Mỗi luồng dedup theo lần xuất hiện đầu, đánh rank liên tiếp theo danh sách
unique, rồi cắt candidate limit. Cuối cùng gom hai luồng, sort RRF score giảm
dần và asset ID tăng dần, rồi cắt cutoff. Tổng rank tính bằng phân số để giữ
tie toán học; float trong output không được clip về cosine.

`RRFConfig` yêu cầu `rank_constant >= 0`, candidate limits và cutoff 1–200
theo snapshot thí nghiệm. Không có cấu hình mặc định hoặc cấu hình được chọn
từ validation. Tham số và policy vào hash tạo `config_version`; mỗi hit có
nguồn/rank/contribution thực. Ví dụ `rank_constant=60` trong unit tests chỉ là
fixture biết đáp án, không phải kết quả tối ưu.

Hàm này không tự retrieval, kiểm tra snapshot hoặc áp dụng filters. Service
tương lai phải xác nhận cùng candidate snapshot và filters trước retrieval,
truyền các cửa sổ ứng viên đã sắp xếp, ghi model/index/corpus versions của
từng luồng và gọi chính hàm này. Evaluation chỉ gọi service đó; không viết
phép retrieval/fusion thứ hai trong runner.

## Kiểm tra không tải model

Từ gốc repo trong Git Bash, dùng Python backend:

```bash
backend/.venv/Scripts/python.exe -m pytest -c backend/pytest.ini backend/tests/unit/test_e5_encoder.py backend/tests/unit/test_rrf.py
```

Các tests dùng loader/model giả, có attention mask/padding, prefix, batch,
reuse, finite/L2, lỗi dependency/config, ví dụ RRF biết đáp án, missing stream,
duplicate, tie và phiên bản tham số. Không chứng minh weights thật chạy được,
filters của E5 retrieval, compatibility E5 index hoặc chất lượng relevance.

Kiểm chứng local ngày 12/11/2026, Windows / Python 3.13.7: 107 tests mới đạt
bằng fixture; hồi quy toàn bộ `backend/tests/unit` đạt **788 passed, 32,00 s**.
Lượt cuối chạy ngoài sandbox để cho phép Git đọc worktree và tạo socket nội
bộ cho TestClient; không sửa/bỏ tests để đạt kết quả. Không có lượt CI,
integration PostgreSQL hoặc weights smoke thật trong bằng chứng này.

Smoke bằng weights thật **chỉ sau khi có cache đúng revision**:

```bash
backend/.venv/Scripts/python.exe scripts/smoke_e5_encoder.py --output data/processed/issue91/e5-encoder-smoke.json
```

Script luôn `local_files_only=True`, không tải weights, không mở Qdrant/DB và
không đọc queries/qrels. Output mới ghi machine/packages, command, thời gian
load/warmup/operations, prefix/token policy, normalization và repeat tolerance
1e-12. Đây là diagnostic encoder bằng ví dụ tự tạo; không đo quality tiếng Việt
hoặc latency protocol của benchmark. File đã có thì chọn tên mới.

## Smoke weights thật — 13/11/2026

Đã chạy CPU bằng cache local đúng model/tokenizer revision đã pin. Sáu file
cache được xác minh checksum; hai metadata file được phục hồi từ blobs bằng
copy thường sau lỗi symlink Windows. Không thay thư viện hoặc quyền hệ thống.

```bash
backend/.venv/Scripts/python.exe -B scripts/smoke_e5_encoder.py --device cpu --output data/processed/issue91/e5-encoder-smoke-20261113.json
```

[Bằng chứng portable](../evidence/issue91-e5-encoder-smoke-20261113.json)
ghi môi trường, packages, command, model/tokenizer pin và hashes source/report.
Raw report gốc giữ ở `data/processed/issue91/` (Git ignore).

- Status `passed`; CPU, dimension 384, token limit 512, prefix query/passage,
  attention-mask mean float32 và L2. Model được dùng lại cho các lời gọi smoke.
- Repeat max absolute difference `0.0`, trong tolerance `1e-12`.
- Model load `1.1721155000268482` s. Nhóm timed operations (4 query calls và
  2 passages) tổng `0.07284080004319549` s, sau warm-up.
- Windows 11, Python 3.13.7, 8 logical CPU; torch 2.8.0, transformers 4.57.1,
  tokenizers 0.22.2, safetensors 0.8.0. Chi tiết CPU có trong JSON.

Đây là encoder diagnostic bằng ví dụ tự tạo, không đọc queries/qrels hoặc
mở index. Thời gian trên không phải p50/p95 benchmark; chưa có kết quả
relevance, E5 index compatibility hoặc chất lượng tiếng Việt.

## Các xác nhận còn cần

1. Huyền: nguồn metadata gốc trên đúng 200 asset; các trường/thứ tự ghép,
   tags order/dedup, whitespace/newline/Unicode, null/empty và asset không có
   nội dung. Chốt recipe version, asset IDs, source/corpus hash trước index.
2. Quỳnh Anh: candidate/fusion interface, `score_type` RRF, provenance mỗi
   nguồn, versions, lỗi dependency và phạm vi integration; không nhét score
   RRF vào contract cosine W3. Chưa sửa shared DTO/API.
3. Khuê đã [đề xuất protocol](https://github.com/Q-Anh2610/SE2026-T03/issues/91#issuecomment-6829347357)
   ngày 12/11/2026; chi tiết ở dưới. Hash query canonical vẫn chưa được xác
   nhận, nên chưa chạy/chọn cấu hình bằng input hiện tại.
4. Đối chiếu query hash: local `queries.csv` có BOM, 70 query, split 28/42;
   SHA-256 bytes là
   `80e7de4db77929bc79c87ddb1da1bdb1f101832d39a2fd3c6549ec8db7ae30b9`,
   khác manifest khóa `f62762c4a0b392ddc310d1d64e0bdb685b2010347e3790395bbb523428c38788`.
   Blob tại commit khóa `ff7b64a` và HEAD đều có SHA-256
   `e202a0dc62406826ec29a2946d489c359a222133e6c530a9954832760d965470`.
   Đổi CRLF của local thành LF tái tạo blob Git; parse CSV sau chuẩn hóa cho
   commit khóa = HEAD = local. Mâu thuẫn với `f627…` còn cần truy artifact/quy
   ước bytes, không quy cho thay đổi nội dung query trong W5. Chưa tự sửa
   file/manifest hoặc chạy benchmark. Qrels bytes vẫn khớp
   `cc1d42f6e3f41f92fab1b842c7a70ca68be4341cdd30e4262e13989f99019df5`,
   source 200 vẫn khớp `9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`.

## Protocol Khuê đề xuất — chưa chạy

- Chỉ 28 validation query tiếng Anh, candidate universe đúng 200 asset,
  filters `{}`; CLIP-only, E5-only, CLIP+E5 RRF cùng inputs.
- Recall@5/10, Hit@5/10, binary nDCG@10, positive qrels >=1. Recall macro có
  mẫu số 21, loại 7 no-positive query; Hit/nDCG giữ đủ 28 với no-positive =0.
  Dùng `compute_metrics` trong `evaluation/run_keyword_baseline.py`; metric
  runner tổng quát hiện tại từ chối query không có relevant IDs.
- Lấy đủ 200 ứng viên mỗi luồng và xuất raw top 200 source/fused. Nếu không
  đủ phải báo/chốt lại protocol; không âm thầm so cửa sổ ứng viên khác nhau.
- Grid k thuộc `{10,20,60}` là đề xuất validation, chưa phải lựa chọn đã đo;
  rank từ 1, tie-break asset ID tăng dần, version hóa k/candidate count.
- Raw có query ID, asset ID, rank, raw score, source, RRF contribution, cả
  source/fused rankings; kèm input hashes, model/index/config versions,
  filters, candidate counts và lỗi/skipped query.
- Latency tuần tự trên cùng máy/runtime: 5 warm-up request mỗi cấu hình,
  sau đó 10 lần đo cho mỗi query (280 lượt/cấu hình). Đo query encoding +
  retrieval + fusion; loại model load/index build/report writing. p50/p95
  nearest-rank; ghi thiết bị, packages và thread settings thực tế. Chưa đo
  được đúng phạm vi thì ghi chưa có latency; không dùng số image #88 thay thế.
- Canonical query hash chưa giải quyết thì chưa chạy hoặc chọn cấu hình.
  Khi xác nhận phải ghi artifact/commit và BOM/newline vào run record; nếu
  hash khóa sai cần cập nhật benchmark có review.

## Truy provenance W3

Đã tìm lại gói `issue71-clip-20261104T090005Z-06a5d33c.zip` trên máy và chỉ
đọc inventory/provenance/source exporter để kiểm tra input integrity. ZIP
SHA-256 `cbcf9e7df90a144f096ac0386e2b6fffcb1d31d37d93e76a4c5c6b56400a7d77`.
`provenance.json` ghi `queries_sha256=f627…`; exporter kiểm raw bytes của path
`--queries` do caller truyền. Tuy nhiên ZIP không chứa `queries.csv`, nên gói
này chưa đủ tái tạo bytes canonical. Không chạy exporter/benchmark hoặc đọc
ranked results W3 trong lượt truy provenance này; còn cần bản input gốc hoặc
quy ước bytes được owner xác nhận.

Không đọc/chạy lại 42 test query để chọn cấu hình. Không thay text qrels bằng
image qrels; không trộn index 354 với phép so sánh candidate 200. Không suy
trạng thái W4 hiện tại từ ghi chú lịch sử trong issue/docs.
