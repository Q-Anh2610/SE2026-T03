# Kiểm chứng và bàn giao báo cáo W5 — Issue #105

Refs [#105](https://github.com/Q-Anh2610/SE2026-T03/issues/105).
Xem [báo cáo W5](../evaluation/issue105-w5-initial-comparison.md) và
[JSON đối chiếu archive](../evidence/issue105-archive-metrics-review-20261116.json).

## 1. Kiểm tra nhánh, inputs

Từ gốc repo trong PowerShell, chạy từng lệnh. Giữ nguyên thay đổi có sẵn của người
khác; nhánh cần là test/105-w5-evaluation-report. Không stage cả repository.

~~~powershell
rtk proxy git status --short --branch
rtk proxy git diff --cached --stat
rtk proxy ./backend/.venv/Scripts/python.exe -B scripts/verify_issue91_query_artifact.py --repo . --compare-source-commit
rtk proxy ./backend/.venv/Scripts/python.exe -B scripts/run_e5_rrf_validation.py --config evaluation/configs/issue91-e5-rrf-validation.confirmed.json --preflight-only
~~~

Kỳ vọng artifact passed, confirmed preflight inputs_verified, 28 validation query,
models_loaded=false. Lệnh không nạp model. Không bỏ --config: CLI default pending
có chủ đích. Nếu hash lệch, đối chiếu bytes và nguồn trước, không sửa pins.
Dùng venv backend đã có; không tạo lại venv/cài dependencies chỉ để làm báo cáo.

## 2. Nhận archive

Tải issue91-validation-20261114-review.zip từ comment bàn giao
[#91](https://github.com/Q-Anh2610/SE2026-T03/issues/91) về ngoài repo.
Pins: 2.543.329 byte, SHA-256
097a1b53ccc0751170d813f0e97407516dd63052bd8ca2c1481477fe46decb6a.
Bản người dùng đã nhận ở D:/Download; lệnh sau chỉ đọc metadata/hash:

~~~powershell
rtk proxy powershell -NoProfile -Command "Get-Item -LiteralPath 'D:/Download/issue91-validation-20261114-review.zip' | Select-Object FullName,Length"
rtk proxy powershell -NoProfile -Command "Get-FileHash -Algorithm SHA256 -LiteralPath 'D:/Download/issue91-validation-20261114-review.zip' | Format-List"
rtk proxy tar -tf D:/Download/issue91-validation-20261114-review.zip
~~~

Archive có 48 entries: 46 payloads trong bảng checksum, thêm README và bảng hash.
Kiểm danh sách không có đường dẫn tuyệt đối, duplicate hoặc parent traversal.
Dùng giao diện giải nén Windows vào thư mục mới, giữ nguyên bytes và cấu trúc:

~~~text
data/processed/issue105/raw-review-1/
  bundle-files-sha256.json
  runs/
  inputs/
  measured-source/
  docs/
  auditor/
~~~

Không chép đè source/input hiện tại, không thay EOL hay hash run. Archive không
chứa weights/Qdrant storage. Raw/ZIP/helpers local/output ở data/processed/ được
ignore, không stage. Nếu đích đã có, dùng thư mục mới và truyền đường dẫn đó cho
helper. Không dùng lại lệnh inline PowerShell nhiều dòng qua RTK: lần thử trong
phiên bị mất quoting; công cụ file bên dưới tránh vấn đề đó.

## 3. Tính lại metric từ raw, không chạy retrieval

[Helper chia sẻ](../../scripts/audit_issue105_review_bundle.mjs) chỉ dùng Node
standard library, không cần npm install. Từ gốc repo:

~~~powershell
rtk proxy node ./scripts/audit_issue105_review_bundle.mjs
~~~

Mặc định đọc raw-review-1 theo cấu trúc trên, ghi file mới
 data/processed/issue105/metrics-review-2.json. Helper từ chối ghi đè output.
Có thể truyền hai positional arguments là thư mục bundle và file output mới:

~~~powershell
rtk proxy node ./scripts/audit_issue105_review_bundle.mjs ./data/processed/issue105/raw-review-1 ./data/processed/issue105/metrics-review-3.json
~~~

Kỳ vọng: PASSED: 9/9 combinations; 252 raw records; 2520 samples; metrics and
latency match. Một trong hai lệnh đủ cho lần kiểm; không cần chạy cả hai nếu đã
đạt. Nếu lỗi, giữ output gốc và chẩn đoán, không sửa bằng chứng để ép passed.

Helper kiểm 46 exact hashes, archived validation queries/qrels và candidate 200,
28 query/cấu hình/run, 10 sample/query, split/text/group/positive IDs/ranks/filters.
Nó tính Recall@5/10, Hit@5/10, binary nDCG@10 và nearest-rank p50/p95 rồi so run
records và evidence #91. Numeric tolerance tuyệt đối là 1e-12, raw hashes exact.
Recall mẫu số 21, Hit/nDCG 28; percentile lấy vị trí 140/266 trên 280 mẫu.

Không chạy lại model/retrieval, toàn bộ Fraction RRF, repeat DTO không xuất hoặc
live persisted-index audit. Đọc split test chỉ kiểm cấu trúc; không tính quality
test. Guide [runner gốc](e5-rrf-validation-results-91.md) và
[auditor gốc](../../scripts/audit_e5_rrf_validation_grid.py) dùng để tái lập bước
rộng hơn khi có đủ artifacts/bytes/code đúng pins. Khác checkout EOL không phải lý
do để sửa hashes report. Không cần chạy benchmark mới chỉ để hoàn thiện tài liệu.

## 4. Đọc kết quả và kiểm diff

Báo cáo phân biệt lần đo model thật #91, audit archive #105, fixture tests và
CI/review/merge của từng PR. Input confirmed chưa phải quyết định model/k khóa.
Phần ảnh giữ blocker quality/raw/protocol, chờ reviewer xác nhận cách ghi; không
suy chất lượng ảnh từ text/smoke. Quyết định W6 và benchmark test thuộc #114.

~~~powershell
rtk proxy git diff --check
rtk proxy git diff --stat
rtk proxy git status --short --branch
~~~

File mới chưa tracked không hiện trong diff --stat. Đọc cả report/guide/script/
evidence; kiểm staged diff sau khi stage đúng đường dẫn. Với thay đổi này, audit
archive là kiểm chứng helper; không cần chạy toàn bộ backend/frontend hoặc nạp
models. Nếu sửa code sản phẩm về sau, bổ sung checks liên quan.

## 5. Commit, PR, review

Chỉ commit/push khi người dùng thực hiện hoặc đã giao quyền tương ứng. Kiểm index
có sẵn, stage đường dẫn cụ thể và đọc staged diff trước commit. Gợi ý message:
 test(evaluation): verify and report W5 validation results.

PR head test/105-w5-evaluation-report, base develop, Refs #105; dùng
[template chung](../../.github/PULL_REQUEST_TEMPLATE.md). Nêu reuse #91, preflight,
audit archive, giới hạn ảnh, chưa chọn model/k và không đổi API/schema/index/deps.
Không dùng test local để tích CI, approve hoặc merge. Sau khi có PR, liên kết và
cập nhật acceptance checklist trong Issue đúng bằng chứng. Reviewer khác approve,
required checks đạt và xử lý trao đổi chặn trước merge; chưa tự nghiệm thu toàn W5.
