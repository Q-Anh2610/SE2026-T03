"""Preflight ảnh #89 trên đúng candidate set 200; không chạy query benchmark/qrels."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import csv
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
from uuid import uuid4

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from PIL import Image
from qdrant_client import QdrantClient
from app.schemas.text_search import TextSearchFilters, TextSearchCandidates
from app.search.image_index_manifest import load_image_index_manifest, require_same_image_inputs
from app.search.image_search import ImageRetrievalConfig, ImageSearchService
from app.search.smoke import (SmokeCheckError, audit_index, digest, handoff_file,
                              load_inputs, read_json, require, REPEAT_SCORE_ABS_TOLERANCE)
from scripts.verify_issue76_image_retrieval import (
    MODULES, build_index, load_encoder, same_ranked_results, versions,
)

SNAPSHOT = "home-interior-clear-200-v3"
SOURCE_SHA256 = "9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd"
ASSET_COUNT = 200
SNAPSHOT_CONFIRMATION = "https://github.com/Q-Anh2610/SE2026-T03/issues/89#issuecomment-6705482003"
FILTER_CONFIRMATION = "https://github.com/Q-Anh2610/SE2026-T03/issues/89#issuecomment-6705967217"
MODEL_IDS = {"clip": "openai/clip-vit-base-patch32", "siglip2": "google/siglip2-base-patch16-224"}
PREFLIGHT_MODULES = (*MODULES, "scripts/verify_issue89_image_preflight.py")


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def rows_by_id(rows, expected_count, code):
    require(isinstance(rows, list) and len(rows) == expected_count, code)
    require(all(isinstance(row, dict) and isinstance(row.get("asset_id"), str)
                and row["asset_id"] for row in rows), code)
    indexed = {row["asset_id"]: row for row in rows}
    require(len(indexed) == expected_count, code)
    return indexed


def candidate_inputs(source_path, candidates_path, provenance_path, *,
                     expected_count=ASSET_COUNT, expected_source_sha256=SOURCE_SHA256):
    require(digest(source_path) == expected_source_sha256, "source_manifest_hash_mismatch")
    metadata = rows_by_id(read_json(source_path), expected_count, "source_ids_mismatch")
    with Path(candidates_path).open(encoding="utf-8-sig", newline="") as stream:
        candidates = rows_by_id(list(csv.DictReader(stream)), expected_count, "candidate_ids_mismatch")
    provenance = read_json(provenance_path)
    require(provenance.get("snapshot") == SNAPSHOT
            and provenance.get("manifest_sha256") == expected_source_sha256,
            "provenance_snapshot_mismatch")
    previews = rows_by_id(provenance.get("previews"), expected_count, "provenance_ids_mismatch")
    require(set(metadata) == set(candidates) == set(previews), "candidate_set_mismatch")
    for aid in metadata:
        require(candidates[aid].get("preview_sha256") == previews[aid].get("sha256"),
                "candidate_provenance_checksum_mismatch")
    return metadata, candidates


def prepare_inputs(source_path, candidates_path, provenance_path, received_root, output, *,
                   received_ready="assets_354.ready.json", expected_count=ASSET_COUNT,
                   expected_source_sha256=SOURCE_SHA256):
    metadata, candidates = candidate_inputs(source_path, candidates_path, provenance_path,
        expected_count=expected_count, expected_source_sha256=expected_source_sha256)
    received = read_json(handoff_file(received_root, received_ready))
    require(isinstance(received, list), "invalid_received_ready")
    require(all(isinstance(row, dict) and isinstance(row.get("metadata"), dict)
                for row in received), "invalid_received_ready")
    received_ids = [row["metadata"].get("asset_id") for row in received]
    require(all(isinstance(aid, str) for aid in received_ids)
            and len(set(received_ids)) == len(received_ids), "ambiguous_received_ready")
    received_map = dict(zip(received_ids, received))
    require(set(metadata) <= set(received_map), "missing_received_candidate")
    selected = []
    for aid in sorted(metadata):
        row = received_map[aid]
        require(row["metadata"] == metadata[aid], "received_metadata_mismatch")
        path = handoff_file(received_root, row.get("image_path"))
        checksum = digest(path)
        require(checksum == row.get("preview_sha256") == candidates[aid].get("preview_sha256"),
                "received_preview_checksum_mismatch")
        with Image.open(path) as image:
            image.load()
        selected.append((aid, path, checksum))
    # Validate every selected input before creating a package; never overwrite a prior package.
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "previews").mkdir()
    for original, name in ((source_path, "source.json"), (candidates_path, "candidate_assets.csv"),
                           (provenance_path, "preview-provenance.json")):
        shutil.copyfile(original, output / name)
    ready = []
    for aid, original, checksum in selected:
        relative = "previews/" + checksum + original.suffix.lower()
        require(not (output / relative).exists(), "duplicate_preview_checksum")
        shutil.copyfile(original, output / relative)
        require(digest(output / relative) == checksum, "copied_preview_checksum_mismatch")
        ready.append({"metadata": metadata[aid], "image_path": relative, "preview_sha256": checksum})
    write_json(output / "ready.json", ready)
    receipt = {"schema_version": "issue89-image-input-v1", "snapshot": SNAPSHOT,
        "asset_count": expected_count, "filters": {}, "source_manifest": "source.json",
        "source_manifest_sha256": digest(output / "source.json"), "ready_manifest": "ready.json",
        "ready_manifest_sha256": digest(output / "ready.json"),
        "candidate_assets_sha256": digest(output / "candidate_assets.csv"),
        "preview_provenance_sha256": digest(output / "preview-provenance.json"),
        "snapshot_confirmation": SNAPSHOT_CONFIRMATION, "filter_confirmation": FILTER_CONFIRMATION,
        "query_images_used": False, "benchmark": False}
    write_json(output / "input-receipt.json", receipt)
    validate_package(output, expected_count=expected_count, expected_source_sha256=expected_source_sha256)
    return receipt


def validate_package(root, *, expected_count=ASSET_COUNT, expected_source_sha256=SOURCE_SHA256):
    receipt = read_json(handoff_file(root, "input-receipt.json"))
    require(receipt.get("schema_version") == "issue89-image-input-v1"
            and receipt.get("snapshot") == SNAPSHOT and receipt.get("filters") == {}
            and receipt.get("asset_count") == expected_count
            and receipt.get("source_manifest_sha256") == expected_source_sha256,
            "invalid_input_receipt")
    for path, key in (("candidate_assets.csv", "candidate_assets_sha256"),
                      ("preview-provenance.json", "preview_provenance_sha256")):
        require(digest(handoff_file(root, path)) == receipt.get(key), "input_receipt_hash_mismatch")
    metadata, candidates = candidate_inputs(handoff_file(root, "source.json"),
        handoff_file(root, "candidate_assets.csv"), handoff_file(root, "preview-provenance.json"),
        expected_count=expected_count, expected_source_sha256=expected_source_sha256)
    audited, _ = load_inputs(root, {"input": {"manifest_sha256": expected_source_sha256,
        "ready_manifest_sha256": receipt["ready_manifest_sha256"], "asset_count": expected_count}},
        source_manifest="source.json", ready_manifest="ready.json", preview_directory="previews")
    require(audited == metadata, "input_metadata_mismatch")
    for row in read_json(handoff_file(root, "ready.json")):
        require(row["preview_sha256"] == candidates[row["metadata"]["asset_id"]]["preview_sha256"],
                "ready_candidate_checksum_mismatch")
    return metadata, receipt


def check_reference(reference, receipt, candidate_limit):
    expected = (SNAPSHOT + "-sha256:" + receipt["source_manifest_sha256"],
                receipt["source_manifest_sha256"], receipt["ready_manifest_sha256"],
                receipt["asset_count"], ImageRetrievalConfig.for_limit(candidate_limit))
    actual = (reference.as_index_config().dataset_snapshot, reference.source_manifest_sha256,
              reference.ready_manifest_sha256, reference.asset_count, reference.retrieval_config)
    require(reference.as_index_config().model_id == MODEL_IDS["clip"]
            and expected == actual, "reference_inputs_mismatch")


def smoke_unfiltered(root, storage, manifest, encoder, metadata, reports):
    manifest.verify_input_hashes(root)
    manifest.check_encoder(encoder)
    ready = sorted(read_json(handoff_file(root, "ready.json")), key=lambda r: r["metadata"]["asset_id"])
    selected = [ready[i] for i in sorted({0, min(1, len(ready)-1), len(ready)-1})]
    with closing(QdrantClient(path=str(storage))) as client:
        store = manifest.make_store(client)
        before = audit_index(store, metadata)
        service = ImageSearchService(encoder, store)
        for row in selected:
            content = handoff_file(root, row["image_path"]).read_bytes()
            started = time.perf_counter()
            first = service.search_image(content, TextSearchFilters(),
                candidate_limit=manifest.retrieval_config.candidate_limit)
            elapsed = time.perf_counter() - started
            repeat = service.search_image(content, TextSearchFilters(),
                candidate_limit=manifest.retrieval_config.candidate_limit)
            ids = [hit.asset_id for hit in first.hits]
            require(len(ids) == min(manifest.retrieval_config.candidate_limit, len(metadata))
                    and set(ids) <= set(metadata) and len(ids) == len(set(ids)), "invalid_candidate_window")
            require(first.versions == manifest.execution_versions(), "execution_version_mismatch")
            reports.append({"query_asset_id": row["metadata"]["asset_id"],
                "query_sha256": row["preview_sha256"], "query_source": "indexed_preview_preflight_only",
                "filters": {}, "elapsed_seconds": elapsed,
                "repeat_consistent": same_ranked_results(first, repeat),
                "repeat_score_abs_tolerance": REPEAT_SCORE_ABS_TOLERANCE,
                "repeat_max_score_delta": max((abs(a.score-b.score) for a,b in zip(first.hits,repeat.hits)), default=0),
                "hits": [{"rank": rank, **hit.model_dump()} for rank,hit in enumerate(first.hits,1)],
                "repeat_hits": [hit.model_dump() for hit in repeat.hits],
                "versions": first.versions.model_dump()})
            require(same_ranked_results(first, repeat), "non_deterministic_results")
        after = audit_index(store, metadata)
    with closing(QdrantClient(path=str(storage))) as client:
        reopened = audit_index(manifest.make_store(client), metadata)
    require(before == reopened, "persisted_index_changed")
    return {"audit_before": before, "audit_after": after, "audit_reopened": reopened,
            "persisted_fingerprint_unchanged": True, "in_memory_fingerprint_unchanged": before == after}


def run_build(args, *, output_root=None):
    metadata, receipt = validate_package(args.input_root)
    reference = None
    if args.model == "siglip2":
        require(args.reference_manifest is not None, "missing_clip_reference_manifest")
    if args.reference_manifest:
        reference = load_image_index_manifest(args.reference_manifest)
        check_reference(reference, receipt, args.candidate_limit)
    output = (Path(output_root) if output_root is not None else REPO / "data/processed/issue89") / (args.model + "-preflight-" + uuid4().hex[:12])
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": "issue89-model-preflight-v1", "preflight_ready": False,
        "benchmark": False, "model": args.model, "filters": {}, "input": receipt,
        "input_root": str(args.input_root.resolve()), "index_manifest": "index-manifest.json",
        "command": sys.argv, "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "machine": {"platform": platform.platform(), "processor": platform.processor(),
                    "python": platform.python_version(), "device": "cpu"},
        "package_versions": versions(), "queries": [],
        "module_sha256": {name: digest(REPO / name) for name in PREFLIGHT_MODULES},
        "code_commit": subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO,text=True).strip(),
        "working_tree_dirty": bool(subprocess.check_output(["git","status","--porcelain"],cwd=REPO,text=True).strip())}
    started, stage = time.perf_counter(), "load_offline_encoder"
    try:
        encoder = load_encoder(args.model)
        report["model_load_seconds"] = time.perf_counter()-started
        stage = "build_index"
        manifest, build = build_index(args.input_root, output, encoder,
            source_manifest="source.json", ready_manifest="ready.json",
            source_sha256=receipt["source_manifest_sha256"], ready_sha256=receipt["ready_manifest_sha256"],
            asset_count=ASSET_COUNT, snapshot=SNAPSHOT, snapshot_confirmation=SNAPSHOT_CONFIRMATION,
            preview_directory="previews", candidate_limit=args.candidate_limit,
            index_prefix="issue89", collection_name="issue89_image_previews", module_paths=PREFLIGHT_MODULES)
        report["build"] = build
        if reference:
            require_same_image_inputs(reference, manifest)
        stage = "smoke_unfiltered"
        report.update(smoke_unfiltered(args.input_root, output/"qdrant", manifest, encoder, metadata, report["queries"]))
        report["preflight_ready"] = True
    except Exception as error:
        report["failure"] = {"stage": stage, "type": type(error).__name__}
        if isinstance(error, SmokeCheckError):
            report["failure"]["code"] = str(error)
    report["total_seconds"] = time.perf_counter()-started
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(output/"report.json", report)
    print(json.dumps({"preflight_ready": report["preflight_ready"], "report": str(output/"report.json")}))
    return 0 if report["preflight_ready"] else 1


def compare_reports(clip_path, siglip_path):
    paths = {"clip": Path(clip_path), "siglip2": Path(siglip_path)}
    reports = {model: read_json(path) for model,path in paths.items()}
    manifests = {}
    for model, report in reports.items():
        require(report.get("schema_version") == "issue89-model-preflight-v1"
                and report.get("preflight_ready") is True and report.get("benchmark") is False
                and report.get("model") == model and report.get("filters") == {}, "model_not_ready")
        require(report["input"]["asset_count"] == ASSET_COUNT
                and report["input"]["source_manifest_sha256"] == SOURCE_SHA256,
                "wrong_candidate_snapshot")
        require(report.get("persisted_fingerprint_unchanged") is True
                and report["audit_before"] == report["audit_reopened"]
                and report["audit_before"]["unique_asset_ids"] == ASSET_COUNT, "invalid_audit")
        manifests[model] = load_image_index_manifest(handoff_file(paths[model].parent, report["index_manifest"]))
        require(manifests[model].as_index_config().model_id == MODEL_IDS[model]
                and manifests[model].point_count == ASSET_COUNT, "wrong_model_manifest")
        metadata, receipt = validate_package(Path(report["input_root"]))
        require(report["input"] == receipt, "report_input_receipt_mismatch")
        manifest = manifests[model]
        manifest.verify_input_hashes(Path(report["input_root"]))
        require(manifest.source_manifest_sha256 == receipt["source_manifest_sha256"]
                and manifest.ready_manifest_sha256 == receipt["ready_manifest_sha256"],
                "manifest_input_mismatch")
        query_hashes = {row["metadata"]["asset_id"]: row["preview_sha256"] for row in
                        read_json(handoff_file(Path(report["input_root"]), "ready.json"))}
        for row in report["queries"]:
            result = TextSearchCandidates(hits=[{"asset_id": hit["asset_id"], "score": hit["score"]}
                                                for hit in row["hits"]], versions=row["versions"])
            repeat = TextSearchCandidates(hits=row["repeat_hits"], versions=row["versions"])
            require(row["filters"] == {} and row["query_asset_id"] in metadata
                    and row["query_sha256"] == query_hashes[row["query_asset_id"]]
                    and result.versions == manifest.execution_versions()
                    and len(result.hits) == min(manifest.retrieval_config.candidate_limit, ASSET_COUNT)
                    and {hit.asset_id for hit in result.hits} <= set(metadata)
                    and same_ranked_results(result, repeat), "invalid_report_smoke")
    require_same_image_inputs(manifests["clip"], manifests["siglip2"])
    require(paths["clip"].resolve().parent != paths["siglip2"].resolve().parent, "shared_model_storage")
    require(manifests["clip"].vector_name != manifests["siglip2"].vector_name, "shared_named_vector")
    a,b = reports["clip"]["queries"], reports["siglip2"]["queries"]
    require(len(a) == len(b) == 3, "incomplete_smoke_queries")
    for first,second in zip(a,b):
        require(all(first[k] == second[k] for k in ("query_asset_id","query_sha256","filters"))
                and first["filters"] == {} and first["repeat_consistent"] and second["repeat_consistent"],
                "inconsistent_smoke_queries")
    return {"schema_version": "issue89-two-model-preflight-v1", "preflight_ready": True,
        "benchmark": False, "snapshot": SNAPSHOT, "source_manifest_sha256": SOURCE_SHA256,
        "ready_manifest_sha256": manifests["clip"].ready_manifest_sha256, "candidate_count": ASSET_COUNT,
        "filters": {}, "filter_confirmation": FILTER_CONFIRMATION,
        "diagnostic_candidate_limit": manifests["clip"].retrieval_config.candidate_limit,
        "models": {model: {"report_path": str(paths[model]), "report_sha256": digest(paths[model]),
            "index_config": manifest.index_config, "vector_name": manifest.vector_name,
            "collection": manifest.collection, "normalization": manifest.normalization,
            "similarity": manifest.similarity, "processor_class": manifest.processor_class,
            "storage_path": str(paths[model].parent / "qdrant"),
            "index_manifest_path": str(paths[model].parent / reports[model]["index_manifest"]),
            "manifest_sha256": digest(handoff_file(paths[model].parent, reports[model]["index_manifest"])),
            "audit": reports[model]["audit_reopened"]} for model,manifest in manifests.items()},
        "limitations": ["Indexed previews used only for module preflight; no independent benchmark query run.",
            "Qrels, group split and locked evaluation protocol must be finalized before benchmark."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--received-root", type=Path, required=True)
    build = sub.add_parser("build")
    build.add_argument("--model", choices=list(MODEL_IDS), required=True)
    build.add_argument("--input-root", type=Path, required=True)
    build.add_argument("--reference-manifest", type=Path)
    build.add_argument("--candidate-limit", type=int, default=10)
    compare = sub.add_parser("compare")
    compare.add_argument("--clip-report", type=Path, required=True)
    compare.add_argument("--siglip2-report", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "prepare":
        output = REPO/"data/processed/issue89"/("inputs-"+uuid4().hex[:12])
        receipt = prepare_inputs(REPO/"data/manifests/objaverse_200.json",
            REPO/"data/benchmark/candidate_assets.csv", REPO/"data/manifests/objaverse_200.provenance.json",
            args.received_root, output)
        print(json.dumps({"prepared": True, "asset_count": ASSET_COUNT,
            "input_root": str(output), "ready_manifest_sha256": receipt["ready_manifest_sha256"]}))
        return 0
    if args.mode == "build":
        ImageRetrievalConfig.for_limit(args.candidate_limit)
        return run_build(args)
    summary = compare_reports(args.clip_report, args.siglip2_report)
    output = REPO/"data/processed/issue89"/("preflight-comparison-"+uuid4().hex[:12]+".json")
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, summary)
    print(json.dumps({"preflight_ready": True, "report": str(output)}))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
