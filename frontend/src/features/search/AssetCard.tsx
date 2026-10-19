import { useState } from 'react'
import type { AssetMetadata, SearchResult } from './types'
import './AssetCard.css'

export interface AssetCardProps {
  result?: SearchResult
  asset?: AssetMetadata
  onOpenDetail?: (assetId: string) => void
}

export function AssetCard({ result, asset: item, onOpenDetail }: AssetCardProps) {
  const asset = (result ? result.asset : item)!
  const [imageFailed, setImageFailed] = useState(false)
  return (
    <li className="asset-card asset-gallery-card">
      <div className="asset-preview">
        {asset.thumbnail_url && !imageFailed ? (
          <img src={asset.thumbnail_url} alt={`Ảnh xem trước ${asset.name}`} loading="lazy"
            referrerPolicy="no-referrer" onError={() => setImageFailed(true)} />
        ) : (
          <div className="placeholder-object" aria-hidden="true"><span /><span /><span /></div>
        )}
        {result && <span className="rank">Hạng {result.rank}</span>}
        {(!asset.thumbnail_url || imageFailed) && <span className="preview-caption">Chưa có ảnh xem trước</span>}
      </div>
      <div className="asset-content">
        <p className="asset-category">{asset.category ?? 'Chưa có thông tin'}</p>
        <h3>{asset.name}</h3>
        <div className="asset-card-actions">
          {onOpenDetail && (
            <button
              type="button"
              className="asset-open-detail"
              aria-label={`Xem chi tiết ${asset.name}`}
              onClick={() => onOpenDetail(asset.asset_id)}
            >
              Xem chi tiết
            </button>
          )}
          <details className="asset-details">
            <summary>Chi tiết</summary>
            <p className="asset-description">{asset.description ?? 'Chưa có thông tin'}</p>
            <dl className="asset-metadata">
              <div><dt>Định dạng</dt><dd>{asset.formats.join(', ').toUpperCase() || 'Chưa có'}</dd></div>
              <div><dt>Số mặt</dt><dd>{asset.face_count?.toLocaleString('vi-VN') ?? 'Chưa có'}</dd></div>
              <div><dt>License</dt><dd>{asset.license ?? 'Chưa có thông tin'}</dd></div>
              <div><dt>Nguồn</dt><dd>{asset.source_url ? (
                <a href={asset.source_url} target="_blank" rel="noopener noreferrer">{asset.source}</a>
              ) : asset.source === 'fixture' ? 'Dữ liệu minh họa tự tạo' : asset.source}</dd></div>
            </dl>
            {result && (
              <>
                <p className="retrieval-note">{result.explanation}</p>
                <p className="retrieval-source">Nguồn truy xuất: {result.retrieval_sources.join(', ') || 'Chưa có'}</p>
              </>
            )}
          </details>
        </div>
      </div>
    </li>
  )
}
