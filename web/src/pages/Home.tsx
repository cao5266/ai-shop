import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRightIcon } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState, Price } from '@/components/Bits'
import { Tile } from '@/components/Brand'
import { SearchInput } from '@/components/SearchInput'
import { useApi } from '@/lib/useApi'
import { hasOffer, periodText, specName, toolCategory, toolMeta } from '@/lib/spec'
import { money, when } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { Home as HomeData, Tool } from '@/lib/types'

function ToolCard({ t }: { t: Tool }) {
  const meta = toolMeta(t.name)
  const price = t.starting_price ?? t.price
  const e = t.entry_spec
  return (
    <Link to={`/tool/${encodeURIComponent(t.name)}`} className="card group flex h-full flex-col rounded-2xl border bg-card p-5 outline-none transition-colors hover:border-foreground/30 focus-visible:ring-3 focus-visible:ring-ring/50">
      <div className="flex items-start gap-3">
        <Tile name={t.name} size="sm" />
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-base leading-tight font-semibold">{t.name}</h3>
          {meta && <p className="mt-0.5 text-xs text-muted-foreground">{meta.vendor}</p>}
        </div>
        <span className="rounded-md bg-secondary px-2 py-1 text-xs font-medium text-secondary-foreground">{t.n_selling} 家在售</span>
      </div>

      <div className="mt-5">
        {price != null ? <Price value={price} currency={t.currency ?? 'CNY'} big suffix="起" className="[&>span:first-child]:text-5xl" /> : <span className="text-sm leading-relaxed text-muted-foreground">{t.status ?? '暂未采到价格'}</span>}
      </div>

      {e && t.entry_price != null && (
        <div className="mt-4 flex items-baseline gap-2 border-t pt-4 text-sm">
          <span className="shrink-0 text-xs text-muted-foreground">入门档</span>
          <span className="min-w-0 truncate font-medium">{[e.period, specName(e)].filter(Boolean).join(' ')}</span>
          <span aria-hidden="true" className="mb-1 min-w-3 flex-1 self-end border-b border-dotted border-foreground/25" />
          <span className="fig shrink-0 text-lg font-semibold">{money(t.entry_price, t.currency ?? 'CNY')}</span>
        </div>
      )}
      {e && t.entry_shop_count ? <p className="mt-1 text-xs text-muted-foreground">该规格 {t.entry_shop_count} 家在售</p> : null}

      <div className="mt-auto flex items-center justify-between pt-4 text-sm">
        <span className="text-muted-foreground">{t.n_specs > 0 ? <>共 <span className="fig text-base font-semibold text-foreground">{t.n_specs}</span> 个规格</> : '暂无在售规格'}</span>
        <span className="inline-flex items-center gap-0.5 font-medium text-primary">{t.n_specs > 0 ? '比较价格' : '查看说明'}<ChevronRightIcon className="size-4 transition-transform group-hover:translate-x-0.5" /></span>
      </div>
    </Link>
  )
}

function CardSkeleton() {
  return (
    <div className="h-80 rounded-2xl border bg-card p-5" aria-hidden="true">
      <div className="flex gap-3"><Skeleton className="size-10 rounded-[22%]" /><Skeleton className="h-10 w-28" /></div>
      <Skeleton className="mt-6 h-12 w-32" />
      <div className="mt-6 space-y-3"><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-full" /></div>
    </div>
  )
}

