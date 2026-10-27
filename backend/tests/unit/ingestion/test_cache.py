"""Kiểm tra tái sử dụng preview local, không truy cập Internet."""

import hashlib
from io import BytesIO

import pytest
from PIL import Image

from backend.app.ingestion.cache import reusable_preview


PREVIEW_URL = "https://media.sketchfab.com/models/test/preview.png"


def create_cached_preview(tmp_path):
    buffer = BytesIO()
    Image.new("RGB", (16, 12), color="blue").save(
        buffer, format="PNG"
    )
    content = buffer.getvalue()

    path = tmp_path / "preview.png"
    path.write_bytes(content)

    previous = {
        "status": "downloaded",
        "preview_source_url": PREVIEW_URL,
        "preview_local_path": path.as_posix(),
        "checksum": hashlib.sha256(content).hexdigest(),
        "checksum_resource": "preview",
    }

    return path, previous


@pytest.mark.parametrize("status", ["downloaded", "skipped"])
def test_valid_preview_can_be_reused(tmp_path, status):
    path, previous = create_cached_preview(tmp_path)
    previous["status"] = status

    result = reusable_preview(previous, PREVIEW_URL, tmp_path)

    assert result is not None
    assert result["attempts"] == 0
    assert result["checksum"] == previous["checksum"]
    assert result["preview_local_path"] == path.as_posix()
    assert result["width"] == 16
    assert result["height"] == 12


def test_missing_file_requires_download(tmp_path):
    path, previous = create_cached_preview(tmp_path)
    path.unlink()

    assert reusable_preview(previous, PREVIEW_URL, tmp_path) is None


def test_modified_file_requires_download(tmp_path):
    path, previous = create_cached_preview(tmp_path)

    # File vẫn là ảnh hợp lệ nhưng nội dung đã thay đổi.
    Image.new("RGB", (16, 12), color="red").save(
        path, format="PNG"
    )

    assert reusable_preview(previous, PREVIEW_URL, tmp_path) is None


def test_broken_image_is_rejected_even_if_checksum_matches(tmp_path):
    path, previous = create_cached_preview(tmp_path)
    content = b"not an image"
    path.write_bytes(content)
    previous["checksum"] = hashlib.sha256(content).hexdigest()

    assert reusable_preview(previous, PREVIEW_URL, tmp_path) is None


def test_changed_source_url_requires_download(tmp_path):
    _, previous = create_cached_preview(tmp_path)

    assert reusable_preview(
        previous,
        "https://media.sketchfab.com/models/test/new-preview.png",
        tmp_path,
    ) is None


def test_file_outside_output_directory_is_not_reused(tmp_path):
    _, previous = create_cached_preview(tmp_path)
    different_directory = tmp_path / "other"

    assert reusable_preview(
        previous, PREVIEW_URL, different_directory
    ) is None