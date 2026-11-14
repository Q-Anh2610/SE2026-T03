# Audit metadata/payload — Issue #101 — 15/11/2026

## Kết quả và giới hạn

Audit `passed`, exit code 0 trên candidate 200 của `home-interior-clear-200-v3`. Đây là kiểm chứng tích hợp trên PostgreSQL test được dựng từ frozen manifest và bản sao index CLIP/E5 đã nhận; không chứng minh DB nghiệp vụ đang dùng đã được đồng bộ. Không chạy retrieval, weights hoặc benchmark.

Thời điểm trong JSON: `2026-11-14T17:38:45.360709+00:00`, tương ứng 00:38:45 ngày 15/11/2026 ở Asia/Bangkok.

| Nguồn | Record/ID duy nhất | IDs thiếu/ngoài phạm vi/trùng | Metadata lệch | Compatibility lệch |
|---|---|---|---|---|
| PostgreSQL test | 200/200 | 0/0/0 | 0 | Source versions khớp nguồn |
| CLIP | 200/200 | 0/0/0 | 0 | 0 |
| E5 | 200/200 | 0/0/0 | 0 | 0 |

So sánh DB với mỗi payload cũng passed. DB dùng transaction `REPEATABLE READ, READ ONLY`; mỗi SQLite giữ nguyên raw SHA-256 trước/sau. Qdrant local có thể quản lý tệp lock khi mở, vì vậy chỉ mở bản sao audit. Không gọi seed/upsert/migration/rebuild trong auditor.

## Input và provenance

- Frozen source: `data/manifests/objaverse_200.json`, SHA-256 `9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`.
- Corpus SHA-256: `66efd87e34447c23b4171e13ac77d78a9c193519141d0dd6a31985c01e65b4f5`.
- Corpus manifest SHA-256: `d069a0f126812e39785a6395aec5e0c03195abbe596abb5a2e3aecc7a5d6f922`.
- Recipe version: `e5-metadata-passage-v1-draft`; corpus manifest được index pin giữ nguyên trạng thái lịch sử, không thay bằng manifest exporter mới.
- ZIP: `issue101-candidate200-clip-e5-storage-20261115.zip`, 3.941.085 byte, SHA-256 `d7f3df8cc1cb0c1a9a59334b7855aeb07c1d3bf8aa1c3b90544661ba2f8d2a52`.
- Verifier ZIP passed: 220 artifact files, 223 checksummed entries, 224 ZIP entries. Bản giải nén và bản sao audit đều passed toàn bộ bảng checksum trước khi mở storage.

| Index | Collection | Named vector | Index version |
|---|---|---|---|
| CLIP | `issue89_image_previews` | `clip_bdd84b49a263010b` | `issue89-clip-preflight-76d5d2c095b6` |
| E5 | `issue91_e5_metadata` | `e5_0c0cbdfd79bca607` | `issue91-e5-metadata-1588f4dc33fbe62609d8` |

CLIP index manifest SHA-256: `7ebba709c46fec69dc4485cd0b358e82ca48c60ce568b3a03111ac943b882528`.

E5 index manifest SHA-256: `b89e50f8dbf3a5d6e57e41f5302a585fd06afb05f09eeb41fe0e09fdaf22a51d`.

Chuẩn bị DB đã kiểm source hash, SourceAdapter hợp lệ, 200 IDs và metadata đọc lại khớp nguồn; không gán downloaded/searchable hoặc versions mới. DB `test_issue101`, schema `test_asset_api_65b587c1206f475a8fb7a4caec3c3e1b`, PostgreSQL 18.6, migration 0002. Người chạy đã báo lưu bằng chứng rồi dùng CLEANUP để helper dọn schema riêng. Schema lịch sử trong JSON không còn là môi trường để kết nối; lần tái lập tạo UUID mới.

## Code thực sự đã chạy

Auditor được chạy khi còn nằm ở `work/audit_issue101_metadata.py`. File `scripts/audit_issue101_metadata.py` được đưa vào review giữ nguyên bytes, SHA-256 `c348e3ae1f3e738b021599fc0dec1e8831378d12889b7b572c668776e5839989`, khớp `auditor_sha256` trong JSON. Không gán commit được tạo sau cho lần chạy này.

[JSON nguyên bytes](../../evidence/issue101-metadata-payload-audit-20261115.json) có 4.211 byte, SHA-256 `09a5982352a9d9745798effdc9d789a4694df40c06d78cbb273b526a8fbf8963`. Giữ LF bằng `.gitattributes`; không sửa nội dung JSON để phản ánh các commit hoặc cleanup về sau.

