"""Service #91: encoder fixtures, Qdrant thật; không tải model hoặc đọc benchmark."""

from contextlib import ExitStack, closing
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import numpy as np
from pydantic import ValidationError
from qdrant_client import QdrantClient

from app.embedding.clip_encoder import MODEL_ID as CLIP_MODEL, MODEL_REVISION as CLIP_REVISION, PREPROCESSING_VERSION as CLIP_PREPROCESSING
from app.embedding.e5_encoder import MODEL_ID, MODEL_REVISION, PREPROCESSING_VERSION
from app.search.e5_index import SERIALIZATION, SNAPSHOT, build_metadata_index, digest, json_bytes, load_metadata_corpus
from app.search.experimental_text_search import (
    CLIPTextSource, E5MetadataSearchService, E5RetrievalConfig, ExperimentalFusionService,
    RankedCandidate,
)
from app.search.image_index_manifest import ImageIndexManifest
from app.search.image_search import ImageRetrievalConfig
from app.search.index_manifest import IndexManifest
from app.search.qdrant_store import IndexConfig, QdrantStore, index_vector_name
from app.search.retrieval_config import RetrievalConfig
from app.search.rrf import CLIP_SOURCE, E5_SOURCE, RRFConfig
from app.search.vector_search import SearchUnavailableError


class FixtureImageProcessor:
    def to_dict(self):
        return {"fixture": True}


class FixtureEncoder:
    def __init__(self, *, e5):
        self.dimension = 384 if e5 else 512
        self.model_id = MODEL_ID if e5 else CLIP_MODEL
        self.revision = self.tokenizer_revision = MODEL_REVISION if e5 else CLIP_REVISION
        self.preprocessing_version = PREPROCESSING_VERSION if e5 else CLIP_PREPROCESSING
        self.max_text_tokens = 512 if e5 else 77
        self.tokenizer = SimpleNamespace(is_fast=True, padding_side="right", truncation_side="right")
        self.processor = SimpleNamespace(image_processor=FixtureImageProcessor())
        self.model = SimpleNamespace(config=SimpleNamespace(text_config=SimpleNamespace(max_position_embeddings=77)))
        self.queries = []

    def encode_text(self, query):
        self.queries.append(query)
        return [1.0] + [0.0] * (self.dimension - 1)

    def encode_passages(self, passages, *, batch_size):
        return [[float(i % 3 == axis) for axis in range(3)] + [0.0] * 381 for i, _ in enumerate(passages)]


