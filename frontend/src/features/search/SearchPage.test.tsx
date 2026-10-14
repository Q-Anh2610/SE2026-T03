import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../../app/App'
import { deferred, makeRequest, makeResponse } from '../../test/fixtures'
import type { SearchClient, SearchResponse } from './types'

const api = vi.hoisted(() => ({ mockMode: true, getSearchClient: vi.fn() }))

vi.mock('../../lib/api/search', () => ({
  getSearchClient: api.getSearchClient,
  get isMockMode() { return api.mockMode },
}))

describe('search page behavior', () => {
  const searchMock = vi.fn<SearchClient['search']>()

  beforeEach(() => {
    api.mockMode = true
    api.getSearchClient.mockReset()
    searchMock.mockReset()
    searchMock.mockImplementation(async (request) => makeResponse(request.query))
    api.getSearchClient.mockResolvedValue({ search: searchMock })
  })

  it('starts with accessible labels, an idle invitation and an explicit mock notice', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Bắt đầu từ một mô tả' })).toBeVisible()
    expect(screen.getByLabelText('Bạn đang tìm asset nào?')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Tìm kiếm' })).toBeEnabled()
    expect(screen.getByLabelText('Chế độ dữ liệu')).toHaveTextContent('chưa kết nối API')
    expect(screen.getByRole('link', { name: 'Đến nội dung chính' })).toHaveAttribute('href', '#main')
    expect(api.getSearchClient).not.toHaveBeenCalled()
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
    await user.selectOptions(screen.getByLabelText('Số kết quả'), '6')
    await user.click(screen.getByRole('button', { name: 'Tìm kiếm' }))
    expect(screen.getByRole('button', { name: 'Đang tìm…' })).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent('Đang tìm kết quả cho “ghế gỗ”')
    expect(searchMock.mock.calls[0]?.[0]).toEqual(makeRequest('ghế gỗ', 6))
    expect(searchMock.mock.calls[0]?.[1].aborted).toBe(false)
    await act(async () => { pending.resolve(makeResponse()); await pending.promise })
    expect(screen.getByRole('heading', { name: 'Ghế gỗ kiểm thử' })).toBeVisible()
    expect(screen.getByRole('status')).toHaveTextContent('Có 1 kết quả cho “ghế gỗ”')
    expect(screen.getByRole('button', { name: 'Tìm kiếm' })).toBeEnabled()
    await user.click(screen.getByText('Thông tin phiên tìm kiếm'))
    expect(screen.getByText('test-query-01')).toBeVisible()
    expect(screen.getByText('test-event-01')).toBeVisible()
    expect(screen.getByText('test-model')).toBeVisible()
    expect(screen.getByText('test-index')).toBeVisible()
    expect(screen.getByText('test-config')).toBeVisible()
  })

  it('supports keyboard submission from the search button', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.tab()
    expect(screen.getByRole('link', { name: 'Đến nội dung chính' })).toHaveFocus()
    await user.click(screen.getByLabelText('Bạn đang tìm asset nào?'))
    await user.keyboard('chair')
    await user.tab()
    expect(screen.getByRole('button', { name: 'Tìm kiếm' })).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(await screen.findByRole('heading', { name: 'Ghế gỗ kiểm thử' })).toBeVisible()
    expect(searchMock.mock.calls[0]?.[0].query).toBe('chair')
  })

  it('submits a suggestion without requiring text entry', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'Đèn bàn' }))
    expect(await screen.findByRole('heading', { name: 'Ghế gỗ kiểm thử' })).toBeVisible()
    expect(screen.getByLabelText('Bạn đang tìm asset nào?')).toHaveValue('Đèn bàn')
    expect(searchMock.mock.calls[0]?.[0]).toEqual(makeRequest('Đèn bàn'))
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
  })

  it('retries the previous request and resets the simulated error scenario', async () => {
    searchMock.mockRejectedValueOnce(new Error('Sự cố kiểm thử'))
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByText('Thử trạng thái giao diện'))
    await user.selectOptions(screen.getByLabelText('Kịch bản lần tìm tiếp theo'), 'error')
    await user.type(screen.getByLabelText('Bạn đang tìm asset nào?'), 'ghế gỗ')
    await user.click(screen.getByRole('button', { name: 'Tìm kiếm' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Sự cố kiểm thử')
    expect(api.getSearchClient).toHaveBeenLastCalledWith('error')
    await user.clear(screen.getByLabelText('Bạn đang tìm asset nào?'))
    await user.type(screen.getByLabelText('Bạn đang tìm asset nào?'), 'query mới chưa gửi')
    await user.click(screen.getByRole('button', { name: 'Thử lại' }))
    expect(await screen.findByRole('heading', { name: 'Ghế gỗ kiểm thử' })).toBeVisible()
    expect(searchMock.mock.calls[1]?.[0]).toEqual(makeRequest())
    expect(api.getSearchClient).toHaveBeenLastCalledWith('success')
    expect(screen.getByLabelText('Kịch bản lần tìm tiếp theo')).toHaveValue('success')
  })

  it('keeps production errors visible without showing mock controls or results', async () => {
    api.mockMode = false
    searchMock.mockRejectedValue(new Error('API chưa sẵn sàng'))
    const user = userEvent.setup()
    render(<App />)
    expect(screen.queryByLabelText('Chế độ dữ liệu')).not.toBeInTheDocument()
    expect(screen.queryByText('Thử trạng thái giao diện')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Ghế gỗ' }))
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
    await user.click(screen.getByRole('button', { name: 'Ghế gỗ' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Không thể tìm kiếm. Hãy thử lại.')
    expect(screen.queryByText('untrusted failure details')).not.toBeInTheDocument()
  })

  it('cancels an older request and ignores its late successful response', async () => {
    const first = deferred<SearchResponse>()
    searchMock.mockReturnValueOnce(first.promise)
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'Ghế gỗ' }))
    const originalSignal = searchMock.mock.calls[0]![1]
    await user.click(screen.getByRole('button', { name: 'Thùng gỗ' }))
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
    await user.click(screen.getByRole('button', { name: 'Ghế gỗ' }))
    await user.click(screen.getByRole('button', { name: 'Thùng gỗ' }))
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
    await user.click(screen.getByRole('button', { name: 'Ghế gỗ' }))
    await user.click(screen.getByRole('button', { name: 'Đèn bàn' }))
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
    await user.click(screen.getByRole('button', { name: 'Ghế gỗ' }))
    const signal = searchMock.mock.calls[0]![1]
    unmount()
    expect(signal.aborted).toBe(true)
    await act(async () => { pending.resolve(makeResponse('Ghế gỗ')); await pending.promise })
  })
})
