"""W7 fixture regression: real Qdrant, synthetic vectors/images, no model/Git/network."""

from contextlib import ExitStack, closing
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import pytest
from qdrant_client import QdrantClient

from app.search.qdrant_store import IndexConfig, QdrantStore
from app.search.rebuild_audit import (RebuildCheckError, compare_indexes, copy_reference,
                                      points_by_asset, storage_hashes)
from app.search.rrf import RRFConfig
from app.search.smoke import audit_index
from app.search.vector_search import SearchUnavailableError
from scripts import verify_issue135_rebuild as runner
# Reuse the existing full 200-asset corpus/service fixture.
from test_experimental_text_search import pair


@pytest.fixture
def indexes(tmp_path):
    metadata = {f"asset_{i:03d}": {"asset_id": f"asset_{i:03d}", "license": "fixture",
                                 "formats": ["glb"], "category": None, "face_count": i}
                for i in range(200)}
    config = IndexConfig("fixture", "a" * 40, 3, "fixture-l2", "fixture-snapshot", "old")
    with ExitStack() as stack:
        stores = []
        for label in ("old", "rebuilt"):
            client = stack.enter_context(closing(QdrantClient(path=str(tmp_path / label / "qdrant"))))
            store = QdrantStore(client, collection_name="fixture", config=replace(config, index_version=label))
            store.upsert([{"asset_id": aid, "metadata": row, "vector": [1.0, 0.0, 0.0]}
                          for aid, row in metadata.items()])
            stores.append(store)
        yield SimpleNamespace(old=stores[0], new=stores[1], metadata=metadata, root=tmp_path)


def compare(case):
    return compare_indexes(case.old, case.new, vector_abs_tolerance=1e-6,
                           expected_ids=sorted(case.metadata))


def first_point(case):
    points, _ = case.new.client.scroll("fixture", limit=1, with_payload=True, with_vectors=True)
    return points[0]


def test_distinct_versions_and_named_vectors_map_without_rewriting_reference(indexes):
    before = points_by_asset(indexes.old)
    assert indexes.old.vector_name != indexes.new.vector_name
    audit_index(indexes.old, indexes.metadata)
    audit_index(indexes.new, indexes.metadata)
    report = compare(indexes)
    assert report["asset_count"] == 200 and report["max_component_abs_delta"] == 0
    assert points_by_asset(indexes.old) == before


@pytest.mark.parametrize("field,value", [("license", "changed"), ("formats", ["obj"]),
                                         ("category", "chair"), ("face_count", 999),
                                         ("_corpus", {"sha256": "different"})])
def test_metadata_and_filter_field_drift_cannot_hide_in_new_provenance(indexes, field, value):
    point = first_point(indexes)
    indexes.new.client.set_payload("fixture", payload={field: value}, points=[point.id], wait=True)
    with pytest.raises(RebuildCheckError, match="payload_mismatch"):
        compare(indexes)


@pytest.mark.parametrize("field,value", [("model_revision", "b" * 40), ("dimension", 4),
                                         ("dataset_snapshot", "wrong"),
                                         ("preprocessing_version", "changed")])
def test_embedding_space_or_input_change_is_not_accepted_as_a_new_index_version(indexes, field, value):
    indexes.new.config = replace(indexes.new.config, **{field: value})
    with pytest.raises(RebuildCheckError, match="config_mismatch"):
        compare(indexes)


def test_same_count_with_wrong_ids_is_rejected(indexes):
    point = first_point(indexes)
    indexes.new.client.set_payload("fixture", payload={"asset_id": "wrong"}, points=[point.id], wait=True)
    with pytest.raises(RebuildCheckError, match="ids_mismatch"):
        compare(indexes)


