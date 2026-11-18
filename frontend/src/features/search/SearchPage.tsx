import { useEffect, useRef, useState } from 'react'
import type { FormEvent, MouseEvent } from 'react'
import { getAssetClient, getSearchClient } from '../../lib/api/search'
import { AssetDetailView, type DetailState } from '../assets/AssetDetailView'
import { AssetCard } from './AssetCard'
import { buildFilterDraft, EMPTY_FILTER_FORM, validateListQuery, validateRequest, type FilterFormValues } from './contract'
import { DiscoveryGallery } from './DiscoveryGallery'
import { SearchResultsGuide } from './SearchResultsGuide'
import type { AssetFilters, AssetListQuery, AssetListResponse, SearchRequest, SearchResponse } from './types'
import './SearchPage.css'
import './SearchWorkbench.css'

type SearchState =
  | { status: 'idle' }
  | { status: 'loading'; query: string }
  | { status: 'browsing-loading' }
  | { status: 'success'; response: SearchResponse }
  | { status: 'browsing'; response: AssetListResponse }
  | { status: 'error'; message: string; source: 'search' | 'browse' }

type SearchUrlMode = 'search' | 'browse' | null
type SearchUrlHistory = 'push' | 'replace'

interface SearchUrlState {
  mode: SearchUrlMode
  query: string
  limit: number
  page: number
  facet: string
  filtersOpen: boolean
  filters: FilterFormValues
}

const FILTER_QUERY_PARAMS = [
  ['category', 'filter_category'],
  ['format', 'filter_format'],
  ['license', 'filter_license'],
  ['face_count_min', 'filter_face_count_min'],
  ['face_count_max', 'filter_face_count_max'],
] as const

function positiveIntegerParam(value: string | null, fallback: number) {
  const parsed = value === null ? Number.NaN : Number(value)
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : fallback
}

function readSearchUrlState(): SearchUrlState {
  const params = new URLSearchParams(window.location.search)
  const rawQuery = params.get('q') ?? ''
  const mode: SearchUrlMode = params.get('mode') === 'browse'
    ? 'browse'
    : params.get('mode') === 'search' && rawQuery ? 'search' : null
  const limit = positiveIntegerParam(params.get('limit'), 12)
  const filters: FilterFormValues = {
    category: params.get('filter_category') ?? '',
    format: params.get('filter_format') ?? '',
    license: params.get('filter_license') ?? '',
    face_count_min: params.get('filter_face_count_min') ?? '',
    face_count_max: params.get('filter_face_count_max') ?? '',
  }
  const hasFilters = Object.values(filters).some((value) => value.trim() !== '')

  return {
    mode,
    query: mode === 'browse' ? '' : rawQuery,
    limit: [2, 6, 12, 24].includes(limit) ? limit : 12,
    page: positiveIntegerParam(params.get('page'), 1),
    facet: params.get('facet') ?? '',
    filtersOpen: params.get('filters_open') === '1'
      || (params.get('filters_open') !== '0' && hasFilters),
    filters,
  }
}

