"""Kiểm tra batch chứa preview lỗi, không gọi mạng hoặc database."""

import json
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from backend.app.ingestion import downloader, pipeline


@pytest.mark.parametrize(
    "invalid_content",
    [
        b"",
        b"<html>Service unavailable</html>",
        b"not an image",
    ],
    ids=["empty", "html", "broken-image"],
)
def test_invalid_preview_does_not_stop_batch(
    tmp_path, monkeypatch, invalid_content
):
    assets = []
    for number in [1, 2, 3]:
        uid = f"{number:032x}"
        assets.append({
            "asset_id": f"objaverse_{uid}",
            "source": "objaverse",
            "source_id": uid,
            "source_url": f"https://sketchfab.com/3d-models/{uid}",
            "name": f"Fixture chair {number}",
            "license": "by",
            "thumbnail_path": (
                f"https://media.sketchfab.com/models/{uid}/preview.png"
            ),
        })

    buffer = BytesIO()
    Image.new("RGB", (16, 12), color="blue").save(
        buffer, format="PNG"
    )
    valid_content = buffer.getvalue()
    invalid_url = assets[1]["thumbnail_path"]
    calls = []

    class FakeResponse(BytesIO):
        def __init__(self, content, url):
            super().__init__(content)
            self.url = url

        def geturl(self):
            return self.url

    def fake_urlopen(url, timeout):
        calls.append(url)
        content = (
            invalid_content if url == invalid_url else valid_content
        )
        return FakeResponse(content, url)

    monkeypatch.setattr(downloader, "urlopen", fake_urlopen)

    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(assets), encoding="utf-8")
    original_manifest = manifest.read_bytes()
    output_dir = tmp_path / "previews"
    report_path = tmp_path / "report.json"

    report = pipeline.run_batch(
        manifest, output_dir, report_path
    )

    assert calls == [asset["thumbnail_path"] for asset in assets]
    assert report["summary"] == {
        "input_count": 3,
        "succeeded": 2,
        "failed": 1,
        "skipped": 0,
    }

    by_id = {
        item["asset_id"]: item for item in report["results"]
    }
    failed = by_id[assets[1]["asset_id"]]
    assert failed["status"] == "failed"
    assert failed["attempts"] == 1
    assert failed["error_type"]
    assert failed["error_message"]

    for asset in [assets[0], assets[2]]:
        result = by_id[asset["asset_id"]]
        assert result["status"] == "downloaded"
        assert Path(result["preview_local_path"]).read_bytes() == valid_content

    assert not list(output_dir.glob("*.part"))
    assert manifest.read_bytes() == original_manifest
    assert json.loads(report_path.read_text(encoding="utf-8")) == report