import './AdminStatusPage.css'
import { useState } from 'react'
import {
  adminJobFixtures,
  emptyAdminJobFixtures,
  type AdminJob,
  type JobStatus,
} from './fixtures'

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

export function AdminStatusPage() {
    const [showEmptyState, setShowEmptyState] = useState(false)
    const jobs = showEmptyState ? emptyAdminJobFixtures : adminJobFixtures
    return (
    <section className="admin-status-page" aria-labelledby="admin-status-title">
      <div className="admin-status-page__intro">
        <button
            type="button"
            onClick={() => setShowEmptyState((current) => !current)}
            >
            {showEmptyState ? 'Xem các job mẫu' : 'Xem trạng thái danh sách rỗng'}
            </button>
        <p className="eyebrow">Khu vực quản trị · Dữ liệu mẫu</p>
        <h1 id="admin-status-title">Trạng thái job</h1>
        <p>
          Màn hình review dùng fixtures cục bộ, chưa kết nối status API thật.
        </p>
      </div>

      <div className="admin-status-page__list">
        {jobs.length === 0 ? (
          <p role="status">Chưa có job nào để hiển thị.</p>
        ) : (
          jobs.map((job) => <JobCard key={job.id} job={job} />)
        )}
      </div>
    </section>
  )
}