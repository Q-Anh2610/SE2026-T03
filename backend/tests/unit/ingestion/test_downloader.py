"""Kiểm thử downloader bằng ảnh tự tạo, không truy cập Internet."""

import hashlib
from io import BytesIO
from urllib.error import URLError
from urllib.error import HTTPError

import pytest
from PIL import Image

from backend.app.ingestion import downloader


PREVIEW_URL = "https://media.sketchfab.com/models/test/preview.png"


def make_image_bytes():
    """Tạo ảnh PNG nhỏ để kiểm thử."""
    buffer = BytesIO()
    Image.new("RGB", (16, 12), color="blue").save(buffer, format="PNG")
    return buffer.getvalue()


def mock_download(monkeypatch, content):
    """Thay kết nối mạng bằng dữ liệu trong bộ nhớ."""
    class FakeResponse(BytesIO):
        def geturl(self):
            return PREVIEW_URL

    def fake_urlopen(url, timeout):
        assert url == PREVIEW_URL
        assert timeout == 15
        return FakeResponse(content)

    monkeypatch.setattr(downloader, "urlopen", fake_urlopen)


def test_download_saves_valid_image_and_matching_checksum(tmp_path, monkeypatch):
    content = make_image_bytes()
    mock_download(monkeypatch, content)

    result = downloader.download_preview(PREVIEW_URL, tmp_path)

    expected_checksum = hashlib.sha256(content).hexdigest()
    saved_file = tmp_path / f"{expected_checksum}.png"

    assert saved_file.read_bytes() == content
    assert result["checksum"] == expected_checksum
    assert result["checksum_resource"] == "preview"
    assert result["preview_source_url"] == PREVIEW_URL
    assert result["preview_local_path"] == saved_file.as_posix()
    assert result["bytes"] == len(content)
    assert result["width"] == 16
    assert result["height"] == 12

    with Image.open(saved_file) as image:
        image.load()
        assert image.size == (16, 12)


def test_broken_image_is_not_saved(tmp_path, monkeypatch):
    mock_download(monkeypatch, b"this is not an image")

    with pytest.raises(OSError):
        downloader.download_preview(PREVIEW_URL, tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_oversized_download_is_not_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "MAX_BYTES", 10)
    mock_download(monkeypatch, b"x" * 11)

    with pytest.raises(ValueError, match="2 MiB"):
        downloader.download_preview(PREVIEW_URL, tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_untrusted_url_is_rejected_before_network(tmp_path, monkeypatch):
    def unexpected_network_call(*args, **kwargs):
        pytest.fail("URL không hợp lệ không được gọi mạng.")

    monkeypatch.setattr(downloader, "urlopen", unexpected_network_call)

    with pytest.raises(ValueError, match="nguồn"):
        downloader.download_preview(
            "https://example.com/preview.png",
            tmp_path,
        )

    assert list(tmp_path.iterdir()) == []


def test_network_failure_is_reported_without_saving(tmp_path, monkeypatch):
    def failing_urlopen(url, timeout):
        raise URLError("Temporary connection failure")

    monkeypatch.setattr(downloader, "urlopen", failing_urlopen)

    with pytest.raises(URLError):
        downloader.download_preview(PREVIEW_URL, tmp_path)

    assert list(tmp_path.iterdir()) == []

def test_retry_succeeds_after_temporary_failure(tmp_path, monkeypatch):
    calls = []
    waits = []

    def fake_download(url, output_dir):
        calls.append(url)
        if len(calls) == 1:
            raise URLError("Temporary failure")
        return {"checksum": "test-checksum"}

    monkeypatch.setattr(downloader, "download_preview", fake_download)
    monkeypatch.setattr(downloader.time, "sleep", waits.append)

    result = downloader.download_preview_with_retry(
        PREVIEW_URL,
        tmp_path,
        max_attempts=3,
    )

    assert result["attempts"] == 2
    assert result["checksum"] == "test-checksum"
    assert len(calls) == 2
    assert waits == [1.0]


def test_retry_stops_at_limit_and_keeps_last_error(tmp_path, monkeypatch):
    calls = []
    waits = []
    errors = []

    def fake_download(url, output_dir):
        calls.append(url)
        error = URLError(f"Failure {len(calls)}")
        errors.append(error)
        raise error

    monkeypatch.setattr(downloader, "download_preview", fake_download)
    monkeypatch.setattr(downloader.time, "sleep", waits.append)

    with pytest.raises(downloader.PreviewDownloadError) as caught:
        downloader.download_preview_with_retry(
            PREVIEW_URL,
            tmp_path,
            max_attempts=3,
        )

    assert len(calls) == 3
    assert caught.value.attempts == 3
    assert caught.value.last_error is errors[-1]
    assert waits == [1.0, 2.0]


@pytest.mark.parametrize(
    "error",
    [
        ValueError("Broken image"),
        HTTPError(PREVIEW_URL, 404, "Not Found", {}, None),
    ],
)
def test_permanent_failure_is_not_retried(tmp_path, monkeypatch, error):
    calls = []

    def fake_download(url, output_dir):
        calls.append(url)
        raise error

    def unexpected_sleep(seconds):
        pytest.fail("Không được chờ retry khi lỗi không tạm thời.")

    monkeypatch.setattr(downloader, "download_preview", fake_download)
    monkeypatch.setattr(downloader.time, "sleep", unexpected_sleep)

    with pytest.raises(downloader.PreviewDownloadError) as caught:
        downloader.download_preview_with_retry(PREVIEW_URL, tmp_path)

    assert len(calls) == 1
    assert caught.value.attempts == 1
    assert caught.value.last_error is error


def test_http_503_is_retried(tmp_path, monkeypatch):
    calls = []

    def fake_download(url, output_dir):
        calls.append(url)
        if len(calls) == 1:
            raise HTTPError(
                PREVIEW_URL, 503, "Service Unavailable", {}, None
            )
        return {"checksum": "test-checksum"}

    monkeypatch.setattr(downloader, "download_preview", fake_download)
    monkeypatch.setattr(downloader.time, "sleep", lambda seconds: None)

    result = downloader.download_preview_with_retry(PREVIEW_URL, tmp_path)

    assert len(calls) == 2
    assert result["attempts"] == 2


@pytest.mark.parametrize("max_attempts", [0, -1, True, 1.5])
def test_invalid_attempt_limit_is_rejected(tmp_path, max_attempts):
    with pytest.raises(ValueError, match="max_attempts"):
        downloader.download_preview_with_retry(
            PREVIEW_URL,
            tmp_path,
            max_attempts=max_attempts,
        )