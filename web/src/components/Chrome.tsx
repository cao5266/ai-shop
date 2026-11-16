import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { FormEvent, useState } from 'react'

export function SearchBox({ initial = '', large = false, autoFocus = false }: { initial?: string; large?: boolean; autoFocus?: boolean }) {
  const nav = useNavigate()
  const [q, setQ] = useState(initial)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    const v = q.trim()
    nav(v ? `/shops?q=${encodeURIComponent(v)}` : '/shops')
  }
  return (
    <form className={'search' + (large ? ' search-lg' : '')} role="search" onSubmit={submit}>
      <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><circle cx="9" cy="9" r="6" fill="none" stroke="currentColor" strokeWidth="1.6" /><path d="M13.6 13.6L17 17" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
      <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜索商品或店铺" aria-label="搜索商品或店铺" autoComplete="off" maxLength={60} autoFocus={autoFocus} />
      {large && <button type="submit" className="btn btn-solid">搜索</button>}
    </form>
  )
}

export function Header() {
  const { pathname } = useLocation()
  const home = pathname === '/' || pathname === '/shops'
  return (
    <header className="top">
      <div className="wrap top-in">
        <Link to="/" className="brand" aria-label="AI 订阅比价，返回首页"><img src="/logo.svg" alt="AI 订阅比价" height="32" /></Link>
        {!home && <div className="top-search"><SearchBox /></div>}
        <nav className="nav" aria-label="主导航">
          <NavLink to="/" end>商品</NavLink>
          <NavLink to="/shops">全部店铺</NavLink>
          <NavLink to="/about">说明</NavLink>
        </nav>
      </div>
    </header>
  )
}

export function Footer() {
  return (
    <footer className="foot">
      <div className="wrap foot-in">
        <p>所有店铺均为非官方渠道，本站不担保交易。</p>
        <Link to="/about">数据说明</Link>
      </div>
    </footer>
  )
}