@pytest.mark.parametrize("delta,accepted", [(5e-7, True), (2e-6, False)])
def test_fixed_vector_bound_reports_difference_and_rejects_excess(indexes, delta, accepted):
    point = first_point(indexes)
    from qdrant_client import models
    indexes.new.client.update_vectors("fixture", points=[models.PointVectors(
        id=point.id, vector={indexes.new.vector_name: [1.0, delta, 0.0]})], wait=True)
    if accepted:
        result = compare(indexes)
        assert 0 < result["max_component_abs_delta"] <= 1e-6
        assert result["different_vector_count"] == 1
    else:
        with pytest.raises(RebuildCheckError, match="tolerance_exceeded") as failed:
            compare(indexes)
        assert failed.value.details["max_component_abs_delta"] > 1e-6
        assert failed.value.details["passed"] is False


@pytest.mark.parametrize("tolerance", [True, -1, 1e-5, float("nan"), float("inf")])
def test_comparison_cannot_relax_protocol_tolerance(indexes, tolerance):
    with pytest.raises(RebuildCheckError, match="invalid_vector_tolerance"):
        compare_indexes(indexes.old, indexes.new, vector_abs_tolerance=tolerance,
                        expected_ids=sorted(indexes.metadata))


def test_storage_copy_and_reopen_leave_reference_bytes_untouched(tmp_path):
    config = IndexConfig("fixture", "a" * 40, 3, "fixture", "snapshot", "version")
    root = tmp_path / "reference"
    with closing(QdrantClient(path=str(root / "qdrant"))) as client:
        QdrantStore(client, collection_name="fixture", config=config).upsert([
            {"asset_id": "one", "metadata": {"asset_id": "one"}, "vector": [1., 0., 0.]}])
    before = storage_hashes(root / "qdrant")
    copy_reference(root, tmp_path / "copy", before)
    with closing(QdrantClient(path=str(tmp_path / "copy/qdrant"))) as client:
        assert client.count("fixture", exact=True).count == 1
    assert storage_hashes(root / "qdrant") == before
    assert storage_hashes(tmp_path / "copy/qdrant") == before
    with pytest.raises(RebuildCheckError, match="unsafe_reference_copy"):
        copy_reference(root, root / "nested", before)


def test_hot_sqlite_or_changed_reference_cannot_be_used(tmp_path):
    root = tmp_path / "qdrant"
    root.mkdir()
    (root / "meta.json").write_text("{}")
    (root / "storage.sqlite").write_bytes(b"fixture")
    before = storage_hashes(root)
    (root / "storage.sqlite-wal").write_bytes(b"fixture")
    with pytest.raises(RebuildCheckError, match="sidecar"):
        storage_hashes(root)
    (root / "storage.sqlite-wal").unlink()
    (root / "storage.sqlite").write_bytes(b"changed")
    with pytest.raises(RebuildCheckError, match="changed_before_copy"):
        copy_reference(tmp_path, tmp_path.parent / (tmp_path.name + "-copy"), before)


@pytest.mark.parametrize("pair", ["image"], indirect=True)
def test_fixed_smoke_calls_real_text_image_fusion_services_with_fixtures(pair):
    ready = json.loads((pair.clip_root / "ready.json").read_bytes())
    preview = pair.clip_root / ready[0]["image_path"]
    preview.parent.mkdir(parents=True)
    with Image.new("RGB", (2, 2), "red") as image:
        image.save(preview)
    pair.clip_encoder.encode_images = lambda images, **kwargs: [[1.] + [0.] * 511 for _ in images]
    protocol = json.loads((Path(runner.ROOT) / runner.PROTOCOL_PATH).read_bytes())
    result = runner.smoke(pair.clip_encoder, pair.e5_encoder, pair.clip_client, pair.e5_client,
                          pair.clip_root, pair.e5_root, pair.clip_root, pair.clip.metadata,
                          protocol, SimpleNamespace(rrf_config=RRFConfig(20, 200, 200, 200)))
    assert len(result) == 4 and all(row["passed"] for row in result)
    assert result[0]["clip_count"] == result[0]["e5_count"] == result[0]["fusion_count"] == 200
    assert result[1]["clip_count"] == result[1]["e5_count"] == result[1]["fusion_count"] == 0
    assert result[2]["count"] == 200 and result[3]["count"] == 0


