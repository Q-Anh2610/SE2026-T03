"""Search service với encoder fixture và Qdrant memory; chưa phải smoke CLIP."""

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from qdrant_client import QdrantClient, models

from app.schemas.text_search import TextSearchCandidates, TextSearchFilters
from app.search.qdrant_store import IndexConfig, QdrantStore
from app.search.text_search import (
    SearchUnavailableError,
    TEXT_RETRIEVAL_CONFIG_VERSION,
    TextSearchService,
)


@pytest.fixture
def setup_service():
    client = QdrantClient(location=":memory:")
    config = IndexConfig(
        model_id="fixture-clip", model_revision="fixture-revision",
        dimension=3, preprocessing_version="fixture-rgb-l2",
        dataset_snapshot="fixture-snapshot", index_version="fixture-index",
    )
    store = QdrantStore(client, collection_name="text_fixtures", config=config)
    store.ensure_collection()
    encoder = SimpleNamespace(
        model_id=config.model_id, revision=config.model_revision,
        dimension=config.dimension, preprocessing_version=config.preprocessing_version,
        encode_text=Mock(return_value=[1.0, 0.0, 0.0]),
    )
    try:
        yield SimpleNamespace(
            client=client, store=store, encoder=encoder,
            service=TextSearchService(encoder, store),
        )
    finally:
        client.close()


def seed(setup, assets):
    setup.store.upsert([
        {"asset_id": asset_id, "metadata": {"asset_id": asset_id, **metadata},
         "vector": vector}
        for asset_id, vector, metadata in assets
    ])


def snapshot(setup):
    points, offset = setup.client.scroll(
        setup.store.collection_name, limit=1000, with_vectors=True,
    )
    assert offset is None
    return points


def test_sorts_cosine_keeps_negative_scores_and_returns_actual_versions(
    setup_service, monkeypatch,
):
    setup = setup_service
    seed(setup, [
        ("z", [1.0, 0.0, 0.0], {}),
        ("a", [1.0, 0.0, 0.0], {}),
        ("zero", [0.0, 1.0, 0.0], {}),
        ("negative", [-1.0, 0.0, 0.0], {}),
    ])
    before = snapshot(setup)
    query_spy = Mock(wraps=setup.client.query_points)
    monkeypatch.setattr(setup.client, "query_points", query_spy)
    monkeypatch.setattr(setup.store, "ensure_collection", Mock(side_effect=AssertionError))
    monkeypatch.setattr(setup.store, "upsert", Mock(side_effect=AssertionError))

    result = setup.service.search_text("  ghế gỗ  ", TextSearchFilters())

    assert isinstance(result, TextSearchCandidates)
    assert [hit.asset_id for hit in result.hits] == ["a", "z", "zero", "negative"]
    assert [hit.score for hit in result.hits] == pytest.approx([1.0, 1.0, 0.0, -1.0])
    assert result.versions.model_dump() == {
        "model_version": "fixture-clip@fixture-revision",
        "index_version": "fixture-index",
        "config_version": f"{TEXT_RETRIEVAL_CONFIG_VERSION}-k200",
        "dataset_snapshot": "fixture-snapshot",
    }
    setup.encoder.encode_text.assert_called_once_with("ghế gỗ")
    options = query_spy.call_args.kwargs
    assert options["using"] == setup.store.vector_name
    assert options["search_params"].exact is True
    assert options["score_threshold"] is None
    assert options["with_vectors"] is False
    assert snapshot(setup) == before


def test_filters_are_passed_to_qdrant_before_selecting_candidates(setup_service):
    setup = setup_service
    seed(setup, [
        ("wrong-category", [1.0, 0.0, 0.0], {"category": "table"}),
        ("no-metadata", [1.0, 0.0, 0.0], {}),
        ("match", [0.6, 0.8, 0.0], {
            "category": "chair", "license": "cc-by", "formats": ["obj", "glb"],
            "face_count": 100,
        }),
    ])
    result = setup.service.search_text("chair", TextSearchFilters(
        category="chair", license="cc-by", format="glb",
        face_count_min=100, face_count_max=100,
    ), candidate_limit=1)

    assert [hit.asset_id for hit in result.hits] == ["match"]
    assert result.hits[0].score == pytest.approx(0.6)
    assert result.versions.config_version.endswith("-k1")


def test_tie_break_includes_all_points_beyond_200_boundary(setup_service):
    setup = setup_service
    ids = [f"asset-{index:03d}" for index in range(205)]
    seed(setup, [(asset_id, [1.0, 0.0, 0.0], {}) for asset_id in reversed(ids)])

    first = setup.service.search_text("chair", TextSearchFilters())
    second = setup.service.search_text("chair", TextSearchFilters())

    assert [hit.asset_id for hit in first.hits] == ids[:200]
    assert second == first
    assert setup.client.count(setup.store.collection_name, exact=True).count == 205


