import type {
  AssetDetailResponse,
  AssetFilters,
  AssetListQuery,
  AssetListResponse,
  AssetMetadata,
  Pagination,
  SearchRequest,
  SearchResponse,
} from './types'

export interface FilterFormValues {
  category: string
  format: string
  license: string
  face_count_min: string
  face_count_max: string
}

export const EMPTY_FILTER_FORM: FilterFormValues = {
  category: '',
  format: '',
  license: '',
  face_count_min: '',
  face_count_max: '',
}

function parseNonNegativeInt(raw: string): number {
  const trimmed = raw.trim()
  if (!/^\d+$/.test(trimmed)) return Number.NaN
  return Number(trimmed)
}

export function buildFilterDraft(values: FilterFormValues): AssetFilters {
  const draft: Record<string, unknown> = {}
  for (const key of ['category', 'format', 'license'] as const) {
    const trimmed = values[key].trim()
    if (trimmed !== '') draft[key] = trimmed
  }
  for (const key of ['face_count_min', 'face_count_max'] as const) {
    if (values[key].trim() !== '') draft[key] = parseNonNegativeInt(values[key])
  }
  return draft as AssetFilters
}

function normalizePaginationAndFilters(input: { page?: number; limit: number; filters: AssetFilters }): {
  page: number
  limit: number
  filters: AssetFilters
} {
  if (!Number.isInteger(input.limit) || input.limit < 1 || input.limit > 50) {
    throw new Error('Số kết quả phải là số nguyên từ 1 đến 50.')
  }
  const page = input.page === undefined ? 1 : input.page
  if (!Number.isSafeInteger(page) || page < 1) throw new Error('Trang phải là số nguyên từ 1.')
  validateFilters(input.filters)
  const filters = Object.fromEntries(
    Object.entries(input.filters)
      .filter(([, value]) => value !== undefined)
      .map(([key, value]) => [key, typeof value === 'string' ? value.trim() : value]),
  ) as AssetFilters
  return { page, limit: input.limit, filters }
}

export function validateRequest(request: SearchRequest): SearchRequest {
  const query = request.query.trim()
  if (Array.from(query).length < 1 || Array.from(query).length > 500) {
    throw new Error('Nhập mô tả từ 1 đến 500 ký tự để tìm kiếm.')
  }
  const { page, limit, filters } = normalizePaginationAndFilters(request)
  return { ...request, query, page, limit, filters }
}

export function validateListQuery(query: AssetListQuery): { page: number; limit: number; filters: AssetFilters } {
  const normalized = normalizePaginationAndFilters(query)
  const filters = Object.fromEntries(
    Object.entries(normalized.filters).filter(([, value]) => value !== null),
  ) as AssetFilters
  return { ...normalized, filters }
}

export function validateAssetId(assetId: string): string {
  const normalized = assetId.trim()
  if (!normalized || normalized.includes('/') || normalized === '.' || normalized === '..') {
    throw new Error('Mã asset không hợp lệ.')
  }
  return normalized
}

export function validateFilters(filters: SearchRequest['filters']): void {
  const invalid = () => new Error('Bộ lọc không hợp lệ. Kiểm tra danh mục, định dạng, license và khoảng số mặt.')
  if (!isRecord(filters)) throw invalid()
  for (const [key, value] of Object.entries(filters)) {
    if (!['category', 'license', 'format', 'face_count_min', 'face_count_max'].includes(key)) throw invalid()
    if (value === null || value === undefined) continue
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

export function isAsset(value: unknown): value is AssetMetadata {
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

function isValidPagination(pagination: unknown, page: number, limit: number, itemCount: number): pagination is Pagination {
  if (!isRecord(pagination) || pagination.page !== page || pagination.limit !== limit
    || !Number.isSafeInteger(pagination.total) || (pagination.total as number) < 0) {
    return false
  }
  const total = pagination.total as number
  const pages = Math.ceil(total / limit)
  const expectedCount = Math.min(limit, Math.max(0, total - (page - 1) * limit))
  return pagination.pages === pages && pagination.has_next === (page < pages) && itemCount === expectedCount
}

export function parseResponse(value: unknown, request: SearchRequest): SearchResponse {
  const invalid = () => new Error('Dữ liệu trả về không đúng contract nháp. Hãy thử lại hoặc kiểm tra API.')
  if (!isRecord(value) || typeof value.query_id !== 'string' || !value.query_id
    || typeof value.search_event_id !== 'string' || !value.search_event_id
    || value.query !== request.query || !isRecord(value.versions)
    || !['model_version', 'index_version', 'config_version'].every(
      (key) => typeof value.versions === 'object' && value.versions !== null
        && typeof (value.versions as Record<string, unknown>)[key] === 'string',
    ) || !Array.isArray(value.results) || value.results.length > request.limit
    || !isValidPagination(value.pagination, request.page ?? 1, request.limit, value.results.length)) {
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

export function parseAssetListResponse(value: unknown, query: AssetListQuery): AssetListResponse {
  const invalid = () => new Error('Dữ liệu danh sách asset không đúng contract. Hãy thử lại hoặc kiểm tra API.')
  const page = query.page ?? 1
  if (!isRecord(value) || !Array.isArray(value.items) || value.items.length > query.limit
    || (value.mock !== undefined && typeof value.mock !== 'boolean')
    || !isValidPagination(value.pagination, page, query.limit, value.items.length)) {
    throw invalid()
  }
  const identifiers = new Set<string>()
  for (const item of value.items) {
    if (!isAsset(item) || identifiers.has(item.asset_id)) throw invalid()
    identifiers.add(item.asset_id)
  }
  return value as unknown as AssetListResponse
}

export function parseAssetDetailResponse(value: unknown, expectedAssetId: string): AssetDetailResponse {
  const invalid = () => new Error('Dữ liệu chi tiết asset không đúng contract. Hãy thử lại hoặc kiểm tra API.')
  if (!isRecord(value) || !isAsset(value.asset) || value.asset.asset_id !== expectedAssetId
    || (value.mock !== undefined && typeof value.mock !== 'boolean')) {
    throw invalid()
  }
  return value as unknown as AssetDetailResponse
}