@pytest.fixture
def pair(tmp_path, request):
    records = [{"asset_id": f"asset_{i:03d}", "name": f"Chair {i}", "description": None,
                "tags": [], "category": None if i == 199 else ("chair" if i % 2 == 0 else "table"),
                "license": "cc-by" if i % 4 == 0 else "cc0", "formats": ["obj"] if i % 3 == 0 else ["glb"],
                "face_count": None if i % 5 == 0 else i * 10} for i in range(200)]
    source = json_bytes(records)
    rows = [{"asset_id": row["asset_id"], "passage": row["name"] + ("\n" + row["category"] if row["category"] else "")} for row in records]
    corpus_raw = b"".join(json_bytes(row) for row in rows)
    corpus_manifest = {
        "snapshot": SNAPSHOT, "source_path": "data/manifests/objaverse_200.json",
        "source_hash_basis": "raw Git blob bytes", "source_manifest_sha256": digest(source),
        "source_commit": "a" * 40, "corpus_file": "corpus.jsonl", "corpus_sha256": digest(corpus_raw),
        "recipe_version": "e5-metadata-passage-v1-draft", "fields": ["name", "description", "tags", "category"],
        "text_policy": "Python str.split then join with one ASCII space",
        "tags_policy": "clean; drop empty; exact dedup; preserve first order", "tags_separator": ", ",
        "field_separator": "\n", "empty_policy": "omit empty fields; reject empty passage",
        "prefix_in_corpus": False, "serialization": SERIALIZATION, "asset_count": 200,
        "nonempty_passage_count": 200, "errors": [], "checkout_matches_source_json": True,
        "asset_ids": [row["asset_id"] for row in rows],
    }
    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir()
    (corpus_root / "corpus.jsonl").write_bytes(corpus_raw)
    (corpus_root / "manifest.json").write_bytes(json_bytes(corpus_manifest))
    corpus = load_metadata_corpus(corpus_root, source, expected_source_sha256=digest(source),
        expected_corpus_sha256=digest(corpus_raw), expected_recipe_version=corpus_manifest["recipe_version"])
    e5_encoder, clip_encoder = FixtureEncoder(e5=True), FixtureEncoder(e5=False)
    dense = getattr(request, "param", "text") == "dense"
    def dense_vector(dimension):
        return (np.full(dimension, 1 / np.sqrt(dimension), dtype=np.float32)
                * np.float32(1 - 2**-21)).tolist()
    if dense:
        e5_encoder.encode_passages = lambda passages, **kwargs: [dense_vector(384) for _ in passages]
    e5_root, clip_root = tmp_path / "e5", tmp_path / "clip"
    build_metadata_index(e5_encoder, corpus, e5_root, batch_size=16, code_commit="b" * 40,
        working_tree_dirty=True, module_sha256={"fixture.py": "c" * 64}, package_versions={"encoder": "fixture"})
    clip_root.mkdir()
    (clip_root / "source.json").write_bytes(source)
    ready = [{"metadata": row, "image_path": f"previews/{i}.png", "preview_sha256": "e" * 64} for i, row in enumerate(records)]
    (clip_root / "ready.json").write_bytes(json_bytes(ready))
    config = IndexConfig(CLIP_MODEL, CLIP_REVISION, 512, CLIP_PREPROCESSING,
        f"{SNAPSHOT}-sha256:{digest(source)}", "fixture-clip-index")
    now = datetime.now(timezone.utc)
    common = dict(created_at_utc=now, observed_at_utc=now, index_config=asdict(config),
        collection="clip", vector_name=index_vector_name(config), processor_revision=CLIP_REVISION,
        source_manifest="source.json", source_manifest_sha256=digest(source), ready_manifest="ready.json",
        ready_manifest_sha256=digest(json_bytes(ready)), asset_count=200, point_count=200,
        code_commit="b" * 40, working_tree_dirty=True, module_sha256={"fixture.py": "c" * 64})
    if getattr(request, "param", "text") == "image":
        manifest = ImageIndexManifest(**common, processor_class="FixtureImageProcessor",
            processor_config={"fixture": True}, package_versions={"encoder": "fixture"},
            snapshot_confirmation="fixture", retrieval_config=ImageRetrievalConfig())
    else:
        manifest = IndexManifest(**common, tokenizer_revision=CLIP_REVISION,
            max_text_tokens=77, retrieval_config=RetrievalConfig())
    (clip_root / "index-manifest.json").write_bytes(json_bytes(manifest.model_dump(mode="json")))
    with ExitStack() as stack:
        e5_client = stack.enter_context(closing(QdrantClient(path=str(e5_root / "qdrant"))))
        clip_client = stack.enter_context(closing(QdrantClient(location=":memory:")))
        clip_store = QdrantStore(clip_client, collection_name="clip", config=config)
        clip_store.upsert([{"asset_id": row["asset_id"], "metadata": row,
            "vector": dense_vector(512) if dense else [float((i + 1) % 3 == axis) for axis in range(3)] + [0.0] * 509}
            for i, row in enumerate(records)])
        clip = CLIPTextSource(clip_encoder, clip_client, clip_root)
        e5 = E5MetadataSearchService(e5_encoder, e5_client, e5_root)
        yield SimpleNamespace(clip=clip, e5=e5, service=ExperimentalFusionService(clip, e5),
            records=records, clip_root=clip_root, e5_root=e5_root,
            clip_client=clip_client, e5_client=e5_client, clip_encoder=clip_encoder, e5_encoder=e5_encoder)


def config(**changes):
    return RRFConfig(**{**dict(rank_constant=60, clip_candidate_limit=200, e5_candidate_limit=200, cutoff=200), **changes})


