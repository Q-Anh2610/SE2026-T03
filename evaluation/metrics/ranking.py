"""Ranking metrics for benchmark records."""

from math import log2
from typing import Any

from ..errors import EvaluationError


def _validated_records(records: list[dict[str, Any]], k: int) -> list[tuple[str, set[str], list[str]]]:
    if k < 1:
        raise EvaluationError("Tham số k phải là số nguyên dương.")
    if not records:
        raise EvaluationError("Không có benchmark record để tính metric.")

    validated: list[tuple[str, set[str], list[str]]] = []
    for index, record in enumerate(records, start=1):
        relevant = record.get("relevant_asset_ids")
        retrieved = record.get("retrieved_asset_ids")
        if not isinstance(relevant, list) or not all(isinstance(value, str) for value in relevant):
            raise EvaluationError(f"Record {index} thiếu relevant_asset_ids dạng mảng string.")
        if not relevant:
            raise EvaluationError(f"Record {index} không có nhãn liên quan; không thể tính metric.")
        if not isinstance(retrieved, list) or not all(isinstance(value, str) for value in retrieved):
            raise EvaluationError(f"Record {index} thiếu retrieved_asset_ids dạng mảng string.")
        validated.append((str(record.get("query_id", index)), set(relevant), retrieved))
    return validated


def _report(name: str, values: list[dict[str, Any]], k: int, value_key: str) -> dict[str, Any]:
    return {
        "name": name,
        "k": k,
        "macro_average": sum(item[value_key] for item in values) / len(values),
        "per_query": values,
    }


def hit_at_k(records: list[dict[str, Any]], k: int) -> dict[str, Any]:
    """Compute macro Hit@k; a query is a hit when any relevant asset is retrieved."""
    values = []
    for query_id, relevant, retrieved in _validated_records(records, k):
        hit = int(bool(relevant.intersection(retrieved[:k])))
        values.append({"query_id": query_id, "hit": hit, "hits_at_k": hit})
    return _report("hit@k", values, k, "hit")


def ndcg_at_k(records: list[dict[str, Any]], k: int) -> dict[str, Any]:
    """Compute macro binary nDCG@k for ranked asset IDs."""
    values = []
    for query_id, relevant, retrieved in _validated_records(records, k):
        dcg = sum(
            1 / log2(rank + 2)
            for rank, asset_id in enumerate(retrieved[:k])
            if asset_id in relevant
        )
        ideal_dcg = sum(1 / log2(rank + 2) for rank in range(min(len(relevant), k)))
        score = dcg / ideal_dcg if ideal_dcg else 0.0
        values.append({"query_id": query_id, "ndcg": score})
    return _report("ndcg@k", values, k, "ndcg")
