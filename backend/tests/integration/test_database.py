from datetime import datetime, timezone
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.seed import seed_assets
from app.models import Asset, Feedback, SearchEvent

pytestmark = pytest.mark.integration


def event(**overrides):
    values = dict(
        query_type="text", query_text="ghế gỗ", model_version="test-model",
        index_version="test-index", config_version="test-config",
    )
    values.update(overrides)
    return SearchEvent(**values)


def test_migration_round_trip_and_model_drift(migrated_database):
    connection, configuration = migrated_database
    assert {"assets", "search_events", "feedbacks"} <= set(inspect(connection).get_table_names())
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001"
    command.check(configuration)
    command.downgrade(configuration, "base")
    assert not {"assets", "search_events", "feedbacks"} & set(inspect(connection).get_table_names())
    command.upgrade(configuration, "head")
    command.check(configuration)


def test_seed_is_idempotent_and_preserves_existing_metadata(migrated_database):
    connection, _ = migrated_database
    with Session(connection, join_transaction_mode="create_savepoint") as session:
        assert seed_assets(session) == 7
        first = session.get(Asset, "mock-asset-001")
        first.name = "Tên đã được chỉnh"
        session.flush()
        assert seed_assets(session) == 0
        assert session.scalar(select(func.count()).select_from(Asset)) == 7
        session.refresh(first)
        assert first.name == "Tên đã được chỉnh"
        assert first.license is None and first.face_count is None
        assert first.ingestion_status == "pending" and first.model_path is None


def test_assets_enforce_source_identity_and_nonnegative_faces(migrated_database):
    connection, _ = migrated_database
    with Session(connection, join_transaction_mode="create_savepoint") as session:
        session.add(Asset(asset_id="a", source="test", source_id="1"))
        session.flush()
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(Asset(asset_id="b", source="test", source_id="1"))
            session.flush()
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(Asset(asset_id="c", source="test", source_id="3", face_count=-1))
            session.flush()
        assert session.get(Asset, "a").face_count is None


def test_arrays_json_and_updated_timestamp_round_trip(migrated_database):
    connection, _ = migrated_database
    old = datetime(2000, 1, 1, tzinfo=timezone.utc)
    with Session(connection, join_transaction_mode="create_savepoint") as session:
        asset = Asset(asset_id="a", source="test", source_id="1", updated_at=old)
        search = event(filters={"category": "Nội thất"})
        session.add_all([asset, search])
        session.flush()
        assert asset.tags == [] and asset.formats == []
        asset.tags.append("ghế")
        asset.formats.append("glb")
        search.filters["license"] = "CC0"
        session.flush()
        session.refresh(asset)
        session.refresh(search)
        assert asset.tags == ["ghế"] and asset.formats == ["glb"]
        assert search.filters == {"category": "Nội thất", "license": "CC0"}
        assert asset.updated_at > old and asset.created_at.utcoffset() is not None


def test_feedback_links_query_asset_and_original_versions(migrated_database):
    connection, _ = migrated_database
    with Session(connection, join_transaction_mode="create_savepoint") as session:
        asset = Asset(asset_id="a", source="test", source_id="1")
        search = event()
        feedback = Feedback(asset=asset, search_event=search, relevance=True)
        session.add(feedback)
        session.flush()
        session.expire_all()
        assert feedback.asset.asset_id == "a"
        assert feedback.search_event.query_text == "ghế gỗ"
        assert feedback.search_event.model_version == "test-model"
        assert feedback.relevance is True
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(Feedback(asset_id="a", search_event_id=uuid4(), relevance=False))
            session.flush()
        with pytest.raises(IntegrityError), session.begin_nested():
            session.execute(text("DELETE FROM assets WHERE asset_id = 'a'"))


@pytest.mark.parametrize("values", [
    {"query_type": "unknown"},
    {"query_text": "   "},
    {"query_type": "image", "query_text": None, "query_image_ref": None},
])
def test_search_event_rejects_invalid_query(migrated_database, values):
    connection, _ = migrated_database
    with Session(connection, join_transaction_mode="create_savepoint") as session:
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(event(**values))
            session.flush()


def test_image_query_and_negative_feedback(migrated_database):
    connection, _ = migrated_database
    with Session(connection, join_transaction_mode="create_savepoint") as session:
        feedback = Feedback(
            asset=Asset(asset_id="a", source="test", source_id="1"),
            search_event=event(query_type="image", query_text=None, query_image_ref="sha256:fixture"),
            relevance=False,
        )
        session.add(feedback)
        session.flush()
        session.refresh(feedback)
        assert feedback.relevance is False
        assert feedback.search_event.query_image_ref == "sha256:fixture"
