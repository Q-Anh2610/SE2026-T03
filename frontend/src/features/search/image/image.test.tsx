import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import userEvent from '@testing-library/user-event'
import { ImageSearchPage } from './ImageSearchPage'
import { App } from '../../../app/App'
import { deferred, makeLiveResponse, makeResponse } from '../../../test/fixtures'

const api = vi.hoisted(() => ({ validate: vi.fn(), search: vi.fn(), detail: vi.fn() }))
vi.mock('./client', async (original) => ({ ...await original<typeof import('./client')>(), validateImage: api.validate, searchImage: api.search }))
vi.mock('../../../lib/api/search', async (original) => ({ ...await original<typeof import('../../../lib/api/search')>(), createHttpAssetClient: () => ({ getAsset: api.detail }) }))
const file = new File(['png'], 'query.png', { type: 'image/png' })
const choose = () => fireEvent.change(screen.getByLabelText(/Chọn hoặc thay ảnh/), { target: { files: [file] } })
beforeEach(() => {
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:preview'), revokeObjectURL: vi.fn() }))
  api.validate.mockReset().mockResolvedValue(undefined)
  api.detail.mockReset().mockResolvedValue({ asset: makeResponse().results[0].asset })
  api.search.mockReset().mockResolvedValue(makeResponse())
})

it('offers a detail action for an image search result', async () => {
  render(<ImageSearchPage />)
  choose()
  await screen.findByRole('img')
  fireEvent.click(screen.getByText('Tìm bằng ảnh'))
  await screen.findByRole('list')
  expect(screen.getByRole('button', { name: /Xem chi tiết/ })).toBeVisible()
})

it('opens the image route from App', () => {
  const previous = window.location.hash
  window.location.hash = '#image-search'
  const view = render(<App />)
  expect(screen.getByRole('heading', { name: 'Tìm kiếm bằng ảnh' })).toBeVisible()
  view.unmount()
  window.location.hash = previous
})

it('does not submit without a file or replace it when the picker is cancelled', () => {
  render(<ImageSearchPage />)
  fireEvent.submit(screen.getByRole('button', { name: 'Tìm bằng ảnh' }).closest('form')!)
  fireEvent.change(screen.getByLabelText(/Chọn hoặc thay ảnh/), { target: { files: [] } })
  expect(api.validate).not.toHaveBeenCalled()
  expect(api.search).not.toHaveBeenCalled()
})

it('ignores validation and HTTP failures after unmount', async () => {
  const validation = deferred<void>()
  api.validate.mockReturnValueOnce(validation.promise)
  const view = render(<ImageSearchPage />); choose(); view.unmount()
  await act(async () => { validation.reject(new Error('old validation')) })
  const request = deferred<ReturnType<typeof makeResponse>>()
  api.search.mockReturnValueOnce(request.promise)
  const next = render(<ImageSearchPage />); choose(); await screen.findByRole('img')
  fireEvent.click(screen.getByText('Tìm bằng ảnh')); next.unmount()
  await act(async () => { request.reject(new Error('old HTTP')) })
})

it('selects, previews, replaces and clears an image, without requesting on selection', async () => {
  render(<ImageSearchPage />)
  expect(screen.getByRole('button', { name: 'Tìm bằng ảnh' })).toBeDisabled()
  choose()
  expect(await screen.findByRole('img')).toHaveAttribute('src', 'blob:preview')
  expect(api.search).not.toHaveBeenCalled()
  choose()
  await screen.findByRole('img')
  fireEvent.click(screen.getByText('Xóa ảnh'))
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  expect(URL.revokeObjectURL).toHaveBeenCalled()
})

it('removes a selected image using the keyboard and returns focus to the file input', async () => {
  const user = userEvent.setup()
  render(<ImageSearchPage />)
  await user.upload(screen.getByLabelText(/Chọn hoặc thay ảnh/), file)
  await screen.findByRole('img')
  const remove = screen.getByRole('button', { name: 'Xóa ảnh' })
  remove.focus()
  await user.keyboard('{Enter}')
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  expect(screen.getByLabelText(/Chọn hoặc thay ảnh/)).toHaveFocus()
})

