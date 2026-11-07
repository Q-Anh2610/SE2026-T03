"""Build index ảnh riêng sau xác nhận TV2 hoặc smoke chỉ đọc index có sẵn.

Không tải weights/preview, không ghi DB; self-preview chỉ là diagnostic.
"""

import argparse
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import version
import json
from math import isclose
from pathlib import Path
import platform
import subprocess
import sys
import time
from uuid import uuid4

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from qdrant_client import QdrantClient
from app.schemas.text_search import TextSearchFilters
from app.search.image_index_manifest import ImageIndexManifest, save_image_index_manifest, load_image_index_manifest, require_same_image_inputs
from app.search.image_search import ImageRetrievalConfig, ImageSearchService
from app.search.index_manifest import IndexManifest
from app.search.qdrant_store import IndexConfig, QdrantStore
from app.search.smoke import audit_index, digest, handoff_file, load_inputs, matches, read_json, require, smoke_cases, SmokeCheckError, REPEAT_SCORE_ABS_TOLERANCE

MODULES = (
    "backend/app/embedding/clip_encoder.py", "backend/app/embedding/siglip2_encoder.py",
    "backend/app/embedding/image_encoding.py", "backend/app/embedding/batch.py",
    "backend/app/search/image_search.py", "backend/app/search/image_index_manifest.py",
    "backend/app/search/vector_search.py", "backend/app/search/qdrant_store.py",
    "backend/app/search/filters.py", "backend/app/search/smoke.py",
    "backend/app/schemas/api.py", "backend/app/schemas/text_search.py",
    "scripts/verify_issue76_image_retrieval.py",
)


def versions():
    return {name: version(name) for name in ("torch", "transformers", "Pillow", "qdrant-client")}


def load_encoder(model):
    if model == "clip":
        from app.embedding.clip_encoder import CLIPEncoder
        return CLIPEncoder(local_files_only=True)
    from app.embedding.siglip2_encoder import SigLIP2Encoder
    return SigLIP2Encoder(local_files_only=True)


def check_inputs(root, manifest, preview_directory):
    return load_inputs(root, {"input": {
        "manifest_sha256": manifest.source_manifest_sha256,
        "ready_manifest_sha256": manifest.ready_manifest_sha256,
        "asset_count": manifest.asset_count,
    }}, source_manifest=manifest.source_manifest, ready_manifest=manifest.ready_manifest,
        preview_directory=preview_directory)


def build_index(root, output, encoder, *, source_manifest, ready_manifest,
                source_sha256, ready_sha256, asset_count, snapshot, snapshot_confirmation,
                preview_directory, candidate_limit, index_prefix="issue76",
                collection_name="issue76_image_previews", module_paths=MODULES):
    """Caller phải xác nhận TV2 trước; fixture tests dùng thư mục tạm riêng."""
    require(bool(snapshot_confirmation and snapshot_confirmation.strip()), "missing_tv2_snapshot_confirmation")
    metadata, receipt = load_inputs(root, {"input": {
        "manifest_sha256": source_sha256, "ready_manifest_sha256": ready_sha256,
        "asset_count": asset_count,
    }}, source_manifest=source_manifest, ready_manifest=ready_manifest, preview_directory=preview_directory)
    require(not (output / "qdrant").exists(), "output_index_already_exists")
    from app.embedding.batch import AssetImage, embed_assets
    ready = read_json(handoff_file(root, ready_manifest))
    started = time.perf_counter()
    batch = embed_assets([AssetImage(row["metadata"], handoff_file(root, row["image_path"]))
                          for row in ready], encoder, batch_size=8)
    require(batch.summary == {"embedded": asset_count, "failed": 0, "skipped": 0}, "embedding_incomplete")
    elapsed = time.perf_counter() - started
    config = IndexConfig(encoder.model_id, encoder.revision, encoder.dimension,
        encoder.preprocessing_version, snapshot + "-sha256:" + source_sha256,
        index_prefix + "-" + output.name)
    storage = output / "qdrant"
    require(not storage.exists(), "output_index_already_exists")
    with closing(QdrantClient(path=str(storage))) as client:
        store = QdrantStore(client, collection_name=collection_name, config=config)
        require(store.upsert(batch.embedded) == asset_count, "upsert_incomplete")
        audit = audit_index(store, metadata)
        processor = getattr(encoder.processor, "image_processor", encoder.processor)
        observed = datetime.now(timezone.utc)
        manifest = ImageIndexManifest(
            created_at_utc=datetime.now(timezone.utc), observed_at_utc=observed,
            index_config=asdict(config), collection=store.collection_name, vector_name=store.vector_name,
            processor_revision=encoder.revision, processor_class=type(processor).__name__,
            processor_config=processor.to_dict(), source_manifest=source_manifest,
            source_manifest_sha256=source_sha256, ready_manifest=ready_manifest,
            ready_manifest_sha256=ready_sha256, asset_count=asset_count,
            point_count=audit["exact_point_count"], snapshot_confirmation=snapshot_confirmation,
            code_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
            working_tree_dirty=bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True).strip()),
            module_sha256={name: digest(REPO / name) for name in module_paths},
            package_versions=versions(), retrieval_config=ImageRetrievalConfig.for_limit(candidate_limit))
        save_image_index_manifest(manifest, output / "index-manifest.json")
    return manifest, {"input": receipt, "embedding_seconds": elapsed, "summary": batch.summary}


