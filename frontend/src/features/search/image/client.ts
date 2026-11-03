import { parseResponse } from '../contract'
import type { MockSearchResponse } from '../types'
import { apiUrl, REQUEST_TIMEOUT_MS } from '../../../lib/api/http'

export async function validateImage(file: File): Promise<void> {
  if (!file.size || file.size > 5 * 1024 * 1024) throw new Error('Ảnh phải có dung lượng từ 1 byte đến 5 MiB.')
  const bytes = new Uint8Array(await file.slice(0, 8).arrayBuffer())
  const png = [137, 80, 78, 71, 13, 10, 26, 10].every((value, i) => bytes[i] === value)
  const jpeg = bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255
  if (!png && !jpeg) throw new Error('Chỉ hỗ trợ ảnh JPEG hoặc PNG decode được.')
  const url = URL.createObjectURL(file)
  try {
    const image = new Image()
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve()
      image.onerror = () => reject(new Error('Không đọc được nội dung ảnh.'))
      image.src = url
    })
    if (!image.naturalWidth || !image.naturalHeight || Math.max(image.naturalWidth, image.naturalHeight) > 4096) {
      throw new Error('Mỗi chiều ảnh phải từ 1 đến 4096 pixel.')
    }
  } finally { URL.revokeObjectURL(url) }
}

/** W1 image endpoint is explicitly a fixture API; no live-image contract exists yet. */
export async function searchImage(file: File, page: number, signal: AbortSignal): Promise<MockSearchResponse> {
  const form = new FormData()
  form.append('image', file)
  form.append('filters', '{}')
  form.append('page', String(page))
  form.append('limit', '12')
  let response: Response
  try {
    response = await fetch(apiUrl(import.meta.env.VITE_API_BASE_URL ?? '', '/api/v1/search/image'), {
      method: 'POST', body: form,
      signal: AbortSignal.any([signal, AbortSignal.timeout(REQUEST_TIMEOUT_MS)]),
    })
  } catch (error) {
    if (signal.aborted) throw error
    throw new Error('Không kết nối được dịch vụ tìm ảnh. Hãy thử lại.')
  }
  if (!response.ok) throw new Error(response.status === 400
    ? 'Ảnh hoặc yêu cầu không hợp lệ. Kiểm tra ảnh rồi thử lại.'
    : 'Dịch vụ tìm ảnh chưa sẵn sàng. Hãy thử lại sau.')
  let payload: unknown
  try { payload = await response.json() } catch { throw new Error('API trả về dữ liệu ảnh không hợp lệ.') }
  if (typeof payload !== 'object' || payload === null || !('query' in payload) || typeof payload.query !== 'string') {
    throw new Error('API trả về dữ liệu ảnh không hợp lệ.')
  }
  const parsed = parseResponse(payload, { query: payload.query, filters: {}, page, limit: 12 })
  if (!parsed.mock) throw new Error('Chưa có contract tìm ảnh thật; không thể xác nhận response này.')
  return parsed
}
