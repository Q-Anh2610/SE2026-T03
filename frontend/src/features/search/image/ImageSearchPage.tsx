import { useEffect, useRef, useState } from 'react'
import { AssetCard } from '../AssetCard'
import { AssetDetailView, type DetailState } from '../../assets/AssetDetailView'
import { createHttpAssetClient } from '../../../lib/api/search'
import type { AssetFilters, SearchResponse } from '../types'
import { searchImage, validateImage } from './client'
import { SearchResultsGuide } from '../SearchResultsGuide'
import '../SearchPage.css'

type State = { status: 'idle' | 'validating' | 'loading' }
  | { status: 'error'; message: string; retryable: boolean }
  | { status: 'success'; response: SearchResponse }

export function ImageSearchPage() {
  const [filters, setFilters] = useState<AssetFilters>({})
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState('')
  const [state, setState] = useState<State>({ status: 'idle' })
  const [detail, setDetail] = useState<DetailState | null>(null)
  const detailController = useRef<AbortController | null>(null)
  const generation = useRef(0)
  const controller = useRef<AbortController | null>(null)
  const last = useRef<{ file: File; page: number; filters: AssetFilters } | null>(null)
  const input = useRef<HTMLInputElement | null>(null)
  useEffect(() => () => { generation.current++; controller.current?.abort(); detailController.current?.abort() }, [])
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview) }, [preview])

  async function openDetail(assetId: string) {
    detailController.current?.abort()
    const current = new AbortController()
    detailController.current = current
    setDetail({ status: 'loading', assetId })
    try {
      const client = createHttpAssetClient(import.meta.env.VITE_API_BASE_URL ?? '')
      if (current.signal.aborted) return
      const response = await client.getAsset(assetId, current.signal)
      if (!current.signal.aborted) setDetail({ status: 'success', asset: response.asset })
    } catch (error) {
      if (current.signal.aborted) return
      const message = error instanceof Error ? error.message : 'Không thể tải chi tiết asset. Hãy thử lại.'
      if (typeof error === 'object' && error !== null && 'kind' in error && error.kind === 'not_found') {
        setDetail({ status: 'not_found', assetId, message })
      } else setDetail({ status: 'error', assetId, message })
    }
  }

  function reset() {
    generation.current++
    controller.current?.abort()
    last.current = null
    setFile(null)
    setPreview('')
    setState({ status: 'idle' })
  }

  async function select(candidate: File) {
    reset()
    const current = generation.current
    setState({ status: 'validating' })
    try {
      await validateImage(candidate)
      if (current !== generation.current) return
      setFile(candidate)
      setPreview(URL.createObjectURL(candidate))
      setState({ status: 'idle' })
    } catch (error) {
      if (current === generation.current) setState({ status: 'error', message: (error as Error).message, retryable: false })
    }
  }

  async function search(request: { file: File; page: number; filters: AssetFilters }) {
    controller.current?.abort()
    const current = new AbortController()
    controller.current = current
    last.current = request
    setState({ status: 'loading' })
    try {
      const response = await searchImage(request.file, request.page, current.signal, request.filters)
      if (!current.signal.aborted) setState({ status: 'success', response })
    } catch (error) {
      if (!current.signal.aborted) setState({ status: 'error', message: (error as Error).message, retryable: true })
    }
  }

  if (detail) {
    const assetId = detail.status === 'success' ? detail.asset.asset_id : detail.assetId
    return <AssetDetailView state={detail} onRetry={() => { void openDetail(assetId) }} onBack={() => { detailController.current?.abort(); setDetail(null) }} />
  }

  return <section id="image-search" className="image-search-page results-section" aria-labelledby="image-search-title">
    <header className="image-search-heading">
      <p className="intro-eyebrow">TÌM KIẾM TRỰC QUAN</p>
      <h1 id="image-search-title">Tìm kiếm bằng ảnh</h1>
      <p>Chọn ảnh tham chiếu, rồi lọc theo danh mục, định dạng, license hoặc số mặt.</p>
    </header>
    <form className="image-search-form" onSubmit={(event) => { event.preventDefault(); if (file) void search({ file, page: 1, filters: { ...filters } }) }}>
      <input className="image-file-input visually-hidden" ref={input} id="query-image" type="file" accept="image/jpeg,image/png" aria-label="Chọn hoặc thay ảnh JPEG/PNG (tối đa 5 MiB, mỗi chiều 4096 px)" aria-invalid={state.status === 'error' && !state.retryable || undefined} aria-describedby={state.status === 'error' && !state.retryable ? 'image-error' : undefined} onChange={(event) => {
        const chosen = event.target.files?.[0]
        event.target.value = ''
        if (chosen) void select(chosen)
      }} />
      <label className="image-file-drop" htmlFor="query-image" aria-hidden="true">
        <span className="image-file-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M5 14v5h14v-5" /></svg></span>
        <span className="image-file-copy"><strong>{file ? 'Đổi ảnh tham chiếu' : 'Chọn ảnh tham chiếu'}</strong><small>{file ? file.name : 'JPEG hoặc PNG · tối đa 5 MiB · mỗi chiều tối đa 4096 px'}</small></span>
        <span className="image-file-button">Chọn ảnh</span>
      </label>
      <fieldset className="image-search-filters" disabled={state.status === 'loading'}><legend>Bộ lọc ảnh</legend>
        {(['category', 'license', 'format'] as const).map((key) => <label key={key}>
          {{ category: 'Danh mục', license: 'License', format: 'Định dạng' }[key]}
          <input value={filters[key] ?? ''} onChange={(event) => setFilters({ ...filters, [key]: event.target.value || undefined })} />
        </label>)}
        {(['face_count_min', 'face_count_max'] as const).map((key) => <label key={key}>
          {key === 'face_count_min' ? 'Số mặt tối thiểu' : 'Số mặt tối đa'}
          <input type="number" min="0" step="1" value={filters[key] ?? ''} onChange={(event) => setFilters({ ...filters, [key]: event.target.value === '' ? undefined : Number(event.target.value) })} />
        </label>)}
        <button type="button" onClick={() => setFilters({})}>Xóa bộ lọc</button>
      </fieldset>
      {preview && <figure className="image-query-preview"><img src={preview} alt={`Ảnh truy vấn: ${file!.name}`} /><figcaption>Ảnh tham chiếu</figcaption></figure>}
      <div className="image-search-actions">
        {file && <button className="image-search-secondary" type="button" onClick={() => { reset(); input.current!.focus() }}>Xóa ảnh</button>}
        <button className="image-search-submit" type="submit" disabled={!file || state.status === 'loading'}>Tìm bằng ảnh</button>
      </div>
    </form>
    <div aria-busy={state.status === 'loading' || state.status === 'validating'}>
      {state.status === 'validating' && <p role="status">Đang kiểm tra ảnh…</p>}
      {state.status === 'loading' && <p role="status">Đang tìm ảnh…</p>}
      {state.status === 'error' && <div role="alert"><p id={!state.retryable ? 'image-error' : undefined}>{state.message}</p>{state.retryable && <button type="button" onClick={() => { void search(last.current!) }}>Thử lại</button>}</div>}
      {state.status === 'success' && <>
        {state.response.results.length > 0 ? (
          <>
            <p className="image-result-status" role="status">{state.response.mock ? 'Kết quả minh họa (mock)' : 'Kết quả tìm kiếm bằng ảnh'}</p>
            <SearchResultsGuide results={state.response.results} mock={state.response.mock} />
            <ul className={`asset-grid${state.response.results.length <= 2 ? ` asset-grid--count-${state.response.results.length}` : ''}`} aria-label="Kết quả ảnh">{state.response.results.map((result) => <AssetCard key={`${state.response.search_event_id}-${result.asset.asset_id}`} result={result} onOpenDetail={(assetId) => { void openDetail(assetId) }} feedback={{ eventId: state.response.search_event_id, mock: state.response.mock }} />)}</ul>
          </>
        ) : (
          <div className="image-empty-state" role="status">
            <h2>Chưa có asset phù hợp</h2>
            <p>Thử một ảnh khác hoặc xóa bớt bộ lọc để mở rộng kết quả.</p>
            <button type="button" onClick={() => input.current?.click()}>Chọn ảnh khác</button>
          </div>
        )}
        <details className="search-session">
          <summary>Thông tin phiên tìm ảnh</summary>
          <dl>
            <dt>Nguồn dữ liệu</dt><dd>{state.response.mock ? 'Minh họa (mock)' : 'API tìm ảnh thật'}</dd>
            <dt>Query ID</dt><dd>{state.response.query_id}</dd>
            <dt>Event ID</dt><dd>{state.response.search_event_id}</dd>
            <dt>Định danh ảnh</dt><dd>{state.response.query}</dd>
            <dt>Model</dt><dd>{state.response.versions.model_version}</dd>
            <dt>Index</dt><dd>{state.response.versions.index_version}</dd>
            <dt>Cấu hình</dt><dd>{state.response.versions.config_version}</dd>
            {!state.response.mock && <><dt>Dataset snapshot</dt><dd>{state.response.versions.dataset_snapshot}</dd></>}
          </dl>
        </details>
        <nav aria-label="Phân trang ảnh">
          <button type="button" disabled={state.response.pagination.page <= 1} onClick={() => { void search({ ...last.current!, page: state.response.pagination.page - 1 }) }}>Trang trước</button>
          <span>Trang {state.response.pagination.page} · {state.response.pagination.total} kết quả {state.response.mock ? 'minh họa' : 'trong cửa sổ tối đa 200 ứng viên'}</span>
          <button type="button" disabled={!state.response.pagination.has_next} onClick={() => { void search({ ...last.current!, page: state.response.pagination.page + 1 }) }}>Trang sau</button>
        </nav>
      </>}
    </div>
  </section>
}
