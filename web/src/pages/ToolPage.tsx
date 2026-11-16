import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Back, Empty, ErrorBox, GoButton, Pager, Tile } from '../components/Bits'
import { useApi } from '../lib/useApi'
import { qs } from '../lib/secureApi'
import { money, specText, when } from '../lib/format'
import type { Offers, ToolDetail } from '../lib/types'

export default function ToolPage() {
  const name = decodeURIComponent(useParams().name ?? '')
  const detail = useApi<ToolDetail>(`/api/v4/tools/${encodeURIComponent(name)}`)
  const [spec, setSpec] = useState('')
  const [sort, setSort] = useState('price-asc')
  const [page, setPage] = useState(1)
  useEffect(() => { setSpec(''); setPage(1) }, [name])
  useEffect(() => { document.title = `${name} 价格对比 | AI 订阅比价` }, [name])
  const active = spec || detail.data?.specs[0]?.key || ''
  const offers = useApi<Offers>(detail.data && detail.data.specs.length ? `/api/v4/tools/${encodeURIComponent(name)}/offers${qs({ spec: active, sort, page, size: 20 })}` : null)
  const d = detail.data

  if (detail.error) return <><Back to="/">全部商品</Back><ErrorBox message={detail.error} retry={detail.reload} /></>
  return (
    <>
      <Back to="/">全部商品</Back>
      <header className="app-head">
        <Tile name={name} size={96} />
        <div>
          <h1>{name}</h1>
          <p className="muted">
            {d ? (d.n_selling ? `${d.n_selling} 家店铺在售，价格更新于 ${when(d.updated_at, true)}` : `${d.n_shops} 家店铺提到，暂无在售报价`) : ' '}
          </p>
          {d?.price != null && <p className="price price-xl"><span className="num">{money(d.price, d.currency ?? 'CNY')}</span><span className="from">起</span></p>}
        </div>
      </header>
      {d && !d.specs.length && (
        <div className="state">
          <p className="state-t">{d.sold_out[0] ? `曾标价 ${money(d.sold_out[0].min, d.sold_out[0].currency)}，已售罄` : d.status ?? '暂未采到价格'}</p>
          {d.note && <p className="muted note">{d.note}</p>}
        </div>
      )}
      {d && d.specs.length > 0 && (
        <>
          <h2 className="sec-h">选择规格</h2>
          <fieldset className="specs-set">
            <legend className="sr">规格</legend>
            <div className="specs">
              {d.specs.map((s) => (
                <label key={s.key} className="spec">
                  <input type="radio" name="spec" checked={s.key === active} onChange={() => { setSpec(s.key); setPage(1) }} />
                  <span className="spec-l">{(d.members.length > 1 ? s.product + '，' : '') + (specText(s.label) || '规格未注明')}</span>
                  <span className="spec-p num">{money(s.min, s.currency)}<span className="from">起</span></span>
                  <span className="muted spec-n">{s.n_shops} 家店铺</span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="list-head">
            <h2 className="sec-h">在售店铺</h2>
            <label className="sel"><span className="sr">排序</span>
              <select value={sort} onChange={(e) => { setSort(e.target.value); setPage(1) }}>
                <option value="price-asc">价格从低到高</option>
                <option value="price-desc">价格从高到低</option>
                <option value="recent">最近更新</option>
              </select>
            </label>
          </div>
          {offers.error ? <ErrorBox message={offers.error} retry={offers.reload} />
            : offers.data && !offers.data.items.length ? <Empty title="这个规格下暂时没有在售商品" />
            : (
              <ul className="rows" aria-busy={offers.loading}>
                {offers.data?.items.map((o) => (
                  <li key={o.id} className="row">
                    <div className="row-main">
                      <p className="row-shop">{o.shop.name}</p>
                      <p className="row-title">{o.title}</p>
                      <p className="row-meta"><span>{o.shop.type}</span><span>更新于 {when(o.observed_at)}</span>{o.stock && <span>库存 {o.stock}</span>}</p>
                    </div>
                    <p className="row-price price"><span className="num">{money(o.price, o.currency)}</span>{o.lowest && <span className="tag-low">最低</span>}</p>
                    <div className="row-go"><GoButton href={o.go} label={`去店铺：${o.shop.name}`} /></div>
                  </li>
                ))}
              </ul>
            )}
          {offers.data && <Pager page={page} total={offers.data.total} size={offers.data.size} onPage={(p) => { setPage(p); window.scrollTo({ top: 0 }) }} />}
        </>
      )}
    </>
  )
}
