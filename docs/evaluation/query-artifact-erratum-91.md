# Đính chính raw query artifact W5 — #91

Theo [phản hồi của Khuê](https://github.com/Q-Anh2610/SE2026-T03/issues/91#issuecomment-6859981671),
PR này đề nghị khóa W5 bằng nguyên blob query tại commit gốc. Chỉ sau review
và merge erratum mới tạo config confirmed và chạy validation. Config hiện
tiếp tục `pending`; tiêu chí 5/6 của #91 chưa hoàn thành.

## Artifact đề nghị khóa

| Thuộc tính | Giá trị |
|---|---|
| Nguồn | `data/benchmark/queries.csv` tại `ff7b64abbbb21677fc2fc6f6ac7daf6f2025742a` |
| SHA-256 raw bytes | `e202a0dc62406826ec29a2946d489c359a222133e6c530a9954832760d965470` |
| Kích thước | 7.851 byte |
| Encoding | UTF-8 có BOM `EF BB BF` |
| Newline | LF; không có CR |
| Cuối file | 4 byte LF liên tiếp: LF kết thúc dòng dữ liệu cuối và 3 dòng trống |
| Cấu trúc | 70 query; 28 validation / 42 test; 10 groups, không giao split |

Hash cũ ghi trong lock:
`f62762c4a0b392ddc310d1d64e0bdb685b2010347e3790395bbb523428c38788`.
Hiện chưa có artifact tái tạo được hash này. Đính chính active lock cho W5
không xác nhận ngược raw input của baseline cũ.

Checkout Windows ban đầu có 7.925 byte/CRLF và hash
`80e7de4db77929bc79c87ddb1da1bdb1f101832d39a2fd3c6549ec8db7ae30b9`.
Đây là bytes checkout khác artifact. Local được đưa về nguyên bytes nguồn
bằng binary copy từ `git show` sau kiểm tra tree sạch và đối chiếu trước sửa;
không parse rồi xuất lại CSV, bỏ BOM, trim dòng trống hoặc đổi wording.

## Thay đổi active metadata và checkout

- `manifest.yaml`: đính chính cả `locked_revision`,
  `locked_files_sha256.queries.csv`, `file_sha256.queries.csv`; ghi thời điểm
  cập nhật và liên kết erratum. Benchmark version/split/seed giữ nguyên.
  Projection hash còn kiểm toàn bộ giá trị manifest ngoài các trường đính
  chính, gồm group IDs, split/seed và metadata/provenance diagnostic lịch sử.
- Config runner pending dùng cùng SHA-256 đề nghị mới; status/evidence/byte
  policy vẫn `pending/null/null`. Không tạo confirmed trong PR này.
- [Record máy đọc được](../../data/benchmark/query-artifact-erratum-91.json)
  ghi hash cũ/mới, source commit, bytes, cấu trúc, EOL và hashes cần bảo toàn.
- `.gitattributes` pin raw artifacts theo quy ước đã được khóa:

| File CSV trong `data/benchmark/` | Checkout EOL | Căn cứ |
|---|---|---|
| `queries.csv` | LF | Blob canonical đề nghị ở trên |
| `qrels.csv` | CRLF | Giữ nguyên raw hash `cc1d42f6…` đã khóa |
| `labels_khue.csv` | CRLF | Giữ nguyên raw hash annotator đã khóa |
| `labels_huyen.csv` | CRLF | Giữ nguyên raw hash annotator đã khóa |
| `candidate_assets.csv` | CRLF | Giữ nguyên raw hash candidate CSV đã khóa |

Qrels/labels/candidate CSV đang có raw hashes của bản CRLF. Pin EOL riêng
giữ đúng những hashes đó cả trên Windows/Linux, không thay nội dung/nhãn.
Không áp dụng một quy tắc chung cho các CSV benchmark ảnh hoặc file khác.
Source `objaverse_200.json` tiếp tục LF theo rule sẵn có, hash `9dcc0afd…`.

Git blob query hiện tại giống nguyên blob `ff7b64a`: toàn bộ IDs, wording,
groups, split và mọi byte trong file Git không đổi. Chỉ sửa metadata nhận diện
artifact và quy tắc checkout. Git blobs của qrels, hai bộ nhãn, candidate CSV
và snapshot JSON giữ nguyên; raw bytes thực tế cũng khớp pins đã có.

## Bảo toàn baseline lịch sử

Giữ nguyên hai result JSON, hai report Markdown W2/W3, config keyword và các
script `run_issue71_clip.py`, `run_keyword_baseline.py`. Record lưu SHA-256
**raw Git blob** của chúng; checker còn so worktree với HEAD bằng đúng Git
path filters. Cách so lịch sử này không dùng để tính hash artifact query.

Không thay `f627…` bằng `e202…` trong report/provenance cũ, không sửa recorded
metrics/hashes để ngụ ý đã chạy lại. Giống nội dung sau parse không chứng minh
lần chạy cũ đã dùng artifact đề nghị này. Baseline cũ không được coi là đối
chứng tương đương W5 khi provenance raw query chưa giải quyết.

`run_issue71_clip.py` vẫn giữ các pins lịch sử và yêu cầu artifact tương ứng;
không dùng entrypoint đó với manifest mới để tái gắn nhãn kết quả cũ. Không
chạy main của hai script baseline trong PR này. Runner W5 chỉ import validator
và metric helper, rồi chạy **mới** CLIP-only/E5-only/RRF trên cùng input đã review.

## Kiểm chứng không chạy benchmark

Từ gốc repo:

```bash
backend/.venv/Scripts/python.exe -B scripts/verify_issue91_query_artifact.py --compare-source-commit
```

Cờ trên so raw query với source commit; cần object `ff7b64a` trong clone.
Với CI shallow, bỏ cờ: checker vẫn kiểm raw SHA-256/size/BOM/LF/EOF, cấu trúc,
HEAD query blob, active locks, pending config, qrels/snapshot và lịch sử. Nó
không đọc ranked results để tính metric hoặc chạy retrieval.

Checker mô phỏng checkout bằng `git cat-file --filters` với cả
`core.autocrlf=true` và `false`, yêu cầu raw hashes giống pins trong mỗi mode.
Các `-c` chỉ áp dụng cho từng lệnh đọc; không ghi Git config/index/worktree.
Không chuẩn hóa bytes trước hash và không tự sửa file bị lỗi.

```bash
backend/.venv/Scripts/python.exe -B -m pytest -c backend/pytest.ini backend/tests/unit/test_issue91_query_artifact.py backend/tests/unit/test_e5_rrf_validation.py -q -p no:cacheprovider
backend/.venv/Scripts/python.exe -B -m pytest -c evaluation/pytest.ini evaluation/tests -q -p no:cacheprovider
backend/.venv/Scripts/python.exe -B scripts/run_e5_rrf_validation.py --preflight-only
```

Lệnh cuối vẫn phải trả `blocked`, exit 2, `models_loaded=false` vì chưa có
review/merge erratum và config confirmed. Các tests kiểm byte drift, các lock
fields, EOL hai mode, bảo toàn lịch sử và gate; không dùng 42 test query để tune.

## Sau khi erratum được merge

Ghi evidence review/merge cùng source/merge commit và hashes đã chốt khi chuẩn
bị config confirmed ở bước tiếp theo. Giữ BOM/LF/4 LF cuối nguyên trạng, kiểm
raw hashes bằng validator. Sau preflight confirmed mới chạy mới cả ba luồng,
grid `k={10,20,60}` trên 28 validation, candidate 200, filters `{}`; dùng cùng
protocol metrics/latency đã chốt và [runner hiện có](../guides/e5-rrf-validation-runner-91.md).
Chưa chạy/chọn cấu hình hoặc đóng #91 chỉ từ PR đính chính.


## Kiểm chứng local — 14/11/2026

- Checker với `--compare-source-commit` **passed**: nguyên bytes query bằng
  source commit và HEAD, raw hashes đúng cả hai autocrlf modes; toàn bộ inputs
  cần giữ và các report/config/script lịch sử không đổi Git blob hay nội dung
  worktree. Hash bytes worktree lịch sử trước/sau local cũng bằng nhau.
- **28 tests artifact guards passed, 2,73 s**; **56 tests runner passed,
  49,36 s**; **23 tests evaluation passed, 9,07 s**. Đây là kiểm tra integrity
  và fixtures, chưa chạy benchmark models thật.
- Preflight mặc định vẫn `blocked`, exit 2, `models_loaded=false`.
- [Bằng chứng](../evidence/issue91-query-artifact-erratum-20261114.json) ghi
  hashes/commands và base `522a466`, dirty=true theo lúc chạy. Các kết quả
  local không thay review/CI/merge của PR erratum.
