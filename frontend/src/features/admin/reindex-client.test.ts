import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ADMIN_TEST_KEY, REINDEX_REQUEST_ID, reindexResponse } from '../../test/admin-reindex'
import { parseReindexResponse, requestReindex } from './reindex-client'

const fetchMock = vi.fn<typeof fetch>()
const options = () => ({ adminKey: ADMIN_TEST_KEY, signal: new AbortController().signal, baseUrl: 'http://localhost:8000' })
beforeEach(() => { fetchMock.mockReset(); vi.stubGlobal('fetch', fetchMock) })
afterEach(() => { vi.restoreAllMocks() })

describe('reindex HTTP contract', () => {
  it.each([202, 200])('gửi đúng POST và nhận HTTP %i', async status => {
    const body = reindexResponse(status === 200)
    fetchMock.mockResolvedValueOnce(Response.json(body, { status }))
    await expect(requestReindex(REINDEX_REQUEST_ID, options())).resolves.toEqual(body)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://localhost:8000/api/v1/admin/reindex')
    expect(init).toMatchObject({ method: 'POST', cache: 'no-store', headers: { 'X-Admin-Key': ADMIN_TEST_KEY, 'Content-Type': 'application/json' } })
    expect(JSON.parse(String(init?.body))).toEqual({ request_id: REINDEX_REQUEST_ID, profile: 'clip-candidate200-v1' })
    expect(String(url)).not.toContain(ADMIN_TEST_KEY)
  })

  it.each(['queued', 'running', 'succeeded', 'failed'] as const)('replay giữ job %s', status => {
    expect(parseReindexResponse(reindexResponse(true, status), 200).status).toBe(status)
  })

  it.each([
    null, {}, [], { ...reindexResponse(), job_id: 'wrong' },
    { ...reindexResponse(), status: 'other' }, { ...reindexResponse(), status: ['queued'] },
    { ...reindexResponse(), status_url: 'https://untrusted.invalid/job' },
    { ...reindexResponse(), status_url: '/api/v1/admin/jobs/wrong' },
    { ...reindexResponse(), reused: true }, { ...reindexResponse(), status: 'succeeded' },
  ])('từ chối body sai: %j', body => {
    expect(() => parseReindexResponse(body, 202)).toThrow()
  })
  it.each([200, 201, 204])('không chấp nhận response mới với HTTP %i', status => {
    expect(() => parseReindexResponse(reindexResponse(), status)).toThrow()
  })

  it.each([
    [400, 'INVALID_REQUEST', 'invalid'], [403, 'ADMIN_ACCESS_DENIED', 'access_denied'],
    [409, 'REINDEX_IN_PROGRESS', 'busy'], [503, 'ADMIN_API_UNAVAILABLE', 'unconfigured'],
    [503, 'REINDEX_UNAVAILABLE', 'unavailable'], [500, 'INTERNAL_ERROR', 'server'],
    [503, 'UNKNOWN', 'server'], [409, 'UNKNOWN', 'server'],
  ])('ánh xạ lỗi %i/%s', async (status, code, kind) => {
    fetchMock.mockResolvedValueOnce(Response.json({ error: { code, message: 'private-backend-message' } }, { status: Number(status) }))
    await expect(requestReindex(REINDEX_REQUEST_ID, options())).rejects.toMatchObject({ kind })
    expect(fetchMock).toHaveBeenCalledOnce()
  })
  it.each([null, { error: null }, { error: 'bad' }, {}, { error: {} }])('chịu được error envelope sai %j', async body => {
    fetchMock.mockResolvedValueOnce(Response.json(body, { status: 500 }))
    await expect(requestReindex(REINDEX_REQUEST_ID, options())).rejects.toMatchObject({ kind: 'server' })
  })
  it('chịu được body lỗi không phải JSON', async () => {
    fetchMock.mockResolvedValueOnce(new Response('bad gateway', { status: 502 }))
    await expect(requestReindex(REINDEX_REQUEST_ID, options())).rejects.toMatchObject({ kind: 'server' })
  })
  it('từ chối JSON thành công bị hỏng', async () => {
    fetchMock.mockResolvedValueOnce(new Response('bad json', { status: 202 }))
    await expect(requestReindex(REINDEX_REQUEST_ID, options())).rejects.toMatchObject({ kind: 'contract' })
  })
  it('không tự retry khi mất kết nối', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('private-network-detail'))
    await expect(requestReindex(REINDEX_REQUEST_ID, options())).rejects.toMatchObject({ kind: 'network' })
    expect(fetchMock).toHaveBeenCalledOnce()
  })
  it('không gửi khi thiếu khóa hoặc UUID sai', async () => {
    await expect(requestReindex(REINDEX_REQUEST_ID, { ...options(), adminKey: '  ' })).rejects.toMatchObject({ kind: 'access_denied' })
    await expect(requestReindex('bad', options())).rejects.toMatchObject({ kind: 'invalid' })
    expect(fetchMock).not.toHaveBeenCalled()
  })
  it.each([undefined, '', 'http://localhost:8000'])('dùng API origin cấu hình %s', async baseUrl => {
    vi.stubEnv('VITE_API_BASE_URL', baseUrl)
    fetchMock.mockResolvedValueOnce(Response.json(reindexResponse(), { status: 202 }))
    await requestReindex(REINDEX_REQUEST_ID, { adminKey: ADMIN_TEST_KEY, signal: new AbortController().signal })
    expect(fetchMock.mock.calls[0][0]).toBe(`${baseUrl ?? ''}/api/v1/admin/reindex`)
  })
  it('giữ lý do caller hủy', async () => {
    const controller = new AbortController()
    const reason = new DOMException('cancelled', 'AbortError')
    controller.abort(reason)
    fetchMock.mockRejectedValueOnce(reason)
    await expect(requestReindex(REINDEX_REQUEST_ID, { ...options(), signal: controller.signal })).rejects.toBe(reason)
  })
  it('timeout lúc đọc JSON vẫn là kết quả chưa xác định', async () => {
    const timeout = new AbortController()
    vi.spyOn(AbortSignal, 'timeout').mockReturnValue(timeout.signal)
    const response = Response.json(reindexResponse(), { status: 202 })
    vi.spyOn(response, 'json').mockImplementation(async () => { timeout.abort(); throw timeout.signal.reason })
    fetchMock.mockResolvedValueOnce(response)
    await expect(requestReindex(REINDEX_REQUEST_ID, options())).rejects.toMatchObject({ kind: 'network' })
  })
})
