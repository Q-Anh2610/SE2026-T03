"""Xuất manifest mẫu offline từ frozen candidate 200; không tải ảnh/ghi DB."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


SOURCE_PATH = "data/manifests/objaverse_200.json"
SOURCE_HASH = "9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd"
SNAPSHOT = "home-interior-clear-200-v3"
RECIPE = "asset-id-sorted-prefix-v1-draft"


def sha256(content):
    return hashlib.sha256(content).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       indent=2, allow_nan=False) + "\n").encode("utf-8")


def git(repo, *arguments):
    return subprocess.check_output(["git", *arguments], cwd=repo)


def prepare_sample(repo, output, count=5, source_ref="HEAD"):
    if type(count) is not int or not 1 <= count <= 200:
        raise ValueError("count phải là số nguyên từ 1 đến 200.")
    repo = Path(repo).resolve()
    output = Path(output).resolve()
    # Resolve ref once so provenance identifies the bytes actually read.
    commit = git(repo, "rev-parse", "--verify", "--end-of-options",
                 source_ref + "^{commit}").decode().strip()
    raw = git(repo, "show", f"{commit}:{SOURCE_PATH}")
    if sha256(raw) != SOURCE_HASH:
        raise ValueError("Source Git SHA-256 không khớp frozen manifest.")
    records = json.loads(raw)
    checkout = json.loads((repo / SOURCE_PATH).read_text(encoding="utf-8"))
    if checkout != records:
        raise ValueError("Metadata checkout khác source Git đã pin.")
    if not isinstance(records, list) or len(records) != 200:
        raise ValueError("Source phải có đúng 200 records.")

    sys.path.insert(0, str(repo / "backend"))
    from app.ingestion.source_adapter import SourceAdapter

    # Reuse validation, but export original metadata, not normalized records.
    valid, invalid = SourceAdapter(repo / SOURCE_PATH).normalize_and_validate(records)
    if invalid or len(valid) != 200:
        raise ValueError("Source không hợp lệ hoặc có định danh trùng.")
    selected = sorted(records, key=lambda row: row["asset_id"])[:count]
    assets = json_bytes(selected)
    attribution_fields = ("asset_id", "name", "source", "source_id",
                          "source_url", "author", "license")
    attribution = json_bytes({
        "status": "source_metadata_only_not_distribution_clearance",
        "records": [{key: row.get(key) for key in attribution_fields}
                    for row in selected],
        "missing_fields": {
            row["asset_id"]: [key for key in ("source_url", "author", "license")
                              if row.get(key) in (None, "")]
            for row in selected
            if any(row.get(key) in (None, "")
                   for key in ("source_url", "author", "license"))
        },
        "note": "Giữ nhãn license nguồn; chưa xác minh quyền phân phối gói ảnh.",
    })
    provenance = json_bytes({
        "schema_version": "dataset-sample-provenance-v1-draft",
        "sample_name": "home-interior-setup-sample-v1-draft",
        "status": "sample_selection_confirmed",
        "purpose": "offline_setup_smoke_not_benchmark",
        "source_snapshot": SNAPSHOT,
        "source_path": SOURCE_PATH,
        "source_commit": commit,
        "source_sha256": SOURCE_HASH,
        "source_count": 200,
        "selection_recipe": RECIPE,
        "asset_count": count,
        "asset_ids": [row["asset_id"] for row in selected],
        "sample_sha256": sha256(assets),
        "attribution_sha256": sha256(attribution),
        "generator_sha256": sha256(Path(__file__).read_bytes()),
        "metadata_policy": "original_source_records_no_normalization",
        "serialization": {
            "encoding": "UTF-8", "bom": False, "newline": "LF",
            "final_newline": True, "sort_keys": True, "indent": 2,
        },
        "previews": "not_downloaded_or_verified",
        "database": "not_written",
        "index": "not_built",
        "compatibility": "Not a replacement for frozen candidate200/config W6.",
    })
    files = {"assets.json": assets, "attribution.json": attribution,
             "provenance.json": provenance}
    files["CHECKSUMS.sha256"] = "".join(
        f"{sha256(content)}  {name}\n"
        for name, content in sorted(files.items())
    ).encode("ascii")

    # All source/serialization validation happens before creating output.
    # Existing outputs are refused; partial I/O failure is never reported passed.
    output.mkdir(parents=True, exist_ok=False)
    for name, content in files.items():
        with (output / name).open("xb") as destination:
            destination.write(content)
    return {
        "status": "offline_sample_generated",
        "sample_selection_status": "sample_selection_confirmed",
        "asset_count": count,
        "sample_sha256": sha256(assets),
        "source_commit": commit,
        "output": str(output),
        "previews_verified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--source-ref", default="HEAD")
    args = parser.parse_args()
    try:
        result = prepare_sample(args.repo, args.output, args.count, args.source_ref)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
