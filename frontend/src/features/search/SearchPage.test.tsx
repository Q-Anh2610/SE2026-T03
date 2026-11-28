import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../../app/App'
import { deferred, makeLiveResponse, makeRequest, makeResponse } from '../../test/fixtures'
import type { AssetClient, AssetDetailResponse, AssetListResponse, SearchClient, SearchResponse } from './types'

const api = vi.hoisted(() => ({ mockMode: true, getSearchClient: vi.fn(), getAssetClient: vi.fn() }))

vi.mock('../../lib/api/search', () => ({
  getSearchClient: api.getSearchClient,
  getAssetClient: api.getAssetClient,
  get isMockMode() { return api.mockMode },
}))

describe('search page behavior', () => {
  it('sends all API filters, validates their range and resets them with the search', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByRole('searchbox'), 'glb')
    await user.click(screen.getByText('Bộ lọc', { exact: true }))
    await user.type(screen.getByLabelText('Danh mục', { exact: true }), ' Nội thất ')
    await user.type(screen.getByLabelText('Định dạng', { exact: true }), 'glb')
    await user.type(screen.getByLabelText('License', { exact: true }), 'CC0')
    await user.type(screen.getByLabelText('Số mặt tối thiểu'), '10')
    await user.type(screen.getByLabelText('Số mặt tối đa'), '2')
    await user.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Bộ lọc không hợp lệ')
    expect(searchMock).not.toHaveBeenCalled()
    await user.clear(screen.getByLabelText('Số mặt tối đa'))
    await user.type(screen.getByLabelText('Số mặt tối đa'), '100')
    searchMock.mockResolvedValueOnce({ ...makeResponse('glb'), results: [], pagination: { page: 1, limit: 12, total: 0, pages: 0, has_next: false } })
    await user.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))
    await screen.findByRole('heading', { name: 'Chưa có asset phù hợp' })
    expect(searchMock.mock.calls[0][0]).toEqual({ query: 'glb', page: 1, limit: 12, filters: { category: 'Nội thất', format: 'glb', license: 'CC0', face_count_min: 10, face_count_max: 100 } })
    await user.click(screen.getByRole('button', { name: 'Xóa tìm kiếm và bộ lọc' }))
    expect(screen.getByLabelText('Danh mục', { exact: true })).toHaveValue('')
  })

  it('uses the submitted query, filters and limit when navigating pages', async () => {
    const user = userEvent.setup()
    searchMock.mockImplementation(async request => ({ ...makeResponse(request.query),
      pagination: { page: request.page!, limit: request.limit, total: 13, pages: 2, has_next: request.page === 1 } }))
    render(<App />)
    await user.type(screen.getByRole('searchbox'), 'ghế gỗ{Enter}')
    await screen.findByRole('heading', { name: 'Ghế gỗ kiểm thử' })
    expect(screen.getByRole('button', { name: 'Trang trước' })).toBeDisabled()
    await user.clear(screen.getByRole('searchbox'))
    await user.type(screen.getByRole('searchbox'), 'chưa gửi')
    await user.selectOptions(screen.getByLabelText('Số kết quả'), '6')
    await user.click(screen.getByRole('button', { name: 'Trang sau' }))
    await waitFor(() => expect(screen.getByText('Trang 2 / 2 · 13 kết quả')).toBeVisible())
    expect(searchMock.mock.calls[1][0]).toEqual({ ...makeRequest(), page: 2 })
    expect(screen.getByRole('button', { name: 'Trang sau' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Trang trước' }))
    await waitFor(() => expect(screen.getByText('Trang 1 / 2 · 13 kết quả')).toBeVisible())
    expect(searchMock.mock.calls[2][0]).toEqual(makeRequest())
  })
  const searchMock = vi.fn<SearchClient['search']>()
  const listAssetsMock = vi.fn<AssetClient['listAssets']>()
  const getAssetMock = vi.fn<AssetClient['getAsset']>()

  beforeEach(() => {
    window.history.replaceState(null, '', window.location.pathname)
    api.mockMode = true
    api.getSearchClient.mockReset()
    api.getAssetClient.mockReset()
    searchMock.mockReset()
    listAssetsMock.mockReset()
    getAssetMock.mockReset()
    searchMock.mockImplementation(async (request) => makeResponse(request.query))
    listAssetsMock.mockImplementation(async (query) => ({
      items: [makeResponse().results[0]!.asset],
      pagination: { page: query.page ?? 1, limit: query.limit, total: 1, pages: 1, has_next: false },
      mock: true,
    }))
    getAssetMock.mockImplementation(async (assetId) => ({
      asset: { ...makeResponse().results[0]!.asset, asset_id: assetId },
      mock: true,
    }))
    api.getSearchClient.mockResolvedValue({ search: searchMock })
    api.getAssetClient.mockResolvedValue({ listAssets: listAssetsMock, getAsset: getAssetMock })
  })

  it('shows the search workspace and discovery examples before searching', () => {
    render(<App />)
    const hero = screen.getByRole('region', { name: 'Tìm mô hình 3D từ ý tưởng của bạn.' })
    expect(screen.queryByText('Khám phá thư viện 3D bằng mô tả của bạn.')).not.toBeInTheDocument()
    expect(within(hero).getByRole('search')).toBeVisible()
    expect(within(hero).getByRole('heading', { name: 'Tìm mô hình 3D từ ý tưởng của bạn.' })).toBeVisible()
    expect(screen.queryByRole('figure', { name: 'Hình minh họa mô hình 3D' })).not.toBeInTheDocument()
    expect(screen.getByRole('searchbox')).toHaveAttribute('placeholder', 'Ví dụ: ghế gỗ có lưng cong, đèn bàn màu xanh…')
    expect(screen.queryByRole('heading', { name: 'Bắt đầu từ một mô tả' })).not.toBeInTheDocument()
    expect(screen.getByRole('searchbox', { name: 'Bạn đang tìm asset nào?' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Tìm kiếm' })).toBeEnabled()
    expect(screen.queryByLabelText('Chế độ dữ liệu')).not.toBeInTheDocument()
    expect(screen.queryByText('Chế độ mẫu')).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Kết quả tìm kiếm' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Số kết quả')).not.toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Bạn đang tìm gì?' })).getAllByRole('button')).toHaveLength(4)
    expect(screen.queryByRole('list', { name: 'Kết quả asset' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Đến nội dung chính' })).toHaveAttribute('href', '#main')
    expect(api.getSearchClient).not.toHaveBeenCalled()
  })

  it('fills the search field from a discovery suggestion without submitting it', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'Điền gợi ý tìm kiếm: Ghế gỗ' }))
    expect(screen.getByRole('searchbox')).toHaveValue('Ghế gỗ')
    expect(screen.getByRole('searchbox')).toHaveFocus()
    expect(searchMock).not.toHaveBeenCalled()
  })

  it('keeps submitted search filters and pagination in the URL', async () => {
    const originalUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`
    window.history.replaceState(null, '', window.location.pathname)
    searchMock.mockImplementation(async (request) => ({
      ...makeResponse(request.query),
      pagination: { page: request.page ?? 1, limit: request.limit, total: 13, pages: 2, has_next: (request.page ?? 1) < 2 },
    }))
    const user = userEvent.setup()

    try {
      render(<App />)
      await user.type(screen.getByRole('searchbox'), 'ghế gỗ')
      await user.click(screen.getByText('Bộ lọc', { exact: true }))
      await user.type(screen.getByLabelText('Danh mục', { exact: true }), 'Nội thất')
      await user.type(screen.getByLabelText('Định dạng', { exact: true }), 'glb')
      await user.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))
      await screen.findByRole('heading', { name: 'Ghế gỗ kiểm thử' })

      let params = new URLSearchParams(window.location.search)
      expect(params.get('mode')).toBe('search')
      expect(params.get('q')).toBe('ghế gỗ')
      expect(params.get('filter_category')).toBe('Nội thất')
      expect(params.get('filter_format')).toBe('glb')
      expect(params.get('page')).toBeNull()
      expect(params.get('filters_open')).toBe('1')

      await user.click(screen.getByText('Bộ lọc', { exact: true }))
      await waitFor(() => expect(new URLSearchParams(window.location.search).get('filters_open')).toBe('0'))
      await user.click(screen.getByText('Bộ lọc', { exact: true }))

      await user.click(screen.getByRole('button', { name: 'Trang sau' }))
      await screen.findByText('Trang 2 / 2 · 13 kết quả')
      params = new URLSearchParams(window.location.search)
      expect(params.get('page')).toBe('2')
      expect(searchMock.mock.calls.at(-1)?.[0]).toEqual({
        query: 'ghế gỗ',
        filters: { category: 'Nội thất', format: 'glb' },
        limit: 12,
        page: 2,
      })
    } finally {
      window.history.replaceState(null, '', originalUrl)
    }
  })

  it('keeps an empty filter panel open or closed state in the URL', async () => {
    const originalUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`
    window.history.replaceState(null, '', window.location.pathname)
    const user = userEvent.setup()

    try {
      render(<App />)
      await user.click(screen.getByText('Bộ lọc', { exact: true }))
      await waitFor(() => expect(new URLSearchParams(window.location.search).get('filters_open')).toBe('1'))

      await user.click(screen.getByText('Bộ lọc', { exact: true }))
      await waitFor(() => expect(new URLSearchParams(window.location.search).get('filters_open')).toBe('0'))
    } finally {
      window.history.replaceState(null, '', originalUrl)
    }
  })

  it('restores a shared search URL and follows browser history changes', async () => {
    const originalUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`
    window.history.replaceState(null, '', '/?mode=search&q=gh%E1%BA%BF%20g%E1%BB%97&limit=6&page=2&filter_category=N%E1%BB%99i%20th%E1%BA%A5t&filter_format=glb&facet=G%E1%BB%97')
    searchMock.mockImplementation(async (request) => ({
      ...makeResponse(request.query),
      pagination: { page: request.page ?? 1, limit: request.limit, total: 13, pages: 2, has_next: (request.page ?? 1) < 2 },
    }))

    try {
      render(<App />)
      await screen.findByText('Trang 2 / 2 · 13 kết quả')
      expect(screen.getByRole('searchbox')).toHaveValue('ghế gỗ')
      expect(searchMock).toHaveBeenLastCalledWith({
        query: 'ghế gỗ',
        filters: { category: 'Nội thất', format: 'glb' },
        limit: 6,
        page: 2,
      }, expect.any(AbortSignal))
      expect(screen.getByText('Bộ lọc', { exact: true }).closest('details')).toHaveAttribute('open', '')
      await userEvent.setup().click(screen.getByText('Bộ lọc', { exact: true }))
      expect(screen.getByLabelText('Danh mục', { exact: true })).toHaveValue('Nội thất')
      expect(screen.getByLabelText('Định dạng', { exact: true })).toHaveValue('glb')

      window.history.pushState(null, '', '/?mode=search&q=lamp&limit=2&filter_format=fbx')
      window.dispatchEvent(new PopStateEvent('popstate'))
      await waitFor(() => expect(searchMock).toHaveBeenLastCalledWith({
        query: 'lamp',
        filters: { format: 'fbx' },
        limit: 2,
        page: 1,
      }, expect.any(AbortSignal)))
      expect(screen.getByRole('searchbox')).toHaveValue('lamp')
    } finally {
      window.history.replaceState(null, '', originalUrl)
    }
  })

  it('keeps results and an unsent draft when navigating to a search anchor', async () => {
    const user = userEvent.setup()
    render(<App />)
    const query = screen.getByRole('searchbox')
    await user.type(query, 'ghế gỗ{Enter}')
    await screen.findByRole('heading', { name: 'Ghế gỗ kiểm thử' })
    await user.clear(query)
    await user.type(query, 'bản nháp chưa gửi')

    await act(async () => {
      window.history.pushState(null, '', '#search-panel')
      window.dispatchEvent(new PopStateEvent('popstate'))
    })

    expect(query).toHaveValue('bản nháp chưa gửi')
    expect(searchMock).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('heading', { name: 'Ghế gỗ kiểm thử' })).toBeVisible()
    expect(new URLSearchParams(window.location.search).get('q')).toBe('ghế gỗ')

    await act(async () => {
      window.history.pushState(null, '', '/')
      window.dispatchEvent(new PopStateEvent('popstate'))
    })
    expect(query).toHaveValue('')
    expect(screen.getByRole('region', { name: 'Bạn đang tìm gì?' })).toBeVisible()
    expect(searchMock).toHaveBeenCalledTimes(1)
  })

  it('returns from detail via a search anchor without rerunning the search', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByRole('searchbox'), 'ghế gỗ{Enter}')
    await user.click(await screen.findByRole('button', { name: 'Xem chi tiết Ghế gỗ kiểm thử' }))
    expect(await screen.findByRole('region', { name: 'Chi tiết asset' })).toBeVisible()

    await act(async () => {
      window.history.pushState(null, '', '#asset-query')
      window.dispatchEvent(new PopStateEvent('popstate'))
    })

    expect(screen.getByRole('region', { name: 'Kết quả tìm kiếm' })).toBeVisible()
    expect(screen.queryByRole('region', { name: 'Chi tiết asset' })).not.toBeInTheDocument()
    expect(searchMock).toHaveBeenCalledTimes(1)
  })

  it('closes the filter disclosure when resetting an empty search', async () => {
    searchMock.mockResolvedValueOnce({ ...makeResponse(), results: [] })
    const user = userEvent.setup()
    render(<App />)
    const summary = screen.getByText('Bộ lọc', { exact: true })
    await user.click(summary)
    await user.type(screen.getByLabelText('Định dạng'), 'glb')
    await user.type(screen.getByRole('searchbox'), 'ghế gỗ{Enter}')
    await user.click(await screen.findByRole('button', { name: 'Xóa tìm kiếm và bộ lọc' }))

    expect(summary.closest('details')).not.toHaveAttribute('open')
    expect(screen.getByLabelText('Định dạng')).toHaveValue('')
    expect(screen.getByRole('searchbox')).toHaveFocus()
    expect(new URLSearchParams(window.location.search).get('filters_open')).toBe('0')
  })

  it('restores a catalog URL and applies its facet only to the received page', async () => {
    window.history.replaceState(null, '', '/?mode=browse&limit=7&page=2&facet=Chi%E1%BA%BFu%20s%C3%A1ng')
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Chưa có asset phù hợp' })).toBeVisible()
    expect(listAssetsMock).toHaveBeenCalledWith({ filters: {}, limit: 12, page: 2 }, expect.any(AbortSignal))
    expect(searchMock).not.toHaveBeenCalled()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Tất cả' }))
    expect(await screen.findByRole('heading', { name: 'Ghế gỗ kiểm thử' })).toBeVisible()
    expect(listAssetsMock).toHaveBeenCalledTimes(1)
    expect(new URLSearchParams(window.location.search).has('facet')).toBe(false)
  })

  it('shows signed cosine values and keeps the explanation available in live results', async () => {
    const response = makeLiveResponse()
    const result = response.results[0]
    Object.assign(result, { score_type: 'cosine', score: -0.125 })
    searchMock.mockResolvedValueOnce(response)
    render(<App />)
    await userEvent.setup().type(screen.getByRole('searchbox'), 'ghế gỗ{Enter}')

    expect(await screen.findByText(result.explanation)).toBeVisible()
    expect(screen.getByText('-0,125')).toBeVisible()
    expect(screen.getByRole('complementary', { name: 'Cách đọc kết quả tìm kiếm' })).toHaveTextContent('Điểm cosine')
    expect(screen.getByText('Văn bản → ảnh xem trước')).toBeVisible()
  })

  it.each(['search', 'browse'] as const)('can clear API filters directly after a %s error', async (mode) => {
    const user = userEvent.setup()
    const client = mode === 'search' ? searchMock : listAssetsMock
    client.mockRejectedValueOnce(new Error('Lỗi API kiểm thử'))
    window.history.replaceState(null, '', `/?mode=${mode}&q=gh%E1%BA%BF%20g%E1%BB%97&filter_format=glb`)
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Lỗi API kiểm thử')
    await user.click(screen.getByRole('button', { name: 'Đặt lại bộ lọc API' }))
    expect(await screen.findByRole('heading', { name: 'Ghế gỗ kiểm thử' })).toBeVisible()
    expect(client.mock.calls.map(([request]) => request.filters)).toEqual([{ format: 'glb' }, {}])
  })

  it('opens, scrolls to and focuses the filter summary from the sidebar link', async () => {
    const user = userEvent.setup()
    render(<App />)
    const summary = screen.getByText('Bộ lọc', { exact: true })
    const disclosure = summary.closest('details')!
    const scrollIntoView = vi.fn()
    Object.defineProperty(summary, 'scrollIntoView', { configurable: true, value: scrollIntoView })

    const filterLink = screen.getByRole('link', { name: /LỌC THUỘC TÍNH/ })
    filterLink.focus()
    await user.keyboard('{Enter}')

    expect(disclosure).toHaveAttribute('open', '')
    expect(summary).toHaveFocus()
    expect(scrollIntoView).toHaveBeenCalledWith({ block: 'start' })
  })

  it('keeps the browse label stable and exposes current, busy and error states', async () => {
    const user = userEvent.setup()
    listAssetsMock.mockImplementation(async (query) => ({
      items: [makeResponse().results[0]!.asset],
      pagination: { page: query.page ?? 1, limit: query.limit, total: 13, pages: 2, has_next: (query.page ?? 1) < 2 },
      mock: true,
    }))
    render(<App />)
    const browseButton = screen.getByRole('button', { name: /Duyệt thư viện/ })
    expect(browseButton).toHaveTextContent('Duyệt thư viện')
    expect(browseButton).toHaveAttribute('aria-pressed', 'false')
    await user.click(screen.getByRole('button', { name: 'Danh sách asset' }))
    await screen.findByRole('heading', { name: 'Danh sách asset' })
    expect(new URLSearchParams(window.location.search).get('mode')).toBe('browse')
    expect(browseButton).toHaveTextContent('Duyệt thư viện')
    expect(browseButton).toHaveAttribute('aria-pressed', 'true')
    await user.selectOptions(screen.getByLabelText('Số kết quả'), '6')
    await user.click(screen.getByText('Bộ lọc', { exact: true }))
    await user.type(screen.getByLabelText('Danh mục', { exact: true }), ' Nội thất ')
    await user.type(screen.getByLabelText('Định dạng', { exact: true }), 'glb')
    await user.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))
    await waitFor(() => expect(listAssetsMock).toHaveBeenLastCalledWith(
      { page: 1, limit: 6, filters: { category: 'Nội thất', format: 'glb' } }, expect.any(AbortSignal),
    ))
    await user.click(screen.getByRole('button', { name: 'Trang sau' }))
    await screen.findByText('Trang 2 / 2 · 13 kết quả')
    expect(new URLSearchParams(window.location.search).get('page')).toBe('2')

    const pending = deferred<AssetListResponse>()
    listAssetsMock.mockReturnValueOnce(pending.promise)
    expect(browseButton).toHaveAttribute('aria-pressed', 'true')
    await user.click(browseButton)
    await waitFor(() => expect(listAssetsMock).toHaveBeenLastCalledWith(
      { page: 1, limit: 6, filters: { category: 'Nội thất', format: 'glb' } }, expect.any(AbortSignal),
    ))
    expect(browseButton).toBeDisabled()
    expect(browseButton).toHaveTextContent('Duyệt thư viện')
    expect(browseButton).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('status')).toHaveTextContent('Đang tải danh sách asset')
    expect(screen.getByLabelText('Số kết quả')).toBeDisabled()
    expect(screen.getByLabelText('Số kết quả')).toHaveValue('6')

    await act(async () => {
      pending.resolve({
        items: [makeResponse().results[0]!.asset],
        pagination: { page: 1, limit: 6, total: 13, pages: 2, has_next: true },
        mock: true,
      })
      await pending.promise
    })
    await screen.findByText('Trang 1 / 2 · 13 kết quả')
    expect(browseButton).toBeEnabled()
    expect(browseButton).toHaveTextContent('Duyệt thư viện')
    expect(browseButton).toHaveAttribute('aria-pressed', 'true')

    listAssetsMock.mockRejectedValueOnce(new Error('Lỗi duyệt kiểm thử'))
    await user.click(browseButton)
    expect(await screen.findByRole('alert')).toHaveTextContent('Lỗi duyệt kiểm thử')
    expect(screen.getByRole('button', { name: /Duyệt thư viện/ })).toBe(browseButton)
    expect(browseButton).toHaveTextContent('Duyệt thư viện')
    expect(browseButton).toHaveAttribute('aria-pressed', 'true')
  })

  it('blocks an empty query, focuses the field and clears the error when edited', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'Tìm kiếm' }))
    const query = screen.getByLabelText('Bạn đang tìm asset nào?')
    expect(screen.getByRole('alert')).toHaveTextContent('1 đến 500 ký tự')
    expect(query).toHaveFocus()
    expect(query).toHaveAttribute('aria-invalid', 'true')
    expect(api.getSearchClient).not.toHaveBeenCalled()
    await user.type(query, 'ghế')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(query).toHaveAttribute('aria-invalid', 'false')
  })

  it('blocks an oversized query without starting a search', async () => {
    render(<App />)
    fireEvent.change(screen.getByLabelText('Bạn đang tìm asset nào?'), { target: { value: 'a'.repeat(501) } })
    fireEvent.submit(screen.getByRole('button', { name: 'Tìm kiếm' }).closest('form')!)
    expect(screen.getByRole('alert')).toHaveTextContent('1 đến 500 ký tự')
    expect(searchMock).not.toHaveBeenCalled()
  })

  it('submits normalized query and limit, shows loading, then renders metadata and session details', async () => {
    const pending = deferred<SearchResponse>()
    searchMock.mockReturnValueOnce(pending.promise)
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByLabelText('Bạn đang tìm asset nào?'), '  ghế gỗ  ')
    await user.click(screen.getByRole('button', { name: 'Tìm kiếm' }))
    expect(screen.getByRole('button', { name: 'Đang tìm…' })).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent('Đang tìm kết quả cho “ghế gỗ”')
    expect(screen.getByText('Đang tìm asset…')).toBeVisible()
    expect(screen.getByRole('region', { name: 'Kết quả tìm kiếm' })).toHaveAttribute('aria-busy', 'true')
    expect(searchMock.mock.calls[0]?.[0]).toEqual(makeRequest('ghế gỗ', 12))
    expect(screen.queryByRole('region', { name: 'Bạn đang tìm gì?' })).not.toBeInTheDocument()
    expect(searchMock.mock.calls[0]?.[1].aborted).toBe(false)
    await act(async () => { pending.resolve(makeResponse()); await pending.promise })
    expect(screen.getByRole('heading', { name: 'Ghế gỗ kiểm thử' })).toBeVisible()
    expect(screen.getByRole('status')).toHaveTextContent('Có 1 kết quả cho “ghế gỗ”')
    expect(screen.getByRole('button', { name: 'Tìm kiếm' })).toBeEnabled()
    expect(screen.getByText('Thông tin phiên tìm kiếm').closest('details')).not.toHaveAttribute('open')
    expect(screen.getByText('test-query-01')).not.toBeVisible()
    await user.click(screen.getByText('Thông tin phiên tìm kiếm'))
    expect(screen.getByText('test-query-01')).toBeVisible()
    expect(screen.getByText('test-event-01')).toBeVisible()
    expect(screen.getByText('test-model')).toBeVisible()
    expect(screen.getByText('test-index')).toBeVisible()
    expect(screen.getByText('test-config')).toBeVisible()
  })

  it('applies the chosen limit to the next search without silently rerunning the current query', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByRole('searchbox'), 'ghế gỗ{Enter}')
    await screen.findByRole('heading', { name: 'Ghế gỗ kiểm thử' })
    await user.selectOptions(screen.getByLabelText('Số kết quả'), '6')
    expect(searchMock).toHaveBeenCalledTimes(1)
    await user.click(screen.getByRole('button', { name: 'Tìm kiếm' }))
    await waitFor(() => expect(searchMock).toHaveBeenCalledTimes(2))
    expect(searchMock.mock.calls[1][0]).toEqual(makeRequest('ghế gỗ', 6))
  })

  it('supports keyboard submission from the search button', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.tab()
    expect(screen.getByRole('link', { name: 'Đến nội dung chính' })).toHaveFocus()
    await user.click(screen.getByLabelText('Bạn đang tìm asset nào?'))
    await user.keyboard('chair')
    await user.tab()
    expect(screen.getByRole('button', { name: 'Xóa truy vấn' })).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('button', { name: 'Tìm kiếm' })).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(await screen.findByRole('heading', { name: 'Ghế gỗ kiểm thử' })).toBeVisible()
    expect(searchMock.mock.calls[0]?.[0].query).toBe('chair')
  })

  it('filters received results locally and preserves the filter when clearing the query', async () => {
    const response = makeResponse()
    response.results[0].asset.category = 'Nội thất'
    response.results.push({
      ...response.results[0], rank: 2,
      asset: { ...response.results[0].asset, asset_id: 'test-lamp', name: 'Đèn kiểm thử', category: 'Chiếu sáng' },
    })
    searchMock.mockResolvedValueOnce(response)
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByRole('searchbox'), 'ghế gỗ{Enter}')
    const filters = await screen.findByRole('group', { name: 'Lọc danh mục trong trang' })
    await user.click(within(filters).getByRole('button', { name: 'Nội thất' }))
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
    expect(screen.getByRole('status')).toHaveTextContent('Có 1 kết quả')
    expect(within(filters).getByRole('button', { name: 'Nội thất' })).toHaveAttribute('aria-pressed', 'true')
    expect(searchMock).toHaveBeenCalledTimes(1)
    expect(searchMock.mock.calls[0]?.[0].filters).toEqual({})
    await user.click(within(filters).getByRole('button', { name: 'Tất cả' }))
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    await user.click(within(filters).getByRole('button', { name: 'Nội thất' }))
    await user.click(screen.getByRole('button', { name: 'Xóa truy vấn' }))
    expect(screen.getByRole('searchbox')).toHaveValue('')
    expect(screen.getByRole('searchbox')).toHaveFocus()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Bạn đang tìm gì?' })).toBeVisible()
    expect(screen.getByText(/chỉ trong trang đã nhận/)).toHaveTextContent('Nội thất')
    await user.click(screen.getByRole('button', { name: 'Xóa bộ lọc' }))
    expect(screen.queryByText(/Đang lọc:/)).not.toBeInTheDocument()
    expect(screen.getByRole('searchbox')).toHaveFocus()
  })

  it('clears a pending search and ignores its late result', async () => {
    const pending = deferred<SearchResponse>()
    searchMock.mockReturnValueOnce(pending.promise)
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByRole('searchbox'), 'ghế gỗ{Enter}')
    const signal = searchMock.mock.calls[0]![1]
    await user.click(screen.getByRole('button', { name: 'Xóa truy vấn' }))
    expect(signal.aborted).toBe(true)
    expect(screen.getByRole('searchbox')).toHaveFocus()
    await act(async () => { pending.resolve(makeResponse()); await pending.promise })
    expect(screen.queryByRole('heading', { name: 'Bắt đầu từ một mô tả' })).not.toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('omits suggestions, usage hints and development scenario controls', () => {
    render(<App />)
    expect(screen.queryByText('Thử với')).not.toBeInTheDocument()
    expect(screen.queryByText('Thử trạng thái giao diện')).not.toBeInTheDocument()
    expect(screen.getByRole('searchbox')).not.toHaveAttribute('aria-describedby')
  })

  it('presents empty results as a successful search with guidance', async () => {
    searchMock.mockResolvedValueOnce({ ...makeResponse(), results: [] })
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByLabelText('Bạn đang tìm asset nào?'), 'ghế gỗ')
    await user.click(screen.getByRole('button', { name: 'Tìm kiếm' }))
    expect(await screen.findByRole('heading', { name: 'Chưa có asset phù hợp' })).toBeVisible()
    expect(screen.getByRole('status')).toHaveTextContent('Có 0 kết quả')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Xóa tìm kiếm và bộ lọc' }))
    expect(screen.getByRole('searchbox')).toHaveValue('')
    expect(screen.getByRole('searchbox')).toHaveFocus()
    expect(screen.queryByText('Thông tin phiên tìm kiếm')).not.toBeInTheDocument()
  })

  it('retries the previous request after an error', async () => {
    searchMock.mockRejectedValueOnce(new Error('Sự cố kiểm thử'))
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByLabelText('Bạn đang tìm asset nào?'), 'ghế gỗ')
    await user.click(screen.getByRole('button', { name: 'Tìm kiếm' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Sự cố kiểm thử')
    expect(api.getSearchClient).toHaveBeenLastCalledWith('success')
    await user.clear(screen.getByLabelText('Bạn đang tìm asset nào?'))
    await user.type(screen.getByLabelText('Bạn đang tìm asset nào?'), 'query mới chưa gửi')
    await user.click(screen.getByRole('button', { name: 'Thử lại' }))
    expect(await screen.findByRole('heading', { name: 'Ghế gỗ kiểm thử' })).toBeVisible()
    expect(searchMock.mock.calls[1]?.[0]).toEqual(makeRequest())
    expect(api.getSearchClient).toHaveBeenLastCalledWith('success')
  })

  it('keeps production errors visible without showing mock controls or results', async () => {
    api.mockMode = false
    searchMock.mockRejectedValue(new Error('API chưa sẵn sàng'))
    const user = userEvent.setup()
    render(<App />)
    expect(screen.queryByLabelText('Chế độ dữ liệu')).not.toBeInTheDocument()
    expect(screen.queryByText('Thử trạng thái giao diện')).not.toBeInTheDocument()
    await user.type(screen.getByRole('searchbox'), 'Ghế gỗ{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent('API chưa sẵn sàng')
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Thử lại' }))
    await waitFor(() => expect(searchMock).toHaveBeenCalledTimes(2))
    expect(screen.getByRole('alert')).toHaveTextContent('API chưa sẵn sàng')
  })

  it('renders a generic safe error when a client rejects with a non-Error value', async () => {
    api.getSearchClient.mockRejectedValueOnce('untrusted failure details')
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByRole('searchbox'), 'Ghế gỗ{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent('Không thể tìm kiếm. Hãy thử lại.')
    expect(screen.queryByText('untrusted failure details')).not.toBeInTheDocument()
  })

  it('cancels an older request and ignores its late successful response', async () => {
    const first = deferred<SearchResponse>()
    searchMock.mockReturnValueOnce(first.promise)
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByRole('searchbox'), 'Ghế gỗ{Enter}')
    const originalSignal = searchMock.mock.calls[0]![1]
    await user.click(screen.getByRole('button', { name: 'Xóa truy vấn' }))
    await user.type(screen.getByRole('searchbox'), 'Thùng gỗ{Enter}')
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Có 1 kết quả cho “Thùng gỗ”'))
    expect(originalSignal.aborted).toBe(true)
    await act(async () => { first.resolve(makeResponse('Ghế gỗ')); await first.promise })
    expect(screen.getByRole('status')).toHaveTextContent('Có 1 kết quả cho “Thùng gỗ”')
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
  })

  it('ignores errors from a replaced request', async () => {
    const first = deferred<SearchResponse>()
    searchMock.mockReturnValueOnce(first.promise)
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByRole('searchbox'), 'Ghế gỗ{Enter}')
    await user.click(screen.getByRole('button', { name: 'Xóa truy vấn' }))
    await user.type(screen.getByRole('searchbox'), 'Thùng gỗ{Enter}')
    await screen.findByRole('heading', { name: 'Ghế gỗ kiểm thử' })
    await act(async () => { first.reject(new Error('Stale error')); await first.promise.catch(() => undefined) })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Thùng gỗ')
  })

  it('does not start a replaced request whose client is still loading', async () => {
    const firstClient = deferred<SearchClient>()
    const staleSearch = vi.fn<SearchClient['search']>()
    api.getSearchClient.mockReturnValueOnce(firstClient.promise)
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByRole('searchbox'), 'Ghế gỗ{Enter}')
    await user.click(screen.getByRole('button', { name: 'Xóa truy vấn' }))
    await user.type(screen.getByRole('searchbox'), 'Đèn bàn{Enter}')
    await screen.findByRole('heading', { name: 'Ghế gỗ kiểm thử' })
    await act(async () => { firstClient.resolve({ search: staleSearch }); await firstClient.promise })
    expect(staleSearch).not.toHaveBeenCalled()
    expect(screen.getByRole('status')).toHaveTextContent('Đèn bàn')
  })

  it('aborts an in-flight request when the page unmounts', async () => {
    const pending = deferred<SearchResponse>()
    searchMock.mockReturnValueOnce(pending.promise)
    const user = userEvent.setup()
    const { unmount } = render(<App />)
    await user.type(screen.getByRole('searchbox'), 'Ghế gỗ{Enter}')
    const signal = searchMock.mock.calls[0]![1]
    unmount()
    expect(signal.aborted).toBe(true)
    await act(async () => { pending.resolve(makeResponse('Ghế gỗ')); await pending.promise })
  })

  it('browses the asset catalog, paginates, changes limit to page 1, applies/resets API filters and preserves state when opening detail and returning', async () => {
    const user = userEvent.setup()
    listAssetsMock.mockImplementation(async (query) => ({
      items: [{ ...makeResponse().results[0]!.asset, asset_id: `chair-p${query.page}`, name: `Ghế trang ${query.page}` }],
      pagination: { page: query.page ?? 1, limit: query.limit, total: 13, pages: 2, has_next: (query.page ?? 1) < 2 },
      mock: true,
    }))
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'Danh sách asset' }))
    expect(await screen.findByRole('heading', { name: 'Danh sách asset' })).toBeVisible()
    expect(screen.getByText('1 / 1 asset trong trang')).toBeVisible()
    expect(listAssetsMock.mock.calls[0]?.[0]).toEqual({ page: 1, limit: 12, filters: {} })

    await user.click(screen.getByRole('button', { name: 'Trang sau' }))
    await waitFor(() => expect(screen.getByText('Trang 2 / 2 · 13 kết quả')).toBeVisible())
    expect(screen.getByRole('heading', { name: 'Ghế trang 2' })).toBeVisible()

    // Open detail from page 2 and return: keeps page 2, limit and filters
    await user.click(screen.getByRole('button', { name: 'Xem chi tiết Ghế trang 2' }))
    expect(await screen.findByRole('heading', { name: 'Ghế gỗ kiểm thử' })).toBeVisible()
    expect(getAssetMock).toHaveBeenCalledWith('chair-p2', expect.any(AbortSignal))
    await user.click(screen.getByRole('button', { name: 'Quay lại danh sách' }))
    expect(screen.getByText('Trang 2 / 2 · 13 kết quả')).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Ghế trang 2' })).toBeVisible()

    // Changing limit in catalog reloads page 1
    await user.selectOptions(screen.getByLabelText('Số kết quả'), '6')
    await waitFor(() => expect(listAssetsMock).toHaveBeenLastCalledWith({ page: 1, limit: 6, filters: {} }, expect.any(AbortSignal)))

    // Applying API filter without text query reloads catalog at page 1
    await user.click(screen.getByText('Bộ lọc', { exact: true }))
    await user.type(screen.getByLabelText('Danh mục', { exact: true }), 'Nội thất')
    await user.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))
    await waitFor(() => expect(listAssetsMock).toHaveBeenLastCalledWith({ page: 1, limit: 6, filters: { category: 'Nội thất' } }, expect.any(AbortSignal)))

    // Resetting API filters reloads catalog at page 1 with empty filters
    await user.click(screen.getByRole('button', { name: 'Đặt lại bộ lọc API' }))
    await waitFor(() => expect(listAssetsMock).toHaveBeenLastCalledWith({ page: 1, limit: 6, filters: {} }, expect.any(AbortSignal)))

    // Navigating back to page 1 from page 2 in catalog
    await user.click(screen.getByRole('button', { name: 'Trang sau' }))
    await waitFor(() => expect(screen.getByText('Trang 2 / 2 · 13 kết quả')).toBeVisible())
    await user.click(screen.getByRole('button', { name: 'Trang trước' }))
    await waitFor(() => expect(screen.getByText('Trang 1 / 2 · 13 kết quả')).toBeVisible())
  })

  it('handles catalog validation error, API error/retry, late response cancellation and search filter reset', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByText('Bộ lọc', { exact: true }))
    await user.type(screen.getByLabelText('Số mặt tối thiểu'), '20')
    await user.type(screen.getByLabelText('Số mặt tối đa'), '5')
    await user.click(screen.getByRole('button', { name: 'Danh sách asset' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Bộ lọc không hợp lệ')
    expect(listAssetsMock).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Đặt lại bộ lọc API' }))
    listAssetsMock.mockRejectedValueOnce(new Error('Dịch vụ asset chưa sẵn sàng.'))
    await user.click(screen.getByRole('button', { name: 'Danh sách asset' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Dịch vụ asset chưa sẵn sàng.')
    await user.click(screen.getByRole('button', { name: 'Thử lại' }))
    expect(await screen.findByRole('heading', { name: 'Ghế gỗ kiểm thử' })).toBeVisible()

    // Non-Error rejection in catalog
    listAssetsMock.mockRejectedValueOnce('raw catalog error')
    await user.click(screen.getByRole('button', { name: 'Danh sách asset' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Không thể tải danh sách asset. Hãy thử lại.')

    // Client loading aborted before listAssets runs
    const slowAssetClient = deferred<AssetClient>()
    api.getAssetClient.mockReturnValueOnce(slowAssetClient.promise)
    await user.type(screen.getByRole('searchbox'), 'ghế')
    await user.click(screen.getByRole('button', { name: 'Danh sách asset' }))
    await user.click(screen.getByRole('button', { name: 'Xóa truy vấn' }))
    await act(async () => {
      slowAssetClient.resolve({ listAssets: listAssetsMock, getAsset: getAssetMock })
      await slowAssetClient.promise
    })
    await user.type(screen.getByRole('searchbox'), 'ghế{Enter}')
    await screen.findByRole('heading', { name: 'Kết quả tìm kiếm' })

    // Resetting API filters while in search success state reruns search with empty filters at page 1
    await user.click(screen.getByRole('button', { name: 'Đặt lại bộ lọc API' }))
    await waitFor(() => expect(searchMock).toHaveBeenLastCalledWith({ query: 'ghế', filters: {}, limit: 12, page: 1 }, expect.any(AbortSignal)))
  })

  it('handles detail view 404, error, retry, late responses and opening detail from search results', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByRole('searchbox'), 'ghế gỗ{Enter}')
    await screen.findByRole('heading', { name: 'Ghế gỗ kiểm thử' })

    // 404 in detail view
    getAssetMock.mockRejectedValueOnce({ kind: 'not_found', message: 'Không tìm thấy asset trong thư viện.' })
    await user.click(screen.getByRole('button', { name: 'Xem chi tiết Ghế gỗ kiểm thử' }))
    expect(await screen.findByRole('heading', { name: 'Không tìm thấy asset' })).toBeVisible()
    await user.click(screen.getAllByRole('button', { name: 'Quay lại danh sách' })[0]!)
    expect(screen.getByRole('heading', { name: 'Ghế gỗ kiểm thử' })).toBeVisible()

    // Error + Retry in detail view
    getAssetMock.mockRejectedValueOnce('unexpected detail failure')
    await user.click(screen.getByRole('button', { name: 'Xem chi tiết Ghế gỗ kiểm thử' }))
    expect(await screen.findByRole('heading', { name: 'Chưa thể tải chi tiết asset' })).toBeVisible()
    expect(screen.getByRole('alert')).toHaveTextContent('Không thể tải chi tiết asset. Hãy thử lại.')
    await user.click(screen.getByRole('button', { name: 'Thử lại' }))
    expect(await screen.findByRole('heading', { name: 'Ghế gỗ kiểm thử' })).toBeVisible()

    // Aborting detail load by clicking back before getAsset resolves
    await user.click(screen.getByRole('button', { name: 'Quay lại danh sách' }))
    const pendingDetail = deferred<AssetDetailResponse>()
    getAssetMock.mockReturnValueOnce(pendingDetail.promise)
    await user.click(screen.getByRole('button', { name: 'Xem chi tiết Ghế gỗ kiểm thử' }))
    const detailSignal = getAssetMock.mock.calls.at(-1)![1]
    await user.click(screen.getByRole('button', { name: 'Quay lại danh sách' }))
    expect(detailSignal.aborted).toBe(true)
    await act(async () => {
      pendingDetail.resolve({ asset: makeResponse().results[0]!.asset, mock: true })
      await pendingDetail.promise
    })

    // Aborting detail client load before getAsset is invoked
    const pendingClient = deferred<AssetClient>()
    api.getAssetClient.mockReturnValueOnce(pendingClient.promise)
    await user.click(screen.getByRole('button', { name: 'Xem chi tiết Ghế gỗ kiểm thử' }))
    await user.click(screen.getByRole('button', { name: 'Quay lại danh sách' }))
    await act(async () => {
      pendingClient.resolve({ listAssets: listAssetsMock, getAsset: getAssetMock })
      await pendingClient.promise
    })

    // Late catalog response ignored when superseded by another request
    const slowCatalog = deferred<AssetListResponse>()
    listAssetsMock.mockReturnValueOnce(slowCatalog.promise)
    await user.click(screen.getByRole('button', { name: 'Danh sách asset' }))
    const catalogSignal = listAssetsMock.mock.calls.at(-1)![1]
    await user.click(screen.getByRole('button', { name: 'Xóa truy vấn' }))
    expect(catalogSignal.aborted).toBe(true)
    await act(async () => {
      slowCatalog.reject(new Error('late catalog error'))
      await slowCatalog.promise.catch(() => undefined)
    })
  })
})
