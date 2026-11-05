from math import log2

from evaluation.run_keyword_baseline import compute_metrics


def test_compute_metrics_known_answers_with_queries_without_positive_qrels() -> None:
    records = [
        {
            "query_id": "q1",
            "relevant_asset_ids": ["a", "b"],
            "retrieved_asset_ids": ["x", "a"],
        },
        {
            "query_id": "q2",
            "relevant_asset_ids": [],
            "retrieved_asset_ids": ["x"],
        },
        {
            "query_id": "q3",
            "relevant_asset_ids": ["c"],
            "retrieved_asset_ids": ["c"],
        },
    ]

    report = compute_metrics(records, [5, 10])

    # Recall excludes q2 because it has no positive qrels; Hit and nDCG include it.
    assert report["recall@5"]["macro_average"] == 0.75
    assert report["recall@5"]["defined_query_count"] == 2
    assert report["recall@5"]["undefined_query_ids_no_relevant_qrels"] == ["q2"]
    assert report["hit@5"]["macro_average"] == 2 / 3
    assert report["hit@5"]["per_query"][1]["hit"] == 0

    q1_ndcg = (1 / log2(3)) / (1 + 1 / log2(3))
    assert report["ndcg@10"]["per_query"][0]["ndcg"] == q1_ndcg
    assert report["ndcg@10"]["per_query"][1]["ndcg"] == 0
    assert report["ndcg@10"]["per_query"][2]["ndcg"] == 1
    assert report["ndcg@10"]["macro_average"] == (q1_ndcg + 1) / 3
    assert report["ndcg@10"]["zero_ideal_dcg_query_ids"] == ["q2"]
