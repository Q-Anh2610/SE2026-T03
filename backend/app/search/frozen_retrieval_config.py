"""Đọc cấu hình benchmark W6 đã pin; không nạp model, chạy query hay bật API."""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re

from app.search.rrf import RRFConfig


SCHEMA = "issue114-frozen-retrieval-v1"
VERSION = "w6-clip-e5-rrf-k20-candidate200-v1"
_HEX = re.compile(r"[0-9a-f]{64}")
_SOURCES = ("clip_text_to_preview", "e5_text_to_metadata")


class FrozenConfigError(ValueError):
    """Config, pins hoặc dependency thiếu/khác bản đã được review."""


def _require(condition, message):
    if not condition:
        raise FrozenConfigError(message)


def _json(raw):
    def reject_constant(value):
        raise FrozenConfigError("nonfinite_json_number")

    def unique(pairs):
        document = {}
        for key, value in pairs:
            _require(key not in document, "duplicate_json_key")
            document[key] = value
        return document

    try:
        return json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise FrozenConfigError("invalid_json") from error


def _same(actual, expected, label):
    # JSON equality alone treats True as 1 and 200.0 as 200.
    encoded = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    _require(encoded(actual) == encoded(expected), label)


def _member(root, relative):
    _require(isinstance(relative, str) and relative and "\\" not in relative
             and ":" not in relative and "\x00" not in relative, "nonportable_path")
    name = PurePosixPath(relative)
    _require(not name.is_absolute() and ".." not in name.parts, "path_outside_repository")
    path = (root / relative).resolve()
    _require(path.is_relative_to(root), "path_outside_repository")
    return path


def _bound_file(root, binding):
    _require(isinstance(binding, dict) and set(binding) == {"path", "sha256"}, "invalid_file_binding")
    _require(isinstance(binding["sha256"], str) and _HEX.fullmatch(binding["sha256"]), "invalid_sha256")
    path = _member(root, binding["path"])
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise FrozenConfigError(f"missing_dependency:{binding['path']}") from error
    _require(sha256(raw).hexdigest() == binding["sha256"], f"raw_hash_mismatch:{binding['path']}")
    return raw


@dataclass(frozen=True)
class FrozenRetrievalConfig:
    config_version: str
    artifact_sha256: str
    rrf_config: RRFConfig
    clip_index_root: Path
    clip_input_root: Path
    e5_index_root: Path
    image_index_root: Path
    image_candidate_limit: int
    local_inputs_verified: bool

    @property
    def filters(self):
        return {}


def load_frozen_config(path, *, expected_sha256, repo_root, verify_local_inputs=False):
    """Bind approved hash supplied by caller; sidecar alone is not approval.

    Tracked pins are always checked. Local mode checks manifests/corpus/input
    bytes, not weights or live Qdrant contents. Actual services retain their
    existing model/index/filter/result compatibility checks. This loader cannot
    establish GitHub review/merge or authorize benchmark test by itself.
    """
    try:
        return _load(path, expected_sha256=expected_sha256, repo_root=repo_root,
                     verify_local_inputs=verify_local_inputs)
    except FrozenConfigError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise FrozenConfigError("invalid_config_structure") from error


