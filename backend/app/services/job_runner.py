"""Bọc runner hiện có bằng lịch sử PostgreSQL; không tạo hàng đợi/background worker."""

import argparse
from dataclasses import dataclass
import logging
from pathlib import Path
import subprocess
import sys
from typing import Callable
from uuid import UUID

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import create_db_engine
from app.schemas.jobs import JobError, JobResult
from app.services.jobs import create_job, finish_job, start_job
from app.services.job_diagnostics import job_failure, safe_failure_code

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Outcome:
    result: JobResult
    processed: int | None = None
    total: int | None = None
    error: JobError | None = None


class InvalidOutcome(ValueError):
    pass


def validate_outcome(outcome):
    """Không suy ra thành công từ dữ liệu thiếu/sai hoặc dấu hiệu thất bại."""
    try:
        if not isinstance(outcome, Outcome) or not isinstance(outcome.result, JobResult):
            raise ValueError('Invalid runner result.')
        result = JobResult.model_validate(outcome.result.model_dump())
        if outcome.error is not None and not isinstance(outcome.error, JobError):
            raise ValueError('Invalid runner error.')
        for count in (outcome.processed, outcome.total):
            if count is not None and (type(count) is not int or count < 0):
                raise ValueError('Invalid runner progress.')
        if (outcome.processed is not None and outcome.total is not None
                and outcome.processed > outcome.total):
            raise ValueError('Invalid runner progress.')
        if outcome.error is None and ((result.failed or 0) > 0
                or result.exit_code not in (None, 0) or result.search_verified is False):
            raise ValueError('Runner result contradicts success.')
        error = None if outcome.error is None else JobError(
            code=safe_failure_code(outcome.error.code),
            message='Runner chưa hoàn tất toàn bộ công việc; kiểm tra báo cáo local.')
        return Outcome(result, outcome.processed, outcome.total, error)
    except Exception:
        raise InvalidOutcome('Runner output invalid.') from None


def execute_job(engine: Engine, *, kind: str, runner: str,
                operation: Callable[[], Outcome]) -> tuple[UUID, bool]:
    try:
        job_id = create_job(engine, kind=kind, runner=runner)
    except Exception:
        job_failure(logger, None, stage='create_state', code='JOB_STATE_UNAVAILABLE', intended_status='queued')
        raise
    try:
        start_job(engine, job_id)
    except Exception:
        job_failure(logger, job_id, stage='start_state', code='JOB_STATE_UNAVAILABLE', intended_status='running')
        raise
    # Nếu DB không ghi được queued/running thì không thực thi operation.
    try:
        outcome = validate_outcome(operation())
    except (Exception, KeyboardInterrupt) as exc:
        code = 'RUNNER_OUTPUT_INVALID' if isinstance(exc, InvalidOutcome) else 'RUNNER_FAILED'
        job_failure(logger, job_id, stage='runner_output' if isinstance(exc, InvalidOutcome) else 'operation', code=code)
        try:
            finish_job(engine, job_id, error={"code": code,
                       "message": "Runner thất bại hoặc bị gián đoạn; kiểm tra báo cáo local."})
        except Exception:
            job_failure(logger, job_id, stage='failure_state', code='JOB_STATE_UNAVAILABLE',
                        operation_code=code, intended_status='failed')
            raise
        # Không lưu exception text, SQL, stdout/stderr hay filesystem paths.
        return job_id, False
    if outcome.error:
        job_failure(logger, job_id, stage='operation', code=outcome.error.code)
    try:
        finish_job(engine, job_id, result=outcome.result.model_dump(mode="json"),
                   processed=outcome.processed, total=outcome.total,
                   error=outcome.error.model_dump() if outcome.error else None)
    except Exception:
        job_failure(logger, job_id, stage='final_state', code='JOB_STATE_UNAVAILABLE',
                    operation_code=outcome.error.code if outcome.error else None,
                    intended_status='failed' if outcome.error else 'succeeded')
        raise
    return job_id, outcome.error is None


