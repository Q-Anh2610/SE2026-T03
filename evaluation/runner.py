import json
from pathlib import Path
from typing import Any

from .errors import EvaluationError
from .search import ProductSearch


def load_queries(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise EvaluationError(f"Không tìm thấy dataset queries: '{path}'.")
    queries: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise EvaluationError(
                        f"Dataset '{path}' sai JSONL ở dòng {line_number}, cột {exc.colno}: {exc.msg}."
                    ) from exc
                if not isinstance(item, dict):
                    raise EvaluationError(f"Dataset '{path}' dòng {line_number} phải là object JSON.")
                query_id, query, relevant = (
                    item.get("query_id"), item.get("query"), item.get("relevant_asset_ids")
                )
                if not isinstance(query_id, str) or not query_id.strip():
                    raise EvaluationError(f"Dataset '{path}' dòng {line_number} thiếu query_id hợp lệ.")
                if not isinstance(query, str) or not query.strip():
                    raise EvaluationError(f"Dataset '{path}' dòng {line_number} thiếu query hợp lệ.")
                if not isinstance(relevant, list) or not all(isinstance(value, str) for value in relevant):
                    raise EvaluationError(
                        f"Dataset '{path}' dòng {line_number}: relevant_asset_ids phải là mảng string."
                    )
                queries.append({
                    "query_id": query_id,
                    "query": query,
                    "relevant_asset_ids": relevant,
                })
    except UnicodeDecodeError as exc:
        raise EvaluationError(f"Dataset '{path}' phải được mã hóa UTF-8.") from exc
    if not queries:
        raise EvaluationError(f"Dataset '{path}' không có query nào.")
    return queries


def run_benchmark(config: dict[str, Any], queries: list[dict[str, Any]], search: ProductSearch) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    versions: dict[str, str] = {}
    for item in queries:
        response = search.search(
            item["query"], filters=config["filters"], limit=config["limit"]
        )
        records.append({
            "query_id": item["query_id"],
            "query": item["query"],
            "relevant_asset_ids": item["relevant_asset_ids"],
            "retrieved_asset_ids": response.asset_ids,
        })
        versions.update(response.versions)
    return {"records": records, "search_versions": versions}
