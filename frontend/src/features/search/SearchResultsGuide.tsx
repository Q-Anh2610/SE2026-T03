import type { SearchResult } from './types'

export function SearchResultsGuide({ results, mock }: { results: SearchResult[]; mock: boolean }) {
  if (results.length === 0) return null

  const hasCosineScore = results.some((result) => result.score_type === 'cosine')
  if (!mock && !hasCosineScore) return null

  return (
    <aside className="search-results-guide" aria-label="Cách đọc kết quả tìm kiếm">
      {mock ? (
        <p><strong>Kết quả minh họa.</strong> Feedback chỉ lưu tạm trong bộ nhớ, không dùng làm nhãn benchmark.</p>
      ) : (
        <p><strong>Điểm cosine:</strong> nằm trong −1 đến 1; điểm cao hơn biểu thị độ tương đồng cao hơn, không phải xác suất.</p>
      )}
    </aside>
  )
}
