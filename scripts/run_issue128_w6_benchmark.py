"""Run the held-out W6 benchmark with the reviewed Issue #114 artifact.

This runner uses the existing CLIP/E5 fusion and image search services. It
copies the local Qdrant stores to a temporary workspace because local cosine
search can normalize persisted vectors while serving a query.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import platform
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.embedding.clip_encoder import CLIPEncoder  # noqa: E402
from app.embedding.e5_encoder import E5Encoder  # noqa: E402
from app.schemas.text_search import TextSearchFilters  # noqa: E402
from app.search.experimental_text_search import (  # noqa: E402
    CLIPTextSource,
    E5MetadataSearchService,
    ExperimentalFusionService,
)
from app.search.frozen_retrieval_config import (  # noqa: E402
    FrozenConfigError,
    load_frozen_config,
)
from app.search.image_index_manifest import load_image_index_manifest  # noqa: E402
from app.search.image_search import ImageSearchService  # noqa: E402


EXPECTED_SHA256 = "1e1962058528e22b5235d989a3613b5077c02d479b8ac19e8dbc28fee0bd08d5"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _positive_qrels(path: Path, query_ids: set[str], threshold: int) -> dict[str, list[str]]:
    relevant: dict[str, set[str]] = {query_id: set() for query_id in query_ids}
    observed: set[str] = set()
    for row in _csv_rows(path):
        query_id = row.get("query_id", "")
        if query_id not in query_ids:
            continue
        try:
            grade = int(row["relevance"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"Qrels có relevance không hợp lệ cho {query_id}.") from error
        observed.add(query_id)
        if grade >= threshold:
            relevant[query_id].add(row["asset_id"])
    missing = query_ids - observed
    if missing:
        raise ValueError(f"Qrels không có dòng cho query: {', '.join(sorted(missing))}")
    return {query_id: sorted(asset_ids) for query_id, asset_ids in relevant.items()}


def _macro_metrics(records: list[dict[str, Any]], cutoffs: list[int], *,
                   include_hit: bool) -> dict[str, Any]:
    """Binary metrics; nDCG/Hit include all queries, Recall excludes no-positive."""
    result: dict[str, Any] = {"query_count": len(records)}
    positive = [record for record in records if record["relevant_asset_ids"]]
    result["positive_query_count"] = len(positive)
    result["no_positive_query_ids"] = [
        record["query_id"] for record in records if not record["relevant_asset_ids"]
    ]
    for k in cutoffs:
        ndcgs: list[float] = []
        recalls: list[float] = []
        hits: list[float] = []
        for record in records:
            relevant = set(record["relevant_asset_ids"])
            retrieved = record["retrieved_asset_ids"][:k]
            found = sum(asset_id in relevant for asset_id in retrieved)
            hits.append(float(found > 0))
            if relevant:
                dcg = sum(1 / math.log2(rank + 2) for rank, asset_id in enumerate(retrieved)
                          if asset_id in relevant)
                ideal = sum(1 / math.log2(rank + 2) for rank in range(min(k, len(relevant))))
                ndcgs.append(dcg / ideal if ideal else 0.0)
                recalls.append(found / len(relevant))
            else:
                ndcgs.append(0.0)
        result[f"ndcg@{k}"] = {
            "macro_average": statistics.fmean(ndcgs),
            "denominator": len(records),
        }
        result[f"recall@{k}"] = {
            "macro_average": statistics.fmean(recalls) if recalls else None,
            "denominator": len(recalls),
        }
        if include_hit:
            result[f"hit@{k}"] = {
                "macro_average": statistics.fmean(hits),
                "denominator": len(records),
            }
    return result


def _nearest_rank(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[index]


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_queries(service: Any, queries: list[dict[str, Any]], qrels: dict[str, list[str]],
                 *, kind: str, filters: dict[str, Any], candidate_limit: int) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    latencies: list[float] = []
    for query in queries:
        query_id = query["query_id"]
        started = time.perf_counter()
        try:
            if kind == "text":
                response = service.search_text(query["query_text"], filters,
                                               config=service._issue128_rrf_config)
                asset_ids = [hit.asset_id for hit in response.hits]
                versions = {
                    "config_version": response.config_version,
                    "retrieval_parameters": getattr(response, "parameters", {}),
                    "candidate_snapshot": response.candidate_snapshot,
                    "source_manifest_sha256": response.source_manifest_sha256,
                    "candidate_ids_sha256": response.candidate_ids_sha256,
                    "corpus_sha256": response.corpus_sha256,
                    "recipe_version": response.recipe_version,
                    "sources": [asdict(source) for source in response.sources],
                }
            else:
                image_path = (ROOT / query["query_image_path"]).resolve()
                if not image_path.is_relative_to(ROOT) or not image_path.is_file():
                    raise ValueError("query_image_missing_or_outside_repo")
                response = service.search_image(image_path.read_bytes(),
                    TextSearchFilters.model_validate(filters), candidate_limit=candidate_limit)
                asset_ids = [hit.asset_id for hit in response.hits]
                versions = response.versions.model_dump(mode="json")
            elapsed_ms = (time.perf_counter() - started) * 1000
            latencies.append(elapsed_ms)
            records.append({
                "query_id": query_id,
                "query_type": kind,
                "query_text": query.get("query_text") or None,
                "query_image_path": query.get("query_image_path") or None,
                "relevant_asset_ids": qrels[query_id],
                "retrieved_asset_ids": asset_ids,
                "latency_ms": elapsed_ms,
                "versions": versions,
                "status": "ok",
            })
        except Exception as error:  # preserve per-query evidence and continue the fixed split
            elapsed_ms = (time.perf_counter() - started) * 1000
            errors.append({"query_id": query_id, "error_type": type(error).__name__,
                           "error": str(error)[:1000]})
            records.append({
                "query_id": query_id,
                "query_type": kind,
                "query_text": query.get("query_text") or None,
                "query_image_path": query.get("query_image_path") or None,
                "relevant_asset_ids": qrels[query_id],
                "retrieved_asset_ids": [],
                "latency_ms": elapsed_ms,
                "versions": {},
                "status": "error",
                "error_type": type(error).__name__,
                "error": str(error)[:1000],
            })
    successful = [record for record in records if record["status"] == "ok"]
    latencies = [record["latency_ms"] for record in successful]
    return {
        "records": records,
        "errors": errors,
        "metrics": _macro_metrics(successful, [5, 10], include_hit=(kind == "text")) if successful else None,
        "metric_scope": "successful queries only; partial runs are not comparable to the full test split",
        "latency_ms": {
            "sample_count": len(latencies),
            "method": "nearest-rank",
            "p50": _nearest_rank(latencies, 0.50),
            "p95": _nearest_rank(latencies, 0.95),
            "samples": latencies,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--expected-sha256", default=EXPECTED_SHA256)
    parser.add_argument("--output", type=Path, required=True,
                        help="Thư mục kết quả mới; runner từ chối ghi đè.")
    parser.add_argument("--work-root", type=Path, required=True,
                        help="Thư mục tạm cho bản sao Qdrant, không dùng storage gốc để query.")
    parser.add_argument("--acknowledge-held-out-test", action="store_true",
                        help="Xác nhận chạy một lượt trên test set đã khóa.")
    args = parser.parse_args()
    if not args.acknowledge_held_out_test:
        parser.error("Cần --acknowledge-held-out-test để xác nhận chạy held-out test.")

    repo = args.repo.resolve()
    output = args.output if args.output.is_absolute() else repo / args.output
    work_root = args.work_root.resolve()
    if output.exists():
        parser.error(f"Output đã tồn tại, không ghi đè: {output}")
    if not output.resolve().is_relative_to(repo):
        parser.error("Output phải nằm trong repository để dễ kiểm soát kết quả.")

    clients = []
    try:
        config_path = repo / "evaluation/configs/issue114-w6-retrieval.frozen.json"
        frozen = load_frozen_config(config_path, expected_sha256=args.expected_sha256,
            repo_root=repo, verify_local_inputs=True)
        config_doc = json.loads(config_path.read_text(encoding="utf-8"))
        files = config_doc["files"]
        query_rows = _csv_rows(repo / files["queries"]["path"])
        text_queries = [row for row in query_rows if row["query_type"] == "text" and row["split"] == "test"]
        image_rows = _csv_rows(repo / files["image_queries"]["path"])
        image_queries = [row for row in image_rows if row["split"] == "test"]
        expected_text = config_doc["benchmark"]["excluded_test_queries"]
        expected_image = config_doc["benchmark"]["image_excluded_test_queries"]
        if len(text_queries) != expected_text or len(image_queries) != expected_image:
            raise ValueError("test_query_count_mismatch")
        threshold = config_doc["benchmark"]["positive_relevance_threshold"]
        text_qrels = _positive_qrels(repo / files["qrels"]["path"],
                                     {row["query_id"] for row in text_queries}, threshold)
        image_qrels = _positive_qrels(repo / files["image_qrels"]["path"],
                                      {row["query_id"] for row in image_queries}, threshold)
        clip_storage = frozen.clip_index_root / "qdrant"
        e5_storage = frozen.e5_index_root / "qdrant"
        original_hashes = {"clip": _tree_hashes(clip_storage), "e5": _tree_hashes(e5_storage)}
        args.work_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="issue128-", dir=work_root) as temporary:
            temporary_root = Path(temporary)
            clip_copy = temporary_root / "clip-qdrant"
            e5_copy = temporary_root / "e5-qdrant"
            shutil.copytree(clip_storage, clip_copy)
            shutil.copytree(e5_storage, e5_copy)

            from qdrant_client import QdrantClient
            clip_client = QdrantClient(path=str(clip_copy), force_disable_check_same_thread=True)
            e5_client = QdrantClient(path=str(e5_copy), force_disable_check_same_thread=True)
            clients.extend([clip_client, e5_client])
            clip_encoder = CLIPEncoder(device="cpu", local_files_only=True)
            e5_encoder = E5Encoder(device="cpu", local_files_only=True)
            clip_source = CLIPTextSource(clip_encoder, clip_client,
                frozen.clip_index_root, input_root=frozen.clip_input_root,
                manifest_ref="data/processed/issue89/clip-preflight-76d5d2c095b6/index-manifest.json")
            e5_source = E5MetadataSearchService(e5_encoder, e5_client, frozen.e5_index_root,
                manifest_ref="data/processed/issue91/e5-index-20261113-2/index-manifest.json")
            fusion = ExperimentalFusionService(clip_source, e5_source)
            fusion._issue128_rrf_config = frozen.rrf_config

            image_manifest = load_image_index_manifest(frozen.image_index_root / "index-manifest.json")
            image_manifest.verify_input_hashes(frozen.clip_input_root)
            image_store = image_manifest.make_store(clip_client)
            image_store.validate_collection()
            image_service = ImageSearchService(clip_encoder, image_store)

            started_at = datetime.now(timezone.utc).isoformat()
            text_result = _run_queries(fusion, text_queries, text_qrels, kind="text",
                filters=frozen.filters, candidate_limit=200)
            image_result = _run_queries(image_service, image_queries, image_qrels, kind="image",
                filters=frozen.filters, candidate_limit=frozen.image_candidate_limit)
            for client in clients:
                client.close()
            clients.clear()

            final_hashes = {"clip": _tree_hashes(clip_storage), "e5": _tree_hashes(e5_storage)}
            originals_unchanged = original_hashes == final_hashes
            raw = {
                "schema_version": 1,
                "status": "complete" if not text_result["errors"] and not image_result["errors"] else "partial",
                "started_at_utc": started_at,
                "finished_at_utc": datetime.now(timezone.utc).isoformat(),
                "config_version": frozen.config_version,
                "config_sha256": frozen.artifact_sha256,
                "command": "backend\\.venv\\Scripts\\python.exe -B scripts\\run_issue128_w6_benchmark.py "
                           "--repo . --expected-sha256 " + args.expected_sha256 +
                           " --output " + str(args.output) + " --work-root " + str(args.work_root) +
                           " --acknowledge-held-out-test",
                "input_hashes": {name: item["sha256"] for name, item in files.items()},
                "test_authorization_note": "Issue owner acknowledged via CLI flag; this runner does not verify GitHub approval.",
                "environment": {
                    "python": sys.version,
                    "platform": platform.platform(),
                    "machine": platform.machine(),
                    "packages": {name: importlib.metadata.version(name) for name in
                                 ("torch", "transformers", "qdrant-client", "numpy", "Pillow")},
                    "device": "cpu",
                    "network_downloads_enabled": False,
                },
                "protocol": {
                    "text_split": "test",
                    "image_split": "test",
                    "text_query_count": len(text_queries),
                    "image_query_count": len(image_queries),
                    "candidate_count": 200,
                    "filters": frozen.filters,
                    "warmup_queries": 0,
                    "repetitions_per_query": 1,
                    "latency_scope": "service-call wall time, including query encoding, audits, local Qdrant and fusion; image includes image read/decode",
                    "metrics": {"relevance": f"binary relevance >= {threshold}",
                                "ndcg_and_hit_denominator": "all successful queries",
                                "recall_denominator": "successful positive queries only",
                                "image_hit_at_k": "not applicable: image split is similarity, not same-ID"},
                },
                "storage": {
                    "queried_temporary_copies_only": True,
                    "original_storage_bytes_unchanged": originals_unchanged,
                    "original_clip_file_hashes_before": original_hashes["clip"],
                    "original_clip_file_hashes_after": final_hashes["clip"],
                    "original_e5_file_hashes_before": original_hashes["e5"],
                    "original_e5_file_hashes_after": final_hashes["e5"],
                },
                "text": text_result,
                "image": image_result,
            }
            output.mkdir(parents=True)
            _write_json(output / "raw-results.json", raw)
            report = {
                "schema_version": 1,
                "status": raw["status"],
                "config_version": frozen.config_version,
                "config_sha256": frozen.artifact_sha256,
                "started_at_utc": started_at,
                "finished_at_utc": raw["finished_at_utc"],
                "environment": raw["environment"],
                "protocol": raw["protocol"],
                "storage": {"queried_temporary_copies_only": True,
                            "original_storage_bytes_unchanged": originals_unchanged},
                "text": {"query_count": len(text_queries), "success_count": len(text_result["records"]) - len(text_result["errors"]),
                         "errors": text_result["errors"], "metrics": text_result["metrics"],
                         "latency_ms": {k: v for k, v in text_result["latency_ms"].items() if k != "samples"}},
                "image": {"query_count": len(image_queries), "success_count": len(image_result["records"]) - len(image_result["errors"]),
                          "errors": image_result["errors"], "metrics": image_result["metrics"],
                          "latency_ms": {k: v for k, v in image_result["latency_ms"].items() if k != "samples"}},
                "raw_results": "raw-results.json",
            }
            _write_json(output / "report.json", report)
        print(json.dumps({"status": raw["status"], "output": str(output),
                          "text_errors": len(text_result["errors"]),
                          "image_errors": len(image_result["errors"]),
                          "original_storage_bytes_unchanged": originals_unchanged}))
        return 0 if raw["status"] == "complete" and originals_unchanged else 1
    except (FrozenConfigError, OSError, ValueError, RuntimeError) as error:
        for client in clients:
            client.close()
        print(json.dumps({"status": "blocked", "error_type": type(error).__name__,
                          "reason": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
