"""API list truy vấn PostgreSQL thật trong transaction của database test riêng."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.api.assets import list_session
from app.main import create_app
from app.models import Asset

pytestmark = pytest.mark.integration


@pytest.fixture
def client(migrated_database):
    connection, _ = migrated_database
    connection.execute(insert(Asset), [
        dict(asset_id=key, source="test", source_id=key, name=name,
             category=category, license=license, formats=formats, face_count=faces,
             thumbnail_path=preview)
        for key, name, category, license, formats, faces, preview in [
            ("asset-c", "Table", "furniture", "CC0", ["glb"], 20, None),
            ("asset-a", "Chair", "furniture", "CC0", ["glb", "fbx"], 10, "https://example.org/a.png"),
            ("asset-e", None, None, None, [], None, r"C:\private\preview.png"),
            ("asset-b", "Lamp", "lighting", "CC-BY", ["fbx"], 10, "/private/preview.png"),
            ("asset-d", "Sofa", "furniture", "CC0", ["glb"], None, None),
        ]
    ])
    application = create_app(Settings(_env_file=None, env="test", asset_list_source="database"))

    def session_override():
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session

    application.dependency_overrides[list_session] = session_override
    with TestClient(application) as value:
        yield value


def test_list_pages_are_sorted_complete_and_not_mock(client):
    pages = [client.get("/api/v1/assets", params={"limit": 2, "page": page}) for page in (1, 2, 3)]
    assert all(response.status_code == 200 for response in pages)
    bodies = [response.json() for response in pages]
    assert [item["asset_id"] for body in bodies for item in body["items"]] == [
        "asset-a", "asset-b", "asset-c", "asset-d", "asset-e",
    ]
    assert all(body["mock"] is False for body in bodies)
    assert bodies[0]["pagination"] == {"page": 1, "limit": 2, "total": 5, "pages": 3, "has_next": True}
    assert bodies[-1]["pagination"]["has_next"] is False
    assert client.get("/api/v1/assets?limit=2").json() == bodies[0]


def test_filters_and_null_semantics(client):
    cases = [
    ({"category": "furniture"}, ["asset-a", "asset-c", "asset-d"]),
    ({"license": "CC-BY"}, ["asset-b"]),
    ({"format": "fbx"}, ["asset-a", "asset-b"]),
    ({"face_count_min": 10, "face_count_max": 10}, ["asset-a", "asset-b"]),
    ({"face_count_min": 0}, ["asset-a", "asset-b", "asset-c"]),
    ({"face_count_max": 20}, ["asset-a", "asset-b", "asset-c"]),
    ({"category": "furniture", "license": "CC0", "format": "glb", "face_count_max": 10}, ["asset-a"]),
    ({"category": "Furniture"}, []),
    ({"category": "furniture' OR 1=1 --"}, []),
    ]
    for params, ids in cases:
        response = client.get("/api/v1/assets", params=params)
        assert response.status_code == 200, params
        body = response.json()
        assert [item["asset_id"] for item in body["items"]] == ids, params
        assert body["pagination"]["total"] == len(ids), params


def test_filter_count_is_before_pagination(client):
    body = client.get("/api/v1/assets?category=furniture&limit=1&page=2").json()
    assert [item["asset_id"] for item in body["items"]] == ["asset-c"]
    assert body["pagination"] == {"page": 2, "limit": 1, "total": 3, "pages": 3, "has_next": True}


def test_empty_and_out_of_range(client):
    cases = [
    ({"category": "missing"}, 0, 0),
    ({"page": 999}, 5, 1),
    ({"page": 10**30}, 5, 1),
    ]
    for params, total, pages in cases:
        response = client.get("/api/v1/assets", params=params)
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["pagination"]["total"] == total
        assert body["pagination"]["pages"] == pages
        assert body["pagination"]["has_next"] is False


def test_metadata_preserves_unknowns_and_hides_local_paths(client):
    body = client.get("/api/v1/assets").json()
    first, last = body["items"][0], body["items"][-1]
    assert first["thumbnail_url"] == "https://example.org/a.png"
    assert last["name"] == last["asset_id"]
    for field in ("description", "category", "face_count", "thumbnail_url", "source_url", "author", "license"):
        assert last[field] is None
    assert last["tags"] == [] and last["formats"] == []
    assert body["items"][1]["thumbnail_url"] is None
    assert "private" not in str(body)


def test_invalid_query_returns_contract_error(client):
    cases = [
    {"page": 0}, {"page": "abc"}, {"limit": 0}, {"limit": 51}, {"limit": "1.5"},
    {"face_count_min": -1}, {"face_count_min": 20, "face_count_max": 10},
    {"face_count_max": "true"}, {"category": " "}, {"unknown": "value"},
    ]
    for params in cases:
        response = client.get("/api/v1/assets", params=params)
        assert response.status_code == 400, params
        assert response.json()["error"]["code"] == "INVALID_REQUEST"
