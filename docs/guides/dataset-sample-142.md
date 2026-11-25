# Tái lập dataset mẫu W7 — Issue #142

## Phạm vi và trạng thái

Sample dùng cho setup/smoke dữ liệu, chưa thay thế candidate 200, snapshot W4
354 asset, corpus E5 hoặc frozen config W6. Chưa xác nhận lựa chọn sample bởi
bên sử dụng; giữ `draft_selection_pending_confirmation` trong artifact hiện tại.

Trịnh Thị Thu Huyền (@TrinhHuyen05) chuẩn bị dữ liệu; Đoàn Thị Minh Khuê
(@doanminhkhue25) phối hợp tái lập môi trường; Lê Thị Linh Chi (@LLC536) đối chiếu
đầu vào #135; Vũ Nguyễn Quỳnh Anh (@Q-Anh2610) review ảnh hưởng ingestion.

Quy trình dưới đây chỉ xuất metadata và tải/kiểm preview. Không ghi PostgreSQL,
không nạp model, dựng Qdrant hoặc đổi active index.

## Inputs và sample draft

| Thuộc tính | Giá trị |
|---|---|
| Manifest nguồn | `data/manifests/objaverse_200.json` |
| Snapshot nguồn | `home-interior-clear-200-v3` |
| Source commit | `bff65ac2a29ae213042ae942524966ed6cd3ea5f` |
| Source SHA-256 | `9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd` |
| Quy tắc | `asset-id-sorted-prefix-v1-draft`: 5 asset đầu theo asset ID tăng dần |
| Sample SHA-256 | `382edf90aaa35cb02bd2b60deba403aa54a5b0f8f4bd2d3560c679b2ea0b4a6d` |

Danh sách IDs:

- `objaverse_0060af6f4da24224a4770eea54685ecf`
- `objaverse_009de5b694dd4aac9c5a760d544046d1`
- `objaverse_00b360de1846428eb5c23464824c5fc8`
- `objaverse_01810aab099a49569c550c646b3427cc`
- `objaverse_018cff2beb324e609446af6f64d059e2`

Manifest giữ metadata gốc, không xuất lại normalized records. Attribution giữ
source URL, author và license theo nguồn; trong sample có nhãn `by-nc`.
Các trường đó chưa phải xác nhận quyền phân phối gói ảnh. License mã nguồn
project không tự áp dụng cho từng asset. Guide/gói tham chiếu không kèm ảnh.

## Prerequisites và ghi môi trường

- Windows/Git Bash, Git và virtualenv backend đã cài dependencies của repo.
- Checkout có script/tests #142; ghi chính xác commit và trạng thái working tree
  đang chạy. Source commit ở bảng trên là commit dữ liệu, không phải commit
  triển khai script #142.
- Có mạng tới nguồn preview cho bước tải; bước xuất metadata/tests không cần mạng.
- Không cần PostgreSQL, Qdrant hoặc model weights.

Từ repository root, chạy:

```bash
source backend/.venv/Scripts/activate
git branch --show-current
git log -1 --oneline
git status --short
python --version
python -m pytest --version
git --version
python -c "import importlib.metadata as m; print('Pillow:', m.version('Pillow'))"
mkdir -p work
```

Nếu dùng OS/virtualenv khác, thay lệnh activate và cách chuyển đường dẫn.
Ghi môi trường thực tế, không sao chép phiên bản của tác giả làm kết quả máy nhận.

## 1. Xuất sample vào output mới

```bash
sample_run="$(mktemp -d work/issue142-review-XXXXXX)"
echo "Run directory: $sample_run"

python scripts/prepare_dataset_sample.py \
  --repo . \
  --source-ref bff65ac2a29ae213042ae942524966ed6cd3ea5f \
  --count 5 \
  --output "$sample_run/sample"
```

Cần exit code 0, `offline_draft_generated`, asset_count 5 và sample SHA-256
khớp bảng trên. `previews_verified=false` là đúng ở bước offline.

Script kiểm source Git hash, metadata checkout và Source Adapter trước khi tạo
output; từ chối output đã tồn tại. Nếu chạy lại, tạo run directory mới, không
xóa artifact cũ để che kết quả khác biệt.

```bash
(cd "$sample_run/sample" && sha256sum -c CHECKSUMS.sha256)

python scripts/prepare_dataset_sample.py \
  --repo . \
  --source-ref bff65ac2a29ae213042ae942524966ed6cd3ea5f \
  --count 5 \
  --output "$sample_run/sample-repeat"

for name in assets.json attribution.json provenance.json CHECKSUMS.sha256
do
  cmp "$sample_run/sample/$name" "$sample_run/sample-repeat/$name" \
    && echo "PASS: $name"
done
```

Cần 3 checksum OK và 4 PASS trên cùng checkout/script bytes. File provenance
ghi SHA-256 raw bytes của generator; nếu máy khác có code/EOL khác, provenance
và bảng checksum có thể khác bản tham chiếu. Báo khác biệt và đối chiếu code/EOL,
không sửa provenance/hash lịch sử. `assets.json` và attribution phải khớp nếu
nguồn, quy tắc và implementation tương ứng không đổi.

## 2. Tải preview thật

Đây là thao tác tải ảnh được kích hoạt riêng; không thêm `--persist-db`.

```bash
python -m backend.app.ingestion.cli \
  --manifest "$sample_run/sample/assets.json" \
  --output-dir "$sample_run/previews" \
  --report "$sample_run/download-report.json" \
  --max-attempts 3
preview_exit=$?
echo "Exit code: $preview_exit"
```

Cần input_count=5, succeeded=5, failed=0, skipped=0, exit code 0. Downloader
kiểm host/redirect được phép, giới hạn nội dung/kích thước, decode và checksum.
Nếu URL lỗi hoặc nội dung đổi, giữ report và báo asset lỗi; không tự chọn asset
khác, sửa pin hoặc coi tải thành công là bytes đã khớp bản bàn giao.

