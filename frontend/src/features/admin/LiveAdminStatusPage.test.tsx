import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { listAdminJobs } from './client'
import { AdminJobsError } from './errors'
import { LiveAdminStatusPage } from './LiveAdminStatusPage'
import type { JobListResponse, JobMetadata } from './types'

vi.mock('./client', () => ({
  listAdminJobs: vi.fn(),
}))

const loadJobs = vi.mocked(listAdminJobs)
const KEY = 'test-admin-key-not-a-real-secret'

function makeJob(index: number): JobMetadata {
  return {
    job_id: `a0b674d2-1286-401f-b73b-${String(index + 1).padStart(12, '0')}`,
    kind: 'ingestion',
    runner: 'ingestion.run_batch',
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
}

function makeResponse(page = 1, total = 0): JobListResponse {
  const limit = 12
  const offset = (page - 1) * limit
  const count = Math.min(limit, Math.max(0, total - offset))
  const pages = Math.ceil(total / limit)

  return {
    items: Array.from({ length: count }, (_, i) => makeJob(offset + i)),
    pagination: {
      page,
      limit,
      total,
      pages,
      has_next: page < pages,
    },
    mock: false,
  }
}

async function connect(
  user: ReturnType<typeof userEvent.setup>,
  key = KEY,
) {
  await user.type(screen.getByLabelText('Khóa quản trị'), key)
  await user.click(screen.getByRole('button', { name: 'Kết nối' }))
}

beforeEach(() => {
  loadJobs.mockReset()
})

function createDeferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void

  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })

  return { promise, resolve, reject }
}

