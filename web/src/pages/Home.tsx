import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { SearchBox } from '../components/Chrome'
import { ErrorBox, Tile } from '../components/Bits'
import { useApi } from '../lib/useApi'
import { money, specText, when } from '../lib/format'
import type { Home as HomeData, Tool } from '../lib/types'

function Card({ t }: { t: Tool }) {
  const priced = t.price != null
  return (
    <Link to={`/tool/${encodeURIComponent(t.name)}`} className="card">
      <div className="card-head">
        <Tile name={t.name} size={56} />
        <div className="card-name">
          <h3>{t.name}</h3>
          <p className="muted">{t.n_selling ? `${t.n_selling} 家店铺在售` : `${t.n_shops} 家店铺提到`}</p>
        </div>
      </div>
      <div className="card-price">
        {priced ? (
          <>
            <p className="price"><span className="num">{money(t.price!, t.currency ?? 'CNY')}</span><span className="from">起</span></p>
            <p className="muted">{specText(t.spec)}</p>
          </>
        ) : (
          <p className="muted">{t.sold_out[0] ? `曾标价 ${money(t.sold_out[0].min, t.sold_out[0].currency)}，已售罄` : t.status ?? '暂未采到价格'}</p>
        )}
      </div>
    </Link>
  )
}

export default function Home() {
  const { data, error, loading, reload } = useApi<HomeData>('/api/v4/home')
  useEffect(() => { document.title = 'AI 订阅比价' }, [])
  return (
    <>
      <section className="hero">
        <h1>AI 工具订阅比价</h1>
        <p className="lead">按工具比较各家店铺的在售价格。价格取自店铺商品页，期限、额度和交付方式不同的商品分开比。</p>
        <SearchBox large />
        <p className="muted hero-meta">{data ? `价格更新于 ${when(data.updated_at, true)}，覆盖 ${data.total_shops} 家店铺` : ' '}</p>
      </section>
      <section aria-labelledby="tools-h">
        <h2 id="tools-h" className="sec-h">全部商品</h2>
        {error ? <ErrorBox message={error} retry={reload} /> : (
          <div className="grid">
            {loading && !data ? Array.from({ length: 8 }, (_, i) => <div key={i} className="card card-skel" aria-hidden="true" />)
              : data?.tools.map((t) => <Card key={t.name} t={t} />)}
          </div>
        )}
      </section>
    </>
  )
}
