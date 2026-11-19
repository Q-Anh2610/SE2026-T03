"""Real PostgreSQL; isolated schemas, fixture previews, no network/Qdrant."""

import hashlib
from io import BytesIO
from pathlib import Path

from PIL import Image
import copy
import json
import os

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.ingestion import pipeline, repository
from app.ingestion.db_writer import DatabaseWriter, PersistenceError
from app.models.asset import Asset
from scripts.asset_api_test_support import isolated_asset_database


pytestmark = pytest.mark.integration


@pytest.fixture
def database():
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set TEST_DATABASE_URL to an isolated test_* database.")

    with isolated_asset_database(value) as db:
        db.migrate()
        yield db


@pytest.fixture
def writer(database, monkeypatch):
    import app.db.session as db_session

    monkeypatch.setattr(
        db_session, "create_db_engine", lambda: database.engine
    )
    with DatabaseWriter() as value:
        yield value


def make_asset(number):
    uid = f"{number:032x}"
    return {
        "asset_id": f"objaverse_{uid}",
        "source": "objaverse",
        "source_id": uid,
        "source_url": f"https://sketchfab.com/3d-models/{uid}",
        "name": f"Fixture chair {number}",
        "description": "Original description",
        "license": "by",
        "tags": ["chair"],
        "category": "furniture",
        "formats": ["glb"],
        "face_count": 10,
        "thumbnail_path": (
            f"https://media.sketchfab.com/models/{uid}/preview.png"
        ),
    }


def make_preview(asset):
    # Preview is a fixture; these tests verify PostgreSQL persistence.
    return {
        "preview_source_url": asset["thumbnail_path"],
        "preview_local_path": "fixture/preview.png",
        "checksum": "a" * 64,
        "checksum_resource": "preview",
        "attempts": 1,
    }


def snapshot(engine, asset_id):
    with engine.connect() as connection:
        row = connection.execute(
            select(Asset.__table__).where(Asset.asset_id == asset_id)
        ).mappings().one_or_none()
        return None if row is None else copy.deepcopy(dict(row))


def test_indexed_asset_rejection_preserves_entire_record(
    database, writer
):
    asset = make_asset(1)
    writer(asset, make_preview(asset))

    with Session(database.engine) as session, session.begin():
        saved = session.get(Asset, asset["asset_id"])
        saved.ingestion_status = "searchable"
        saved.index_version = "fixture-index-v1"
        saved.model_version = "fixture-model-v1"
        saved.model_path = "fixture/model.glb"
        saved.checksum = "b" * 64

    before = snapshot(database.engine, asset["asset_id"])
    changed = {
        **asset,
        "name": "Must not overwrite",
        "description": None,
        "tags": [],
        "thumbnail_path": asset["thumbnail_path"] + "?changed=1",
    }

    with pytest.raises(PersistenceError, match="index_version"):
        writer(changed, make_preview(changed))

    assert snapshot(database.engine, asset["asset_id"]) == before


def test_database_constraint_failure_rolls_back_and_batch_continues(
    database, writer, tmp_path, monkeypatch
):
    assets = [make_asset(1), make_asset(2)]
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(assets), encoding="utf-8")
    original_manifest = manifest.read_bytes()

    original_upsert = repository.upsert_downloaded_asset
    attempted = []

    def upsert_then_trigger_constraint(session, asset, preview):
        attempted.append(asset["asset_id"])
        saved_id = original_upsert(session, asset, preview)
        if asset["asset_id"] == assets[0]["asset_id"]:
            # Real SQL runs after the insert, in the same transaction.
            # PostgreSQL rejects this through face_count_nonnegative.
            session.execute(
                update(Asset)
                .where(Asset.asset_id == saved_id)
                .values(face_count=-1)
            )
        return saved_id

    monkeypatch.setattr(
        repository,
        "upsert_downloaded_asset",
        upsert_then_trigger_constraint,
    )

    def download(url, output_dir, *, max_attempts):
        asset = next(
            row for row in assets if row["thumbnail_path"] == url
        )
        return make_preview(asset)

    monkeypatch.setattr(
        pipeline, "download_preview_with_retry", download
    )

    report_path = tmp_path / "report.json"
    report = pipeline.run_batch(
        manifest,
        tmp_path / "previews",
        report_path,
        persist_asset=writer,
    )

    assert attempted == [asset["asset_id"] for asset in assets]
    assert report["summary"] == {
        "input_count": 2,
        "succeeded": 1,
        "failed": 1,
        "skipped": 0,
    }

    failed = report["results"][0]
    assert failed["asset_id"] == assets[0]["asset_id"]
    assert failed["status"] == "failed"
    assert failed["stage"] == "persistence"
    assert failed["database_status"] == "failed"
    assert failed["preview_status"] == "downloaded"
    assert failed["error_type"] == "PersistenceError"
    assert failed["error_message"] == (
        "Không ghi được PostgreSQL; transaction asset đã rollback."
    )

    # The insert before the SQL error must also have been rolled back.
    assert snapshot(database.engine, assets[0]["asset_id"]) is None

    saved = snapshot(database.engine, assets[1]["asset_id"])
    assert saved is not None
    assert saved["name"] == assets[1]["name"]
    assert saved["face_count"] == 10
    assert saved["ingestion_status"] == "downloaded"
    assert saved["index_version"] is None

    assert report["results"][1]["database_status"] == "saved"
    assert json.loads(report_path.read_text(encoding="utf-8")) == report
    assert manifest.read_bytes() == original_manifest


