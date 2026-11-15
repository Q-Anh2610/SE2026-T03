import { useEffect, useRef, useState } from 'react'
import { ReindexError, requestReindex, type ReindexResponse } from './reindex-client'

const statusLabels = { queued: 'Đang chờ', running: 'Đang chạy', succeeded: 'Thành công', failed: 'Thất bại' }

type State =
  | { phase: 'idle' }
  | { phase: 'confirm'; requestId: string }
  | { phase: 'sending'; requestId: string }
  | { phase: 'error'; requestId: string; error: ReindexError }
  | { phase: 'accepted'; response: ReindexResponse }

export function ReindexPanel({ adminKey, disabled }: { adminKey: string; disabled: boolean }) {
  const [state, setState] = useState<State>({ phase: 'idle' })
  const [creationError, setCreationError] = useState(false)
  const active = useRef<AbortController | null>(null)

  useEffect(() => () => active.current?.abort(), [])

  function prepare() {
    try {
      const requestId = crypto.randomUUID()
      setState({ phase: 'confirm', requestId })
      setCreationError(false)
    } catch {
      setCreationError(true)
    }
  }

  async function send(requestId: string) {
    if (active.current !== null) return
    const controller = new AbortController()
    active.current = controller
    setState({ phase: 'sending', requestId })
    try {
      const response = await requestReindex(requestId, { adminKey, signal: controller.signal })
      if (!controller.signal.aborted) setState({ phase: 'accepted', response })
    } catch (error) {
      if (!controller.signal.aborted) {
        setState({ phase: 'error', requestId, error: error instanceof ReindexError ? error : new ReindexError('server') })
      }
    } finally {
      // send() rejects a second request while this controller is active.
      active.current = null
    }
  }

  return (
    <section className="admin-reindex" aria-labelledby="reindex-title">
      <h2 id="reindex-title">Dựng index CLIP mới</h2>
      <p>Dựng index riêng cho 200 asset của snapshot home-interior-clear-200-v3. Index đang phục vụ tìm kiếm chưa được chuyển.</p>
      <p>Rời trang hoặc xóa khóa khỏi phiên không hủy job đã được backend nhận.</p>
      {creationError && <p role="alert">{new ReindexError('uuid').message}</p>}
      {state.phase === 'idle' && (
        <button type="button" disabled={disabled} onClick={prepare}>Yêu cầu reindex</button>
      )}
      {state.phase === 'confirm' && (
        <div role="group" aria-label="Xác nhận reindex">
          <p>Bạn xác nhận dựng một index CLIP mới từ bộ 200 asset đã chốt?</p>
          <div className="admin-status-page__actions">
            <button type="button" disabled={disabled} onClick={() => void send(state.requestId)}>Xác nhận reindex</button>
            <button type="button" onClick={() => setState({ phase: 'idle' })}>Hủy yêu cầu</button>
          </div>
        </div>
      )}
      {state.phase === 'sending' && <p role="status">Đang gửi yêu cầu reindex…</p>}
      {state.phase === 'error' && (
        <div>
          <p role="alert">{state.error.message}</p>
          {state.error.kind === 'busy' && (
            <a href="#admin-status">Xem danh sách jobs/status</a>
          )}
          <button type="button" disabled={disabled} onClick={() => void send(state.requestId)}>Gửi lại cùng yêu cầu</button>
        </div>
      )}
      {state.phase === 'accepted' && (
        <div>
          <p role="status">{state.response.reused ? 'API trả lại job đã có; không chạy lại operation.' : 'API đã nhận yêu cầu; job chưa được xác nhận hoàn thành.'}</p>
          <p>Job: {state.response.job_id}</p>
          <p>Trạng thái lúc nhận phản hồi: {statusLabels[state.response.status]}</p>
          <a href={`#admin-status/job/${state.response.job_id}`}>Theo dõi job này</a>
          <p>Lượt mới cần mã yêu cầu mới và xác nhận lại; backend sẽ từ chối nếu tài nguyên đang bận.</p>
          <button type="button" disabled={disabled} onClick={prepare}>Chuẩn bị lượt mới</button>
        </div>
      )}
    </section>
  )
}
