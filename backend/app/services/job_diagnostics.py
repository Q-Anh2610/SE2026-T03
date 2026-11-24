"""Chẩn đoán job bằng allowlist; không nhận exception, command hay đường dẫn."""

from datetime import datetime, timezone
import json
from uuid import UUID

from app.core.request_logging import current_trace

FAILURE_CODES = frozenset({
    'RUNNER_FAILED', 'RUNNER_OUTPUT_INVALID', 'BATCH_PARTIAL_FAILURE',
    'INDEXING_FAILED', 'REINDEX_TIMEOUT', 'REINDEX_OUTPUT_INVALID',
    'REINDEX_INPUT_INVALID', 'REINDEX_SCHEDULING_FAILED',
})


def safe_failure_code(code):
    return code if isinstance(code, str) and code in FAILURE_CODES else 'RUNNER_FAILED'


def job_failure(logger, job_id, *, stage, code, operation_code=None, intended_status=None):
    trace = current_trace.get()
    logger.error(json.dumps({
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'level': 'ERROR', 'event': 'job.failure', 'component': logger.name,
        'job_id': str(job_id) if isinstance(job_id, UUID) else None,
        'request_id': trace.request_id if trace else None,
        'stage': stage, 'error_code': code,
        'operation_error_code': safe_failure_code(operation_code) if operation_code else None,
        'intended_status': intended_status,
    }, ensure_ascii=False, separators=(',', ':')))
