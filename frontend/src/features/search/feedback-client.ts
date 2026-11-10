import { apiUrl, REQUEST_TIMEOUT_MS } from '../../lib/api/http'

export class FeedbackApiError extends Error {
  constructor(readonly response?: Response, message = 'Chưa gửi được đánh giá.') {
    super(message)
  }
}

/** Confirm the API's persistence mode before linking a search event to feedback. */
export async function sendFeedback(
  eventId: string,
  assetId: string,
  relevance: boolean,
  mock: boolean,
  signal: AbortSignal,
): Promise<void> {
  const base = import.meta.env.VITE_API_BASE_URL ?? ''
  const requestSignal = AbortSignal.any([signal, AbortSignal.timeout(REQUEST_TIMEOUT_MS)])
  const specResponse = await fetch(apiUrl(base, '/openapi.json'), { signal: requestSignal })
  if (!specResponse.ok) throw new FeedbackApiError(undefined, 'Không xác minh được nguồn lưu feedback.')
  const spec = await specResponse.json()
  const schema = spec?.paths?.['/api/v1/feedback']?.post?.responses?.['201']?.content?.['application/json']?.schema?.$ref
  const expectedSchema = `#/components/schemas/${mock ? 'FeedbackResponse' : 'LiveFeedbackResponse'}`
  if (schema !== expectedSchema) throw new FeedbackApiError(undefined, 'Nguồn feedback không khớp lượt tìm kiếm.')

  const response = await fetch(apiUrl(base, '/api/v1/feedback'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ search_event_id: eventId, asset_id: assetId, relevance }),
    signal: requestSignal,
  })
  if (response.status !== 201) throw new FeedbackApiError(response)
  const body = await response.json()
  if (!body || typeof body.feedback_id !== 'string' || !body.feedback_id
    || body.search_event_id !== eventId || body.asset_id !== assetId || body.relevance !== relevance
    || body.mock !== mock || body.storage !== (mock ? 'memory' : 'postgresql')
    || typeof body.created_at !== 'string' || !Number.isFinite(Date.parse(body.created_at))) {
    throw new FeedbackApiError(undefined, 'Phản hồi feedback không hợp lệ.')
  }
}
