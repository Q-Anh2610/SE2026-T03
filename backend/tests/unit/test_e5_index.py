"""Corpus integrity và index E5: encoder fixture, Qdrant local thật, không tải weights."""

from copy import deepcopy
from contextlib import closing
import json
from math import sqrt
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

import numpy as np
import pytest
from pydantic import ValidationError
from qdrant_client import QdrantClient, models

from app.embedding.e5_encoder import (
    DIMENSION, MAX_TEXT_TOKENS, MODEL_ID, MODEL_REVISION, PREPROCESSING_VERSION,
)
from app.search.e5_index import (
    E5IndexManifest, SERIALIZATION, SNAPSHOT, audit_metadata_index, build_metadata_index,
    check_e5_encoder, corpus_index_config, digest, json_bytes,
    load_e5_index_manifest, load_metadata_corpus,
)
from app.search.qdrant_store import IndexConfig, index_vector_name


@pytest.fixture
def corpus_inputs(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    source = [{"asset_id": f"asset_{i:03d}", "name": f"Chair {i}",
               "description": None, "category": None, "tags": [],
               "license": "CC0", "formats": ["glb"], "face_count": None} for i in range(200)]
    source_raw = json_bytes(source)
    rows = [{"asset_id": row["asset_id"], "passage": row["name"]} for row in source]
    raw = b"".join(json_bytes(row) for row in rows)
    manifest = {
        "snapshot": SNAPSHOT, "source_path": "data/manifests/objaverse_200.json",
        "source_hash_basis": "raw Git blob bytes", "source_manifest_sha256": digest(source_raw),
        "source_commit": "a" * 40, "corpus_file": "corpus.jsonl", "corpus_sha256": digest(raw),
        "recipe_version": "e5-metadata-passage-v1-draft",
        "fields": ["name", "description", "tags", "category"],
        "text_policy": "Python str.split then join with one ASCII space",
        "tags_policy": "clean; drop empty; exact dedup; preserve first order",
        "tags_separator": ", ", "field_separator": "\n",
        "empty_policy": "omit empty fields; reject empty passage",
        "prefix_in_corpus": False, "serialization": SERIALIZATION,
        "asset_count": 200, "nonempty_passage_count": 200,
        "errors": [], "checkout_matches_source_json": True,
        "asset_ids": [row["asset_id"] for row in rows],
    }
    (root / "manifest.json").write_bytes(json_bytes(manifest))
    (root / "corpus.jsonl").write_bytes(raw)
    pins = {"expected_source_sha256": digest(source_raw),
            "expected_corpus_sha256": digest(raw), "expected_recipe_version": manifest["recipe_version"]}
    return root, source_raw, pins, manifest, rows


@pytest.fixture
def corpus(corpus_inputs):
    root, source_raw, pins, _, _ = corpus_inputs
    return load_metadata_corpus(root, source_raw, **pins)


class Encoder:
    model_id = MODEL_ID
    revision = tokenizer_revision = MODEL_REVISION
    dimension = DIMENSION
    max_text_tokens = MAX_TEXT_TOKENS
    preprocessing_version = PREPROCESSING_VERSION

    def __init__(self):
        self.tokenizer = SimpleNamespace(is_fast=True, padding_side="right", truncation_side="right")
        self.calls = []

    def encode_passages(self, passages, *, batch_size):
        self.calls.append((passages, batch_size))
        return [[1.0] + [0.0] * (DIMENSION - 1) for _ in passages]


PROVENANCE = {"code_commit": "b" * 40, "working_tree_dirty": True,
              "module_sha256": {"backend/app/search/e5_index.py": "c" * 64},
              "package_versions": {"encoder": "fixture"}}


@pytest.fixture
def built(tmp_path, corpus):
    root = tmp_path / "index"
    encoder = Encoder()
    manifest = build_metadata_index(encoder, corpus, root, batch_size=16, **PROVENANCE)
    return root, manifest, encoder


def test_new_local_index_persists_and_passages_have_no_added_prefix(built, corpus):
    root, manifest, encoder = built
    assert encoder.calls == [([row["passage"] for row in corpus.rows], 16)]
    assert manifest.vector_name.startswith("e5_")
    assert manifest.index_config["dimension"] == 384
    assert load_e5_index_manifest(root / "index-manifest.json") == manifest
    assert (root / "corpus.jsonl").read_bytes() == corpus.corpus_bytes
    with closing(QdrantClient(path=str(root / "qdrant"))) as client:
        audit = audit_metadata_index(manifest, client, root)
        assert audit["asset_count"] == audit["point_count"] == 200
        assert audit == json.loads((root / "audit.json").read_bytes())
        # Metadata null/arrays vẫn là metadata nguồn, không thay bằng passage.
        point = client.retrieve(manifest.collection,
            [str(uuid5(NAMESPACE_URL, "ai04/asset/asset_000"))])[0]
        assert point.payload["category"] is None
        assert point.payload["formats"] == ["glb"]
        assert point.payload["_corpus"]["sha256"] == digest(corpus.corpus_bytes)


@pytest.mark.parametrize("key,value", [
    ("model_id", "openai/clip-vit-base-patch32"), ("revision", "wrong"),
    ("tokenizer_revision", "wrong"), ("dimension", 512),
    ("max_text_tokens", 511), ("preprocessing_version", "other"),
])
def test_incompatible_encoder_rejected_before_creating_output(tmp_path, corpus, key, value):
    encoder = Encoder()
    setattr(encoder, key, value)
    root = tmp_path / "must-not-exist"
    with pytest.raises(ValueError, match="không tương thích"):
        build_metadata_index(encoder, corpus, root, batch_size=16, **PROVENANCE)
    assert not root.exists()
    assert encoder.calls == []


@pytest.mark.parametrize("key,value", [("is_fast", False), ("padding_side", "left"), ("truncation_side", "left")])
def test_tokenizer_policy_cannot_drift(key, value):
    encoder = Encoder()
    setattr(encoder.tokenizer, key, value)
    with pytest.raises(ValueError):
        check_e5_encoder(encoder)


def test_existing_output_not_modified(built, corpus):
    root, _, _ = built
    before = (root / "index-manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        build_metadata_index(Encoder(), corpus, root, batch_size=16, **PROVENANCE)
    assert (root / "index-manifest.json").read_bytes() == before


@pytest.mark.parametrize("mutation", ["corpus", "source", "manifest", "prefix", "recipe", "order", "empty", "duplicate"])
def test_corpus_input_integrity(corpus_inputs, mutation):
    root, source_raw, pins, manifest, rows = corpus_inputs
    if mutation == "source":
        source_raw += b" "
    elif mutation == "manifest":
        manifest["errors"] = ["missing asset"]
    elif mutation == "prefix":
        manifest["prefix_in_corpus"] = True
    elif mutation == "recipe":
        manifest["recipe_version"] = "unconfirmed-v2"
    elif mutation == "corpus":
        rows[0]["passage"] = "Different content"
    elif mutation == "order":
        rows.reverse()
    elif mutation == "empty":
        rows[0]["passage"] = ""
    else:
        rows[1]["asset_id"] = rows[0]["asset_id"]
    if mutation in {"order", "empty", "duplicate"}:
        # Ngay cả khi hash được cung cấp đúng, cấu trúc artifact vẫn phải hợp lệ.
        raw = b"".join(json_bytes(row) for row in rows)
        pins["expected_corpus_sha256"] = digest(raw)
        manifest["corpus_sha256"] = digest(raw)
    (root / "corpus.jsonl").write_bytes(b"".join(json_bytes(row) for row in rows))
    (root / "manifest.json").write_bytes(json_bytes(manifest))
    with pytest.raises(ValueError):
        load_metadata_corpus(root, source_raw, **pins)


@pytest.mark.parametrize("member", ["source.json", "corpus.jsonl", "corpus-manifest.json"])
def test_audit_rejects_input_drift_without_touching_index(built, member):
    root, manifest, _ = built
    (root / member).write_bytes((root / member).read_bytes() + b" ")
    with closing(QdrantClient(path=str(root / "qdrant"))) as client:
        with pytest.raises(ValueError, match="SHA-256"):
            audit_metadata_index(manifest, client, root)
        assert client.count(manifest.collection, exact=True).count == 200


@pytest.mark.parametrize("mutation", ["missing", "metadata", "corpus-version", "named-vector"])
def test_reopened_index_rejects_corruption(built, mutation):
    root, manifest, _ = built
    pid = str(uuid5(NAMESPACE_URL, "ai04/asset/asset_000"))
    with closing(QdrantClient(path=str(root / "qdrant"))) as client:
        if mutation == "missing":
            client.delete(manifest.collection, models.PointIdsList(points=[pid]), wait=True)
        elif mutation == "metadata":
            client.set_payload(manifest.collection, {"category": "invented"}, points=[pid], wait=True)
        elif mutation == "corpus-version":
            client.set_payload(manifest.collection, {"_corpus": {"sha256": "d" * 64}}, points=[pid], wait=True)
        else:
            client.delete_collection(manifest.collection)
            client.create_collection(manifest.collection, vectors_config={
                "clip_wrong": models.VectorParams(size=384, distance=models.Distance.COSINE)})
    with closing(QdrantClient(path=str(root / "qdrant"))) as client:
        with pytest.raises(ValueError):
            audit_metadata_index(manifest, client, root)


def test_manifest_cannot_relabel_corpus_index_version(built):
    root, manifest, _ = built
    data = manifest.model_dump()
    data["index_config"]["index_version"] = "mislabelled"
    data["vector_name"] = index_vector_name(IndexConfig(**data["index_config"]))
    changed = E5IndexManifest(**data)
    with pytest.raises(ValueError, match="corpus"):
        changed.verify_inputs(root)


def test_recipe_manifest_changes_index_namespace(corpus):
    changed = deepcopy(corpus)
    changed.manifest["recipe_version"] = "other"
    # MetadataCorpus giữ bytes nhận vào; tạo một artifact version mới rõ ràng.
    from dataclasses import replace
    changed = replace(changed, manifest_bytes=json_bytes(changed.manifest))
    first, second = corpus_index_config(corpus), corpus_index_config(changed)
    assert first.index_version != second.index_version
    assert index_vector_name(first) != index_vector_name(second)


@pytest.mark.parametrize("field,value", [
    ("tokenizer_revision", "d" * 40), ("max_text_tokens", 511),
    ("passage_prefix", "query: "), ("normalization", "none"),
    ("source_manifest", "../source.json"), ("point_count", 199),
    ("asset_ids", ["duplicate"] * 200), ("vector_name", "clip_wrong"),
])
def test_index_manifest_rejects_incompatible_policy(built, field, value):
    _, manifest, _ = built
    data = manifest.model_dump()
    data[field] = value
    with pytest.raises(ValidationError):
        E5IndexManifest(**data)


@pytest.mark.parametrize("field,value", [
    ("dimension", 512), ("model_revision", "d" * 40),
    ("preprocessing_version", "other"), ("dataset_snapshot", "other-354"),
])
def test_manifest_rejects_mixed_model_or_snapshot(built, field, value):
    _, manifest, _ = built
    data = manifest.model_dump()
    data["index_config"][field] = value
    data["vector_name"] = index_vector_name(IndexConfig(**data["index_config"]))
    with pytest.raises(ValidationError):
        E5IndexManifest(**data)


def test_incomplete_encoder_batch_never_creates_index(tmp_path, corpus):
    encoder = Encoder()
    encoder.encode_passages = lambda *args, **kwargs: [[1.0] + [0.0] * 383]
    root = tmp_path / "incomplete"
    with pytest.raises(ValueError, match="không trả đủ"):
        build_metadata_index(encoder, corpus, root, batch_size=16, **PROVENANCE)
    assert not root.exists()


def test_non_axis_float32_vectors_keep_persisted_fingerprint(tmp_path, corpus):
    # L2 float32 thực tế có thể lệch norm 1 vài ULP; vector trục [1,0,...] che lỗi này.
    vector = np.full(384, 1 / sqrt(384), dtype=np.float32)
    vector *= np.float32(1 - 2**-21)
    assert abs(float(np.linalg.norm(vector)) - 1) < 1e-5
    assert float(np.linalg.norm(vector)) != 1
    submitted = vector.tolist()
    encoder = Encoder()
    encoder.encode_passages = lambda passages, **kwargs: [submitted[:] for _ in passages]
    root = tmp_path / "non-axis-index"
    manifest = build_metadata_index(encoder, corpus, root, batch_size=16, **PROVENANCE)
    previous = json.loads((root / "audit.json").read_bytes())
    persistence = json.loads((root / "persistence-audit.json").read_bytes())
    assert persistence["policy"] == "qdrant-local-submitted-vectors-exact-v1"
    assert persistence["expected_submitted"] == persistence["persisted_after_reopen"] == previous
    assert persistence["in_memory_after_upsert"] != previous
    for _ in range(2):
        with closing(QdrantClient(path=str(root / "qdrant"))) as client:
            audit = audit_metadata_index(manifest, client, root)
            assert audit == previous
            point = client.retrieve(manifest.collection,
                [str(uuid5(NAMESPACE_URL, "ai04/asset/asset_000"))], with_vectors=True)[0]
            # Kiểm byte-value đã submit, không làm tròn hash hoặc nới tolerance.
            assert point.vector[manifest.vector_name] == submitted


def test_persisted_fingerprint_still_detects_changed_unit_vector(built):
    root, manifest, _ = built
    before = json.loads((root / "audit.json").read_bytes())
    pid = str(uuid5(NAMESPACE_URL, "ai04/asset/asset_000"))
    with closing(QdrantClient(path=str(root / "qdrant"))) as client:
        client.update_vectors(manifest.collection, points=[models.PointVectors(
            id=pid, vector={manifest.vector_name: [0.0, 1.0] + [0.0] * 382})], wait=True)
    with closing(QdrantClient(path=str(root / "qdrant"))) as client:
        changed = audit_metadata_index(manifest, client, root)
    assert changed["asset_count"] == before["asset_count"] == 200
    assert changed["point_payload_vector_sha256"] != before["point_payload_vector_sha256"]
