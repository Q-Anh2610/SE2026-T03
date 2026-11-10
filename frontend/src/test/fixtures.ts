import type { LiveSearchResponse, MockSearchResponse, SearchRequest } from '../features/search/types'

export function makeRequest(query = 'ghế gỗ', limit = 12): SearchRequest {
  return { query, filters: {}, limit, page: 1 }
}

export function makeResponse(query = 'ghế gỗ'): MockSearchResponse {
  return {
    mock: true,
    pagination: { page: 1, limit: 12, total: 1, pages: 1, has_next: false },
    query_id: 'test-query-01',
    search_event_id: 'test-event-01',
    query,
    results: [{
      rank: 1,
      asset: {
        asset_id: 'test-chair-01',
        name: 'Ghế gỗ kiểm thử',
        description: 'Metadata tự tạo dành riêng cho kiểm thử.',
        category: 'Nội thất',
        tags: ['ghế', 'gỗ'],
        formats: ['glb'],
        face_count: null,
        thumbnail_url: null,
        source: 'fixture',
        source_url: null,
        author: null,
        license: null,
      },
      retrieval_sources: ['test_metadata'],
      explanation: 'Giải thích minh họa cho kiểm thử.',
      score: null,
    }],
    versions: { model_version: 'test-model', index_version: 'test-index', config_version: 'test-config' },
  }
}

/** Simulates the live response shape; still test data, never evidence of real retrieval. */
export function makeLiveResponse(query = 'ghế gỗ'): LiveSearchResponse {
  const response = makeResponse(query)
  return {
    ...response,
    mock: false,
    query_id: '00000000-0000-4000-8000-000000000054',
    search_event_id: '00000000-0000-4000-8000-000000000054',
    results: response.results.map((result) => ({
      ...result, score: 0.25, retrieval_sources: ['clip_text_to_preview'],
    })),
    versions: { ...response.versions, dataset_snapshot: 'test-dataset-snapshot' },
  }
}

export function deferred<Value>() {
  let resolve!: (value: Value) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<Value>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}
