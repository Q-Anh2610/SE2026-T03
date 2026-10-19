import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AssetCard } from './AssetCard'
import { makeResponse } from '../../test/fixtures'

describe('asset result card', () => {
  it('renders rank, metadata and explicit placeholders without fabricating missing data', () => {
    render(<ul><AssetCard result={makeResponse().results[0]!} /></ul>)
    expect(screen.getByRole('heading', { name: 'Ghế gỗ kiểm thử' })).toBeVisible()
    expect(screen.getByText('Hạng 1')).toBeVisible()
    expect(screen.getByText('GLB')).not.toBeVisible()
    expect(screen.getByText('Chưa có thông tin')).not.toBeVisible()
    expect(screen.getByText('Dữ liệu minh họa tự tạo')).not.toBeVisible()
    expect(screen.getByText('Chưa có ảnh xem trước')).toBeVisible()
    expect(screen.getByText('Nguồn truy xuất: test_metadata')).not.toBeVisible()
    fireEvent.click(screen.getByText('Chi tiết'))
    expect(screen.getByText('GLB')).toBeVisible()
    expect(screen.getByText('Chưa có thông tin')).toBeVisible()
    expect(screen.getByText('Dữ liệu minh họa tự tạo')).toBeVisible()
    expect(screen.getByText('Nguồn truy xuất: test_metadata')).toBeVisible()
    fireEvent.click(screen.getByText('Chi tiết'))
    expect(screen.getByText('GLB')).not.toBeVisible()
    expect(screen.getByText('Nguồn truy xuất: test_metadata')).not.toBeVisible()
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
    fireEvent.click(screen.getByText('Chi tiết'))
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
    expect(screen.getByText('Test source')).not.toBeVisible()
    fireEvent.click(screen.getByText('Chi tiết'))
    expect(screen.getByText('Test source')).toBeVisible()
    expect(screen.getByText('Nguồn truy xuất: Chưa có')).toBeVisible()
  })

  it('keeps details focusable and toggles all metadata while keeping the title visible', async () => {
    const user = userEvent.setup()
    const result = makeResponse().results[0]!
    render(<ul><AssetCard result={result} /></ul>)
    const summary = screen.getByText('Chi tiết')
    const details = summary.closest('details')!
    expect(details).not.toHaveAttribute('open')
    expect(screen.getByText(result.asset.description!)).not.toBeVisible()
    await user.tab()
    expect(summary).toHaveFocus()
    await user.click(summary)
    expect(details).toHaveAttribute('open')
    expect(screen.getByText(result.asset.description!)).toBeVisible()
    expect(screen.getByText(result.explanation)).toBeVisible()
    await user.click(summary)
    expect(details).not.toHaveAttribute('open')
    expect(screen.getByText(result.asset.description!)).not.toBeVisible()
    expect(screen.getByRole('heading', { name: result.asset.name })).toBeVisible()
    expect(screen.getByRole('listitem')).toHaveClass('asset-card')
  })

  it('keeps missing descriptions and categories explicit', () => {
    const result = makeResponse().results[0]!
    result.asset.category = null
    result.asset.description = null
    render(<ul><AssetCard result={result} /></ul>)
    const placeholders = screen.getAllByText('Chưa có thông tin')
    expect(placeholders).toHaveLength(3)
    expect(placeholders[0]).toBeVisible()
    expect(placeholders[1]).not.toBeVisible()
    fireEvent.click(screen.getByText('Chi tiết'))
    for (const placeholder of placeholders) expect(placeholder).toBeVisible()
  })

  it('renders a catalog asset without rank/retrieval fields and triggers onOpenDetail', async () => {
    const user = userEvent.setup()
    const onOpenDetail = vi.fn()
    const asset = makeResponse().results[0]!.asset
    render(<ul><AssetCard asset={asset} onOpenDetail={onOpenDetail} /></ul>)
    expect(screen.queryByText(/Hạng/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Nguồn truy xuất/)).not.toBeInTheDocument()
    const openBtn = screen.getByRole('button', { name: `Xem chi tiết ${asset.name}` })
    await user.click(openBtn)
    expect(onOpenDetail).toHaveBeenCalledWith(asset.asset_id)
  })
})
