import './SiteHeader.css'

type SiteHeaderProps = {
  theme: 'light' | 'dark'
  onToggleTheme: () => void
}

export function SiteHeader({ theme, onToggleTheme }: SiteHeaderProps) {
  return (
    <header className="site-header connected-header">
      <a className="connected-header__brand" href="./" aria-label="Connected, trang chủ">
        Connected<span>Thư viện 3D</span>
      </a>
      <div className="connected-header__actions">
        <nav className="connected-header__nav" aria-label="Điều hướng chính">
          <a href="#search-panel">Khám phá</a>
          <a href="#results-title">Kết quả</a>
        </nav>
        <button
          className="connected-header__theme"
          type="button"
          onClick={onToggleTheme}
          aria-label="Chế độ tối"
          aria-pressed={theme === 'dark'}
          title={theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
            {theme === 'dark' ? (
              <>
                <circle cx="12" cy="12" r="4" />
                <path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5" />
              </>
            ) : (
              <path d="M20.5 14A8.8 8.8 0 0 1 10 3.5 8.8 8.8 0 1 0 20.5 14Z" />
            )}
          </svg>
        </button>
      </div>
    </header>
  )
}
