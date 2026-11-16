import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { InfoIcon } from 'lucide-react'
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { EmptyState, ErrorState, GoButton, LowestBadge, Pager, Price, RowsSkeleton } from '@/components/Bits'
import { Tile } from '@/components/Brand'
import { useAllSpecs, useApi } from '@/lib/useApi'
import { qs } from '@/lib/secureApi'
import { money, shopTitle, stockText, when } from '@/lib/format'
import { cn } from '@/lib/utils'
import { durationGroup, lowestShopName, periodText, specName, toolMeta } from '@/lib/spec'
import type { Offers, Spec, ToolDetail } from '@/lib/types'

export default function ToolPage() {
  const name = decodeURIComponent(useParams().name ?? '')
  return <ToolPageInner key={name} name={name} />   // 换商品时整页重置，避免短暂显示上一个商品的数据
}

/** 详情加载中的占位：规格列表 + 在售店铺列表（头部价格区在页面里单独占位） */
function BodySkeleton() {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[340px_minmax(0,1fr)] lg:gap-8" aria-hidden="true">
      <section className="space-y-6">
        <Skeleton className="h-7 w-28" />
        {[3, 2].map((n, g) => (
          <div key={g} className="space-y-2">
            <Skeleton className="h-5 w-16" />
            {Array.from({ length: n }, (_, i) => <Skeleton key={i} className="h-14 w-full rounded-xl" />)}
          </div>
        ))}
      </section>
      <section>
        <Skeleton className="mb-4 h-7 w-48" />
        <RowsSkeleton />
      </section>
    </div>
  )
}

