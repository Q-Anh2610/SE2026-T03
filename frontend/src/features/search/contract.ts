import type { AssetMetadata, SearchRequest, SearchResponse } from './types'

export function validateRequest(request: SearchRequest): SearchRequest {
  const query = request.query.trim()
  if (Array.from(query).length < 1 || Array.from(query).length > 500) {
    throw new Error('Nhập mô tả từ 1 đến 500 ký tự để tìm kiếm.')
  }
  if (!Number.isInteger(request.limit) || request.limit < 1 || request.limit > 50) {
    throw new Error('Số kết quả phải là số nguyên từ 1 đến 50.')
  }
  if (!isRecord(request.filters) || Object.keys(request.filters).length > 0) {
    throw new Error('Bộ lọc chưa được hỗ trợ trong bản tuần 1.')
  }
  return { ...request, query }
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
  return ['asset_id', 'name', 'description', 'category', 'source'].every(
    (key) => typeof value[key] === 'string',
  ) && value.asset_id !== '' && value.name !== ''
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
