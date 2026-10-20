from typing import Any

from ..errors import EvaluationError


def recall_at_k(records: list[dict[str, Any]], k: int) -> dict[str, Any]:
    """Compute macro Recall@k for records with ranked and relevant asset IDs."""
    if k < 1:
        raise EvaluationError("Tham số k phải là số nguyên dương.")
    if not records:
        raise EvaluationError("Không có benchmark record để tính Recall@k.")

    per_query: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        relevant = record.get("relevant_asset_ids")
        retrieved = record.get("retrieved_asset_ids")
        if not isinstance(relevant, list) or not all(isinstance(value, str) for value in relevant):
            raise EvaluationError(f"Record {index} thiếu relevant_asset_ids dạng mảng string.")
        if not relevant:
            raise EvaluationError(f"Record {index} không có nhãn liên quan; không thể tính Recall@k.")
        if not isinstance(retrieved, list) or not all(isinstance(value, str) for value in retrieved):
            raise EvaluationError(f"Record {index} thiếu retrieved_asset_ids dạng mảng string.")
        hits = len(set(relevant).intersection(retrieved[:k]))
        per_query.append({
            "query_id": record.get("query_id", str(index)),
            "recall": hits / len(set(relevant)),
            "relevant_count": len(set(relevant)),
            "hits_at_k": hits,
        })

    return {
        "name": "recall@k",
        "k": k,
        "macro_average": sum(item["recall"] for item in per_query) / len(per_query),
        "per_query": per_query,
    }
