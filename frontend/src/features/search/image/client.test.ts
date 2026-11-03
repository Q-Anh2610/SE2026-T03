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
it.each(['bad-json', '{}', '{"query":1}', 'null', '1'])('rejects invalid response %s', async (body) => {
  fetchMock.mockResolvedValue(new Response(body))
  await expect(searchImage(file, 1, new AbortController().signal)).rejects.toThrow()
})
it('does not silently accept an unagreed live image contract', async () => {
  fetchMock.mockResolvedValue(new Response(JSON.stringify(makeLiveResponse('mock-image:fixture'))))
  await expect(searchImage(file, 1, new AbortController().signal)).rejects.toThrow('Chưa có contract')
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