function ToolPageInner({ name }: { name: string }) {
  const [sp, setSp] = useSearchParams()
  const sort = sp.get('sort') ?? 'price-asc'
  const page = Number(sp.get('page') ?? 1) || 1
  const detail = useApi<ToolDetail>(`/api/v4/tools/${encodeURIComponent(name)}`)
  const d = detail.loading ? null : detail.data   // d 为空 = 还在加载，此时不能显示「暂无报价 / 0」
  // /tools/:name 已返回全量规格；若少于 n_specs（接口分页），按 total_pages 翻页补全
  const all = useAllSpecs(name, d?.specs, d?.n_specs)
  const specs: Spec[] = all.specs ?? []
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  // spec 参数可以是 key（页面内选择），也可以是 label（首页价目板链接，接口入门档不带 key）
  const want = sp.get('spec')
  const cur = specs.find((s) => s.key === want) ?? (want ? specs.find((s) => s.label === want && s.currency === 'CNY') : undefined) ?? specs[0]
  const active = cur?.key ?? ''
  const offers = useApi<Offers>(d && cur ? `/api/v4/tools/${encodeURIComponent(name)}/offers${qs({ spec: active, sort, page, size: 20 })}` : null)
  useEffect(() => { document.title = `${name} 价格对比 | AI 订阅比价` }, [name])

  const update = (k: string, v: string, resetPage = true) => {
    const n = new URLSearchParams(sp)
    if (v) n.set(k, v); else n.delete(k)
    if (resetPage) n.delete('page')
    setSp(n, { replace: k === 'page' ? false : true })
  }
  const pageHref = (p: number) => { const n = new URLSearchParams(sp); if (p > 1) n.set('page', String(p)); else n.delete('page'); const s = n.toString(); return s ? `?${s}` : '?' }

  const crumbs = (
    <Breadcrumb className="my-1">
      <BreadcrumbList>
        <BreadcrumbItem><BreadcrumbLink asChild><Link to="/" className="inline-flex min-h-11 items-center">全部商品</Link></BreadcrumbLink></BreadcrumbItem>
        <BreadcrumbSeparator />
        <BreadcrumbItem><BreadcrumbPage>{name}</BreadcrumbPage></BreadcrumbItem>
      </BreadcrumbList>
    </Breadcrumb>
  )
  if (detail.error) return <>{crumbs}<ErrorState message={detail.error} retry={detail.reload} /></>

  const meta = toolMeta(name)
  const GROUP_LIMIT = 8
  const groups = Array.from(new Set(specs.map((s) => durationGroup(s.period)))).map((k) => {
    const items = specs.filter((s) => durationGroup(s.period) === k)
    const open = expanded[k] || items.length <= GROUP_LIMIT || items.some((s) => s.key === active)
    return { kind: k, items: open ? items : items.slice(0, GROUP_LIMIT), hidden: open ? 0 : items.length - GROUP_LIMIT }
  })
  const shopsTotal = d?.n_selling ?? 0
  const price = d?.starting_price ?? d?.price ?? null

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
            {!d ? <Skeleton className="h-12 w-36" aria-hidden="true" /> : price != null ? <Price value={price} currency={d.currency ?? 'CNY'} big /> : <span className="text-muted-foreground">暂无报价</span>}
          </div>
          <dl className="grid grid-cols-2 gap-x-6 pb-1 text-sm">
            <div><dd className="fig text-2xl font-semibold">{d ? d.n_specs : <Skeleton className="h-8 w-8" aria-hidden="true" />}</dd><dt className="text-muted-foreground">个规格</dt></div>
            <div><dd className="fig text-2xl font-semibold">{d ? shopsTotal : <Skeleton className="h-8 w-8" aria-hidden="true" />}</dd><dt className="text-muted-foreground">家在售</dt></div>
          </dl>
        </div>
      </header>
      {d && d.updated_at && <p className="-mt-4 mb-6 text-sm text-muted-foreground">价格更新于 {when(d.updated_at, true)}{specs.length > 0 && d.note ? '。' + d.note : ''}</p>}

      {!d && <BodySkeleton />}
      {d && !specs.length && (
        <EmptyState title={d.sold_out[0] ? `曾标价 ${money(d.sold_out[0].lowest_price, d.sold_out[0].currency)}，已售罄` : d.status ?? '暂未采到价格'} hint={d.note && d.note !== (d.sold_out[0] ? '' : d.status) ? d.note : undefined} action={{ to: '/shops', label: '查看全部店铺' }} />
      )}

      {d && specs.length > 0 && (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[340px_minmax(0,1fr)] lg:items-start lg:gap-8">
          <section aria-labelledby="spec-h" className="min-w-0 lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto lg:pr-1">
            <div className="mb-3 flex items-center justify-between">
              <h2 id="spec-h" className="text-lg font-semibold">选择规格</h2>
              <Dialog>
                <DialogTrigger asChild><Button variant="link" className="h-11 px-2 text-muted-foreground"><InfoIcon />价格怎么比</Button></DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>价格怎么比</DialogTitle>
                    <DialogDescription>价格取自店铺公开的商品页，每天更新。类型、时长、档位、区域和交付方式不同的商品分开比，不会把月卡和年卡放在一起排价格。已售罄的商品不计入。下单前请到店铺页面核对价格和售后说明。</DialogDescription>
                  </DialogHeader>
                </DialogContent>
              </Dialog>
            </div>
            <RadioGroup value={active} onValueChange={(v) => update('spec', v)} aria-label="规格" className="block space-y-6">
              {groups.map((g) => (
                <div key={g.kind}>
                  <p className="mb-2 flex items-center gap-2 text-sm font-medium text-muted-foreground">{g.kind}</p>
                  <div className="space-y-2">
                    {g.items.map((s) => (
                      <label key={s.key} className="relative flex w-full cursor-pointer items-center gap-3 min-h-14 rounded-xl border bg-card px-4 py-3 transition-colors hover:border-foreground/40 has-focus-visible:ring-3 has-focus-visible:ring-ring/50 has-data-checked:border-primary has-data-checked:bg-secondary has-data-checked:ring-1 has-data-checked:ring-primary">
                        <span className="absolute size-px overflow-hidden opacity-0"><RadioGroupItem value={s.key} /></span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium" title={specName(s)}>{specName(s)}</span>
                          <span className="mt-0.5 block text-xs text-muted-foreground">{[periodText(s), `${s.shop_count} 家在售`].filter(Boolean).join('，')}</span>
                        </span>
                        <Price value={s.lowest_price} currency={s.currency} suffix="" className="[&>span]:text-2xl" />
                      </label>
                    ))}
                  </div>
                  {g.hidden > 0 && <button type="button" onClick={() => setExpanded((e) => ({ ...e, [g.kind]: true }))} className="mt-2 h-11 w-full rounded-xl border border-dashed text-sm text-muted-foreground hover:border-foreground/40">展开其余 {g.hidden} 个规格</button>}
                </div>
              ))}
            </RadioGroup>
            {all.partial && <p className="mt-3 text-xs text-muted-foreground">正在加载其余规格……</p>}
            {all.error && <p className="mt-3 text-xs text-destructive">部分规格没有加载成功，请刷新重试。</p>}
          </section>

          <section aria-labelledby="shops-h" className="min-w-0">
            <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 id="shops-h" className="text-lg font-semibold">{cur ? specName(cur) : '在售店铺'}</h2>
                {cur && <p className="mt-0.5 text-sm text-muted-foreground">{[periodText(cur), `${cur.shop_count} 家在售`].filter(Boolean).join('，')}，最低 {money(cur.lowest_price, cur.currency)}{lowestShopName(cur) ? `（${lowestShopName(cur)}）` : ''}</p>}
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
                            <p className="flex flex-wrap items-center gap-2 font-semibold break-words">{shopTitle(o.shop.name).title}{o.lowest && <LowestBadge />}</p>
                            <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground" title={o.title}>{o.title}</p>
                            <p className="mt-1 flex flex-wrap gap-x-4 text-xs text-muted-foreground"><span>{o.shop.type}</span><span>更新于 {when(o.observed_at)}</span>{stockText(o.stock) && <span>{stockText(o.stock)}</span>}</p>
                          </div>
                          <div className="flex items-baseline justify-between gap-3 sm:block sm:text-right">
                            <Price value={o.price} currency={o.currency} suffix="" />
                            <p className="fig text-sm text-muted-foreground sm:mt-1">{i === 0 || o.price === base ? '本规格最低' : `比最低贵 ${money(Math.round((o.price - base) * 100) / 100)}`}</p>
                          </div>
                          <GoButton href={o.go} label={`去店铺：${shopTitle(o.shop.name).title}`} className="sm:w-28" />
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
