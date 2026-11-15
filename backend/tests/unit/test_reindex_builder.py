"""Cache adapter của runner #117; encoder/store kiểm bằng tests integration/smoke riêng."""

from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import prepare_text_search_index as builder


def inputs(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    image = cache / "preview.png"
    image.write_bytes(b"fixture-bytes-only-cache-copy-test")
    asset = {"asset_id": "a", "source": "fixture", "source_id": "a", "name": "Chair",
        "source_url": "https://example.org/a", "license": "CC0", "thumbnail_path": "https://media.sketchfab.com/a.png"}
    manifest = tmp_path / "source.json"
    manifest.write_text(json.dumps([asset]), encoding="utf-8")
    ready = cache / "ready.json"
    row = {"metadata": asset, "image_path": "preview.png", "checksum": sha256(image.read_bytes()).hexdigest()}
    ready.write_text(json.dumps([row]), encoding="utf-8")
    args = SimpleNamespace(manifest=manifest, output_dir=tmp_path / "new-output", cache_ready=ready)
    return args, row


def test_cached_preview_keeps_target_metadata_and_does_not_download(monkeypatch, tmp_path):
    args, row = inputs(tmp_path)
    captured = []
    monkeypatch.setattr(builder, "embed_index", lambda *values: captured.append(values) or 0)
    import app.ingestion.downloader as downloader
    monkeypatch.setattr(downloader, "download_preview_with_retry", lambda *_a, **_k: pytest.fail("No download"))
    assert builder.build_index(args) == 0
    assert (args.output_dir / "source.json").read_bytes() == args.manifest.read_bytes()
    ready = json.loads((args.output_dir / "ready.json").read_text(encoding="utf-8"))
    assert ready[0]["metadata"]["name"] == "Chair"
    assert ready[0]["checksum"] == row["checksum"] and len(captured) == 1
    with pytest.raises(FileExistsError):
        builder.build_index(args)


@pytest.mark.parametrize("bad", ["checksum", "url", "path", "duplicate", "missing"])
def test_bad_cache_is_rejected_before_embedding(monkeypatch, tmp_path, bad):
    args, row = inputs(tmp_path)
    if bad == "checksum": row["checksum"] = "0" * 64
    if bad == "url": row["metadata"] = {**row["metadata"], "thumbnail_path": "https://other.example/a.png"}
    if bad == "path": row["image_path"] = "../outside.png"
    args.cache_ready.write_text(json.dumps([] if bad == "missing" else [row, row] if bad == "duplicate" else [row]), encoding="utf-8")
    monkeypatch.setattr(builder, "embed_index", lambda *_: pytest.fail("Invalid cache must not embed"))
    with pytest.raises((ValueError, KeyError)):
        builder.build_index(args)


def test_existing_download_flow_still_uses_same_builder(monkeypatch, tmp_path):
    args, _ = inputs(tmp_path)
    args.cache_ready = None
    downloaded = []
    def download(url, output, **_):
        target = output / "fixture.png"
        target.write_bytes(b"fixture-download-path")
        downloaded.append(url)
        return {"preview_local_path": str(target), "checksum": sha256(target.read_bytes()).hexdigest()}
    import app.ingestion.downloader as downloader
    monkeypatch.setattr(downloader, "download_preview_with_retry", download)
    monkeypatch.setattr(builder, "embed_index", lambda *_: 0)
    assert builder.build_index(args) == 0
    assert len(downloaded) == 1
    assert len(json.loads((args.output_dir / "ready.json").read_text(encoding="utf-8"))) == 1
