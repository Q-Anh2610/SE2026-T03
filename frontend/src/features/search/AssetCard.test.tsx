import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AssetCard } from './AssetCard'
import { makeResponse } from '../../test/fixtures'

describe('asset result card', () => {
  it('renders rank, metadata and explicit placeholders without fabricating missing data', () => {
    render(<ul><AssetCard result={makeResponse().results[0]!} /></ul>)
    expect(screen.getByRole('heading', { name: 'Ghế gỗ kiểm thử' })).toBeVisible()
    expect(screen.getByText('Hạng 1')).toBeVisible()
    expect(screen.getByText('GLB')).toBeVisible()
    expect(screen.getByText('Chưa có thông tin')).toBeVisible()
    expect(screen.getByText('Dữ liệu minh họa tự tạo')).toBeVisible()
    expect(screen.getByText('Chưa có ảnh xem trước')).toBeVisible()
    expect(screen.getByText('Nguồn truy xuất: test_metadata')).toBeVisible()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('renders a provided image and an external source link with safe link attributes', () => {
    const result = makeResponse().results[0]!
    Object.assign(result.asset, {
      thumbnail_url: 'https://example.com/preview.png', source_url: 'https://example.com/asset',
      source: 'Test source', face_count: 1200, license: 'Test license',
    })
    render(<ul><AssetCard result={result} /></ul>)
    expect(screen.getByRole('img', { name: 'Ảnh xem trước Ghế gỗ kiểm thử' })).toHaveAttribute('src', result.asset.thumbnail_url)
    expect(screen.getByText((1200).toLocaleString('vi-VN'))).toBeVisible()
    expect(screen.getByText('Test license')).toBeVisible()
    const source = screen.getByRole('link', { name: 'Test source' })
    expect(source).toHaveAttribute('href', result.asset.source_url)
    expect(source).toHaveAttribute('target', '_blank')
    expect(source).toHaveAttribute('rel', 'noopener noreferrer')
    expect(screen.queryByText('Chưa có ảnh xem trước')).not.toBeInTheDocument()
  })

  it('replaces a broken thumbnail with the explicit placeholder', () => {
    const result = makeResponse().results[0]!
    result.asset.thumbnail_url = 'https://example.com/broken.png'
    render(<ul><AssetCard result={result} /></ul>)
    fireEvent.error(screen.getByRole('img'))
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByText('Chưa có ảnh xem trước')).toBeVisible()
  })

  it('handles empty formats/retrieval sources and non-fixture source names', () => {
    const result = makeResponse().results[0]!
    result.asset.formats = []
    result.asset.source = 'Test source'
    result.retrieval_sources = []
    render(<ul><AssetCard result={result} /></ul>)
    expect(screen.getAllByText('Chưa có')).toHaveLength(2)
    expect(screen.getByText('Test source')).toBeVisible()
    expect(screen.getByText('Nguồn truy xuất: Chưa có')).toBeVisible()
  })
})