def test_dedup_uses_best_score_before_limiting_unique_assets(setup_service):
    setup = setup_service
    seed(setup, [
        ("duplicate", [0.0, 1.0, 0.0], {}),
        ("other", [0.6, 0.8, 0.0], {}),
        ("third", [-1.0, 0.0, 0.0], {}),
    ])
    payload = next(p.payload for p in snapshot(setup) if p.payload["asset_id"] == "duplicate")
    setup.client.upsert(
        setup.store.collection_name,
        points=[models.PointStruct(
            id=index, vector={setup.store.vector_name: [1.0, 0.0, 0.0]},
            payload=deepcopy(payload),
        ) for index in range(5)],
        wait=True,
    )

    result = setup.service.search_text("chair", TextSearchFilters(), candidate_limit=2)

    assert [hit.asset_id for hit in result.hits] == ["duplicate", "other"]
    assert result.hits[0].score == pytest.approx(1.0)


@pytest.mark.parametrize("populated", [False, True])
def test_empty_results_still_carry_actual_execution_versions(setup_service, populated):
    setup = setup_service
    if populated:
        seed(setup, [("chair", [1.0, 0.0, 0.0], {"category": "chair"})])

    result = setup.service.search_text("chair", TextSearchFilters(category="absent"))

    assert result.hits == []
    assert result.versions.dataset_snapshot == setup.store.config.dataset_snapshot
    setup.encoder.encode_text.assert_called_once()


def test_missing_collection_is_unavailable_and_is_not_created(setup_service, monkeypatch):
    setup = setup_service
    setup.client.delete_collection(setup.store.collection_name)
    create_spy = Mock(wraps=setup.client.create_collection)
    monkeypatch.setattr(setup.client, "create_collection", create_spy)

    with pytest.raises(SearchUnavailableError):
        setup.service.search_text("chair", TextSearchFilters())

    create_spy.assert_not_called()
    setup.encoder.encode_text.assert_not_called()
    assert not setup.client.collection_exists(setup.store.collection_name)


@pytest.mark.parametrize("kind", ["dimension", "distance", "named-vector"])
def test_incompatible_collection_is_rejected_before_encoding(setup_service, kind):
    setup = setup_service
    setup.client.delete_collection(setup.store.collection_name)
    setup.client.create_collection(
        setup.store.collection_name,
        vectors_config={
            "other" if kind == "named-vector" else setup.store.vector_name:
                models.VectorParams(
                    size=4 if kind == "dimension" else 3,
                    distance=models.Distance.DOT if kind == "distance" else models.Distance.COSINE,
                )
        },
    )

    with pytest.raises(SearchUnavailableError):
        setup.service.search_text("chair", TextSearchFilters())

    setup.encoder.encode_text.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value"),
    [("model_id", "other"), ("revision", "other"), ("dimension", 4),
     ("preprocessing_version", "other")],
)
def test_incompatible_encoder_is_rejected(setup_service, field, value):
    setup = setup_service
    setattr(setup.encoder, field, value)

    with pytest.raises(SearchUnavailableError, match="chưa sẵn sàng") as error:
        setup.service.search_text("chair", TextSearchFilters())

    assert error.value.reason == "incompatible_encoder"
    setup.encoder.encode_text.assert_not_called()


@pytest.mark.parametrize("field", ["index_version", "dataset_snapshot"])
def test_mock_execution_versions_are_not_advertised_as_real(setup_service, field):
    setup = setup_service
    setup.store.config = replace(setup.store.config, **{field: "mock-placeholder"})

    with pytest.raises(SearchUnavailableError) as error:
        setup.service.search_text("chair", TextSearchFilters())

    assert error.value.reason == "invalid_index_versions"
    setup.encoder.encode_text.assert_not_called()


@pytest.mark.parametrize("change", ["snapshot", "model-version", "index-version", "asset-id"])
def test_corrupt_point_payload_is_not_returned_or_silently_ignored(setup_service, change):
    setup = setup_service
    seed(setup, [("chair", [1.0, 0.0, 0.0], {})])
    point = snapshot(setup)[0]
    payload = deepcopy(point.payload)
    if change == "snapshot":
        payload["_index"]["dataset_snapshot"] = "other"
    elif change == "model-version":
        payload["model_version"] = "other"
    elif change == "index-version":
        payload["index_version"] = "other"
    else:
        payload["asset_id"] = "../invalid"
    setup.client.overwrite_payload(setup.store.collection_name, payload, points=[point.id])

    with pytest.raises(SearchUnavailableError):
        setup.service.search_text("chair", TextSearchFilters())