def test_missing_fusion_dependency_raises_instead_of_falling_back(pair):
    pair.e5_encoder.revision = "b" * 40
    with pytest.raises(SearchUnavailableError):
        pair.service.search_text("W7 index reproducibility check", {}, config=RRFConfig(20, 200, 200, 200))


def test_protocol_edit_is_blocked_before_models_or_git(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    protocol_path = tmp_path / runner.PROTOCOL_PATH
    protocol_path.parent.mkdir(parents=True)
    protocol_path.write_text('{"vector_component_abs_tolerance":0.1}')
    monkeypatch.setattr(runner, "read_git", lambda *_: pytest.fail("Must not read Git"))
    output = tmp_path / "data/processed/issue135/test"
    with pytest.raises(RebuildCheckError, match="protocol_hash_mismatch"):
        runner.run(output)
    assert not output.exists()


def test_dependency_failure_writes_blocked_evidence_without_success_map(tmp_path, monkeypatch):
    protocol_raw = (runner.ROOT / runner.PROTOCOL_PATH).read_bytes()
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    protocol_path = tmp_path / runner.PROTOCOL_PATH
    protocol_path.parent.mkdir(parents=True)
    protocol_path.write_bytes(protocol_raw)
    monkeypatch.setattr(runner, "version", lambda _: "incompatible-fixture-version")
    monkeypatch.setattr(runner, "read_git", lambda *_: pytest.fail("Must not read Git"))
    output = tmp_path / "data/processed/issue135/test"
    assert runner.run(output) == 2
    report = json.loads((output / "report.json").read_bytes())
    assert report["status"] == "blocked" and report["stage"] == "dependencies"
    assert report["reason"] == "dependency_version_mismatch"
    assert (output / "protocol.json").read_bytes() == protocol_raw
    assert not (output / "reference-map.json").exists()
    with pytest.raises(RebuildCheckError, match="requires_new"):
        runner.run(output)


@pytest.mark.parametrize("pair", ["image"], indirect=True)
def test_full_runner_builds_both_indexes_and_reopens_with_fixture_models(pair, tmp_path, monkeypatch):
    """Exercise both original builders and W7 orchestration, on synthetic pins only."""
    from hashlib import sha256
    from app.embedding import clip_encoder, e5_encoder
    from app.search import frozen_retrieval_config
    from app.search.e5_index import audit_metadata_index, json_bytes
    from app.search.image_index_manifest import save_image_index_manifest
    from app.search.rebuild_audit import file_hash
    from scripts import verify_issue76_image_retrieval as builder

    repo = tmp_path / "fixture-repo"
    repo.mkdir()
    (repo / "fixture.py").write_text("# synthetic runner code provenance\n")
    inputs = repo / "inputs"
    inputs.mkdir()
    (inputs / "previews").mkdir()
    source = (pair.clip_root / "source.json").read_bytes()
    (inputs / "source.json").write_bytes(source)
    ready = []
    for i, row in enumerate(pair.records):
        path = inputs / "previews" / f"{i}.png"
        with Image.new("RGB", (2, 2), (i, 0, 0)) as image:
            image.save(path)
        ready.append({"metadata": row, "image_path": f"previews/{i}.png",
                      "preview_sha256": file_hash(path)})
    (inputs / "ready.json").write_bytes(json_bytes(ready))
    reference = repo / "reference-clip"
    reference.mkdir()
    config = pair.clip.store.config
    with closing(QdrantClient(path=str(reference / "qdrant"))) as client:
        store = QdrantStore(client, collection_name=pair.clip.store.collection_name, config=config)
        store.upsert([{"asset_id": row["asset_id"], "metadata": row,
                       "vector": [float((i + 1) % 3 == axis) for axis in range(3)] + [0.] * 509}
                      for i, row in enumerate(pair.records)])
    manifest = pair.clip.manifest.model_copy(update={"ready_manifest_sha256": file_hash(inputs / "ready.json")})
    save_image_index_manifest(manifest, reference / "index-manifest.json")
    pair.e5_client.close()
    with ExitStack() as stack:
        rc = stack.enter_context(closing(QdrantClient(path=str(reference / "qdrant"))))
        re = stack.enter_context(closing(QdrantClient(path=str(pair.e5_root / "qdrant"))))
        fingerprints = {"clip": audit_index(manifest.make_store(rc), pair.clip.metadata)["point_payload_vector_sha256"],
                        "e5": audit_metadata_index(pair.e5.manifest, re, pair.e5_root)["point_payload_vector_sha256"]}
    protocol = json.loads((runner.ROOT / runner.PROTOCOL_PATH).read_bytes())
    protocol["reference_fingerprints"] = fingerprints  # Synthetic pin, never used outside pytest.
    raw = json_bytes(protocol, pretty=True)
    protocol_path = repo / runner.PROTOCOL_PATH
    protocol_path.parent.mkdir(parents=True)
    protocol_path.write_bytes(raw)
    monkeypatch.setattr(runner, "ROOT", repo)
    monkeypatch.setattr(runner, "PROTOCOL_SHA256", sha256(raw).hexdigest())
    frozen = SimpleNamespace(clip_index_root=reference, clip_input_root=inputs,
                             e5_index_root=pair.e5_root, rrf_config=RRFConfig(20, 200, 200, 200))
    monkeypatch.setattr(frozen_retrieval_config, "load_frozen_config", lambda *a, **k: frozen)
    monkeypatch.setattr(runner, "input_inventory", lambda *a: {"fixture.py": file_hash(repo / "fixture.py")})
    info = {"code_commit": "b" * 40, "working_tree_dirty": True,
            "module_sha256": {"fixture.py": file_hash(repo / "fixture.py")},
            "package_versions": {"model": "fixture"}}
    monkeypatch.setattr(runner, "provenance", lambda: info)
    monkeypatch.setattr(builder, "REPO", repo)
    monkeypatch.setattr(builder.subprocess, "check_output", lambda command, **kwargs:
                        "b" * 40 if "rev-parse" in command else "fixture-dirty")
    for encoder in (pair.clip_encoder, pair.e5_encoder):
        encoder.device = "cpu"
        encoder.model.config._commit_hash = encoder.revision
    pair.clip_encoder.encode_images = lambda images, **kwargs: [
        [float((image.getpixel((0, 0))[0] + 1) % 3 == axis) for axis in range(3)] + [0.] * 509
        for image in images]
    monkeypatch.setattr(clip_encoder, "CLIPEncoder", lambda **kwargs: pair.clip_encoder)
    monkeypatch.setattr(e5_encoder, "E5Encoder", lambda **kwargs: pair.e5_encoder)
    import torch
    monkeypatch.setattr(torch, "set_num_interop_threads", lambda _: None)
    output = repo / "data/processed/issue135/fixture-run"
    assert runner.run(output) == 0
    report = json.loads((output / "report.json").read_bytes())
    assert report["status"] == "rebuild_and_service_smoke_verified"
    assert report["persisted_reopen_exact"] is True
    assert report["original_storage_bytes_unchanged"] is True
    assert all(r["asset_count"] == 200 for r in report["reference_comparison"].values())
    mapping = json.loads((output / "reference-map.json").read_bytes())
    assert mapping["review_status"] == "pending" and mapping["benchmark_binding_reviewed"] is False
    assert mapping["sources"]["clip"]["rebuilt_index_version"] != config.index_version
    assert mapping["sources"]["e5"]["rebuilt_index_version"] == pair.e5.manifest.index_config["index_version"]
    for line in (output / "CHECKSUMS.sha256").read_text().splitlines():
        expected, name = line.split("  ", 1)
        assert file_hash(output / name) == expected
