import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ADMIN_TEST_KEY, REINDEX_REQUEST_ID, reindexResponse } from '../../test/admin-reindex'
import { deferred } from '../../test/fixtures'
import { ReindexPanel } from './ReindexPanel'
import { ReindexError, requestReindex } from './reindex-client'

vi.mock('./reindex-client', async importOriginal => ({
  ...await importOriginal<typeof import('./reindex-client')>(), requestReindex: vi.fn(),
}))
const post = vi.mocked(requestReindex)
beforeEach(() => {
  post.mockReset()
  vi.spyOn(crypto, 'randomUUID').mockReturnValue(REINDEX_REQUEST_ID)
})
async function confirm() {
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Yêu cầu reindex' }))
  await user.click(screen.getByRole('button', { name: 'Xác nhận reindex' }))
}

describe('ReindexPanel', () => {
  it('chưa gửi khi mở, cho hủy xác nhận và khóa thao tác khi chưa xác thực', async () => {
    const user = userEvent.setup()
    const view = render(<ReindexPanel adminKey={ADMIN_TEST_KEY} disabled />)
    expect(screen.getByRole('button', { name: 'Yêu cầu reindex' })).toBeDisabled()
    view.rerender(<ReindexPanel adminKey={ADMIN_TEST_KEY} disabled={false} />)
    await user.click(screen.getByRole('button', { name: 'Yêu cầu reindex' }))
    expect(screen.getByRole('group', { name: 'Xác nhận reindex' })).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Hủy yêu cầu' }))
    expect(screen.queryByRole('group')).not.toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })
  it('gửi một lần, chặn double click và hiển thị liên kết job', async () => {
    const pending = deferred<ReturnType<typeof reindexResponse>>()
    post.mockReturnValueOnce(pending.promise)
    render(<ReindexPanel adminKey={ADMIN_TEST_KEY} disabled={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'Yêu cầu reindex' }))
    const button = screen.getByRole('button', { name: 'Xác nhận reindex' })
    // Both clicks arrive before React renders the loading state. The ref guard
    // must prevent the second POST even while the old button is still mounted.
    act(() => {
      fireEvent.click(button)
      fireEvent.click(button)
    })
    expect(post).toHaveBeenCalledOnce()
    expect(post.mock.calls[0][0]).toBe(REINDEX_REQUEST_ID)
    expect(post.mock.calls[0][1].adminKey).toBe(ADMIN_TEST_KEY)
    expect(screen.getByRole('status')).toHaveTextContent('Đang gửi')
    expect(screen.queryByRole('button', { name: 'Hủy yêu cầu' })).not.toBeInTheDocument()
    await act(async () => pending.resolve(reindexResponse()))
    expect(await screen.findByRole('link', { name: 'Theo dõi job này' })).toHaveAttribute('href', `#admin-status/job/${reindexResponse().job_id}`)
    expect(screen.getByRole('status')).toHaveTextContent('job chưa được xác nhận hoàn thành')
  })
  it('retry giữ nguyên UUID, không tự gửi lại và không lộ chi tiết exception', async () => {
    post.mockRejectedValueOnce(new ReindexError('network')).mockResolvedValueOnce(reindexResponse(true, 'failed'))
    render(<ReindexPanel adminKey={ADMIN_TEST_KEY} disabled={false} />)
    await confirm()
    expect(await screen.findByRole('alert')).toHaveTextContent('Chưa xác định API đã nhận')
    expect(screen.queryByRole('link', { name: 'Theo dõi job này' })).not.toBeInTheDocument()
    expect(post).toHaveBeenCalledOnce()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Gửi lại cùng yêu cầu' }))
    expect(await screen.findByRole('status')).toHaveTextContent('không chạy lại operation')
    expect(post.mock.calls[1][0]).toBe(post.mock.calls[0][0])
  })
  it('lượt mới cần UUID mới và xác nhận mới', async () => {
    post.mockResolvedValue(reindexResponse())
    render(<ReindexPanel adminKey={ADMIN_TEST_KEY} disabled={false} />)
    await confirm()
    await screen.findByRole('link', { name: 'Theo dõi job này' })
    const nextId = 'c0b674d2-1286-401f-b73b-72cae159fcad'
    vi.mocked(crypto.randomUUID).mockReturnValueOnce(nextId)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Chuẩn bị lượt mới' }))
    expect(post).toHaveBeenCalledOnce()
    await user.click(screen.getByRole('button', { name: 'Xác nhận reindex' }))
    expect(post.mock.calls[1][0]).toBe(nextId)
  })
  it('409 dẫn sang jobs/status và không tự POST lặp', async () => {
    post.mockRejectedValueOnce(new ReindexError('busy'))
    render(<ReindexPanel adminKey={ADMIN_TEST_KEY} disabled={false} />)
    await confirm()
    expect(await screen.findByRole('alert')).toHaveTextContent('Có lượt reindex khác')
    expect(screen.getByRole('link', { name: 'Xem danh sách jobs/status' })).toHaveAttribute('href', '#admin-status')
    expect(post).toHaveBeenCalledOnce()
  })
  it.each(['access_denied', 'unconfigured', 'unavailable', 'invalid', 'contract', 'server'] as const)('hiển thị lỗi %s, không báo thành công', async kind => {
    post.mockRejectedValueOnce(new ReindexError(kind))
    render(<ReindexPanel adminKey={ADMIN_TEST_KEY} disabled={false} />)
    await confirm()
    expect(await screen.findByRole('alert')).toHaveTextContent(new ReindexError(kind).message)
    expect(screen.queryByRole('link', { name: 'Theo dõi job này' })).not.toBeInTheDocument()
  })
  it('ẩn exception ngoài dự kiến', async () => {
    post.mockRejectedValueOnce(new Error('private-detail'))
    render(<ReindexPanel adminKey={ADMIN_TEST_KEY} disabled={false} />)
    await confirm()
    expect(await screen.findByRole('alert')).toHaveTextContent(new ReindexError('server').message)
    expect(screen.queryByText(/private-detail/)).not.toBeInTheDocument()
  })
  it('không gửi nếu không có secure random UUID', async () => {
    vi.mocked(crypto.randomUUID).mockImplementationOnce(() => { throw new Error('unavailable') })
    render(<ReindexPanel adminKey={ADMIN_TEST_KEY} disabled={false} />)
    await userEvent.setup().click(screen.getByRole('button', { name: 'Yêu cầu reindex' }))
    expect(screen.getByRole('alert')).toHaveTextContent('HTTPS hoặc localhost')
    expect(post).not.toHaveBeenCalled()
  })
  it.each(['success', 'error'] as const)('hủy request và bỏ response sau unmount: %s', async outcome => {
    const pending = deferred<ReturnType<typeof reindexResponse>>()
    post.mockReturnValueOnce(pending.promise)
    const view = render(<ReindexPanel adminKey={ADMIN_TEST_KEY} disabled={false} />)
    await confirm()
    view.unmount()
    expect(post.mock.calls[0][1].signal.aborted).toBe(true)
    await act(async () => {
      if (outcome === 'success') pending.resolve(reindexResponse())
      else pending.reject(new ReindexError('network'))
      await pending.promise.catch(() => undefined)
    })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
