"""Ảnh fixture + Qdrant thật in-memory; không phải benchmark model."""

from copy import deepcopy
from dataclasses import replace
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from PIL import Image
from pydantic import ValidationError
from qdrant_client import QdrantClient, models

from app.schemas.text_search import TextSearchFilters
from app.search.image_search import (ImageSearchService, ImageRetrievalConfig,
    InvalidQueryImageError, SearchUnavailableError, decode_query_image, MAX_IMAGE_BYTES)
from app.search.qdrant_store import IndexConfig, QdrantStore


def image_bytes(mode="RGB", fmt="PNG", size=(3, 2)):
    output = BytesIO()
    with Image.new(mode, size) as image:
        image.save(output, format=fmt)
    return output.getvalue()


@pytest.fixture
def setup():
    client = QdrantClient(":memory:")
    config = IndexConfig("fixture", "b" * 40, 3, "rgb-l2-v1", "fixture-snapshot", "fixture-index")
    store = QdrantStore(client, collection_name="image_fixture", config=config)
    store.ensure_collection()
    encoder = SimpleNamespace(model_id=config.model_id, revision=config.model_revision,
        dimension=3, preprocessing_version=config.preprocessing_version,
        encode_images=Mock(return_value=[[1., 0., 0.]]))
    yield SimpleNamespace(client=client, store=store, encoder=encoder,
                          service=ImageSearchService(encoder, store))
    client.close()


def seed(setup, rows):
    setup.store.upsert([dict(asset_id=aid, metadata={"asset_id": aid, **metadata}, vector=vector)
                        for aid, vector, metadata in rows])


@pytest.mark.parametrize("mode,fmt", [("RGB", "JPEG"), ("L", "PNG"), ("RGBA", "PNG"), ("P", "PNG")])
def test_decodes_rgb_and_keeps_original_bytes(mode, fmt):
    content = image_bytes(mode, fmt)
    before = bytes(content)
    with decode_query_image(content) as decoded:
        assert decoded.mode == "RGB" and decoded.size == (3, 2)
    assert content == before


@pytest.mark.parametrize("content,code", [
    (b"", "INVALID_IMAGE"), (None, "INVALID_IMAGE"), ("url", "INVALID_IMAGE"),
    (b"bad", "INVALID_IMAGE"), (b"x" * (MAX_IMAGE_BYTES + 1), "IMAGE_TOO_LARGE"),
    (image_bytes(fmt="GIF"), "UNSUPPORTED_IMAGE"),
    (image_bytes(size=(4097, 1)), "IMAGE_DIMENSIONS_EXCEEDED"),
    (image_bytes(fmt="JPEG")[:-20], "INVALID_IMAGE"),
    (image_bytes()[:-20], "INVALID_IMAGE"),
], ids=["empty", "none", "url", "garbage", "oversized", "gif", "dimensions", "truncated-jpeg", "truncated-png"])
def test_bad_image_is_typed_before_model_or_index(setup, content, code):
    with pytest.raises(InvalidQueryImageError) as error:
        setup.service.search_image(content, TextSearchFilters())
    assert error.value.code == code
    setup.encoder.encode_images.assert_not_called()


def test_accepts_dimension_boundary():
    with decode_query_image(image_bytes(size=(4096, 1))) as decoded:
        assert decoded.size == (4096, 1)


def test_exact_retrieval_is_deterministic_and_read_only(setup, monkeypatch):
    seed(setup, [("z", [1., 0., 0.], {}), ("a", [1., 0., 0.], {}),
                 ("negative", [-1., 0., 0.], {})])
    before = setup.client.scroll(setup.store.collection_name, with_vectors=True)[0]
    spy = Mock(wraps=setup.client.query_points)
    monkeypatch.setattr(setup.client, "query_points", spy)
    monkeypatch.setattr(setup.store, "upsert", Mock(side_effect=AssertionError))
    first = setup.service.search_image(image_bytes(), TextSearchFilters())
    second = setup.service.search_image(image_bytes(), TextSearchFilters())
    assert first == second
    assert [h.asset_id for h in first.hits] == ["a", "z", "negative"]
    assert [h.score for h in first.hits] == pytest.approx([1, 1, -1])
    assert first.versions.config_version == "image-exact-all-filtered-rgb-v1-k200"
    assert first.versions.model_version == "fixture@" + "b" * 40
    assert setup.client.scroll(setup.store.collection_name, with_vectors=True)[0] == before
    assert spy.call_args.kwargs["search_params"].exact is True
    assert spy.call_args.kwargs["score_threshold"] is None


