"""Kiểm tra preview local trước khi tái sử dụng."""

import hashlib
import warnings
from pathlib import Path

from PIL import Image

from .downloader import MAX_BYTES, MAX_DIMENSION


def reusable_preview(previous, source_url, output_dir):
    """Trả thông tin preview hợp lệ; trả None nếu cần tải lại."""
    if not isinstance(previous, dict):
        return None

    if previous.get("status") not in {"downloaded", "skipped"}:
        return None

    if previous.get("preview_source_url") != source_url:
        return None

    if previous.get("checksum_resource") != "preview":
        return None

    local_path = previous.get("preview_local_path")
    checksum = previous.get("checksum")

    if not isinstance(local_path, str) or not isinstance(checksum, str):
        return None

    try:
        path = Path(local_path)
        root = Path(output_dir).resolve()
        resolved = path.resolve()

        if not resolved.is_relative_to(root) or not resolved.is_file():
            return None

        if not 0 < resolved.stat().st_size <= MAX_BYTES:
            return None

        content = resolved.read_bytes()

        if len(content) > MAX_BYTES:
            return None

        if hashlib.sha256(content).hexdigest() != checksum:
            return None

        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            with Image.open(resolved) as image:
                width, height = image.size

                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    return None

                if max(width, height) > MAX_DIMENSION:
                    return None

                image.verify()

            with Image.open(resolved) as image:
                image.load()

        return {
            "preview_source_url": source_url,
            "preview_local_path": path.as_posix(),
            "checksum": checksum,
            "checksum_resource": "preview",
            "bytes": len(content),
            "width": width,
            "height": height,
            "attempts": 0,
        }

    except (OSError, ValueError, Image.DecompressionBombWarning):
        return None