@pytest.mark.parametrize("method", ["get_collection", "count", "query_points"])
def test_qdrant_error_is_typed_and_does_not_expose_raw_exception(
    setup_service, monkeypatch, method,
):
    setup = setup_service
    seed(setup, [("chair", [1.0, 0.0, 0.0], {})])
    monkeypatch.setattr(
        setup.client, method, Mock(side_effect=RuntimeError("sensitive connection detail")),
    )

    with pytest.raises(SearchUnavailableError) as error:
        setup.service.search_text("chair", TextSearchFilters())

    assert "sensitive" not in str(error.value)
    assert error.value.__suppress_context__ is True


@pytest.mark.parametrize("failure", [RuntimeError("model unavailable"), OSError("weights unavailable")])
def test_model_failure_is_unavailable_including_empty_collection(setup_service, failure):
    setup = setup_service
    setup.encoder.encode_text.side_effect = failure

    with pytest.raises(SearchUnavailableError) as error:
        setup.service.search_text("chair", TextSearchFilters())

    assert error.value.reason == "encoder_unavailable"


@pytest.mark.parametrize(
    "vector",
    [None, [1.0, 0.0], [0.0, 0.0, 0.0], [2.0, 0.0, 0.0],
     [True, 0.0, 0.0], [float("nan"), 0.0, 0.0], [float("inf"), 0.0, 0.0]],
)
def test_invalid_query_vector_is_unavailable(setup_service, vector):
    setup = setup_service
    setup.encoder.encode_text.return_value = vector

    with pytest.raises(SearchUnavailableError) as error:
        setup.service.search_text("chair", TextSearchFilters())

    assert error.value.reason == "invalid_query_vector"


@pytest.mark.parametrize("query", [" ", "x" * 501, None, 12])
def test_invalid_query_fails_validation_before_encoding(setup_service, query):
    with pytest.raises(ValidationError):
        setup_service.service.search_text(query, TextSearchFilters())

    setup_service.encoder.encode_text.assert_not_called()


@pytest.mark.parametrize("limit", [0, -1, 201, True, 1.5, "2"])
def test_candidate_limit_is_strict_and_bounded(setup_service, limit):
    with pytest.raises(ValueError):
        setup_service.service.search_text("chair", TextSearchFilters(), candidate_limit=limit)

    setup_service.encoder.encode_text.assert_not_called()


def test_invalid_filter_is_not_ignored_by_service(setup_service):
    with pytest.raises(ValidationError):
        setup_service.service.search_text("chair", {"unknown": "value"})

    setup_service.encoder.encode_text.assert_not_called()


def test_incomplete_count_query_window_is_unavailable(setup_service, monkeypatch):
    setup = setup_service
    seed(setup, [("chair", [1.0, 0.0, 0.0], {})])
    monkeypatch.setattr(setup.client, "count", Mock(return_value=SimpleNamespace(count=2)))

    with pytest.raises(SearchUnavailableError) as error:
        setup.service.search_text("chair", TextSearchFilters())

    assert error.value.reason == "index_changed_or_incomplete"


@pytest.mark.parametrize("score", [float("nan"), float("inf"), 1.1, -1.1, True])
def test_invalid_cosine_score_is_unavailable(setup_service, monkeypatch, score):
    setup = setup_service
    seed(setup, [("chair", [1.0, 0.0, 0.0], {})])
    payload = snapshot(setup)[0].payload
    monkeypatch.setattr(setup.client, "query_points", Mock(return_value=SimpleNamespace(
        points=[SimpleNamespace(payload=payload, score=score)],
    )))

    with pytest.raises(SearchUnavailableError) as error:
        setup.service.search_text("chair", TextSearchFilters())

    assert error.value.reason == "invalid_cosine_score"


@pytest.mark.parametrize(("score", "expected"), [(1.0000001, 1.0), (-1.0000001, -1.0)])
def test_only_small_cosine_roundoff_is_clamped(setup_service, monkeypatch, score, expected):
    setup = setup_service
    seed(setup, [("chair", [1.0, 0.0, 0.0], {})])
    payload = snapshot(setup)[0].payload
    monkeypatch.setattr(setup.client, "query_points", Mock(return_value=SimpleNamespace(
        points=[SimpleNamespace(payload=payload, score=score)],
    )))

    result = setup.service.search_text("chair", TextSearchFilters())

    assert result.hits[0].score == expected
