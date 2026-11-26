"""W7 rebuild CLIP/E5 offline into new outputs; no HTTP/DB/benchmark activation."""

import argparse
from contextlib import ExitStack, closing
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
sys.dont_write_bytecode = True

CONFIG_SHA256 = "1e1962058528e22b5235d989a3613b5077c02d479b8ac19e8dbc28fee0bd08d5"
PROTOCOL_PATH = "docs/configs/issue135-rebuild-protocol-v1.json"
PROTOCOL_SHA256 = "01130a382181aed65ac461d7b6a8b55c35d6c301f3ce759b57c77e5baa40900a"


def read_git(*arguments):
    # Invoked by the operator running this CLI: read provenance only, no mutations.
    return subprocess.check_output(["git", "-C", str(ROOT), *arguments])


def provenance():
    from app.search.rebuild_audit import file_hash
    names = {p.relative_to(ROOT).as_posix()
             for directory in ("backend/app/embedding", "backend/app/search")
             for p in (ROOT / directory).glob("*.py")}
    names.update(("scripts/verify_issue135_rebuild.py", "scripts/verify_issue76_image_retrieval.py",
                  "backend/app/schemas/text_search.py", "backend/app/schemas/api.py",
                  "backend/app/ingestion/source_adapter.py", PROTOCOL_PATH))
    packages = ("torch", "transformers", "tokenizers", "safetensors", "qdrant-client",
                "numpy", "pydantic", "Pillow", "huggingface-hub")
    return {
        "code_commit": read_git("rev-parse", "HEAD").decode().strip(),
        "working_tree_dirty": bool(read_git("status", "--porcelain").strip()),
        "module_sha256": {name: file_hash(ROOT / name) for name in sorted(names)},
        "package_versions": {name: version(name) for name in packages},
        "machine": {"platform": platform.platform(), "processor": platform.processor(),
                    "architecture": platform.machine(), "python": platform.python_version()},
    }


def input_inventory(frozen, clip_manifest):
    from app.search.rebuild_audit import file_hash
    from app.search.smoke import handoff_file
    paths = [ROOT / "evaluation/configs/issue114-w6-retrieval.frozen.json",
             ROOT / "evaluation/configs/issue114-w6-retrieval.frozen.sha256",
             ROOT / "docs/adr/0001-w6-retrieval-config.md",
             ROOT / "docs/evidence/issue89-clip-image-index-manifest.json",
             ROOT / "evaluation/configs/issue114/e5-index-manifest.json",
             ROOT / "evaluation/configs/issue114/e5-corpus-manifest.json",
             frozen.clip_index_root / "index-manifest.json"]
    # Include protected historical evidence, without parsing rankings or qrels.
    paths.extend((ROOT / "docs/evidence").glob("issue91*.json"))
    for name in (clip_manifest.source_manifest, clip_manifest.ready_manifest):
        paths.append(handoff_file(frozen.clip_input_root, name))
    ready = json.loads((frozen.clip_input_root / clip_manifest.ready_manifest).read_bytes())
    paths.extend(handoff_file(frozen.clip_input_root, row["image_path"]) for row in ready)
    for name in ("index-manifest.json", "source.json", "corpus.jsonl", "corpus-manifest.json"):
        paths.append(frozen.e5_index_root / name)
    return {p.resolve().relative_to(ROOT).as_posix(): file_hash(p) for p in sorted(set(paths))}


def audit_pair(clip_manifest, e5_manifest, clip_client, e5_client, metadata, e5_root):
    from app.search.e5_index import audit_metadata_index
    from app.search.smoke import audit_index
    return {"clip": audit_index(clip_manifest.make_store(clip_client), metadata),
            "e5": audit_metadata_index(e5_manifest, e5_client, e5_root)}


def check_results(result, expected_ids, expected_versions):
    from app.search.rebuild_audit import require
    ids = [hit.asset_id for hit in result.hits]
    require(len(ids) == len(set(ids)) == len(expected_ids) and set(ids) == set(expected_ids),
            "smoke_filters_count_or_dedup_mismatch")
    require(list(result.hits) == sorted(result.hits, key=lambda h: (-h.score, h.asset_id)),
            "smoke_ordering_mismatch")
    require(result.versions == expected_versions, "smoke_versions_mismatch")


