"""Manifest/config tests bằng fixtures; không xác nhận index/model thật."""

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from qdrant_client import QdrantClient

from app.search.index_manifest import IndexManifest, load_index_manifest, save_index_manifest
from app.search.qdrant_store import IndexConfig, index_vector_name
from app.search.retrieval_config import RetrievalConfig


@pytest.fixture
def manifest_input(tmp_path):
    source = tmp_path / "source.json"
    ready = tmp_path / "ready.json"
    source.write_text('[{"asset_id":"a"},{"asset_id":"b"}]', encoding="utf-8")
    ready.write_text(
        '[{"metadata":{"asset_id":"a"}},{"metadata":{"asset_id":"b"}}]',
        encoding="utf-8",
    )
    digest = sha256(source.read_bytes()).hexdigest()
    config = IndexConfig(
        model_id="fixture-clip", model_revision="b" * 40, dimension=3,
        preprocessing_version="fixture-rgb-l2-v1",
        dataset_snapshot="fixture-sha256:" + digest, index_version="fixture-index",
    )
    now = datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc)
    return dict(
        created_at_utc=now, observed_at_utc=now,
        index_config=asdict(config), collection="fixture-assets",
        vector_name=index_vector_name(config),
        processor_revision=config.model_revision, tokenizer_revision=config.model_revision,
        max_text_tokens=77,
        source_manifest="source.json", source_manifest_sha256=digest,
        ready_manifest="ready.json", ready_manifest_sha256=sha256(ready.read_bytes()).hexdigest(),
        asset_count=2, point_count=2, code_commit="1" * 40,
        working_tree_dirty=True,
        module_sha256={"backend/app/search/text_search.py": "2" * 64},
        retrieval_config=RetrievalConfig().model_dump(),
    )


def test_manifest_round_trip_preserves_config_versions_and_source_hashes(tmp_path, manifest_input):
    manifest = IndexManifest(**manifest_input)
    target = tmp_path / "index.json"

    save_index_manifest(manifest, target)
    loaded = load_index_manifest(target)

    assert loaded == manifest
    assert asdict(loaded.as_index_config()) == manifest_input["index_config"]
    assert loaded.execution_versions().model_dump() == {
        "model_version": "fixture-clip@" + "b" * 40,
        "index_version": "fixture-index",
        "dataset_snapshot": manifest_input["index_config"]["dataset_snapshot"],
        "config_version": "clip-text-exact-all-filtered-v1-k200",
    }
    loaded.verify_input_hashes(tmp_path)


def test_save_does_not_overwrite_existing_evidence(tmp_path, manifest_input):
    path = tmp_path / "existing.json"
    path.write_text("existing evidence", encoding="utf-8")

    with pytest.raises(FileExistsError):
        save_index_manifest(IndexManifest(**manifest_input), path)

    assert path.read_text(encoding="utf-8") == "existing evidence"


def test_save_revalidates_modified_nested_index_config(tmp_path, manifest_input):
    manifest = IndexManifest(**manifest_input)
    manifest.index_config["dataset_snapshot"] = "changed"
    target = tmp_path / "invalid.json"

    with pytest.raises(ValidationError):
        save_index_manifest(manifest, target)

    assert not target.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("vector_name", "clip_wrong"),
        ("processor_revision", "different"),
        ("tokenizer_revision", "different"),
        ("normalization", "none"),
        ("similarity", "Dot"),
        ("processor_use_fast", True),
        ("image_color_mode", "L"),
        ("source_manifest_sha256", "0" * 64),
        ("ready_manifest_sha256", "invalid-hash"),
        ("asset_count", 3),
        ("point_count", 0),
        ("point_count", True),
        ("max_text_tokens", True),
        ("code_commit", "not-a-commit"),
        ("working_tree_dirty", "false"),
        ("module_sha256", {}),
        ("module_sha256", {"../outside.py": "2" * 64}),
        ("module_sha256", {"module.py": "not-a-hash"}),
        ("unexpected", "do-not-ignore"),
    ],
)
def test_incompatible_or_incomplete_manifest_is_rejected(manifest_input, field, value):
    data = {**manifest_input, field: value}

    with pytest.raises(ValidationError):
        IndexManifest(**data)


@pytest.mark.parametrize("path", ["../source.json", "/source.json", "C:/source.json", "data\\source.json", "data//source.json", "./source.json"])
def test_nonportable_input_paths_are_rejected(manifest_input, path):
    with pytest.raises(ValidationError):
        IndexManifest(**{**manifest_input, "source_manifest": path})


@pytest.mark.parametrize("change", ["missing-field", "extra-field", "bool-dimension", "mock-version"])
def test_nested_index_settings_are_validated(manifest_input, change):
    data = deepcopy(manifest_input)
    if change == "missing-field":
        del data["index_config"]["dimension"]
    elif change == "extra-field":
        data["index_config"]["unknown"] = "value"
    elif change == "bool-dimension":
        data["index_config"]["dimension"] = True
    else:
        data["index_config"]["index_version"] = "mock-index"
        data["vector_name"] = index_vector_name(IndexConfig(**data["index_config"]))

    with pytest.raises(ValidationError):
        IndexManifest(**data)


