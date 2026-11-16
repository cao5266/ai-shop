import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { InfoIcon } from 'lucide-react'
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { EmptyState, ErrorState, GoButton, LowestBadge, Pager, Price, RowsSkeleton } from '@/components/Bits'
import { Tile } from '@/components/Brand'
import { useApi, useCatalog } from '@/lib/useApi'
import { qs } from '@/lib/secureApi'
import { money, when } from '@/lib/format'
import { cn } from '@/lib/utils'
import { durationGroup, specName, toolMeta } from '@/lib/spec'
import type { Offers, SpecInfo, ToolDetail } from '@/lib/types'

export default function ToolPage() {
  const name = decodeURIComponent(useParams().name ?? '')
  const [sp, setSp] = useSearchParams()
  const sort = sp.get('sort') ?? 'price-asc'
  const page = Number(sp.get('page') ?? 1) || 1
  const detail = useApi<ToolDetail>(`/api/v4/tools/${encodeURIComponent(name)}`)
  const d = detail.data
  const catalog = useCatalog(name, !!d && d.specs.length > 0)
  // 以 /tools/:name 的 specs 为准（顺序、n_prices），用 catalog 的结构化字段补全；catalog 失败时退回 label
  const specs: SpecInfo[] = useMemo(() => {
    const extra = new Map((catalog.data?.specs ?? []).map((s) => [s.key, s]))
    return (d?.specs ?? []).map((s) => ({ ...s, ...(extra.get(s.key) ?? {}) }))
  }, [d, catalog.data])
  const [showRest, setShowRest] = useState(false)
  const active = sp.get('spec') || d?.specs[0]?.key || ''
  const offers = useApi<Offers>(d && d.specs.length ? `/api/v4/tools/${encodeURIComponent(name)}/offers${qs({ spec: active, sort, page, size: 20 })}` : null)
  useEffect(() => { document.title = `${name} 价格对比 | AI 订阅比价` }, [name])

  const update = (k: string, v: string, resetPage = true) => {
    const n = new URLSearchParams(sp)
    if (v) n.set(k, v); else n.delete(k)
    if (resetPage) n.delete('page')
    setSp(n, { replace: k === 'page' ? false : true })
  }
  const pageHref = (p: number) => { const n = new URLSearchParams(sp); if (p > 1) n.set('page', String(p)); else n.delete('page'); const s = n.toString(); return s ? `?${s}` : '?' }

  const crumbs = (
    <Breadcrumb className="my-4">
      <BreadcrumbList>
        <BreadcrumbItem><BreadcrumbLink asChild><Link to="/">全部商品</Link></BreadcrumbLink></BreadcrumbItem>
        <BreadcrumbSeparator />
        <BreadcrumbItem><BreadcrumbPage>{name}</BreadcrumbPage></BreadcrumbItem>
      </BreadcrumbList>
    </Breadcrumb>
  )
  if (detail.error) return <>{crumbs}<ErrorState message={detail.error} retry={detail.reload} /></>

  const meta = toolMeta(name)
  const complete = specs.filter((s) => !s.incomplete)
  const rest = specs.filter((s) => s.incomplete)
  const groups = Array.from(new Set(complete.map((s) => durationGroup(s.duration)))).map((k) => ({ kind: k, items: complete.filter((s) => durationGroup(s.duration) === k) }))
  const restOpen = showRest || rest.some((s) => s.key === active)
  const shown = restOpen ? [...groups, { kind: '信息不全，按原标题单独比', items: rest }] : groups
  const cur = specs.find((s) => s.key === active)
  const shopsTotal = d?.n_selling ?? 0

  return (
    <>
      {crumbs}
      <header className="app-head mb-8 grid gap-6 rounded-2xl border bg-card p-5 md:grid-cols-[1fr_auto] md:items-center md:p-7">
        <div className="flex items-center gap-4 md:gap-6">
          <Tile name={name} size="lg" />
          <div className="min-w-0">
            <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">{name}</h1>
            <p className="mt-1 text-sm text-muted-foreground">{meta?.vendor ?? ' '}</p>
            <p className="mt-2 max-w-md text-sm leading-relaxed text-pretty md:text-base">{meta?.tagline ?? ' '}</p>
          </div>
        </div>
        <div className="flex items-end gap-6 border-t pt-5 md:border-t-0 md:border-l md:pt-0 md:pl-8">
          <div>
            <p className="mb-1 text-sm text-muted-foreground">全部规格最低价</p>
            {d?.price != null ? <Price value={d.price} currency={d.currency ?? 'CNY'} big /> : <span className="text-muted-foreground">暂无报价</span>}
          </div>
          <dl className="grid grid-cols-2 gap-x-6 pb-1 text-sm">
            <div><dd className="fig text-2xl font-semibold">{d?.n_specs ?? specs.length}</dd><dt className="text-muted-foreground">个规格</dt></div>
            <div><dd className="fig text-2xl font-semibold">{shopsTotal}</dd><dt className="text-muted-foreground">家在售</dt></div>
          </dl>
        </div>
      </header>
      {d && d.updated_at && <p className="-mt-4 mb-6 text-sm text-muted-foreground">价格更新于 {when(d.updated_at, true)}{specs.length > 0 && d.note ? '。' + d.note : ''}</p>}

      {d && !specs.length && (
        <EmptyState title={d.sold_out[0] ? `曾标价 ${money(d.sold_out[0].min, d.sold_out[0].currency)}，已售罄` : d.status ?? '暂未采到价格'} hint={d.note ?? undefined} action={{ to: '/shops', label: '查看全部店铺' }} />
      )}

      {d && specs.length > 0 && (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[340px_minmax(0,1fr)] lg:items-start lg:gap-8">
          <section aria-labelledby="spec-h" className="min-w-0 lg:sticky lg:top-20">
            <div className="mb-3 flex items-center justify-between">
              <h2 id="spec-h" className="text-lg font-semibold">选择规格</h2>
              <Dialog>
                <DialogTrigger asChild><Button variant="link" className="h-auto p-0 text-muted-foreground"><InfoIcon />价格怎么比</Button></DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>价格怎么比</DialogTitle>
                    <DialogDescription>价格取自店铺公开的商品页，每天更新。类型、时长、档位、区域和交付方式不同的商品分开比，不会把月卡和年卡放在一起排价格。已售罄的商品不计入。下单前请到店铺页面核对价格和售后说明。</DialogDescription>
                  </DialogHeader>
                </DialogContent>
              </Dialog>
            </div>
            <RadioGroup value={active} onValueChange={(v) => update('spec', v)} aria-label="规格" className="-mx-4 flex gap-3 overflow-x-auto px-4 pb-2 lg:mx-0 lg:block lg:space-y-6 lg:overflow-visible lg:px-0 lg:pb-0">
              {shown.map((g) => (
                <div key={g.kind} className="max-lg:contents">
                  <p className="mb-2 hidden items-center gap-2 text-sm font-medium text-muted-foreground lg:flex">{g.kind}</p>
                  <div className="max-lg:contents lg:space-y-2">
                    {g.items.map((s) => (
                      <label key={s.key} className="relative flex w-56 shrink-0 cursor-pointer items-center gap-3 rounded-xl border bg-card px-4 py-3 transition-colors hover:border-foreground/40 has-focus-visible:ring-3 has-focus-visible:ring-ring/50 has-data-checked:border-primary has-data-checked:bg-secondary has-data-checked:ring-1 has-data-checked:ring-primary lg:w-auto">
                        <span className="absolute size-px overflow-hidden opacity-0"><RadioGroupItem value={s.key} /></span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium" title={specName(s)}>{specName(s)}</span>
                          <span className="mt-0.5 block text-xs text-muted-foreground">{s.duration ?? '时长未注明'}，{s.n_shops} 家在售</span>
                        </span>
                        <Price value={s.min} currency={s.currency} suffix="" className="[&>span]:text-2xl" />
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </RadioGroup>
            {rest.length > 0 && (
              <Button variant="outline" className="mt-3 h-10 w-full bg-card" onClick={() => setShowRest((v) => !v)} aria-expanded={restOpen}>
                {restOpen ? '收起信息不全的规格' : `另有 ${rest.length} 个信息不全的规格`}
              </Button>
            )}
          </section>

          <section aria-labelledby="shops-h" className="min-w-0">
            <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 id="shops-h" className="text-lg font-semibold">{cur ? specName(cur) : '在售店铺'}</h2>
                {cur && <p className="mt-0.5 text-sm text-muted-foreground">{cur.duration ?? '时长未注明'}，{cur.n_shops} 家在售，{cur.min === cur.max ? money(cur.min, cur.currency) : `${money(cur.min, cur.currency)} 到 ${money(cur.max, cur.currency)}`}{cur.incomplete ? '，规格信息不全，仅与同标题商品比较' : ''}</p>}
              </div>
              <Select value={sort} onValueChange={(v) => update('sort', v === 'price-asc' ? '' : v)}>
                <SelectTrigger aria-label="排序" className="h-10 w-40 bg-card"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="price-asc">价格从低到高</SelectItem>
                  <SelectItem value="price-desc">价格从高到低</SelectItem>
                  <SelectItem value="recent">最近更新</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {offers.error ? <ErrorState message={offers.error} retry={offers.reload} />
              : !offers.data ? <RowsSkeleton />
              : !offers.data.items.length ? <EmptyState title="这个规格下暂时没有在售商品" />
              : (
                <div className="overflow-hidden rounded-2xl border bg-card" aria-busy={offers.loading}>
                  <ul className="divide-y">
                    {offers.data.items.map((o, i) => {
                      const base = offers.data!.items.reduce((m, x) => Math.min(m, x.price), Infinity)
                      return (
                        <li key={o.id} className={cn('row relative flex flex-col gap-3 p-4 sm:grid sm:grid-cols-[minmax(0,1fr)_9rem_auto] sm:items-center sm:gap-6 sm:p-5', o.lowest && 'bg-secondary/50')}>
                          {o.lowest && <span aria-hidden="true" className="absolute inset-y-0 left-0 w-1 bg-primary" />}
                          <div className="min-w-0">
                            <p className="flex flex-wrap items-center gap-2 font-semibold break-words">{o.shop.name}{o.lowest && <LowestBadge />}</p>
                            <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground" title={o.title}>{o.title}</p>
                            <p className="mt-1 flex flex-wrap gap-x-4 text-xs text-muted-foreground"><span>{o.shop.type}</span><span>更新于 {when(o.observed_at)}</span>{o.stock && <span>库存 {o.stock}</span>}</p>
                          </div>
                          <div className="flex items-baseline justify-between gap-3 sm:block sm:text-right">
                            <Price value={o.price} currency={o.currency} suffix="" />
                            <p className="fig text-sm text-muted-foreground sm:mt-1">{i === 0 || o.price === base ? '本规格最低' : `比最低贵 ${money(Math.round((o.price - base) * 100) / 100)}`}</p>
                          </div>
                          <GoButton href={o.go} label={`去店铺：${o.shop.name}`} className="sm:w-28" />
                        </li>
                      )
                    })}
                  </ul>
                </div>
              )}
            {offers.data && <Pager page={page} total={offers.data.total} size={offers.data.size} href={pageHref} onPage={(p) => { update('page', p > 1 ? String(p) : '', false); window.scrollTo({ top: 0 }) }} />}
          </section>
        </div>
      )}
    </>
  )
}