def smoke(clip_encoder, e5_encoder, clip_client, e5_client, clip_root, e5_root,
          input_root, metadata, protocol, frozen):
    from app.schemas.text_search import TextSearchFilters
    from app.search.experimental_text_search import CLIPTextSource, E5MetadataSearchService, ExperimentalFusionService
    from app.search.image_search import ImageSearchService
    from app.search.rebuild_audit import require
    from app.search.retrieval_config import RetrievalConfig
    from app.search.smoke import handoff_file, matches

    clip = CLIPTextSource(clip_encoder, clip_client, clip_root, input_root=input_root)
    e5 = E5MetadataSearchService(e5_encoder, e5_client, e5_root)
    fusion = ExperimentalFusionService(clip, e5)
    query = protocol["text_probe"]
    category = protocol["empty_category"]
    require(all(row.get("category") != category for row in metadata.values()), "empty_probe_category_exists")
    # Fixed properties, no relevance labels, ranking targets or parameter selection.
    cases = ({}, {"category": category})
    rows = []
    for filters in cases:
        expected = {aid for aid, row in metadata.items() if matches(row, TextSearchFilters(**filters))}
        clip_result = clip.search_text(query, filters, candidate_limit=200)
        clip_versions = clip.manifest.execution_versions().model_copy(update={
            "config_version": RetrievalConfig.for_limit(200).config_version})
        # CLIP source wraps the existing TextSearchService; it exposes a SourceRanking.
        require({h.asset_id for h in clip_result.hits} == expected
                and len(clip_result.hits) == len(expected), "clip_smoke_count_mismatch")
        require(clip_result.provenance.config_version == clip_versions.config_version,
                "clip_smoke_config_mismatch")
        e5_result = e5.search_text(query, filters, candidate_limit=200)
        require({h.asset_id for h in e5_result.hits} == expected
                and len(e5_result.hits) == len(expected), "e5_smoke_count_mismatch")
        result = fusion.search_text(query, filters, config=frozen.rrf_config)
        ids = [hit.asset_id for hit in result.hits]
        require(len(ids) == len(set(ids)) == len(expected) and set(ids) == expected,
                "fusion_smoke_filters_or_dedup_mismatch")
        require(result.parameters["rank_constant"] == 20
                and result.parameters["weights"] == [1, 1]
                and result.parameters["source_retrieval_window"] == 200
                and result.parameters["clip_candidate_limit"] == 200
                and result.parameters["e5_candidate_limit"] == 200
                and result.parameters["cutoff"] == 200, "fusion_smoke_parameters_mismatch")
        require(result.filters == filters and all(r.filters == filters for r in result.raw_rankings)
                and [s.source for s in result.sources] == ["clip_text_to_preview", "e5_text_to_metadata"],
                "fusion_smoke_provenance_mismatch")
        require(list(result.hits) == sorted(result.hits, key=lambda h: (-h.score, h.asset_id)),
                "fusion_smoke_ordering_mismatch")
        rows.append({"filters": filters, "clip_count": len(clip_result.hits),
                     "e5_count": len(e5_result.hits), "fusion_count": len(ids),
                     "parameters": result.parameters, "passed": True})

    # Image queries follow text/fusion: local cosine may normalize RAM in place.
    # Persistence is checked separately after clients have closed, with exact hashes.
    ready = json.loads((input_root / clip.manifest.ready_manifest).read_bytes())
    first = min(ready, key=lambda row: row["metadata"]["asset_id"])
    content = handoff_file(input_root, first["image_path"]).read_bytes()
    image_service = ImageSearchService(clip_encoder, clip.store)
    for filters in cases:
        expected = {aid for aid, row in metadata.items() if matches(row, TextSearchFilters(**filters))}
        result = image_service.search_image(content, TextSearchFilters(**filters), candidate_limit=200)
        check_results(result, expected, clip.manifest.execution_versions())
        rows.append({"service": "image", "filters": filters, "count": len(result.hits),
                     "probe_asset_id": first["metadata"]["asset_id"], "passed": True})
    return rows


