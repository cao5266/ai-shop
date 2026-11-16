import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Back, Empty, ErrorBox, GoButton } from '../components/Bits'
import { useApi } from '../lib/useApi'
import { money, specText, when } from '../lib/format'
import type { Listing, ShopDetail } from '../lib/types'

function ListingRow({ l }: { l: Listing }) {
  return (
    <li className="row">
      <div className="row-main">
        <p className="row-title strong">{l.title}</p>
        <p className="row-meta">
          {l.product && <span>{l.product}</span>}
          {l.spec && <span>{specText(l.spec)}</span>}
          <span>更新于 {when(l.observed_at)}</span>
          {l.stock && <span>库存 {l.stock}</span>}
        </p>
        {l.history.length > 1 && <p className="row-meta"><span>价格变动 {l.history.map((h) => money(h.price)).join(' 到 ')}</span></p>}
      </div>
      <p className="row-price price"><span className="num">{money(l.price, l.currency)}</span></p>
      <div className="row-go">{l.active && <GoButton href={l.go} label={`查看商品：${l.title}`}>查看商品</GoButton>}</div>
    </li>
  )
}

export default function ShopPage() {
  const id = useParams().id ?? ''
  const { data, error, reload } = useApi<ShopDetail>(`/api/v4/shops/${encodeURIComponent(id)}`)
  useEffect(() => { document.title = data ? `${data.name} | AI 订阅比价` : 'AI 订阅比价' }, [data])
  if (error) return <><Back to="/shops">全部店铺</Back><ErrorBox message={error} retry={reload} /></>
  const on = data?.listings.filter((l) => l.active) ?? [], off = data?.listings.filter((l) => !l.active) ?? []
  return (
    <>
      <Back to="/shops">全部店铺</Back>
      <header className="shop-head">
        <div>
          <h1 className="shop-name">{data?.name ?? ' '}</h1>
          <p className="muted">{data ? `${data.domain}，${data.type}，更新于 ${when(data.updated_at, true)}` : ' '}</p>
        </div>
        {data && <GoButton href={data.go}>去店铺</GoButton>}
      </header>
      {data && !data.listings.length && <Empty title="暂未采到这家店铺的商品价格" hint={data.crawl_status ?? undefined} />}
      {on.length > 0 && <><h2 className="sec-h">在售商品</h2><ul className="rows">{on.map((l) => <ListingRow key={l.id} l={l} />)}</ul></>}
      {off.length > 0 && <details className="off"><summary>已售罄或下架（{off.length}）</summary><ul className="rows">{off.map((l) => <ListingRow key={l.id} l={l} />)}</ul></details>}
    </>
  )
}
