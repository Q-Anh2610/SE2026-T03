"""Kiểm tra ảnh upload trước khi chuyển bytes cho search service."""

from io import BytesIO

from fastapi import UploadFile
from PIL import Image
from starlette.concurrency import run_in_threadpool

from app.core.errors import api_error

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_DIMENSION = 4096


def _verify_image(content: bytes) -> None:
    try:
        with Image.open(BytesIO(content)) as decoded:
            if decoded.format not in {"JPEG", "PNG"}:
                raise api_error(400, "UNSUPPORTED_IMAGE", "Chỉ hỗ trợ ảnh JPEG hoặc PNG.")
            if max(decoded.size) > MAX_IMAGE_DIMENSION:
                raise api_error(400, "IMAGE_DIMENSIONS_EXCEEDED", "Mỗi chiều ảnh không được vượt 4096 pixel.")
            decoded.verify()
        # verify() không giải mã toàn bộ pixel và không cho phép tái dùng image.
        with Image.open(BytesIO(content), formats=["JPEG", "PNG"]) as decoded:
            decoded.load()
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise api_error(400, "INVALID_IMAGE", "Không đọc được nội dung ảnh.") from None


async def read_validated_image(image: UploadFile) -> bytes:
    """Trả bytes gốc đã kiểm tra. Caller chịu trách nhiệm đóng UploadFile."""
    content = await image.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise api_error(400, "IMAGE_TOO_LARGE", "Ảnh vượt giới hạn 5 MiB.")
    await run_in_threadpool(_verify_image, content)
    return content
