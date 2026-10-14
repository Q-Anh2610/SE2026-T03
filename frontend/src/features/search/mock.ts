import { parseResponse, validateRequest } from './contract'
import type { AssetMetadata, MockScenario, SearchClient } from './types'

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

function normalize(value: string): string {
  return value.toLocaleLowerCase('vi').normalize('NFD').replace(/\p{Diacritic}/gu, '').replace(/đ/g, 'd')
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
      const tokens = normalize(request.query).split(/\s+/).filter(Boolean)
      const selected = scenario === 'empty' ? [] : mockAssets.filter((asset) => {
        const haystack = normalize([asset.name, asset.category, ...asset.tags].join(' '))
        return tokens.every((token) => haystack.includes(token))
      }).slice(0, request.limit)
      return parseResponse({
        query_id: `mock-query-${crypto.randomUUID()}`,
        search_event_id: `mock-event-${crypto.randomUUID()}`,
        query: request.query,
        results: selected.map((asset, position) => ({
          rank: position + 1,
          asset: { ...asset, tags: [...asset.tags], formats: [...asset.formats] },
          retrieval_sources: ['mock_metadata'],
          explanation: 'Minh họa khớp từ khóa trong metadata; chưa chạy semantic search.',
          score: null,
        })),
        versions: { model_version: 'mock-no-encoder', index_version: 'mock-w1', config_version: 'mock-text-v1' },
      }, request)
    },
  }
}