def test_cache_hit_updates_metadata_through_real_database_writer(
    database, writer, tmp_path, monkeypatch
):
    asset = make_asset(1)
    untouched = make_asset(2)
    writer(untouched, make_preview(untouched))
    untouched_before = snapshot(database.engine, untouched["asset_id"])

    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([asset]), encoding="utf-8")
    previews = tmp_path / "previews"

    buffer = BytesIO()
    Image.new("RGB", (16, 12), color="blue").save(buffer, format="PNG")
    content = buffer.getvalue()
    checksum = hashlib.sha256(content).hexdigest()
    downloads = []

    def download(url, output_dir, *, max_attempts):
        downloads.append(url)
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{checksum}.png"
        path.write_bytes(content)
        return {
            "preview_source_url": url,
            "preview_local_path": path.as_posix(),
            "checksum": checksum,
            "checksum_resource": "preview",
            "bytes": len(content),
            "width": 16,
            "height": 12,
            "attempts": 1,
        }

    monkeypatch.setattr(
        pipeline, "download_preview_with_retry", download
    )
    previous_report = tmp_path / "first.json"

    first = pipeline.run_batch(
        manifest,
        previews,
        previous_report,
        persist_asset=writer,
    )

    assert downloads == [asset["thumbnail_path"]]
    assert first["summary"]["succeeded"] == 1
    assert first["results"][0]["database_status"] == "saved"

    saved_before = snapshot(database.engine, asset["asset_id"])
    assert saved_before["name"] == asset["name"]
    previous_bytes = previous_report.read_bytes()
    preview_path = Path(first["results"][0]["preview_local_path"])
    preview_bytes = preview_path.read_bytes()

    changed = {
        **asset,
        "name": "Updated cached chair",
        "description": "New metadata with the same preview.",
        "tags": ["chair", "wood"],
    }
    manifest.write_text(json.dumps([changed]), encoding="utf-8")
    manifest_before = manifest.read_bytes()

    def unexpected_download(*args, **kwargs):
        pytest.fail("Valid cache hit must not download again.")

    monkeypatch.setattr(
        pipeline, "download_preview_with_retry", unexpected_download
    )

    persistence_calls = []

    def persist_current_metadata(record, preview):
        persistence_calls.append(copy.deepcopy(record))
        writer(record, preview)

    report_path = tmp_path / "second.json"
    second = pipeline.run_batch(
        manifest,
        previews,
        report_path,
        previous_report_path=previous_report,
        persist_asset=persist_current_metadata,
    )

    assert len(persistence_calls) == 1
    assert persistence_calls[0]["name"] == changed["name"]
    assert second["summary"] == {
        "input_count": 1,
        "succeeded": 0,
        "failed": 0,
        "skipped": 1,
    }

    result = second["results"][0]
    assert result["status"] == "skipped"
    assert result["preview_status"] == "skipped"
    assert result["database_status"] == "saved"
    assert result["attempts"] == 0
    assert result["checksum"] == checksum

    # Read through a new connection after DatabaseWriter committed.
    saved_after = snapshot(database.engine, asset["asset_id"])
    assert saved_after["name"] == changed["name"]
    assert saved_after["description"] == changed["description"]
    assert saved_after["tags"] == changed["tags"]
    assert saved_after["created_at"] == saved_before["created_at"]
    assert saved_after["thumbnail_path"] == asset["thumbnail_path"]
    assert saved_after["ingestion_status"] == "downloaded"
    assert saved_after["index_version"] is None

    with database.engine.connect() as connection:
        ids = connection.execute(
            select(Asset.asset_id).where(
                Asset.asset_id.in_([
                    asset["asset_id"], untouched["asset_id"]
                ])
            )
        ).scalars().all()
    assert sorted(ids) == sorted([
        asset["asset_id"], untouched["asset_id"]
    ])

    assert snapshot(
        database.engine, untouched["asset_id"]
    ) == untouched_before
    assert preview_path.read_bytes() == preview_bytes
    assert previous_report.read_bytes() == previous_bytes
    assert manifest.read_bytes() == manifest_before
    assert len(list(previews.iterdir())) == 1
    assert json.loads(report_path.read_text(encoding="utf-8")) == second


