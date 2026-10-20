import { parseResponse, validateRequest } from './contract'
import type { AssetFilters, AssetMetadata, MockScenario, SearchClient } from './types'

const fixtureDescriptions = [
  { asset_id: 'mock-chair-01', name: 'Ghế gỗ đơn giản', category: 'Nội thất', tags: ['ghế', 'gỗ', 'chair', 'wood'] },
  { asset_id: 'mock-chair-02', name: 'Ghế thư giãn', category: 'Nội thất', tags: ['ghế', 'vải', 'chair', 'lounge'] },
  { asset_id: 'mock-table-01', name: 'Bàn gỗ tròn', category: 'Nội thất', tags: ['bàn', 'gỗ', 'table', 'wood'] },
  { asset_id: 'mock-lamp-01', name: 'Đèn bàn', category: 'Đồ gia dụng', tags: ['đèn', 'lamp', 'light'] },
  { asset_id: 'mock-vase-01', name: 'Bình hoa', category: 'Đồ gia dụng', tags: ['bình', 'hoa', 'vase'] },
  { asset_id: 'mock-box-01', name: 'Thùng gỗ', category: 'Game props', tags: ['thùng', 'gỗ', 'crate', 'wood', 'box'] },
]

export const mockAssets: AssetMetadata[] = fixtureDescriptions.map((fixture) => ({
  ...fixture,
  description: 'Bản ghi minh họa tự tạo cho giao diện tuần 1.',
  formats: ['glb'],
  face_count: null,
  thumbnail_url: null,
  source: 'fixture',
  source_url: null,
  author: null,
  license: null,
}))

export function normalizeQuery(value: string): string {
  return value.toLocaleLowerCase('vi').normalize('NFD').replace(/\p{Diacritic}/gu, '').replace(/đ/g, 'd').trim()
}

function waitForMock(signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException('Aborted', 'AbortError'))
      return
    }
    const abort = () => {
      clearTimeout(timeout)
      reject(new DOMException('Aborted', 'AbortError'))
    }
    const timeout = setTimeout(() => {
      signal.removeEventListener('abort', abort)
      resolve()
    }, 450)
    signal.addEventListener('abort', abort, { once: true })
  })
}

export function createMockSearchClient(scenario: MockScenario): SearchClient {
  return {
    async search(input, signal) {
      const request = validateRequest(input)
      await waitForMock(signal)
      if (scenario === 'error') throw new Error('Lỗi kết nối minh họa. Chọn Thử lại để chạy mock bình thường.')
      return createMockSearchResponse(request.query, request.limit, scenario, request.page, request.filters)
    },
  }
}


export function findMockAssets(query: string): AssetMetadata[] {
  const tokens = normalizeQuery(query).split(/\s+/).filter(Boolean)
  return mockAssets.filter((asset) => {
    const haystack = normalizeQuery([asset.name, asset.category, ...asset.formats, ...asset.tags].join(' '))
    return tokens.every((token) => haystack.includes(token))
  })
}

export function createMockSearchResponse(query: string, limit = 12, scenario: MockScenario = 'success', page = 1, filters: AssetFilters = {}) {
  const request = validateRequest({ query, filters, limit, page })
  filters = request.filters
  const matching = scenario === 'empty' ? [] : findMockAssets(request.query).filter((asset) =>
    (filters.category == null || asset.category === filters.category)
    && (filters.license == null || asset.license === filters.license)
    && (filters.format == null || asset.formats.includes(filters.format))
    && (filters.face_count_min == null || (asset.face_count !== null && asset.face_count >= filters.face_count_min))
    && (filters.face_count_max == null || (asset.face_count !== null && asset.face_count <= filters.face_count_max)))
  const selected = matching.slice((page - 1) * request.limit, page * request.limit)
  return parseResponse({
    query_id: `mock-query-${crypto.randomUUID()}`,
    search_event_id: `mock-event-${crypto.randomUUID()}`,
    query: request.query,
    pagination: { page, limit, total: matching.length, pages: Math.ceil(matching.length / limit), has_next: page * limit < matching.length },
    results: selected.map((asset, position) => ({
      rank: position + 1,
      asset: { ...asset, tags: [...asset.tags], formats: [...asset.formats] },
      retrieval_sources: ['mock_metadata'],
      explanation: 'Minh họa khớp từ khóa trong metadata; chưa chạy semantic search.',
      score: null,
    })),
    versions: { model_version: 'mock-no-encoder', index_version: 'mock-w1', config_version: 'mock-text-v1' },
  }, request)
}
