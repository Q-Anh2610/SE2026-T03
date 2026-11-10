import { parseResponse, validateListQuery } from '../contract'
import type { AssetFilters, SearchResponse } from '../types'
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

/** Multipart contract shared by fixture and W4 image service. */
export async function searchImage(file: File, page: number, signal: AbortSignal, filters: AssetFilters = {}): Promise<SearchResponse> {
  const request = validateListQuery({ filters, page, limit: 12 })
  const form = new FormData()
  form.append('image', file)
  form.append('filters', JSON.stringify(request.filters))
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
  if (!response.ok) {
    if (response.status !== 400) throw new Error('Dịch vụ tìm ảnh chưa sẵn sàng. Hãy thử lại sau.')
    const messages: Record<string, string> = {
      INVALID_REQUEST: 'Thiếu ảnh hoặc phân trang không hợp lệ. Kiểm tra yêu cầu rồi thử lại.',
      INVALID_FILTERS: 'Bộ lọc không hợp lệ. Kiểm tra bộ lọc rồi thử lại.',
      IMAGE_TOO_LARGE: 'Ảnh vượt giới hạn 5 MiB. Hãy chọn ảnh nhỏ hơn.',
      IMAGE_DIMENSIONS_EXCEEDED: 'Mỗi chiều ảnh không được vượt 4096 pixel.',
      UNSUPPORTED_IMAGE: 'Chỉ hỗ trợ ảnh JPEG hoặc PNG.',
      INVALID_IMAGE: 'Không đọc được nội dung ảnh. Hãy chọn ảnh JPEG hoặc PNG hợp lệ.',
    }
    let code: unknown
    try {
      const body: unknown = await response.json()
      if (typeof body === 'object' && body !== null && 'error' in body
        && typeof body.error === 'object' && body.error !== null && 'code' in body.error) {
        code = body.error.code
      }
    } catch { /* Giữ thông báo an toàn nếu server không trả JSON. */ }
    throw new Error(typeof code === 'string' && Object.hasOwn(messages, code)
      ? messages[code] : 'Ảnh hoặc yêu cầu không hợp lệ. Kiểm tra ảnh rồi thử lại.')
  }
  let payload: unknown
  try { payload = await response.json() } catch { throw new Error('API trả về dữ liệu ảnh không hợp lệ.') }
  if (typeof payload !== 'object' || payload === null || !('query' in payload) || typeof payload.query !== 'string') {
    throw new Error('API trả về dữ liệu ảnh không hợp lệ.')
  }
  const parsed = parseResponse(payload, { query: payload.query, ...request })
  if (!parsed.mock && !/^sha256:[a-f0-9]{64}$/.test(parsed.query)) throw new Error('API trả về định danh ảnh không hợp lệ.')
  if (!parsed.mock && (!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(parsed.search_event_id)
    || parsed.results.some((result) => result.retrieval_sources.length !== 1
      || result.retrieval_sources[0] !== 'clip_image_to_preview'
      || result.score === null || result.score < -1 || result.score > 1))) {
    throw new Error('API trả về kết quả không đúng contract tìm ảnh thật.')
  }
  return parsed
}
