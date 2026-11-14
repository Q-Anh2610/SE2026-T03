"""VT-011: bounded metadata export. Principal phải do trusted adapter cung cấp."""
from dataclasses import dataclass

from pydantic import Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import api_error
from app.models import Asset
from app.schemas.api import InputModel
from app.services.assets import asset_metadata


@dataclass(frozen=True)
class ExportPrincipal:
    can_export: bool
    sources: frozenset[str]


class ExportRequest(InputModel):
    source: str = Field(min_length=1, max_length=64, strict=True)
    limit: int = Field(default=1000, ge=1, le=2000, strict=True)


def authorize(principal: ExportPrincipal | None, source: str) -> None:
    if principal is None:
        raise api_error(401, 'UNAUTHENTICATED', 'Cần xác thực để xuất dữ liệu.')
    if not principal.can_export:
        raise api_error(403, 'EXPORT_FORBIDDEN', 'Không có quyền xuất dữ liệu.')
    if source not in principal.sources:
        raise api_error(403, 'SCOPE_FORBIDDEN', 'Phạm vi xuất không được cấp quyền.')


def export_metadata(session: Session, principal: ExportPrincipal | None,
                    params: ExportRequest) -> dict:
    # Bảo vệ cả caller ngoài HTTP. Không đọc dữ liệu trước khi kiểm tra quyền.
    authorize(principal, params.source)
    # Read-only projection: Row exposes the public mapper's attributes without
    # constructing tracked ORM entities for every exported record.
    statement = (select(
        Asset.asset_id, Asset.name, Asset.description, Asset.category, Asset.tags,
        Asset.formats, Asset.face_count, Asset.thumbnail_path, Asset.source,
        Asset.source_url, Asset.author, Asset.license,
    ).where(Asset.source == params.source)
                 .order_by(Asset.asset_id.asc()).limit(params.limit + 1))
    try:
        rows = session.execute(statement).all()
    except SQLAlchemyError:
        raise api_error(503, 'EXPORT_UNAVAILABLE', 'Không thể xuất dữ liệu lúc này.') from None
    if len(rows) > params.limit:
        raise api_error(413, 'EXPORT_TOO_LARGE', 'Dữ liệu vượt giới hạn xuất.')
    # Tái dùng mapping/schema chung: null, ARRAY, URLs công khai; không lộ local paths.
    return {'source': params.source,
            'items': [asset_metadata(asset).model_dump(mode='json') for asset in rows]}