def test_filters_before_topk_and_empty_versions(setup):
    seed(setup, [("wrong", [1., 0., 0.], {"category": "table"}),
                 ("right", [0.6, 0.8, 0.], {"category": "chair", "license": "CC", "formats": ["glb"], "face_count": 10})])
    result = setup.service.search_image(image_bytes(), TextSearchFilters(
        category="chair", license="CC", format="glb", face_count_min=10, face_count_max=10), candidate_limit=1)
    assert [h.asset_id for h in result.hits] == ["right"]
    empty = setup.service.search_image(image_bytes(), TextSearchFilters(category="absent"))
    assert empty.hits == [] and empty.versions.dataset_snapshot == "fixture-snapshot"


def test_ties_past_candidate_boundary_and_dedup(setup):
    ids = [f"asset-{i:03d}" for i in range(205)]
    seed(setup, [(aid, [1., 0., 0.], {}) for aid in reversed(ids)])
    payload = setup.client.scroll(setup.store.collection_name, limit=1)[0][0].payload
    setup.client.upsert(setup.store.collection_name, points=[models.PointStruct(
        id=i, vector={setup.store.vector_name: [1., 0., 0.]}, payload=deepcopy(payload)) for i in range(5)])
    result = setup.service.search_image(image_bytes(), TextSearchFilters())
    assert [h.asset_id for h in result.hits] == ids[:200]


@pytest.mark.parametrize("field,value", [("model_id", "other"), ("revision", "c" * 40),
    ("dimension", 4), ("preprocessing_version", "different")])
def test_incompatible_encoder_before_inference(setup, field, value):
    setattr(setup.encoder, field, value)
    with pytest.raises(SearchUnavailableError) as error:
        setup.service.search_image(image_bytes(), TextSearchFilters())
    assert error.value.reason == "incompatible_encoder"
    setup.encoder.encode_images.assert_not_called()


@pytest.mark.parametrize("field", ["index_version", "dataset_snapshot"])
def test_collection_version_mismatch(setup, field):
    setup.store.config = replace(setup.store.config, **{field: "changed"})
    setup.store.vector_name = QdrantStore(setup.client, collection_name=setup.store.collection_name,
                                        config=setup.store.config).vector_name
    with pytest.raises(SearchUnavailableError):
        setup.service.search_image(image_bytes(), TextSearchFilters())
    setup.encoder.encode_images.assert_not_called()


def test_missing_collection_does_not_create(setup):
    setup.client.delete_collection(setup.store.collection_name)
    with pytest.raises(SearchUnavailableError):
        setup.service.search_image(image_bytes(), TextSearchFilters())
    assert not setup.client.collection_exists(setup.store.collection_name)


@pytest.mark.parametrize("vectors", [[], None, [[1., 0.]], [[0., 0., 0.]],
    [[float("nan"), 0., 0.]], [[True, 0., 0.]], [[2., 0., 0.]], [[1., 0., 0.], [1., 0., 0.]]])
def test_invalid_encoder_output_is_unavailable(setup, vectors):
    setup.encoder.encode_images.return_value = vectors
    with pytest.raises(SearchUnavailableError):
        setup.service.search_image(image_bytes(), TextSearchFilters())


@pytest.mark.parametrize("limit", [0, 201, True, "2", 1.5])
def test_strict_limit(setup, limit):
    with pytest.raises(ValueError):
        setup.service.search_image(image_bytes(), TextSearchFilters(), candidate_limit=limit)
    setup.encoder.encode_images.assert_not_called()


def test_unknown_filter_not_ignored(setup):
    with pytest.raises(ValidationError):
        setup.service.search_image(image_bytes(), {"unknown": 1})
    setup.encoder.encode_images.assert_not_called()


def test_invalid_config_version():
    with pytest.raises(ValidationError):
        ImageRetrievalConfig(candidate_limit=10)
