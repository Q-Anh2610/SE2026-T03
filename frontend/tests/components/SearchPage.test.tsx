import { act, render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../../src/app/App'
import { createMockSearchResponse } from '../../src/features/search/mock'
import { deferred, makeResponse } from '../../src/test/fixtures'
import type { SearchClient, SearchResponse } from '../../src/features/search/types'

const api = vi.hoisted(() => ({ getSearchClient: vi.fn() }))
vi.mock('../../src/lib/api/search', () => ({ isMockMode: true, getSearchClient: api.getSearchClient }))
const searchMock = vi.fn<SearchClient['search']>()
beforeEach(() => {
  searchMock.mockReset()
  searchMock.mockImplementation(async (request) => createMockSearchResponse(request.query, request.limit))
  api.getSearchClient.mockReset().mockResolvedValue({ search: searchMock })
})
function cards() { return within(screen.getByRole('list', { name: 'Kết quả asset' })).getAllByRole('listitem') }
async function submit(user: ReturnType<typeof userEvent.setup>, query: string) {
  await user.type(screen.getByRole('searchbox'), `${query}{Enter}`)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Tìm kiếm' })).toBeEnabled())
}

describe('search UI after contract consolidation', () => {
  it('starts without usage instructions, demo badges or a search request', () => {
    render(<App />)
    expect(screen.queryByRole('heading', { name: 'Bắt đầu từ một mô tả' })).not.toBeInTheDocument()
    expect(screen.queryByText('Chế độ mẫu')).not.toBeInTheDocument()
    expect(screen.queryByText('Bản mẫu tuần 1')).not.toBeInTheDocument()
    expect(api.getSearchClient).not.toHaveBeenCalled()
  })
  it('labels the search box without a persistent usage hint', () => {
    render(<App />)
    expect(screen.getByRole('searchbox', { name: 'Bạn đang tìm asset nào?' })).not.toHaveAttribute('aria-describedby')
  })
  it('typing alone does not submit the query', async () => {
    render(<App />)
    await userEvent.setup().type(screen.getByRole('searchbox'), 'ghe go')
    expect(searchMock).not.toHaveBeenCalled()
  })
  it('submits an accentless query with Enter', async () => {
    render(<App />)
    await submit(userEvent.setup(), 'ghe go')
    expect(cards()).toHaveLength(1)
    expect(within(cards()[0]).getByRole('heading')).toHaveTextContent('Ghế gỗ đơn giản')
  })
  it('submits using the search button', async () => {
    const user = userEvent.setup(); render(<App />)
    await user.type(screen.getByRole('searchbox'), 'đèn')
    await user.click(screen.getByRole('button', { name: 'Tìm kiếm' }))
    expect(await screen.findByRole('heading', { name: 'Đèn bàn' })).toBeVisible()
    expect(cards()).toHaveLength(1)
  })
  it('removes suggestion and scenario controls from the interface', () => {
    render(<App />)
    expect(screen.queryByText('Thử với')).not.toBeInTheDocument()
    expect(screen.queryByText('Thử trạng thái giao diện')).not.toBeInTheDocument()
  })
  it('clears the active query and restores focus to the search field', async () => {
    const user = userEvent.setup(); render(<App />)
    await submit(user, 'lamp')
    await user.click(screen.getByRole('button', { name: 'Xóa truy vấn' }))
    expect(screen.getByRole('searchbox')).toHaveValue('')
    expect(screen.getByRole('searchbox')).toHaveFocus()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })
  it('filters by category and exposes the selected state', async () => {
    const user = userEvent.setup(); render(<App />)
    await submit(user, 'glb')
    expect(cards()).toHaveLength(6)
    const group = screen.getByRole('group', { name: 'Lọc danh mục trong trang' })
    const chair = within(group).getByRole('button', { name: 'Nội thất' })
    await user.click(chair)
    expect(chair).toHaveAttribute('aria-pressed', 'true')
    expect(cards()).toHaveLength(3)
    await user.click(within(group).getByRole('button', { name: 'Tất cả' }))
    expect(cards()).toHaveLength(6)
  })
  it('combines category and query, then resets both from empty state', async () => {
    const user = userEvent.setup(); render(<App />)
    await submit(user, 'glb')
    await user.click(screen.getByRole('button', { name: 'Nội thất' }))
    await user.clear(screen.getByRole('searchbox'))
    await submit(user, 'lamp')
    expect(screen.getByRole('heading', { name: 'Chưa có asset phù hợp' })).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Xóa tìm kiếm và bộ lọc' }))
    expect(screen.getByRole('searchbox')).toHaveFocus()
    expect(screen.queryByText(/Đang lọc:/)).not.toBeInTheDocument()
  })
  it('rejects empty input submission without requesting HTTP', async () => {
    render(<App />)
    await userEvent.setup().click(screen.getByRole('button', { name: 'Tìm kiếm' }))
    expect(screen.getByRole('alert')).toHaveTextContent('1 đến 500')
    expect(searchMock).not.toHaveBeenCalled()
  })
  it('renders HTML-like query as text without injecting markup', async () => {
    const response = makeResponse('<img src=x onerror=alert(1)>')
    searchMock.mockResolvedValueOnce(response)
    render(<App />)
    await submit(userEvent.setup(), response.query)
    expect(screen.getByRole('status')).toHaveTextContent(response.query)
    expect(document.querySelector('img')).toBeNull()
  })
  it('supports keyboard access to search submission', async () => {
    const user = userEvent.setup(); render(<App />)
    screen.getByRole('searchbox').focus()
    await user.type(screen.getByRole('searchbox'), 'lamp')
    await user.tab()
    expect(screen.getByRole('button', { name: 'Xóa truy vấn' })).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('button', { name: 'Tìm kiếm' })).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(await screen.findByRole('heading', { name: 'Đèn bàn' })).toBeVisible()
  })
  it('clearing the query preserves and identifies the active filter', async () => {
    const user = userEvent.setup(); render(<App />)
    await submit(user, 'glb')
    await user.click(screen.getByRole('button', { name: 'Nội thất' }))
    await user.click(screen.getByRole('button', { name: 'Xóa truy vấn' }))
    expect(screen.getByText(/chỉ trong trang đã nhận/)).toHaveTextContent('Nội thất')
    await user.click(screen.getByRole('button', { name: 'Xóa bộ lọc' }))
    expect(screen.getByRole('searchbox')).toHaveFocus()
    expect(screen.queryByText(/Đang lọc:/)).not.toBeInTheDocument()
  })
  it('clearing while loading aborts the request and ignores its late response', async () => {
    const pending = deferred<SearchResponse>(); searchMock.mockReturnValueOnce(pending.promise)
    const user = userEvent.setup(); render(<App />)
    await user.type(screen.getByRole('searchbox'), 'lamp{Enter}')
    await user.click(screen.getByRole('button', { name: 'Xóa truy vấn' }))
    expect(searchMock.mock.calls[0][1].aborted).toBe(true)
    await act(async () => { pending.resolve(makeResponse('lamp')); await pending.promise })
    expect(screen.queryByRole('heading', { name: 'Bắt đầu từ một mô tả' })).not.toBeInTheDocument()
  })
  it('allows null metadata with clear placeholders', async () => {
    const response = makeResponse('lamp')
    Object.assign(response.results[0].asset, { description: null, category: null })
    searchMock.mockResolvedValueOnce(response)
    render(<App />)
    await submit(userEvent.setup(), 'lamp')
    expect(screen.getAllByText('Chưa có thông tin')).toHaveLength(3)
    expect(screen.queryByRole('button', { name: 'null' })).not.toBeInTheDocument()
  })
})
