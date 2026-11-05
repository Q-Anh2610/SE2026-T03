"""Run the locked W2 metadata keyword baseline without the W3 HTTP API."""

from __future__ import annotations

import csv
import hashlib
import json
from math import log2
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.search.keyword import KEYWORD_CONFIG_VERSION, KeywordBaseline
DEFAULT_CONFIG = ROOT / "evaluation/configs/home-interior-text-v2-keyword.json"
RESULTS_DIR = ROOT / "evaluation/results"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("version") != 1:
        raise ValueError("Unsupported or invalid baseline config.")
    return config


def validate_locked_inputs(config: dict[str, Any], paths: dict[str, Path]) -> dict[str, str]:
    manifest = paths["manifest"]
    text = manifest.read_text(encoding="utf-8")
    expected_version = config["benchmark_version"]
    if f"benchmark_version: {expected_version}" not in text:
        raise ValueError("Benchmark version in manifest does not match config.")
    expected_hashes: dict[str, str] = {}
    in_locked_hashes = False
    for line in text.splitlines():
        if line == "locked_files_sha256:":
            in_locked_hashes = True
            continue
        if in_locked_hashes:
            if not line.startswith("  "):
                break
            name, value = line.strip().split(":", 1)
            expected_hashes[name] = value.strip()
    actual = {
        "queries.csv": sha256(paths["queries"]),
        "qrels.csv": sha256(paths["qrels"]),
    }
    for name, digest in actual.items():
        if expected_hashes.get(name) != digest:
            raise ValueError(f"Locked file hash mismatch for {name}; refusing to run.")
    snapshot_hash = sha256(paths["candidates"])
    expected_snapshot = next(
        (line.split(":", 1)[1].strip() for line in text.splitlines()
         if line.startswith("snapshot_manifest_sha256:")),
        None,
    )
    if snapshot_hash != expected_snapshot:
        raise ValueError("Candidate snapshot hash mismatch; refusing to run.")
    actual["candidate_metadata"] = snapshot_hash
    return actual


