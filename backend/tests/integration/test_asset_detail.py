"""Detail và list dùng PostgreSQL test thật, không dùng mock store."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, update
from sqlalchemy.orm import Session

from app.api.assets import detail_session, list_session
from app.core.config import Settings
from app.main import create_app
from app.models import Asset

pytestmark = pytest.mark.integration


@pytest.fixture
def detail_client(migrated_database):
    connection, _ = migrated_database
    connection.execute(insert(Asset), [
        {
            "asset_id": "db-chair", "source": "test", "source_id": "chair",
            "name": "Ghế thử nghiệm", "description": "Metadata kiểm thử",
            "category": "Nội thất", "tags": ["chair", "wood"], "formats": ["glb"],
            "face_count": 100, "author": "Test author", "license": "Test license",
            "thumbnail_path": "https://example.org/preview.png",
            "source_url": "https://example.org/asset",
        },
        {
            "asset_id": "db-unknown", "source": "test", "source_id": "unknown",
            "name": None, "description": None, "category": None, "tags": [], "formats": [],
            "face_count": None, "author": None, "license": None,
            "thumbnail_path": None, "source_url": None,
        },
    ])
    application = create_app(Settings(_env_file=None, env="test", asset_list_source="database"))

    def session_override():
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session

    application.dependency_overrides[detail_session] = session_override
    application.dependency_overrides[list_session] = session_override
    with TestClient(application) as client:
        yield client, connection


def test_detail_matches_database_metadata(detail_client):
    client, _ = detail_client
    response = client.get("/api/v1/assets/db-chair")
    assert response.status_code == 200
    assert response.json() == {"mock": False, "asset": {
        "asset_id": "db-chair", "source": "test", "name": "Ghế thử nghiệm",
        "description": "Metadata kiểm thử", "category": "Nội thất", "tags": ["chair", "wood"],
        "formats": ["glb"], "face_count": 100, "author": "Test author", "license": "Test license",
        "thumbnail_url": "https://example.org/preview.png", "source_url": "https://example.org/asset",
    }}


def test_missing_asset_is_404_and_does_not_fall_back_to_fixture(detail_client):
    client, _ = detail_client
    # mock-chair-01 tồn tại trong MockStore, nhưng không có trong PostgreSQL.
    for identifier in ("not-found", "mock-chair-01", "DB-chair", "' OR 1=1 --"):
        response = client.get("/api/v1/assets/" + identifier)
        assert response.status_code == 404
        assert response.json() == {"error": {
            "code": "ASSET_NOT_FOUND", "message": "Không tìm thấy asset.", "details": [],
        }}


def test_detail_unknown_metadata_preserves_nulls_without_changing_database(detail_client):
    client, connection = detail_client
    response = client.get("/api/v1/assets/db-unknown")
    assert response.status_code == 200
    asset = response.json()["asset"]
    assert asset["name"] == "db-unknown"  # Quy ước hiển thị đã dùng ở #47.
    for field in ("description", "category", "face_count", "author", "license", "source_url", "thumbnail_url"):
        assert asset[field] is None
    assert asset["tags"] == [] and asset["formats"] == []
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        assert session.get(Asset, "db-unknown").name is None


def test_preview_and_source_urls_are_safe_in_both_list_and_detail(detail_client):
    client, connection = detail_client
    for value in (None, r"C:\private\preview.png", "/private/preview.png", "file:///private/preview.png",
                  "https://user:secret@example.org/image.png", "javascript:alert(1)", "https://[invalid"):
        connection.execute(update(Asset).where(Asset.asset_id == "db-chair").values(
            thumbnail_path=value, source_url=value,
        ))
        body = client.get("/api/v1/assets/db-chair").json()
        assert body["asset"]["thumbnail_url"] is None
        assert body["asset"]["source_url"] is None
        assert "private" not in str(body) and "secret" not in str(body)
        listing = client.get("/api/v1/assets").json()
        assert listing["items"][0] == body["asset"]


def test_list_detail_and_return_to_same_page_have_consistent_metadata(detail_client):
    client, _ = detail_client
    query = {"limit": 1, "page": 2}
    listing = client.get("/api/v1/assets", params=query).json()
    item = listing["items"][0]
    detail = client.get("/api/v1/assets/" + item["asset_id"]).json()
    assert detail["mock"] is False
    assert detail["asset"] == item
    assert client.get("/api/v1/assets", params=query).json() == listing
