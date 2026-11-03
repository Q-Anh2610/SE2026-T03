import { useEffect, useRef, useState } from 'react'
import { AssetCard } from '../AssetCard'
import type { MockSearchResponse } from '../types'
import { searchImage, validateImage } from './client'
import '../SearchPage.css'

type State = { status: 'idle' | 'validating' | 'loading' }
  | { status: 'error'; message: string; retryable: boolean }
  | { status: 'success'; response: MockSearchResponse }

export function ImageSearchPage() {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState('')
  const [state, setState] = useState<State>({ status: 'idle' })
  const generation = useRef(0)
  const controller = useRef<AbortController | null>(null)
  const last = useRef<{ file: File; page: number } | null>(null)
  const input = useRef<HTMLInputElement | null>(null)
  useEffect(() => () => { generation.current++; controller.current?.abort() }, [])
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview) }, [preview])

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

  async function search(request: { file: File; page: number }) {
    controller.current?.abort()
    const current = new AbortController()
    controller.current = current
    last.current = request
    setState({ status: 'loading' })
    try {
      const response = await searchImage(request.file, request.page, current.signal)
      if (!current.signal.aborted) setState({ status: 'success', response })
    } catch (error) {
      if (!current.signal.aborted) setState({ status: 'error', message: (error as Error).message, retryable: true })
    }
  }

  return <section className="results-section" aria-label="Tìm kiếm bằng ảnh">
    <h1>Tìm kiếm bằng ảnh</h1>
    <p>Chế độ phát triển: API ảnh hiện trả fixture minh họa, chưa tìm theo nội dung ảnh.</p>
    <form onSubmit={(event) => { event.preventDefault(); if (file) void search({ file, page: 1 }) }}>
      <label htmlFor="query-image">Chọn hoặc thay ảnh JPEG/PNG (tối đa 5 MiB, mỗi chiều 4096 px)</label>
      <input ref={input} id="query-image" type="file" accept="image/jpeg,image/png" onChange={(event) => {
        const chosen = event.target.files?.[0]
        event.target.value = ''
        if (chosen) void select(chosen)
      }} />
      {preview && <div><img src={preview} alt={`Ảnh truy vấn: ${file!.name}`} style={{ maxWidth: '100%', width: 240, maxHeight: 240, objectFit: 'contain' }} /></div>}
      {file && <button type="button" onClick={() => { reset(); input.current!.focus() }}>Xóa ảnh</button>}
      <button type="submit" disabled={!file || state.status === 'loading'}>Tìm bằng ảnh</button>
    </form>
    <div aria-busy={state.status === 'loading' || state.status === 'validating'}>
      {state.status === 'validating' && <p role="status">Đang kiểm tra ảnh…</p>}
      {state.status === 'loading' && <p role="status">Đang tìm ảnh…</p>}
      {state.status === 'error' && <div role="alert"><p>{state.message}</p>{state.retryable && <button type="button" onClick={() => { void search(last.current!) }}>Thử lại</button>}</div>}
      {state.status === 'success' && <>
        <p role="status">{state.response.results.length ? 'Kết quả minh họa (mock)' : 'Chưa có asset phù hợp'}</p>
        {state.response.results.length > 0 && <ul className="asset-grid" aria-label="Kết quả ảnh">{state.response.results.map((result) => <AssetCard key={result.asset.asset_id} result={result} />)}</ul>}
        <nav aria-label="Phân trang ảnh">
          <button type="button" disabled={state.response.pagination.page <= 1} onClick={() => { void search({ ...last.current!, page: state.response.pagination.page - 1 }) }}>Trang trước</button>
          <span>Trang {state.response.pagination.page} · {state.response.pagination.total} kết quả minh họa</span>
          <button type="button" disabled={!state.response.pagination.has_next} onClick={() => { void search({ ...last.current!, page: state.response.pagination.page + 1 }) }}>Trang sau</button>
        </nav>
      </>}
    </div>
  </section>
}
