import { useEffect, useState, type FormEvent } from 'react'
import './AdminStatusPage.css'
import { listAdminJobs } from './client'
import { AdminJobsError } from './errors'
import { JobStatusCard } from './JobStatusCard'
import type { JobKind, JobListResponse, JobStatus } from './types'

type JobsRequest = {
  adminKey: string
  page: number
  kind?: JobKind
  status?: JobStatus
}

type JobsState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; error: AdminJobsError; page: number }
  | { status: 'success'; data: JobListResponse }

export function LiveAdminStatusPage() {
  const [draftKey, setDraftKey] = useState('')
  const [request, setRequest] = useState<JobsRequest | null>(null)
  const [state, setState] = useState<JobsState>({ status: 'idle' })

  useEffect(() => {
    if (request === null) return

    const controller = new AbortController()

    listAdminJobs(
      {
        page: request.page,
        limit: 12,
        kind: request.kind,
        status: request.status,
    },
      {
        adminKey: request.adminKey,
        signal: controller.signal,
      },
    ).then(
      (data) => {
        if (!controller.signal.aborted) {
          setState({ status: 'success', data })
        }
      },
      (error: unknown) => {
        if (!controller.signal.aborted) {
          setState({
            status: 'error',
            page: request.page,
            error: error instanceof AdminJobsError
              ? error
              : new AdminJobsError('server'),
          })
        }
      },
    )

    return () => controller.abort()
  }, [request])

  function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!draftKey.trim()) return

    setState({ status: 'loading' })
    setRequest({ adminKey: draftKey, page: 1 })
    setDraftKey('')
  }

  function loadPage(page: number) {
    if (request === null) return

    setState({ status: 'loading' })
    setRequest({ ...request, page })
  }

  function disconnect() {
    setRequest(null)
    setDraftKey('')
    setState({ status: 'idle' })
  }
  function changeFilters(filters: {
    kind?: JobKind
    status?: JobStatus
    }) {
    if (request === null) return

    setState({ status: 'loading' })
    setRequest({ ...request, ...filters, page: 1 })
    }
  function changeKind(value: string) {
    if (value === '' || value === 'ingestion' || value === 'indexing') {
        changeFilters({ kind: value === '' ? undefined : value })
    }
    }

  function changeStatus(value: string) {
    if (
        value === ''
        || value === 'queued'
        || value === 'running'
        || value === 'succeeded'
        || value === 'failed'
    ) {
        changeFilters({ status: value === '' ? undefined : value })
    }
    }
  return (
    <section
      className="admin-status-page admin-status-page--live"
      aria-labelledby="live-admin-status-title"
    >
      <div className="admin-status-page__intro">
        <p className="eyebrow">Khu vực quản trị</p>
        <h1 id="live-admin-status-title">Trạng thái job</h1>
        <p>Theo dõi lịch sử ingestion và indexing từ API.</p>
      </div>

      <form className="admin-status-page__auth" onSubmit={connect}>
        <label htmlFor="admin-key">Khóa quản trị</label>
        <input
          id="admin-key"
          type="password"
          autoComplete="off"
          required
          value={draftKey}
          onChange={(event) => setDraftKey(event.target.value)}
        />
        <button type="submit">Kết nối</button>
      </form>

      {request !== null && (
        <div className="admin-status-page__filters">
            <div>
            <label htmlFor="job-kind">Loại job</label>
            <select
                id="job-kind"
                value={request.kind ?? ''}
                onChange={(event) => changeKind(event.target.value)}
            >
                <option value="">Tất cả loại</option>
                <option value="ingestion">Ingestion</option>
                <option value="indexing">Indexing</option>
            </select>
            </div>

            <div>
            <label htmlFor="job-status">Trạng thái</label>
            <select
                id="job-status"
                value={request.status ?? ''}
                onChange={(event) => changeStatus(event.target.value)}
            >
                <option value="">Tất cả trạng thái</option>
                <option value="queued">Đang chờ</option>
                <option value="running">Đang chạy</option>
                <option value="succeeded">Thành công</option>
                <option value="failed">Thất bại</option>
            </select>
            </div>
        </div>
        )}
      {request !== null && (
        <div className="admin-status-page__actions">
          <button
            type="button"
            disabled={state.status === 'loading'}
            onClick={() => loadPage(request.page)}
          >
            Tải lại
          </button>
          <button type="button" onClick={disconnect}>
            Xóa khóa khỏi phiên
          </button>
        </div>
      )}

      <div
        className="admin-status-page__list"
        aria-busy={state.status === 'loading'}
      >
        {state.status === 'idle' && (
          <p className="admin-status-page__state">
            Nhập khóa quản trị để tải trạng thái job.
          </p>
        )}

        {state.status === 'loading' && (
          <p className="admin-status-page__state" role="status">
            Đang tải trạng thái job…
          </p>
        )}

        {state.status === 'error' && (
          <div className="admin-status-page__error" role="alert">
            <p>{state.error.message}</p>
            {state.error.kind === 'access_denied' ? (
              <p>Nhập lại khóa và nhấn Kết nối.</p>
            ) : (
              <button
                type="button"
                onClick={() => loadPage(state.page)}
              >
                Thử lại
              </button>
            )}
          </div>
        )}

        {state.status === 'success' && (
          <>
            {state.data.items.length === 0 ? (
              <p className="admin-status-page__state" role="status">
                {state.data.pagination.total === 0
                  ? (request?.kind || request?.status
                        ? 'Không có job khớp bộ lọc.'
                        : 'Chưa có job nào để hiển thị.')
                  : 'Trang này không có job. Hãy quay về trang trước.'}
              </p>
            ) : (
              state.data.items.map((job) => (
                <JobStatusCard key={job.job_id} job={job} />
              ))
            )}

            <nav
            className="admin-status-page__pagination"
            aria-label="Phân trang jobs"
            >
              <button
                type="button"
                disabled={state.data.pagination.page <= 1}
                onClick={() => loadPage(state.data.pagination.page - 1)}
              >
                Trang trước
              </button>
              <span>
                {' '}Trang {state.data.pagination.page}
                {' · '}{state.data.pagination.total} job{' '}
              </span>
              <button
                type="button"
                disabled={!state.data.pagination.has_next}
                onClick={() => loadPage(state.data.pagination.page + 1)}
              >
                Trang sau
              </button>
            </nav>
          </>
        )}
      </div>
    </section>
  )
}
