export interface AssetFilters {
  category?: string | null
  license?: string | null
  format?: string | null
  face_count_min?: number | null
  face_count_max?: number | null
}

export interface SearchRequest {
  query: string
  filters: AssetFilters
  page?: number
  limit: number
}

export interface AssetMetadata {
  asset_id: string
  name: string
  description: string | null
  category: string | null
  tags: string[]
  formats: string[]
  face_count: number | null
  thumbnail_url: string | null
  source: string
  source_url: string | null
  author: string | null
  license: string | null
}

export interface SearchResult {
  rank: number
  asset: AssetMetadata
  retrieval_sources: string[]
  explanation: string
  score: number | null
}

export interface SearchResponse {
  pagination: { page: number; limit: number; total: number; pages: number; has_next: boolean }
  query_id: string
  search_event_id: string
  query: string
  results: SearchResult[]
  versions: {
    model_version: string
    index_version: string
    config_version: string
  }
}

export type MockScenario = 'success' | 'empty' | 'error'

export interface SearchClient {
  search(request: SearchRequest, signal: AbortSignal): Promise<SearchResponse>
}
