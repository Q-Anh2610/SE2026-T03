"""Tải preview Objaverse, kiểm tra ảnh và tính SHA-256."""
import time
from urllib.error import HTTPError, URLError
import hashlib
import warnings
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

from PIL import Image


MAX_BYTES = 2 * 1024 * 1024
MAX_DIMENSION = 4096
ALLOWED_HOST = "media.sketchfab.com"


def validate_preview_url(url: str) -> None:
    """Chỉ chấp nhận URL HTTPS từ nguồn preview đã chọn."""
    parsed = urlsplit(url)

    if (
        parsed.scheme != "https"
        or parsed.hostname != ALLOWED_HOST
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
    ):
        raise ValueError("URL preview không thuộc nguồn được phép.")


def download_preview(url: str, output_dir: str | Path) -> dict:
    """Tải một ảnh; chỉ lưu file sau khi nội dung đã được kiểm tra."""
    validate_preview_url(url)

    with urlopen(url, timeout=15) as response:
        validate_preview_url(response.geturl())
        content = response.read(MAX_BYTES + 1)

    if not content:
        raise ValueError("Preview không có nội dung.")

    if len(content) > MAX_BYTES:
        raise ValueError("Preview vượt giới hạn 2 MiB.")

    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)

        with Image.open(BytesIO(content)) as image:
            image_format = image.format
            width, height = image.size

            if image_format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("Định dạng preview không được hỗ trợ.")

            if max(width, height) > MAX_DIMENSION:
                raise ValueError("Preview vượt giới hạn 4096 px mỗi chiều.")

            image.verify()

        # Mở lại để xác nhận toàn bộ ảnh decode được.
        with Image.open(BytesIO(content)) as image:
            image.load()

    checksum = hashlib.sha256(content).hexdigest()
    extension = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[image_format]

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{checksum}{extension}"

    # Ghi file tạm trước để hạn chế để lại file cuối bị ghi dở.
    temporary = destination.with_suffix(destination.suffix + ".part")

    try:
        temporary.write_bytes(content)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)

    return {
        "preview_source_url": url,
        "preview_local_path": destination.as_posix(),
        "checksum": checksum,
        "checksum_resource": "preview",
        "bytes": len(content),
        "width": width,
        "height": height,
    }

class PreviewDownloadError(Exception):
    """Lưu số lần thử và nguyên nhân cuối khi tải thất bại."""

    def __init__(self, attempts: int, last_error: Exception):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"Tải preview thất bại sau {attempts} lần thử: "
            f"{type(last_error).__name__}: {last_error}"
        )


def download_preview_with_retry(
    url: str,
    output_dir: str | Path,
    *,
    max_attempts: int = 3,
    retry_delay: float = 1.0,
) -> dict:
    """Thử lại lỗi tải tạm thời; max_attempts bao gồm lần đầu."""
    if type(max_attempts) is not int or max_attempts < 1:
        raise ValueError("max_attempts phải là số nguyên dương.")

    if retry_delay < 0:
        raise ValueError("retry_delay không được âm.")

    for attempt in range(1, max_attempts + 1):
        try:
            result = download_preview(url, output_dir)
            return {**result, "attempts": attempt}

        except Exception as exc:
            if isinstance(exc, HTTPError):
                retryable = exc.code in {
                    408, 429, 500, 502, 503, 504
                }
            else:
                retryable = isinstance(
                    exc,
                    (URLError, TimeoutError, ConnectionError),
                )

            if not retryable or attempt == max_attempts:
                raise PreviewDownloadError(attempt, exc) from exc

            time.sleep(retry_delay * attempt)