def same_ranked_results(first, second):
    return (first.versions == second.versions
            and [hit.asset_id for hit in first.hits] == [hit.asset_id for hit in second.hits]
            and all(isclose(a.score, b.score, rel_tol=0, abs_tol=REPEAT_SCORE_ABS_TOLERANCE)
                    for a, b in zip(first.hits, second.hits)))


def smoke_index(root, storage, manifest, encoder, *, preview_directory, candidate_limit, reports=None):
    metadata, receipt = check_inputs(root, manifest, preview_directory)
    manifest.check_encoder(encoder)
    ready = sorted(read_json(handoff_file(root, manifest.ready_manifest)), key=lambda row: row["metadata"]["asset_id"])
    reports = [] if reports is None else reports
    with closing(QdrantClient(path=str(storage))) as client:
        store = manifest.make_store(client)
        before = audit_index(store, metadata)
        service = ImageSearchService(encoder, store)
        # All inputs are indexed previews: no quality metric or held-out benchmark claim.
        cases = [("self_preview_" + str(i + 1), row, {}) for i, row in enumerate(ready[:3])]
        cases += [(label, ready[0], filters) for label, _, filters in smoke_cases(metadata)
                  if label not in {"unfiltered_en", "unfiltered_vi", "token_truncation"}]
        for label, row, raw_filters in cases:
            content = handoff_file(root, row["image_path"]).read_bytes()
            filters = TextSearchFilters(**raw_filters)
            started = time.perf_counter()
            result = service.search_image(content, filters, candidate_limit=candidate_limit)
            elapsed = time.perf_counter() - started
            repeat = service.search_image(content, filters, candidate_limit=candidate_limit)
            repeat_delta = max((abs(a.score - b.score) for a, b in zip(result.hits, repeat.hits)), default=0)
            expected = {aid for aid, record in metadata.items() if matches(record, filters)}
            ids = [hit.asset_id for hit in result.hits]
            require(len(ids) == min(len(expected), candidate_limit) and set(ids) <= expected,
                    "filter_or_count_mismatch")
            reports.append({"case": label, "query_asset_id": row["metadata"]["asset_id"],
                "query_image_path": row["image_path"], "query_sha256": digest(handoff_file(root, row["image_path"])),
                "query_source": "indexed_preview_diagnostic_only", "filters": raw_filters,
                "elapsed_seconds": elapsed, "repeat_consistent": same_ranked_results(result, repeat),
                "repeat_exact_equal": repeat == result,
                "repeat_score_abs_tolerance": REPEAT_SCORE_ABS_TOLERANCE,
                "repeat_max_score_delta": repeat_delta,
                "repeat_hits": [hit.model_dump() for hit in repeat.hits],
                "self_in_top_k": row["metadata"]["asset_id"] in ids,
                "hits": [{"rank": i + 1, **hit.model_dump()} for i, hit in enumerate(result.hits)],
                "versions": result.versions.model_dump()})
            require(same_ranked_results(result, repeat), "non_deterministic_results")
        after = audit_index(store, metadata)
        # Qdrant local 1.15.1 cosine normalizes its RAM arrays in place.
        # Compare persisted content after closing/reopening; record RAM drift explicitly.
    with closing(QdrantClient(path=str(storage))) as client:
        reopened = audit_index(manifest.make_store(client), metadata)
    require(before == reopened, "persisted_index_changed")
    return {"input": receipt, "audit_before": before, "audit_after": after,
            "audit_reopened": reopened, "in_memory_fingerprint_unchanged": before == after,
            "persisted_fingerprint_unchanged": before == reopened, "queries": reports, "passed": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["build", "smoke"])
    parser.add_argument("--model", choices=["clip", "siglip2"], required=True)
    parser.add_argument("--handoff-root", type=Path, required=True)
    parser.add_argument("--preview-directory", default="previews")
    parser.add_argument("--candidate-limit", type=int, default=10)
    parser.add_argument("--index-manifest", type=Path)
    parser.add_argument("--reference-manifest", type=Path, help="Manifest ảnh CLIP để kiểm tra cùng input khi build SigLIP 2.")
    parser.add_argument("--qdrant-path", type=Path)
    parser.add_argument("--source-manifest")
    parser.add_argument("--ready-manifest")
    parser.add_argument("--source-sha256")
    parser.add_argument("--ready-sha256")
    parser.add_argument("--asset-count", type=int)
    parser.add_argument("--snapshot")
    parser.add_argument("--snapshot-confirmation", help="Link TV2 xác nhận snapshot W4; không tự suy ra từ W3.")
    args = parser.parse_args()
    ImageRetrievalConfig.for_limit(args.candidate_limit)
    if args.mode == "smoke" and not (args.index_manifest and args.qdrant_path):
        parser.error("smoke cần --index-manifest và --qdrant-path có sẵn")
    if args.mode == "build" and not all((args.source_manifest, args.ready_manifest, args.source_sha256,
            args.ready_sha256, args.asset_count, args.snapshot, args.snapshot_confirmation)):
        parser.error("build cần source/ready manifest, hai SHA-256, asset-count, snapshot và xác nhận TV2")
    if args.mode == "build" and args.model == "siglip2" and not args.reference_manifest:
        parser.error("build SigLIP 2 cần --reference-manifest của index ảnh CLIP cùng snapshot")
    if args.mode == "build" and args.reference_manifest:
        reference = load_image_index_manifest(args.reference_manifest)
        expected = (args.snapshot + "-sha256:" + args.source_sha256, args.source_sha256,
                    args.ready_sha256, args.asset_count, ImageRetrievalConfig.for_limit(args.candidate_limit))
        actual = (reference.as_index_config().dataset_snapshot, reference.source_manifest_sha256,
                  reference.ready_manifest_sha256, reference.asset_count, reference.retrieval_config)
        if actual != expected:
            parser.error("reference-manifest không cùng snapshot/checksum/cutoff; chưa build index")
    output = REPO / "data/processed/issue76" / (args.model + "-" + args.mode + "-" + uuid4().hex[:12])
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": "issue76-image-diagnostic-v1", "passed": False,
        "started_at_utc": datetime.now(timezone.utc).isoformat(), "mode": args.mode,
        "benchmark": False, "model": args.model, "command": sys.argv,
        "machine": {"platform": platform.platform(), "processor": platform.processor(),
                    "python": platform.python_version(), "device": "cpu"},
        "package_versions": versions(),
        "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "working_tree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True).strip()),
        "module_sha256": {name: digest(REPO / name) for name in MODULES}}
    stage, started = "load_offline_encoder", time.perf_counter()
    try:
        encoder = load_encoder(args.model)
        report["model_load_seconds"] = time.perf_counter() - started
        stage = "build" if args.mode == "build" else "load_manifest"
        if args.mode == "build":
            manifest, build = build_index(args.handoff_root, output, encoder,
                source_manifest=args.source_manifest, ready_manifest=args.ready_manifest,
                source_sha256=args.source_sha256, ready_sha256=args.ready_sha256,
                asset_count=args.asset_count, snapshot=args.snapshot,
                snapshot_confirmation=args.snapshot_confirmation, preview_directory=args.preview_directory,
                candidate_limit=args.candidate_limit)
            report["build"] = build
            if args.reference_manifest:
                reference = load_image_index_manifest(args.reference_manifest)
                require_same_image_inputs(reference, manifest)
                report["comparison_inputs_match"] = True
            storage = output / "qdrant"
        else:
            raw = read_json(args.index_manifest)
            manifest = (ImageIndexManifest if raw.get("schema_version") == "image-index-manifest-v1" else IndexManifest).model_validate(raw)
            storage = args.qdrant_path
            require(storage.is_dir() and any(storage.iterdir()), "missing_existing_qdrant_storage")
        stage = "smoke"
        report["queries"] = []
        report.update(smoke_index(args.handoff_root, storage, manifest, encoder,
            preview_directory=args.preview_directory, candidate_limit=args.candidate_limit, reports=report["queries"]))
    except Exception as error:
        report["failure"] = {"stage": stage, "type": type(error).__name__}
        if isinstance(error, SmokeCheckError):
            report["failure"]["code"] = str(error)
        # Never print raw exceptions which can contain local inputs/URLs.
    report["total_seconds"] = time.perf_counter() - started
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    with (output / "report.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": report["passed"], "report": str(output / "report.json")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
