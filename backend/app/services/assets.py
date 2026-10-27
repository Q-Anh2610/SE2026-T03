"""Danh sách asset từ PostgreSQL; lọc trước phân trang, không dùng mock store."""

from urllib.parse import urlsplit

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Asset
from app.core.errors import api_error
from app.schemas.api import AssetDetailResponse, AssetListQuery, AssetListResponse, AssetMetadata, Pagination


def public_thumbnail(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        url = urlsplit(value)
        if url.scheme in {"http", "https"} and url.hostname and not url.username and not url.password:
            return value
    except ValueError:
        pass
    # Chưa có cơ chế phục vụ file preview local: không lộ đường dẫn filesystem.
    return None


def asset_metadata(asset: Asset) -> AssetMetadata:
    return AssetMetadata(
        asset_id=asset.asset_id,
        # Contract frontend yêu cầu name là string. ID là nhãn hiển thị dự phòng,
        # không ghi đè tên gốc hoặc tự sinh tên asset trong database.
        name=asset.name if asset.name and asset.name.strip() else asset.asset_id,
        description=asset.description, category=asset.category,
        tags=asset.tags, formats=asset.formats, face_count=asset.face_count,
        thumbnail_url=public_thumbnail(asset.thumbnail_path), source=asset.source,
        source_url=public_thumbnail(asset.source_url), author=asset.author, license=asset.license,
    )


def get_asset(session: Session, asset_id: str) -> AssetDetailResponse:
    asset = session.get(Asset, asset_id)
    if asset is None:
        raise api_error(404, "ASSET_NOT_FOUND", "Không tìm thấy asset.")
    return AssetDetailResponse(asset=asset_metadata(asset), mock=False)


def list_assets(session: Session, params: AssetListQuery) -> AssetListResponse:
    conditions = []
    for field in ("category", "license"):
        value = getattr(params, field)
        if value is not None:
            conditions.append(getattr(Asset, field) == value)
    if params.format is not None:
        conditions.append(Asset.formats.contains([params.format]))
    if params.face_count_min is not None:
        conditions.append(Asset.face_count >= params.face_count_min)
    if params.face_count_max is not None:
        conditions.append(Asset.face_count <= params.face_count_max)
    total = session.scalar(select(func.count()).select_from(Asset).where(*conditions))
    offset = (params.page - 1) * params.limit
    # Tránh OFFSET quá lớn vượt BIGINT; trang ngoài phạm vi luôn rỗng.
    rows = [] if offset >= total else session.scalars(
        select(Asset).where(*conditions).order_by(Asset.asset_id.asc())
        .offset(offset).limit(params.limit)
    ).all()
    pages = (total + params.limit - 1) // params.limit
    return AssetListResponse(
        items=[asset_metadata(asset) for asset in rows],
        pagination=Pagination(page=params.page, limit=params.limit, total=total,
                              pages=pages, has_next=params.page < pages),
        mock=False,
    )
