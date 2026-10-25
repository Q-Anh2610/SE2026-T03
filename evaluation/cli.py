import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import load_config, resolve_repo_path
from .errors import EvaluationError
from .metrics.recall import recall_at_k
from .metrics.ranking import hit_at_k, ndcg_at_k
from .results import make_run, read_run, write_run
from .runner import load_queries, run_benchmark
from .search import HttpProductSearch


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m evaluation", description="Benchmark CLI cho product search.")
    commands = parser.add_subparsers(dest="command", required=True)

    benchmark = commands.add_parser("benchmark", help="Chạy queries qua Search API của sản phẩm.")
    benchmark.add_argument("--config", default="example.json", help="Tên config trong evaluation/configs/ hoặc đường dẫn JSON.")
    benchmark.add_argument("--output", help="File JSON kết quả; mặc định evaluation/results/<timestamp>.json.")

    metrics = commands.add_parser("metrics", help="Tính các metric xếp hạng từ kết quả benchmark.")
    metrics.add_argument("--input", required=True, help="File kết quả JSON.")
    metrics.add_argument(
        "--k",
        action="append",
        type=int,
        help="Cutoff k; có thể lặp lại (mặc định Recall/Hit @5 và @10, nDCG@10).",
    )
    metrics.add_argument("--output", help="Ghi report JSON ra file thay vì stdout.")

    writer = commands.add_parser("write-results", help="Chuẩn hóa/ghi một file kết quả JSON.")
    writer.add_argument("--input", required=True, help="File JSON chứa object kết quả.")
    writer.add_argument("--output", required=True, help="Đường dẫn file JSON đầu ra.")
    return parser


def _default_output() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(__file__).resolve().parent / "results" / f"benchmark-{stamp}.json"


def _benchmark(config_value: str, output_value: str | None) -> int:
    config, config_path = load_config(config_value)
    dataset = resolve_repo_path(config["dataset_path"])
    queries = load_queries(dataset)
    search = HttpProductSearch(config["search_api_url"], config["timeout_seconds"])
    benchmark = run_benchmark(config, queries, search)
    result = make_run(config, config_path, benchmark)
    output = Path(output_value).resolve() if output_value else _default_output()
    write_run(result, output)
    print(f"Đã ghi {len(benchmark['records'])} query vào {output}")
    return 0


def _metrics(input_value: str, k_values: list[int] | None, output_value: str | None) -> int:
    path = Path(input_value).resolve()
    run = read_run(path)
    records = run.get("records")
    if not isinstance(records, list):
        raise EvaluationError(f"File '{path}' không có mảng records hợp lệ.")
    cutoffs = k_values or [5, 10]
    reports = {
        **{f"recall@{k}": recall_at_k(records, k) for k in cutoffs},
        **{f"hit@{k}": hit_at_k(records, k) for k in cutoffs},
    }
    if 10 in cutoffs or k_values is None:
        reports["ndcg@10"] = ndcg_at_k(records, 10)
    elif len(cutoffs) == 1:
        reports[f"ndcg@{cutoffs[0]}"] = ndcg_at_k(records, cutoffs[0])

    if len(cutoffs) == 1:
        report = reports[f"recall@{cutoffs[0]}"]
        report["additional_metrics"] = {
            name: value for name, value in reports.items() if name != f"recall@{cutoffs[0]}"
        }
    else:
        report = {"name": "ranking_metrics", "cutoffs": cutoffs, "metrics": reports}
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if output_value:
        metrics_result = {"provenance": run.get("provenance", {}), "metrics": report}
        output = write_run(metrics_result, Path(output_value).resolve())
        print(f"Đã ghi report {report['name']} vào {output}")
    else:
        print(serialized)
    return 0


def _write_results(input_value: str, output_value: str) -> int:
    source = Path(input_value).resolve()
    payload = read_run(source)
    output = write_run(payload, Path(output_value).resolve())
    print(f"Đã ghi kết quả vào {output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "benchmark":
            return _benchmark(args.config, args.output)
        if args.command == "metrics":
            return _metrics(args.input, args.k, args.output)
        if args.command == "write-results":
            return _write_results(args.input, args.output)
    except EvaluationError as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # Keep unexpected adapter errors concise for CLI users.
        print(f"Lỗi không mong đợi khi chạy '{args.command}': {exc}", file=sys.stderr)
        return 1
    parser.error("Subcommand không được hỗ trợ.")
    return 2
