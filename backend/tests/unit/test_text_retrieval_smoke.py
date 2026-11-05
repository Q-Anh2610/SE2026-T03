"""Test helpers smoke với ảnh nhỏ, vectors fixture và Qdrant memory."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image
import pytest
from qdrant_client import QdrantClient, models

from app.schemas.text_search import TextSearchFilters
from app.search.qdrant_store import IndexConfig, QdrantStore
from app.search.smoke import (
    READY_MANIFEST, SOURCE_MANIFEST, SmokeCheckError, audit_index, digest,
    handoff_file, load_inputs, matches, output_directory, run_queries, smoke_cases,
)
from app.search.retrieval_config import RetrievalConfig
from app.search.text_search import TextSearchService


@pytest.fixture
def handoff(tmp_path):
    source, ready = [], []
    for index in range(2):
        metadata = {
            "asset_id": f"asset-{index}", "category": "chair" if index == 0 else None,
            "license": "by", "formats": ["obj", "glb"],
            "face_count": 100 if index == 0 else None,
        }
        relative = f"data/raw/objaverse/previews/{index}.png"
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with Image.new("RGB", (2, 2), (30 + index, 50, 80)) as image:
            image.save(path)
        source.append(metadata)
        ready.append({"metadata": deepcopy(metadata), "image_path": relative,
                      "preview_sha256": digest(path)})
    for name, content in ((SOURCE_MANIFEST, source), (READY_MANIFEST, ready)):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content), encoding="utf-8")
    reference = {"input": {
        "manifest_sha256": digest(tmp_path / SOURCE_MANIFEST),
        "ready_manifest_sha256": digest(tmp_path / READY_MANIFEST),
        "asset_count": 2,
    }}
    return tmp_path, source, ready, reference


def test_loads_only_handoff_snapshot_and_verifies_images(handoff):
    root, source, _, reference = handoff

    metadata, receipt = load_inputs(root, reference)

    assert metadata == {item["asset_id"]: item for item in source}
    assert receipt["asset_count"] == receipt["distinct_readable_previews"] == 2
    assert receipt["manifest_sha256"] == reference["input"]["manifest_sha256"]


@pytest.mark.parametrize("target", [SOURCE_MANIFEST, READY_MANIFEST, "data/raw/objaverse/previews/0.png"])
def test_changed_source_ready_or_preview_is_rejected(handoff, target):
    root, _, _, reference = handoff
    (root / target).write_bytes(b"changed")

    with pytest.raises(SmokeCheckError):
        load_inputs(root, reference)


@pytest.mark.parametrize("kind", ["metadata", "duplicate-id", "duplicate-preview", "wrong-count"])
def test_ready_semantic_integrity_is_checked_even_if_hash_is_updated(handoff, kind):
    root, _, ready, reference = handoff
    if kind == "metadata":
        ready[0]["metadata"]["license"] = "changed"
    elif kind == "duplicate-id":
        ready[1]["metadata"] = deepcopy(ready[0]["metadata"])
    elif kind == "duplicate-preview":
        ready[1]["image_path"] = ready[0]["image_path"]
        ready[1]["preview_sha256"] = ready[0]["preview_sha256"]
    else:
        ready.pop()
    (root / READY_MANIFEST).write_text(json.dumps(ready), encoding="utf-8")
    reference["input"]["ready_manifest_sha256"] = digest(root / READY_MANIFEST)

    with pytest.raises(SmokeCheckError):
        load_inputs(root, reference)


@pytest.mark.parametrize("path", ["../outside.png", "C:/outside.png", "/outside.png", "data\\file.png", "./file.png", None])
def test_handoff_path_cannot_escape_package(tmp_path, path):
    with pytest.raises(SmokeCheckError):
        handoff_file(tmp_path, path)


@pytest.fixture
def indexed():
    client = QdrantClient(location=":memory:")
    config = IndexConfig("fixture-clip", "fixture-revision", 3, "fixture-rgb-l2", "fixture", "fixture-index")
    store = QdrantStore(client, collection_name="smoke_fixtures", config=config)
    metadata = {
        "a": {"asset_id": "a", "category": "chair", "license": "by", "formats": ["glb"], "face_count": 100},
        "b": {"asset_id": "b", "category": None, "license": None, "formats": [], "face_count": None},
    }
    store.upsert([{"asset_id": aid, "metadata": row, "vector": [1.0, 0.0, 0.0]}
                  for aid, row in metadata.items()])
    try:
        yield store, metadata
    finally:
        client.close()


def test_read_only_audit_is_repeatable_and_fingerprints_all_vectors(indexed):
    store, metadata = indexed

    first = audit_index(store, metadata)
    second = audit_index(store, metadata)

    assert first == second
    assert first["exact_point_count"] == first["unique_asset_ids"] == 2
    assert len(first["point_payload_vector_sha256"]) == 64


@pytest.mark.parametrize("kind", ["vector", "payload", "duplicate", "missing"])
def test_audit_detects_changed_vectors_payload_duplicates_or_missing_points(indexed, kind):
    store, metadata = indexed
    before = audit_index(store, metadata)
    points, _ = store.client.scroll(store.collection_name, with_vectors=True)
    point = points[0]
    if kind == "vector":
        store.client.update_vectors(store.collection_name, points=[models.PointVectors(
            id=point.id, vector={store.vector_name: [0.0, 1.0, 0.0]},
        )], wait=True)
        assert audit_index(store, metadata) != before
        return
    if kind == "payload":
        store.client.set_payload(store.collection_name, {"license": "wrong"}, points=[point.id])
    elif kind == "duplicate":
        store.client.upsert(store.collection_name, [models.PointStruct(
            id=123, vector=point.vector, payload=point.payload,
        )], wait=True)
    else:
        store.client.delete(store.collection_name, points_selector=[point.id], wait=True)

    with pytest.raises(SmokeCheckError):
        audit_index(store, metadata)


def test_live_cases_have_all_filters_and_only_empty_case_has_no_match(indexed):
    _, metadata = indexed
    cases = smoke_cases(metadata)

    assert len(cases) == 10
    for label, query, raw_filters in cases:
        assert 1 <= len(query.strip()) <= 500
        eligible = [row for row in metadata.values() if matches(row, TextSearchFilters(**raw_filters))]
        assert bool(eligible) == (label != "empty")


def fixture_encoder(store):
    return SimpleNamespace(
        model_id=store.config.model_id, revision=store.config.model_revision,
        dimension=store.config.dimension, preprocessing_version=store.config.preprocessing_version,
        encode_text=Mock(return_value=[1.0, 0.0, 0.0]),
        model=SimpleNamespace(config=SimpleNamespace(
            text_config=SimpleNamespace(max_position_embeddings=77),
        )),
        processor=SimpleNamespace(tokenizer=lambda text, **kwargs: {
            "input_ids": list(range(len(text.split()) + 2)),
        }),
    )


def test_query_runner_checks_all_cases_and_does_not_write_index(indexed, monkeypatch):
    store, metadata = indexed
    encoder = fixture_encoder(store)
    before = audit_index(store, metadata)
    for method in (
        "upsert", "delete", "set_payload", "overwrite_payload", "update_vectors",
        "delete_vectors", "create_collection", "delete_collection", "recreate_collection",
    ):
        monkeypatch.setattr(store.client, method, Mock(side_effect=AssertionError))

    reports = run_queries(TextSearchService(encoder, store), encoder, metadata, RetrievalConfig())

    assert len(reports) == 10
    assert reports[0]["returned_count"] == 2
    assert next(case for case in reports if case["case"] == "empty")["returned_count"] == 0
    assert reports[-1]["truncated"] is True
    assert all(case["versions"]["model_version"].startswith("fixture-clip@") for case in reports)
    assert audit_index(store, metadata) == before


def test_query_runner_rejects_fake_empty_success(indexed):
    store, metadata = indexed
    service = SimpleNamespace(store=store, search_text=Mock(return_value=SimpleNamespace(hits=[])))

    with pytest.raises(SmokeCheckError, match="query_filter_or_dedup_mismatch"):
        run_queries(service, fixture_encoder(store), metadata, RetrievalConfig())


def test_query_runner_accepts_capped_results_when_more_assets_match(indexed):
    store, metadata = indexed
    encoder = fixture_encoder(store)

    reports = run_queries(
        TextSearchService(encoder, store), encoder, metadata, RetrievalConfig.for_limit(1),
    )

    assert reports[0]["expected_asset_count"] == 2
    assert reports[0]["expected_returned_count"] == reports[0]["returned_count"] == 1
    assert next(case for case in reports if case["case"] == "empty")["returned_count"] == 0


@pytest.mark.parametrize(("score_delta", "passes"), [(1e-15, True), (1e-9, False)])
def test_repeat_query_allows_only_small_score_roundoff(indexed, monkeypatch, score_delta, passes):
    store, metadata = indexed
    encoder = fixture_encoder(store)
    service = TextSearchService(encoder, store)
    search_text = service.search_text
    reports = []
    case_count = len(smoke_cases(metadata))

    def query_with_repeat_drift(*args, **kwargs):
        result = search_text(*args, **kwargs)
        if len(reports) == case_count:
            hit = result.hits[0]
            return result.model_copy(update={"hits": [hit.model_copy(update={"score": hit.score - score_delta})]})
        return result

    monkeypatch.setattr(service, "search_text", query_with_repeat_drift)
    config = RetrievalConfig.for_limit(1)
    if passes:
        run_queries(service, encoder, metadata, config, reports=reports)
    else:
        with pytest.raises(SmokeCheckError, match="repeat_query_changed"):
            run_queries(service, encoder, metadata, config, reports=reports)

    assert reports[0]["repeat"]["ordered_asset_ids_equal"] is True
    assert reports[0]["repeat"]["max_score_abs_delta"] == pytest.approx(score_delta, abs=1e-16)


@pytest.mark.parametrize(
    ("filters", "matches_a", "matches_b"),
    [
        ({}, True, True),
        ({"category": "chair"}, True, False),
        ({"category": "Chair"}, False, False),
        ({"license": "by"}, True, False),
        ({"format": "glb"}, True, False),
        ({"face_count_min": 100, "face_count_max": 100}, True, False),
        ({"face_count_min": 101}, False, False),
        ({"category": "chair", "license": "different"}, False, False),
    ],
)
def test_independent_metadata_filter_checker(indexed, filters, matches_a, matches_b):
    _, metadata = indexed
    parsed = TextSearchFilters(**filters)

    assert matches(metadata["a"], parsed) is matches_a
    assert matches(metadata["b"], parsed) is matches_b


def test_runtime_output_directory_is_unique_and_refuses_overwrite(tmp_path):
    first = output_directory(tmp_path)
    second = output_directory(tmp_path)

    assert first != second
    assert first.is_relative_to(tmp_path / "data/processed/issue60")
    with pytest.raises(SmokeCheckError, match="output_already_exists"):
        output_directory(tmp_path, first)


@pytest.mark.parametrize("path", ["../outside", "docs/evidence/test", "data/processed/issue60"])
def test_runtime_output_must_stay_in_dedicated_subdirectory(tmp_path, path):
    with pytest.raises(SmokeCheckError):
        output_directory(tmp_path, Path(path))
