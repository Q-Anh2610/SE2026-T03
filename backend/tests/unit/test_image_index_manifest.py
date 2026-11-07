"""Manifest/model isolation và runner với ảnh tự tạo; không dùng snapshot W4."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import pytest
from PIL import Image
from pydantic import ValidationError
from app.search.image_index_manifest import (ImageIndexManifest, load_image_index_manifest,
                                             save_image_index_manifest, require_same_image_inputs)
from scripts.verify_issue76_image_retrieval import build_index, smoke_index, same_ranked_results


class FixtureProcessor:
    def to_dict(self):
        return {"size": {"width": 224, "height": 224}, "fixture": True}


class FixtureEncoder:
    revision = "b" * 40
    dimension = 3
    preprocessing_version = "fixture-rgb-l2-v1"
    processor = FixtureProcessor()
    def __init__(self, model="fixture-clip"):
        self.model_id = model
    def encode_images(self, images, *, batch_size):
        return [[1., 0., 0.] for _ in images]


@pytest.fixture
def inputs(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    (root / "previews").mkdir()
    source, ready = [], []
    for i, color in enumerate(["red", "blue"]):
        metadata = {"asset_id": f"asset-{i}", "category": "chair", "license": "CC",
                    "formats": ["glb"], "face_count": 10}
        path = root / "previews" / f"{i}.png"
        with Image.new("RGB", (3, 2), color) as image:
            image.save(path)
        source.append(metadata)
        ready.append({"metadata": metadata, "image_path": f"previews/{i}.png",
                      "preview_sha256": sha256(path.read_bytes()).hexdigest()})
    (root / "source.json").write_text(json.dumps(source), encoding="utf-8")
    (root / "ready.json").write_text(json.dumps(ready), encoding="utf-8")
    return root, dict(source_manifest="source.json", ready_manifest="ready.json",
        source_sha256=sha256((root / "source.json").read_bytes()).hexdigest(),
        ready_sha256=sha256((root / "ready.json").read_bytes()).hexdigest(),
        asset_count=2, snapshot="fixture-snapshot", snapshot_confirmation="fixture-only-TV2-receipt",
        preview_directory="previews", candidate_limit=10)


@pytest.fixture
def built(tmp_path, inputs):
    root, options = inputs
    output = tmp_path / "clip"
    output.mkdir()
    encoder = FixtureEncoder()
    manifest, report = build_index(root, output, encoder, **options)
    return root, output, encoder, manifest, report


def test_build_manifest_roundtrip_audit_and_smoke(built):
    root, output, encoder, manifest, report = built
    assert report["summary"] == {"embedded": 2, "failed": 0, "skipped": 0}
    loaded = load_image_index_manifest(output / "index-manifest.json")
    assert loaded == manifest
    loaded.verify_input_hashes(root)
    loaded.check_encoder(encoder)
    result = smoke_index(root, output / "qdrant", loaded, encoder,
                         preview_directory="previews", candidate_limit=10)
    assert result["passed"]
    assert result["audit_before"] == result["audit_after"] == result["audit_reopened"]
    assert all(row["repeat_consistent"] for row in result["queries"])


def test_models_use_separate_named_vectors_same_inputs(tmp_path, inputs):
    root, options = inputs
    manifests = []
    for name in ("fixture-clip", "google/siglip2-base-patch16-224"):
        output = tmp_path / name.replace("/", "_")
        output.mkdir()
        manifest, _ = build_index(root, output, FixtureEncoder(name), **options)
        manifests.append(manifest)
    a, b = manifests
    require_same_image_inputs(a, b)
    assert a.vector_name.startswith("clip_") and b.vector_name.startswith("siglip2_")
    assert a.vector_name != b.vector_name
    assert a.source_manifest_sha256 == b.source_manifest_sha256
    assert a.ready_manifest_sha256 == b.ready_manifest_sha256
    assert a.as_index_config().dataset_snapshot == b.as_index_config().dataset_snapshot
    with pytest.raises(ValueError):
        a.check_encoder(FixtureEncoder("google/siglip2-base-patch16-224"))


@pytest.mark.parametrize("field,value", [
    ("vector_name", "wrong"), ("processor_revision", "c" * 40),
    ("source_manifest_sha256", "0" * 64), ("point_count", 3),
    ("source_manifest", "../outside"), ("ready_manifest", "C:/outside"),
    ("normalization", "none"), ("similarity", "Dot"),
    ("asset_count", True), ("point_count", 0), ("processor_use_fast", True),
    ("snapshot_confirmation", ""), ("created_at_utc", "2026-11-07T00:00:00"),
    ("module_sha256", {"../outside": "a" * 64}),
])
def test_manifest_rejects_inconsistent_provenance(built, field, value):
    data = deepcopy(built[3].model_dump())
    data[field] = value
    with pytest.raises(ValidationError):
        ImageIndexManifest.model_validate(data)


def test_save_never_overwrites_and_revalidates_nested_config(built, tmp_path):
    manifest = built[3]
    target = tmp_path / "existing.json"
    target.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        save_image_index_manifest(manifest, target)
    assert target.read_text() == "keep"
    manifest.index_config["dataset_snapshot"] = "changed"
    with pytest.raises(ValidationError):
        save_image_index_manifest(manifest, tmp_path / "invalid.json")
    assert not (tmp_path / "invalid.json").exists()


def test_modified_input_or_processor_rejected(built):
    root, _, encoder, manifest, _ = built
    (root / "source.json").write_text("[]")
    with pytest.raises(ValueError):
        manifest.verify_input_hashes(root)
    manifest.processor_config["size"] = {"width": 512, "height": 512}
    with pytest.raises(ValueError):
        manifest.check_encoder(encoder)


@pytest.mark.parametrize("change", ["missing-confirmation", "preview-checksum", "source-checksum"])
def test_rejects_unconfirmed_or_changed_input_before_index(tmp_path, inputs, change):
    root, options = inputs
    if change == "missing-confirmation":
        options["snapshot_confirmation"] = ""
    elif change == "preview-checksum":
        (root / "previews/0.png").write_bytes(b"changed")
    else:
        (root / "source.json").write_text("[]")
    output = tmp_path / "rejected"
    output.mkdir()
    with pytest.raises(ValueError):
        build_index(root, output, FixtureEncoder(), **options)
    assert not (output / "qdrant").exists()


def test_repeat_policy_keeps_order_exact_and_only_allows_w3_float_tolerance():
    from app.schemas.text_search import TextSearchCandidates, SearchExecutionVersions
    versions = SearchExecutionVersions(model_version="fixture", index_version="fixture",
        config_version="fixture", dataset_snapshot="fixture")
    a = TextSearchCandidates(hits=[{"asset_id": "a", "score": 0.9}], versions=versions)
    b = TextSearchCandidates(hits=[{"asset_id": "a", "score": 0.9 + 1e-16}], versions=versions)
    assert same_ranked_results(a, b)
    c = TextSearchCandidates(hits=[{"asset_id": "a", "score": 0.90001}], versions=versions)
    assert not same_ranked_results(a, c)
    d = TextSearchCandidates(hits=[{"asset_id": "different", "score": 0.9}], versions=versions)
    assert not same_ranked_results(a, d)
    assert not same_ranked_results(a, TextSearchCandidates(hits=[], versions=versions))


def test_comparison_rejects_changed_snapshot_or_cutoff(built):
    from app.search.image_search import ImageRetrievalConfig
    first = built[3]
    raw = deepcopy(first.model_dump())
    raw["retrieval_config"] = ImageRetrievalConfig.for_limit(5).model_dump()
    with pytest.raises(ValueError):
        require_same_image_inputs(first, ImageIndexManifest.model_validate(raw))
    raw = deepcopy(first.model_dump())
    raw["ready_manifest_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        require_same_image_inputs(first, ImageIndexManifest.model_validate(raw))