def run(output):
    from app.search.rebuild_audit import (RebuildCheckError, compare_indexes, copy_reference,
                                         file_hash, require, storage_hashes, write_json)
    output = Path(output).resolve()
    base = (ROOT / "data/processed/issue135").resolve()
    require(output.is_relative_to(base) and output != base and not output.exists(), "output_requires_new_issue135_directory")
    protocol_raw = (ROOT / PROTOCOL_PATH).read_bytes()
    require(sha256(protocol_raw).hexdigest() == PROTOCOL_SHA256, "protocol_hash_mismatch")
    protocol = json.loads(protocol_raw)
    output.mkdir(parents=True, exist_ok=False)
    # Freeze the actual protocol bytes before loading models or comparing vectors.
    (output / "protocol.json").write_bytes(protocol_raw)
    started = datetime.now(timezone.utc).isoformat()
    report = {"schema_version": "issue135-rebuild-report-v1", "status": "blocked", "stage": "dependencies",
              "started_at_utc": started, "protocol_sha256": PROTOCOL_SHA256,
              "fixture_encoder": False, "benchmark_executed": False, "held_out_queries_executed": 0,
              "runtime_activated": False, "benchmark_binding_reviewed": False,
              "other_member_reproduced": False}
    original_storages, inputs_before, frozen, clip_reference = {}, None, None, None
    try:
        # Set hub offline policy before importing transformers through e5_index.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        for name, pin in (("qdrant-client", "qdrant_client_version"), ("torch", "torch_version"),
                          ("transformers", "transformers_version")):
            require(version(name) == protocol[pin], "dependency_version_mismatch")
        from app.search.frozen_retrieval_config import load_frozen_config
        from app.search.image_index_manifest import load_image_index_manifest
        from app.search.e5_index import (load_e5_index_manifest, load_metadata_corpus, build_metadata_index)
        from app.search.smoke import load_inputs
        frozen = load_frozen_config(ROOT / "evaluation/configs/issue114-w6-retrieval.frozen.json",
                                    expected_sha256=CONFIG_SHA256, repo_root=ROOT, verify_local_inputs=True)
        clip_reference = load_image_index_manifest(frozen.clip_index_root / "index-manifest.json")
        e5_reference = load_e5_index_manifest(frozen.e5_index_root / "index-manifest.json")
        metadata, receipt = load_inputs(frozen.clip_input_root, {"input": {
            "manifest_sha256": clip_reference.source_manifest_sha256,
            "ready_manifest_sha256": clip_reference.ready_manifest_sha256, "asset_count": 200}},
            source_manifest=clip_reference.source_manifest, ready_manifest=clip_reference.ready_manifest,
            preview_directory="previews")
        corpus = load_metadata_corpus(frozen.e5_index_root,
            (frozen.e5_index_root / "source.json").read_bytes(),
            expected_source_sha256=clip_reference.source_manifest_sha256,
            expected_corpus_sha256=e5_reference.corpus_sha256,
            expected_recipe_version=e5_reference.recipe_version, manifest_name="corpus-manifest.json")
        require(corpus.metadata == metadata, "clip_e5_metadata_mismatch")
        inputs_before = input_inventory(frozen, clip_reference)
        info = provenance()
        report.update(provenance=info, input=receipt)
        write_json(output / "input-inventory.json", inputs_before)
        original_roots = {"clip": frozen.clip_index_root, "e5": frozen.e5_index_root}
        for name, root in original_roots.items():
            original_storages[name] = storage_hashes(root / "qdrant")
        for name, root in original_roots.items():
            copy_reference(root, output / "reference-copies" / name, original_storages[name])
        report["reference_storage_sha256"] = original_storages

        report["stage"] = "offline_models"
        import torch
        torch.set_num_threads(protocol["torch_threads"])
        torch.set_num_interop_threads(protocol["torch_interop_threads"])
        torch.manual_seed(protocol["seed"])
        from app.embedding.clip_encoder import CLIPEncoder
        from app.embedding.e5_encoder import E5Encoder
        clip_encoder = CLIPEncoder(device="cpu", local_files_only=True)
        e5_encoder = E5Encoder(device="cpu", local_files_only=True)
        for encoder in (clip_encoder, e5_encoder):
            require(encoder.model.config._commit_hash == encoder.revision, "resolved_model_revision_mismatch")
        clip_reference.check_encoder(clip_encoder)
        e5_reference.check_encoder(e5_encoder)
        report["models"] = [{"model_id": e.model_id, "revision": e.revision,
                             "resolved_config_commit": e.model.config._commit_hash,
                             "tokenizer_revision_requested": e.revision,
                             "preprocessing_version": e.preprocessing_version,
                             "device": str(e.device), "dimension": e.dimension,
                             "local_files_only": True} for e in (clip_encoder, e5_encoder)]
        report["execution"] = {"clip_batch_size": 8, "e5_batch_size": 16, "seed": 0,
                                "torch_threads": torch.get_num_threads(),
                                "torch_interop_threads": torch.get_num_interop_threads()}

        report["stage"] = "clip_build"
        print("W7: building CLIP from 200 pinned previews into new storage...", flush=True)
        from scripts.verify_issue76_image_retrieval import build_index
        clip_root, e5_root = output / "clip", output / "e5"
        clip_root.mkdir()
        clip_manifest, clip_build = build_index(frozen.clip_input_root, clip_root, clip_encoder,
            source_manifest=clip_reference.source_manifest, ready_manifest=clip_reference.ready_manifest,
            source_sha256=clip_reference.source_manifest_sha256, ready_sha256=clip_reference.ready_manifest_sha256,
            asset_count=200, snapshot="home-interior-clear-200-v3",
            snapshot_confirmation=clip_reference.snapshot_confirmation, preview_directory="previews",
            candidate_limit=200, index_prefix="issue135-" + output.name,
            collection_name=clip_reference.collection, module_paths=tuple(info["module_sha256"]))
        report["clip_build"] = clip_build
        report["stage"] = "e5_build"
        print("W7: building E5 from 200 pinned passages into new storage...", flush=True)
        e5_manifest = build_metadata_index(e5_encoder, corpus, e5_root, batch_size=16,
            code_commit=info["code_commit"], working_tree_dirty=info["working_tree_dirty"],
            module_sha256=info["module_sha256"], package_versions=info["package_versions"])
        report["e5_build"] = {"input_count": 200, "embedded": 200, "failed": 0,
                               "skipped": 0, "corpus_sha256": e5_manifest.corpus_sha256,
                               "recipe_version": e5_manifest.recipe_version}

        report["stage"] = "compatibility_and_reopen"
        from qdrant_client import QdrantClient
        def clients(stack, clip_path, e5_path):
            return [stack.enter_context(closing(QdrantClient(path=str(p / "qdrant"))))
                    for p in (clip_path, e5_path)]
        with ExitStack() as stack:
            cc, ec = clients(stack, clip_root, e5_root)
            rc, re = clients(stack, output / "reference-copies/clip", output / "reference-copies/e5")
            baseline = audit_pair(clip_manifest, e5_manifest, cc, ec, metadata, e5_root)
            reference_audit = audit_pair(clip_reference, e5_reference, rc, re, metadata,
                                         output / "reference-copies/e5")
            for name in ("clip", "e5"):
                require(reference_audit[name]["point_payload_vector_sha256"]
                        == protocol["reference_fingerprints"][name], "historical_reference_fingerprint_mismatch")
            report.update(reference_audit=reference_audit, rebuilt_audit=baseline,
                          reference_comparison={}, persisted_reopen_exact=False)
            for name, rm, bm, ref_client, new_client in (
                    ("clip", clip_reference, clip_manifest, rc, cc),
                    ("e5", e5_reference, e5_manifest, re, ec)):
                report["reference_comparison"][name] = compare_indexes(
                    rm.make_store(ref_client), bm.make_store(new_client),
                    vector_abs_tolerance=protocol["vector_component_abs_tolerance"], expected_ids=sorted(metadata))
        # Exact second reopen, before any query; separate from tolerant reference comparison.
        with ExitStack() as stack:
            cc, ec = clients(stack, clip_root, e5_root)
            require(audit_pair(clip_manifest, e5_manifest, cc, ec, metadata, e5_root) == baseline,
                    "persisted_second_reopen_mismatch")
            report["stage"] = "real_model_service_smoke"
            report["smoke"] = smoke(clip_encoder, e5_encoder, cc, ec, clip_root, e5_root,
                                     frozen.clip_input_root, metadata, protocol, frozen)
        with ExitStack() as stack:
            cc, ec = clients(stack, clip_root, e5_root)
            require(audit_pair(clip_manifest, e5_manifest, cc, ec, metadata, e5_root) == baseline,
                    "persisted_storage_changed_after_smoke")
        report["persisted_reopen_exact"] = True
        report["stage"] = "final_integrity"
        require(input_inventory(frozen, clip_reference) == inputs_before, "original_inputs_or_freeze_changed")
        require(provenance() == info, "code_or_environment_changed_during_run")
        for name, root in original_roots.items():
            require(storage_hashes(root / "qdrant") == original_storages[name], "original_storage_changed")
        mapping = {"schema_version": "issue135-index-reference-map-v1", "review_status": "pending",
                   "frozen_config_sha256": CONFIG_SHA256, "protocol_sha256": PROTOCOL_SHA256,
                   "runtime_activation_authorized": False, "benchmark_binding_reviewed": False,
                   "sources": {name: {"reference_manifest_sha256": file_hash(r / "index-manifest.json"),
                                       "rebuilt_manifest": name + "/index-manifest.json",
                                       "rebuilt_manifest_sha256": file_hash(b / "index-manifest.json"),
                                       "reference_index_version": rm.index_config["index_version"],
                                       "rebuilt_index_version": bm.index_config["index_version"],
                                       "reference_collection": rm.collection, "rebuilt_collection": bm.collection,
                                       "reference_vector_name": rm.vector_name, "rebuilt_vector_name": bm.vector_name}
                               for name, r, b, rm, bm in (
                                   ("clip", frozen.clip_index_root, clip_root, clip_reference, clip_manifest),
                                   ("e5", frozen.e5_index_root, e5_root, e5_reference, e5_manifest))}}
        write_json(output / "reference-map.json", mapping)
        report.update(status="rebuild_and_service_smoke_verified", stage="complete")
    except Exception as error:
        from app.search.frozen_retrieval_config import FrozenConfigError
        from app.search.smoke import SmokeCheckError
        report.update(status="blocked", error_type=type(error).__name__,
                      reason=str(error) if isinstance(error, (RebuildCheckError, FrozenConfigError, SmokeCheckError))
                      else "dependency_or_build_check_failed")
        if isinstance(error, RebuildCheckError) and error.details is not None:
            report["failure_details"] = error.details
    finally:
        unchanged = bool(original_storages) and len(original_storages) == 2
        if frozen is not None:
            for name, hashes in original_storages.items():
                try:
                    root = frozen.clip_index_root if name == "clip" else frozen.e5_index_root
                    unchanged = unchanged and storage_hashes(root / "qdrant") == hashes
                except Exception:
                    unchanged = False
            if inputs_before is not None:
                try:
                    report["original_inputs_and_freeze_unchanged"] = input_inventory(frozen, clip_reference) == inputs_before
                except Exception:
                    report["original_inputs_and_freeze_unchanged"] = False
        report["original_storage_bytes_unchanged"] = unchanged
        if report["status"] == "rebuild_and_service_smoke_verified" and (
                not unchanged or not report.get("original_inputs_and_freeze_unchanged")):
            report.update(status="blocked", reason="original_artifacts_changed")
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(output / "report.json", report)
        files = [p for p in output.rglob("*.json") if "qdrant" not in p.parts
                 and "reference-copies" not in p.parts]
        with (output / "CHECKSUMS.sha256").open("x", encoding="utf-8", newline="\n") as stream:
            stream.writelines(f"{file_hash(p)}  {p.relative_to(output).as_posix()}\n" for p in sorted(files))
    print(json.dumps({"status": report["status"], "stage": report["stage"],
                      "reason": report.get("reason"), "report": str(output / "report.json"),
                      "benchmark_binding_reviewed": False}, ensure_ascii=False))
    return 0 if report["status"] == "rebuild_and_service_smoke_verified" else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New directory under data/processed/issue135; never reuse a run.")
    args = parser.parse_args(argv)
    output = args.output or ROOT / "data/processed/issue135" / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8])
    try:
        return run(output)
    except Exception as error:
        # Failure before report directory creation; no success artifact is emitted.
        from app.search.rebuild_audit import RebuildCheckError
        print(json.dumps({"status": "blocked", "error_type": type(error).__name__,
                          "reason": str(error) if isinstance(error, RebuildCheckError)
                          else "protocol_or_output_unavailable"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