def test_e5_only_uses_shared_exact_retrieval_and_records_versions(pair):
    result = pair.e5.search_text("  ghế gỗ  ", {}, candidate_limit=3)
    assert result.source == E5_SOURCE and result.score_type == "cosine"
    assert [h.asset_id for h in result.hits] == ["asset_000", "asset_003", "asset_006"]
    assert [h.rank for h in result.hits] == [1, 2, 3]
    assert [h.score for h in result.hits] == [1.0] * 3
    assert result.provenance.model_revision == MODEL_REVISION
    assert result.provenance.corpus_sha256 == pair.e5.manifest.corpus_sha256
    assert result.provenance.config_version.endswith("-k3")
    assert pair.e5_encoder.queries == ["ghế gỗ"]


@pytest.mark.parametrize("pair", ["text", "image"], indirect=True)
def test_clip_uses_existing_service_on_both_manifest_types(pair):
    result = pair.clip.search_text("chair", {}, candidate_limit=2)
    assert result.source == CLIP_SOURCE
    assert [h.asset_id for h in result.hits] == ["asset_002", "asset_005"]
    assert result.provenance.config_version == "clip-text-exact-all-filtered-v1-k2"


def test_same_and_filters_before_topk_and_full_source_window(pair):
    filters = {"category": "chair", "license": "cc0", "format": "glb", "face_count_min": 20, "face_count_max": 300}
    result = pair.service.search_text("chair", filters, config=config(clip_candidate_limit=1, e5_candidate_limit=1, cutoff=2))
    expected = {row["asset_id"] for row in pair.records if row["category"] == "chair" and row["license"] == "cc0"
                and "glb" in row["formats"] and row["face_count"] is not None and 20 <= row["face_count"] <= 300}
    assert expected
    assert all({h.asset_id for h in ranking.hits} == expected for ranking in result.raw_rankings)
    assert all(ranking.filters == filters for ranking in result.raw_rankings)
    assert all(source.candidate_limit == 200 for source in result.sources)
    assert len(result.hits) <= 2 and len({h.asset_id for h in result.hits}) == len(result.hits)
    assert result.score_type == "rrf" and result.filters == filters
    assert result.parameters["source_retrieval_window"] == 200


@pytest.mark.parametrize("filters", [{"category": "absent"}, {"face_count_max": 0}, {"format": "fbx"}])
def test_successful_empty_streams_are_valid_not_unavailable(pair, filters):
    result = pair.service.search_text("chair", filters, config=config())
    assert result.hits == ()
    assert all(r.hits == () for r in result.raw_rankings)
    assert len(result.sources) == 2


def test_null_metadata_matches_only_without_corresponding_filter(pair):
    all_hits = pair.e5.search_text("chair", {}).hits
    assert "asset_199" in {h.asset_id for h in all_hits}
    filtered = pair.e5.search_text("chair", {"category": "chair"}).hits
    assert "asset_199" not in {h.asset_id for h in filtered}
    counts = pair.e5.search_text("chair", {"face_count_min": 1}).hits
    assert all(pair.e5.metadata[h.asset_id]["face_count"] is not None for h in counts)


@pytest.mark.parametrize("query,filters", [("", {}), ("x" * 501, {}), (None, {}),
    ("chair", {"unknown": "x"}), ("chair", {"face_count_min": True}),
    ("chair", {"face_count_min": 20, "face_count_max": 10})])
def test_input_validation_precedes_retrieval(pair, monkeypatch, query, filters):
    clip = Mock(side_effect=AssertionError("must not retrieve"))
    e5 = Mock(side_effect=AssertionError("must not retrieve"))
    monkeypatch.setattr(pair.clip, "assert_ready", clip)
    monkeypatch.setattr(pair.e5, "assert_ready", e5)
    with pytest.raises(ValidationError):
        pair.service.search_text(query, filters, config=config())
    clip.assert_not_called(); e5.assert_not_called()
    assert pair.clip_encoder.queries == pair.e5_encoder.queries == []


@pytest.mark.parametrize("source", ["clip", "e5"])
def test_one_dependency_failure_fails_whole_fusion_without_fallback(pair, monkeypatch, source):
    provider = getattr(pair, source)
    monkeypatch.setattr(provider.encoder, "encode_text", Mock(side_effect=RuntimeError("private diagnostic")))
    with pytest.raises(SearchUnavailableError) as error:
        pair.service.search_text("chair", {}, config=config())
    assert "private diagnostic" not in str(error.value)


