"""Gate/pins bằng fixtures; không nạp model hoặc chạy benchmark query/test split."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from app.search.frozen_retrieval_config import FrozenConfigError, load_frozen_config
from app.search.rrf import reciprocal_rank_fusion


ROOT = Path(__file__).resolve().parents[3]
REFERENCE = ROOT / "evaluation/configs/issue114-w6-retrieval.frozen.json"
READY_BYTES = b"synthetic ready bytes; no image/model dependency\n"
CORPUS_BYTES = b"synthetic corpus bytes; not a retrieval benchmark\n"


def serialize(doc):
    return (json.dumps(doc, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


@pytest.fixture
def case(tmp_path):
    doc = json.loads(REFERENCE.read_bytes())
    for binding in doc["files"].values():
        dest = tmp_path / binding["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / binding["path"], dest)
    # Local byte bindings are synthetic fixtures. CI never needs the owner's
    # ignored data/processed files, model cache or Qdrant storage.
    files = doc["files"]
    clip_path = tmp_path / files["clip_index_manifest"]["path"]
    clip = json.loads(clip_path.read_bytes())
    clip["ready_manifest_sha256"] = sha256(READY_BYTES).hexdigest()
    clip_path.write_bytes(serialize(clip))
    files["clip_index_manifest"]["sha256"] = sha256(clip_path.read_bytes()).hexdigest()
    corpus_path = tmp_path / files["e5_corpus_manifest"]["path"]
    corpus = json.loads(corpus_path.read_bytes())
    corpus["corpus_sha256"] = sha256(CORPUS_BYTES).hexdigest()
    corpus_path.write_bytes(serialize(corpus))
    files["e5_corpus_manifest"]["sha256"] = sha256(corpus_path.read_bytes()).hexdigest()
    e5_path = tmp_path / files["e5_index_manifest"]["path"]
    e5 = json.loads(e5_path.read_bytes())
    e5["corpus_sha256"] = corpus["corpus_sha256"]
    e5["corpus_manifest_sha256"] = files["e5_corpus_manifest"]["sha256"]
    e5_path.write_bytes(serialize(e5))
    files["e5_index_manifest"]["sha256"] = sha256(e5_path.read_bytes()).hexdigest()
    pin = doc["sources"]["e5_text_to_metadata"]
    pin["corpus_sha256"], pin["corpus_manifest_sha256"] = e5["corpus_sha256"], e5["corpus_manifest_sha256"]
    for binding, value in zip(doc["local_files"]["bindings"], [files["clip_index_manifest"]["sha256"],
        files["candidate_metadata"]["sha256"], clip["ready_manifest_sha256"],
        files["e5_index_manifest"]["sha256"], files["candidate_metadata"]["sha256"],
        files["e5_corpus_manifest"]["sha256"], e5["corpus_sha256"]], strict=True):
        binding["sha256"] = value
    path = tmp_path / "frozen.json"
    path.write_bytes(serialize(doc))
    return tmp_path, path, doc


def load(case, changed=None, *, local=False):
    root, path, doc = case
    if changed is not None:
        path.write_bytes(serialize(changed))
    return load_frozen_config(path, expected_sha256=sha256(path.read_bytes()).hexdigest(),
                              repo_root=root, verify_local_inputs=local)


def test_selected_config_calls_existing_rrf_with_unique_ids_and_deterministic_ties(case):
    config = load(case)
    result = reciprocal_rank_fusion(["b", "a", "a"], ["a", "b"], config=config.rrf_config)
    assert [hit.asset_id for hit in result.hits] == ["a", "b"]
    assert all(len(hit.contributions) == 2 for hit in result.hits)
    assert config.rrf_config.rank_constant == 20
    assert config.rrf_config.cutoff == 200
    filters = config.filters
    filters["category"] = "unreviewed"
    assert config.filters == {}


def test_changed_artifact_cannot_rebind_itself_with_an_updated_sidecar(case):
    root, path, doc = case
    reviewed = sha256(path.read_bytes()).hexdigest()
    doc["text"]["rrf"]["rank_constant"] = 10
    path.write_bytes(serialize(doc))
    path.with_suffix(".sha256").write_text(sha256(path.read_bytes()).hexdigest())
    with pytest.raises(FrozenConfigError, match="artifact_hash_mismatch"):
        load_frozen_config(path, expected_sha256=reviewed, repo_root=root)


@pytest.mark.parametrize("version", ["issue91-validation-config-v2", "issue114-frozen-retrieval-v2", None])
def test_input_confirmation_or_unknown_schema_cannot_open_freeze_gate(case, version):
    doc = deepcopy(case[2])
    doc["schema_version"] = version
    with pytest.raises(FrozenConfigError, match="unsupported_config_version"):
        load(case, doc)


@pytest.mark.parametrize("status", ["draft", "pending_review", "confirmed", None])
def test_nonfrozen_status_is_rejected_even_with_matching_hash(case, status):
    doc = deepcopy(case[2])
    doc["selection_status"] = status
    with pytest.raises(FrozenConfigError, match="configuration_not_frozen"):
        load(case, doc)


@pytest.mark.parametrize("field,value", [
    ("mode", "clip_only"), ("sources", ["e5_text_to_metadata", "clip_text_to_preview"]),
    ("filters", {"category": "chair"}), ("source_retrieval_window", 50),
    ("exact", False), ("source_strategy", "ann"), ("score_threshold", 0.1),
    ("source_ordering", ["asset_id_asc", "score_desc"]),
    ("dependency_failure_policy", "fallback_to_clip"),
])
def test_runtime_policy_drift_is_not_silently_ignored(case, field, value):
    doc = deepcopy(case[2])
    doc["text"][field] = value
    with pytest.raises(FrozenConfigError, match="unsupported_text_policy"):
        load(case, doc)


@pytest.mark.parametrize("field,value", [
    ("rank_constant", 10), ("rank_constant", 20.0), ("clip_candidate_limit", 50),
    ("e5_candidate_limit", 100), ("cutoff", 10), ("weights", [1, 2]),
    ("weights", [True, True]), ("ordering", ["asset_id_asc", "rrf_score_desc"]),
    ("deduplication", "none"),
])
def test_fusion_and_type_changes_require_a_new_reviewed_version(case, field, value):
    doc = deepcopy(case[2])
    doc["text"]["rrf"][field] = value
    with pytest.raises(FrozenConfigError, match="unsupported_text_policy"):
        load(case, doc)


@pytest.mark.parametrize("field,value", [("mode", "siglip2_image_to_preview"), ("candidate_limit", 10),
                                        ("filters", {"category": "chair"})])
def test_image_policy_cannot_drift_from_retained_clip(case, field, value):
    doc = deepcopy(case[2])
    doc["image"][field] = value
    with pytest.raises(FrozenConfigError, match="unsupported_image_policy"):
        load(case, doc)


def test_missing_or_modified_input_is_a_dependency_error_not_fallback(case):
    root, path, doc = case
    target = root / doc["files"]["queries"]["path"]
    target.unlink()
    with pytest.raises(FrozenConfigError, match="missing_dependency"):
        load(case)
    target.write_bytes(b"different query bytes\n")
    with pytest.raises(FrozenConfigError, match="raw_hash_mismatch"):
        load(case)


def test_model_revision_and_tokenizer_mismatch_are_rejected(case):
    doc = deepcopy(case[2])
    doc["sources"]["e5_text_to_metadata"]["model_revision"] = "0" * 40
    with pytest.raises(FrozenConfigError, match="incompatible_model"):
        load(case, doc)
    doc = deepcopy(case[2])
    doc["sources"]["clip_text_to_preview"]["tokenizer_revision"] = "0" * 40
    with pytest.raises(FrozenConfigError, match="incompatible_tokenizer"):
        load(case, doc)


def test_index_version_mismatch_is_rejected_without_opening_qdrant(case):
    doc = deepcopy(case[2])
    doc["sources"]["clip_text_to_preview"]["index_version"] = "other-index"
    with pytest.raises(FrozenConfigError, match="incompatible_index_pins"):
        load(case, doc)


@pytest.mark.parametrize("unsafe", ["../outside.csv", "/outside.csv", "C:/outside.csv", "data\\queries.csv"])
def test_input_paths_cannot_escape_repository(case, unsafe):
    doc = deepcopy(case[2])
    doc["files"]["queries"]["path"] = unsafe
    with pytest.raises(FrozenConfigError, match="path|repository"):
        load(case, doc)


def test_rename_of_local_dependency_cannot_bypass_manifest_binding(case):
    doc = deepcopy(case[2])
    doc["local_files"]["bindings"][0]["path"] = "different/index-manifest.json"
    with pytest.raises(FrozenConfigError, match="incompatible_local_pins"):
        load(case, doc)


def test_local_input_check_refuses_missing_dependencies_and_accepts_bound_copies(case):
    root, path, doc = case
    with pytest.raises(FrozenConfigError, match="missing_dependency"):
        load(case, local=True)
    for binding in doc["local_files"]["bindings"]:
        dest = root / binding["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        local = doc["local_files"]
        data = {
            local["clip_index_root"] + "/index-manifest.json": (root / doc["files"]["clip_index_manifest"]["path"]).read_bytes(),
            local["clip_input_root"] + "/source.json": (root / doc["files"]["candidate_metadata"]["path"]).read_bytes(),
            local["clip_input_root"] + "/ready.json": READY_BYTES,
            local["e5_index_root"] + "/index-manifest.json": (root / doc["files"]["e5_index_manifest"]["path"]).read_bytes(),
            local["e5_index_root"] + "/source.json": (root / doc["files"]["candidate_metadata"]["path"]).read_bytes(),
            local["e5_index_root"] + "/corpus-manifest.json": (root / doc["files"]["e5_corpus_manifest"]["path"]).read_bytes(),
            local["e5_index_root"] + "/corpus.jsonl": CORPUS_BYTES,
        }
        dest.write_bytes(data[binding["path"]])
    assert load(case, local=True).local_inputs_verified is True
    target = root / doc["local_files"]["bindings"][-1]["path"]
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(FrozenConfigError, match="raw_hash_mismatch"):
        load(case, local=True)


@pytest.mark.parametrize("transform", [lambda raw: b"\xef\xbb\xbf" + raw,
    lambda raw: raw.replace(b"\n", b"\r\n"), lambda raw: raw.rstrip(b"\n"), lambda raw: raw + b"\n"])
def test_artifact_byte_policy_remains_strict_even_if_rehashed(case, transform):
    root, path, doc = case
    path.write_bytes(transform(path.read_bytes()))
    with pytest.raises(FrozenConfigError, match="artifact_byte_policy_mismatch"):
        load(case)


def test_duplicate_json_key_cannot_override_reviewed_semantics(case):
    path = case[1]
    raw = path.read_bytes().replace(b'{\n', b'{\n  "schema_version": "hidden",\n', 1)
    path.write_bytes(raw)
    with pytest.raises(FrozenConfigError, match="duplicate_json_key"):
        load(case)


@pytest.mark.parametrize("replacement", [None, [], True, {"schema_version": None}])
def test_malformed_config_has_a_single_safe_error_type(case, replacement):
    case[1].write_bytes(serialize(replacement))
    with pytest.raises(FrozenConfigError):
        load(case)


def test_blocked_cli_reports_no_model_or_benchmark_execution():
    script = ROOT / "scripts/verify_issue114_frozen_config.py"
    result = subprocess.run([sys.executable, "-B", str(script), "--repo", str(ROOT),
                             "--expected-sha256", "0" * 64], capture_output=True, text=True, check=False)
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["reason"] == "artifact_hash_mismatch"
    assert payload["models_loaded"] is payload["benchmark_executed"] is payload["test_authorized"] is False
