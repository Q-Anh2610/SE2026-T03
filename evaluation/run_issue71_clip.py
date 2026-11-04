"""Validate the Issue #71 CLIP handoff and compute locked benchmark metrics."""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "issue71"
RESULTS = ROOT / "evaluation/results/home-interior-clear-200-v3-clip-baseline.json"
EXPECTED_BENCHMARK_MANIFEST_SHA256 = (
    "2c2dcf7758376103117f7112f99ad310e94328897b5cbb26446428da10ecc6d4"
)
EXPECTED_SOURCE_MANIFEST_SHA256 = (
    "9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd"
)
EXPECTED_QUERIES_SHA256 = (
    "f62762c4a0b392ddc310d1d64e0bdb685b2010347e3790395bbb523428c38788"
)
EXPECTED_QRELS_SHA256 = (
    "cc1d42f6e3f41f92fab1b842c7a70ca68be4341cdd30e4262e13989f99019df5"
)
EXPECTED_HANDOFF_354_READY_SHA256 = (
    "7d0a3e59f4d1c697cb37fd8b82decea3ba3efa95d8c84235bda73b5afb67474c"
)
SNAPSHOT = "home-interior-clear-200-v3"
THRESHOLD = 1

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.run_keyword_baseline import compute_metrics, read_csv  # noqa: E402


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def compare_ids(expected: set[str], actual: set[str], label: str) -> None:
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    require(not missing and not unexpected, f"{label} mismatch: missing={missing[:5]}, unexpected={unexpected[:5]}")


