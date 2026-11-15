import type { JobMetadata, JobStatus } from '../features/admin/types'

// Synthetic jobs only; these IDs and this key do not identify live data.
export const ADMIN_TEST_KEY = 'test-admin-key-104-not-a-real-secret'
export const REINDEX_JOB_ID = 'a0b674d2-1286-401f-b73b-72cae159fcad'
export const REINDEX_REQUEST_ID = 'b0b674d2-1286-401f-b73b-72cae159fcad'

export function reindexResponse(reused = false, status: JobStatus = 'queued') {
  return { job_id: REINDEX_JOB_ID, status, status_url: `/api/v1/admin/jobs/${REINDEX_JOB_ID}`, reused }
}

export function reindexJob(status: JobStatus = 'running'): JobMetadata {
  const terminal = status === 'succeeded' || status === 'failed'
  return {
    job_id: REINDEX_JOB_ID,
    kind: 'indexing',
    runner: 'reindex.clip_candidate200',
    status,
    created_at: '2026-11-15T08:00:00Z',
    updated_at: '2026-11-15T08:01:00Z',
    started_at: status === 'queued' ? null : '2026-11-15T08:00:01Z',
    finished_at: terminal ? '2026-11-15T08:01:00Z' : null,
    progress: { unit: 'assets', processed: terminal ? 200 : null, total: terminal ? 200 : null, percent: terminal ? 100 : null },
    result: status === 'succeeded' ? {
      persistence: null, input_count: 200, succeeded: 200, failed: 0, skipped: 0,
      manifest_sha256: 'a'.repeat(64), exit_code: 0,
      index_version: 'reindex-clip-fixture', model_version: 'clip@fixture-revision',
      dataset_snapshot: 'home-interior-clear-200-v3@fixture-hash',
      asset_count: 200, point_count: 200, index_ref: 'reindex-fixture',
      index_manifest_sha256: 'b'.repeat(64), search_verified: true,
    } : null,
    error: status === 'failed' ? { code: 'INDEXING_FAILED', message: 'Indexing thất bại trong fixture.' } : null,
  }
}
