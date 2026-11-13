"""Build a draft E5 metadata corpus from the locked 200-asset manifest."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

SOURCE_PATH = "data/manifests/objaverse_200.json"
EXPECTED_SOURCE_SHA256 = (
    "9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd"
)
RECIPE_VERSION = "e5-metadata-passage-v1-draft"


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
    ).stdout


def clean_text(value, field):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string or null")
    return " ".join(value.split())


def make_passage(asset):
    tags = asset.get("tags")
    if tags is None:
        tags = []
    if not isinstance(tags, list):
        raise ValueError("tags must be a list or null")

    cleaned_tags = []
    seen = set()
    for tag in tags:
        if not isinstance(tag, str):
            raise ValueError("Each tag must be a string")
        cleaned = clean_text(tag, "tag")
        if cleaned and cleaned not in seen:
            cleaned_tags.append(cleaned)
            seen.add(cleaned)

    parts = [
        clean_text(asset.get("name"), "name"),
        clean_text(asset.get("description"), "description"),
        ", ".join(cleaned_tags),
        clean_text(asset.get("category"), "category"),
    ]
    return "\n".join(part for part in parts if part)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()

    # Git blob gives canonical bytes, independent of checkout CRLF.
    source_bytes = git(repo, "show", f"HEAD:{SOURCE_PATH}")
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if source_sha256 != EXPECTED_SOURCE_SHA256:
        raise ValueError(f"Unexpected source manifest hash: {source_sha256}")

    records = json.loads(source_bytes.decode("utf-8-sig"))
    checkout_bytes = (repo / SOURCE_PATH).read_bytes()
    checkout_records = json.loads(checkout_bytes.decode("utf-8-sig"))
    if checkout_records != records:
        raise ValueError("Checkout metadata differs from the committed source")

    if not isinstance(records, list) or len(records) != 200:
        raise ValueError("Expected exactly 200 source records")

    corpus = []
    seen_ids = set()
    for asset in records:
        if not isinstance(asset, dict):
            raise ValueError("Each source record must be an object")

        asset_id = asset.get("asset_id")
        if (
            not isinstance(asset_id, str)
            or not asset_id.strip()
            or asset_id != asset_id.strip()
        ):
            raise ValueError("Invalid asset_id")
        if asset_id in seen_ids:
            raise ValueError(f"Duplicate asset_id: {asset_id}")
        seen_ids.add(asset_id)

        try:
            passage = make_passage(asset)
        except ValueError as error:
            raise ValueError(f"{asset_id}: {error}") from error
        if not passage:
            raise ValueError(f"Empty passage: {asset_id}")

        corpus.append({"asset_id": asset_id, "passage": passage})

    corpus.sort(key=lambda row: row["asset_id"])
    corpus_bytes = (
        "\n".join(
            json.dumps(
                row,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            for row in corpus
        )
        + "\n"
    ).encode("utf-8")

    manifest = {
        "status": "draft_recipe_pending_confirmation",
        "snapshot": "home-interior-clear-200-v3",
        "source_path": SOURCE_PATH,
        "source_commit": git(repo, "rev-parse", "HEAD").decode().strip(),
        "source_manifest_sha256": source_sha256,
        "source_hash_basis": "raw Git blob bytes",
        "checkout_manifest_sha256": hashlib.sha256(checkout_bytes).hexdigest(),
        "checkout_matches_source_json": True,
        "recipe_version": RECIPE_VERSION,
        "fields": ["name", "description", "tags", "category"],
        "text_policy": "Python str.split then join with one ASCII space",
        "tags_policy": "clean; drop empty; exact dedup; preserve first order",
        "tags_separator": ", ",
        "field_separator": "\n",
        "empty_policy": "omit empty fields; reject empty passage",
        "prefix_in_corpus": False,
        "serialization": {
            "format": "JSONL",
            "encoding": "UTF-8 without BOM",
            "record_order": "asset_id ascending",
            "json_sort_keys": True,
            "json_ensure_ascii": False,
            "json_separators": [",", ":"],
            "record_newline": "LF",
            "final_newline": True,
        },
        "asset_count": len(corpus),
        "nonempty_passage_count": len(corpus),
        "asset_ids": [row["asset_id"] for row in corpus],
        "corpus_file": "corpus.jsonl",
        "corpus_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
        "errors": [],
    }

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "corpus.jsonl").write_bytes(corpus_bytes)
    (args.output / "manifest.json").write_bytes(
        (
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n"
        ).encode("utf-8")
    )

    print(f"Asset count: {len(corpus)}")
    print(f"Nonempty passages: {len(corpus)}")
    print(f"Corpus SHA-256: {manifest['corpus_sha256']}")
    print(f"Output: {args.output}")
    print(f"Status: {manifest['status']}")


if __name__ == "__main__":
    main()