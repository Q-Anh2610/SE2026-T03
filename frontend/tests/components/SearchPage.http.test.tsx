import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SearchPage } from '../../src/features/search/SearchPage'
import { deferred, makeResponse } from '../../src/test/fixtures'

// Keep the production HTTP clients and validators; only transport is simulated.
vi.mock('../../src/lib/api/search', async (importOriginal) => {
  const api = await importOriginal<typeof import('../../src/lib/api/search')>()
  return {
    ...api,
    getSearchClient: async () => api.createHttpSearchClient(),
    getAssetClient: async () => api.createHttpAssetClient(),
  }
})

const fetchMock = vi.fn<typeof fetch>()
const json = (payload: unknown) => new Response(JSON.stringify(payload), { status: 200 })

function submit(query: string) {
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: query } })
  fireEvent.submit(screen.getByRole('search'))
}

function resultNames() {
  return within(screen.getByRole('list', { name: 'Kết quả asset' }))
    .getAllByRole('heading').map((heading) => heading.textContent)
}

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

describe('text search UI through HTTP clients (simulated transport, no retrieval)', () => {
  it('shows empty only after a successful response, keeping idle and loading distinct', async () => {
    const pending = deferred<Response>()
    fetchMock.mockReturnValueOnce(pending.promise)
    render(<SearchPage />)
    expect(screen.queryByText('Đang tìm asset…')).not.toBeInTheDocument()
    expect(screen.queryByText('Chưa có asset phù hợp')).not.toBeInTheDocument()
    submit('không khớp')
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce())
    expect(screen.getByRole('region', { name: 'Kết quả tìm kiếm' })).toHaveAttribute('aria-busy', 'true')
    expect(screen.queryByText('Chưa có asset phù hợp')).not.toBeInTheDocument()
    const empty = makeResponse('không khớp')
    empty.results = []
    empty.pagination = { page: 1, limit: 12, total: 0, pages: 0, has_next: false }
    await act(async () => { pending.resolve(json(empty)) })
    expect(await screen.findByText('Chưa có asset phù hợp')).toBeVisible()
    expect(screen.getByRole('region', { name: 'Kết quả tìm kiếm' })).toHaveAttribute('aria-busy', 'false')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it.each(['network', 'timeout'])('retries the failed request after %s even when draft query and filters change', async (failure) => {
    const timeout = new AbortController()
    vi.spyOn(AbortSignal, 'timeout').mockReturnValueOnce(timeout.signal)
    fetchMock.mockImplementationOnce((_url, options) => new Promise((_resolve, reject) => {
      if (failure === 'network') reject(new TypeError('private network failure'))
      else options!.signal!.addEventListener('abort', () => reject(options!.signal!.reason), { once: true })
    })).mockResolvedValueOnce(json(makeResponse('ghế')))
    const user = userEvent.setup()
    render(<SearchPage />)
    await user.click(screen.getByText('Bộ lọc', { exact: true }))
    await user.type(screen.getByLabelText('Định dạng'), 'glb')
    submit('  ghế  ')
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce())
    if (failure === 'timeout') {
      await act(async () => { timeout.abort(new DOMException('Timeout', 'TimeoutError')) })
    }
    expect(await screen.findByRole('alert')).toHaveTextContent('Không kết nối được dịch vụ tìm kiếm')
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'chưa gửi' } })
    await user.clear(screen.getByLabelText('Định dạng'))
    await user.selectOptions(screen.getByLabelText('Số kết quả'), '2')
    await user.click(screen.getByRole('button', { name: 'Thử lại' }))
    await screen.findByRole('list', { name: 'Kết quả asset' })
    expect(fetchMock.mock.calls[1][1]!.signal!.aborted).toBe(false)
    expect(JSON.parse(fetchMock.mock.calls[1][1]!.body as string)).toEqual({ query: 'ghế', filters: { format: 'glb' }, page: 1, limit: 12 })
    expect(fetchMock.mock.calls[1][1]!.body).toBe(fetchMock.mock.calls[0][1]!.body)
  })

  it('shows a missing detail without substituting search metadata and preserves results on back', async () => {
    fetchMock.mockResolvedValueOnce(json(makeResponse('ghế')))
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: 'ASSET_NOT_FOUND' } }), { status: 404 }))
    const user = userEvent.setup()
    render(<SearchPage />)
    submit('ghế')
    await user.click(await screen.findByRole('button', { name: 'Xem chi tiết Ghế gỗ kiểm thử' }))
    expect(await screen.findByRole('heading', { name: 'Không tìm thấy asset' })).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'Ghế gỗ kiểm thử' })).not.toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: 'Quay lại danh sách' })[0])
    expect(resultNames()).toEqual(['Ghế gỗ kiểm thử'])
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('preserves API order, page IDs and versions through pagination and detail/back', async () => {
    const user = userEvent.setup()
    const first = makeResponse('ghế')
    first.pagination = { page: 1, limit: 12, total: 13, pages: 2, has_next: true }
    const template = first.results[0]
    const names = ['Z cuối bảng chữ', 'A đầu bảng chữ', ...Array.from({ length: 10 }, (_, i) => `Asset ${i}`)]
    first.results = names.map((name, index) => ({
      ...template, rank: index + 1,
      asset: { ...template.asset, asset_id: `test-${index}`, name },
    }))
    const second = makeResponse('ghế')
    second.pagination = { ...first.pagination, page: 2, has_next: false }
    second.query_id = 'page-two-query'
    second.search_event_id = 'page-two-event'
    second.versions = { model_version: 'model-page-two', index_version: 'index-page-two', config_version: 'config-page-two' }
    second.results[0].asset = {
      ...template.asset, asset_id: 'id with ?#', name: 'Ghế trang hai',
      source: 'Nguồn kiểm thử', source_url: 'https://example.com/asset', author: 'Tác giả kiểm thử', license: 'CC0',
    }
    fetchMock.mockResolvedValueOnce(json(first)).mockResolvedValueOnce(json(second))
      .mockResolvedValueOnce(json({ asset: second.results[0].asset }))
    render(<SearchPage />)
    submit('  ghế  ')
    await screen.findByRole('list', { name: 'Kết quả asset' })
    expect(resultNames()).toEqual(names)
    await user.click(screen.getByRole('button', { name: 'Trang sau' }))
    await screen.findByRole('heading', { name: 'Ghế trang hai' })
    expect(JSON.parse(fetchMock.mock.calls[1][1]!.body as string)).toEqual({ query: 'ghế', filters: {}, limit: 12, page: 2 })
    await user.click(screen.getByText('Thông tin phiên tìm kiếm'))
    for (const value of [second.query_id, second.search_event_id, ...Object.values(second.versions)]) {
      expect(screen.getByText(value)).toBeVisible()
    }
    await user.click(screen.getByRole('button', { name: 'Xem chi tiết Ghế trang hai' }))
    const detail = await screen.findByRole('region', { name: 'Chi tiết asset' })
    await waitFor(() => expect(within(detail).getByText('Tác giả kiểm thử')).toBeVisible())
    expect(within(detail).getByText('CC0')).toBeVisible()
    expect(within(detail).getByRole('link', { name: 'Nguồn kiểm thử' })).toHaveAttribute('href', 'https://example.com/asset')
    expect(fetchMock.mock.calls[2][0]).toBe('/api/v1/assets/id%20with%20%3F%23')
    await user.click(screen.getByRole('button', { name: 'Quay lại danh sách' }))
    expect(resultNames()).toEqual(['Ghế trang hai'])
    expect(screen.getByRole('navigation', { name: 'Phân trang kết quả' })).toHaveTextContent('Trang 2 / 2 · 13 kết quả')
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it.each(['resolve', 'reject'] as const)('ignores an older request that later %ss after a newer HTTP result', async (outcome) => {
    const old = deferred<Response>()
    fetchMock.mockReturnValueOnce(old.promise).mockResolvedValueOnce(json(makeResponse('mới')))
    render(<SearchPage />)
    submit('cũ')
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    expect(screen.getByText('Đang tìm asset…')).toBeVisible()
    submit('mới')
    await screen.findByRole('list', { name: 'Kết quả asset' })
    expect(fetchMock.mock.calls[0][1]!.signal!.aborted).toBe(true)
    await act(async () => {
      if (outcome === 'resolve') old.resolve(json(makeResponse('cũ')))
      else old.reject(new TypeError('old connection failed'))
    })
    expect(screen.getByRole('status')).toHaveTextContent('“mới”')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('keeps API errors visible and retries the submitted query, then renders empty results', async () => {
    const empty = makeResponse('ghế')
    empty.results = []
    empty.pagination = { page: 1, limit: 12, total: 0, pages: 0, has_next: false }
    fetchMock.mockResolvedValueOnce(new Response('private server detail', { status: 503 }))
      .mockResolvedValueOnce(json(empty))
    const user = userEvent.setup()
    render(<SearchPage />)
    submit('ghế')
    expect(await screen.findByRole('alert')).toHaveTextContent('Dịch vụ tìm kiếm chưa sẵn sàng')
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'chưa gửi' } })
    await user.click(screen.getByRole('button', { name: 'Thử lại' }))
    await screen.findByRole('heading', { name: 'Chưa có asset phù hợp' })
    expect(fetchMock.mock.calls[1][1]!.body).toBe(fetchMock.mock.calls[0][1]!.body)
    expect(screen.queryByText('private server detail')).not.toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })
})