## Cách tái lập

Cần Python/backend dependencies, Git và qdrant-client đúng `1.15.1`. Không cần weights. Phải nhận đủ storage/artifacts và kiểm ZIP/checksum như hướng dẫn bàn giao; audit trên bản sao riêng, không dùng bản nhận gốc và không mở hai client cùng storage.

Từ gốc repo, terminal thứ nhất:

```bash
source backend/.venv/Scripts/activate
python scripts/prepare_issue101_db.py --repo . --host 127.0.0.1 --port 5432 --user postgres
```

Nhập mật khẩu local tại prompt ẩn. Script chỉ dùng database `test_issue101`, tạo nếu chưa có rồi dùng helper schema UUID mới, migration và nạp 200 record. Không kết nối `semantic_search`. Giữ terminal mở ở `Command:` và ghi lại đường dẫn preparation report. Không đăng mật khẩu/connection string lên GitHub.

Terminal thứ hai, thay đường dẫn bằng output và bản sao artifact của lần hiện tại:

```bash
source backend/.venv/Scripts/activate
read -r -p "Preparation report path: " preparation_report
read -r -p "Audit-copy root path: " audit_copy_root
python scripts/audit_issue101_metadata.py --repo . --artifact-root "$audit_copy_root" --preparation-report "$preparation_report" --user postgres
audit_exit=$?
echo "Exit code: $audit_exit"
```

Chỉ kết luận đạt khi `AUDIT STATUS: passed`, PostgreSQL/CLIP/E5 đều passed và exit code 0. JSON được ghi tại thư mục UUID mới trong `work/issue101-audit/`. Auditor đọc source Git HEAD nhưng kiểm đúng frozen hash và checkout JSON, kiểm toàn bộ checksum artifact trước mở clients, tái dùng passage recipe từ exporter hiện có, đối chiếu metadata, payload provenance, collection/vector/dimension/Cosine và SQLite bytes trước/sau.

Lưu report và code provenance trước khi gõ `CLEANUP` ở terminal thứ nhất. Helper chỉ dọn schema do lượt đó tạo; database test vẫn còn. Nếu có mismatch, giữ report và thống nhất hướng xử lý trước khi sửa nguồn/DB/index; auditor không tự đồng bộ. `--storage-only` chỉ là preflight index và không được coi là audit PostgreSQL–payload đã đạt.

## Kiểm thử và trạng thái nghiệm thu

Bộ `backend/tests/unit/ingestion/test_metadata_audit.py` dùng fixtures, không kết nối PostgreSQL hoặc storage thật. Trong lúc chuẩn bị bộ file review, 37 cases đã passed trong 2,49 giây. Đây là bằng chứng riêng với live audit và không thay kết quả tests/CI trên checkout cuối của PR.

Tests bao phủ metadata khác nhau, null so với trường thiếu, IDs thiếu/ngoài phạm vi/trùng, kiểu dữ liệu, input không bị sửa, guard DB/schema/host, READ ONLY trước SELECT, versions riêng từng index, named vector/dimension, mapping point ID và phát hiện SQLite bị đổi. Tests source preparation kiểm frozen bytes, IDs và checkout sai; việc tạo/nạp DB thật được ghi nhận trong lượt kiểm chứng local riêng.

Chạy từ Git Bash:

```bash
corpus_test_tmp="$(mktemp -d "$PWD/work/pytest-audit-XXXXXX")"
python -m pytest backend/tests/unit/ingestion/test_metadata_audit.py --basetemp="$(cygpath -w "$corpus_test_tmp")" --tb=short -q
```

Môi trường live audit: Windows, Git Bash, Python 3.13.17, pytest 9.1.1, Git 2.56.0.windows.4, qdrant-client 1.15.1, PostgreSQL 18.6.

Không có metadata/compatibility mismatch trong phạm vi này nên không phát sinh sửa đồng bộ; không đánh dấu như đã triển khai hoặc test một cơ chế retry/idempotency mới. Kết quả còn cần bên nhận review/xác nhận bàn giao, CI head mới nhất và merge PR #102; chưa tự nghiệm thu cả W5.

Phối hợp backend: Vũ Nguyễn Quỳnh Anh (https://github.com/Q-Anh2610). Phối hợp index: Lê Thị Linh Chi (https://github.com/LLC536).
