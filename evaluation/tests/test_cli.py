import json
from pathlib import Path

import pytest

from evaluation.cli import main
from evaluation.config import load_config
from evaluation.errors import ConfigError
from evaluation.metrics.recall import recall_at_k
from evaluation.results import make_run, read_run, write_run
from evaluation.runner import load_queries, run_benchmark
from evaluation.search import ProductSearchResult


class StubSearch:
    """Fake product search for deterministic CLI/runner tests; not retrieval logic."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object], int]] = []

    def search(self, query: str, *, filters: dict[str, object], limit: int) -> ProductSearchResult:
        self.calls.append((query, filters, limit))
        return ProductSearchResult(["asset-b", "asset-a"], {"model_version": "stub-v1"})


def _valid_config(path: Path, dataset: Path) -> Path:
    config = {
        "version": 1,
        "dataset_path": str(dataset),
        "search_api_url": "http://127.0.0.1:8000/api/v1/search/text",
        "limit": 5,
        "filters": {"category": "chair"},
        "seed": 7,
        "timeout_seconds": 2,
    }
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_help_lists_required_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    output = capsys.readouterr().out
    assert "benchmark" in output
    assert "metrics" in output
    assert "write-results" in output


def test_config_error_is_actionable(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = tmp_path / "bad.json"
    config.write_text("{broken", encoding="utf-8")

    assert main(["benchmark", "--config", str(config)]) == 2
    captured = capsys.readouterr()
    assert "JSON" in captured.err
    assert "Traceback" not in captured.err


def test_load_config_rejects_wrong_field_type(tmp_path: Path) -> None:
    config = tmp_path / "bad.json"
    config.write_text(json.dumps({"version": "1"}), encoding="utf-8")
    with pytest.raises(ConfigError, match="Trường 'version'.*phải có kiểu int"):
        load_config(config)


def test_runner_calls_stub_search_and_preserves_rank_order(tmp_path: Path) -> None:
    dataset = tmp_path / "queries.jsonl"
    dataset.write_text(
        '{"query_id":"q1","query":"chair","relevant_asset_ids":["asset-a"]}\n',
        encoding="utf-8",
    )
    queries = load_queries(dataset)
    fake = StubSearch()
    config = {"filters": {"category": "chair"}, "limit": 5}

    run = run_benchmark(config, queries, fake)

    assert fake.calls == [("chair", {"category": "chair"}, 5)]
    assert run["records"][0]["retrieved_asset_ids"] == ["asset-b", "asset-a"]
    assert run["search_versions"] == {"model_version": "stub-v1"}


def test_benchmark_cli_uses_stub_search_and_writes_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dataset = tmp_path / "queries.jsonl"
    dataset.write_text(
        '{"query_id":"q1","query":"chair","relevant_asset_ids":["asset-a"]}\n',
        encoding="utf-8",
    )
    config = _valid_config(tmp_path / "config.json", dataset)
    output = tmp_path / "run.json"
    fake_search = StubSearch()

    monkeypatch.setattr(
        "evaluation.cli.HttpProductSearch",
        lambda _url, _timeout_seconds: fake_search,
    )

    assert main(["benchmark", "--config", str(config), "--output", str(output)]) == 0

    result = read_run(output)
    assert fake_search.calls == [("chair", {"category": "chair"}, 5)]
    assert result["records"][0]["retrieved_asset_ids"] == ["asset-b", "asset-a"]
    assert result["provenance"]["search_versions"] == {"model_version": "stub-v1"}
    assert "Đã ghi 1 query" in capsys.readouterr().out


def test_result_writer_round_trips_provenance(tmp_path: Path) -> None:
    config_path = _valid_config(tmp_path / "config.json", tmp_path / "queries.jsonl")
    config, _ = load_config(config_path)
    run = make_run(config, config_path, {"records": [], "search_versions": {"index_version": "idx-v1"}})
    output = write_run(run, tmp_path / "results" / "run.json")

    restored = read_run(output)
    assert restored["provenance"]["seed"] == 7
    assert restored["provenance"]["search_versions"] == {"index_version": "idx-v1"}
    assert "python_version" in restored["provenance"]
    assert "platform" in restored["provenance"]


def test_recall_at_k_has_known_answer() -> None:
    report = recall_at_k(
        [
            {"query_id": "q1", "relevant_asset_ids": ["a", "b"], "retrieved_asset_ids": ["b", "x"]},
            {"query_id": "q2", "relevant_asset_ids": ["c"], "retrieved_asset_ids": ["c"]},
        ],
        k=1,
    )
    assert report["per_query"][0]["recall"] == 0.5
    assert report["macro_average"] == 0.75


def test_metrics_cli_prints_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    result = tmp_path / "run.json"
    result.write_text(
        json.dumps({"records": [{"query_id": "q1", "relevant_asset_ids": ["a"], "retrieved_asset_ids": ["a"]}]}),
        encoding="utf-8",
    )
    assert main(["metrics", "--input", str(result), "--k", "1"]) == 0
    assert '"macro_average": 1.0' in capsys.readouterr().out


def test_write_results_cli_copies_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "source.json"
    output = tmp_path / "output" / "copy.json"
    payload = {"provenance": {"seed": 3}, "records": []}
    source.write_text(json.dumps(payload), encoding="utf-8")

    assert main(["write-results", "--input", str(source), "--output", str(output)]) == 0

    assert json.loads(output.read_text(encoding="utf-8")) == payload
    assert "Đã ghi kết quả" in capsys.readouterr().out
