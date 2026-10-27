"""Kiểm thử persistence ingestion trên PostgreSQL test riêng."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ingestion.repository import upsert_downloaded_asset
from app.models.asset import Asset


pytestmark = pytest.mark.integration


@pytest.fixture
def db_session(migrated_database):
    connection, _ = migrated_database

    with Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    ) as session:
        yield session


def make_asset(number=1):
    uid = f"{number:032x}"

    return {
        "asset_id": f"objaverse_{uid}",
        "source": "objaverse",
        "source_id": uid,
        "source_url": f"https://sketchfab.com/3d-models/{uid}",
        "author": "Fixture author",
        "license": "by",
        "name": f"Fixture chair {number}",
        "description": None,
        "tags": ["chair"],
        "category": "furniture",
        "thumbnail_path": (
            f"https://media.sketchfab.com/models/{uid}/preview.png"
        ),
        "formats": ["glb"],
        "face_count": None,
    }


def make_preview(asset):
    # Kết quả preview giả lập; tests này tập trung vào persistence DB.
    return {
        "preview_source_url": asset["thumbnail_path"],
        "preview_local_path": "fixture/preview.png",
        "checksum": "a" * 64,
        "checksum_resource": "preview",
    }


def test_insert_and_rerun_do_not_create_duplicate(db_session):
    asset = make_asset()
    preview = make_preview(asset)

    first_id = upsert_downloaded_asset(db_session, asset, preview)
    db_session.commit()

    second_id = upsert_downloaded_asset(db_session, asset, preview)
    db_session.commit()

    count = db_session.scalar(
        select(func.count()).select_from(Asset).where(
            Asset.source == asset["source"],
            Asset.source_id == asset["source_id"],
        )
    )

    db_session.expire_all()
    saved = db_session.get(Asset, asset["asset_id"])

    assert first_id == second_id == asset["asset_id"]
    assert count == 1
    assert saved.ingestion_status == "downloaded"
    assert saved.thumbnail_path == asset["thumbnail_path"]
    assert saved.checksum is None
    assert saved.model_version is None
    assert saved.index_version is None


def test_update_preserves_model_fields(db_session):
    asset = make_asset()
    preview = make_preview(asset)

    upsert_downloaded_asset(db_session, asset, preview)
    saved = db_session.get(Asset, asset["asset_id"])
    saved.checksum = "b" * 64
    saved.model_path = "fixture/model.glb"
    saved.model_version = "fixture-model"
    db_session.commit()

    changed = {
        **asset,
        "name": "Updated fixture chair",
        "tags": ["chair", "wood"],
    }

    upsert_downloaded_asset(db_session, changed, preview)
    db_session.commit()
    db_session.expire_all()

    saved = db_session.get(Asset, asset["asset_id"])

    assert saved.name == "Updated fixture chair"
    assert saved.tags == ["chair", "wood"]
    assert saved.checksum == "b" * 64
    assert saved.model_path == "fixture/model.glb"
    assert saved.model_version == "fixture-model"


def test_same_source_cannot_use_another_asset_id(db_session):
    asset = make_asset()
    preview = make_preview(asset)

    upsert_downloaded_asset(db_session, asset, preview)
    db_session.commit()

    conflicting = {
        **asset,
        "asset_id": "another-asset-id",
    }

    with pytest.raises(ValueError, match="source/source_id"):
        upsert_downloaded_asset(
            db_session,
            conflicting,
            preview,
        )

    assert db_session.get(Asset, "another-asset-id") is None


def test_same_asset_id_cannot_change_source_identity(db_session):
    asset = make_asset()
    preview = make_preview(asset)

    upsert_downloaded_asset(db_session, asset, preview)
    db_session.commit()

    conflicting = {
        **asset,
        "source_id": "different-source-id",
    }

    with pytest.raises(ValueError, match="định danh"):
        upsert_downloaded_asset(
            db_session,
            conflicting,
            preview,
        )

    db_session.expire_all()
    saved = db_session.get(Asset, asset["asset_id"])

    assert saved.source_id == asset["source_id"]


def test_indexed_asset_is_not_overwritten(db_session):
    asset = make_asset()
    preview = make_preview(asset)

    upsert_downloaded_asset(db_session, asset, preview)
    saved = db_session.get(Asset, asset["asset_id"])
    saved.index_version = "fixture-index-v1"
    saved.ingestion_status = "searchable"
    db_session.commit()

    changed = {
        **asset,
        "name": "Must not replace existing name",
    }

    with pytest.raises(ValueError, match="index_version"):
        upsert_downloaded_asset(db_session, changed, preview)

    db_session.expire_all()
    saved = db_session.get(Asset, asset["asset_id"])

    assert saved.name == asset["name"]
    assert saved.index_version == "fixture-index-v1"
    assert saved.ingestion_status == "searchable"