import type { AssetMetadata, SearchRequest, SearchResponse } from './types'

export function validateRequest(request: SearchRequest): SearchRequest {
  const query = request.query.trim()
  if (Array.from(query).length < 1 || Array.from(query).length > 500) {
    throw new Error('Nhập mô tả từ 1 đến 500 ký tự để tìm kiếm.')
  }
  if (!Number.isInteger(request.limit) || request.limit < 1 || request.limit > 50) {
    throw new Error('Số kết quả phải là số nguyên từ 1 đến 50.')
  }
  const page = request.page === undefined ? 1 : request.page
  if (!Number.isSafeInteger(page) || page < 1) throw new Error('Trang phải là số nguyên từ 1.')
  validateFilters(request.filters)
  const filters = Object.fromEntries(Object.entries(request.filters).map(([key, value]) =>
    [key, typeof value === 'string' ? value.trim() : value]))
  return { ...request, query, page, filters }
}

export function validateFilters(filters: SearchRequest['filters']): void {
  const invalid = () => new Error('Bộ lọc không hợp lệ. Kiểm tra danh mục, định dạng, license và khoảng số mặt.')
  if (!isRecord(filters)) throw invalid()
  for (const [key, value] of Object.entries(filters)) {
    if (!['category', 'license', 'format', 'face_count_min', 'face_count_max'].includes(key)) throw invalid()
    if (value === null) continue
    if (['category', 'license', 'format'].includes(key)) {
      if (typeof value !== 'string' || !value.trim()) throw invalid()
    } else if (!Number.isSafeInteger(value) || (value as number) < 0) throw invalid()
  }
  if (filters.face_count_min != null && filters.face_count_max != null
    && filters.face_count_min > filters.face_count_max) throw invalid()
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

function isNullableString(value: unknown): boolean {
  return value === null || typeof value === 'string'
}

export function isHttpUrl(value: unknown): value is string {
  if (typeof value !== 'string') return false
  try {
    const parsed = new URL(value)
    return ['http:', 'https:'].includes(parsed.protocol) && !parsed.username && !parsed.password
  } catch {
    return false
  }
}

function isAsset(value: unknown): value is AssetMetadata {
  if (!isRecord(value)) return false
  return ['asset_id', 'name', 'source'].every(
    (key) => typeof value[key] === 'string',
  ) && value.asset_id !== '' && value.name !== ''
    && isNullableString(value.description) && isNullableString(value.category)
    && isStringArray(value.tags) && isStringArray(value.formats)
    && (value.face_count === null || (typeof value.face_count === 'number'
      && Number.isInteger(value.face_count) && value.face_count >= 0))
    && isNullableString(value.author) && isNullableString(value.license)
    && (value.thumbnail_url === null || isHttpUrl(value.thumbnail_url))
    && (value.source_url === null || isHttpUrl(value.source_url))
}

export function parseResponse(value: unknown, request: SearchRequest): SearchResponse {
  const invalid = () => new Error('Dữ liệu trả về không đúng contract nháp. Hãy thử lại hoặc kiểm tra API.')
  if (!isRecord(value) || typeof value.query_id !== 'string' || !value.query_id
    || typeof value.search_event_id !== 'string' || !value.search_event_id
    || value.query !== request.query || !isRecord(value.versions)
    || !['model_version', 'index_version', 'config_version'].every(
      (key) => typeof value.versions === 'object' && value.versions !== null
        && typeof (value.versions as Record<string, unknown>)[key] === 'string',
    ) || !Array.isArray(value.results) || value.results.length > request.limit) {
    throw invalid()
  }
  const pagination = value.pagination
  if (!isRecord(pagination) || pagination.page !== (request.page ?? 1) || pagination.limit !== request.limit
    || !Number.isSafeInteger(pagination.total) || (pagination.total as number) < 0
    || pagination.pages !== Math.ceil((pagination.total as number) / request.limit)
    || pagination.has_next !== ((request.page ?? 1) < (pagination.pages as number))
    || value.results.length !== Math.min(request.limit, Math.max(0,
      (pagination.total as number) - ((request.page ?? 1) - 1) * request.limit))) throw invalid()
  const identifiers = new Set<string>()
  for (const [position, result] of value.results.entries()) {
    if (!isRecord(result) || result.rank !== position + 1 || !isAsset(result.asset)
      || !isStringArray(result.retrieval_sources) || typeof result.explanation !== 'string'
      || (result.score !== null && (typeof result.score !== 'number' || !Number.isFinite(result.score)))
      || identifiers.has(result.asset.asset_id)) {
      throw invalid()
    }
    identifiers.add(result.asset.asset_id)
  }
  return value as unknown as SearchResponse
}