it('associates an invalid image error with the file input', async () => {
  api.validate.mockRejectedValueOnce(new Error('Ảnh hỏng'))
  render(<ImageSearchPage />)
  choose()
  const error = await screen.findByRole('alert')
  expect(screen.getByLabelText(/Chọn hoặc thay ảnh/)).toHaveAccessibleDescription(error.textContent ?? '')
})

it('handles validation errors and ignores an old validation after replacement', async () => {
  const old = deferred<void>()
  api.validate.mockReturnValueOnce(old.promise).mockRejectedValueOnce(new Error('Ảnh hỏng'))
  render(<ImageSearchPage />)
  choose(); expect(screen.getByRole('status')).toHaveTextContent('Đang kiểm tra')
  choose(); expect(await screen.findByRole('alert')).toHaveTextContent('Ảnh hỏng')
  await act(async () => { old.resolve() })
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  expect(screen.queryByText('Thử lại')).not.toBeInTheDocument()
})

it('shows loading/error, retries the same file/page and renders an empty success', async () => {
  const pending = deferred<ReturnType<typeof makeResponse>>()
  const empty = makeResponse(); empty.results = []; empty.pagination = { page: 1, limit: 12, total: 0, pages: 0, has_next: false }
  api.search.mockReturnValueOnce(pending.promise).mockResolvedValueOnce(empty)
  render(<ImageSearchPage />); choose(); await screen.findByRole('img')
  fireEvent.click(screen.getByText('Tìm bằng ảnh'))
  expect(screen.getByRole('status')).toHaveTextContent('Đang tìm ảnh')
  expect(screen.queryByText('Chưa có asset phù hợp')).not.toBeInTheDocument()
  await act(async () => { pending.reject(new Error('API lỗi')) })
  expect(await screen.findByRole('alert')).toHaveTextContent('API lỗi')
  fireEvent.click(screen.getByText('Thử lại'))
  expect(await screen.findByText('Chưa có asset phù hợp')).toBeVisible()
  expect(api.search.mock.calls[0].slice(0, 2)).toEqual(api.search.mock.calls[1].slice(0, 2))
})

it('submits selected filters and preserves them on retry', async () => {
  api.search.mockRejectedValueOnce(new Error('API lỗi')).mockResolvedValueOnce(makeResponse())
  render(<ImageSearchPage />); choose(); await screen.findByRole('img')
  fireEvent.change(screen.getByLabelText('Định dạng'), { target: { value: 'glb' } })
  fireEvent.click(screen.getByText('Tìm bằng ảnh'))
  await screen.findByRole('alert')
  fireEvent.change(screen.getByLabelText('Định dạng'), { target: { value: 'obj' } })
  fireEvent.click(screen.getByText('Thử lại'))
  await screen.findByRole('list')
  expect(api.search.mock.calls[0][3]).toEqual({ format: 'glb' })
  expect(api.search.mock.calls[1][3]).toEqual({ format: 'glb' })
})

it('paginates mock results and ignores a request after clearing the selected image', async () => {
  const first = makeResponse(); first.pagination.has_next = true
  const second = makeResponse(); second.pagination.page = 2
  api.search.mockResolvedValueOnce(first).mockResolvedValueOnce(second).mockResolvedValueOnce(first)
  const pending = deferred<ReturnType<typeof makeResponse>>()
  api.search.mockReturnValueOnce(pending.promise)
  render(<ImageSearchPage />); choose(); await screen.findByRole('img')
  fireEvent.click(screen.getByText('Tìm bằng ảnh')); await screen.findByRole('list')
  fireEvent.click(screen.getByText('Trang sau')); await screen.findByRole('list')
  expect(api.search.mock.calls[1][1]).toBe(2)
  fireEvent.click(screen.getByText('Trang trước')); await screen.findByRole('list')
  fireEvent.click(screen.getByText('Tìm bằng ảnh')); fireEvent.click(screen.getByText('Xóa ảnh'))
  await act(async () => { pending.resolve(first) })
  expect(screen.queryByRole('list')).not.toBeInTheDocument()
})

