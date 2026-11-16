import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRightIcon } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState, Price } from '@/components/Bits'
import { Tile } from '@/components/Brand'
import { SearchInput } from '@/components/SearchInput'
import { useApi, useCatalogs } from '@/lib/useApi'
import { entrySpec, specName, toolCategory, toolMeta } from '@/lib/spec'
import { money, when } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { Home as HomeData, SpecInfo, Tool, ToolSpecs } from '@/lib/types'

function SpecLine({ s, lowest }: { s: SpecInfo; lowest: boolean }) {
  return (
    <li className="flex items-baseline gap-2 text-sm">
      <span className="shrink-0 text-xs text-muted-foreground">{s.duration ?? '时长未注明'}</span>
      <span className="min-w-0 truncate font-medium">{specName(s)}</span>
      <span aria-hidden="true" className="mb-1 min-w-3 flex-1 self-end border-b border-dotted border-foreground/25" />
      <span className={cn('fig shrink-0 text-lg font-semibold', lowest ? 'text-price' : 'text-foreground')}>{money(s.min, s.currency)}</span>
    </li>
  )
}

function ToolCard({ t, catalog }: { t: Tool; catalog?: ToolSpecs }) {
  const specs = catalog?.specs
  // 大字起价与下方规格行同源（规格接口的 starting_price）；规格接口没返回时退回 /home 的 price
  const price = catalog?.starting_price ?? t.price
  const currency = catalog?.starting_price != null ? catalog.currency : t.currency
  const meta = toolMeta(t.name)
  // 卡片里展示的规格：优先完整规格，按最低价排序取前 3 个
  const complete = (specs ?? []).filter((s) => !s.incomplete && s.currency === 'CNY').sort((a, b) => a.min - b.min)
  const shown = complete.slice(0, 3)
  const low = shown[0]
  const spread = low && low.max > 0 ? Math.round((1 - low.min / low.max) * 100) : 0
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

      <div className="mt-5 flex items-end justify-between gap-3">
        {price != null ? <Price value={price} currency={currency ?? 'CNY'} big suffix="起" className="[&>span:first-child]:text-5xl" /> : <span className="text-sm text-muted-foreground">{t.status ?? '暂未采到价格'}</span>}
        {low && spread > 0 && <p className="pb-1 text-right text-xs leading-snug text-muted-foreground">最高 <span className="fig text-sm font-semibold text-foreground">{money(low.max, low.currency)}</span><br />价差 {spread}%</p>}
      </div>

      {shown.length > 0 && (
        <ul className="mt-4 space-y-1.5 border-t pt-4">
          {shown.map((s, i) => <SpecLine key={s.key} s={s} lowest={i === 0} />)}
        </ul>
      )}

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

/** 价目板：每个商品取“入门档”（完整规格、优先 1 月、最低价），按在售店铺数挑最热门的 6 个 */
function Board({ tools, catalogs }: { tools: Tool[]; catalogs: Record<string, ToolSpecs> }) {
  const rows = tools
    .map((t) => ({ t, s: entrySpec(catalogs[t.name]?.specs ?? []) }))
    .filter((r): r is { t: Tool; s: SpecInfo } => !!r.s)
    .sort((a, b) => b.t.n_selling - a.t.n_selling)
    .slice(0, 6)
  if (!rows.length) return null
  return (
    <aside aria-label="入门档最低价" className="hidden rounded-2xl border bg-card lg:block">
      <div className="flex items-baseline justify-between border-b px-5 py-3.5">
        <h2 className="text-sm font-semibold">入门档最低价</h2>
        <span className="text-xs text-muted-foreground">优先 1 月 / 人民币</span>
      </div>
      <ul className="divide-y">
        {rows.map(({ t, s }) => (
          <li key={t.name}>
            <Link to={`/tool/${encodeURIComponent(t.name)}?spec=${encodeURIComponent(s.key)}`} className="flex items-center gap-3 px-5 py-3 outline-none transition-colors hover:bg-muted/60 focus-visible:bg-muted">
              <Tile name={t.name} size="xs" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{t.name} <span className="font-normal text-muted-foreground">{specName(s)}</span></p>
                <p className="truncate text-xs text-muted-foreground">{s.duration ?? '时长未注明'}，共 {s.n_shops} 家在售</p>
              </div>
              <span className="fig text-2xl font-semibold text-price"><span className="mr-0.5 text-[0.62em] font-medium">¥</span>{new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(s.min)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </aside>
  )
}

export default function Home() {
  const { data, error, loading, reload } = useApi<HomeData>('/api/v4/home')
  const [cat, setCat] = useState('全部')
  const { catalogs } = useCatalogs(useMemo(() => data?.tools.filter((t) => t.n_specs > 0).map((t) => t.name) ?? [], [data]))
  useEffect(() => { document.title = 'AI 订阅比价' }, [])
  const cats = useMemo(() => ['全部', ...Array.from(new Set(data?.tools.map(toolCategory) ?? []))], [data])
  const tools = data?.tools.filter((t) => cat === '全部' || toolCategory(t) === cat) ?? []
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
            {[['店铺', data ? `${data.total_shops}` : '—'], ['商品', data ? `${data.tools.length}` : '—'], ['规格', data ? `${data.tools.reduce((a, t) => a + t.n_specs, 0)}` : '—']].map(([k, v]) => (
              <div key={k}><dd className="fig text-3xl font-semibold">{v}</dd><dt className="text-muted-foreground">{k}</dt></div>
            ))}
            <div className="hidden sm:block"><dd className="pt-2 text-sm">{data ? when(data.updated_at, true) : '—'}</dd><dt className="text-muted-foreground">价格更新时间</dt></div>
          </dl>
        </div>
        {data && <Board tools={data.tools} catalogs={catalogs} />}
      </section>

      <section aria-labelledby="tools-h">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
          <h2 id="tools-h" className="text-2xl font-semibold tracking-tight">全部商品</h2>
          <div role="group" aria-label="按分类筛选" className="-mx-4 flex max-w-[calc(100%+2rem)] gap-1.5 overflow-x-auto px-4 sm:mx-0 sm:max-w-none sm:px-0">
            {cats.map((c) => (
              <button key={c} type="button" aria-pressed={cat === c} onClick={() => setCat(c)}
                className={cn('h-10 shrink-0 rounded-full border px-4 text-sm transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
                  cat === c ? 'border-foreground bg-foreground text-background' : 'bg-card hover:border-foreground/40')}>{c}</button>
            ))}
          </div>
        </div>
        {error ? <ErrorState message={error} retry={reload} /> : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {loading && !data ? Array.from({ length: 6 }, (_, i) => <CardSkeleton key={i} />) : tools.map((t) => <ToolCard key={t.name} t={t} catalog={catalogs[t.name]} />)}
          </div>
        )}
      </section>
    </>
  )
}
