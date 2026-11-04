"""Kiểm tra pipeline phục hồi cache, không gọi mạng hoặc database."""

import hashlib
import json
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from backend.app.ingestion import downloader, pipeline


@pytest.mark.parametrize("damage", ["missing", "modified", "broken"])
def test_rerun_recovers_only_invalid_cached_preview(
    tmp_path, monkeypatch, damage
):
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
        Image.new("RGB", (16, 12), color=color).save(
            buffer, format="PNG"
        )
        contents[url] = buffer.getvalue()

    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(assets), encoding="utf-8")
    original_manifest = manifest.read_bytes()
    calls = []

    class FakeResponse(BytesIO):
        def __init__(self, content, url):
            super().__init__(content)
            self.url = url

        def geturl(self):
            return self.url

    def fake_urlopen(url, timeout):
        calls.append(url)
        return FakeResponse(contents[url], url)

    monkeypatch.setattr(downloader, "urlopen", fake_urlopen)

    output_dir = tmp_path / "previews"
    first_report_path = tmp_path / "first.json"
    first = pipeline.run_batch(
        manifest, output_dir, first_report_path
    )
    assert first["summary"]["succeeded"] == 2

    by_id = {
        item["asset_id"]: item for item in first["results"]
    }
    damaged_path = Path(
        by_id[assets[0]["asset_id"]]["preview_local_path"]
    )
    healthy_path = Path(
        by_id[assets[1]["asset_id"]]["preview_local_path"]
    )
    healthy_content = healthy_path.read_bytes()

    if damage == "missing":
        damaged_path.unlink()
    elif damage == "modified":
        Image.new("RGB", (16, 12), color="red").save(
            damaged_path, format="PNG"
        )
    else:
        damaged_path.write_bytes(b"not an image")

    calls.clear()
    second = pipeline.run_batch(
        manifest,
        output_dir,
        tmp_path / "second.json",
        previous_report_path=first_report_path,
    )

    assert calls == [assets[0]["thumbnail_path"]]
    assert second["summary"] == {
        "input_count": 2,
        "succeeded": 1,
        "failed": 0,
        "skipped": 1,
    }
    assert healthy_path.read_bytes() == healthy_content
    assert manifest.read_bytes() == original_manifest

    for result in second["results"]:
        content = Path(result["preview_local_path"]).read_bytes()
        expected = contents[result["preview_source_url"]]
        assert content == expected
        assert result["checksum"] == hashlib.sha256(content).hexdigest()