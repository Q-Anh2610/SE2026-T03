import { useEffect, useRef, useState } from 'react'
import { FeedbackApiError, sendFeedback } from './feedback-client'
import { notifyBusinessEvent } from './business-notification'

export function Feedback({ eventId, assetId, mock }: { eventId: string; assetId: string; mock: boolean }) {
  const [state, setState] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState('')
  const controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), [])
  async function send(relevance: boolean) {
    controller.current?.abort()
    const current = new AbortController()
    controller.current = current
    setState('loading')
    try {
      await sendFeedback(eventId, assetId, relevance, mock, current.signal)
      if (!current.signal.aborted) {
        setState('success')
        if (!mock) {
          try { notifyBusinessEvent('Đã lưu đánh giá', 'Phản hồi của bạn đã được lưu thành công.') }
          catch { /* Feedback is committed; notification failure cannot undo it. */ }
        }
      }
    } catch (error) {
      if (!current.signal.aborted) {
        const code = await readErrorCode(error)
        setErrorMessage(error instanceof FeedbackApiError && !error.response ? error.message
          : code === 'SEARCH_EVENT_RESULTS_UNAVAILABLE'
          ? 'Lượt tìm kiếm cũ chưa lưu danh sách kết quả. Hãy tìm lại rồi gửi đánh giá.'
          : code === 'EVENT_ASSET_MISMATCH' || code === 'ASSET_NOT_FOUND'
            ? 'Asset không thuộc lượt tìm kiếm này. Hãy tìm lại trước khi đánh giá.'
            : code === 'SEARCH_EVENT_NOT_FOUND'
              ? 'Không tìm thấy lượt tìm kiếm. Hãy tìm lại rồi thử đánh giá.'
              : 'Chưa gửi được đánh giá. Kiểm tra kết nối rồi thử lại.')
        setState('error')
      }
    }
  }
  return <fieldset aria-label="Đánh giá kết quả" disabled={state === 'loading' || state === 'success'}>
    <legend>Kết quả có phù hợp không?</legend>
    <button type="button" onClick={() => { void send(true) }}>Phù hợp</button>
    <button type="button" onClick={() => { void send(false) }}>Không phù hợp</button>
    <p>{mock ? 'Feedback mock chỉ lưu tạm trong bộ nhớ API; không dùng làm nhãn benchmark.' : 'Đánh giá được lưu vào PostgreSQL cho lượt tìm kiếm này.'}</p>
    {state === 'loading' && <p role="status">Đang gửi đánh giá…</p>}
    {state === 'success' && <p role="status">{mock ? 'Đã gửi đánh giá minh họa (lưu tạm).' : 'Đã lưu đánh giá.'}</p>}
    {state === 'error' && <p role="alert">{errorMessage}</p>}
  </fieldset>
}


async function readErrorCode(error: unknown): Promise<string | undefined> {
  if (!(error instanceof FeedbackApiError)) return undefined
  const response = error.response
  if (!response) return undefined
  try {
    const body: unknown = await response.clone().json()
    if (typeof body === 'object' && body !== null && 'error' in body
      && typeof body.error === 'object' && body.error !== null && 'code' in body.error
      && typeof body.error.code === 'string') return body.error.code
  } catch { /* Return safe generic feedback error. */ }
  return undefined
}