def ingestion_operation(*, manifest_path, output_dir, report_path, max_attempts=3,
                        limit=None, previous_report_path=None, persist_asset=None) -> Outcome:
    from app.ingestion.pipeline import run_batch

    # Không ghi đè report lần trước. Runner cũ không tự đăng ký jobs.
    if Path(report_path).exists():
        raise ValueError("Choose a new report path.")
    report = run_batch(manifest_path, output_dir, report_path, max_attempts=max_attempts,
                       limit=limit, previous_report_path=previous_report_path, persist_asset=persist_asset)
    summary = report["summary"]
    error = None if summary["failed"] == 0 else JobError(
        code="BATCH_PARTIAL_FAILURE", message="Có asset xử lý thất bại; kiểm tra báo cáo local.")
    return Outcome(result=JobResult(**summary, persistence=report["persistence"], manifest_sha256=report["manifest_sha256"]),
        processed=summary["succeeded"] + summary["failed"] + summary["skipped"],
        total=summary["input_count"], error=error)


def indexing_operation(*, manifest_path, snapshot: str) -> Outcome:
    # Chỉ runner CLIP standalone có sẵn, không nhận shell command từ HTTP/CLI.
    # Script tạo output UUID mới, không ghi đè index đang phục vụ API.
    root = Path(__file__).resolve().parents[3]
    completed = subprocess.run([
        sys.executable, str(root / "scripts/prepare_text_search_index.py"),
        "--manifest", str(Path(manifest_path).resolve()), "--snapshot", snapshot,
        "--download-previews",
    ], cwd=root, check=False)
    error = None if completed.returncode == 0 else JobError(
        code="INDEXING_FAILED", message="Runner tạo index thất bại; kiểm tra báo cáo local.")
    # Runner chưa có callback tiến độ chuẩn: không suy diễn số asset từ exit code.
    return Outcome(result=JobResult(exit_code=completed.returncode), error=error)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Chạy batch local và ghi jobs/status PostgreSQL.")
    commands = parser.add_subparsers(dest="kind", required=True)
    ingestion = commands.add_parser("ingestion")
    ingestion.add_argument("--manifest", type=Path, required=True)
    ingestion.add_argument("--output-dir", type=Path, required=True)
    ingestion.add_argument("--report", type=Path, required=True)
    ingestion.add_argument("--previous-report", type=Path)
    ingestion.add_argument("--limit", type=int)
    ingestion.add_argument("--max-attempts", type=int, default=3)
    ingestion.add_argument("--persist-db", action="store_true")
    indexing = commands.add_parser("indexing")
    indexing.add_argument("--manifest", type=Path, required=True)
    indexing.add_argument("--snapshot", required=True)
    indexing.add_argument("--download-previews", action="store_true", required=True,
                          help="Xác nhận tải preview; model phải có sẵn trong cache.")
    args = parser.parse_args(argv)
    engine = create_db_engine()
    try:
        if args.kind == "ingestion":
            options = dict(manifest_path=args.manifest, output_dir=args.output_dir, report_path=args.report,
                           limit=args.limit, max_attempts=args.max_attempts, previous_report_path=args.previous_report)
            def operation():
                if args.persist_db:
                    from app.ingestion.db_writer import DatabaseWriter
                    with DatabaseWriter() as writer:
                        return ingestion_operation(**options, persist_asset=writer)
                return ingestion_operation(**options)
            runner = "ingestion.run_batch"
        else:
            def operation():
                return indexing_operation(manifest_path=args.manifest, snapshot=args.snapshot)
            runner = "prepare_text_search_index"
        job_id, succeeded = execute_job(engine, kind=args.kind, runner=runner, operation=operation)
        print(f"job_id={job_id} status={'succeeded' if succeeded else 'failed'}")
        return 0 if succeeded else 1
    except (SQLAlchemyError, ValueError):
        print("Không ghi được trạng thái job; kiểm tra DB/migration. Không xác nhận job thành công.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
