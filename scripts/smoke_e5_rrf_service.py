"""Smoke service CLIP/E5/RRF trên index có sẵn, query tự tạo; không benchmark."""

import argparse
from contextlib import ExitStack, closing
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def open_existing_index(root):
    from qdrant_client import QdrantClient
    storage = Path(root) / "qdrant"
    if not storage.is_dir() or not (storage / "meta.json").is_file():
        raise ValueError("Need existing local Qdrant storage; smoke never creates an index.")
    return QdrantClient(path=str(storage))


def compare_source_rankings(first, repeat):
    """Exact ranks/provenance; report bounded raw cosine roundoff separately."""
    first, repeat = asdict(first), asdict(repeat)
    first_hits, repeat_hits = first.pop("hits"), repeat.pop("hits")
    if first != repeat or len(first_hits) != len(repeat_hits):
        raise RuntimeError("Source repeat provenance/count mismatch.")
    delta = 0.0
    for a, b in zip(first_hits, repeat_hits, strict=True):
        a_score, b_score = a.pop("score"), b.pop("score")
        if a != b:
            raise RuntimeError("Source repeat IDs/ranks mismatch.")
        delta = max(delta, abs(a_score - b_score))
    if delta > 1e-12:
        raise RuntimeError("Source repeat cosine exceeds diagnostic tolerance 1e-12.")
    return delta


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clip-index-root", required=True, type=Path)
    parser.add_argument("--clip-input-root", required=True, type=Path)
    parser.add_argument("--e5-index-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--rank-constant", required=True, type=int)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output đã tồn tại, chọn thư mục mới.")
    from app.search.rrf import RRFConfig
    config = RRFConfig(rank_constant=args.rank_constant, clip_candidate_limit=200,
                       e5_candidate_limit=200, cutoff=200)
    from app.embedding.clip_encoder import CLIPEncoder
    from app.embedding.e5_encoder import E5Encoder
    from app.search.experimental_text_search import CLIPTextSource, E5MetadataSearchService, ExperimentalFusionService
    from app.search.e5_index import digest, json_bytes
    from app.search.smoke import matches
    import torch

    started = datetime.now(timezone.utc).isoformat()
    start = perf_counter()
    print("Loading pinned CLIP/E5 from offline cache...", flush=True)
    clip_encoder = CLIPEncoder(device="cpu", local_files_only=True)
    e5_encoder = E5Encoder(device="cpu", local_files_only=True)
    load_seconds = perf_counter() - start
    with ExitStack() as stack:
        clip_client = stack.enter_context(closing(open_existing_index(args.clip_index_root)))
        e5_client = stack.enter_context(closing(open_existing_index(args.e5_index_root)))
        clip = CLIPTextSource(clip_encoder, clip_client, args.clip_index_root,
                              input_root=args.clip_input_root, manifest_ref="clip-index-manifest.json")
        e5 = E5MetadataSearchService(e5_encoder, e5_client, args.e5_index_root,
                                     manifest_ref="e5-index-manifest.json")
        service = ExperimentalFusionService(clip, e5)
        row = next(row for row in e5.metadata.values() if row.get("category") and row.get("formats") and row.get("license"))
        cases = [
            ("english_unfiltered", "wooden chair", {}),
            ("vietnamese_diagnostic", "ghế gỗ", {}),
            ("and_metadata_filters", "wooden chair", {"category": row["category"], "license": row["license"], "format": row["formats"][0]}),
            ("nullable_face_count", "wooden chair", {"face_count_min": 0, "face_count_max": 0}),
            ("empty_category", "wooden chair", {"category": "__issue91_diagnostic_absent_category__"}),
        ]
        output, results = [], []
        from app.schemas.text_search import TextSearchFilters
        for name, query, filters in cases:
            result = service.search_text(query, filters, config=config)
            expected_ids = {aid for aid, metadata in e5.metadata.items()
                            if matches(metadata, TextSearchFilters(**filters))}
            for ranking in result.raw_rankings:
                ids = [hit.asset_id for hit in ranking.hits]
                if len(ids) != len(set(ids)) or set(ids) != expected_ids:
                    raise RuntimeError("Source ranking không khớp filtered candidate universe.")
            fused_ids = [hit.asset_id for hit in result.hits]
            if set(fused_ids) != expected_ids or len(fused_ids) != len(expected_ids):
                raise RuntimeError("Fusion thiếu/thừa/trùng asset IDs.")
            output.append({"case": name, "query": query, "expected_filtered_count": len(expected_ids),
                           "source_counts": {r.source: len(r.hits) for r in result.raw_rankings},
                           "result": asdict(result)})
            results.append(result)
        repeat = service.search_text(cases[0][1], cases[0][2], config=config)
        first_dto, repeat_dto = asdict(results[0]), asdict(repeat)
        first_dto.pop("raw_rankings"); repeat_dto.pop("raw_rankings")
        if first_dto != repeat_dto:
            raise RuntimeError("Repeat fusion ranking/provenance không xác định.")
        repeat_deltas = {a.source: compare_source_rankings(a, b)
                         for a, b in zip(results[0].raw_rankings, repeat.raw_rankings, strict=True)}
        e5_only_delta = compare_source_rankings(results[0].raw_rankings[1], e5.search_text(cases[0][1], {}))
        clip.assert_ready(); e5.assert_ready()
        ram_after = {"clip": clip.current_audit, "e5": e5.current_audit}
        stack.close()
        # A new client observes disk values, independently of RAM query normalization.
        from app.search.smoke import audit_index
        from app.search.e5_index import audit_metadata_index
        with ExitStack() as reopened:
            clip_disk = reopened.enter_context(closing(open_existing_index(args.clip_index_root)))
            e5_disk = reopened.enter_context(closing(open_existing_index(args.e5_index_root)))
            persisted_after = {
                "clip": audit_index(clip.manifest.make_store(clip_disk), clip.metadata),
                "e5": audit_metadata_index(e5.manifest, e5_disk, args.e5_index_root),
            }
        persisted_before = {"clip": clip.baseline, "e5": e5.baseline}
        if persisted_after != persisted_before:
            raise RuntimeError("Persisted index fingerprint đổi sau smoke/reopen.")
        raw = b"".join(json_bytes(record) for record in output)
        modules = ("backend/app/search/experimental_text_search.py", "backend/app/search/vector_search.py",
                   "backend/app/search/text_search.py", "backend/app/search/rrf.py",
                   "backend/app/search/filters.py", "backend/app/search/e5_index.py",
                   "backend/app/search/smoke.py", "backend/app/embedding/e5_encoder.py",
                   "backend/app/embedding/clip_encoder.py", "scripts/smoke_e5_rrf_service.py")
        report = {
            "schema_version": "issue91-experimental-service-smoke-v1", "status": "passed",
            "scope": "synthetic queries and filter/repeat/index integrity diagnostics; not relevance or latency benchmark",
            "started_at_utc": started, "finished_at_utc": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(), "platform": platform.platform(), "device": "cpu",
            "model_load_seconds": load_seconds, "elapsed_seconds": perf_counter() - start,
            "torch_threads": torch.get_num_threads(), "torch_interop_threads": torch.get_num_interop_threads(),
            "rank_constant": args.rank_constant, "configuration_selected_by_validation": False,
            "command": ["scripts/smoke_e5_rrf_service.py", "--clip-index-root", args.clip_index_root.as_posix(),
                        "--clip-input-root", args.clip_input_root.as_posix(), "--e5-index-root", args.e5_index_root.as_posix(),
                        "--output", args.output.as_posix(), "--rank-constant", str(args.rank_constant)],
            "case_counts": {record["case"]: record["expected_filtered_count"] for record in output},
            "source_versions": [asdict(source) for source in results[0].sources],
            "persisted_before": persisted_before, "persisted_after_reopen": persisted_after,
            "persisted_fingerprints_unchanged": True, "ram_after_queries": ram_after,
            "all_query_ram_transitions_exactly_verified": True,
            "repeat_fusion_and_source_ranks_provenance_exact": True,
            "raw_cosine_repeat_tolerance": 1e-12, "raw_cosine_repeat_max_abs_delta": repeat_deltas,
            "e5_only_matches_fusion_source_ranks_provenance": True,
            "e5_only_raw_cosine_max_abs_delta": e5_only_delta,
            "raw_rankings_sha256": digest(raw),
            "code_commit": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
            "working_tree_dirty": bool(subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain"], text=True).strip()),
            "module_sha256": {name: digest((ROOT / name).read_bytes()) for name in modules},
            "package_versions": {name: version(name) for name in ("torch", "transformers", "qdrant-client", "numpy", "pydantic")},
        }
        args.output.mkdir(parents=True, exist_ok=False)
        for name, content in (("raw-rankings.jsonl", raw), ("report.json", json_bytes(report, pretty=True)),
            ("clip-index-manifest.json", (args.clip_index_root / "index-manifest.json").read_bytes()),
            ("e5-index-manifest.json", (args.e5_index_root / "index-manifest.json").read_bytes())):
            with (args.output / name).open("xb") as stream:
                stream.write(content)
    print(json.dumps({"status": "passed", "case_counts": report["case_counts"], "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