def main() -> int:
    manifest_path = ROOT / "data/benchmark/manifest.yaml"
    queries_path = ROOT / "data/benchmark/queries.csv"
    qrels_path = ROOT / "data/benchmark/qrels.csv"
    candidates_path = ROOT / "data/benchmark/candidate_assets.csv"
    source_manifest_path = ROOT / "data/manifests/objaverse_200.json"
    preview_provenance_path = ROOT / "data/manifests/objaverse_200.provenance.json"
    ranked_path = HANDOFF / "ranked-results.csv"
    provenance_path = HANDOFF / "provenance.json"
    index_path = HANDOFF / "index-manifest.json"

    for path in (ranked_path, provenance_path, index_path):
        require(path.is_file(), f"Missing handoff file: {path.relative_to(ROOT)}")

    manifest_bytes = manifest_path.read_bytes()
    normalized_manifest = manifest_bytes.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    manifest_hash = sha256_bytes(normalized_manifest)
    require(
        manifest_hash == EXPECTED_BENCHMARK_MANIFEST_SHA256,
        "Benchmark manifest hash differs after the agreed LF-to-CRLF normalization.",
    )

    queries_hash = sha256_file(queries_path)
    qrels_hash = sha256_file(qrels_path)
    source_hash = sha256_file(source_manifest_path)
    preview_provenance_hash = sha256_file(preview_provenance_path)
    candidates_hash = sha256_file(candidates_path)
    ranked_hash = sha256_file(ranked_path)
    index_hash = sha256_file(index_path)
    require(queries_hash == EXPECTED_QUERIES_SHA256, "Locked query hash mismatch.")
    require(qrels_hash == EXPECTED_QRELS_SHA256, "Locked qrels hash mismatch.")
    require(source_hash == EXPECTED_SOURCE_MANIFEST_SHA256, "Snapshot source manifest hash mismatch.")

    provenance: dict[str, Any] = json.loads(provenance_path.read_text(encoding="utf-8"))
    index_manifest: dict[str, Any] = json.loads(index_path.read_text(encoding="utf-8"))
    inputs = provenance["inputs"]
    execution = provenance["execution_versions"]
    require(inputs["benchmark_manifest_sha256"] == manifest_hash, "Benchmark manifest provenance mismatch.")
    require(inputs["queries_sha256"] == queries_hash, "Query provenance mismatch.")
    require(inputs["locked_revision"].endswith(f"qrels.csv={qrels_hash}"), "Locked revision qrels hash mismatch.")
    require(inputs["snapshot"] == SNAPSHOT, "Wrong dataset snapshot in provenance.")
    require(inputs["source_manifest_sha256"] == source_hash, "Source manifest provenance mismatch.")
    require(inputs["preview_provenance_sha256"] == preview_provenance_hash, "Preview provenance mismatch.")
    require(inputs["candidate_assets_worktree_sha256"] == candidates_hash, "Candidate CSV provenance mismatch.")
    require(provenance["ranked_results_sha256"] == ranked_hash, "Ranked results hash mismatch.")
    require(provenance["index_manifest_sha256"] == index_hash, "Index manifest hash mismatch.")
    require(index_manifest["source_manifest_sha256"] == source_hash, "Index source manifest hash mismatch.")
    require(index_manifest["index_config"]["dataset_snapshot"].startswith(f"{SNAPSHOT}-sha256:{source_hash}"), "Index snapshot mismatch.")
    require(index_manifest["asset_count"] == 200 and index_manifest["point_count"] == 200, "Index does not contain 200 assets.")
    require(index_manifest["ready_manifest_sha256"] == sha256_file(HANDOFF / "objaverse_200.ready.json"), "Index ready-manifest checksum mismatch.")
    require(execution["dataset_snapshot"].startswith(f"{SNAPSHOT}-sha256:{source_hash}"), "Execution snapshot mismatch.")
    require(execution["model_version"] == f"{index_manifest['index_config']['model_id']}@{index_manifest['index_config']['model_revision']}", "Model provenance mismatch.")
    encoder_path = ROOT / "backend/app/embedding/clip_encoder.py"
    require(index_manifest["module_sha256"]["backend/app/embedding/clip_encoder.py"] == sha256_file(encoder_path), "CLIP encoder source hash mismatch.")
    require(index_manifest["retrieval_config"]["candidate_limit"] == 10, "Index config is not top 10.")
    require(provenance["top_k"] == 10, "Run provenance is not top 10.")
    require(provenance["incomplete_queries"] == [], "Handoff lists incomplete queries.")
    require(provenance["embedding"]["failed"] == 0 and provenance["embedding"]["skipped"] == 0, "Index reported embedding failures/skips.")
    require(
        inputs["handoff_ready_manifest_sha256"] == EXPECTED_HANDOFF_354_READY_SHA256,
        "Source 354-asset ready-manifest checksum differs from Chi's clarification.",
    )

    queries = read_csv(queries_path)
    qrels = read_csv(qrels_path)
    candidates = read_csv(candidates_path)
    source_assets = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    attached_assets = json.loads((HANDOFF / "objaverse_200.json").read_text(encoding="utf-8"))
    attached_ready = json.loads((HANDOFF / "objaverse_200.ready.json").read_text(encoding="utf-8"))
    require(len(queries) == 70 and len({row["query_id"] for row in queries}) == 70, "Locked query file is not 70 unique queries.")
    query_by_id = {row["query_id"]: row for row in queries}
    candidate_ids = {row["asset_id"] for row in candidates}
    source_ids = {row["asset_id"] for row in source_assets}
    compare_ids(candidate_ids, source_ids, "Candidate/source asset IDs")
    compare_ids(candidate_ids, {row["asset_id"] for row in attached_assets}, "Attached source asset IDs")
    compare_ids(candidate_ids, {row["metadata"]["asset_id"] for row in attached_ready}, "Attached ready asset IDs")
    require(len(candidate_ids) == 200, "Locked candidate set is not 200 assets.")

    ranked = read_csv(ranked_path)
    require(len(ranked) == 700, f"Expected 700 ranked rows, got {len(ranked)}.")
    compare_ids(set(query_by_id), {row["query_id"] for row in ranked}, "Ranked query IDs")
    ranked_by_query: dict[str, list[dict[str, str]]] = {query_id: [] for query_id in query_by_id}
    for row in ranked:
        require(row["asset_id"] in candidate_ids, f"Unknown asset ID in ranked results: {row['asset_id']}")
        ranked_by_query[row["query_id"]].append(row)
    for query_id, rows in ranked_by_query.items():
        rows.sort(key=lambda row: int(row["rank"]))
        require([int(row["rank"]) for row in rows] == list(range(1, 11)), f"Ranks are not 1..10 for {query_id}.")
        require(len({row["asset_id"] for row in rows}) == 10, f"Duplicate asset in top 10 for {query_id}.")
        for previous, current in zip(rows, rows[1:]):
            previous_score, current_score = float(previous["score"]), float(current["score"])
            require(previous_score >= current_score, f"Scores are out of order for {query_id}.")
            if previous_score == current_score:
                require(previous["asset_id"] <= current["asset_id"], f"Tie ordering is invalid for {query_id}.")

    query_status = {row["query_id"]: row for row in provenance["query_status"]}
    require(len(provenance["query_status"]) == 70, "Provenance query-status list is not 70 rows.")
    compare_ids(set(query_by_id), set(query_status), "Provenance query-status IDs")
    for query_id, query in query_by_id.items():
        status = query_status[query_id]
        require(status["status"] == "complete" and status["result_count"] == 10, f"Incomplete run status for {query_id}.")
        require(status["split"] == query["split"], f"Split mismatch for {query_id}.")
    split_counts = {split: sum(row["split"] == split for row in queries) for split in ("validation", "test")}
    require(split_counts == {"validation": 28, "test": 42}, "Locked split is not 28 validation / 42 test.")

    relevant_by_query: dict[str, list[str]] = {query_id: [] for query_id in query_by_id}
    seen_pairs: set[tuple[str, str]] = set()
    for row in qrels:
        pair = (row["query_id"], row["asset_id"])
        require(pair[0] in query_by_id and pair[1] in candidate_ids, f"Unknown qrels pair: {pair}.")
        require(pair not in seen_pairs, f"Duplicate qrels pair: {pair}.")
        seen_pairs.add(pair)
        require(row["relevance"] in {"0", "1", "2"}, f"Invalid qrels value for {pair}.")
        require(row["adjudication_status"] == "Adjudicated", f"Unadjudicated qrels pair: {pair}.")
        if int(row["relevance"]) >= THRESHOLD:
            relevant_by_query[pair[0]].append(pair[1])
    require(len(qrels) == 14_000, f"Expected 14,000 locked qrels, got {len(qrels)}.")

    records: list[dict[str, Any]] = []
    for query in queries:
        query_id = query["query_id"]
        rows = ranked_by_query[query_id]
        records.append({
            "query_id": query_id,
            "query": query["query_text"],
            "query_group_id": query["query_group_id"],
            "split": query["split"],
            "relevant_asset_ids": sorted(relevant_by_query[query_id]),
            "retrieved_asset_ids": [row["asset_id"] for row in rows],
            "ranked_results": [
                {"asset_id": row["asset_id"], "rank": int(row["rank"]), "score": float(row["score"])}
                for row in rows
            ],
        })

    keyword_run_path = ROOT / "evaluation/results/home-interior-text-v2-keyword-baseline.json"
    keyword_run = json.loads(keyword_run_path.read_text(encoding="utf-8"))
    keyword_hash = sha256_file(keyword_run_path)
    require(keyword_run["provenance"]["input_sha256"]["queries.csv"] == queries_hash, "Keyword baseline used different queries.")
    require(keyword_run["provenance"]["input_sha256"]["qrels.csv"] == qrels_hash, "Keyword baseline used different qrels.")
    require(keyword_run["provenance"]["input_sha256"]["candidate_metadata"] == source_hash, "Keyword baseline used a different candidate snapshot.")

    split_metrics: dict[str, Any] = {}
    for split in ("validation", "test"):
        subset = [record for record in records if record["split"] == split]
        split_metrics[split] = {"query_count": len(subset), "metrics": compute_metrics(subset, [5, 10])}
    all_metrics = compute_metrics(records, [5, 10])

    try:
        git_revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        git_revision = None
    output: dict[str, Any] = {
        "schema_version": 1,
        "benchmark_version": "home-interior-text-v2",
        "run_id": "issue-71-clip-home-interior-clear-200-v3",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "provenance": {
            "git_revision": git_revision,
            "metric_implementation": "evaluation.run_keyword_baseline.compute_metrics",
            "metric_implementation_sha256": sha256_file(ROOT / "evaluation/run_keyword_baseline.py"),
            "metric_runner_sha256": sha256_file(Path(__file__).resolve()),
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
            "input_sha256": {
                "queries.csv": queries_hash,
                "qrels.csv": qrels_hash,
                "candidate_metadata": source_hash,
                "preview_provenance": preview_provenance_hash,
                "candidate_assets.csv": candidates_hash,
                "ranked-results.csv": ranked_hash,
                "index-manifest.json": index_hash,
                "provenance.json": sha256_file(provenance_path),
                "keyword_baseline.json": keyword_hash,
            },
            "benchmark_manifest_sha256_crlf_normalized": manifest_hash,
            "benchmark_manifest_sha256_local_bytes": sha256_bytes(manifest_bytes),
            "snapshot": SNAPSHOT,
            "model_version": execution["model_version"],
            "index_version": execution["index_version"],
            "config_version": execution["config_version"],
            "filters": provenance["filters"],
            "top_k": 10,
            "query_count": len(queries),
            "split_counts": split_counts,
            "split_version": inputs["split_version"],
            "split_seed": inputs["split_seed"],
            "relevance_threshold": THRESHOLD,
            "metric_interpretation": "binary; relevance >= 1 is positive; macro Recall excludes queries with no positive qrels",
            "test_set_used_for_configuration_changes": False,
            "handoff_ready_manifest_note": (
                "Chi confirmed in Issue #71 that the provenance hash 7d0a3e... refers to the source "
                "home-interior-354-v1 ready manifest; the bundled index ready manifest 85aefb... "
                "refers to the selected 200-asset set."
            ),
        },
        "metrics": {
            "all": {"query_count": len(records), "metrics": all_metrics},
            **split_metrics,
        },
        "comparison_to_keyword": {
            split: {
                metric: {
                    "clip": split_metrics[split]["metrics"][metric]["macro_average"],
                    "keyword": keyword_run["metrics"][split]["metrics"][metric]["macro_average"],
                    "delta_clip_minus_keyword": (
                        split_metrics[split]["metrics"][metric]["macro_average"]
                        - keyword_run["metrics"][split]["metrics"][metric]["macro_average"]
                    ),
                }
                for metric in ("recall@5", "hit@5", "recall@10", "hit@10", "ndcg@10")
            }
            for split in ("validation", "test")
        },
        "records": records,
    }
    RESULTS.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": RESULTS.relative_to(ROOT).as_posix(),
        "validated_query_count": len(queries),
        "validated_ranked_row_count": len(ranked),
        "split_counts": split_counts,
        "metrics": {
            split: {name: round(value["macro_average"], 6) for name, value in data["metrics"].items()}
            for split, data in {"validation": split_metrics["validation"], "test": split_metrics["test"]}.items()
        },
        "comparison_to_keyword": output["comparison_to_keyword"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