def _load(path, *, expected_sha256, repo_root, verify_local_inputs):
    _require(isinstance(expected_sha256, str) and _HEX.fullmatch(expected_sha256), "expected_sha256_required")
    _require(type(verify_local_inputs) is bool, "invalid_local_check_option")
    root = Path(repo_root).resolve()
    try:
        raw = Path(path).read_bytes()
    except OSError as error:
        raise FrozenConfigError("config_unavailable") from error
    _require(sha256(raw).hexdigest() == expected_sha256, "artifact_hash_mismatch")
    _require(not raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw
             and raw.endswith(b"\n") and not raw.endswith(b"\n\n"), "artifact_byte_policy_mismatch")
    doc = _json(raw)
    _require(isinstance(doc, dict), "config_must_be_object")
    _require(set(doc) == {"schema_version", "config_version", "selection_status", "decision",
                         "benchmark", "text", "image", "sources", "files", "local_files",
                         "byte_policy", "test_gate", "validation_evidence"}, "unknown_config_fields")
    _require(doc["schema_version"] == SCHEMA and doc["config_version"] == VERSION, "unsupported_config_version")
    _require(doc["selection_status"] == "frozen", "configuration_not_frozen")
    _same(doc["byte_policy"], {"encoding": "UTF-8", "bom": False, "newline": "LF", "trailing_lf_count": 1,
                              "digest": "sha256_raw_bytes_including_final_lf"}, "unsupported_byte_policy")
    _same(doc["text"], {"mode": "clip_e5_rrf", "sources": list(_SOURCES), "source_retrieval_window": 200,
        "query_policy": {"trim": True, "min_characters": 1, "max_characters": 500},
        "filters": {}, "source_strategy": "exact_all_filtered_points", "exact": True,
        "score_threshold": None, "score_roundoff_tolerance": 1e-6,
        "source_ordering": ["score_desc", "asset_id_asc"], "source_deduplication": "max_score_per_asset",
        "audit_policy": "exact-pre-post-local-cosine-transition-v1",
        "orchestration_policy": "audit-both-same-inputs-all200-before-fusion-v2",
        "dependency_failure_policy": "error_no_silent_fallback",
        "rrf": RRFConfig(20, 200, 200, 200).parameters()}, "unsupported_text_policy")
    _same(doc["image"], {"mode": "clip_image_to_preview", "source": _SOURCES[0],
        "index_scope": "benchmark_candidate200", "candidate_limit": 200, "filters": {},
        "config_version": "image-exact-all-filtered-rgb-v1-k200", "exact": True,
        "score_threshold": None, "score_roundoff_tolerance": 1e-6,
        "ordering": ["score_desc", "asset_id_asc"], "deduplication": "max_score_per_asset",
        "image_formats": ["JPEG", "PNG"], "max_image_bytes": 5242880, "max_image_dimension": 4096,
        "image_color_mode": "RGB", "frame_policy": "first", "exif_orientation": "stored_pixels"}, "unsupported_image_policy")
    _same(doc["test_gate"], {"requires_reviewed_hash_commit_and_khue_handoff": True,
        "loader_proves_github_approval": False, "shared_runtime_activation": False,
        "held_out_results_must_not_change_selection": True}, "unsupported_test_gate")
    _same(doc["benchmark"], {"text_version": "home-interior-text-v2", "snapshot": "home-interior-clear-200-v3",
        "candidate_count": 200, "validation_queries": 28, "excluded_test_queries": 42,
        "language": "en", "positive_relevance_threshold": 1, "gain": "binary",
        "validation_recall_denominator": 21, "validation_hit_ndcg_denominator": 28,
        "validation_no_positive_queries": 7, "metric_cutoffs": [5, 10],
        "image_version": "home-interior-image-v1", "image_validation_queries": 8,
        "image_excluded_test_queries": 12, "image_task": "similarity", "image_same_id_queries": 0}, "incompatible_benchmark")
    files = doc["files"]
    required = {"queries", "qrels", "candidate_metadata", "benchmark_manifest", "image_benchmark_manifest",
                "image_queries", "image_qrels", "clip_index_manifest", "e5_index_manifest", "e5_corpus_manifest"}
    _require(isinstance(files, dict) and set(files) == required, "incomplete_input_pins")
    contents = {name: _bound_file(root, binding) for name, binding in files.items()}
    sources = doc["sources"]
    _require(isinstance(sources, dict) and set(sources) == set(_SOURCES), "incompatible_sources")
    expected_models = (("openai/clip-vit-base-patch32", "3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268", 512,
                        "clip-slow-processor-rgb-l2-v1"),
                       ("intfloat/multilingual-e5-small", "614241f622f53c4eeff9890bdc4f31cfecc418b3", 384,
                        "e5-fast-right-truncate512-mask-mean-fp32-l2-v1"))
    for source, prefix, model in zip(_SOURCES, ("clip", "e5"), expected_models, strict=True):
        pin = sources[source]
        manifest = _json(contents[f"{prefix}_index_manifest"])
        cfg = manifest["index_config"]
        _same([pin["model_id"], pin["model_revision"], pin["dimension"], pin["preprocessing_version"]],
              list(model), "incompatible_model")
        _same([cfg["model_id"], cfg["model_revision"], cfg["dimension"], cfg["preprocessing_version"]],
              list(model), "incompatible_index_model")
        _require(pin["index_version"] == cfg["index_version"]
                 and pin["collection"] == manifest["collection"] and pin["vector_name"] == manifest["vector_name"]
                 and manifest["source_manifest_sha256"] == files["candidate_metadata"]["sha256"]
                 and cfg["dataset_snapshot"] == pin["dataset_snapshot"]
                 == doc["benchmark"]["snapshot"] + "-sha256:" + files["candidate_metadata"]["sha256"], "incompatible_index_pins")
        _require(pin["normalization"] == manifest["normalization"] == "L2"
                 and pin["similarity"] == manifest["similarity"] == "Cosine"
                 and type(manifest["asset_count"]) is int and manifest["asset_count"] == 200,
                 "incompatible_index_shape")
        _require(pin["tokenizer_revision"] == pin["model_revision"], "incompatible_tokenizer")
        _require(pin["config_version"] == ("clip-text-exact-all-filtered-v1-k200" if prefix == "clip"
                 else "e5-metadata-exact-all-filtered-maskmean512-l2-v1-k200"), "incompatible_source_config")
        if prefix == "clip":
            _require(pin["processor_revision"] == manifest["processor_revision"] == pin["model_revision"], "incompatible_processor")
            _same(pin["processor_config"], manifest["processor_config"], "incompatible_processor")
            _require(pin["processor_use_fast"] is False and pin["text_max_tokens"] == 77, "unsupported_clip_preprocessing")
        else:
            corpus_manifest = _json(contents["e5_corpus_manifest"])
            _require(pin["tokenizer_revision"] == manifest["tokenizer_revision"]
                     and pin["corpus_sha256"] == manifest["corpus_sha256"]
                     and pin["corpus_manifest_sha256"] == manifest["corpus_manifest_sha256"]
                     == files["e5_corpus_manifest"]["sha256"]
                     and pin["recipe_version"] == manifest["recipe_version"], "incompatible_corpus")
            _require(corpus_manifest["corpus_sha256"] == pin["corpus_sha256"]
                     and corpus_manifest["recipe_version"] == pin["recipe_version"]
                     and corpus_manifest["source_manifest_sha256"] == files["candidate_metadata"]["sha256"]
                     and corpus_manifest["snapshot"] == doc["benchmark"]["snapshot"]
                     and corpus_manifest["asset_count"] == 200, "incompatible_corpus_manifest")
            _same([manifest["max_text_tokens"], manifest["query_prefix"], manifest["passage_prefix"]],
                  [512, "query: ", "passage: "], "incompatible_e5_index_preprocessing")
            _same(pin["text_preprocessing"], {"max_tokens": 512, "query_prefix": "query: ", "passage_prefix": "passage: ",
                "tokenizer_use_fast": True, "padding_side": "right", "truncation_side": "right",
                "pooling": "attention_mask_mean_fp32", "normalization": "L2"}, "unsupported_e5_preprocessing")
    local = doc["local_files"]
    _require(isinstance(local, dict) and set(local) == {"clip_index_root", "clip_input_root", "e5_index_root", "bindings"}, "invalid_local_files")
    roots = {name: _member(root, local[name]) for name in ("clip_index_root", "clip_input_root", "e5_index_root")}
    _require(isinstance(local["bindings"], list) and len(local["bindings"]) == 7, "incomplete_local_pins")
    # Bind local copies to the reviewed manifests; an edited path/hash pair is not an independent pin.
    clip_manifest = _json(contents["clip_index_manifest"])
    e5_manifest = _json(contents["e5_index_manifest"])
    expected_local = [
        {"path": local["clip_index_root"] + "/index-manifest.json", "sha256": files["clip_index_manifest"]["sha256"]},
        {"path": local["clip_input_root"] + "/" + clip_manifest["source_manifest"], "sha256": files["candidate_metadata"]["sha256"]},
        {"path": local["clip_input_root"] + "/" + clip_manifest["ready_manifest"], "sha256": clip_manifest["ready_manifest_sha256"]},
        {"path": local["e5_index_root"] + "/index-manifest.json", "sha256": files["e5_index_manifest"]["sha256"]},
        {"path": local["e5_index_root"] + "/" + e5_manifest["source_manifest"], "sha256": files["candidate_metadata"]["sha256"]},
        {"path": local["e5_index_root"] + "/" + e5_manifest["corpus_manifest"], "sha256": files["e5_corpus_manifest"]["sha256"]},
        {"path": local["e5_index_root"] + "/" + e5_manifest["corpus_file"], "sha256": e5_manifest["corpus_sha256"]},
    ]
    _same(local["bindings"], expected_local, "incompatible_local_pins")
    for binding in local["bindings"]:
        _member(root, binding["path"])
        if verify_local_inputs:
            _bound_file(root, binding)
    return FrozenRetrievalConfig(VERSION, expected_sha256, RRFConfig(20, 200, 200, 200),
        roots["clip_index_root"], roots["clip_input_root"], roots["e5_index_root"], roots["clip_index_root"], 200,
        verify_local_inputs)