/** 价目板：直接用 /home 每个商品的入门档（entry_spec / entry_price），按在售店铺数取最热门的 6 个 */
function Board({ tools }: { tools: Tool[] }) {
  const rows = tools.filter((t) => t.entry_spec && t.entry_price != null).sort((a, b) => b.n_selling - a.n_selling).slice(0, 6)
  if (!rows.length) return null
  return (
    <aside aria-label="入门档最低价" className="hidden rounded-2xl border bg-card lg:block">
      <div className="flex items-baseline justify-between border-b px-5 py-3.5">
        <h2 className="text-sm font-semibold">入门档最低价</h2>
        <span className="text-xs text-muted-foreground">优先月卡 / 人民币</span>
      </div>
      <ul className="divide-y">
        {rows.map((t) => {
          const e = t.entry_spec!
          return (
            <li key={t.name}>
              <Link to={`/tool/${encodeURIComponent(t.name)}?spec=${encodeURIComponent(e.label)}`} className="flex items-center gap-3 px-5 py-3 outline-none transition-colors hover:bg-muted/60 focus-visible:bg-muted">
                <Tile name={t.name} size="xs" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{t.name} <span className="font-normal text-muted-foreground">{specName(e).split(' ').filter((w) => !t.name.toLowerCase().split(' ').includes(w.toLowerCase())).join(' ')}</span></p>
                  <p className="truncate text-xs text-muted-foreground">{[periodText(e), `共 ${t.entry_shop_count ?? 0} 家在售`].filter(Boolean).join('，')}</p>
                </div>
                <span className="fig text-2xl font-semibold text-price"><span className="mr-0.5 text-[0.62em] font-medium">¥</span>{new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(t.entry_price!)}</span>
              </Link>
            </li>
          )
        })}
      </ul>
    </aside>
  )
}

export default function Home() {
  const { data, error, loading, reload } = useApi<HomeData>('/api/v4/home')
  const [cat, setCat] = useState('全部')
  useEffect(() => { document.title = 'AI 订阅比价' }, [])
  const shown = useMemo(() => data?.tools.filter(hasOffer) ?? [], [data])
  const cats = useMemo(() => ['全部', ...Array.from(new Set(shown.map(toolCategory)))], [shown])
  const tools = shown.filter((t) => cat === '全部' || toolCategory(t) === cat)
  return (
    <>
      <section className="grid items-center gap-10 py-10 md:py-14 lg:grid-cols-[minmax(0,1fr)_420px] lg:gap-14">
        <div>
          <h1 className="text-4xl leading-[1.15] font-semibold tracking-tight text-balance md:text-5xl">
            买 AI 订阅之前，<br />先看各家报价
          </h1>
          <p className="mt-4 mb-7 max-w-lg text-base leading-relaxed text-muted-foreground text-pretty md:text-lg">月卡、年卡、成品号、代充、组合套餐，规格不同的商品分开比，同一规格下谁最便宜一目了然。</p>
          <div className="max-w-xl"><SearchInput large /></div>
          <dl className="mt-7 flex gap-8 text-sm">
            {[['店铺', data ? `${data.total_shops}` : '—'], ['商品', data ? `${shown.length}` : '—'], ['规格', data ? `${shown.reduce((a, t) => a + t.n_specs, 0)}` : '—']].map(([k, v]) => (
              <div key={k}><dd className="fig text-3xl font-semibold">{v}</dd><dt className="text-muted-foreground">{k}</dt></div>
            ))}
            <div className="hidden sm:block"><dd className="pt-2 text-sm">{data ? when(data.updated_at, true) : '—'}</dd><dt className="text-muted-foreground">价格更新时间</dt></div>
          </dl>
        </div>
        {data && <Board tools={shown} />}
      </section>

      <section aria-labelledby="tools-h">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
          <h2 id="tools-h" className="text-2xl font-semibold tracking-tight">全部商品</h2>
          <div role="group" aria-label="按分类筛选" className="-mx-4 flex max-w-[calc(100%+2rem)] gap-1.5 overflow-x-auto px-4 sm:mx-0 sm:max-w-none sm:px-0">
            {cats.map((c) => (
              <button key={c} type="button" aria-pressed={cat === c} onClick={() => setCat(c)}
                className={cn('h-11 shrink-0 rounded-full border px-4 text-sm transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
                  cat === c ? 'border-foreground bg-foreground text-background' : 'bg-card hover:border-foreground/40')}>{c}</button>
            ))}
          </div>
        </div>
        {error ? <ErrorState message={error} retry={reload} /> : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {loading && !data ? Array.from({ length: 6 }, (_, i) => <CardSkeleton key={i} />) : tools.map((t) => <ToolCard key={t.name} t={t} />)}
          </div>
        )}
      </section>
    </>
  )
}