@pytest.mark.parametrize("kind", ["naive", "non-utc", "future-observation"])
def test_manifest_requires_consistent_utc_observation_times(manifest_input, kind):
    data = deepcopy(manifest_input)
    if kind == "naive":
        data["observed_at_utc"] = data["observed_at_utc"].replace(tzinfo=None)
    elif kind == "non-utc":
        data["observed_at_utc"] = data["observed_at_utc"].astimezone(timezone(timedelta(hours=7)))
    else:
        data["observed_at_utc"] += timedelta(seconds=1)

    with pytest.raises(ValidationError):
        IndexManifest(**data)


@pytest.mark.parametrize("path", ["source.json", "ready.json"])
def test_input_file_hash_drift_is_detected(tmp_path, manifest_input, path):
    manifest = IndexManifest(**manifest_input)
    (tmp_path / path).write_text("changed snapshot", encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256"):
        manifest.verify_input_hashes(tmp_path)


def test_input_paths_are_relative_to_handoff_not_repo(tmp_path, manifest_input):
    manifest = IndexManifest(**manifest_input)
    other_root = tmp_path / "repo"
    other_root.mkdir()

    with pytest.raises(ValueError):
        manifest.verify_input_hashes(other_root)


def test_make_store_does_not_create_collection_or_contact_server(manifest_input):
    manifest = IndexManifest(**manifest_input)
    client = QdrantClient(location=":memory:")
    try:
        store = manifest.make_store(client)

        assert store.collection_name == manifest.collection
        assert store.vector_name == manifest.vector_name
        assert client.get_collections().collections == []
    finally:
        client.close()


@pytest.mark.parametrize("change", [None, "revision", "tokens"])
def test_encoder_compatibility_includes_token_limit(manifest_input, change):
    manifest = IndexManifest(**manifest_input)
    config = manifest.as_index_config()
    encoder = SimpleNamespace(
        model_id=config.model_id, revision=config.model_revision, dimension=config.dimension,
        preprocessing_version=config.preprocessing_version,
        model=SimpleNamespace(config=SimpleNamespace(
            text_config=SimpleNamespace(max_position_embeddings=77),
        )),
    )
    if change == "revision":
        encoder.revision = "other"
    elif change == "tokens":
        encoder.model.config.text_config.max_position_embeddings = 76

    if change is None:
        manifest.check_encoder(encoder)
    else:
        with pytest.raises(ValueError):
            manifest.check_encoder(encoder)


def test_vector_name_for_historical_issue39_config_is_unchanged():
    # Golden config đã được ghi trong evidence #39; không đọc dịch vụ thật.
    config = IndexConfig(
        model_id="openai/clip-vit-base-patch32",
        model_revision="3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268", dimension=512,
        preprocessing_version="clip-slow-processor-rgb-l2-v1",
        dataset_snapshot="objaverse200-w1-sha256:b37947fd1f2201dacf92e657d0580981315dd6252ad785e60657f4c1fe595e4a",
        index_version="issue39-objaverse200-clip-v1",
    )

    assert index_vector_name(config) == "clip_c243769d0cc6846b"


def test_checked_in_retrieval_config_matches_runtime_policy():
    path = Path(__file__).resolve().parents[3] / "docs/configs/clip-text-exact-v1.json"
    loaded = RetrievalConfig.model_validate_json(path.read_text(encoding="utf-8"))

    assert loaded == RetrievalConfig()
    assert json.loads(loaded.model_dump_json())["ordering"] == ["score_desc", "asset_id_asc"]


@pytest.mark.parametrize("limit", [1, 50, 200])
def test_retrieval_version_tracks_effective_candidate_limit(limit):
    config = RetrievalConfig.for_limit(limit)

    assert config.candidate_limit == limit
    assert config.config_version == f"clip-text-exact-all-filtered-v1-k{limit}"


@pytest.mark.parametrize(
    "options",
    [
        {"candidate_limit": True}, {"candidate_limit": 0}, {"candidate_limit": 201},
        {"candidate_limit": 1.5}, {"candidate_limit": "200"},
        {"candidate_limit": 50}, {"config_version": "other"},
        {"exact": False}, {"score_threshold": 0.5}, {"score_roundoff_tolerance": 0.1},
        {"ordering": ["asset_id_asc", "score_desc"]}, {"deduplication": "first_point"},
        {"query_trim": False}, {"text_token_policy": "reject"}, {"hnsw_ef": 100},
    ],
)
def test_unsupported_or_unversioned_retrieval_options_are_rejected(options):
    with pytest.raises(ValidationError):
        RetrievalConfig(**options)
