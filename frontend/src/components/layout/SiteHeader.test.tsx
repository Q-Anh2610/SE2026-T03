import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { SiteHeader } from './SiteHeader'

describe('SiteHeader', () => {
  it('keeps the Connected wordmark and the two search anchors', () => {
    render(<SiteHeader theme="light" onToggleTheme={vi.fn()} />)

    expect(screen.getByRole('link', { name: 'Connected, trang chủ' })).toHaveAttribute('href', './')
    expect(screen.getByText('Thư viện 3D')).toBeInTheDocument()
    const navigation = screen.getByRole('navigation', { name: 'Điều hướng chính' })
    expect(within(navigation).getAllByRole('link')).toHaveLength(2)
    expect(within(navigation).getByRole('link', { name: 'Khám phá' })).toHaveAttribute('href', '#search-panel')
    expect(within(navigation).getByRole('link', { name: 'Kết quả' })).toHaveAttribute('href', '#results-title')
    expect(screen.getAllByRole('button')).toHaveLength(1)
    expect(screen.queryByText(/demo|bản mẫu|tuần 1|AI-04/i)).not.toBeInTheDocument()
  })

  it('calls the parent on click and reflects only the supplied theme', async () => {
    const onToggleTheme = vi.fn()
    const user = userEvent.setup()
    const { rerender } = render(<SiteHeader theme="light" onToggleTheme={onToggleTheme} />)
    const toggle = screen.getByRole('button', { name: 'Chế độ tối' })

    expect(toggle).toHaveAttribute('type', 'button')
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    expect(toggle).toHaveAttribute('title', 'Chuyển sang giao diện tối')
    await user.click(toggle)
    expect(onToggleTheme).toHaveBeenCalledTimes(1)
    expect(toggle).toHaveAttribute('aria-pressed', 'false')

    rerender(<SiteHeader theme="dark" onToggleTheme={onToggleTheme} />)
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
    expect(toggle).toHaveAttribute('title', 'Chuyển sang giao diện sáng')
    await user.click(toggle)
    expect(onToggleTheme).toHaveBeenCalledTimes(2)
  })

  it('supports keyboard navigation and theme activation with Enter and Space', async () => {
    const user = userEvent.setup()
    const onToggleTheme = vi.fn()
    render(<SiteHeader theme="dark" onToggleTheme={onToggleTheme} />)

    await user.tab()
    expect(screen.getByRole('link', { name: 'Connected, trang chủ' })).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('link', { name: 'Khám phá' })).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('link', { name: 'Kết quả' })).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('button', { name: 'Chế độ tối' })).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(onToggleTheme).toHaveBeenCalledTimes(1)
    await user.keyboard(' ')
    expect(onToggleTheme).toHaveBeenCalledTimes(2)
  })
})