def compute_metrics(records: list[dict[str, Any]], cutoffs: list[int]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for k in cutoffs:
        recall_rows = []
        hit_rows = []
        ndcg_rows = []
        for record in records:
            relevant = set(record["relevant_asset_ids"])
            retrieved = record["retrieved_asset_ids"][:k]
            hit_count = len(relevant.intersection(retrieved))
            hit_rows.append({"query_id": record["query_id"], "hit": int(hit_count > 0), "hits_at_k": hit_count})
            if relevant:
                recall_rows.append({
                    "query_id": record["query_id"],
                    "recall": hit_count / len(relevant),
                    "relevant_count": len(relevant),
                    "hits_at_k": hit_count,
                })
            dcg = sum(1 / log2(rank + 2) for rank, asset_id in enumerate(retrieved) if asset_id in relevant)
            ideal_dcg = sum(1 / log2(rank + 2) for rank in range(min(len(relevant), k)))
            ndcg_rows.append({"query_id": record["query_id"], "ndcg": dcg / ideal_dcg if ideal_dcg else 0.0})
        defined_ids = {row["query_id"] for row in recall_rows}
        undefined_ids = [record["query_id"] for record in records if record["query_id"] not in defined_ids]
        output[f"recall@{k}"] = {
            "name": "recall@k",
            "k": k,
            "macro_average": sum(row["recall"] for row in recall_rows) / len(recall_rows) if recall_rows else None,
            "defined_query_count": len(recall_rows),
            "undefined_query_ids_no_relevant_qrels": undefined_ids,
            "per_query": recall_rows,
        }
        output[f"hit@{k}"] = {
            "name": "hit@k",
            "k": k,
            "macro_average": sum(row["hit"] for row in hit_rows) / len(hit_rows),
            "per_query": hit_rows,
        }
        if k == 10:
            output["ndcg@10"] = {
                "name": "ndcg@k",
                "k": 10,
                "macro_average": sum(row["ndcg"] for row in ndcg_rows) / len(ndcg_rows),
                "zero_ideal_dcg_query_ids": undefined_ids,
                "per_query": ndcg_rows,
            }
    return output


def main() -> int:
    config_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_CONFIG
    config = load_config(config_path)
    paths = {
        key: (ROOT / config[value]).resolve()
        for key, value in {
            "manifest": "manifest_path",
            "queries": "queries_path",
            "qrels": "qrels_path",
            "candidates": "candidate_metadata_path",
        }.items()
    }
    input_hashes = validate_locked_inputs(config, paths)
    if KEYWORD_CONFIG_VERSION != config["search_config_version"]:
        raise ValueError("Keyword implementation version does not match the locked run config.")

    queries = read_csv(paths["queries"])
    qrels = read_csv(paths["qrels"])
    assets = json.loads(paths["candidates"].read_text(encoding="utf-8"))
    if not isinstance(assets, list):
        raise ValueError("Candidate metadata must be a JSON array.")
    asset_ids = [item.get("asset_id") for item in assets]
    if len(asset_ids) != 200 or len(set(asset_ids)) != 200:
        raise ValueError("Expected exactly 200 unique candidate assets.")
    query_ids = [row["query_id"] for row in queries]
    if len(query_ids) != 70 or len(set(query_ids)) != 70:
        raise ValueError("Expected exactly 70 unique benchmark queries.")
    if any(row.get("query_type") != "text" or row.get("language") != "en" for row in queries):
        raise ValueError("This config only supports English text queries.")

    query_splits = {row["query_id"]: row["split"] for row in queries}
    qrels_by_query: dict[str, list[dict[str, str]]] = {query_id: [] for query_id in query_ids}
    seen_pairs: set[tuple[str, str]] = set()
    for row in qrels:
        pair = (row["query_id"], row["asset_id"])
        if pair in seen_pairs or pair[0] not in qrels_by_query or pair[1] not in set(asset_ids):
            raise ValueError("Qrels contain duplicate or unknown query/asset IDs.")
        seen_pairs.add(pair)
        if row["relevance"] not in {"0", "1", "2"}:
            raise ValueError("Qrels contain an invalid relevance score.")
        qrels_by_query[pair[0]].append(row)
    if any(len(qrels_by_query[qid]) != 200 for qid in query_ids):
        raise ValueError("Every query must have exactly 200 adjudicated asset judgments.")

    search = KeywordBaseline(assets)
    ranked_records: list[dict[str, Any]] = []
    metric_records: list[dict[str, Any]] = []
    limit = int(config["top_k"])
    threshold = int(config["relevance_threshold"])
    for row in queries:
        result_rows = search.search(row["query_text"], limit=limit)
        retrieved = [item["asset"]["asset_id"] for item in result_rows]
        relevant = sorted(
            item["asset_id"] for item in qrels_by_query[row["query_id"]]
            if int(item["relevance"]) >= threshold
        )
        metric_records.append({
            "query_id": row["query_id"],
            "relevant_asset_ids": relevant,
            "retrieved_asset_ids": retrieved,
        })
        ranked_records.append({
            "query_id": row["query_id"],
            "query": row["query_text"],
            "query_group_id": row["query_group_id"],
            "split": row["split"],
            "relevant_asset_ids": relevant,
            "retrieved_asset_ids": retrieved,
            "ranked_results": [
                {"asset_id": item["asset"]["asset_id"], "rank": item["rank"], "score": item["score"]}
                for item in result_rows
            ],
        })

    split_metrics = {}
    for split in ("validation", "test"):
        subset = [record for record in metric_records if query_splits[record["query_id"]] == split]
        split_metrics[split] = {
            "query_count": len(subset),
            "metrics": compute_metrics(subset, config["metric_cutoffs"]),
        }
    all_metrics = compute_metrics(metric_records, config["metric_cutoffs"])

    try:
        git_revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        git_revision = None
    run = {
        "schema_version": 1,
        "benchmark_version": config["benchmark_version"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "provenance": {
            "git_revision": git_revision,
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
            "config_path": config_path.relative_to(ROOT).as_posix(),
            "config_sha256": sha256(config_path),
            "config": config,
            "input_sha256": input_hashes,
            "search_implementation": "backend.app.search.keyword.KeywordBaseline",
            "search_config_version": KEYWORD_CONFIG_VERSION,
            "relevance_threshold": threshold,
            "metric_interpretation": "binary; relevance >= threshold is positive",
            "filters": {},
            "w3_text_search_api_used": False,
            "test_set_used_for_configuration_changes": False,
        },
        "metrics": {
            "all": {"query_count": len(metric_records), "metrics": all_metrics},
            **split_metrics,
        },
        "records": ranked_records,
    }
    output = RESULTS_DIR / f"{config['benchmark_version']}-keyword-baseline.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": output.relative_to(ROOT).as_posix(),
        "input_sha256": input_hashes,
        "query_counts": {"all": len(queries), **{k: v["query_count"] for k, v in split_metrics.items()}},
        "metrics": {
            split: {
                name: round(metric["macro_average"], 6)
                for name, metric in data["metrics"].items()
            }
            for split, data in {"validation": split_metrics["validation"], "test": split_metrics["test"], "all": {"metrics": all_metrics}}.items()
        },
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
