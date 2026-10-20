import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AssetDetailView } from './AssetDetailView'
import { makeResponse } from '../../test/fixtures'

describe('AssetDetailView', () => {
  it('shows loading state and focuses the back button', () => {
    const onBack = vi.fn()
    render(
      <AssetDetailView
        state={{ status: 'loading', assetId: 'mock-chair-01' }}
        onRetry={vi.fn()}
        onBack={onBack}
      />,
    )
    expect(screen.getByRole('button', { name: 'Quay lại danh sách' })).toHaveFocus()
    expect(screen.getByRole('status')).toHaveTextContent('Đang tải chi tiết asset…')
  })

  it('shows 404 not found state and navigates back', async () => {
    const user = userEvent.setup()
    const onBack = vi.fn()
    render(
      <AssetDetailView
        state={{ status: 'not_found', assetId: 'missing', message: 'Không tìm thấy asset trong thư viện.' }}
        onRetry={vi.fn()}
        onBack={onBack}
      />,
    )
    expect(screen.getByRole('heading', { name: 'Không tìm thấy asset' })).toBeVisible()
    expect(screen.getByRole('alert')).toHaveTextContent('Không tìm thấy asset trong thư viện.')
    await user.click(screen.getAllByRole('button', { name: 'Quay lại danh sách' })[1]!)
    expect(onBack).toHaveBeenCalledOnce()
  })

  it('shows error state with retry and back actions', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()
    const onBack = vi.fn()
    render(
      <AssetDetailView
        state={{ status: 'error', assetId: 'mock-chair-01', message: 'Dịch vụ asset chưa sẵn sàng.' }}
        onRetry={onRetry}
        onBack={onBack}
      />,
    )
    expect(screen.getByRole('heading', { name: 'Chưa thể tải chi tiết asset' })).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Thử lại' }))
    expect(onRetry).toHaveBeenCalledOnce()
    await user.click(screen.getAllByRole('button', { name: 'Quay lại danh sách' })[1]!)
    expect(onBack).toHaveBeenCalledOnce()
  })

  it('renders asset metadata with null placeholders and fixture provenance without fabricating data', () => {
    const asset = makeResponse().results[0]!.asset
    asset.category = null
    asset.description = null
    asset.formats = []
    asset.tags = []
    render(<AssetDetailView state={{ status: 'success', asset }} onRetry={vi.fn()} onBack={vi.fn()} />)
    expect(screen.getByRole('heading', { name: asset.name })).toBeVisible()
    expect(screen.getByText('Chưa có ảnh xem trước')).toBeVisible()
    expect(screen.getByText('Dữ liệu minh họa tự tạo')).toBeVisible()
    expect(screen.getAllByText('Chưa có thông tin').length).toBeGreaterThanOrEqual(4)
    expect(screen.getAllByText('Chưa có').length).toBeGreaterThanOrEqual(3)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('renders a preview image, external source link, populated fields, and falls back when the image fails', () => {
    const asset = {
      ...makeResponse().results[0]!.asset,
      category: 'Nội thất',
      description: 'Mô tả đầy đủ của ghế gỗ.',
      formats: ['glb', 'obj'],
      tags: ['ghế', 'gỗ'],
      face_count: 2400,
      author: 'Tác giả A',
      license: 'CC-BY-4.0',
      source: 'Objaverse',
      source_url: 'https://example.com/objaverse/1',
      thumbnail_url: 'https://example.com/thumb.png',
    }
    const { rerender } = render(<AssetDetailView state={{ status: 'success', asset }} onRetry={vi.fn()} onBack={vi.fn()} />)
    const img = screen.getByRole('img', { name: `Ảnh xem trước ${asset.name}` })
    expect(img).toHaveAttribute('src', asset.thumbnail_url)
    expect(screen.getByText('GLB, OBJ')).toBeVisible()
    expect(screen.getByText('ghế, gỗ')).toBeVisible()
    expect(screen.getByText((2400).toLocaleString('vi-VN'))).toBeVisible()
    expect(screen.getByText('Tác giả A')).toBeVisible()
    expect(screen.getByText('CC-BY-4.0')).toBeVisible()
    const link = screen.getByRole('link', { name: 'Objaverse' })
    expect(link).toHaveAttribute('href', asset.source_url)
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    fireEvent.error(img)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByText('Chưa có ảnh xem trước')).toBeVisible()

    rerender(
      <AssetDetailView
        state={{ status: 'success', asset: { ...asset, source_url: null } }}
        onRetry={vi.fn()}
        onBack={vi.fn()}
      />,
    )
    expect(screen.getByText('Objaverse')).toBeVisible()
  })
})