describe('LiveAdminStatusPage', () => {
  it('retries the failed page rather than falling back to page 1', async () => {
    const user = userEvent.setup()
    loadJobs
      .mockResolvedValueOnce(makeResponse(1, 13))
      .mockRejectedValueOnce(new AdminJobsError('network'))
      .mockResolvedValueOnce(makeResponse(2, 13))

    render(<LiveAdminStatusPage />)
    await connect(user)
    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(12))
    await user.click(screen.getByRole('button', { name: 'Trang sau' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Không thể kết nối API.')

    await user.click(screen.getByRole('button', { name: 'Thử lại' }))

    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(1))
    expect(loadJobs.mock.calls[2][0]).toMatchObject({ page: 2, limit: 12 })
    expect(loadJobs.mock.calls[2][1].adminKey).toBe(KEY)
    expect(screen.getByText(/Trang 2/)).toBeInTheDocument()
  })

  it('keeps a status-only filter when retrying a failed request', async () => {
    const user = userEvent.setup()
    loadJobs
      .mockResolvedValueOnce(makeResponse())
      .mockRejectedValueOnce(new AdminJobsError('network'))
      .mockResolvedValueOnce(makeResponse())

    render(<LiveAdminStatusPage />)
    await connect(user)
    await screen.findByText('Chưa có job nào để hiển thị.')
    await user.selectOptions(screen.getByLabelText('Trạng thái'), 'failed')
    expect(await screen.findByRole('alert')).toHaveTextContent('Không thể kết nối API.')
    await user.click(screen.getByRole('button', { name: 'Thử lại' }))

    expect(await screen.findByText('Không có job khớp bộ lọc.')).toBeInTheDocument()
    expect(loadJobs.mock.calls[2][0]).toEqual({
      page: 1, limit: 12, kind: undefined, status: 'failed',
    })
    expect(loadJobs.mock.calls[2][1].adminKey).toBe(KEY)
  })

  it.each(['Loại job', 'Trạng thái'])(
    'ignores an unsupported value inserted into the %s control',
    async (label) => {
      const user = userEvent.setup()
      loadJobs.mockResolvedValue(makeResponse())
      render(<LiveAdminStatusPage />)
      await connect(user)
      await screen.findByText('Chưa có job nào để hiển thị.')

      const select = screen.getByLabelText<HTMLSelectElement>(label)
      const invalidOption = document.createElement('option')
      invalidOption.value = 'unsupported'
      select.append(invalidOption)
      fireEvent.change(select, { target: { value: 'unsupported' } })

      expect(loadJobs).toHaveBeenCalledTimes(1)
      expect(screen.getByText('Chưa có job nào để hiển thị.')).toBeInTheDocument()
    },
  )

  it.each(['success', 'error'] as const)(
    'does not restore jobs or errors after clearing a pending session: %s',
    async (outcome) => {
      const user = userEvent.setup()
      const pending = createDeferred<JobListResponse>()
      loadJobs.mockReturnValueOnce(pending.promise)
      render(<LiveAdminStatusPage />)
      await connect(user)
      await waitFor(() => expect(loadJobs).toHaveBeenCalledOnce())
      const signal = loadJobs.mock.calls[0][1].signal

      await user.click(screen.getByRole('button', { name: 'Xóa khóa khỏi phiên' }))
      expect(signal.aborted).toBe(true)
      await act(async () => {
        if (outcome === 'success') pending.resolve(makeResponse(1, 1))
        else pending.reject(new AdminJobsError('network'))
        await pending.promise.catch(() => undefined)
      })

      expect(screen.getByText('Nhập khóa quản trị để tải trạng thái job.')).toBeInTheDocument()
      expect(screen.queryByRole('article')).not.toBeInTheDocument()
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    },
  )

  it('chỉ tải sau khi nhập khóa, hiển thị loading/empty và xóa phiên', async () => {
    const user = userEvent.setup()
    let resolve!: (value: JobListResponse) => void

    loadJobs.mockImplementationOnce(() => new Promise((done) => {
      resolve = done
    }))

    render(<LiveAdminStatusPage />)

    expect(loadJobs).not.toHaveBeenCalled()
    expect(
      screen.getByText('Nhập khóa quản trị để tải trạng thái job.'),
    ).toBeInTheDocument()

    await connect(user)

    expect(screen.getByRole('status')).toHaveTextContent(
      'Đang tải trạng thái job',
    )
    expect(screen.getByLabelText('Khóa quản trị')).toHaveValue('')

    await act(async () => {
      resolve(makeResponse())
    })

    expect(await screen.findByText(
      'Chưa có job nào để hiển thị.',
    )).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Trang trước' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Trang sau' })).toBeDisabled()

    const signal = loadJobs.mock.calls[0][1].signal

    await user.click(screen.getByRole('button', {
      name: 'Xóa khóa khỏi phiên',
    }))

    expect(signal.aborted).toBe(true)
    expect(screen.getByText(
      'Nhập khóa quản trị để tải trạng thái job.',
    )).toBeInTheDocument()
    expect(screen.queryByRole('navigation', {
      name: 'Phân trang jobs',
    })).not.toBeInTheDocument()
  })

  it('hiển thị lỗi tải và retry bằng khóa hiện tại', async () => {
    const user = userEvent.setup()

    loadJobs
      .mockRejectedValueOnce(new AdminJobsError('network'))
      .mockResolvedValueOnce(makeResponse())

    render(<LiveAdminStatusPage />)
    await connect(user)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Không thể kết nối API.',
    )
    expect(screen.queryByRole('article')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Thử lại' }))

    expect(await screen.findByText(
      'Chưa có job nào để hiển thị.',
    )).toBeInTheDocument()
    expect(loadJobs).toHaveBeenCalledTimes(2)
    expect(loadJobs.mock.calls[1][1].adminKey).toBe(KEY)
  })

  it('không tự retry khóa sai và cho phép nhập khóa khác', async () => {
    const user = userEvent.setup()

    loadJobs
      .mockRejectedValueOnce(new AdminJobsError('access_denied', 403))
      .mockResolvedValueOnce(makeResponse())

    render(<LiveAdminStatusPage />)
    await connect(user, 'wrong-test-key')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Khóa quản trị thiếu hoặc không đúng.',
    )
    expect(screen.queryByRole('button', {
      name: 'Thử lại',
    })).not.toBeInTheDocument()
    expect(loadJobs).toHaveBeenCalledTimes(1)

    await connect(user)

    expect(await screen.findByText(
      'Chưa có job nào để hiển thị.',
    )).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(loadJobs.mock.calls[1][1].adminKey).toBe(KEY)
  })

  it('chuyển trang, đổi lọc về trang 1 và tải lại giữ bộ lọc', async () => {
    const user = userEvent.setup()

    loadJobs
      .mockResolvedValueOnce(makeResponse(1, 13))
      .mockResolvedValueOnce(makeResponse(2, 13))
      .mockResolvedValueOnce(makeResponse())
      .mockResolvedValueOnce(makeResponse())

    render(<LiveAdminStatusPage />)
    await connect(user)

    await waitFor(() => {
      expect(screen.getAllByRole('article')).toHaveLength(12)
    })

    await user.click(screen.getByRole('button', { name: 'Trang sau' }))

    await waitFor(() => {
      expect(screen.getAllByRole('article')).toHaveLength(1)
    })
    expect(loadJobs.mock.calls[1][0]).toMatchObject({ page: 2 })
    expect(screen.getByRole('button', { name: 'Trang sau' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Trang trước' })).toBeEnabled()

    await user.selectOptions(screen.getByLabelText('Loại job'), 'indexing')

    expect(await screen.findByText(
      'Không có job khớp bộ lọc.',
    )).toBeInTheDocument()
    expect(loadJobs.mock.calls[2][0]).toMatchObject({
      page: 1,
      kind: 'indexing',
    })

    await user.click(screen.getByRole('button', { name: 'Tải lại' }))

    await waitFor(() => expect(loadJobs).toHaveBeenCalledTimes(4))
    expect(loadJobs.mock.calls[3][0]).toMatchObject({
      page: 1,
      kind: 'indexing',
    })
    expect(screen.getByLabelText('Loại job')).toHaveValue('indexing')

    await screen.findByText('Không có job khớp bộ lọc.')
  })
  it.each(['success', 'error'] as const)(
    'bỏ qua response cũ đến muộn: %s',
    async (outcome) => {
        const user = userEvent.setup()
        const oldRequest = createDeferred<JobListResponse>()

        loadJobs
        .mockReturnValueOnce(oldRequest.promise)
        .mockResolvedValueOnce(makeResponse())

        render(<LiveAdminStatusPage />)
        await connect(user)

        await waitFor(() => expect(loadJobs).toHaveBeenCalledTimes(1))
        const oldSignal = loadJobs.mock.calls[0][1].signal

        await user.selectOptions(
        screen.getByLabelText('Loại job'),
        'indexing',
        )

        expect(await screen.findByText(
        'Không có job khớp bộ lọc.',
        )).toBeInTheDocument()
        expect(oldSignal.aborted).toBe(true)

        await act(async () => {
        if (outcome === 'success') {
            oldRequest.resolve(makeResponse(1, 1))
        } else {
            oldRequest.reject(new AdminJobsError('network'))
        }
        await oldRequest.promise.catch(() => undefined)
        })

        expect(screen.getByText(
        'Không có job khớp bộ lọc.',
        )).toBeInTheDocument()
        expect(screen.queryByRole('article')).not.toBeInTheDocument()
        expect(screen.queryByRole('alert')).not.toBeInTheDocument()
        expect(screen.getByLabelText('Loại job')).toHaveValue('indexing')
    },
    )

    it('hủy request khi unmount và bỏ qua lỗi đến sau đó', async () => {
    const user = userEvent.setup()
    const pending = createDeferred<JobListResponse>()

    loadJobs.mockReturnValueOnce(pending.promise)

    const { unmount } = render(<LiveAdminStatusPage />)
    await connect(user)

    await waitFor(() => expect(loadJobs).toHaveBeenCalledTimes(1))
    const signal = loadJobs.mock.calls[0][1].signal

    unmount()
    expect(signal.aborted).toBe(true)

    await act(async () => {
        pending.reject(new AdminJobsError('network'))
        await pending.promise.catch(() => undefined)
    })
    })
    it.each(['queued', 'running', 'succeeded', 'failed'] as const)(
    'kết hợp trạng thái %s với loại job và xóa từng bộ lọc',
    async (status) => {
      const user = userEvent.setup()
      loadJobs.mockResolvedValue(makeResponse())

      render(<LiveAdminStatusPage />)
      await connect(user)

      await screen.findByText('Chưa có job nào để hiển thị.')

      await user.selectOptions(
        screen.getByLabelText('Loại job'),
        'ingestion',
      )

      await waitFor(() => expect(loadJobs).toHaveBeenCalledTimes(2))

      await user.selectOptions(
        screen.getByLabelText('Trạng thái'),
        status,
      )

      await waitFor(() => expect(loadJobs).toHaveBeenCalledTimes(3))
      expect(loadJobs.mock.calls[2][0]).toMatchObject({
        page: 1,
        kind: 'ingestion',
        status,
      })
      expect(await screen.findByText(
        'Không có job khớp bộ lọc.',
      )).toBeInTheDocument()

      await user.selectOptions(screen.getByLabelText('Trạng thái'), '')

      await waitFor(() => expect(loadJobs).toHaveBeenCalledTimes(4))
      expect(loadJobs.mock.calls[3][0]).toMatchObject({
        page: 1,
        kind: 'ingestion',
        status: undefined,
      })

      await user.selectOptions(screen.getByLabelText('Loại job'), '')

      await waitFor(() => expect(loadJobs).toHaveBeenCalledTimes(5))
      expect(loadJobs.mock.calls[4][0]).toMatchObject({
        page: 1,
        kind: undefined,
        status: undefined,
      })
      expect(await screen.findByText(
        'Chưa có job nào để hiển thị.',
      )).toBeInTheDocument()
    },
  )

  it('cho phép quay lại khi trang hiện tại rỗng do total giảm', async () => {
    const user = userEvent.setup()

    loadJobs
      .mockResolvedValueOnce(makeResponse(1, 13))
      .mockResolvedValueOnce(makeResponse(2, 1))
      .mockResolvedValueOnce(makeResponse(1, 1))

    render(<LiveAdminStatusPage />)
    await connect(user)

    await waitFor(() => {
      expect(screen.getAllByRole('article')).toHaveLength(12)
    })

    await user.click(screen.getByRole('button', { name: 'Trang sau' }))

    expect(await screen.findByText(
      'Trang này không có job. Hãy quay về trang trước.',
    )).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Trang trước' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Trang sau' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Trang trước' }))

    await waitFor(() => {
      expect(screen.getAllByRole('article')).toHaveLength(1)
    })
    expect(loadJobs.mock.calls[2][0]).toMatchObject({ page: 1 })
  })

  it('hiển thị thông báo an toàn khi client ném lỗi ngoài dự kiến', async () => {
    const user = userEvent.setup()
    loadJobs.mockRejectedValueOnce(new Error('private-internal-detail'))

    render(<LiveAdminStatusPage />)
    await connect(user)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Không thể tải trạng thái job. Vui lòng thử lại.',
    )
    expect(screen.queryByText(/private-internal-detail/)).not.toBeInTheDocument()
  })

  it('không gửi request khi khóa chỉ chứa khoảng trắng', async () => {
    const user = userEvent.setup()
    render(<LiveAdminStatusPage />)

    await user.type(screen.getByLabelText('Khóa quản trị'), '   ')
    await user.click(screen.getByRole('button', { name: 'Kết nối' }))

    expect(loadJobs).not.toHaveBeenCalled()
    expect(screen.getByText(
      'Nhập khóa quản trị để tải trạng thái job.',
    )).toBeInTheDocument()
  })
})