@pytest.mark.parametrize("source", ["clip", "e5"])
def test_missing_collection_cannot_be_rebuilt_by_search(pair, source):
    provider = getattr(pair, source)
    provider.client.delete_collection(provider.store.collection_name)
    with pytest.raises(SearchUnavailableError):
        pair.service.search_text("chair", {}, config=config())
    assert not provider.client.collection_exists(provider.store.collection_name)


@pytest.mark.parametrize("source", ["clip", "e5"])
def test_metadata_drift_after_startup_is_unavailable(pair, source):
    provider = getattr(pair, source)
    points, _ = provider.client.scroll(provider.store.collection_name, limit=1)
    provider.client.set_payload(provider.store.collection_name, {"category": "changed"}, points=[points[0].id], wait=True)
    with pytest.raises(SearchUnavailableError):
        pair.service.search_text("chair", {}, config=config())


def test_source_hash_or_candidate_mismatch_rejected_before_encode(pair):
    pair.e5.asset_ids = pair.e5.asset_ids[:-1]
    with pytest.raises(SearchUnavailableError, match="sẵn sàng"):
        ExperimentalFusionService(pair.clip, pair.e5)
    assert not pair.clip_encoder.queries and not pair.e5_encoder.queries


def test_manifest_drift_is_unavailable(pair):
    path = pair.e5_root / "index-manifest.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(SearchUnavailableError):
        pair.e5.search_text("chair", {})


def test_two_e5_providers_cannot_be_labelled_as_clip_e5(pair):
    with pytest.raises(SearchUnavailableError):
        ExperimentalFusionService(pair.e5, pair.e5)


def test_malformed_ready_input_is_unavailable_not_partial_results(pair):
    import json
    ready_path = pair.clip_root / "ready.json"
    ready = json.loads(ready_path.read_bytes())
    ready[0]["metadata"]["asset_id"] = None
    raw = json_bytes(ready)
    ready_path.write_bytes(raw)
    manifest_path = pair.clip_root / "index-manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["ready_manifest_sha256"] = digest(raw)
    manifest_path.write_bytes(json_bytes(manifest))
    with pytest.raises(SearchUnavailableError):
        CLIPTextSource(pair.clip_encoder, pair.clip_client, pair.clip_root)


def rankings(pair):
    return pair.clip.search_text("chair", {}), pair.e5.search_text("chair", {})


def test_duplicates_missing_asset_and_score_above_one(pair, monkeypatch):
    clip, e5 = rankings(pair)
    clip = replace(clip, hits=(RankedCandidate("asset_000", 1, 1.0),
        RankedCandidate("asset_000", 2, 0.9), RankedCandidate("asset_001", 3, 0.8)))
    e5 = replace(e5, hits=(RankedCandidate("asset_001", 1, 1.0), RankedCandidate("asset_002", 2, 0.5)))
    monkeypatch.setattr(pair.clip, "search_text", lambda *a, **k: clip)
    monkeypatch.setattr(pair.e5, "search_text", lambda *a, **k: e5)
    result = pair.service.search_text("chair", {}, config=config(rank_constant=0, clip_candidate_limit=2, e5_candidate_limit=2, cutoff=3))
    assert [h.asset_id for h in result.hits] == ["asset_001", "asset_000", "asset_002"]
    assert [h.score for h in result.hits] == [1.5, 1.0, 0.5]
    assert [c.rank for c in result.hits[0].contributions] == [2, 1]
    assert result.hits[1].contributions[0].source == CLIP_SOURCE


def test_one_successful_empty_source_is_valid(pair, monkeypatch):
    clip, _ = rankings(pair)
    monkeypatch.setattr(pair.clip, "search_text", lambda *a, **k: replace(clip, hits=()))
    result = pair.service.search_text("chair", {}, config=config())
    assert len(result.hits) == 200
    assert all(len(h.contributions) == 1 and h.contributions[0].source == E5_SOURCE for h in result.hits)


