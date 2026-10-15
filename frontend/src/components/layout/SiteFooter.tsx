import './SiteFooter.css'

export function SiteFooter() {
  return (
    <footer className="site-footer connected-footer">
      <div className="connected-footer__intro">
        <strong className="connected-footer__brand">Connected</strong>
        <p className="connected-footer__description">Không gian cho ý tưởng tiếp theo.</p>
      </div>
      <a className="connected-footer__back-to-top" href="#main">Trở về đầu trang</a>
    </footer>
  )
}
