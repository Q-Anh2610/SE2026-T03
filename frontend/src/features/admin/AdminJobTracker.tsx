import { useEffect, useState } from 'react'
import { getAdminJob } from './client'
import { AdminJobsError } from './errors'
import { JobStatusCard } from './JobStatusCard'
import type { JobMetadata } from './types'

export const JOB_POLL_INTERVAL_MS = 3000

type State =
  | { phase: 'loading' }
  | { phase: 'loaded'; job: JobMetadata }
  | { phase: 'error'; error: AdminJobsError }

// The parent keys this component by session and job, discarding old requests/data.
export function AdminJobTracker({ jobId, adminKey }: { jobId: string; adminKey: string }) {
  const [state, setState] = useState<State>({ phase: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    async function load() {
      try {
        const { job } = await getAdminJob(jobId, { adminKey, signal: controller.signal })
        if (controller.signal.aborted) return
        setState({ phase: 'loaded', job })
        if (job.status === 'queued' || job.status === 'running') {
          timer = setTimeout(() => void load(), JOB_POLL_INTERVAL_MS)
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setState({ phase: 'error', error: error instanceof AdminJobsError ? error : new AdminJobsError('server') })
        }
      }
    }
    void load()
    return () => {
      controller.abort()
      clearTimeout(timer)
    }
  }, [jobId, adminKey, attempt])

  return (
    <section className="admin-job-tracker" aria-labelledby="tracked-job-title">
      <h2 id="tracked-job-title">Theo dõi job đã chọn</h2>
      <p>Job: {jobId}</p>
      <a href="#admin-status">Về danh sách jobs/status</a>
      {state.phase === 'loading' && <p role="status">Đang tải job đã chọn…</p>}
      {state.phase === 'error' && (
        <div>
          <p role="alert">{state.error.message}</p>
          {state.error.kind !== 'access_denied' && (
            <button type="button" onClick={() => { setState({ phase: 'loading' }); setAttempt(attempt + 1) }}>Thử tải lại job</button>
          )}
        </div>
      )}
      {state.phase === 'loaded' && (
        <>
          <JobStatusCard job={state.job} />
          <p role="status">{state.job.status === 'queued' || state.job.status === 'running'
            ? 'Tự cập nhật mỗi 3 giây khi job đang chờ hoặc đang chạy.'
            : state.job.status === 'failed' ? 'Job đã kết thúc với lỗi. Không tự chạy lại.' : 'Job đã hoàn thành. Index đang phục vụ chưa được chuyển.'}</p>
        </>
      )}
    </section>
  )
}
