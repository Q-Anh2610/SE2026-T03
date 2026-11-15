import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../../app/App'
import { ADMIN_TEST_KEY, REINDEX_JOB_ID, reindexJob, reindexResponse } from '../../test/admin-reindex'
import { deferred } from '../../test/fixtures'

const empty = { items: [], pagination: { page: 1, limit: 12, total: 0, pages: 0, has_next: false }, mock: false }
const fetchMock = vi.fn<typeof fetch>()
beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
  window.location.hash = '#admin-status'
})
afterEach(() => { window.location.hash = '' })
async function connect() {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Khóa quản trị'), ADMIN_TEST_KEY)
  await user.click(screen.getByRole('button', { name: 'Kết nối' }))
  await screen.findByText('Chưa có job nào để hiển thị.')
  return user
}

describe('Admin reindex routing and session', () => {
  it('đi xuyên UI/HTTP/validator, theo dõi đúng UUID và giữ phiên khi điều hướng', async () => {
    fetchMock.mockImplementation(async (url, init) => {
      expect(init?.headers).toMatchObject({ 'X-Admin-Key': ADMIN_TEST_KEY })
      if (String(url).includes('/reindex')) return Response.json(reindexResponse(), { status: 202 })
      if (String(url).includes(`/jobs/${REINDEX_JOB_ID}`)) return Response.json({ job: reindexJob('succeeded'), mock: false })
      return Response.json(empty)
    })
    render(<App />)
    const user = await connect()
    await user.click(screen.getByRole('button', { name: 'Yêu cầu reindex' }))
    await user.click(screen.getByRole('button', { name: 'Xác nhận reindex' }))
    const link = await screen.findByRole('link', { name: 'Theo dõi job này' })
    await user.click(link)
    await waitFor(() => expect(window.location.hash).toBe(`#admin-status/job/${REINDEX_JOB_ID}`))
    // Explicit event also works if the test DOM hasn't dispatched hashchange yet.
    await act(async () => window.dispatchEvent(new Event('hashchange')))
    expect(await screen.findByText('reindex-clip-fixture')).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
    await user.click(screen.getByRole('link', { name: 'Về danh sách jobs/status' }))
    await act(async () => window.dispatchEvent(new Event('hashchange')))
    await waitFor(() => expect(screen.queryByRole('heading', { name: 'Theo dõi job đã chọn' })).not.toBeInTheDocument())
    expect(screen.getByRole('link', { name: 'Theo dõi job này' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Xóa khóa khỏi phiên' }))
    expect(screen.queryByRole('heading', { name: 'Dựng index CLIP mới' })).not.toBeInTheDocument()
    expect(JSON.stringify({ ...localStorage, ...sessionStorage })).not.toContain(ADMIN_TEST_KEY)
  })
  it('bookmark chỉ tải chi tiết sau khi nhập khóa; reset hủy GET và bỏ kết quả cũ', async () => {
    window.location.hash = `#admin-status/job/${REINDEX_JOB_ID}`
    const pending = deferred<Response>()
    fetchMock.mockImplementation(url => String(url).includes(`/jobs/${REINDEX_JOB_ID}`)
      ? pending.promise : Promise.resolve(Response.json(empty)))
    render(<App />)
    expect(fetchMock).not.toHaveBeenCalled()
    const user = await connect()
    await screen.findByText('Đang tải job đã chọn…')
    const detailRequest = fetchMock.mock.calls.find(([url]) => String(url).includes(`/jobs/${REINDEX_JOB_ID}`))
    await user.click(screen.getByRole('button', { name: 'Xóa khóa khỏi phiên' }))
    expect(detailRequest?.[1]?.signal?.aborted).toBe(true)
    await act(async () => pending.resolve(Response.json({ job: reindexJob('succeeded'), mock: false })))
    expect(screen.queryByText('reindex-clip-fixture')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Theo dõi job đã chọn' })).not.toBeInTheDocument()
  })
})
