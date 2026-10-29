"""Audit helper tests: in-memory Qdrant and fixture vectors, no CLIP download."""

import pytest
from qdrant_client import QdrantClient, models

from app.search.qdrant_store import IndexConfig, QdrantStore
from scripts.verify_issue39_real_assets import audit_collection, point_id


@pytest.fixture
def indexed():
    client = QdrantClient(location=":memory:")
    store = QdrantStore(client, collection_name="runner-helper-test", config=IndexConfig(
        "fixture", "fixture-revision", 3, "rgb-l2-v1", "fixture", "v1"))
    metadata = {aid: {"asset_id": aid, "name": aid} for aid in ("a", "b")}
    points = [{"asset_id": aid, "metadata": payload, "vector": [1.0, 0.0, 0.0]}
              for aid, payload in metadata.items()]
    store.upsert(points)
    yield client, store, metadata, points
    client.close()


def test_repeat_retains_point_ids_and_payloads(indexed):
    client, store, metadata, points = indexed
    before, valid = audit_collection(client, store, metadata)
    assert valid == {"a", "b"}
    store.upsert(points)
    after, _ = audit_collection(client, store, metadata)
    assert before == after
    assert after["exact_point_count"] == 2


def test_correct_count_cannot_hide_wrong_payload(indexed):
    client, store, metadata, _ = indexed
    client.set_payload(collection_name=store.collection_name,
                       payload={"index_version": "wrong"}, points=[point_id("a")], wait=True)
    summary, valid = audit_collection(client, store, metadata)
    assert summary["exact_point_count"] == 2
    assert valid == {"b"}
    assert summary["invalid_payload_or_point_ids"] == [point_id("a")]


def test_duplicate_asset_payload_is_detected(indexed):
    client, store, metadata, _ = indexed
    records, _ = client.scroll(store.collection_name, limit=10,
                               with_payload=True, with_vectors=True)
    record = records[0]
    client.upsert(store.collection_name, points=[models.PointStruct(
        id=123, vector=record.vector, payload=record.payload)], wait=True)
    summary, _ = audit_collection(client, store, metadata)
    assert summary["exact_point_count"] == 3
    assert len(summary["duplicate_asset_ids"]) == 1
    assert "123" in summary["invalid_payload_or_point_ids"]