@pytest.mark.parametrize("change", ["provenance", "filters", "order", "unknown-id", "nonfinite"])
def test_invalid_source_output_cannot_be_fused(pair, monkeypatch, change):
    clip, _ = rankings(pair)
    if change == "provenance":
        clip = replace(clip, provenance=replace(clip.provenance, index_version="other"))
    elif change == "filters":
        clip = replace(clip, filters={"category": "unexpected"})
    elif change == "order":
        clip = replace(clip, hits=tuple(reversed(clip.hits)))
    elif change == "unknown-id":
        clip = replace(clip, hits=(RankedCandidate("outside", 1, 1.0),))
    else:
        clip = replace(clip, hits=(RankedCandidate("asset_000", 1, float("nan")),))
    monkeypatch.setattr(pair.clip, "search_text", lambda *a, **k: clip)
    with pytest.raises(SearchUnavailableError):
        pair.service.search_text("chair", {}, config=config())


def test_reuse_readonly_repeat_and_versioning(pair, monkeypatch):
    for source in (pair.clip, pair.e5):
        monkeypatch.setattr(source.store, "upsert", Mock(side_effect=AssertionError("write")))
        monkeypatch.setattr(source.store, "ensure_collection", Mock(side_effect=AssertionError("create")))
    first = pair.service.search_text("chair", {}, config=config())
    repeat = pair.service.search_text("chair", {}, config=config())
    assert asdict(first) == asdict(repeat)
    changed = pair.service.search_text("chair", {}, config=config(rank_constant=20))
    assert changed.config_version != first.config_version
    assert pair.clip._audit() == pair.clip.baseline
    assert pair.e5._audit() == pair.e5.baseline
    assert len(pair.e5_encoder.queries) == len(pair.clip_encoder.queries) == 3


@pytest.mark.parametrize("value", [True, 0, 201, 1.5, "1"])
def test_e5_candidate_window_is_strict(value):
    with pytest.raises(ValueError):
        E5RetrievalConfig(value)


@pytest.mark.parametrize("pair", ["dense"], indirect=True)
def test_dense_local_cosine_normalization_preserves_repeat_and_persistence(pair):
    before = pair.e5.baseline.copy()
    first = pair.service.search_text("chair", {}, config=config())
    repeat = pair.service.search_text("chair", {}, config=config())
    assert first.hits == repeat.hits
    assert [[h.asset_id for h in r.hits] for r in first.raw_rankings] == [
        [h.asset_id for h in r.hits] for r in repeat.raw_rankings]
    assert pair.e5._audit() != before  # Actual dense data exercises the RAM transition.
    pair.clip.assert_ready()
    pair.e5.assert_ready()
    pair.e5_client.close()
    with closing(QdrantClient(path=str(pair.e5_root / "qdrant"))) as reopened:
        from app.search.e5_index import audit_metadata_index
        assert audit_metadata_index(pair.e5.manifest, reopened, pair.e5_root) == before


@pytest.mark.parametrize("pair", ["dense"], indirect=True)
@pytest.mark.parametrize("source", ["clip", "e5"])
def test_dense_vector_tampering_still_fails_after_legitimate_query(pair, source):
    pair.service.search_text("chair", {}, config=config())
    provider = getattr(pair, source)
    row = pair.records[0]
    provider.store.upsert([{"asset_id": row["asset_id"], "metadata": row,
        "vector": [1.0] + [0.0] * (provider.encoder.dimension - 1)}])
    with pytest.raises(SearchUnavailableError):
        pair.service.search_text("chair", {}, config=config())


@pytest.mark.parametrize("pair", ["dense"], indirect=True)
def test_dense_empty_filter_does_not_predict_a_query_that_was_skipped(pair):
    before = pair.e5.baseline.copy()
    assert pair.service.search_text("chair", {"category": "absent"}, config=config()).hits == ()
    assert pair.e5._audit() == before
    pair.service.search_text("chair", {}, config=config())
    pair.e5.assert_ready()


@pytest.mark.parametrize("source", ["clip", "e5"])
def test_payload_mutation_during_query_is_rejected(pair, monkeypatch, source):
    provider = getattr(pair, source)
    original = provider.client.query_points
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        provider.client.set_payload(provider.store.collection_name, {"category": "changed"},
            points=[result.points[0].id], wait=True)
        return result
    monkeypatch.setattr(provider.client, "query_points", changed)
    with pytest.raises(SearchUnavailableError):
        pair.service.search_text("chair", {}, config=config())
