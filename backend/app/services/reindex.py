"""Một worker local, durable job/idempotency/resource guard bằng PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import logging
from pathlib import Path
import subprocess
import sys

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.errors import api_error
from app.models import Job
from app.schemas.jobs import JobResult
from app.schemas.reindex import ReindexResponse
from app.services.job_runner import InvalidOutcome, Outcome, validate_outcome
from app.services.job_diagnostics import job_failure, safe_failure_code
from app.services.jobs import finish_job, start_job

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "data/manifests/objaverse_200.json"
SOURCE_HASH = "9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd"
SNAPSHOT = "home-interior-clear-200-v3"
RESOURCE = "clip-candidate200-v1"
MODEL = "openai/clip-vit-base-patch32@3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268"
logger = logging.getLogger(__name__)


class ReindexFailure(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__("Reindex chưa hoàn tất; kiểm tra artifact local.")


def validate_configuration(settings):
    if not settings.reindex_enabled or settings.reindex_cache_ready is None or not settings.reindex_cache_ready.is_file():
        raise api_error(503, "REINDEX_UNAVAILABLE", "Reindex chưa được cấu hình sẵn sàng.")
    if not SOURCE.is_file() or sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_HASH:
        raise api_error(503, "REINDEX_UNAVAILABLE", "Đầu vào reindex chưa sẵn sàng.")


def reserve_job(engine, request):
    # Serialize bước nhận request trên cùng profile qua mọi process. Không giữ
    # advisory transaction lock trong lúc embedding; partial unique index bảo vệ
    # tài nguyên cho toàn bộ vòng đời queued/running.
    with Session(engine) as session, session.begin():
        session.execute(text("SELECT pg_advisory_xact_lock(11720001)"))
        existing = session.scalar(select(Job).where(Job.request_id == request.request_id))
        if existing is not None:
            return response_for(existing, reused=True)
        active = session.scalar(select(Job).where(Job.resource_key == RESOURCE, Job.status.in_(["queued", "running"])))
        if active is not None:
            raise api_error(409, "REINDEX_IN_PROGRESS", "Đã có lượt reindex trên tài nguyên này. Theo dõi jobs/status.")
        job = Job(kind="indexing", runner="reindex.clip_candidate200", status="queued",
                  request_id=request.request_id, resource_key=RESOURCE)
        session.add(job)
        session.flush()
        return response_for(job, reused=False)


def response_for(job, *, reused):
    return ReindexResponse(job_id=job.job_id, status=job.status,
                          status_url=f"/api/v1/admin/jobs/{job.job_id}", reused=reused)


def run_index(settings, job_id):
    from contextlib import closing
    from qdrant_client import QdrantClient
    from app.search.index_manifest import load_index_manifest

    # Profile cố định; frontend không thể thay command, path, model hay snapshot.
    try:
        validate_configuration(settings)
        output = settings.reindex_output_root.resolve() / str(job_id)
    except Exception:
        raise ReindexFailure('REINDEX_INPUT_INVALID') from None
    version = "reindex-clip-" + job_id.hex
    command = [sys.executable, str(ROOT / "scripts/prepare_text_search_index.py"),
        "--manifest", str(SOURCE), "--snapshot", SNAPSHOT,
        "--cache-ready", str(settings.reindex_cache_ready.resolve()),
        "--output-dir", str(output), "--index-version", version, "--verify-search"]
    try:
        completed = subprocess.run(command, cwd=ROOT, check=False, timeout=settings.reindex_timeout_seconds,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        raise ReindexFailure("REINDEX_TIMEOUT") from None
    if completed.returncode != 0:
        raise ReindexFailure("INDEXING_FAILED")
    try:
        manifest = load_index_manifest(output / "index-manifest.json")
        manifest.verify_input_hashes(output)
        versions = manifest.execution_versions()
        config = manifest.as_index_config()
        if (manifest.source_manifest_sha256 != SOURCE_HASH or versions.model_version != MODEL
                or versions.index_version != version or manifest.asset_count != 200 or manifest.point_count != 200
                or versions.dataset_snapshot != SNAPSHOT + "-sha256:" + SOURCE_HASH
                or versions.config_version != "clip-text-exact-all-filtered-v1-k200"
                or config.dimension != 512 or config.preprocessing_version != "clip-slow-processor-rgb-l2-v1"):
            raise ValueError("Profile mismatch.")
        search_check = json.loads((output / "search-check.json").read_text(encoding="utf-8"))
        if (search_check["passed"] is not True or search_check["hit_count"] != 200
                or search_check["versions"] != versions.model_dump()):
            raise ValueError("Search check mismatch.")
        with closing(QdrantClient(path=str(output / "qdrant"))) as client:
            store = manifest.make_store(client)
            store.validate_collection()
            if client.count(manifest.collection, exact=True).count != 200:
                raise ValueError("Count mismatch.")
        manifest_hash = sha256((output / "index-manifest.json").read_bytes()).hexdigest()
    except Exception:
        raise ReindexFailure("REINDEX_OUTPUT_INVALID") from None
    return Outcome(result=JobResult(input_count=200, succeeded=200, failed=0, skipped=0,
        manifest_sha256=SOURCE_HASH, exit_code=0, index_version=version,
        model_version=versions.model_version, dataset_snapshot=versions.dataset_snapshot,
        asset_count=200, point_count=200, index_ref="reindex-" + job_id.hex,
        index_manifest_sha256=manifest_hash,
        search_verified=True), processed=200, total=200)


class ReindexManager:
    def __init__(self, engine, settings, operation=None):
        self.engine = engine
        self.settings = settings
        self.operation = operation or run_index
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="reindex")

    def submit(self, request):
        validate_configuration(self.settings)
        response = reserve_job(self.engine, request)
        if not response.reused:
            try:
                self.executor.submit(self.work, response.job_id)
            except RuntimeError:
                job_failure(logger, response.job_id, stage='scheduling', code='REINDEX_SCHEDULING_FAILED')
                try:
                    start_job(self.engine, response.job_id)
                except Exception:
                    job_failure(logger, response.job_id, stage='start_state', code='JOB_STATE_UNAVAILABLE',
                                operation_code='REINDEX_SCHEDULING_FAILED', intended_status='running')
                    raise
                try:
                    finish_job(self.engine, response.job_id, error={"code": "REINDEX_SCHEDULING_FAILED",
                               "message": "Không khởi chạy được worker reindex."})
                except Exception:
                    job_failure(logger, response.job_id, stage='failure_state', code='JOB_STATE_UNAVAILABLE',
                                operation_code='REINDEX_SCHEDULING_FAILED', intended_status='failed')
                    raise
                raise api_error(503, "REINDEX_UNAVAILABLE", "Worker reindex chưa sẵn sàng.") from None
        return response

    def work(self, job_id):
        try:
            start_job(self.engine, job_id)
        except Exception:
            job_failure(logger, job_id, stage='start_state', code='JOB_STATE_UNAVAILABLE', intended_status='running')
            return  # Không chạy nếu chưa commit running.
        try:
            outcome = validate_outcome(self.operation(self.settings, job_id))
        except Exception as exc:
            code = (safe_failure_code(exc.code) if isinstance(exc, ReindexFailure) else
                    'RUNNER_OUTPUT_INVALID' if isinstance(exc, InvalidOutcome) else 'RUNNER_FAILED')
            stage = {'REINDEX_TIMEOUT': 'runner_timeout', 'INDEXING_FAILED': 'runner_exit',
                     'REINDEX_OUTPUT_INVALID': 'artifact', 'REINDEX_INPUT_INVALID': 'input',
                     'RUNNER_OUTPUT_INVALID': 'runner_output'}.get(code, 'operation')
            job_failure(logger, job_id, stage=stage, code=code)
            try:
                finish_job(self.engine, job_id, error={"code": code,
                    "message": "Reindex chưa hoàn tất; kiểm tra artifact local."})
            except Exception:
                job_failure(logger, job_id, stage='failure_state', code='JOB_STATE_UNAVAILABLE',
                            operation_code=code, intended_status='failed')
            return
        if outcome.error:
            job_failure(logger, job_id, stage='operation', code=outcome.error.code)
        try:
            finish_job(self.engine, job_id, result=outcome.result.model_dump(mode="json"),
                       error=outcome.error.model_dump() if outcome.error else None,
                       processed=outcome.processed, total=outcome.total)
        except Exception:
            # Không đổi thành succeeded trong RAM nếu commit DB thất bại.
            job_failure(logger, job_id, stage='final_state', code='JOB_STATE_UNAVAILABLE',
                        operation_code=outcome.error.code if outcome.error else None,
                        intended_status='failed' if outcome.error else 'succeeded')

    def close(self):
        self.executor.shutdown(wait=True)