@pytest.mark.parametrize("mode", ["omitted", "null", "empty"])
def test_full_record_update_preserves_protected_fields_and_reruns(
    database, writer, mode
):
    asset = make_asset(1)
    writer(asset, make_preview(asset))

    outside = make_asset(2)
    writer(outside, make_preview(outside))
    outside_before = snapshot(database.engine, outside["asset_id"])

    with Session(database.engine) as session, session.begin():
        saved = session.get(Asset, asset["asset_id"])
        saved.model_path = "fixture/model.glb"
        saved.checksum = "b" * 64
        saved.model_version = "fixture-model-v1"
        saved.ingestion_status = "pending"

    before = snapshot(database.engine, asset["asset_id"])
    changed = copy.deepcopy(asset)
    changed["name"] = "Updated full-record chair"
    changed["thumbnail_path"] = (
        asset["thumbnail_path"].replace("preview.png", "new-preview.png")
    )

    fields = ("description", "tags", "formats")
    if mode == "omitted":
        for field in fields:
            changed.pop(field)
    elif mode == "null":
        for field in fields:
            changed[field] = None
    else:
        changed.update(description="", tags=[], formats=[])

    # Exercise the same normalization used by the batch pipeline.
    normalized, invalid = pipeline.SourceAdapter(
        "unused-fixture-manifest.json"
    ).normalize_and_validate([changed])
    assert invalid == []
    assert len(normalized) == 1
    record = normalized[0]

    preview = make_preview(record)
    preview["checksum"] = "c" * 64
    writer(record, preview)

    after = snapshot(database.engine, asset["asset_id"])
    assert after["name"] == changed["name"]
    assert after["thumbnail_path"] == changed["thumbnail_path"]
    assert after["description"] == ("" if mode == "empty" else None)
    assert after["tags"] == []
    assert after["formats"] == []

    protected = (
        "asset_id", "source", "source_id", "created_at",
        "model_path", "checksum", "model_version",
        "index_version", "ingestion_status",
    )
    for field in protected:
        assert after[field] == before[field], field

    # Preview checksum must not overwrite the model checksum.
    assert after["checksum"] == "b" * 64
    assert after["index_version"] is None

    writer(record, preview)
    rerun = snapshot(database.engine, asset["asset_id"])

    # updated_at may change on a successful rerun.
    assert {
        key: value for key, value in rerun.items()
        if key != "updated_at"
    } == {
        key: value for key, value in after.items()
        if key != "updated_at"
    }

    with database.engine.connect() as connection:
        ids = connection.execute(
            select(Asset.asset_id).where(
                Asset.source == asset["source"],
                Asset.source_id == asset["source_id"],
            )
        ).scalars().all()
    assert ids == [asset["asset_id"]]
    assert snapshot(database.engine, outside["asset_id"]) == outside_before


@pytest.mark.parametrize("conflict", ["asset_id", "source_id"])
def test_identity_conflict_preserves_existing_record(
    database, writer, conflict
):
    asset = make_asset(1)
    writer(asset, make_preview(asset))
    before = snapshot(database.engine, asset["asset_id"])

    changed = {
        **asset,
        "name": "Must not replace original metadata",
    }
    if conflict == "asset_id":
        changed["asset_id"] = "fixture-conflicting-id"
    else:
        changed["source_id"] = "f" * 32

    with pytest.raises(PersistenceError):
        writer(changed, make_preview(changed))

    assert snapshot(database.engine, asset["asset_id"]) == before

    with database.engine.connect() as connection:
        rows = connection.execute(
            select(Asset.__table__)
        ).mappings().all()
    assert len(rows) == 1
    assert dict(rows[0]) == before