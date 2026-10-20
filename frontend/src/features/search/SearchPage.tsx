import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { getAssetClient, getSearchClient } from '../../lib/api/search'
import { AssetDetailView, type DetailState } from '../assets/AssetDetailView'
import { AssetCard } from './AssetCard'
import { buildFilterDraft, EMPTY_FILTER_FORM, validateListQuery, validateRequest } from './contract'
import { DiscoveryGallery } from './DiscoveryGallery'
import { SearchBackdrop } from './SearchBackdrop'
import type { AssetListQuery, AssetListResponse, SearchRequest, SearchResponse } from './types'
import './SearchPage.css'

type SearchState =
  | { status: 'idle' }
  | { status: 'loading'; query: string }
  | { status: 'browsing-loading' }
  | { status: 'success'; response: SearchResponse }
  | { status: 'browsing'; response: AssetListResponse }
  | { status: 'error'; message: string; source: 'search' | 'browse' }

function isNotFoundError(error: unknown): error is { kind: 'not_found'; message: string } {
  return typeof error === 'object' && error !== null && (error as { kind?: unknown }).kind === 'not_found'
    && typeof (error as { message?: unknown }).message === 'string'
}

export function SearchPage() {
  const [query, setQuery] = useState('')
  const [limit, setLimit] = useState(12)
  const [category, setCategory] = useState('')
  const [filters, setFilters] = useState({ ...EMPTY_FILTER_FORM })
  const [formError, setFormError] = useState('')
  const [state, setState] = useState<SearchState>({ status: 'idle' })
  const [detailState, setDetailState] = useState<DetailState | null>(null)
  const controller = useRef<AbortController | null>(null)
  const detailController = useRef<AbortController | null>(null)
  const lastRequest = useRef<SearchRequest | null>(null)
  const lastListQuery = useRef<AssetListQuery | null>(null)
  const queryInput = useRef<HTMLInputElement | null>(null)

  useEffect(() => () => {
    controller.current?.abort()
    detailController.current?.abort()
  }, [])

  async function openDetail(assetId: string) {
    detailController.current?.abort()
    const currentController = new AbortController()
    detailController.current = currentController
    setDetailState({ status: 'loading', assetId })
    try {
      const client = await getAssetClient('success')
      if (currentController.signal.aborted) return
      const response = await client.getAsset(assetId, currentController.signal)
      if (!currentController.signal.aborted) setDetailState({ status: 'success', asset: response.asset })
    } catch (error) {
      if (currentController.signal.aborted) return
      if (isNotFoundError(error)) {
        setDetailState({ status: 'not_found', assetId, message: error.message })
      } else {
        setDetailState({
          status: 'error',
          assetId,
          message: error instanceof Error ? error.message : 'Không thể tải chi tiết asset. Hãy thử lại.',
        })
      }
    }
  }

  function closeDetail() {
    detailController.current?.abort()
    setDetailState(null)
  }

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
    detailController.current?.abort()
    const currentController = new AbortController()
    controller.current = currentController
    lastRequest.current = request
    setDetailState(null)
    setFormError('')
    setState({ status: 'loading', query: request.query })
    try {
      const client = await getSearchClient('success')
      if (currentController.signal.aborted) return
      const response = await client.search(request, currentController.signal)
      if (!currentController.signal.aborted) setState({ status: 'success', response })
    } catch (error) {
      if (!currentController.signal.aborted) {
        setState({ status: 'error', message: error instanceof Error ? error.message : 'Không thể tìm kiếm. Hãy thử lại.', source: 'search' })
      }
    }
  }

  async function loadAssetCatalog(input: AssetListQuery) {
    let normalized: AssetListQuery
    try {
      normalized = validateListQuery(input)
    } catch (error) {
      setFormError((error as Error).message)
      queryInput.current?.focus()
      return
    }
    controller.current?.abort()
    detailController.current?.abort()
    const currentController = new AbortController()
    controller.current = currentController
    lastListQuery.current = normalized
    setDetailState(null)
    setFormError('')
    setState({ status: 'browsing-loading' })
    try {
      const client = await getAssetClient('success')
      if (currentController.signal.aborted) return
      const response = await client.listAssets(normalized, currentController.signal)
      if (!currentController.signal.aborted) setState({ status: 'browsing', response })
    } catch (error) {
      if (!currentController.signal.aborted) {
        setState({ status: 'error', message: error instanceof Error ? error.message : 'Không thể tải danh sách asset. Hãy thử lại.', source: 'browse' })
      }
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const draftFilters = buildFilterDraft(filters)
    const isBrowseContext = state.status === 'browsing' || state.status === 'browsing-loading'
      || (state.status === 'error' && state.source === 'browse')
    if (query.trim() === '' && (isBrowseContext || Object.keys(draftFilters).length > 0)) {
      void loadAssetCatalog({ filters: draftFilters, limit, page: 1 })
      return
    }
    void search({ query, filters: draftFilters, limit, page: 1 })
  }

  function retry() {
    if (state.status === 'error' && state.source === 'browse') {
      void loadAssetCatalog(lastListQuery.current!)
      return
    }
    void search(lastRequest.current!)
  }

  function clearQuery() {
    controller.current?.abort()
    detailController.current?.abort()
    lastRequest.current = null
    lastListQuery.current = null
    setDetailState(null)
    setQuery('')
    setFormError('')
    setState({ status: 'idle' })
    queryInput.current?.focus()
  }

  function resetSearch() {
    clearQuery()
    setCategory('')
    setFilters({ ...EMPTY_FILTER_FORM })
  }

  function clearApiFilters() {
    setFilters({ ...EMPTY_FILTER_FORM })
    setFormError('')
    if (state.status === 'browsing' || (state.status === 'error' && state.source === 'browse')) {
      void loadAssetCatalog({ filters: {}, limit, page: 1 })
    } else if (state.status === 'success') {
      void search({ ...lastRequest.current!, filters: {}, limit, page: 1 })
    }
  }

  function clearFilter() {
    setCategory('')
    queryInput.current?.focus()
  }

  function changeLimit(nextLimit: number) {
    setLimit(nextLimit)
    if (state.status === 'browsing') {
      void loadAssetCatalog({ ...lastListQuery.current!, limit: nextLimit, page: 1 })
    }
  }

  const isCatalogView = state.status === 'browsing' || state.status === 'browsing-loading'
    || (state.status === 'error' && state.source === 'browse')
  const results = state.status === 'success' ? state.response.results : []
  const catalogItems = state.status === 'browsing' ? state.response.items : []
  const sourceAssets = state.status === 'success' ? results.map(({ asset }) => asset) : catalogItems
  const categories = [...new Set(sourceAssets.map((asset) => asset.category).filter((value): value is string => Boolean(value)))]
  if (category && !categories.includes(category)) categories.push(category)
  const visibleResults = results.filter(({ asset }) => !category || asset.category === category)
  const visibleCatalogItems = catalogItems.filter((asset) => !category || asset.category === category)
  const visibleCount = state.status === 'success' ? visibleResults.length : visibleCatalogItems.length
  const pageCount = state.status === 'success' ? results.length : catalogItems.length
  const pagination = state.status === 'success' || state.status === 'browsing' ? state.response.pagination : null
  const isBusy = state.status === 'loading' || state.status === 'browsing-loading'
  const activeDetailId = detailState ? (detailState.status === 'success' ? detailState.asset.asset_id : detailState.assetId) : null

  return (
    <div className={`search-page${state.status === 'idle' && !detailState ? ' is-discovering' : ' has-search'}`}>
      {detailState && activeDetailId ? (
        <AssetDetailView
          key={activeDetailId}
          state={detailState}
          onRetry={() => { void openDetail(activeDetailId) }}
          onBack={closeDetail}
        />
      ) : (
        <>
          <section className="search-intro" aria-labelledby="search-title">
            {state.status === 'idle' && <SearchBackdrop />}
            <div className="intro-copy visually-hidden">
              <h1 id="search-title">Thư viện 3D</h1>
            </div>
            <section id="search-panel" className="search-panel" aria-label="Tìm kiếm asset">
              <form id="asset-search" onSubmit={submit} noValidate role="search">
                <label className="visually-hidden" htmlFor="asset-query">Bạn đang tìm asset nào?</label>
                <div className="search-field"><div className="input-wrap">
                  <svg className="search-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></svg>
                  <input id="asset-query" ref={queryInput} type="search" value={query} onChange={(event) => { setQuery(event.target.value); setFormError('') }} placeholder="Tìm asset 3D…" maxLength={1000} aria-invalid={Boolean(formError)} aria-describedby={formError ? 'query-error' : undefined} />
                </div>{query && <button className="clear-query" type="button" onClick={clearQuery} aria-label="Xóa truy vấn"><span aria-hidden="true">×</span></button>}<button className="search-submit" type="submit" disabled={isBusy} aria-label={isBusy ? 'Đang tìm…' : 'Tìm kiếm'}><svg className={isBusy ? 'search-spinner' : undefined} width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">{isBusy ? <path d="M20 12a8 8 0 1 1-8-8" /> : <path d="M5 12h14m-6-6 6 6-6 6" />}</svg></button></div>
                {formError && <p id="query-error" className="field-error" role="alert">{formError}</p>}
                <div className="search-controls-row">
                  <details className="search-filters">
                    <summary>Bộ lọc</summary>
                    <p className="filter-scope-note">Bộ lọc API (kết hợp AND, áp dụng trước phân trang)</p>
                    <div className="filter-fields">
                      {([['category', 'Danh mục'], ['format', 'Định dạng'], ['license', 'License'], ['face_count_min', 'Số mặt tối thiểu'], ['face_count_max', 'Số mặt tối đa']] as const).map(([key, label]) => (
                        <label key={key} htmlFor={`filter-${key}`}>{label}<input id={`filter-${key}`} type={key.startsWith('face_count_') ? 'number' : 'text'} min={0} step={1} value={filters[key]} onChange={(event) => { setFilters({ ...filters, [key]: event.target.value }); setFormError('') }} /></label>
                      ))}
                    </div>
                    <div className="filter-actions">
                      <button type="submit" disabled={isBusy}>Áp dụng bộ lọc</button>
                      <button type="button" disabled={isBusy} onClick={clearApiFilters}>Đặt lại bộ lọc API</button>
                    </div>
                  </details>
                  <button
                    type="button"
                    className="browse-catalog-button"
                    disabled={isBusy}
                    onClick={() => { void loadAssetCatalog({ filters: buildFilterDraft(filters), limit, page: 1 }) }}
                  >
                    Danh sách asset
                  </button>
                </div>
              </form>
            </section>
          </section>
          <div role="status" aria-live="polite" aria-atomic="true" className="visually-hidden">
            {state.status === 'loading' && `Đang tìm kết quả cho “${state.query}”…`}
            {state.status === 'browsing-loading' && 'Đang tải danh sách asset…'}
            {state.status === 'success' && `Có ${visibleResults.length} kết quả cho “${state.response.query}”.`}
            {state.status === 'browsing' && `Đang hiển thị ${visibleCatalogItems.length} asset trong danh sách.`}
          </div>
          {state.status === 'idle' && <>
            {category && <div className="active-filter"><span>Đang lọc: <strong>{category}</strong> · chỉ trong trang đã nhận</span><button type="button" onClick={clearFilter}>Xóa bộ lọc</button></div>}
            <DiscoveryGallery />
          </>}
          {state.status !== 'idle' && <section className="results-section" aria-labelledby="results-title" aria-busy={isBusy}>
            <div className="results-heading">
              <div className="results-summary">
                <h2 id="results-title">{isCatalogView ? 'Danh sách asset' : 'Kết quả tìm kiếm'}</h2>
                {(state.status === 'success' || state.status === 'browsing') && (
                  <p>{visibleCount} / {pageCount} asset trong {isCatalogView ? 'trang' : 'kết quả'}</p>
                )}
              </div>
              <label className="limit-label" htmlFor="limit"><span className="visually-hidden">Số kết quả</span><select id="limit" value={limit} onChange={(event) => changeLimit(Number(event.target.value))}><option value={2}>2 asset</option><option value={6}>6 asset</option><option value={12}>12 asset</option><option value={24}>24 asset</option></select></label>
            </div>
            {(state.status === 'success' || state.status === 'browsing' || category) && <div className="category-tabs" role="group" aria-label="Lọc danh mục trong trang"><button type="button" aria-pressed={!category} onClick={() => setCategory('')}>Tất cả</button>{categories.map((value) => <button type="button" key={value} aria-pressed={category === value} onClick={() => setCategory(value)}>{value}</button>)}</div>}
            {category && <div className="active-filter"><span>Đang lọc: <strong>{category}</strong> · chỉ trong trang đã nhận</span><button type="button" onClick={clearFilter}>Xóa bộ lọc</button></div>}
            {isBusy && <><p className="loading-message" aria-hidden="true">{state.status === 'browsing-loading' ? 'Đang tải danh sách asset…' : 'Đang tìm asset…'}</p><div className="loading-grid" aria-hidden="true">{[1, 2, 3].map((value) => <div className="skeleton-card" key={value}><div /><span /><span /></div>)}</div></>}
            {state.status === 'error' && <div className="empty-state error-state" role="alert"><h3>Chưa thể lấy kết quả</h3><p>{state.message}</p><button className="primary-button" type="button" onClick={retry}>Thử lại</button></div>}
            {(state.status === 'success' || state.status === 'browsing') && visibleCount === 0 && <div className="empty-state"><h3>Chưa có asset phù hợp</h3><p>Thử mô tả ngắn hơn hoặc xóa bộ lọc đang chọn.</p><button type="button" onClick={resetSearch}>Xóa tìm kiếm và bộ lọc</button></div>}
            {state.status === 'success' && visibleResults.length > 0 && (
              <ul className="asset-grid" aria-label="Kết quả asset">
                {visibleResults.map((result) => (
                  <AssetCard
                    key={`${state.response.search_event_id}-${result.asset.asset_id}`}
                    result={result}
                    onOpenDetail={(assetId) => { void openDetail(assetId) }}
                  />
                ))}
              </ul>
            )}
            {state.status === 'browsing' && visibleCatalogItems.length > 0 && (
              <ul className="asset-grid" aria-label="Kết quả asset">
                {visibleCatalogItems.map((asset) => (
                  <AssetCard
                    key={asset.asset_id}
                    asset={asset}
                    onOpenDetail={(assetId) => { void openDetail(assetId) }}
                  />
                ))}
              </ul>
            )}
            {pagination && <nav className="search-pagination" aria-label="Phân trang kết quả">
              <button
                type="button"
                disabled={pagination.page <= 1}
                onClick={() => {
                  if (state.status === 'browsing') {
                    void loadAssetCatalog({ ...lastListQuery.current!, page: pagination.page - 1 })
                  } else {
                    void search({ ...lastRequest.current!, page: pagination.page - 1 })
                  }
                }}
              >
                Trang trước
              </button>
              <span>Trang {pagination.page} / {Math.max(1, pagination.pages)} · {pagination.total} kết quả</span>
              <button
                type="button"
                disabled={!pagination.has_next}
                onClick={() => {
                  if (state.status === 'browsing') {
                    void loadAssetCatalog({ ...lastListQuery.current!, page: pagination.page + 1 })
                  } else {
                    void search({ ...lastRequest.current!, page: pagination.page + 1 })
                  }
                }}
              >
                Trang sau
              </button>
            </nav>}
            {state.status === 'success' && <details className="response-details"><summary>Thông tin phiên tìm kiếm</summary><dl><div><dt>Query ID</dt><dd>{state.response.query_id}</dd></div><div><dt>Event ID</dt><dd>{state.response.search_event_id}</dd></div><div><dt>Model</dt><dd>{state.response.versions.model_version}</dd></div><div><dt>Index</dt><dd>{state.response.versions.index_version}</dd></div><div><dt>Cấu hình</dt><dd>{state.response.versions.config_version}</dd></div></dl></details>}
          </section>}
        </>
      )}
    </div>
  )
}
