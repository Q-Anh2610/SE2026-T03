import { useState } from 'react'
import type { AssetMetadata, SearchResult } from './types'
import './AssetCard.css'
import { Feedback } from './Feedback'

export interface AssetCardProps {
  feedback?: { eventId: string; mock: boolean }
  result?: SearchResult
  asset?: AssetMetadata
  onOpenDetail?: (assetId: string) => void
}

export function AssetCard({ result, asset: item, onOpenDetail, feedback }: AssetCardProps) {
  const asset = (result ? result.asset : item)!
  const [imageFailed, setImageFailed] = useState(false)
  const thumbnailUrl = !imageFailed ? asset.thumbnail_url : undefined
  const scoreName = result?.score_type === 'cosine' ? 'Điểm cosine' : 'Điểm API'
  const scoreLabel = result?.score === null || result?.score === undefined
    ? null
    : result.score.toLocaleString('vi-VN', { maximumFractionDigits: 4 })

  return (
    <li className="asset-card asset-gallery-card">
      <div className={`asset-preview${thumbnailUrl ? '' : ' asset-preview--empty'}`}>
        {thumbnailUrl ? (
          <img src={thumbnailUrl} alt={`Ảnh xem trước ${asset.name}`} loading="lazy" decoding="async" width="768" height="768"
            referrerPolicy="no-referrer" onError={() => setImageFailed(true)} />
        ) : (
          <div className="placeholder-object" aria-hidden="true"><span /><span /><span /></div>
        )}
        {result && <span className="rank">Hạng {result.rank}</span>}
        {!thumbnailUrl && <span className="preview-caption">Chưa có ảnh xem trước</span>}
      </div>
      <div className="asset-content">
        <p className="asset-category">{asset.category ?? 'Chưa có thông tin'}</p>
        <h3>{asset.name}</h3>
          {result && (
            <div className="asset-result-signal">
              <div className="asset-result-signal-heading">
                {scoreLabel && (
                  <p className="asset-score">
                    <span>{scoreName}</span>
                    <strong>{scoreLabel}</strong>
                  </p>
                )}
                {result.retrieval_sources.length > 0 && (
                  <div className="asset-retrieval-sources" aria-label="Nguồn truy xuất">
                    {result.retrieval_sources.map((source) => (
                      <span key={source} title={source} aria-label={`Nguồn truy xuất: ${source}`}>
                        {formatRetrievalSource(source)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <p className="retrieval-note">{result.explanation.trim() || 'API chưa cung cấp giải thích cho kết quả này.'}</p>
              {result.retrieval_sources.length === 0 && <p className="retrieval-note">API chưa cung cấp nguồn truy xuất.</p>}
            </div>
          )}
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
          </details>
          {result && feedback && <Feedback key={`${feedback.eventId}-${asset.asset_id}`} {...feedback} assetId={asset.asset_id} />}
        </div>
      </div>
    </li>
  )
}

function formatRetrievalSource(source: string) {
  switch (source) {
    case 'clip_text_to_preview': return 'Văn bản → ảnh xem trước'
    case 'clip_image_to_preview': return 'Ảnh → ảnh xem trước'
    case 'mock_metadata': return 'Metadata · mock'
    case 'mock_preview_fixture': return 'Ảnh xem trước · mock'
    default: return source
  }
}
