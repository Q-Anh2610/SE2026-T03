import { AdminJobsError } from './errors'
import type {
  JobDetailResponse,
  JobListResponse,
  JobMetadata,
  JobsPagination,
} from './types'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isCount(value: unknown): value is number {
  return typeof value === 'number'
    && Number.isSafeInteger(value)
    && value >= 0
}

function isNullableCount(value: unknown): boolean {
  return value === null || isCount(value)
}

function isTimestamp(value: unknown): boolean {
  return typeof value === 'string'
    && /^\d{4}-\d{2}-\d{2}T/.test(value)
    && /(Z|[+-]\d{2}:\d{2})$/i.test(value)
    && Number.isFinite(Date.parse(value))
}

function isProgress(value: unknown): boolean {
  if (!isRecord(value)) return false

  return value.unit === 'assets'
    && isNullableCount(value.processed)
    && isNullableCount(value.total)
    && (
      value.percent === null
      || (
        typeof value.percent === 'number'
        && Number.isFinite(value.percent)
        && value.percent >= 0
        && value.percent <= 100
      )
    )
}

function isResult(value: unknown): boolean {
  if (value === null) return true
  if (!isRecord(value)) return false

  const counts = ['input_count', 'succeeded', 'failed', 'skipped']

  return (
    value.persistence === null
    || value.persistence === 'postgresql'
    || value.persistence === 'local_files_only'
  )
    && counts.every((key) => isNullableCount(value[key]))
    && (
      value.manifest_sha256 === null
      || typeof value.manifest_sha256 === 'string'
    )
    && (
      value.exit_code === null
      || (
        typeof value.exit_code === 'number'
        && Number.isSafeInteger(value.exit_code)
      )
    )
}

function isJobError(value: unknown): boolean {
  return value === null || (
    isRecord(value)
    && typeof value.code === 'string'
    && typeof value.message === 'string'
  )
}

function isJob(value: unknown): value is JobMetadata {
  if (!isRecord(value)) return false

  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

  return typeof value.job_id === 'string'
    && uuid.test(value.job_id)
    && (value.kind === 'ingestion' || value.kind === 'indexing')
    && (
      value.status === 'queued'
      || value.status === 'running'
      || value.status === 'succeeded'
      || value.status === 'failed'
    )
    && typeof value.runner === 'string'
    && isTimestamp(value.created_at)
    && isTimestamp(value.updated_at)
    && (value.started_at === null || isTimestamp(value.started_at))
    && (value.finished_at === null || isTimestamp(value.finished_at))
    && isProgress(value.progress)
    && isResult(value.result)
    && isJobError(value.error)
}

function isPagination(value: unknown): value is JobsPagination {
  if (!isRecord(value)) return false

  return isCount(value.page)
    && value.page >= 1
    && isCount(value.limit)
    && value.limit >= 1
    && value.limit <= 50
    && isCount(value.total)
    && isCount(value.pages)
    && value.pages === Math.ceil(value.total / value.limit)
    && typeof value.has_next === 'boolean'
    && value.has_next === (value.page < value.pages)
}

export function parseJobListResponse(value: unknown): JobListResponse {
  if (
    !isRecord(value)
    || value.mock !== false
    || !Array.isArray(value.items)
    || !value.items.every(isJob)
    || !isPagination(value.pagination)
  ) {
    throw new AdminJobsError('contract')
  }

  const { items, pagination } = value
  const remaining = Math.max(
    0,
    pagination.total - (pagination.page - 1) * pagination.limit,
  )
  const expectedCount = Math.min(pagination.limit, remaining)
  const uniqueIds = new Set(items.map((job) => job.job_id))

  if (items.length !== expectedCount || uniqueIds.size !== items.length) {
    throw new AdminJobsError('contract')
  }

  return { items, pagination, mock: false }
}

export function parseJobDetailResponse(value: unknown): JobDetailResponse {
  if (!isRecord(value) || value.mock !== false || !isJob(value.job)) {
    throw new AdminJobsError('contract')
  }

  return { job: value.job, mock: false }
}