## 3. Kiểm lại file và đối chiếu evidence tham chiếu

Giải nén ZIP tham chiếu vào thư mục mới. Khai báo đường dẫn tới thư mục đã giải
nén, ví dụ bên dưới; thư mục này phải có `CHECKSUMS.sha256` và `reference/`.

```bash
reference_dir="work/issue142-reference"
(cd "$reference_dir" && sha256sum -c CHECKSUMS.sha256)

python - "$sample_run" "$reference_dir/reference/preview-verification.json" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

from backend.app.ingestion.cache import reusable_preview

run = Path(sys.argv[1]).resolve()
reference = json.loads(Path(sys.argv[2]).read_bytes())
sample = run / "sample/assets.json"
provenance = run / "sample/provenance.json"
report_path = run / "download-report.json"
assets = json.loads(sample.read_bytes())
report = json.loads(report_path.read_bytes())
expected = {row["asset_id"]: row for row in assets}
reference_rows = {row["asset_id"]: row for row in reference["verified_previews"]}
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()

assert len(assets) == len(expected) == 5
assert digest(sample) == reference["sample_sha256"]
assert set(expected) == set(reference_rows)
assert report["persistence"] == "local_files_only"
assert report["manifest_sha256"] == digest(sample)
assert report["summary"] == {
    "input_count": 5, "succeeded": 5, "failed": 0, "skipped": 0,
}
assert len(report["results"]) == 5
assert {row["asset_id"] for row in report["results"]} == set(expected)
verified = []
for row in report["results"]:
    asset = expected[row["asset_id"]]
    assert row["status"] == "downloaded"
    assert row["source"] == asset["source"]
    assert row["source_id"] == asset["source_id"]
    checked = reusable_preview(row, asset["thumbnail_path"], run / "previews")
    assert checked is not None, asset["asset_id"]
    pin = reference_rows[asset["asset_id"]]
    for key in ("sha256", "bytes", "width", "height"):
        current = checked["checksum"] if key == "sha256" else checked[key]
        assert current == pin[key], (asset["asset_id"], key)
    path = Path(checked["preview_local_path"]).resolve()
    verified.append({
        "asset_id": asset["asset_id"],
        "file": path.relative_to(run).as_posix(),
        "sha256": checked["checksum"], "bytes": checked["bytes"],
        "width": checked["width"], "height": checked["height"],
    })
result = {
    "status": "passed_receiver_preview_check",
    "sample_sha256": digest(sample),
    "sample_provenance_sha256": digest(provenance),
    "download_report_sha256": digest(report_path),
    "verified_previews": verified,
    "database_written": False, "index_built": False,
    "distribution_rights_verified": False,
}
output = run / "receiver-verification.json"
with output.open("x", encoding="utf-8", newline="\n") as file:
    json.dump(result, file, ensure_ascii=False, indent=2)
    file.write("\n")
print("PASS: 5 previews match IDs, URLs, checksums, decoding and reference bytes")
print("Evidence:", output)
PY
receiver_exit=$?
echo "Exit code: $receiver_exit"
```

Nếu kiểm tra fail, không có kết quả passed hợp lệ. Báo đúng bước/ID khác biệt;
không cập nhật hashes tham chiếu theo ảnh mới để vượt kiểm tra.
`provenance.json` offline vẫn ghi previews chưa được kiểm; evidence tải/kiểm
thật nằm riêng, không sửa artifact offline hoặc bảng checksum cũ bằng tay.

## 4. Tests exporter

```bash
sample_test_tmp="$(mktemp -d "$PWD/work/pytest-142-review-XXXXXX")"
python -m pytest backend/tests/unit/ingestion/test_dataset_sample.py \
  --basetemp="$(cygpath -w "$sample_test_tmp")" --tb=short -q
```

Kết quả tác giả đã ghi nhận: 17 tests exporter passed; ingestion suite 220 passed.
Các tests dùng metadata/Git reader giả lập và validator thật. Không thay thế
bước tải/kiểm preview thật, CI hoặc phản hồi tái lập của thành viên khác.

## Bằng chứng tác giả và bàn giao

- Sample draft xuất từ source commit nêu trên, 5 IDs, sample hash đã ghi trong bảng.
- Lần preview local của tác giả: 5 downloaded, không lỗi, checksum/decode đạt.
  Evidence tham chiếu ở `reference/preview-verification.json`; không dùng output
  của tác giả làm kết quả tự chạy của người nhận.
- Tại lượt đo, script/tests #142 chưa commit; gói tham chiếu lưu raw generator
  để đối chiếu hash. Không gán commit tạo sau cho lần đo trước.
- ZIP tham chiếu chỉ chứa metadata/provenance, evidence, guide và raw generator;
  không chứa ảnh, model/index, credentials hoặc DB dump.
- Không có yêu cầu rebuild index trong guide này. #135 vẫn cần candidate 200,
  corpus/model pins và quy trình riêng.

Người nhận comment tại #142: commit/working-tree status, OS/Python/Pillow/Git,
lệnh thực hiện, counts/exit codes, sample hash, kết quả đối chiếu preview và vị
trí evidence riêng; nêu lỗi/giới hạn thực tế. Xác nhận riêng mục đích/chọn sample,
việc chạy tái lập và phạm vi đầu vào #135; không gộp thành xác nhận toàn W7.

Giữ data/runtime trong `work/`. Helper không tự xóa dữ liệu kiểm chứng. Nếu dọn,
chỉ xóa đúng run directory do mình tạo sau khi đã lưu evidence cần thiết;
không xóa nguồn, output của người khác hoặc thư mục dùng chung.