function writeSearchUrlState(input: {
  mode: SearchUrlMode
  query?: string
  filters: AssetFilters
  limit: number
  page: number
  facet: string
  filtersOpen: boolean
  history?: SearchUrlHistory
}) {
  const url = new URL(window.location.href)
  const params = url.searchParams
  for (const key of ['q', 'mode', 'limit', 'page', 'facet', 'filters_open', ...FILTER_QUERY_PARAMS.map(([, param]) => param)]) {
    params.delete(key)
  }

  if (input.mode) params.set('mode', input.mode)
  if (input.mode === 'search' && input.query) params.set('q', input.query)
  if (input.limit !== 12) params.set('limit', String(input.limit))
  if (input.page > 1) params.set('page', String(input.page))
  if (input.facet) params.set('facet', input.facet)
  params.set('filters_open', input.filtersOpen ? '1' : '0')
  for (const [key, param] of FILTER_QUERY_PARAMS) {
    const value = input.filters[key]
    if (value !== null && value !== undefined && !(typeof value === 'number' && !Number.isFinite(value)) && String(value).trim() !== '') {
      params.set(param, String(value))
    }
  }

  const nextUrl = `${url.pathname}${url.search}${url.hash}`
  const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`
  if (nextUrl === currentUrl) return

  if (input.history === 'replace') {
    window.history.replaceState(window.history.state, '', nextUrl)
  } else {
    window.history.pushState(window.history.state, '', nextUrl)
  }
}

function isNotFoundError(error: unknown): error is { kind: 'not_found'; message: string } {
  return typeof error === 'object' && error !== null && (error as { kind?: unknown }).kind === 'not_found'
    && typeof (error as { message?: unknown }).message === 'string'
}

function assetGridClass(count: number) {
  return count <= 2 ? `asset-grid asset-grid--count-${count}` : 'asset-grid'
}

export function SearchPage() {
  const [initialUrlState] = useState(readSearchUrlState)
  const [query, setQuery] = useState(initialUrlState.query)
  const [limit, setLimit] = useState(initialUrlState.limit)
  const [category, setCategory] = useState(initialUrlState.facet)
  const [filters, setFilters] = useState({ ...initialUrlState.filters })
  const [formError, setFormError] = useState('')
  const [state, setState] = useState<SearchState>({ status: 'idle' })
  const [detailState, setDetailState] = useState<DetailState | null>(null)
  const controller = useRef<AbortController | null>(null)
  const detailController = useRef<AbortController | null>(null)
  const lastRequest = useRef<SearchRequest | null>(null)
  const lastListQuery = useRef<AssetListQuery | null>(null)
  const queryInput = useRef<HTMLInputElement | null>(null)
  const filtersDisclosure = useRef<HTMLDetailsElement | null>(null)
  const filtersSummary = useRef<HTMLElement | null>(null)

  function getFiltersOpen() {
    return Boolean(filtersDisclosure.current?.open)
  }

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

  async function search(input: SearchRequest, history: SearchUrlHistory = 'push', facet = category) {
    let request: SearchRequest
    try {
      request = validateRequest(input)
    } catch (error) {
      setFormError(error instanceof Error ? error.message : 'Yêu cầu tìm kiếm không hợp lệ.')
      queryInput.current?.focus()
      return
    }
    writeSearchUrlState({
      mode: 'search',
      query: request.query,
      filters: request.filters,
      limit: request.limit,
      page: request.page ?? 1,
      facet,
      filtersOpen: getFiltersOpen(),
      history,
    })
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

  async function loadAssetCatalog(input: AssetListQuery, history: SearchUrlHistory = 'push', facet = category) {
    let normalized: AssetListQuery
    try {
      normalized = validateListQuery(input)
    } catch (error) {
      setFormError((error as Error).message)
      queryInput.current?.focus()
      return
    }
    writeSearchUrlState({
      mode: 'browse',
      filters: normalized.filters,
      limit: normalized.limit,
      page: normalized.page ?? 1,
      facet,
      filtersOpen: getFiltersOpen(),
      history,
    })
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

  function clearQuery(history: SearchUrlHistory = 'push') {
    controller.current?.abort()
    detailController.current?.abort()
    lastRequest.current = null
    lastListQuery.current = null
    setDetailState(null)
    setQuery('')
    setFormError('')
    setState({ status: 'idle' })
    writeSearchUrlState({ mode: null, filters: buildFilterDraft(filters), limit, page: 1, facet: category, filtersOpen: getFiltersOpen(), history })
    queryInput.current?.focus()
  }

  function resetSearch() {
    clearQuery('replace')
    setCategory('')
    setFilters({ ...EMPTY_FILTER_FORM })
    writeSearchUrlState({ mode: null, filters: {}, limit, page: 1, facet: '', filtersOpen: false, history: 'replace' })
  }

  function clearApiFilters() {
    setFilters({ ...EMPTY_FILTER_FORM })
    setFormError('')
    if (state.status === 'browsing' || (state.status === 'error' && state.source === 'browse')) {
      void loadAssetCatalog({ filters: {}, limit, page: 1 })
    } else if (state.status === 'success' || (state.status === 'error' && state.source === 'search' && lastRequest.current)) {
      void search({ ...lastRequest.current!, filters: {}, limit, page: 1 })
    } else {
      writeSearchUrlState({ mode: null, filters: {}, limit, page: 1, facet: category, filtersOpen: getFiltersOpen() })
    }
  }

  function clearFilter() {
    updateCategoryFacet('')
    queryInput.current?.focus()
  }

  function selectSuggestedQuery(value: string) {
    setQuery(value)
    setFormError('')
    queryInput.current?.focus()
  }

  function openSearchFilters(event: MouseEvent<HTMLAnchorElement>) {
    const disclosure = filtersDisclosure.current
    const summary = filtersSummary.current
    if (!disclosure || !summary) return

    event.preventDefault()
    disclosure.open = true
    summary.scrollIntoView?.({ block: 'start' })
    summary.focus()
  }

  function changeLimit(nextLimit: number) {
    setLimit(nextLimit)
    if (state.status === 'browsing' || (state.status === 'error' && state.source === 'browse')) {
      void loadAssetCatalog({ ...lastListQuery.current!, limit: nextLimit, page: 1 })
    }
  }

  function updateCategoryFacet(nextCategory: string) {
    setCategory(nextCategory)
    const current = readSearchUrlState()
    writeSearchUrlState({
      ...current,
      filters: buildFilterDraft(current.mode === null ? filters : current.filters),
      limit: current.mode === null ? limit : current.limit,
      facet: nextCategory,
      filtersOpen: getFiltersOpen(),
    })
  }

  const restoreUrlStateRef = useRef<() => void>(() => {})
  const shouldLoadInitialUrlRef = useRef(initialUrlState.mode !== null)
  restoreUrlStateRef.current = () => {
    const next = readSearchUrlState()
    setQuery(next.query)
    setLimit(next.limit)
    setCategory(next.facet)
    setFilters(next.filters)
    setFormError('')
    setDetailState(null)
    if (filtersDisclosure.current) {
      filtersDisclosure.current.open = next.filtersOpen
    }

    if (next.mode === 'search' && next.query) {
      void search({ query: next.query, filters: buildFilterDraft(next.filters), limit: next.limit, page: next.page }, 'replace', next.facet)
    } else if (next.mode === 'browse') {
      void loadAssetCatalog({ filters: buildFilterDraft(next.filters), limit: next.limit, page: next.page }, 'replace', next.facet)
    } else {
      controller.current?.abort()
      detailController.current?.abort()
      lastRequest.current = null
      lastListQuery.current = null
      setState({ status: 'idle' })
    }
  }

  function syncFilterDisclosureUrl() {
    const current = readSearchUrlState()
    writeSearchUrlState({
      mode: current.mode,
      query: current.query,
      filters: buildFilterDraft(current.filters),
      limit: current.limit,
      page: current.page,
      facet: current.facet,
      filtersOpen: getFiltersOpen(),
      history: 'replace',
    })
  }

  useEffect(() => {
    const handlePopState = () => restoreUrlStateRef.current()
    window.addEventListener('popstate', handlePopState)
    if (shouldLoadInitialUrlRef.current) restoreUrlStateRef.current()
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

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
  const isBrowsing = state.status === 'browsing' || state.status === 'browsing-loading'
    || (state.status === 'error' && state.source === 'browse')
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
        <div className="search-workbench">
          <aside className="search-rail" aria-label="Công cụ tìm kiếm">
            <p className="rail-title">Không gian<br />tìm kiếm</p>
            <p className="rail-description">Tìm asset theo mô tả, hình tham chiếu hoặc thuộc tính.</p>
            <nav className="rail-nav" aria-label="Phương thức tìm kiếm">
              <p>PHƯƠNG THỨC</p>
              <a href="#asset-query" aria-current={!isBrowsing ? 'page' : undefined}><span>Mô tả bằng chữ</span><span className="rail-arrow" aria-hidden="true">↗</span></a>
              <a href="#image-search"><span>Tìm bằng ảnh</span><span className="rail-arrow" aria-hidden="true">↗</span></a>
              <button
                type="button"
                disabled={isBusy}
                aria-pressed={isBrowsing}
                onClick={() => { void loadAssetCatalog({ filters: buildFilterDraft(filters), limit, page: 1 }) }}
              >
                <span>Duyệt thư viện</span>
                <span className="rail-arrow" aria-hidden="true">↗</span>
              </button>
            </nav>
            <a className="rail-refine" href="#search-filters" onClick={openSearchFilters}>
              <span>LỌC THUỘC TÍNH</span>
              <strong>Danh mục, license,<br />định dạng và số mặt</strong>
              <span className="rail-refine-arrow" aria-hidden="true">↗</span>
            </a>
          </aside>
          <div className="search-main-content">
        <>
          <section className="search-intro" aria-labelledby="search-title">
            <div className="intro-copy">
              <p className="intro-eyebrow">TÌM KIẾM <span> / </span> MÔ HÌNH 3D</p>
              <h1 id="search-title">Tìm mô hình 3D <em>từ ý tưởng của bạn.</em></h1>
              <p className="intro-description">Mô tả hình dáng, vật liệu hay không gian. Tìm bằng ảnh khi bạn đã có hình tham chiếu.</p>
            </div>
            {state.status === 'idle' && <div className="hero-showcase" aria-hidden="true">
              <span className="hero-showcase-heading">Mẫu minh họa</span>
              <figure className="hero-sample hero-sample--arch">
                <img src={`${import.meta.env.BASE_URL}images/discovery/arch.webp`} alt="" width="768" height="768" />
                <figcaption>Vòm đá</figcaption>
              </figure>
              <figure className="hero-sample hero-sample--vase">
                <img src={`${import.meta.env.BASE_URL}images/discovery/vase.webp`} alt="" width="768" height="768" />
                <figcaption>Bình gốm</figcaption>
              </figure>
            </div>}
            <section id="search-panel" className="search-panel" aria-label="Tìm kiếm asset">
              <form id="asset-search" onSubmit={submit} noValidate role="search">
                <label className="visually-hidden" htmlFor="asset-query">Bạn đang tìm asset nào?</label>
                <div className="search-field"><div className="input-wrap">
                  <svg className="search-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></svg>
                  <input id="asset-query" ref={queryInput} name="query" type="search" autoComplete="off" value={query} onChange={(event) => { setQuery(event.target.value); setFormError('') }} placeholder="Ví dụ: ghế gỗ có lưng cong, đèn bàn màu xanh…" maxLength={1000} aria-invalid={Boolean(formError)} aria-describedby={formError ? 'query-error' : undefined} />
                </div>{query && <button className="clear-query" type="button" onClick={() => clearQuery()} aria-label="Xóa truy vấn"><span aria-hidden="true">×</span></button>}<button className="search-submit" type="submit" disabled={isBusy} aria-label={isBusy ? 'Đang tìm…' : 'Tìm kiếm'}><svg className={isBusy ? 'search-spinner' : undefined} width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">{isBusy ? <path d="M20 12a8 8 0 1 1-8-8" /> : <path d="M5 12h14m-6-6 6 6-6 6" />}</svg></button></div>
                {formError && <p id="query-error" className="field-error" role="alert">{formError}</p>}
                <div className="search-controls-row">
                  <details className="search-filters" id="search-filters" ref={filtersDisclosure} onToggle={syncFilterDisclosureUrl}>
                    <summary ref={filtersSummary}>Bộ lọc</summary>
                    <div className="filter-panel">
                      <p className="filter-scope-note">Bộ lọc API (kết hợp AND, áp dụng trước phân trang)</p>
                      <div className="filter-fields">
                        {([['category', 'Danh mục'], ['format', 'Định dạng'], ['license', 'License'], ['face_count_min', 'Số mặt tối thiểu'], ['face_count_max', 'Số mặt tối đa']] as const).map(([key, label]) => (
                          <label key={key} htmlFor={`filter-${key}`}>{label}<input id={`filter-${key}`} name={key} autoComplete="off" type={key.startsWith('face_count_') ? 'number' : 'text'} min={0} step={1} value={filters[key]} onChange={(event) => { setFilters({ ...filters, [key]: event.target.value }); setFormError('') }} /></label>
                        ))}
                      </div>
                      <div className="filter-actions">
                        <button type="submit" disabled={isBusy}>Áp dụng bộ lọc</button>
                        <button type="button" disabled={isBusy} onClick={clearApiFilters}>Đặt lại bộ lọc API</button>
                      </div>
                    </div>
                  </details>
                  <button
                    type="button"
                    className="browse-catalog-button"
                    id="browse-catalog"
                    disabled={isBusy}
                    onClick={() => { void loadAssetCatalog({ filters: buildFilterDraft(filters), limit, page: 1 }) }}
                  >
                    Danh sách asset
                  </button>
                </div>
                <a className="image-search-link" href="#image-search">
                  Tìm bằng ảnh <span aria-hidden="true">↗</span>
                </a>
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
            <DiscoveryGallery onSelectQuery={selectSuggestedQuery} />
          </>}
          {state.status !== 'idle' && <section className="results-section" aria-labelledby="results-title" aria-busy={isBusy}>
            <div className="results-heading">
              <div className="results-summary">
                <h2 id="results-title">{isCatalogView ? 'Danh sách asset' : 'Kết quả tìm kiếm'}</h2>
                {(state.status === 'success' || state.status === 'browsing') && (
                  <p>{visibleCount} / {pageCount} asset trong {isCatalogView ? 'trang' : 'kết quả'}</p>
                )}
              </div>
            <label className="limit-label" htmlFor="limit"><span className="visually-hidden">Số kết quả</span><select id="limit" value={limit} disabled={isBusy} onChange={(event) => changeLimit(Number(event.target.value))}><option value={2}>2 asset</option><option value={6}>6 asset</option><option value={12}>12 asset</option><option value={24}>24 asset</option></select></label>
            </div>
            {(state.status === 'success' || state.status === 'browsing' || category) && <div className="category-tabs" role="group" aria-label="Lọc danh mục trong trang"><button type="button" aria-pressed={!category} onClick={() => updateCategoryFacet('')}>Tất cả</button>{categories.map((value) => <button type="button" key={value} aria-pressed={category === value} onClick={() => updateCategoryFacet(value)}>{value}</button>)}</div>}
            {state.status === 'success' && <SearchResultsGuide results={visibleResults} mock={state.response.mock} />}
            {category && <div className="active-filter"><span>Đang lọc: <strong>{category}</strong> · chỉ trong trang đã nhận</span><button type="button" onClick={clearFilter}>Xóa bộ lọc</button></div>}
            {isBusy && <><p className="loading-message" aria-hidden="true">{state.status === 'browsing-loading' ? 'Đang tải danh sách asset…' : 'Đang tìm asset…'}</p><div className="loading-grid" aria-hidden="true">{[1, 2, 3].map((value) => <div className="skeleton-card" key={value}><div /><span /><span /></div>)}</div></>}
            {state.status === 'error' && <div className="empty-state error-state" role="alert"><h3>Chưa thể lấy kết quả</h3><p>{state.message}</p><button className="primary-button" type="button" onClick={retry}>Thử lại</button></div>}
            {(state.status === 'success' || state.status === 'browsing') && visibleCount === 0 && <div className="empty-state"><h3>Chưa có asset phù hợp</h3><p>Thử mô tả ngắn hơn hoặc xóa bộ lọc đang chọn.</p><button type="button" onClick={resetSearch}>Xóa tìm kiếm và bộ lọc</button></div>}
            {state.status === 'success' && visibleResults.length > 0 && (
              <ul className={assetGridClass(visibleResults.length)} aria-label="Kết quả asset">
                {visibleResults.map((result) => (
                  <AssetCard
                    key={`${state.response.search_event_id}-${result.asset.asset_id}`}
                    result={result}
                    feedback={{ eventId: state.response.search_event_id, mock: state.response.mock }}
                    onOpenDetail={(assetId) => { void openDetail(assetId) }}
                  />
                ))}
              </ul>
            )}
            {state.status === 'browsing' && visibleCatalogItems.length > 0 && (
              <ul className={assetGridClass(visibleCatalogItems.length)} aria-label="Kết quả asset">
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
            {state.status === 'success' && <details className="response-details"><summary>Thông tin phiên tìm kiếm</summary><dl><div><dt>Dữ liệu</dt><dd>{state.response.mock ? 'Minh họa (mock)' : 'API khai báo không dùng mock'}</dd></div><div><dt>Query ID</dt><dd>{state.response.query_id}</dd></div><div><dt>Event ID</dt><dd>{state.response.search_event_id}</dd></div><div><dt>Model</dt><dd>{state.response.versions.model_version}</dd></div><div><dt>Index</dt><dd>{state.response.versions.index_version}</dd></div><div><dt>Cấu hình</dt><dd>{state.response.versions.config_version}</dd></div>{!state.response.mock && <div><dt>Dataset snapshot</dt><dd>{state.response.versions.dataset_snapshot}</dd></div>}</dl></details>}
          </section>}
        </>
          </div>
        </div>
      )}
    </div>
  )
}