it('renders live metadata and execution versions and retains submitted filters when paging', async () => {
  const first = makeLiveResponse(`sha256:${'a'.repeat(64)}`)
  first.results[0].retrieval_sources = ['clip_image_to_preview']
  first.pagination = { page: 1, limit: 12, total: 13, pages: 2, has_next: true }
  const second = { ...first, query_id: 'next-event', search_event_id: 'next-event', pagination: { ...first.pagination, page: 2, has_next: false } }
  api.search.mockResolvedValueOnce(first).mockResolvedValueOnce(second)
  render(<ImageSearchPage />); choose(); await screen.findByRole('img')
  fireEvent.change(screen.getByLabelText('Định dạng'), { target: { value: 'glb' } })
  fireEvent.click(screen.getByText('Tìm bằng ảnh'))
  expect(await screen.findByText('Kết quả tìm kiếm bằng ảnh')).toBeVisible()
  expect(screen.getByText(first.results[0].asset.name)).toBeVisible()
  fireEvent.click(screen.getByText('Thông tin phiên tìm ảnh'))
  expect(screen.getByText(first.versions.dataset_snapshot)).toBeVisible()
  expect(screen.getByText(first.versions.index_version)).toBeVisible()
  fireEvent.change(screen.getByLabelText('Định dạng'), { target: { value: 'obj' } })
  fireEvent.click(screen.getByText('Trang sau'))
  await screen.findByText(/Trang 2/)
  expect(api.search.mock.calls[1][1]).toBe(2)
  expect(api.search.mock.calls[1][3]).toEqual({ format: 'glb' })
})

it('submits numeric face bounds and clears the filter form', async () => {
  render(<ImageSearchPage />); choose(); await screen.findByRole('img')
  fireEvent.change(screen.getByLabelText('Số mặt tối thiểu'), { target: { value: '10' } })
  fireEvent.change(screen.getByLabelText('Số mặt tối đa'), { target: { value: '100' } })
  fireEvent.click(screen.getByText('Tìm bằng ảnh')); await screen.findByRole('list')
  expect(api.search.mock.calls[0][3]).toEqual({ face_count_min: 10, face_count_max: 100 })
  fireEvent.change(screen.getByLabelText('Số mặt tối thiểu'), { target: { value: '' } })
  fireEvent.click(screen.getByText('Xóa bộ lọc'))
  expect(screen.getByLabelText('Số mặt tối đa')).toHaveValue(null)
})

async function showImageResults() {
  render(<ImageSearchPage />); choose(); await screen.findByRole('img')
  fireEvent.click(screen.getByText('Tìm bằng ảnh')); await screen.findByRole('list')
  fireEvent.click(screen.getByRole('button', { name: /Xem chi tiết/ }))
}
it('loads detail through HTTP using the result ID and returns to unchanged image results', async () => {
  await showImageResults()
  await screen.findByRole('heading', { name: makeResponse().results[0].asset.name })
  expect(api.detail.mock.calls[0][0]).toBe(makeResponse().results[0].asset.asset_id)
  fireEvent.click(screen.getByRole('button', { name: 'Quay lại danh sách' }))
  expect(screen.getByRole('list')).toBeVisible()
  expect(screen.getByRole('img', { name: 'Ảnh truy vấn: query.png' })).toBeVisible()
})
it.each([new Error('offline'), { kind: 'not_found', message: 'missing' }, null])('handles a detail failure %j and retries or returns', async (error) => {
  api.detail.mockRejectedValueOnce(error)
  await showImageResults()
  await screen.findByRole('alert')
  const retry = screen.queryByRole('button', { name: 'Thử lại' })
  if (retry) {
    fireEvent.click(retry)
    await screen.findByRole('heading', { name: makeResponse().results[0].asset.name })
    fireEvent.click(screen.getByRole('button', { name: 'Quay lại danh sách' }))
  } else fireEvent.click(screen.getAllByRole('button', { name: 'Quay lại danh sách' })[0])
  expect(screen.getByRole('list')).toBeVisible()
})
it.each([true, false])('ignores detail completion after returning (success=%s)', async (success) => {
  const pending = deferred<{ asset: ReturnType<typeof makeResponse>['results'][0]['asset'] }>()
  api.detail.mockReturnValueOnce(pending.promise)
  await showImageResults()
  expect(screen.getByRole('status')).toHaveTextContent('Đang tải chi tiết')
  fireEvent.click(screen.getByRole('button', { name: 'Quay lại danh sách' }))
  await act(async () => { if (success) pending.resolve({ asset: makeResponse().results[0].asset }); else pending.reject(new Error('late')) })
  expect(screen.getByRole('list')).toBeVisible()
})
