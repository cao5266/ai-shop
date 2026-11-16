import { Link } from 'react-router-dom'
import { LOGO } from '../lib/logos'

export function Tile({ name, size = 56 }: { name: string; size?: number }) {
  const f = LOGO[name]
  return (
    <span className="tile" style={{ width: size, height: size, borderRadius: size * 0.2237 }} aria-hidden="true">
      {f ? <img src={`/logos/${f}.svg`} alt="" width={size * 0.58} height={size * 0.58} />
        : <span className="tile-letter" style={{ fontSize: size * 0.42 }}>{[...name][0].toUpperCase()}</span>}
    </span>
  )
}

export function Chevron({ dir = 'left' }: { dir?: 'left' | 'right' }) {
  return <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true" style={dir === 'right' ? { transform: 'scaleX(-1)' } : undefined}><path d="M12.5 4.5L7 10l5.5 5.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
}

export function Back({ to, children }: { to: string; children: string }) {
  return <Link className="back" to={to}><Chevron />{children}</Link>
}

export function ErrorBox({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="state" role="alert">
      <p>{message}</p>
      {retry && <button className="btn btn-soft" type="button" onClick={retry}>重试</button>}
    </div>
  )
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return <div className="state"><p className="state-t">{title}</p>{hint && <p className="muted">{hint}</p>}</div>
}

export function NotFound() {
  return <div className="state"><p className="state-t">页面不存在</p><Link className="btn btn-soft" to="/">回到首页</Link></div>
}

export function GoButton({ href, children = '去店铺', label }: { href: string; children?: string; label?: string }) {
  return <a className="btn btn-soft" href={href} target="_blank" rel="noopener noreferrer nofollow" aria-label={label}>{children}</a>
}

export function Pager({ page, total, size, onPage }: { page: number; total: number; size: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / size))
  if (pages <= 1) return null
  return (
    <nav className="pager" aria-label="分页">
      <button className="btn btn-line" type="button" disabled={page <= 1} onClick={() => onPage(page - 1)}>上一页</button>
      <span className="muted">第 {page} 页，共 {pages} 页</span>
      <button className="btn btn-line" type="button" disabled={page >= pages} onClick={() => onPage(page + 1)}>下一页</button>
    </nav>
  )
}
