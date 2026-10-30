import { useEffect, useRef, useState } from 'react'
import type { AssetMetadata } from '../search/types'
import { isHttpUrl } from '../search/contract'
import './AssetDetailView.css'

export type DetailState =
  | { status: 'loading'; assetId: string }
  | { status: 'success'; asset: AssetMetadata }
  | { status: 'not_found'; assetId: string; message: string }
  | { status: 'error'; assetId: string; message: string }

export interface AssetDetailViewProps {
  state: DetailState
  onRetry: () => void
  onBack: () => void
}

export function AssetDetailView({ state, onRetry, onBack }: AssetDetailViewProps) {
  const [imageFailed, setImageFailed] = useState(false)
  const backButton = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    backButton.current?.focus()
  }, [])

  const asset = state.status === 'success' ? state.asset : null
  const sourceLabel = asset?.source.trim() ? asset.source : 'Chưa có thông tin'

  return (
    <section
      className="asset-detail-section"
      aria-label="Chi tiết asset"
      aria-busy={state.status === 'loading'}
    >
      <div className="asset-detail-toolbar">
        <button ref={backButton} type="button" className="asset-detail-back" onClick={onBack}>
          Quay lại danh sách
        </button>
      </div>

      {state.status === 'loading' && (
        <div className="asset-detail-loading">
          <h2 id="asset-detail-title" className="visually-hidden">Chi tiết asset</h2>
          <p className="loading-message" role="status">Đang tải chi tiết asset…</p>
          <div className="asset-detail-skeleton" aria-hidden="true">
            <div className="skeleton-preview" />
            <div className="skeleton-meta">
              <span />
              <span />
              <span />
            </div>
          </div>
        </div>
      )}

      {state.status === 'not_found' && (
        <div className="empty-state error-state asset-detail-error" role="alert">
          <h2 id="asset-detail-title">Không tìm thấy asset</h2>
          <p>{state.message}</p>
          <button type="button" onClick={onBack}>Quay lại danh sách</button>
        </div>
      )}

      {state.status === 'error' && (
        <div className="empty-state error-state asset-detail-error" role="alert">
          <h2 id="asset-detail-title">Chưa thể tải chi tiết asset</h2>
          <p>{state.message}</p>
          <div className="asset-detail-actions">
            <button className="primary-button" type="button" onClick={onRetry}>Thử lại</button>
            <button type="button" onClick={onBack}>Quay lại danh sách</button>
          </div>
        </div>
      )}

      {asset && (
        <article className="asset-detail-card">
          <div className="asset-detail-preview">
            {asset.thumbnail_url && !imageFailed ? (
              <img
                src={asset.thumbnail_url}
                alt={`Ảnh xem trước ${asset.name}`}
                referrerPolicy="no-referrer"
                onError={() => setImageFailed(true)}
              />
            ) : (
              <div className="placeholder-object" aria-hidden="true"><span /><span /><span /></div>
            )}
            {(!asset.thumbnail_url || imageFailed) && (
              <span className="preview-caption">Chưa có ảnh xem trước</span>
            )}
          </div>
          <div className="asset-detail-body">
            <p className="asset-detail-category">{asset.category ?? 'Chưa có thông tin'}</p>
            <h2 id="asset-detail-title">{asset.name}</h2>
            <p className="asset-detail-description">{asset.description ?? 'Chưa có thông tin'}</p>
            <dl className="asset-detail-metadata">
              <div><dt>Mã asset</dt><dd>{asset.asset_id}</dd></div>
              <div><dt>Danh mục</dt><dd>{asset.category ?? 'Chưa có thông tin'}</dd></div>
              <div><dt>Định dạng</dt><dd>{asset.formats.join(', ').toUpperCase() || 'Chưa có'}</dd></div>
              <div><dt>Số mặt</dt><dd>{asset.face_count?.toLocaleString('vi-VN') ?? 'Chưa có'}</dd></div>
              <div><dt>Tags</dt><dd>{asset.tags.join(', ') || 'Chưa có'}</dd></div>
              <div><dt>Tác giả</dt><dd>{asset.author?.trim() ? asset.author : 'Chưa có thông tin'}</dd></div>
              <div><dt>License</dt><dd>{asset.license?.trim() ? asset.license : 'Chưa có thông tin'}</dd></div>
              <div>
                <dt>Nguồn</dt>
                <dd>
                  {isHttpUrl(asset.source_url) ? (
                    <a href={asset.source_url} target="_blank" rel="noopener noreferrer">{sourceLabel}</a>
                  ) : asset.source === 'fixture' ? 'Dữ liệu minh họa tự tạo' : sourceLabel}
                </dd>
              </div>
            </dl>
          </div>
        </article>
      )}
    </section>
  )
}
