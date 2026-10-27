"""Ghi metadata ingestion vào PostgreSQL, không tự commit transaction."""

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.asset import Asset


METADATA_FIELDS = (
    "source_url",
    "author",
    "license",
    "name",
    "description",
    "tags",
    "category",
    "thumbnail_path",
    "formats",
    "face_count",
)


def upsert_downloaded_asset(
    session: Session,
    asset: dict,
    preview: dict,
) -> str:
    """Ghi asset đã có preview hợp lệ và trả asset_id.

    Caller quản lý commit/rollback.
    Checksum preview được giữ trong báo cáo, không ghi vào checksum model.
    """
    asset_id = asset["asset_id"]
    source = asset["source"]
    source_id = asset["source_id"]

    if preview.get("checksum_resource") != "preview":
        raise ValueError("Kết quả phải chỉ rõ checksum_resource=preview.")

    if not preview.get("preview_local_path") or not preview.get("checksum"):
        raise ValueError("Thiếu đường dẫn local hoặc checksum preview.")

    if preview.get("preview_source_url") != asset.get("thumbnail_path"):
        raise ValueError("URL preview không khớp metadata nguồn.")

    # Phát hiện cùng nguồn nhưng bị gán asset_id khác.
    source_asset_id = session.scalar(
        select(Asset.asset_id).where(
            Asset.source == source,
            Asset.source_id == source_id,
        )
    )

    if source_asset_id is not None and source_asset_id != asset_id:
        raise ValueError(
            "Cặp source/source_id đã thuộc một asset_id khác."
        )

    values = {
        "asset_id": asset_id,
        "source": source,
        "source_id": source_id,
        "ingestion_status": "downloaded",
    }

    for field in METADATA_FIELDS:
        values[field] = asset.get(field)

    values["tags"] = list(asset.get("tags") or [])
    values["formats"] = list(asset.get("formats") or [])

    statement = insert(Asset).values(**values)

    updates = {
        field: getattr(statement.excluded, field)
        for field in METADATA_FIELDS
    }

    updates["updated_at"] = func.now()

    statement = statement.on_conflict_do_update(
        index_elements=[Asset.asset_id],
        set_=updates,
        where=(
            (Asset.source == source)
            & (Asset.source_id == source_id)
            & Asset.index_version.is_(None)
        ),
    ).returning(Asset.asset_id)

    saved_asset_id = session.scalar(statement)

    if saved_asset_id is None:
        raise ValueError(
            "Asset có định danh không khớp hoặc đã có index_version; "
            "không cập nhật tự động."
        )

    return saved_asset_id
