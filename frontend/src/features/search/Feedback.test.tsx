import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { Feedback } from './Feedback'
const fetchMock = vi.fn()
let schemaMock = true
let postResponse = () => new Response('{}', { status: 500 })
const openapi = (mock: boolean) => new Response(JSON.stringify({ paths: { '/api/v1/feedback': { post: { responses: { 201: { content: { 'application/json': { schema: { $ref: `#/components/schemas/${mock ? 'FeedbackResponse' : 'LiveFeedbackResponse'}` } } } } } } } } }))
beforeEach(() => {
  fetchMock.mockReset()
  schemaMock = true
  postResponse = () => new Response('{}', { status: 500 })
  fetchMock.mockImplementation((url: string) => String(url).endsWith('/openapi.json') ? openapi(schemaMock) : postResponse())
  vi.stubGlobal('fetch', fetchMock)
})
function respond(body: unknown, status = 201) { postResponse = () => new Response(JSON.stringify(body), { status }) }
it.each([true, false])('sends Boolean relevance %s with exact event and asset', async (relevance) => {
  respond({ feedback_id: 'f1', search_event_id: 'event', asset_id: 'asset', relevance, created_at: '2026-11-07T00:00:00Z', mock: true, storage: 'memory' })
  render(<Feedback eventId="event" assetId="asset" mock />)
  fireEvent.click(screen.getByRole('button', { name: relevance ? 'Phù hợp' : 'Không phù hợp' }))
  expect(await screen.findByText('Đã gửi đánh giá minh họa (lưu tạm).')).toBeVisible()
  expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ search_event_id: 'event', asset_id: 'asset', relevance })
  expect(screen.getByRole('button', { name: 'Phù hợp' })).toBeDisabled()
})
it('shows failure and allows retry instead of claiming success', async () => {
  respond({}, 404)
  render(<Feedback eventId="event" assetId="asset" mock />)
  fireEvent.click(screen.getByRole('button', { name: 'Phù hợp' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Chưa gửi được')
  expect(screen.getByRole('button', { name: 'Phù hợp' })).toBeEnabled()
})
it('does not send live events when OpenAPI advertises memory-only feedback', async () => {
  schemaMock = true
  render(<Feedback eventId="live-event" assetId="asset" mock={false} />)
  fireEvent.click(screen.getByRole('button', { name: 'Phù hợp' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Nguồn feedback không khớp lượt tìm kiếm.')
  expect(fetchMock).toHaveBeenCalledTimes(1)
})
it('does not post feedback when the API schema cannot be verified', async () => {
  fetchMock.mockImplementation(() => new Response('{}', { status: 503 }))
  render(<Feedback eventId="event" assetId="asset" mock />)
  fireEvent.click(screen.getByRole('button', { name: 'Phù hợp' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Không xác minh được nguồn lưu feedback.')
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it.each([null, {}, { feedback_id: 'f', search_event_id: 'wrong' }, { feedback_id: 'f', search_event_id: 'event', asset_id: 'asset', relevance: true, mock: false, storage: 'database', created_at: 'bad' }])('rejects a malformed success response %j', async (body) => {
  respond(body)
  render(<Feedback eventId="event" assetId="asset" mock />)
  fireEvent.click(screen.getByRole('button', { name: 'Phù hợp' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Phản hồi feedback không hợp lệ.')
  expect(screen.queryByText('Đã gửi đánh giá minh họa (lưu tạm).')).not.toBeInTheDocument()
})

it.each([true, false])('ignores a completed feedback request after unmount (success=%s)', async (success) => {
  let resolve!: (value: Response) => void
  let reject!: (error: Error) => void
  postResponse = () => new Promise<Response>((res, rej) => { resolve = res; reject = rej }) as unknown as Response
  const view = render(<Feedback eventId="event" assetId="asset" mock />)
  fireEvent.click(screen.getByRole('button', { name: 'Phù hợp' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  view.unmount()
  expect(fetchMock.mock.calls[1][1].signal.aborted).toBe(true)
  await act(async () => {
    if (success) resolve(new Response(JSON.stringify({ feedback_id: 'f', search_event_id: 'event', asset_id: 'asset', relevance: true, mock: true, storage: 'memory', created_at: '2026-11-07T00:00:00Z' }), { status: 201 }))
    else reject(new Error('cancelled'))
  })
})

it('stores live feedback only after PostgreSQL response matches event, asset and relevance', async () => {
  schemaMock = false
  respond({ feedback_id: 'f2', search_event_id: 'live-event', asset_id: 'asset-2', relevance: false, created_at: '2026-11-10T00:00:00Z', mock: false, storage: 'postgresql' })
  render(<Feedback eventId="live-event" assetId="asset-2" mock={false} />)
  fireEvent.click(screen.getByRole('button', { name: 'Không phù hợp' }))
  expect(await screen.findByText('Đã lưu đánh giá.')).toBeVisible()
  expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ search_event_id: 'live-event', asset_id: 'asset-2', relevance: false })
})
it.each([
  ['SEARCH_EVENT_RESULTS_UNAVAILABLE', 'chưa lưu danh sách kết quả'],
  ['EVENT_ASSET_MISMATCH', 'không thuộc lượt tìm kiếm'],
  ['SEARCH_EVENT_NOT_FOUND', 'Không tìm thấy lượt tìm kiếm'],
])('shows safe API feedback error %s', async (code, message) => {
  schemaMock = false
  respond({ error: { code, message: 'internal' } }, 400)
  render(<Feedback eventId="event" assetId="asset" mock={false} />)
  fireEvent.click(screen.getByRole('button', { name: 'Phù hợp' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(message)
  expect(screen.getByRole('alert')).not.toHaveTextContent('internal')
})
