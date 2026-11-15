import { apiUrl, REQUEST_TIMEOUT_MS } from '../../lib/api/http'
import type { AdminJobsRequestOptions } from './client'
import type { JobStatus } from './types'

export const REINDEX_PROFILE = 'clip-candidate200-v1'
export const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export interface ReindexResponse {
  job_id: string
  status: JobStatus
  status_url: string
  reused: boolean
}

const messages = {
  access_denied: 'Khóa quản trị thiếu hoặc không đúng.',
  unconfigured: 'Backend chưa cấu hình API quản trị.',
  unavailable: 'Reindex chưa được bật hoặc tài nguyên chưa sẵn sàng.',
  busy: 'Có lượt reindex khác đang chờ hoặc đang chạy. Hãy xem danh sách job.',
  invalid: 'Yêu cầu reindex không hợp lệ.',
  network: 'Chưa xác định API đã nhận yêu cầu hay chưa. Gửi lại cùng yêu cầu để kiểm tra, không tạo lượt mới.',
  contract: 'Phản hồi reindex không đúng định dạng. Gửi lại cùng yêu cầu để kiểm tra.',
  server: 'Chưa xác nhận được yêu cầu reindex. Có thể gửi lại cùng yêu cầu.',
  uuid: 'Không thể tạo mã yêu cầu. Hãy mở ứng dụng qua HTTPS hoặc localhost.',
}

export class ReindexError extends Error {
  constructor(readonly kind: keyof typeof messages) {
    super(messages[kind])
    this.name = 'ReindexError'
  }
}

export function parseReindexResponse(value: unknown, httpStatus: number): ReindexResponse {
  if (typeof value !== 'object' || value === null) throw new ReindexError('contract')
  const body = value as Record<string, unknown>
  if (
    typeof body.job_id !== 'string' || !UUID_PATTERN.test(body.job_id)
    || typeof body.status !== 'string' || !['queued', 'running', 'succeeded', 'failed'].includes(body.status)
    || body.status_url !== `/api/v1/admin/jobs/${body.job_id}`
    || !((httpStatus === 202 && body.reused === false && body.status === 'queued')
      || (httpStatus === 200 && body.reused === true))
  ) throw new ReindexError('contract')
  return body as unknown as ReindexResponse
}

export async function requestReindex(
  requestId: string,
  options: AdminJobsRequestOptions,
): Promise<ReindexResponse> {
  if (!options.adminKey.trim()) throw new ReindexError('access_denied')
  if (!UUID_PATTERN.test(requestId)) throw new ReindexError('invalid')
  const url = apiUrl(options.baseUrl ?? import.meta.env.VITE_API_BASE_URL ?? '', '/api/v1/admin/reindex')
  const signal = AbortSignal.any([options.signal, AbortSignal.timeout(REQUEST_TIMEOUT_MS)])
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        'X-Admin-Key': options.adminKey,
      },
      body: JSON.stringify({ request_id: requestId, profile: REINDEX_PROFILE }),
      signal,
      cache: 'no-store',
    })
    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null)
      const error = typeof body === 'object' && body !== null && 'error' in body ? body.error : null
      const code = typeof error === 'object' && error !== null && 'code' in error ? error.code : null
      if (response.status === 403) throw new ReindexError('access_denied')
      if (response.status === 400) throw new ReindexError('invalid')
      if (response.status === 409 && code === 'REINDEX_IN_PROGRESS') throw new ReindexError('busy')
      if (response.status === 503 && code === 'ADMIN_API_UNAVAILABLE') throw new ReindexError('unconfigured')
      if (response.status === 503 && code === 'REINDEX_UNAVAILABLE') throw new ReindexError('unavailable')
      throw new ReindexError('server')
    }
    let body: unknown
    try {
      body = await response.json()
    } catch (error) {
      if (signal.aborted) throw error
      throw new ReindexError('contract')
    }
    return parseReindexResponse(body, response.status)
  } catch (error) {
    if (options.signal.aborted) throw options.signal.reason
    if (error instanceof ReindexError) throw error
    throw new ReindexError('network')
  }
}
