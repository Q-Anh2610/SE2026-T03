import { useEffect, useState } from 'react'
import { SearchPage } from '../features/search/SearchPage'

export function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    try {
      const saved = localStorage.getItem('connected-theme')
      if (saved === 'light' || saved === 'dark') return saved
    } catch { /* Storage may be unavailable; the theme control still works. */ }
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  })

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#171717' : '#f8f8f6')
  }, [theme])

  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    try { localStorage.setItem('connected-theme', next) } catch { /* Keep the choice for this session. */ }
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">Đến nội dung chính</a>
      <header className="site-header">
        <div className="header-identity"><a className="brand" href="./" aria-label="Connected, trang chủ">Connected</a><span className="site-title">Thư viện 3D</span></div>
        <nav className="header-nav" aria-label="Điều hướng chính"><a href="#search-panel">Khám phá asset</a></nav>
        <button className="theme-toggle" type="button" onClick={toggleTheme} aria-label="Chế độ tối" aria-pressed={theme === 'dark'} title={theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">{theme === 'dark' ? <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5" /></> : <path d="M20.5 14A8.8 8.8 0 0 1 10 3.5 8.8 8.8 0 1 0 20.5 14Z" />}</svg>
        </button>
      </header>
      <main id="main" tabIndex={-1}><SearchPage /></main>
      <footer className="site-footer"><div><strong>Connected</strong></div><span>Thư viện 3D</span></footer>
    </div>
  )
}
