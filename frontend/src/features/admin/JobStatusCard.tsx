import './AdminStatusPage.css'
import type { JobKind, JobMetadata, JobStatus } from './types'

const statusLabels: Record<JobStatus, string> = {
  queued: 'Đang chờ',
  running: 'Đang chạy',
  succeeded: 'Thành công',
  failed: 'Thất bại',
}

const kindLabels: Record<JobKind, string> = {
  ingestion: 'Ingestion',
  indexing: 'Indexing',
}

function formatDate(value: string | null): string {
  if (value === null) return 'Chưa có'

  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function formatCount(value: number | null): string {
  return value === null ? 'Chưa xác định' : String(value)
}

export function JobStatusCard({ job }: { job: JobMetadata }) {
  const { progress, result, error } = job

  return (
    <article
      className={`admin-job-card admin-job-card--${job.status}`}
      aria-label={`Job ${job.job_id}`}
    >
      <div className="admin-job-card__header">
        <div>
          <p className="admin-job-card__type">{kindLabels[job.kind]}</p>
          <h2>{job.job_id}</h2>
        </div>
        <span className="admin-job-card__status">
          {statusLabels[job.status]}
        </span>
      </div>

      <dl className="admin-job-card__details">
        <div>
          <dt>Tạo lúc</dt>
          <dd>{formatDate(job.created_at)}</dd>
        </div>
        <div>
          <dt>Cập nhật</dt>
          <dd>{formatDate(job.updated_at)}</dd>
        </div>
        <div>
          <dt>Bắt đầu</dt>
          <dd>{formatDate(job.started_at)}</dd>
        </div>
        <div>
          <dt>Kết thúc</dt>
          <dd>{formatDate(job.finished_at)}</dd>
        </div>
      </dl>

      <div className="admin-job-card__progress">
        {progress.percent === null ? (
          <p>Chưa xác định tiến độ.</p>
        ) : (
          <>
            <div className="admin-job-card__progress-label">
              <span>Tiến độ xử lý</span>
              <strong>{progress.percent}%</strong>
            </div>
            <progress
              aria-label={`Tiến độ job ${job.job_id}`}
              value={progress.percent}
              max={100}
            >
              {progress.percent}%
            </progress>
          </>
        )}

        <p>
          Đã xử lý: {formatCount(progress.processed)}
          {' / '}
          {formatCount(progress.total)} asset.
        </p>
      </div>

      {result !== null && job.kind === 'ingestion' && (
        <div className="admin-job-card__result">
          <dl className="admin-job-card__details">
            <div>
              <dt>Đầu vào</dt>
              <dd>{formatCount(result.input_count)}</dd>
            </div>
            <div>
              <dt>Tải thành công</dt>
              <dd>{formatCount(result.succeeded)}</dd>
            </div>
            <div>
              <dt>Thất bại</dt>
              <dd>{formatCount(result.failed)}</dd>
            </div>
            <div>
              <dt>Tái sử dụng cache</dt>
              <dd>{formatCount(result.skipped)}</dd>
            </div>
          </dl>
          <p>
            Lưu trữ:{' '}
            {result.persistence === 'postgresql'
              ? 'PostgreSQL'
              : result.persistence === 'local_files_only'
                ? 'Chỉ file local'
                : 'Chưa xác định'}
          </p>
          <p>Kết quả ingestion chưa xác nhận asset đã sẵn sàng tìm kiếm.</p>
        </div>
      )}

      {result !== null && job.kind === 'indexing' && (
        <div className="admin-job-card__result">
          <p>Mã thoát runner: {formatCount(result.exit_code)}</p>
          <p>Kết quả indexing chưa xác nhận index đang phục vụ đã được đổi.</p>
        </div>
      )}

      {error !== null && (
        <p className="admin-job-card__error">
          {error.code}: {error.message}
        </p>
      )}
    </article>
  )
}