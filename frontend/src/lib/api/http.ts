import { isHttpUrl } from '../../features/search/contract'

export const REQUEST_TIMEOUT_MS = 15000

export type ApiErrorKind = 'invalid' | 'not_found' | 'unavailable' | 'network' | 'contract' | 'config'

/** Error with a fixed Vietnamese message; never carries the server body text. */
export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status?: number
  readonly code?: string

  constructor(kind: ApiErrorKind, message: string, details: { status?: number; code?: string; cause?: unknown } = {}) {
    super(message, details.cause === undefined ? undefined : { cause: details.cause })
    this.name = 'ApiError'
    this.kind = kind
    this.status = details.status
    this.code = details.code
  }
}

/** Builds an API URL from an optional HTTP(S) origin, rejecting paths, credentials and queries. */
export function apiUrl(baseUrl: string, path: string): string {
  if (baseUrl) {
    if (!isHttpUrl(baseUrl)) throw new ApiError('config', 'Địa chỉ API không hợp lệ. Hãy kiểm tra cấu hình frontend.')
    const parsed = new URL(baseUrl)
    if (parsed.pathname !== '/' || parsed.search || parsed.hash) {
      throw new ApiError('config', 'Địa chỉ API phải là origin HTTP(S), không có đường dẫn hoặc tham số.')
    }
  }
  return `${baseUrl.replace(/\/$/, '')}${path}`
}

export interface ApiMessages {
  network: string
  invalid: string
  notFound: string
  routeNotFound: string
  unavailable: string
  contract: string
}

async function errorCode(response: Response): Promise<string | undefined> {
  try {
    const body: unknown = await response.json()
    const error = typeof body === 'object' && body !== null ? (body as { error?: unknown }).error : undefined
    const code = typeof error === 'object' && error !== null ? (error as { code?: unknown }).code : undefined
    return typeof code === 'string' ? code : undefined
  } catch {
    return undefined
  }
}

/**
 * GET JSON with caller cancellation plus a timeout. `notFoundCodes` lists backend
 * error codes meaning "resource missing" (vs. a missing route or disabled API).
 */
export async function getJson(url: string, signal: AbortSignal, messages: ApiMessages, notFoundCodes: string[] = []): Promise<unknown> {
  let response: Response
  try {
    response = await fetch(url, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal: AbortSignal.any([signal, AbortSignal.timeout(REQUEST_TIMEOUT_MS)]),
    })
  } catch (error) {
    if (signal.aborted) throw error
    throw new ApiError('network', messages.network, { cause: error })
  }
  if (!response.ok) {
    const code = await errorCode(response)
    if (response.status === 400 || response.status === 422) throw new ApiError('invalid', messages.invalid, { status: response.status, code })
    if (response.status === 404) {
      if (code && notFoundCodes.includes(code)) throw new ApiError('not_found', messages.notFound, { status: 404, code })
      throw new ApiError('unavailable', messages.routeNotFound, { status: 404, code })
    }
    throw new ApiError('unavailable', messages.unavailable, { status: response.status, code })
  }
  try {
    return await response.json()
  } catch (error) {
    throw new ApiError('contract', messages.contract, { cause: error })
  }
}
