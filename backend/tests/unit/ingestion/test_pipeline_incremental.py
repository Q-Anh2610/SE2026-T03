"""Incremental pipeline fixtures; no network or real database."""

import copy
import hashlib
import json
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from backend.app.ingestion import pipeline


@pytest.fixture
def cached_batch(tmp_path, monkeypatch):
    assets = []
    contents = {}

    for number, color in [(1, "blue"), (2, "green")]:
        uid = f"{number:032x}"
        url = f"https://media.sketchfab.com/models/{uid}/preview.png"
        assets.append({
            "asset_id": f"objaverse_{uid}",
            "source": "objaverse",
            "source_id": uid,
            "source_url": f"https://sketchfab.com/3d-models/{uid}",
            "name": f"Fixture chair {number}",
            "license": "by",
            "thumbnail_path": url,
        })
        buffer = BytesIO()
        Image.new("RGB", (16, 12), color=color).save(buffer, format="PNG")
        contents[url] = buffer.getvalue()

    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(assets), encoding="utf-8")
    previews = tmp_path / "previews"

    def download(url, output_dir, *, max_attempts):
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        content = contents[url]
        checksum = hashlib.sha256(content).hexdigest()
        path = directory / f"{checksum}.png"
        path.write_bytes(content)
        return {
            "preview_source_url": url,
            "preview_local_path": path.as_posix(),
            "checksum": checksum,
            "checksum_resource": "preview",
            "bytes": len(content),
            "width": 16,
            "height": 12,
            "attempts": 1,
        }

    monkeypatch.setattr(pipeline, "download_preview_with_retry", download)
    previous = tmp_path / "previous.json"
    first = pipeline.run_batch(manifest, previews, previous)
    assert first["summary"]["succeeded"] == 2

    original_previews = {
        path: path.read_bytes() for path in previews.iterdir()
    }
    original_report = previous.read_bytes()

    def unexpected_download(*args, **kwargs):
        pytest.fail("Valid cached previews must not be downloaded again.")

    monkeypatch.setattr(
        pipeline, "download_preview_with_retry", unexpected_download
    )

    return {
        "assets": assets,
        "manifest": manifest,
        "previews": previews,
        "previous": previous,
        "original_previews": original_previews,
        "original_report": original_report,
    }


def assert_cache_unchanged(batch):
    assert batch["previous"].read_bytes() == batch["original_report"]
    assert {
        path: path.read_bytes() for path in batch["previews"].iterdir()
    } == batch["original_previews"]


def test_cache_hit_passes_current_metadata_to_persistence(
    tmp_path, cached_batch
):
    batch = cached_batch
    changed = copy.deepcopy(batch["assets"])
    changed[0]["name"] = "Updated fixture chair"
    changed[0]["description"] = "Current metadata, same preview."
    changed[0]["tags"] = ["chair", "wood"]

    batch["manifest"].write_text(json.dumps(changed), encoding="utf-8")
    manifest_before = batch["manifest"].read_bytes()
    calls = []

    def persist(asset, preview):
        calls.append((copy.deepcopy(asset), copy.deepcopy(preview)))

    report_path = tmp_path / "metadata-update.json"
    report = pipeline.run_batch(
        batch["manifest"],
        batch["previews"],
        report_path,
        previous_report_path=batch["previous"],
        persist_asset=persist,
    )

    assert [asset["asset_id"] for asset, _ in calls] == [
        asset["asset_id"] for asset in changed
    ]
    assert calls[0][0]["name"] == changed[0]["name"]
    assert calls[0][0]["description"] == changed[0]["description"]
    assert calls[0][0]["tags"] == ["chair", "wood"]
    assert calls[1][0]["name"] == changed[1]["name"]
    assert all(preview["attempts"] == 0 for _, preview in calls)

    assert report["summary"] == {
        "input_count": 2,
        "succeeded": 0,
        "failed": 0,
        "skipped": 2,
    }
    assert all(
        row["database_status"] == "saved"
        and row["preview_status"] == "skipped"
        for row in report["results"]
    )
    assert json.loads(report_path.read_text(encoding="utf-8")) == report
    assert batch["manifest"].read_bytes() == manifest_before
    assert_cache_unchanged(batch)


def test_cache_hit_persistence_failure_is_reported_and_batch_continues(
    tmp_path, cached_batch
):
    batch = cached_batch
    attempted = []
    saved = []
    failed_id = batch["assets"][0]["asset_id"]
    manifest_before = batch["manifest"].read_bytes()

    def persist(asset, preview):
        attempted.append(asset["asset_id"])
        assert preview["attempts"] == 0
        if asset["asset_id"] == failed_id:
            raise pipeline.PersistenceError("Fixture persistence failure.")
        saved.append(asset["asset_id"])

    report_path = tmp_path / "persistence-failure.json"
    report = pipeline.run_batch(
        batch["manifest"],
        batch["previews"],
        report_path,
        previous_report_path=batch["previous"],
        persist_asset=persist,
    )

    assert attempted == [asset["asset_id"] for asset in batch["assets"]]
    assert saved == [batch["assets"][1]["asset_id"]]
    assert report["summary"] == {
        "input_count": 2,
        "succeeded": 0,
        "failed": 1,
        "skipped": 1,
    }

    by_id = {row["asset_id"]: row for row in report["results"]}
    failed = by_id[failed_id]
    assert failed["status"] == "failed"
    assert failed["stage"] == "persistence"
    assert failed["database_status"] == "failed"
    assert failed["preview_status"] == "skipped"
    assert failed["error_type"] == "PersistenceError"
    assert failed["error_message"] == "Fixture persistence failure."
    assert failed["attempts"] == 0
    assert failed["checksum_resource"] == "preview"
    assert Path(failed["preview_local_path"]).is_file()

    remaining = by_id[batch["assets"][1]["asset_id"]]
    assert remaining["status"] == "skipped"
    assert remaining["database_status"] == "saved"
    assert remaining["error_type"] is None

    assert json.loads(report_path.read_text(encoding="utf-8")) == report
    assert batch["manifest"].read_bytes() == manifest_before
    assert_cache_unchanged(batch)