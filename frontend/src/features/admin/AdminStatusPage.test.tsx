import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AdminStatusPage, type AdminJobsLoader } from './AdminStatusPage'
import { adminJobFixtures, type AdminJob } from './fixtures'

function createDeferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })

  return { promise, resolve, reject }
}

describe('AdminStatusPage', () => {
  it('renders job statuses and progress returned by the loader', async () => {
    const loadJobs = vi.fn<AdminJobsLoader>().mockResolvedValue(adminJobFixtures)

    render(<AdminStatusPage loadJobs={loadJobs} />)

    expect(await screen.findByText('Đang chờ')).toBeInTheDocument()
    expect(screen.getByText('Đang chạy')).toBeInTheDocument()
    expect(screen.getByText('Thành công')).toBeInTheDocument()
    expect(screen.getByText('Thất bại')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveValue(62)
  })

  it('shows loading while jobs are being fetched', async () => {
    const deferred = createDeferred<AdminJob[]>()
    const loadJobs = vi.fn<AdminJobsLoader>(() => deferred.promise)

    render(<AdminStatusPage loadJobs={loadJobs} />)

    expect(screen.getByRole('status')).toHaveTextContent('Đang tải trạng thái job')
    expect(screen.getByRole('status').closest('[aria-busy="true"]')).not.toBeNull()
    await waitFor(() => expect(loadJobs).toHaveBeenCalledOnce())
  })

  it('shows an empty state when the loader returns no jobs', async () => {
    const loadJobs = vi.fn<AdminJobsLoader>().mockResolvedValue([])

    render(<AdminStatusPage loadJobs={loadJobs} />)

    expect(await screen.findByRole('status')).toHaveTextContent('Chưa có job nào để hiển thị.')
  })

  it('does not show progress when a running job has no progress value', async () => {
    const jobWithoutProgress: AdminJob = {
      ...adminJobFixtures[1],
      progress: undefined,
    }
    const loadJobs = vi.fn<AdminJobsLoader>().mockResolvedValue([jobWithoutProgress])

    render(<AdminStatusPage loadJobs={loadJobs} />)

    expect(await screen.findByText('job-indexing-002')).toBeInTheDocument()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })

  it('shows an error and retries the request', async () => {
    const user = userEvent.setup()
    const deferred = createDeferred<AdminJob[]>()
    const loadJobs = vi.fn<AdminJobsLoader>()
      .mockRejectedValueOnce(new Error('API unavailable'))
      .mockReturnValueOnce(deferred.promise)

    render(<AdminStatusPage loadJobs={loadJobs} />)

    expect(screen.getByText(/trạng thái và tiến độ chỉ là ví dụ, không phải contract backend/i)).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Không thể tải trạng thái job. Vui lòng thử lại.',
    )
    expect(screen.queryByText('job-ingestion-001')).not.toBeInTheDocument()
    expect(screen.queryByText('job-indexing-002')).not.toBeInTheDocument()
    expect(screen.queryByText('Thành công')).not.toBeInTheDocument()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Thử lại' }))

    expect(screen.getByRole('status')).toHaveTextContent('Đang tải trạng thái job')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    deferred.resolve(adminJobFixtures)

    expect(await screen.findByText('job-ingestion-001')).toBeInTheDocument()
    await waitFor(() => expect(loadJobs).toHaveBeenCalledTimes(2))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('ignores a rejected request after the page unmounts', async () => {
    const deferred = createDeferred<AdminJob[]>()
    const loadJobs = vi.fn<AdminJobsLoader>(() => deferred.promise)
    const { unmount } = render(<AdminStatusPage loadJobs={loadJobs} />)

    await waitFor(() => expect(loadJobs).toHaveBeenCalledOnce())
    unmount()

    await act(async () => {
      deferred.reject(new Error('Request finished after unmount'))
      await deferred.promise.catch(() => undefined)
    })
  })
})
