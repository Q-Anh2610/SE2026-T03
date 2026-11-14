"""Khóa quản trị cho API nội bộ; không dùng làm xác thực người dùng công khai."""

from hmac import compare_digest
from typing import Annotated

from fastapi import Request, Security
from fastapi.security import APIKeyHeader

from app.core.errors import api_error

admin_key = APIKeyHeader(name="X-Admin-Key", scheme_name="AdminKey", auto_error=False)


def require_admin(request: Request, supplied: Annotated[str | None, Security(admin_key)]):
    expected = request.app.state.settings.admin_api_key
    if expected is None:
        raise api_error(503, "ADMIN_API_UNAVAILABLE", "API quản trị chưa được cấu hình.")
    if supplied is None or not compare_digest(supplied.encode(), expected.get_secret_value().encode()):
        raise api_error(403, "ADMIN_ACCESS_DENIED", "Không có quyền truy cập quản trị.")
