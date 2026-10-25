from evaluation.metrics.ranking import hit_at_k, ndcg_at_k
from evaluation.errors import EvaluationError
import pytest


def test_ranking_metrics_have_known_answers() -> None:
    records = [
        {"query_id": "q1", "relevant_asset_ids": ["a", "b"], "retrieved_asset_ids": ["x", "y", "a"]},
        {"query_id": "q2", "relevant_asset_ids": ["c"], "retrieved_asset_ids": ["c"]},
    ]
    assert hit_at_k(records, 2)["macro_average"] == 0.5
    assert ndcg_at_k(records, 2)["per_query"][1]["ndcg"] == 1.0


@pytest.mark.parametrize(
    "record",
    [
        {"query_id": "q1", "retrieved_asset_ids": ["a"]},
        {"query_id": "q1", "relevant_asset_ids": ["a"]},
        {"query_id": "q1", "relevant_asset_ids": [], "retrieved_asset_ids": ["a"]},
    ],
)
def test_ranking_metrics_reject_missing_or_invalid_records(record: dict[str, object]) -> None:
    with pytest.raises(EvaluationError):
        hit_at_k([record], 1)
import json
from pathlib import Path

from evaluation.cli import main


def test_metrics_cli_defaults_to_benchmark_cutoffs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = tmp_path / "run.json"
    result.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "query_id": "q1",
                        "relevant_asset_ids": ["a"],
                        "retrieved_asset_ids": ["a"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert main(["metrics", "--input", str(result)]) == 0
    output = capsys.readouterr().out
    assert '"recall@5"' in output
    assert '"recall@10"' in output
    assert '"ndcg@10"' in output
    assert '"hit@5"' in output
