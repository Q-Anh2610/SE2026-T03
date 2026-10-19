import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createHttpSearchClient } from './search'
import { makeRequest, makeResponse } from '../../test/fixtures'

describe('HTTP search client', () => {
  const fetchMock = vi.fn<typeof fetch>()

  beforeEach(() => { vi.stubGlobal('fetch', fetchMock) })

  it.each(['', 'https://api.example.com', 'https://api.example.com/'])('posts a normalized request using base URL %s', async (baseUrl) => {
    const response = makeResponse()
    fetchMock.mockResolvedValue(new Response(JSON.stringify(response), { status: 200 }))
    const client = createHttpSearchClient(baseUrl)
    expect(await client.search(makeRequest('  ghế gỗ  '), new AbortController().signal)).toEqual(response)
    const [url, options] = fetchMock.mock.calls[0]!
    expect(url).toBe(`${baseUrl.replace(/\/$/, '')}/api/v1/search/text`)
    expect(options).toMatchObject({ method: 'POST', headers: { 'Content-Type': 'application/json' } })
    expect(JSON.parse(options!.body as string)).toEqual(makeRequest())
    expect(options!.signal).toBeDefined()
  })

  it.each(['relative', 'ftp://api.example.com', 'https://user:secret@api.example.com',
    'https://api.example.com/path', 'https://api.example.com/?token=test', 'https://api.example.com/#fragment'])('rejects invalid API origins before fetching', async (baseUrl) => {
    await expect(createHttpSearchClient(baseUrl).search(makeRequest(), new AbortController().signal)).rejects.toThrow('Địa chỉ API')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('validates the request before fetching', async () => {
    await expect(createHttpSearchClient().search(makeRequest(' '), new AbortController().signal)).rejects.toThrow('1 đến 500')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it.each([400, 422, 503, 500, 404])('maps HTTP %s to a safe message without returning fixtures', async (status) => {
    fetchMock.mockResolvedValue(new Response('private server detail', { status }))
    const expected = [400, 422].includes(status) ? 'Yêu cầu tìm kiếm không hợp lệ' : status === 404 ? 'Không tìm thấy dịch vụ tìm kiếm' : 'Dịch vụ tìm kiếm chưa sẵn sàng'
    await expect(createHttpSearchClient().search(makeRequest(), new AbortController().signal)).rejects.toThrow(expected)
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('maps network failures and retains the original cause without exposing its message', async () => {
    const failure = new TypeError('private connection detail')
    fetchMock.mockRejectedValue(failure)
    await expect(createHttpSearchClient().search(makeRequest(), new AbortController().signal)).rejects.toMatchObject({
      message: 'Không kết nối được dịch vụ tìm kiếm. Kiểm tra kết nối rồi thử lại.', cause: failure,
    })
  })

  it('propagates caller cancellation instead of presenting it as a failed search', async () => {
    const controller = new AbortController()
    const aborted = new DOMException('Aborted', 'AbortError')
    controller.abort()
    fetchMock.mockRejectedValue(aborted)
    await expect(createHttpSearchClient().search(makeRequest(), controller.signal)).rejects.toBe(aborted)
  })

  it('passes caller cancellation through the combined fetch signal', async () => {
    const controller = new AbortController()
    fetchMock.mockImplementation((_url, options) => new Promise((_resolve, reject) => {
      options!.signal!.addEventListener('abort', () => reject(options!.signal!.reason), { once: true })
    }))
    const pending = createHttpSearchClient().search(makeRequest(), controller.signal)
    const assertion = expect(pending).rejects.toMatchObject({ name: 'AbortError' })
    controller.abort()
    await assertion
  })

  it('configures a 15-second timeout and treats timeout as a retryable network failure', async () => {
    const timeoutController = new AbortController()
    const timeout = vi.spyOn(AbortSignal, 'timeout').mockReturnValue(timeoutController.signal)
    fetchMock.mockImplementation((_url, options) => new Promise((_resolve, reject) => {
      options!.signal!.addEventListener('abort', () => reject(options!.signal!.reason), { once: true })
    }))
    const pending = createHttpSearchClient().search(makeRequest(), new AbortController().signal)
    const assertion = expect(pending).rejects.toThrow('Không kết nối được dịch vụ tìm kiếm')
    timeoutController.abort(new DOMException('Timeout', 'TimeoutError'))
    await assertion
    expect(timeout).toHaveBeenCalledWith(15000)
  })

  it('rejects invalid JSON without leaking its contents', async () => {
    fetchMock.mockResolvedValue(new Response('<html>private data</html>', { status: 200 }))
    await expect(createHttpSearchClient().search(makeRequest(), new AbortController().signal)).rejects.toThrow('API trả về dữ liệu không hợp lệ')
  })

  it('rejects valid JSON that violates the response contract', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ query_id: 'broken' }), { status: 200 }))
    await expect(createHttpSearchClient().search(makeRequest(), new AbortController().signal)).rejects.toThrow('không đúng contract nháp')
  })
})

describe('search client mode selection', () => {
  it('uses development mock by default without making an HTTP request', async () => {
    vi.useFakeTimers()
    vi.stubEnv('DEV', true)
    vi.stubEnv('MODE', 'development')
    vi.stubEnv('VITE_SEARCH_MODE', '')
    vi.resetModules()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const { getSearchClient, isMockMode } = await import('./search')
    expect(isMockMode).toBe(true)
    const client = await getSearchClient('empty')
    const pending = client.search(makeRequest(), new AbortController().signal)
    await vi.advanceTimersByTimeAsync(450)
    expect((await pending).results).toEqual([])
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it.each([
    [true, 'api', 'mock', ''],
    [true, 'development', 'api', 'https://api.example.com'],
    [false, 'production', 'mock', ''],
  ])('uses HTTP for DEV=%s MODE=%s selection=%s', async (development, mode, selection, baseUrl) => {
    vi.stubEnv('DEV', development)
    vi.stubEnv('MODE', mode)
    vi.stubEnv('VITE_SEARCH_MODE', selection)
    vi.stubEnv('VITE_API_BASE_URL', baseUrl)
    vi.resetModules()
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(makeResponse()), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    const { getSearchClient, isMockMode } = await import('./search')
    expect(isMockMode).toBe(false)
    const client = await getSearchClient('error')
    expect(await client.search(makeRequest(), new AbortController().signal)).toEqual(makeResponse())
    expect(fetchMock.mock.calls[0]?.[0]).toBe(`${baseUrl}/api/v1/search/text`)
  })

  it('defaults to same-origin HTTP when production has no configured API origin', async () => {
    vi.stubEnv('DEV', false)
    vi.stubEnv('VITE_API_BASE_URL', undefined)
    vi.resetModules()
    const fetchMock = vi.fn().mockResolvedValue(new Response('unavailable', { status: 503 }))
    vi.stubGlobal('fetch', fetchMock)
    const { getSearchClient } = await import('./search')
    const client = await getSearchClient('success')
    await expect(client.search(makeRequest(), new AbortController().signal)).rejects.toThrow('chưa sẵn sàng')
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/search/text')
  })
})
