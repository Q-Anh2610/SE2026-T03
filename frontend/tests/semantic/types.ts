// DTO tối thiểu cho assertions mạng thật; không thay đổi contract/client sản phẩm.
export interface LiveTextSearchResponse {
  mock: boolean
  query_id: string
  search_event_id: string
  versions: { dataset_snapshot: string }
  pagination: { page: number; total: number }
  results: Array<{
    asset: {
      asset_id: string; name: string; category: string | null; license: string | null
      formats: string[]; face_count: number | null
    }
  }>
}
