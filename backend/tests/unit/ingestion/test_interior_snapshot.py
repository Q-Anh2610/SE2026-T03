"""Kiểm tra snapshot mở rộng bằng metadata đã commit, không gọi mạng/DB."""

import hashlib
import json
from pathlib import Path, PurePosixPath

from backend.app.ingestion.objaverse import annotation_to_asset
from backend.app.ingestion.source_adapter import SourceAdapter


REPO = Path(__file__).resolve().parents[4]
SNAPSHOT = REPO / "data/manifests/home-interior-354-v1"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_snapshot():
    records = read_json(SNAPSHOT / "assets_354.json")
    annotations = read_json(SNAPSHOT / "assets_354.annotations.json")
    provenance = read_json(SNAPSHOT / "assets_354.provenance.json")
    curation = read_json(SNAPSHOT / "assets_354.curation.json")
    return records, annotations, provenance, curation


def test_snapshot_metadata_matches_source_and_passes_validation():
    records, annotations, _, _ = load_snapshot()

    assert len(records) == len(annotations) == 354
    assert set(annotations) == {item["source_id"] for item in records}
    assert records == [
        annotation_to_asset(annotations[item["source_id"]])
        for item in records
    ]

    adapter = SourceAdapter(SNAPSHOT / "assets_354.json")
    valid, invalid = adapter.normalize_and_validate(records)

    assert not invalid, invalid
    assert len(valid) == 354


def test_snapshot_preserves_baseline_and_adds_154_unique_assets():
    records, _, provenance, _ = load_snapshot()
    baseline = read_json(REPO / "data/manifests/objaverse_200.json")

    by_id = {item["asset_id"]: item for item in records}
    baseline_ids = {item["asset_id"] for item in baseline}
    source_pairs = {
        (item["source"], item["source_id"]) for item in records
    }

    assert len(baseline) == len(baseline_ids) == 200
    assert len(records) == len(by_id) == len(source_pairs) == 354
    assert baseline_ids <= set(by_id)
    assert len(set(by_id) - baseline_ids) == 154

    for item in baseline:
        assert by_id[item["asset_id"]] == item

    parents = {item["snapshot"]: item for item in provenance["parents"]}
    assert parents["home-interior-clear-200-v3"]["count"] == 200
    assert parents["interior-additions-reviewed-v3"]["count"] == 154


def test_snapshot_checksums_and_preview_evidence_are_consistent():
    records, _, provenance, _ = load_snapshot()

    for name, key in [
        ("assets_354.json", "manifest_sha256"),
        ("assets_354.annotations.json", "annotations_sha256"),
    ]:
        digest = hashlib.sha256((SNAPSHOT / name).read_bytes()).hexdigest()
        assert digest == provenance[key]

    assert provenance["snapshot"] == "home-interior-354-v1"
    assert provenance["count"] == 354

    rows = provenance["previews"]
    previews = {item["asset_id"]: item for item in rows}
    assert len(rows) == len(previews) == 354
    assert set(previews) == {item["asset_id"] for item in records}
    assert len({item["sha256"] for item in rows}) == 354

    for record in records:
        preview = previews[record["asset_id"]]
        assert preview["url"] == record["thumbnail_path"]
        assert preview["bytes"] > 0
        assert len(preview["dimensions"]) == 2
        assert all(value > 0 for value in preview["dimensions"])
        assert len(preview["sha256"]) == 64
        int(preview["sha256"], 16)


def test_curation_matches_previews_and_uses_portable_paths():
    records, _, provenance, curation = load_snapshot()

    previews = {
        item["asset_id"]: item for item in provenance["previews"]
    }
    reviews = {item["asset_id"]: item for item in curation["assets"]}

    assert curation["snapshot"] == "home-interior-354-v1"
    assert len(curation["assets"]) == len(reviews) == 354
    assert set(reviews) == {item["asset_id"] for item in records}

    for asset_id, review in reviews.items():
        preview = previews[asset_id]
        assert review["decision"] == "keep"
        assert review["reviewed_category_vi"]
        assert review["preview_sha256"] == preview["sha256"]
        assert review["preview_local_path"] == preview["preview_local_path"]

        path = PurePosixPath(review["preview_local_path"])
        assert not path.is_absolute()
        assert ".." not in path.parts
        assert path.parts[0] == "previews"
        assert "\\" not in review["preview_local_path"]
        assert ":" not in review["preview_local_path"]