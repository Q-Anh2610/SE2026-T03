# Keyword diagnostic: home-interior-text-v2

**This is not the final retrieval baseline for Issue #46.** It is retained as a
metadata keyword diagnostic and must not be presented as CLIP text retrieval
quality on the verified snapshot.

## Phạm vi và cách chạy

Đã chạy một lần trên bộ query/qrels đã khóa bằng SHA-256, dùng implementation
W2 `backend.app.search.keyword.KeywordBaseline` (`keyword-token-overlap-v1`)
trên metadata của 200 asset. Đây chỉ là phép đo keyword trên name/description/
tags. Nó không tạo ranked results từ CLIP text retrieval hoặc index mới của
snapshot `home-interior-clear-200-v3`, nên không thỏa phần baseline retrieval
Chi cần cung cấp cho Issue #46. Không gọi HTTP Search API/W3 và không dùng kết
quả test để thay đổi cấu hình.

- Query: 70 tiếng Anh; validation 28, test 42; split theo group, seed 42.
- Cấu hình cố định: top-10, không filters, nhãn dương `relevance >= 1`.
- Keyword score là số token truy vấn khác nhau khớp trong name/description/tags;
  không phải xác suất và không biểu diễn semantic relevance.
- Baseline và metric được tạo bởi
  [run_keyword_baseline.py](../../evaluation/run_keyword_baseline.py), với cấu hình
  [home-interior-text-v2-keyword.json](../../evaluation/configs/home-interior-text-v2-keyword.json).
- Kết quả có ranked IDs, scores, provenance và metric theo split tại
  [home-interior-text-v2-keyword-baseline.json](../../evaluation/results/home-interior-text-v2-keyword-baseline.json).

## Kết quả

| Tập | Queries | Recall@5 | Hit@5 | Recall@10 | Hit@10 | nDCG@10 |
|---|---:|---:|---:|---:|---:|---:|
| Validation | 28 | 0.124704 | 0.535714 | 0.172658 | 0.642857 | 0.188325 |
| Test | 42 | 0.138764 | 0.642857 | 0.231332 | 0.738095 | 0.276618 |
| Tất cả | 70 | 0.133760 | 0.600000 | 0.210448 | 0.700000 | 0.241301 |

Recall là macro average trên các query có ít nhất một asset relevance ≥1:
21/28 validation, 38/42 test và 59/70 tổng. Các query không có nhãn dương
không có Recall xác định và được liệt kê trong JSON. Hit/nDCG tính các query đó
là 0; nDCG cũng có ideal DCG bằng 0 nên không thể diễn giải riêng như query có
đáp án liên quan.

Query không có nhãn dương:

- Validation (7): `q0043`, `q0044`, `q0045`, `q0046`, `q0047`, `q0068`, `q0070`.
- Test (4): `q0031`, `q0053`, `q0057`, `q0066`.

Đây là vấn đề cần được ghi nhận khi diễn giải benchmark. Do đã xem kết quả test
của phép đo diagnostic này, không sửa qrels, query hay cấu hình của benchmark
đã khóa dựa trên các kết quả đó. Nếu nhóm xác nhận có lỗi nhãn/query hoặc cần
đổi tiêu chí, tạo benchmark version mới, khóa lại inputs và đánh giá lại theo
quy trình đã duyệt.

Chi xác nhận chưa có ranked results thật cho text retrieval trên snapshot mới.
Các kết quả index cũ thuộc snapshot W1 không thay thế được snapshot này. Cần
chờ Chi triển khai/chạy text retrieval và xuất kết quả theo contract trong phản
hồi của Chi; qrels có thể giữ phía evaluation, chỉ cần cung cấp query đã khóa.

## Khóa đầu vào và provenance

| Đầu vào | SHA-256 |
|---|---|
| `queries.csv` | `f62762c4a0b392ddc310d1d64e0bdb685b2010347e3790395bbb523428c38788` |
| `qrels.csv` | `cc1d42f6e3f41f92fab1b842c7a70ca68be4341cdd30e4262e13989f99019df5` |
| Snapshot `objaverse_200.json` | `9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd` |
| Config JSON | `340de3dc1bb42ef63ea8ac070c99cd5b238be3a74c948a485b4797e5d4974289` |
| Raw run JSON | `b81546e9209c076f91f369462dfec0e6cb82e3b2dbfb3548d9fb9e3ec3853fb9` |

- Run time: `2026-11-03T14:29:24.547689+00:00`.
- Git revision: `e8b8312b245d5999a03b03192ad476f47914d7fd`.
- Environment: Python 3.13.15 on Windows; full platform string is recorded in
  the run JSON.
- Test set used for configuration changes: no.

## Reproduction

From the repository root, run:

```powershell
.venv-1\Scripts\python.exe evaluation\run_keyword_baseline.py
```

The runner verifies query, qrels, and snapshot hashes against the lock manifest
before running. It does not change the config after computing test metrics.
