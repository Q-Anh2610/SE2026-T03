import { beforeEach, expect, it, vi } from 'vitest'
import { searchImage, validateImage } from './client'
import { makeLiveResponse, makeResponse } from '../../../test/fixtures'

const file = new File(['image'], 'query.png', { type: 'image/png' })
const fetchMock = vi.fn()
beforeEach(() => {
  fetchMock.mockReset(); vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(), revokeObjectURL: vi.fn() }))
})
it('sends multipart without overriding the boundary and preserves server image reference', async () => {
  const response = makeResponse('mock-image:server-hash')
  fetchMock.mockResolvedValue(new Response(JSON.stringify(response)))
  expect(await searchImage(file, 1, new AbortController().signal)).toEqual(response)
  const [url, options] = fetchMock.mock.calls[0]
  expect(url).toContain('/api/v1/search/image')
  expect(options.headers).toBeUndefined()
  expect(options.body.get('image')).toBe(file)
  expect(options.body.get('filters')).toBe('{}')
  expect(options.body.get('page')).toBe('1')
  expect(options.body.get('limit')).toBe('12')
})
it.each([400, 503, 500])('rejects HTTP %s without mock fallback', async (status) => {
  fetchMock.mockResolvedValue(new Response('private', { status }))
  await expect(searchImage(file, 1, new AbortController().signal)).rejects.toThrow(status === 400 ? 'không hợp lệ' : 'chưa sẵn sàng')
  expect(fetchMock).toHaveBeenCalledOnce()
})
it.each([
  ['INVALID_REQUEST', 'phân trang không hợp lệ'],
  ['INVALID_FILTERS', 'Bộ lọc không hợp lệ'],
  ['IMAGE_TOO_LARGE', '5 MiB'],
  ['IMAGE_DIMENSIONS_EXCEEDED', '4096 pixel'],
  ['UNSUPPORTED_IMAGE', 'JPEG hoặc PNG'],
  ['INVALID_IMAGE', 'Không đọc được nội dung ảnh'],
])('maps upload error %s to a safe Vietnamese message', async (code, message) => {
  fetchMock.mockResolvedValue(new Response(JSON.stringify({ error: { code, message: 'private server detail' } }), { status: 400 }))
  await expect(searchImage(file, 1, new AbortController().signal)).rejects.toThrow(message)
})
it.each(['{}', 'null', '{"error":null}', '{"error":{"code":123}}', '{"error":{"code":"UNKNOWN"}}', '{"error":{"code":"toString"}}'])('handles malformed or unknown upload error %s', async (body) => {
  fetchMock.mockResolvedValue(new Response(body, { status: 400 }))
  await expect(searchImage(file, 1, new AbortController().signal)).rejects.toThrow('Ảnh hoặc yêu cầu không hợp lệ')
})
it.each(['bad-json', '{}', '{"query":1}', 'null', '1'])('rejects invalid response %s', async (body) => {
  fetchMock.mockResolvedValue(new Response(body))
  await expect(searchImage(file, 1, new AbortController().signal)).rejects.toThrow()
})
it('accepts the W4 live contract and sends filters', async () => {
  const response = makeLiveResponse(`sha256:${'a'.repeat(64)}`)
  response.results[0].retrieval_sources = ['clip_image_to_preview']
  fetchMock.mockResolvedValue(new Response(JSON.stringify(response)))
  expect(await searchImage(file, 1, new AbortController().signal, { format: 'glb', face_count_max: 1000 })).toEqual(response)
  expect(JSON.parse(fetchMock.mock.calls[0][1].body.get('filters'))).toEqual({ format: 'glb', face_count_max: 1000 })
})
it('rejects invalid filter bounds before HTTP', async () => {
  await expect(searchImage(file, 1, new AbortController().signal, { face_count_min: 2, face_count_max: 1 })).rejects.toThrow()
  expect(fetchMock).not.toHaveBeenCalled()
})
it('rejects an invalid live image reference', async () => {
  fetchMock.mockResolvedValue(new Response(JSON.stringify(makeLiveResponse('mock-image:fixture'))))
  await expect(searchImage(file, 1, new AbortController().signal)).rejects.toThrow('định danh ảnh')
})
it('maps network and timeout failures; preserves caller cancellation', async () => {
  fetchMock.mockRejectedValue(new Error('network'))
  await expect(searchImage(file, 1, new AbortController().signal)).rejects.toThrow('Không kết nối')
  const c = new AbortController(); c.abort()
  await expect(searchImage(file, 1, c.signal)).rejects.toThrow('network')
})
it('rejects unsupported and oversized files before decoding', async () => {
  await expect(validateImage(new File([], 'empty.png'))).rejects.toThrow('5 MiB')
  const large = new File(['x'], 'large.png'); Object.defineProperty(large, 'size', { value: 6 * 1024 * 1024 })
  await expect(validateImage(large)).rejects.toThrow('5 MiB')
  const bad = { size: 5, slice: () => ({ arrayBuffer: async () => new ArrayBuffer(8) }) } as unknown as File
  await expect(validateImage(bad)).rejects.toThrow('JPEG')
})
it('accepts a decodable image at both file and dimension limits', async () => {
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:limit')
  vi.stubGlobal('Image', class {
    naturalWidth = 4096
    naturalHeight = 4096
    onload = () => {}
    set src(_value: string) { queueMicrotask(() => this.onload()) }
  })
  const image = { size: 5 * 1024 * 1024, slice: () => ({ arrayBuffer: async () => new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]).buffer }) } as unknown as File
  await expect(validateImage(image)).resolves.toBeUndefined()
})

it.each(['png', 'jpeg', 'broken', 'oversized', 'zero-width', 'zero-height'])('decodes %s and revokes validation URLs', async (kind) => {
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test')
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  vi.stubGlobal('Image', class {
    naturalWidth = kind === 'oversized' ? 4097 : kind === 'zero-width' ? 0 : 2
    naturalHeight = kind === 'zero-height' ? 0 : 2
    onload = () => {}; onerror = () => {}
    set src(_value: string) { queueMicrotask(() => kind === 'broken' ? this.onerror() : this.onload()) }
  })
  const bytes = kind === 'jpeg' ? [255, 216, 255] : [137, 80, 78, 71, 13, 10, 26, 10]
  const image = { size: 8, slice: () => ({ arrayBuffer: async () => new Uint8Array(bytes).buffer }) } as unknown as File
  if (['broken', 'oversized', 'zero-width', 'zero-height'].includes(kind)) await expect(validateImage(image)).rejects.toThrow()
  else await expect(validateImage(image)).resolves.toBeUndefined()
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test')
})

it.each(['event', 'versions', 'source', 'score', 'metadata', 'pagination'])('rejects a malformed live image %s', async (field) => {
  const response = makeLiveResponse(`sha256:${'a'.repeat(64)}`)
  response.results[0].retrieval_sources = ['clip_image_to_preview']
  if (field === 'event') response.query_id = response.search_event_id = 'not-a-uuid'
  if (field === 'versions') response.versions.dataset_snapshot = ''
  if (field === 'source') response.results[0].retrieval_sources = ['clip_text_to_preview']
  if (field === 'score') response.results[0].score = 1.5
  if (field === 'metadata') response.results[0].asset.asset_id = ''
  if (field === 'pagination') response.pagination.page = 2
  fetchMock.mockResolvedValue(new Response(JSON.stringify(response)))
  await expect(searchImage(file, 1, new AbortController().signal)).rejects.toThrow()
})
