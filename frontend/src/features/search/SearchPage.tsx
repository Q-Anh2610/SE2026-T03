import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { getSearchClient, isMockMode } from '../../lib/api/search'
import { AssetCard } from './AssetCard'
import { validateRequest } from './contract'
import type { MockScenario, SearchRequest, SearchResponse } from './types'

type SearchState =
  | { status: 'idle' }
  | { status: 'loading'; query: string }
  | { status: 'success'; response: SearchResponse }
  | { status: 'error'; message: string }

const suggestions = ['Ghế gỗ', 'Đèn bàn', 'Thùng gỗ']

export function SearchPage() {
  const [query, setQuery] = useState('')
  const [limit, setLimit] = useState(12)
  const [scenario, setScenario] = useState<MockScenario>('success')
  const [formError, setFormError] = useState('')
  const [state, setState] = useState<SearchState>({ status: 'idle' })
  const controller = useRef<AbortController | null>(null)
  const lastRequest = useRef<SearchRequest | null>(null)
  const textarea = useRef<HTMLTextAreaElement | null>(null)

  useEffect(() => () => controller.current?.abort(), [])

  async function search(input: SearchRequest, selectedScenario: MockScenario) {
    let request: SearchRequest
    try {
      request = validateRequest(input)
    } catch (error) {
      setFormError(error instanceof Error ? error.message : 'Yêu cầu tìm kiếm không hợp lệ.')
      textarea.current?.focus()
      return
    }
    controller.current?.abort()
    const currentController = new AbortController()
    controller.current = currentController
    lastRequest.current = request
    setFormError('')
    setState({ status: 'loading', query: request.query })
    try {
      const client = await getSearchClient(selectedScenario)
      if (currentController.signal.aborted) return
      const response = await client.search(request, currentController.signal)
      if (!currentController.signal.aborted) setState({ status: 'success', response })
    } catch (error) {
      if (!currentController.signal.aborted) {
        setState({ status: 'error', message: error instanceof Error ? error.message : 'Không thể tìm kiếm. Hãy thử lại.' })
      }
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void search({ query, filters: {}, limit }, scenario)
  }

  function retry() {
    if (lastRequest.current) {
      if (isMockMode) setScenario('success')
      void search(lastRequest.current, 'success')
    }
  }

  function chooseSuggestion(suggestion: string) {
    setQuery(suggestion)
    void search({ query: suggestion, filters: {}, limit }, scenario)
  }

  return (
    <>
      <a className="skip-link" href="#main">Đến nội dung chính</a>
      <header className="site-header">
        <a className="brand" href="#main" aria-label="Thư viện 3D, đến nội dung chính">
          <span className="brand-mark" aria-hidden="true">3D</span>
          <span>Thư viện 3D<span className="brand-team">SE2026-T03</span></span>
        </a>
        <span className="header-label">Tìm kiếm asset</span>
      </header>
      {isMockMode && (
        <aside className="mock-banner" aria-label="Chế độ dữ liệu">
          <span className="mock-tag">Bản minh họa W1</span>
          Dữ liệu tự tạo, chưa kết nối API hoặc mô hình tìm kiếm.
        </aside>
      )}
      <main id="main" className="page-shell">
        <section className="search-intro" aria-labelledby="page-title">
          <div>
            <h1 id="page-title">Tìm chất liệu cho<br />ý tưởng của bạn.</h1>
            <p>Mô tả món đồ bạn cần. Khám phá asset 3D và xem thông tin nguồn ngay trong kết quả.</p>
          </div>
          <div className="intro-object" aria-hidden="true">
            <div className="coordinate-grid" />
            <div className="placeholder-object"><span /><span /><span /></div>
          </div>
        </section>
        <section className="search-panel" aria-label="Tìm kiếm văn bản">
          <form onSubmit={submit} noValidate>
            <label htmlFor="query" className="query-label">Bạn đang tìm asset nào?</label>
            <div className="query-row">
              <textarea id="query" ref={textarea} value={query} rows={2} maxLength={1000}
                placeholder="Ví dụ: ghế gỗ, đèn bàn, thùng gỗ…"
                onChange={(event) => { setQuery(event.target.value); setFormError('') }}
                aria-invalid={Boolean(formError)} aria-describedby={formError ? 'query-help query-error' : 'query-help'} />
              <button type="submit" className="primary-button" disabled={state.status === 'loading'}>
                {state.status === 'loading' ? 'Đang tìm…' : 'Tìm kiếm'}
              </button>
            </div>
            <p id="query-help" className="field-hint">Nhập từ 1 đến 500 ký tự. Tìm kiếm bằng văn bản.</p>
            {formError && <p id="query-error" className="field-error" role="alert">{formError}</p>}
            <div className="search-options">
              <div className="suggestions"><span>Thử tìm:</span>{suggestions.map((suggestion) => (
                <button type="button" key={suggestion} onClick={() => chooseSuggestion(suggestion)}>{suggestion}</button>
              ))}</div>
              <label className="limit-label" htmlFor="limit">Số kết quả
                <select id="limit" value={limit} onChange={(event) => setLimit(Number(event.target.value))}>
                  <option value={6}>6</option><option value={12}>12</option><option value={24}>24</option>
                </select>
              </label>
            </div>
          </form>
          {isMockMode && (
            <details className="mock-controls">
              <summary>Thử trạng thái giao diện</summary>
              <label htmlFor="scenario">Kịch bản lần tìm tiếp theo
                <select id="scenario" value={scenario} onChange={(event) => setScenario(event.target.value as MockScenario)}>
                  <option value="success">Bình thường</option><option value="empty">Không có kết quả</option>
                  <option value="error">Lỗi kết nối</option>
                </select>
              </label>
              <p>Chỉ có trong mock phát triển. Các kịch bản không phản ánh chất lượng tìm kiếm thật.</p>
            </details>
          )}
        </section>
        <section className="results-section" aria-labelledby="results-title" aria-busy={state.status === 'loading'}>
          <div className="results-heading"><h2 id="results-title">Kết quả tìm kiếm</h2>
            {state.status === 'success' && <span>{state.response.results.length} asset</span>}
          </div>
          <div className="result-announcement" role="status" aria-live="polite" aria-atomic="true">
            {state.status === 'loading' && `Đang tìm kết quả cho “${state.query}”…`}
            {state.status === 'success' && `Có ${state.response.results.length} kết quả cho “${state.response.query}”.`}
          </div>
          {state.status === 'idle' && (
            <div className="empty-state"><div className="empty-symbol" aria-hidden="true">⌕</div>
              <h3>Bắt đầu từ một mô tả</h3><p>Nhập tên món đồ hoặc chọn gợi ý ở trên để xem kết quả.</p>
              {isMockMode && <p className="state-detail">Bộ minh họa gồm 6 bản ghi nội thất, đồ gia dụng và game props.</p>}
            </div>
          )}
          {state.status === 'loading' && (
            <div className="loading-grid" aria-hidden="true">{[1, 2, 3].map((placeholder) => (
              <div className="skeleton-card" key={placeholder}><div /><span /><span /></div>
            ))}</div>
          )}
          {state.status === 'error' && (
            <div className="empty-state error-state" role="alert"><h3>Chưa thể lấy kết quả</h3>
              <p>{state.message}</p><button className="primary-button" type="button" onClick={retry}>Thử lại</button>
            </div>
          )}
          {state.status === 'success' && state.response.results.length === 0 && (
            <div className="empty-state"><h3>Chưa có asset phù hợp</h3>
              <p>Thử mô tả ngắn hơn, tên món đồ khác hoặc một gợi ý ở trên.</p>
              {isMockMode && <p className="state-detail">Mock chỉ khớp từ khóa trong metadata của 6 bản ghi.</p>}
            </div>
          )}
          {state.status === 'success' && state.response.results.length > 0 && (
            <ul className="asset-grid">{state.response.results.map((result) => (
              <AssetCard key={`${state.response.search_event_id}-${result.asset.asset_id}`} result={result} />
            ))}</ul>
          )}
          {state.status === 'success' && (
            <details className="response-details"><summary>Thông tin phiên tìm kiếm</summary>
              <dl>
                <div><dt>Query ID</dt><dd>{state.response.query_id}</dd></div>
                <div><dt>Event ID</dt><dd>{state.response.search_event_id}</dd></div>
                <div><dt>Model</dt><dd>{state.response.versions.model_version}</dd></div>
                <div><dt>Index</dt><dd>{state.response.versions.index_version}</dd></div>
                <div><dt>Cấu hình</dt><dd>{state.response.versions.config_version}</dd></div>
              </dl>
            </details>
          )}
        </section>
      </main>
      <footer className="site-footer"><span>Thư viện 3D · SE2026-T03</span>
        <span>{isMockMode ? 'Prototype tuần 1 · dữ liệu minh họa' : 'Tìm kiếm thư viện asset 3D'}</span>
      </footer>
    </>
  )
}
