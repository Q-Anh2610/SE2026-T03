import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { getSearchClient } from '../../lib/api/search'
import { AssetCard } from './AssetCard'
import { DiscoveryGallery } from './DiscoveryGallery'
import { SearchBackdrop } from './SearchBackdrop'
import { validateRequest } from './contract'
import type { SearchRequest, SearchResponse } from './types'
import './SearchPage.css'

type SearchState =
  | { status: 'idle' }
  | { status: 'loading'; query: string }
  | { status: 'success'; response: SearchResponse }
  | { status: 'error'; message: string }

export function SearchPage() {
  const [query, setQuery] = useState('')
  const [limit, setLimit] = useState(12)
  const [category, setCategory] = useState('')
  const [formError, setFormError] = useState('')
  const [state, setState] = useState<SearchState>({ status: 'idle' })
  const controller = useRef<AbortController | null>(null)
  const lastRequest = useRef<SearchRequest | null>(null)
  const queryInput = useRef<HTMLInputElement | null>(null)

  useEffect(() => () => controller.current?.abort(), [])

  async function search(input: SearchRequest) {
    let request: SearchRequest
    try {
      request = validateRequest(input)
    } catch (error) {
      setFormError(error instanceof Error ? error.message : 'Yêu cầu tìm kiếm không hợp lệ.')
      queryInput.current?.focus()
      return
    }
    controller.current?.abort()
    const currentController = new AbortController()
    controller.current = currentController
    lastRequest.current = request
    setFormError('')
    setState({ status: 'loading', query: request.query })
    try {
      const client = await getSearchClient('success')
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
    void search({ query, filters: {}, limit })
  }

  function retry() {
    if (lastRequest.current) {
      void search(lastRequest.current)
    }
  }

  function clearQuery() {
    controller.current?.abort()
    lastRequest.current = null
    setQuery('')
    setFormError('')
    setState({ status: 'idle' })
    queryInput.current?.focus()
  }

  function resetSearch() {
    clearQuery()
    setCategory('')
  }

  function clearFilter() {
    setCategory('')
    queryInput.current?.focus()
  }

  const results = state.status === 'success' ? state.response.results : []
  const categories = [...new Set(results.map(({ asset }) => asset.category).filter((value): value is string => Boolean(value)))]
  if (category && !categories.includes(category)) categories.push(category)
  const visibleResults = results.filter(({ asset }) => !category || asset.category === category)

  return (
    <div className={`search-page${state.status === 'idle' ? ' is-discovering' : ' has-search'}`}>
      <section className="search-intro" aria-labelledby="search-title">
        {state.status === 'idle' && <SearchBackdrop />}
        <div className="intro-copy visually-hidden">
          <h1 id="search-title">Thư viện 3D</h1>
        </div>
        <section id="search-panel" className="search-panel" aria-label="Tìm kiếm asset">
          <form onSubmit={submit} noValidate role="search">
            <label className="visually-hidden" htmlFor="asset-query">Bạn đang tìm asset nào?</label>
            <div className="search-field"><div className="input-wrap">
              <svg className="search-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></svg>
              <input id="asset-query" ref={queryInput} type="search" value={query} onChange={(event) => { setQuery(event.target.value); setFormError('') }} placeholder="Tìm asset 3D…" maxLength={1000} aria-invalid={Boolean(formError)} aria-describedby={formError ? 'query-error' : undefined} />
            </div>{query && <button className="clear-query" type="button" onClick={clearQuery} aria-label="Xóa truy vấn"><span aria-hidden="true">×</span></button>}<button className="search-submit" type="submit" disabled={state.status === 'loading'} aria-label={state.status === 'loading' ? 'Đang tìm…' : 'Tìm kiếm'}><svg className={state.status === 'loading' ? 'search-spinner' : undefined} width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">{state.status === 'loading' ? <path d="M20 12a8 8 0 1 1-8-8" /> : <path d="M5 12h14m-6-6 6 6-6 6" />}</svg></button></div>
            {formError && <p id="query-error" className="field-error" role="alert">{formError}</p>}
          </form>
        </section>
      </section>
      <div role="status" aria-live="polite" aria-atomic="true" className="visually-hidden">{state.status === 'loading' && `Đang tìm kết quả cho “${state.query}”…`}{state.status === 'success' && `Có ${visibleResults.length} kết quả cho “${state.response.query}”.`}</div>
      {state.status === 'idle' && <>
        {category && <div className="active-filter"><span>Đang lọc: <strong>{category}</strong> · chỉ trong kết quả đã nhận</span><button type="button" onClick={clearFilter}>Xóa bộ lọc</button></div>}
        <DiscoveryGallery />
      </>}
      {state.status !== 'idle' && <section className="results-section" aria-labelledby="results-title" aria-busy={state.status === 'loading'}>
        <div className="results-heading">
          <div className="results-summary"><h2 id="results-title">Kết quả tìm kiếm</h2>{state.status === 'success' && <p>{visibleResults.length} / {results.length} asset trong kết quả</p>}</div>
          <label className="limit-label" htmlFor="limit"><span className="visually-hidden">Số kết quả</span><select id="limit" value={limit} onChange={(event) => setLimit(Number(event.target.value))}><option value={6}>6 asset</option><option value={12}>12 asset</option><option value={24}>24 asset</option></select></label>
        </div>
        {(state.status === 'success' || category) && <div className="category-tabs" role="group" aria-label="Lọc danh mục trong kết quả"><button type="button" aria-pressed={!category} onClick={() => setCategory('')}>Tất cả</button>{categories.map((value) => <button type="button" key={value} aria-pressed={category === value} onClick={() => setCategory(value)}>{value}</button>)}</div>}
        {category && <div className="active-filter"><span>Đang lọc: <strong>{category}</strong> · chỉ trong kết quả đã nhận</span><button type="button" onClick={clearFilter}>Xóa bộ lọc</button></div>}
        {state.status === 'loading' && <><p className="loading-message" aria-hidden="true">Đang tìm asset…</p><div className="loading-grid" aria-hidden="true">{[1, 2, 3].map((value) => <div className="skeleton-card" key={value}><div /><span /><span /></div>)}</div></>}
        {state.status === 'error' && <div className="empty-state error-state" role="alert"><h3>Chưa thể lấy kết quả</h3><p>{state.message}</p><button className="primary-button" type="button" onClick={retry}>Thử lại</button></div>}
        {state.status === 'success' && visibleResults.length === 0 && <div className="empty-state"><h3>Chưa có asset phù hợp</h3><p>Thử mô tả ngắn hơn hoặc xóa bộ lọc đang chọn.</p><button type="button" onClick={resetSearch}>Xóa tìm kiếm và bộ lọc</button></div>}
        {state.status === 'success' && visibleResults.length > 0 && <ul className="asset-grid" aria-label="Kết quả asset">{visibleResults.map((result) => <AssetCard key={`${state.response.search_event_id}-${result.asset.asset_id}`} result={result} />)}</ul>}
        {state.status === 'success' && <details className="response-details"><summary>Thông tin phiên tìm kiếm</summary><dl><div><dt>Query ID</dt><dd>{state.response.query_id}</dd></div><div><dt>Event ID</dt><dd>{state.response.search_event_id}</dd></div><div><dt>Model</dt><dd>{state.response.versions.model_version}</dd></div><div><dt>Index</dt><dd>{state.response.versions.index_version}</dd></div><div><dt>Cấu hình</dt><dd>{state.response.versions.config_version}</dd></div></dl></details>}
      </section>}
    </div>
  )
}
