import './AdminStatusPage.css'
import { useEffect, useState } from 'react'
import {
  adminJobFixtures,
  type AdminJob,
  type JobStatus,
} from './fixtures'

export type AdminJobsLoader = () => Promise<AdminJob[]>
export type AdminStatusPageProps = { loadJobs?: AdminJobsLoader }

type AdminJobsState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; jobs: AdminJob[] }

const loadFixtureJobs: AdminJobsLoader = async () => adminJobFixtures

const statusLabels: Record<JobStatus, string> = {
  queued: 'Đang chờ',
  running: 'Đang chạy',
  succeeded: 'Thành công',
  failed: 'Thất bại',
}

const jobTypeLabels: Record<AdminJob['type'], string> = {
  ingestion: 'Ingestion',
  indexing: 'Indexing',
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function JobCard({ job }: { job: AdminJob }) {
  return (
    <article className={`admin-job-card admin-job-card--${job.status}`}>
      <div className="admin-job-card__header">
        <div>
          <p className="admin-job-card__type">{jobTypeLabels[job.type]}</p>
          <h2>{job.id}</h2>
        </div>
        <span className="admin-job-card__status">{statusLabels[job.status]}</span>
      </div>

      <dl className="admin-job-card__details">
        <div>
          <dt>Tạo lúc</dt>
          <dd>{formatDate(job.createdAt)}</dd>
        </div>
        <div>
          <dt>Cập nhật</dt>
          <dd>{formatDate(job.updatedAt)}</dd>
        </div>
      </dl>

      {job.status === 'running' && job.progress !== undefined && (
        <div className="admin-job-card__progress">
          <div className="admin-job-card__progress-label">
            <span>Tiến độ</span>
            <strong>{job.progress}%</strong>
          </div>
          <progress value={job.progress} max={100}>
            {job.progress}%
          </progress>
        </div>
      )}

      {job.result && <p className="admin-job-card__result">{job.result}</p>}
      {job.error && <p className="admin-job-card__error">{job.error}</p>}
    </article>
  )
}

export function AdminStatusPage({ loadJobs = loadFixtureJobs }: AdminStatusPageProps) {
  const [state, setState] = useState<AdminJobsState>({ status: 'loading' })
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    let cancelled = false

    Promise.resolve()
      .then(loadJobs)
      .then(
        (jobs) => {
          if (!cancelled) {
            setState({ status: 'success', jobs })
          }
        },
      )
      .catch(() => {
        if (!cancelled) {
          setState({ status: 'error' })
        }
      })

    return () => {
      cancelled = true
    }
  }, [loadJobs, retryCount])

  function retryLoadingJobs() {
    setState({ status: 'loading' })
    setRetryCount((count) => count + 1)
  }

  return (
    <section className="admin-status-page" aria-labelledby="admin-status-title">
      <div className="admin-status-page__intro">
        <p className="eyebrow">Khu vực quản trị</p>
        <h1 id="admin-status-title">Trạng thái job</h1>
        <p>Theo dõi tình trạng ingestion và indexing.</p>
        <p>
          Dữ liệu dưới đây là fixtures xem trước; trạng thái và tiến độ chỉ là ví dụ,
          không phải contract backend. API jobs/status chưa được nối.
        </p>
      </div>

      <div
        className="admin-status-page__list"
        aria-busy={state.status === 'loading'}
      >
        {state.status === 'loading' ? (
          <p className="admin-status-page__state" role="status">
            Đang tải trạng thái job…
          </p>
        ) : state.status === 'error' ? (
          <div className="admin-status-page__error" role="alert">
            <p>Không thể tải trạng thái job. Vui lòng thử lại.</p>
            <button type="button" onClick={retryLoadingJobs}>
              Thử lại
            </button>
          </div>
        ) : state.jobs.length === 0 ? (
          <p className="admin-status-page__state" role="status">
            Chưa có job nào để hiển thị.
          </p>
        ) : (
          state.jobs.map((job) => <JobCard key={job.id} job={job} />)
        )}
      </div>
    </section>
  )
}
