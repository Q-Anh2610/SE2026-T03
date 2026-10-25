import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'

beforeEach(() => {
  localStorage.clear()
  delete document.documentElement.dataset.theme
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false })))
})
afterEach(() => {
  localStorage.clear()
  window.location.hash = ''
  delete document.documentElement.dataset.theme
  document.querySelector('meta[name="theme-color"]')?.remove()
})

describe('theme preference', () => {
  it('renders one actual header and footer with the current navigation and no stale slogan', () => {
    render(<App />)
    expect(screen.getAllByRole('banner')).toHaveLength(1)
    expect(screen.getAllByRole('contentinfo')).toHaveLength(1)
    expect(screen.getByRole('link', { name: 'Connected, trang chủ' })).toHaveAttribute('href', './')
    const navigation = screen.getByRole('navigation', { name: 'Điều hướng chính' })
    expect(navigation.querySelectorAll('a')).toHaveLength(2)
    expect(screen.getByRole('link', { name: 'Trạng thái job' })).toHaveAttribute(
      'href',
      '#admin-status',
    )
    expect(screen.getByRole('link', { name: 'Khám phá asset' })).toHaveAttribute('href', '#search-panel')
    expect(screen.getByRole('link', { name: 'Đến nội dung chính' })).toHaveAttribute('href', '#main')
    expect(screen.queryByText('Không gian cho ý tưởng tiếp theo.')).not.toBeInTheDocument()
    expect(screen.getByRole('contentinfo')).toHaveTextContent('Thư viện 3D')
  })

  it('uses the system preference when no choice is saved', () => {
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true })))
    render(<App />)
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
    expect(screen.getByRole('button', { name: 'Chế độ tối' })).toHaveAttribute('aria-pressed', 'true')
    expect(localStorage.getItem('connected-theme')).toBeNull()
  })

  it('uses a saved light choice even when the system prefers dark', () => {
    localStorage.setItem('connected-theme', 'light')
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true })))
    render(<App />)
    expect(document.documentElement).toHaveAttribute('data-theme', 'light')
  })

  it('restores a saved dark choice', () => {
    localStorage.setItem('connected-theme', 'dark')
    render(<App />)
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
  })

  it('ignores invalid stored values and falls back to light without matchMedia', () => {
    localStorage.setItem('connected-theme', 'invalid')
    vi.stubGlobal('matchMedia', undefined)
    render(<App />)
    expect(document.documentElement).toHaveAttribute('data-theme', 'light')
  })

  it('switches by keyboard, persists the choice and updates browser theme color', async () => {
    const meta = document.createElement('meta')
    meta.name = 'theme-color'; document.head.append(meta)
    const user = userEvent.setup()
    render(<App />)
    const button = screen.getByRole('button', { name: 'Chế độ tối' })
    button.focus()
    await user.keyboard('{Enter}')
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
    expect(localStorage.getItem('connected-theme')).toBe('dark')
    expect(meta).toHaveAttribute('content', '#171717')
    await user.keyboard(' ')
    expect(document.documentElement).toHaveAttribute('data-theme', 'light')
    expect(localStorage.getItem('connected-theme')).toBe('light')
    expect(meta).toHaveAttribute('content', '#f8f8f6')
  })

  it('keeps the theme switch working when browser storage is unavailable', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('Storage blocked') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('Storage blocked') })
    render(<App />)
    await userEvent.setup().click(screen.getByRole('button', { name: 'Chế độ tối' }))
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
  })
})

describe('admin status routing', () => {
  it('renders the admin status page when loaded with the admin hash', () => {
    window.location.hash = '#admin-status'

    render(<App />)

    expect(screen.getByRole('heading', { name: 'Trạng thái job' })).toBeInTheDocument()
  })

  it('switches to the admin status page when the hash changes', async () => {
    window.location.hash = '#search-panel'
    render(<App />)

    window.location.hash = '#admin-status'
    window.dispatchEvent(new Event('hashchange'))

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Trạng thái job' })).toBeInTheDocument()
    })
  })

  it('switches back to the search page when leaving the admin hash', async () => {
    window.location.hash = '#admin-status'
    render(<App />)

    window.location.hash = '#search-panel'
    window.dispatchEvent(new Event('hashchange'))

    await waitFor(() => {
      expect(document.querySelector('#search-panel')).toBeInTheDocument()
      expect(screen.queryByRole('heading', { name: 'Trạng thái job' })).not.toBeInTheDocument()
    })
  })
})
