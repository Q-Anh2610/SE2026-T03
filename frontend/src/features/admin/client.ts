import { apiUrl, REQUEST_TIMEOUT_MS } from '../../lib/api/http'
import {
  parseJobDetailResponse,
  parseJobListResponse,
} from './contract'
import { AdminJobsError } from './errors'
import type {
  JobDetailResponse,
  JobListQuery,
  JobListResponse,
} from './types'

export interface AdminJobsRequestOptions {
  adminKey: string
  signal: AbortSignal
  baseUrl?: string
}

function getErrorCode(value: unknown): string | undefined {
  if (typeof value !== 'object' || value === null) return undefined
  if (!('error' in value)) return undefined

  const error = value.error

  if (typeof error !== 'object' || error === null) return undefined
  if (!('code' in error)) return undefined

  return typeof error.code === 'string' ? error.code : undefined
}

async function getAdminJson(
  path: string,
  options: AdminJobsRequestOptions,
): Promise<unknown> {
  const { adminKey, signal } = options

  if (!adminKey.trim()) {
    throw new AdminJobsError('access_denied')
  }

  const baseUrl = options.baseUrl
    ?? import.meta.env.VITE_API_BASE_URL
    ?? ''
  const url = apiUrl(baseUrl, path)
  const requestSignal = AbortSignal.any([
    signal,
    AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  ])

  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        'X-Admin-Key': adminKey,
      },
      signal: requestSignal,
      cache: 'no-store',
    })

    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null)
      const code = getErrorCode(body)

      if (response.status === 403) {
        throw new AdminJobsError('access_denied', 403)
      }

      if (response.status === 400) {
        throw new AdminJobsError('invalid_request', 400)
      }

      if (response.status === 404 && code === 'JOB_NOT_FOUND') {
        throw new AdminJobsError('not_found', 404)
      }

      if (
        response.status === 503
        && code === 'ADMIN_API_UNAVAILABLE'
      ) {
        throw new AdminJobsError('unconfigured', 503)
      }

      throw new AdminJobsError('server', response.status)
    }

    try {
      const body: unknown = await response.json()
      return body
    } catch (error) {
      if (requestSignal.aborted) throw error
      throw new AdminJobsError('contract')
    }
  } catch (error) {
    if (signal.aborted) throw signal.reason
    if (error instanceof AdminJobsError) throw error

    throw new AdminJobsError('network')
  }
}

export async function listAdminJobs(
  query: JobListQuery,
  options: AdminJobsRequestOptions,
): Promise<JobListResponse> {
  const page = query.page ?? 1
  const limit = query.limit ?? 12

  if (
    !Number.isSafeInteger(page)
    || page < 1
    || !Number.isSafeInteger(limit)
    || limit < 1
    || limit > 50
  ) {
    throw new AdminJobsError('invalid_request')
  }

  const params = new URLSearchParams({
    page: String(page),
    limit: String(limit),
  })

  if (query.kind !== undefined) params.set('kind', query.kind)
  if (query.status !== undefined) params.set('status', query.status)

  const body = await getAdminJson(
    `/api/v1/admin/jobs?${params.toString()}`,
    options,
  )

  return parseJobListResponse(body)
}

export async function getAdminJob(
  jobId: string,
  options: AdminJobsRequestOptions,
): Promise<JobDetailResponse> {
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

  if (!uuid.test(jobId)) {
    throw new AdminJobsError('invalid_request')
  }

  const body = await getAdminJson(
    `/api/v1/admin/jobs/${encodeURIComponent(jobId)}`,
    options,
  )
  const result = parseJobDetailResponse(body)

  if (result.job.job_id.toLowerCase() !== jobId.toLowerCase()) {
    throw new AdminJobsError('contract')
  }

  return result
}