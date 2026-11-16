import { useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { SearchBox } from '../components/Chrome'
import { Empty, ErrorBox, GoButton, Pager } from '../components/Bits'
import { useApi } from '../lib/useApi'
import { qs } from '../lib/secureApi'
import { money, specText } from '../lib/format'
import type { Home, Shops as ShopsData } from '../lib/types'

export default function Shops() {
  const [sp, setSp] = useSearchParams()
  const q = sp.get('q') ?? '', type = sp.get('type') ?? '', product = sp.get('product') ?? ''
  const sort = sp.get('sort') ?? 'price-asc', page = Number(sp.get('page') ?? 1) || 1
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); if (v && !(k === 'page' && v === '1')) n.set(k, v); else n.delete(k); if (k !== 'page') n.delete('page'); setSp(n) }
  const home = useApi<Home>('/api/v4/home')
  const list = useApi<ShopsData>(`/api/v4/shops${qs({ q, type, product, sort, page, size: 20 })}`)
  useEffect(() => { document.title = '全部店铺 | AI 订阅比价' }, [])
  return (
    <>
      <h1 className="page-h">全部店铺</h1>
      <div className="filters">
        <div className="filters-search"><SearchBox key={q} initial={q} /></div>
        <label className="sel"><span className="sr">商品</span>
          <select value={product} onChange={(e) => set('product', e.target.value)}>
            <option value="">全部商品</option>
            {home.data?.tools.map((t) => <option key={t.name} value={t.name}>{t.name}</option>)}
          </select>
        </label>
        <label className="sel"><span className="sr">店铺类型</span>
          <select value={type} onChange={(e) => set('type', e.target.value)}>
            <option value="">全部类型</option>
            {home.data?.types.map((t) => <option key={t.name} value={t.name}>{t.name}</option>)}
          </select>
        </label>
        <label className="sel"><span className="sr">排序</span>
          <select value={sort} onChange={(e) => set('sort', e.target.value)}>
            <option value="price-asc">最低价从低到高</option>
            <option value="price-desc">最低价从高到低</option>
            <option value="recent">最近更新</option>
            <option value="name">店名</option>
          </select>
        </label>
      </div>
      {list.error ? <ErrorBox message={list.error} retry={list.reload} /> : (
        <>
          <p className="muted count" aria-live="polite">{list.data ? (q ? `“${q}” 共 ${list.data.total} 家店铺` : `共 ${list.data.total} 家店铺`) : ' '}</p>
          {list.data && !list.data.items.length ? <Empty title="没有找到匹配的店铺" hint="换个关键词，或者把商品、类型改回“全部”。" /> : (
            <ul className="rows" aria-busy={list.loading}>
              {list.data?.items.map((s) => (
                <li key={s.id} className="row">
                  <div className="row-main">
                    <p className="row-shop"><Link to={`/shop/${s.id}`}>{s.name}</Link></p>
                    <p className="row-title">{s.products.length ? s.products.join('、') : '暂未识别到商品'}</p>
                    <p className="row-meta"><span>{s.domain}</span><span>{s.type}</span></p>
                  </div>
                  <div className="row-price">
                    {s.price != null ? (
                      <>
                        <p className="price"><span className="num">{money(s.price)}</span><span className="from">起</span></p>
                        <p className="muted price-note">{[s.price_product, specText(s.price_spec)].filter(Boolean).join('，')}</p>
                      </>
                    ) : <p className="muted">暂未采到价格</p>}
                  </div>
                  <div className="row-go"><GoButton href={s.go} label={`去店铺：${s.name}`} /></div>
                </li>
              ))}
            </ul>
          )}
          {list.data && <Pager page={page} total={list.data.total} size={list.data.size} onPage={(p) => { set('page', String(p)); window.scrollTo({ top: 0 }) }} />}
        </>
      )}
    </>
  )
}
