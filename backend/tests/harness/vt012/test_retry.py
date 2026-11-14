"""Test-first theo contract và state transitions; không mirror implementation."""

from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest
from qdrant_client import models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.search.qdrant_store import QdrantStore

from .support import embedding, http_error, make_store


@pytest.fixture
def setup_store(monkeypatch):
    stores = []
    waits = []
    monkeypatch.setattr("time.sleep", waits.append)

    def create(faults=(), **kwargs):
        store, client = make_store(faults, **kwargs)
        stores.append(client)
        return store, client, waits

    yield create
    for client in stores:
        client.close()


def test_t01_first_success_has_one_write_and_no_wait(setup_store):
    store, client, waits = setup_store()
    assert store.upsert([embedding()]) == 1
    assert len(client.calls) == 1
    assert client.count(store.collection_name).count == 1
    assert waits == []


def test_t02_http503_transitions_from_error_to_completed(setup_store):
    store, client, waits = setup_store([http_error(503), None])
    assert store.upsert([embedding()]) == 1
    assert client.events == ["UPSERT", "ERROR", "UPSERT", "COMPLETED"]
    assert client.count(store.collection_name).count == 1
    assert len(waits) == 1


def test_t03_timeout_before_write_recovers(setup_store):
    store, client, _ = setup_store(["before", None])
    assert store.upsert([embedding()]) == 1
    assert len(client.calls) == 2
    assert client.count(store.collection_name).count == 1


def test_t04_write_then_timeout_reuses_same_ids_payload_and_vectors(setup_store):
    store, client, _ = setup_store(["after", None])
    items = [embedding("chair-a"), embedding("chair-b")]
    assert store.upsert(items) == 2
    assert client.count(store.collection_name).count == 2
    assert client.calls[0] == client.calls[1]
    assert all(call["wait"] is True for call in client.calls)
    assert {p["payload"]["asset_id"] for p in client.snapshot(store.collection_name)} == {
        "chair-a", "chair-b"
    }
    assert items[0]["metadata"] == {
        "asset_id": "chair-a", "name": "Synthetic chair", "license": None
    }


def test_t05_partial_batch_then_retry_converges_without_duplicates(setup_store):
    store, client, _ = setup_store(["partial", None])
    assert store.upsert([embedding("chair-a"), embedding("chair-b")]) == 2
    snapshot = client.snapshot(store.collection_name)
    assert len(snapshot) == 2
    assert len({p["id"] for p in snapshot}) == 2
    assert client.events == [
        "UPSERT", "PARTIAL_WRITE_RESPONSE_LOST", "UPSERT", "COMPLETED"
    ]


@pytest.mark.parametrize("code", [400, 401, 403, 404, 409, 422])
def test_t06_permanent_http_errors_fail_fast_without_side_effects(setup_store, code):
    store, client, waits = setup_store([http_error(code)])
    with pytest.raises(UnexpectedResponse) as caught:
        store.upsert([embedding()])
    assert caught.value.status_code == code
    assert len(client.calls) == 1
    assert client.count(store.collection_name).count == 0
    assert waits == []


def test_t07_invalid_dimension_rejected_before_any_write(setup_store):
    store, client, waits = setup_store()
    item = embedding()
    item["vector"] = [1.0, 0.0]
    with pytest.raises(ValueError, match="dimension"):
        store.upsert([item])
    assert client.calls == []
    assert not client.collection_exists(store.collection_name)
    assert waits == []


def test_t08_exhausted_transient_failure_stops_after_three_attempts(setup_store):
    store, client, waits = setup_store(["before"] * 4)
    with pytest.raises(ResponseHandlingException):
        store.upsert([embedding()])
    assert len(client.calls) == 3
    assert len(waits) == 2
    assert client.count(store.collection_name).count == 0


def test_t09_acknowledged_is_not_completed_and_is_not_replayed(setup_store, monkeypatch):
    store, client, waits = setup_store()
    calls = []

    def acknowledged(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(status=models.UpdateStatus.ACKNOWLEDGED)

    monkeypatch.setattr(client, "upsert", acknowledged)
    with pytest.raises(RuntimeError, match="hoàn tất"):
        store.upsert([embedding()])
    assert len(calls) == 1
    assert waits == []


def test_t10_incompatible_index_never_reaches_upsert(setup_store):
    store, client, _ = setup_store()
    store.upsert([embedding()])
    before = client.snapshot(store.collection_name)
    other = QdrantStore(
        client, collection_name=store.collection_name,
        config=replace(store.config, index_version="incompatible-v2"),
    )
    with pytest.raises(ValueError, match="phiên bản"):
        other.upsert([embedding()])
    assert len(client.calls) == 1
    assert client.snapshot(store.collection_name) == before


def test_t11_repeated_success_keeps_one_logical_point(setup_store):
    store, client, _ = setup_store()
    assert store.upsert([embedding()]) == 1
    before = client.snapshot(store.collection_name)
    assert store.upsert([embedding()]) == 1
    assert client.snapshot(store.collection_name) == before


def test_t12_last_permitted_attempt_can_succeed(setup_store):
    store, client, waits = setup_store([http_error(500), "before", None])
    assert store.upsert([embedding()]) == 1
    assert len(client.calls) == 3
    assert len(waits) == 2


def test_t13_wrapped_parse_error_is_not_a_network_retry(setup_store):
    error = ResponseHandlingException(ValueError("invalid response schema"))
    store, client, waits = setup_store([error])
    with pytest.raises(ResponseHandlingException):
        store.upsert([embedding()])
    assert len(client.calls) == 1
    assert waits == []


@pytest.mark.parametrize("code", [408, 429, 500, 502, 503, 504])
def test_t14_temporary_http_status_recovers_with_one_logical_effect(setup_store, code):
    store, client, _ = setup_store([http_error(code), None])
    assert store.upsert([embedding()]) == 1
    assert len(client.calls) == 2
    assert client.count(store.collection_name).count == 1


def test_t15_retry_exhaustion_after_write_does_not_claim_success(setup_store):
    store, client, waits = setup_store(["after"] * 4)
    with pytest.raises(ResponseHandlingException):
        store.upsert([embedding()])
    assert len(client.calls) == 3
    assert len(waits) == 2
    # Không nói "rollback": remote có thể đã ghi dù caller nhận lỗi.
    assert client.count(store.collection_name).count == 1


@pytest.mark.parametrize(
    "error", [httpx.ConnectError("injected"), httpx.ReadTimeout("injected")]
)
def test_t16_transport_failure_recovers(setup_store, error):
    store, client, _ = setup_store([ResponseHandlingException(error), None])
    assert store.upsert([embedding()]) == 1
    assert len(client.calls) == 2


def test_t17_empty_batch_has_no_remote_effect(setup_store):
    store, client, waits = setup_store()
    assert store.upsert([]) == 0
    assert client.calls == []
    assert not client.collection_exists(store.collection_name)
    assert waits == []


def test_t18_duplicate_asset_ids_are_rejected_before_remote_effect(setup_store):
    store, client, _ = setup_store()
    with pytest.raises(ValueError, match="Trùng"):
        store.upsert([embedding(), embedding()])
    assert client.calls == []
