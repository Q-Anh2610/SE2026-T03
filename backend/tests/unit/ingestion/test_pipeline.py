"""Tests pipeline dùng manifest tạm và downloader giả, không gọi mạng."""

import hashlib
import json

from io import BytesIO
from pathlib import Path

from PIL import Image
from urllib.error import URLError

from backend.app.ingestion import pipeline
from backend.app.ingestion.downloader import PreviewDownloadError


def make_asset(number):
    """Tạo metadata hợp lệ theo Source Adapter."""
    uid = f"{number:032x}"

    return {
        "asset_id": f"objaverse_{uid}",
        "source": "objaverse",
        "source_id": uid,
        "source_url": f"https://sketchfab.com/3d-models/{uid}",
        "name": f"Fixture chair {number}",
        "license": "by",
        "thumbnail_path": (
            f"https://media.sketchfab.com/models/{uid}/preview.png"
        ),
    }


def write_manifest(tmp_path, records):
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(records, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def fake_success(url, output_dir, *, max_attempts):
    return {
        "preview_source_url": url,
        "preview_local_path": "fixture/preview.png",
        "checksum": "a" * 64,
        "checksum_resource": "preview",
        "bytes": 100,
        "width": 16,
        "height": 12,
        "attempts": 1,
    }


def test_successful_batch_writes_report_and_keeps_manifest(
    tmp_path, monkeypatch
):
    manifest = write_manifest(
        tmp_path,
        [make_asset(1), make_asset(2)],
    )
    original_content = manifest.read_bytes()
    report_path = tmp_path / "reports" / "run.json"

    monkeypatch.setattr(
        pipeline, "download_preview_with_retry", fake_success
    )

    report = pipeline.run_batch(
        manifest,
        tmp_path / "previews",
        report_path,
    )

    assert report["summary"] == {
        "input_count": 2,
        "succeeded": 2,
        "failed": 0,
        "skipped": 0,
    }
    assert manifest.read_bytes() == original_content
    assert report["manifest_sha256"] == hashlib.sha256(
        original_content
    ).hexdigest()
    assert report["persistence"] == "local_files_only"
    assert all(
        item["status"] == "downloaded"
        for item in report["results"]
    )

    saved_report = json.loads(
        report_path.read_text(encoding="utf-8")
    )
    assert saved_report == report


def test_failed_asset_does_not_stop_remaining_assets(
    tmp_path, monkeypatch
):
    assets = [make_asset(1), make_asset(2), make_asset(3)]
    manifest = write_manifest(tmp_path, assets)
    calls = []

    def fake_download(url, output_dir, *, max_attempts):
        calls.append(url)

        if url == assets[1]["thumbnail_path"]:
            raise PreviewDownloadError(
                3,
                URLError("Temporary connection failure"),
            )

        return fake_success(
            url, output_dir, max_attempts=max_attempts
        )

    monkeypatch.setattr(
        pipeline, "download_preview_with_retry", fake_download
    )

    report = pipeline.run_batch(
        manifest,
        tmp_path / "previews",
        tmp_path / "report.json",
    )

    assert len(calls) == 3
    assert report["summary"] == {
        "input_count": 3,
        "succeeded": 2,
        "failed": 1,
        "skipped": 0,
    }

    by_id = {
        item["asset_id"]: item
        for item in report["results"]
    }
    failed = by_id[assets[1]["asset_id"]]

    assert failed["status"] == "failed"
    assert failed["attempts"] == 3
    assert failed["error_type"] == "URLError"
    assert "Temporary connection failure" in failed["error_message"]
    assert by_id[assets[2]["asset_id"]]["status"] == "downloaded"


def test_invalid_metadata_is_reported_without_download(
    tmp_path, monkeypatch
):
    invalid = make_asset(1)
    invalid["license"] = None
    valid = make_asset(2)
    manifest = write_manifest(tmp_path, [invalid, valid])
    calls = []

    def fake_download(url, output_dir, *, max_attempts):
        calls.append(url)
        return fake_success(
            url, output_dir, max_attempts=max_attempts
        )

    monkeypatch.setattr(
        pipeline, "download_preview_with_retry", fake_download
    )

    report = pipeline.run_batch(
        manifest,
        tmp_path / "previews",
        tmp_path / "report.json",
    )

    assert calls == [valid["thumbnail_path"]]
    assert report["summary"]["succeeded"] == 1
    assert report["summary"]["failed"] == 1

    failed = next(
        item for item in report["results"]
        if item["status"] == "failed"
    )
    assert failed["stage"] == "validation"
    assert failed["attempts"] == 0
    assert "license" in failed["error_message"]


def test_duplicate_id_is_not_downloaded_twice(tmp_path, monkeypatch):
    asset = make_asset(1)
    manifest = write_manifest(tmp_path, [asset, dict(asset)])
    calls = []

    def fake_download(url, output_dir, *, max_attempts):
        calls.append(url)
        return fake_success(
            url, output_dir, max_attempts=max_attempts
        )

    monkeypatch.setattr(
        pipeline, "download_preview_with_retry", fake_download
    )

    report = pipeline.run_batch(
        manifest,
        tmp_path / "previews",
        tmp_path / "report.json",
    )

    assert len(calls) == 1
    assert report["summary"] == {
        "input_count": 2,
        "succeeded": 1,
        "failed": 1,
        "skipped": 0,
    }


def test_limit_only_processes_selected_records(tmp_path, monkeypatch):
    manifest = write_manifest(
        tmp_path,
        [make_asset(1), make_asset(2), make_asset(3)],
    )
    calls = []

    def fake_download(url, output_dir, *, max_attempts):
        calls.append(url)
        return fake_success(
            url, output_dir, max_attempts=max_attempts
        )

    monkeypatch.setattr(
        pipeline, "download_preview_with_retry", fake_download
    )

    report = pipeline.run_batch(
        manifest,
        tmp_path / "previews",
        tmp_path / "report.json",
        limit=2,
    )

    assert len(calls) == 2
    assert report["summary"]["input_count"] == 2
    assert report["summary"]["succeeded"] == 2

def test_rerun_reuses_preview_without_downloading(
    tmp_path, monkeypatch
):
    manifest = write_manifest(tmp_path, [make_asset(1)])
    output_dir = tmp_path / "previews"

    def fake_download(url, output_dir, *, max_attempts):
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)

        buffer = BytesIO()
        Image.new("RGB", (16, 12), color="blue").save(
            buffer, format="PNG"
        )
        content = buffer.getvalue()
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

    monkeypatch.setattr(
        pipeline, "download_preview_with_retry", fake_download
    )

    first_report = tmp_path / "first.json"

    pipeline.run_batch(
        manifest,
        output_dir,
        first_report,
    )

    def unexpected_download(*args, **kwargs):
        raise AssertionError(
            "Không được tải lại preview đã kiểm tra hợp lệ."
        )

    monkeypatch.setattr(
        pipeline,
        "download_preview_with_retry",
        unexpected_download,
    )

    report = pipeline.run_batch(
        manifest,
        output_dir,
        tmp_path / "second.json",
        previous_report_path=first_report,
    )

    assert report["summary"] == {
        "input_count": 1,
        "succeeded": 0,
        "failed": 0,
        "skipped": 1,
    }
    assert report["results"][0]["attempts"] == 0
    assert len(list(output_dir.iterdir())) == 1