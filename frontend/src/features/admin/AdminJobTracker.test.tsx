import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ADMIN_TEST_KEY, REINDEX_JOB_ID, reindexJob } from '../../test/admin-reindex'
import { deferred } from '../../test/fixtures'
import { AdminJobTracker, JOB_POLL_INTERVAL_MS } from './AdminJobTracker'
import { getAdminJob } from './client'
import { AdminJobsError } from './errors'
import type { JobDetailResponse } from './types'

vi.mock('./client', () => ({ getAdminJob: vi.fn() }))
const getJob = vi.mocked(getAdminJob)
const detail = (status: Parameters<typeof reindexJob>[0]): JobDetailResponse => ({ job: reindexJob(status), mock: false })
beforeEach(() => { getJob.mockReset(); vi.useFakeTimers() })
const flush = async () => { await act(async () => { await Promise.resolve() }) }

describe('AdminJobTracker', () => {
  it('poll queued/running đến succeeded rồi dừng, không suy progress null thành 0', async () => {
    getJob.mockResolvedValueOnce(detail('queued')).mockResolvedValueOnce(detail('running')).mockResolvedValueOnce(detail('succeeded'))
    render(<AdminJobTracker jobId={REINDEX_JOB_ID} adminKey={ADMIN_TEST_KEY} />)
    expect(screen.getByRole('status')).toHaveTextContent('Đang tải job đã chọn')
    await flush()
    expect(screen.getByText('Chưa xác định tiến độ.')).toBeInTheDocument()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(getJob.mock.calls[0][1].adminKey).toBe(ADMIN_TEST_KEY)
    await act(async () => vi.advanceTimersByTimeAsync(JOB_POLL_INTERVAL_MS))
    expect(screen.getByRole('status')).toHaveTextContent('Tự cập nhật')
    await act(async () => vi.advanceTimersByTimeAsync(JOB_POLL_INTERVAL_MS))
    expect(screen.getByRole('status')).toHaveTextContent('Job đã hoàn thành')
    expect(screen.getByText('reindex-clip-fixture')).toBeInTheDocument()
    expect(screen.getByText('Đã kiểm chứng')).toBeInTheDocument()
    await act(async () => vi.advanceTimersByTimeAsync(JOB_POLL_INTERVAL_MS * 3))
    expect(getJob).toHaveBeenCalledTimes(3)
  })
  it('failed trong GET 200 là operation lỗi; không POST/retry operation', async () => {
    getJob.mockResolvedValue(detail('failed'))
    render(<AdminJobTracker jobId={REINDEX_JOB_ID} adminKey={ADMIN_TEST_KEY} />)
    await flush()
    expect(screen.getByRole('status')).toHaveTextContent('kết thúc với lỗi')
    expect(screen.getByText(/INDEXING_FAILED:/)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    await act(async () => vi.advanceTimersByTimeAsync(20000))
    expect(getJob).toHaveBeenCalledOnce()
  })
  it('dừng polling khi lỗi đọc; retry chỉ đọc lại cùng job', async () => {
    getJob.mockRejectedValueOnce(new AdminJobsError('network')).mockResolvedValueOnce(detail('succeeded'))
    render(<AdminJobTracker jobId={REINDEX_JOB_ID} adminKey={ADMIN_TEST_KEY} />)
    await flush()
    expect(screen.getByRole('alert')).toHaveTextContent('Không thể kết nối API')
    await act(async () => vi.advanceTimersByTimeAsync(20000))
    expect(getJob).toHaveBeenCalledOnce()
    fireEvent.click(screen.getByRole('button', { name: 'Thử tải lại job' }))
    await flush()
    expect(getJob.mock.calls[1][0]).toBe(REINDEX_JOB_ID)
    expect(screen.getByRole('status')).toHaveTextContent('Job đã hoàn thành')
  })
  it('403 yêu cầu kết nối lại, không tự polling', async () => {
    getJob.mockRejectedValueOnce(new AdminJobsError('access_denied'))
    render(<AdminJobTracker jobId={REINDEX_JOB_ID} adminKey={ADMIN_TEST_KEY} />)
    await flush()
    expect(screen.getByRole('alert')).toHaveTextContent('Khóa quản trị')
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
  it('ẩn exception không an toàn', async () => {
    getJob.mockRejectedValueOnce(new Error('private-detail'))
    render(<AdminJobTracker jobId={REINDEX_JOB_ID} adminKey={ADMIN_TEST_KEY} />)
    await flush()
    expect(screen.getByRole('alert')).toHaveTextContent('Không thể tải trạng thái job')
    expect(screen.queryByText(/private-detail/)).not.toBeInTheDocument()
  })
  it.each(['success', 'error'] as const)('bỏ response cũ sau unmount: %s', async outcome => {
    const pending = deferred<JobDetailResponse>()
    getJob.mockReturnValueOnce(pending.promise)
    const view = render(<AdminJobTracker jobId={REINDEX_JOB_ID} adminKey={ADMIN_TEST_KEY} />)
    view.unmount()
    expect(getJob.mock.calls[0][1].signal.aborted).toBe(true)
    await act(async () => {
      if (outcome === 'success') pending.resolve(detail('running'))
      else pending.reject(new AdminJobsError('network'))
      await pending.promise.catch(() => undefined)
    })
    await act(async () => vi.advanceTimersByTimeAsync(20000))
    expect(getJob).toHaveBeenCalledOnce()
  })
  it('dọn timer khi rời trang trong lúc chờ lần poll sau', async () => {
    getJob.mockResolvedValueOnce(detail('running'))
    const view = render(<AdminJobTracker jobId={REINDEX_JOB_ID} adminKey={ADMIN_TEST_KEY} />)
    await flush()
    view.unmount()
    await act(async () => vi.advanceTimersByTimeAsync(20000))
    expect(getJob).toHaveBeenCalledOnce()
  })
})
