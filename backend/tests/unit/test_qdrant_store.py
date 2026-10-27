"""Tests Qdrant local mode; không cần server hoặc model."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from qdrant_client import QdrantClient, models

from app.search.qdrant_store import IndexConfig, QdrantStore


@pytest.fixture
def store():
    client = QdrantClient(location=":memory:")
    config = IndexConfig(
        model_id="fixture-model",
        model_revision="fixture-revision",
        dimension=3,
        preprocessing_version="fixture-rgb-l2-v1",
        dataset_snapshot="fixture-snapshot",
        index_version="fixture-index-v1",
    )
    instance = QdrantStore(
        client,
        collection_name="test_assets",
        config=config,
    )
    yield instance
    client.close()


def embedding(asset_id="chair", name="Fixture chair"):
    return {
        "asset_id": asset_id,
        "metadata": {
            "asset_id": asset_id,
            "name": name,
            "description": None,
            "license": None,
            "formats": ["glb"],
            "ingestion_status": "PENDING",
            "model_version": None,
            "index_version": None,
        },
        "vector": [1.0, 0.0, 0.0],
    }


def test_upsert_is_idempotent_and_updates_payload_and_vector(store):
    original = embedding()
    assert store.upsert([original]) == 1

    before, _ = store.client.scroll(
        collection_name=store.collection_name,
        with_vectors=True,
    )

    updated = embedding(name="Updated fixture chair")
    updated["vector"] = [0.0, 1.0, 0.0]
    assert store.upsert([updated]) == 1

    after, _ = store.client.scroll(
        collection_name=store.collection_name,
        with_vectors=True,
    )

    assert store.client.count(store.collection_name).count == 1
    assert after[0].id == before[0].id
    assert after[0].vector[store.vector_name] == pytest.approx(
        [0.0, 1.0, 0.0]
    )

    payload = after[0].payload
    assert payload["name"] == "Updated fixture chair"
    assert payload["license"] is None
    assert payload["model_version"] == "fixture-model@fixture-revision"
    assert payload["index_version"] == "fixture-index-v1"
    assert payload["_index"]["dataset_snapshot"] == "fixture-snapshot"
    assert payload["ingestion_status"] == "PENDING"

    # Việc tạo payload không sửa metadata đầu vào.
    assert original["metadata"]["model_version"] is None
    assert original["metadata"]["index_version"] is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("model_id", "other-model"),
        ("model_revision", "other-revision"),
        ("dimension", 4),
        ("preprocessing_version", "other-preprocessing"),
        ("dataset_snapshot", "other-snapshot"),
        ("index_version", "other-index"),
    ],
)
def test_rejects_incompatible_versions_without_modifying_data(
    store, field, value
):
    store.upsert([embedding()])
    changed = replace(store.config, **{field: value})
    other = QdrantStore(
        store.client,
        collection_name=store.collection_name,
        config=changed,
    )

    with pytest.raises(ValueError):
        other.ensure_collection()

    assert store.client.count(store.collection_name).count == 1
    points, _ = store.client.scroll(store.collection_name)
    assert points[0].payload["_index"]["index_version"] == "fixture-index-v1"


@pytest.mark.parametrize("kind", ["unnamed", "dimension", "distance"])
def test_rejects_incompatible_collection_schema(store, kind):
    params = models.VectorParams(
        size=4 if kind == "dimension" else 3,
        distance=(
            models.Distance.DOT
            if kind == "distance"
            else models.Distance.COSINE
        ),
    )
    vectors = params if kind == "unnamed" else {store.vector_name: params}

    store.client.create_collection(
        collection_name=store.collection_name,
        vectors_config=vectors,
    )

    with pytest.raises(ValueError):
        store.ensure_collection()


@pytest.mark.parametrize(
    "vector",
    [
        [1.0, 0.0],
        [0.0, 0.0, 0.0],
        [2.0, 0.0, 0.0],
        [float("nan"), 0.0, 0.0],
        [float("inf"), 0.0, 0.0],
        [True, 0.0, 0.0],
        ["1", 0.0, 0.0],
        None,
    ],
)
def test_invalid_vector_is_rejected_before_collection_creation(store, vector):
    item = embedding()
    item["vector"] = vector

    with pytest.raises(ValueError):
        store.upsert([item])

    assert not store.client.collection_exists(store.collection_name)


def test_duplicate_ids_are_rejected_before_writing(store):
    with pytest.raises(ValueError):
        store.upsert([embedding(), embedding()])

    assert not store.client.collection_exists(store.collection_name)


def test_metadata_id_must_match_embedding_id(store):
    item = embedding()
    item["metadata"]["asset_id"] = "different"

    with pytest.raises(ValueError):
        store.upsert([item])

    assert not store.client.collection_exists(store.collection_name)


def test_empty_upsert_does_not_create_collection(store):
    assert store.upsert([]) == 0
    assert not store.client.collection_exists(store.collection_name)


def test_acknowledged_operation_is_not_reported_as_completed(
    store, monkeypatch
):
    operation = SimpleNamespace(status=models.UpdateStatus.ACKNOWLEDGED)
    monkeypatch.setattr(
        store.client,
        "upsert",
        Mock(return_value=operation),
    )

    with pytest.raises(RuntimeError):
        store.upsert([embedding()])