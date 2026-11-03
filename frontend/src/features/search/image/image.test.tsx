import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { ImageSearchPage } from './ImageSearchPage'
import { App } from '../../../app/App'
import { deferred, makeResponse } from '../../../test/fixtures'

const api = vi.hoisted(() => ({ validate: vi.fn(), search: vi.fn() }))
vi.mock('./client', async (original) => ({ ...await original<typeof import('./client')>(), validateImage: api.validate, searchImage: api.search }))
const file = new File(['png'], 'query.png', { type: 'image/png' })
const choose = () => fireEvent.change(screen.getByLabelText(/Chọn hoặc thay ảnh/), { target: { files: [file] } })
beforeEach(() => {
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:preview'), revokeObjectURL: vi.fn() }))
  api.validate.mockReset().mockResolvedValue(undefined)
  api.search.mockReset().mockResolvedValue(makeResponse())
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

