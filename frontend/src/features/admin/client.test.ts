import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getAdminJob, listAdminJobs } from './client'
import type { JobMetadata } from './types'

const fetchMock = vi.fn<typeof fetch>()

// Khóa giả dành riêng cho tests.
const options = () => ({
  adminKey: 'test-admin-key-not-a-real-secret',
  signal: new AbortController().signal,
  baseUrl: 'http://localhost:8000',
})

const job: JobMetadata = {
  job_id: 'a0b674d2-1286-401f-b73b-72cae159fcad',
  kind: 'indexing',
  runner: 'prepare_text_search_index',
  status: 'running',
  created_at: '2026-11-14T08:00:00Z',
  updated_at: '2026-11-14T08:00:01Z',
  started_at: '2026-11-14T08:00:01Z',
  finished_at: null,
  progress: {
    unit: 'assets',
    processed: null,
    total: null,
    percent: null,
  },
  result: null,
  error: null,
}

function listBody(items: JobMetadata[] = []) {
  return {
    items,
    pagination: {
      page: 1,
      limit: 12,
      total: items.length,
      pages: items.length === 0 ? 0 : 1,
      has_next: false,
    },
    mock: false,
  }
}

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})

describe('admin jobs client', () => {
  it('gửi GET với filters, phân trang và khóa trong header', async () => {
    const requestOptions = options()
    fetchMock.mockResolvedValueOnce(Response.json(listBody()))

    await listAdminJobs(
      { kind: 'indexing', status: 'running', page: 1, limit: 12 },
      requestOptions,
    )

    expect(fetchMock).toHaveBeenCalledTimes(1)

    const [url, init] = fetchMock.mock.calls[0]
    const parsedUrl = new URL(String(url))

    expect(parsedUrl.pathname).toBe('/api/v1/admin/jobs')
    expect(Object.fromEntries(parsedUrl.searchParams)).toEqual({
      page: '1',
      limit: '12',
      kind: 'indexing',
      status: 'running',
    })
    expect(String(url)).not.toContain(requestOptions.adminKey)
    expect(init).toMatchObject({
      method: 'GET',
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
        'X-Admin-Key': requestOptions.adminKey,
      },
    })
  })

  it('giữ nguyên danh sách rỗng hợp lệ', async () => {
    const body = listBody()
    fetchMock.mockResolvedValueOnce(Response.json(body))

    await expect(listAdminJobs({}, options())).resolves.toEqual(body)
  })

  it('chấp nhận job có progress chưa xác định', async () => {
    fetchMock.mockResolvedValueOnce(Response.json(listBody([job])))

    const result = await listAdminJobs({}, options())

    expect(result.items[0]).toEqual(job)
    expect(result.items[0].progress.percent).toBeNull()
  })

  it('đọc chi tiết theo đúng job ID', async () => {
    fetchMock.mockResolvedValueOnce(Response.json({
      job,
      mock: false,
    }))

    await expect(getAdminJob(job.job_id, options())).resolves.toEqual({
      job,
      mock: false,
    })

    expect(fetchMock.mock.calls[0][0]).toBe(
      `http://localhost:8000/api/v1/admin/jobs/${job.job_id}`,
    )
  })

  it.each([
    [400, 'INVALID_REQUEST', 'invalid_request'],
    [403, 'ADMIN_ACCESS_DENIED', 'access_denied'],
    [404, 'JOB_NOT_FOUND', 'not_found'],
    [503, 'ADMIN_API_UNAVAILABLE', 'unconfigured'],
    [500, 'INTERNAL_ERROR', 'server'],
  ] as const)(
    'ánh xạ HTTP %s thành lỗi %s/%s',
    async (status, code, kind) => {
      fetchMock.mockResolvedValueOnce(Response.json({
        error: { code, message: 'Thông báo backend', details: [] },
      }, { status }))

      await expect(getAdminJob(job.job_id, options())).rejects.toMatchObject({
        name: 'AdminJobsError',
        kind,
        status,
      })

      expect(fetchMock).toHaveBeenCalledTimes(1)
    },
  )

  it('báo lỗi mạng và không tự retry hoặc trả fixtures', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))

    await expect(listAdminJobs({}, options())).rejects.toMatchObject({
      kind: 'network',
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('từ chối response mock', async () => {
    fetchMock.mockResolvedValueOnce(Response.json({
      ...listBody(),
      mock: true,
    }))

    await expect(listAdminJobs({}, options())).rejects.toMatchObject({
      kind: 'contract',
    })
  })

  it('từ chối JSON không hợp lệ', async () => {
    fetchMock.mockResolvedValueOnce(new Response('invalid-json', {
      status: 200,
    }))

    await expect(listAdminJobs({}, options())).rejects.toMatchObject({
      kind: 'contract',
    })
  })

  it('không gửi request khi thiếu khóa', async () => {
    await expect(listAdminJobs({}, {
      ...options(),
      adminKey: '',
    })).rejects.toMatchObject({
      kind: 'access_denied',
    })

    expect(fetchMock).not.toHaveBeenCalled()
  })
  it.each([
    { page: 0 },
    { page: 1.5 },
    { limit: 0 },
    { limit: 51 },
    { limit: 1.5 },
  ])('không gửi request với phân trang sai: %j', async (query) => {
    await expect(listAdminJobs(query, options())).rejects.toMatchObject({
      kind: 'invalid_request',
    })

    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('không gửi request với job ID sai', async () => {
    await expect(getAdminJob('not-a-uuid', options())).rejects.toMatchObject({
      kind: 'invalid_request',
    })

    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('từ chối chi tiết trả về nhầm job ID', async () => {
    fetchMock.mockResolvedValueOnce(Response.json({
      job: {
        ...job,
        job_id: 'b0b674d2-1286-401f-b73b-72cae159fcad',
      },
      mock: false,
    }))

    await expect(getAdminJob(job.job_id, options())).rejects.toMatchObject({
      kind: 'contract',
    })
  })

  it.each([
    null,
    {},
    { error: null },
    { error: { code: 123 } },
    { error: { code: 'OTHER_UNAVAILABLE' } },
  ])('không diễn giải mọi lỗi 503 là chưa cấu hình: %j', async (body) => {
    fetchMock.mockResolvedValueOnce(Response.json(body, { status: 503 }))

    await expect(listAdminJobs({}, options())).rejects.toMatchObject({
      kind: 'server',
      status: 503,
    })
  })

  it('xử lý HTTP lỗi có body không phải JSON', async () => {
    fetchMock.mockResolvedValueOnce(new Response('Bad gateway', {
      status: 502,
    }))

    await expect(listAdminJobs({}, options())).rejects.toMatchObject({
      kind: 'server',
      status: 502,
    })
  })

  it('phân biệt route không tồn tại với job không tồn tại', async () => {
    fetchMock.mockResolvedValueOnce(Response.json({
      error: { code: 'HTTP_404', message: 'Not found', details: [] },
    }, { status: 404 }))

    await expect(listAdminJobs({}, options())).rejects.toMatchObject({
      kind: 'server',
      status: 404,
    })
  })

  it.each([
    undefined,
    '',
    'http://localhost:8000',
  ])('dùng origin từ cấu hình khi không truyền baseUrl: %s', async (baseUrl) => {
    vi.stubEnv('VITE_API_BASE_URL', baseUrl)
    fetchMock.mockResolvedValueOnce(Response.json(listBody()))

    const { adminKey, signal } = options()
    await listAdminJobs({}, { adminKey, signal })

    expect(fetchMock.mock.calls[0][0]).toBe(
      `${baseUrl ?? ''}/api/v1/admin/jobs?page=1&limit=12`,
    )
  })

  it('giữ nguyên lý do hủy do bên gọi', async () => {
    const controller = new AbortController()
    const reason = new DOMException('Cancelled by caller', 'AbortError')

    controller.abort(reason)
    fetchMock.mockRejectedValueOnce(reason)

    await expect(listAdminJobs({}, {
      ...options(),
      signal: controller.signal,
    })).rejects.toBe(reason)
  })

  it('timeout khi chờ HTTP được phân loại là lỗi mạng', async () => {
    const timeout = new AbortController()
    const timeoutSpy = vi.spyOn(AbortSignal, 'timeout')
      .mockReturnValue(timeout.signal)

    fetchMock.mockImplementationOnce((_url, init) => new Promise(
      (_resolve, reject) => {
        const signal = init?.signal

        signal?.addEventListener('abort', () => {
          reject(signal.reason)
        }, { once: true })
      },
    ))

    const pending = listAdminJobs({}, options())
    const assertion = expect(pending).rejects.toMatchObject({
      kind: 'network',
    })

    timeout.abort(new DOMException('Request timed out', 'TimeoutError'))

    await assertion
    expect(timeoutSpy).toHaveBeenCalledWith(15000)
  })

  it('timeout khi đọc response body cũng là lỗi mạng', async () => {
    const timeout = new AbortController()
    vi.spyOn(AbortSignal, 'timeout').mockReturnValue(timeout.signal)

    const response = Response.json(listBody())
    const reason = new DOMException('Body timed out', 'TimeoutError')

    vi.spyOn(response, 'json').mockImplementation(async () => {
      timeout.abort(reason)
      throw reason
    })
    fetchMock.mockResolvedValueOnce(response)

    await expect(listAdminJobs({}, options())).rejects.toMatchObject({
      kind: 'network',
    })
  })
})