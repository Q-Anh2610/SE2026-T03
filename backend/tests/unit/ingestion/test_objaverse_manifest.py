"""Regression tests offline cho mapping, provenance và CLI tạo subset."""

import gzip
import hashlib
from io import BytesIO
import json
from pathlib import Path
from urllib.error import HTTPError

from PIL import Image
import pytest

from backend.app.ingestion.objaverse import annotation_to_asset
from scripts.generate_objaverse_200 import main


def annotation(uid="a" * 32, **changes):
    return {
        "uid": uid, "name": "Wooden Chair", "license": "by",
        "viewerUrl": f"https://sketchfab.com/3d-models/{uid}",
        "tags": [{"name": "chair", "uri": "https://example.org/tags/chair"}],
        "categories": [{"name": "furniture-home"}],
        "user": {"displayName": "Fixture creator"},
        "thumbnails": {"images": [{"width": 720, "url": f"https://media.sketchfab.com/models/{uid}/preview.jpg"}]},
        "archives": {"glb": {"type": "glb"}, "source": {"type": "source"}},
        **changes,
    }


def test_mapping_uses_source_values_and_stable_ids():
    source = annotation()
    record = annotation_to_asset(source)
    assert record["asset_id"] == "objaverse_" + source["uid"]
    assert record["license"] == "by"
    assert record["face_count"] is None
    assert record["checksum"] is None  # preview hash nằm ở provenance, chưa phải checksum model
    assert record["formats"] == ["glb"]
    assert record["tags"] == ["chair"]
    assert record["model_path"] is None
    assert record["ingestion_status"] == "PENDING"


@pytest.mark.parametrize("changes", [{"uid": "fake"}, {"license": None}, {"license": "unknown"}, {"faceCount": -1}])
def test_mapping_rejects_invalid_source(changes):
    with pytest.raises(ValueError):
        annotation_to_asset(annotation(**changes))


def test_mapping_does_not_invent_missing_author_or_categories():
    record = annotation_to_asset(annotation(user=None, categories=[], thumbnails=None, archives=None))
    assert record["author"] is None
    assert record["category"] is None
    assert record["thumbnail_path"] is None
    assert record["formats"] == []


def fake_source(monkeypatch, *, broken_preview=False):
    item = annotation()
    compressed = gzip.compress(json.dumps({item["uid"]: item}).encode())
    image = BytesIO()
    Image.new("RGB", (8, 8)).save(image, format="PNG")

    class Response(BytesIO):
        def __init__(self, content, url):
            super().__init__(content)
            self.url = url

    def urlopen(url, timeout):
        if "huggingface.co" in url:
            return Response(compressed, url)
        if broken_preview:
            raise HTTPError(url, 404, "Not Found", {}, None)
        return Response(image.getvalue(), url)

    monkeypatch.setattr("urllib.request.urlopen", urlopen)


def test_cli_writes_manifest_raw_annotations_and_preview_provenance(tmp_path, monkeypatch):
    fake_source(monkeypatch)
    output = tmp_path / "subset.json"
    assert main(["--count", "1", "--output", str(output), "--cache-dir", str(tmp_path / "cache")]) == 0
    record = json.loads(output.read_text(encoding="utf-8"))[0]
    report = json.loads(output.with_suffix(".provenance.json").read_text(encoding="utf-8"))
    assert record["asset_id"] == report["previews"][0]["asset_id"]
    assert report["manifest_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert report["annotations_sha256"] == hashlib.sha256(output.with_suffix(".annotations.json").read_bytes()).hexdigest()
    assert report["previews"][0]["dimensions"] == [8, 8]
    assert report["count"] == 1


@pytest.mark.parametrize("broken_preview,count", [(True, "1"), (False, "2")])
def test_failed_or_insufficient_subset_keeps_existing_manifest(tmp_path, monkeypatch, broken_preview, count):
    fake_source(monkeypatch, broken_preview=broken_preview)
    output = tmp_path / "subset.json"
    output.write_text("existing", encoding="utf-8")
    assert main(["--count", count, "--output", str(output), "--cache-dir", str(tmp_path / "cache")]) == 1
    assert output.read_text(encoding="utf-8") == "existing"
    assert not output.with_suffix(".provenance.json").exists()


def test_committed_manifest_matches_raw_source_and_evidence():
    path = Path(__file__).resolve().parents[4] / "data/manifests/objaverse_200.json"
    records = json.loads(path.read_text(encoding="utf-8"))
    raw_path = path.with_suffix(".annotations.json")
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    report = json.loads(path.with_suffix(".provenance.json").read_text(encoding="utf-8"))
    assert len(records) == len(raw) == len(report["previews"]) == report["count"] == 200
    assert report["manifest_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert report["annotations_sha256"] == hashlib.sha256(raw_path.read_bytes()).hexdigest()
    assert records == [annotation_to_asset(raw[record["source_id"]]) for record in records]
    previews = {item["asset_id"]: item for item in report["previews"]}
    assert len(previews) == 200
    for record in records:
        assert record["thumbnail_path"] == previews[record["asset_id"]]["url"]
        assert previews[record["asset_id"]]["bytes"] > 0
        assert len(previews[record["asset_id"]]["sha256"]) == 64
