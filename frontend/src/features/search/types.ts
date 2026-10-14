export interface SearchRequest {
  query: string
  filters: Record<string, never>
  limit: number
}

export interface AssetMetadata {
  asset_id: string
  name: string
  description: string
  category: string
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
