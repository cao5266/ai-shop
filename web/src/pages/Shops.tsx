import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { SlidersHorizontalIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { EmptyState, ErrorState, GoButton, Pager, Price, RowsSkeleton } from '@/components/Bits'
import { SearchInput } from '@/components/SearchInput'
import { useApi } from '@/lib/useApi'
import { qs } from '@/lib/secureApi'
import { specText } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { Home, Shops as ShopsData } from '@/lib/types'

const ALL = 'all'

export default function Shops() {
  const [sp, setSp] = useSearchParams()
  const [sheet, setSheet] = useState(false)
  const q = sp.get('q') ?? '', type = sp.get('type') ?? '', product = sp.get('product') ?? ''
  const sort = sp.get('sort') ?? 'price-asc', page = Number(sp.get('page') ?? 1) || 1
  const set = (k: string, v: string) => {
    const n = new URLSearchParams(sp)
    if (v && v !== ALL && !(k === 'page' && v === '1') && !(k === 'sort' && v === 'price-asc')) n.set(k, v); else n.delete(k)
    if (k !== 'page') n.delete('page')
    setSp(n)
  }
  const home = useApi<Home>('/api/v4/home')
  const list = useApi<ShopsData>(`/api/v4/shops${qs({ q, type, product, sort, page, size: 20 })}`)
  useEffect(() => { document.title = '全部店铺 | AI 订阅比价' }, [])
  const pageHref = (p: number) => { const n = new URLSearchParams(sp); if (p > 1) n.set('page', String(p)); else n.delete('page'); const s = n.toString(); return s ? `?${s}` : '?' }

  const selects = (cls: string, withType = true) => (
    <>
      <Select value={product || ALL} onValueChange={(v) => set('product', v)}>
        <SelectTrigger aria-label="商品" className={cls}><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>全部商品</SelectItem>
          {home.data?.tools.map((t) => <SelectItem key={t.name} value={t.name}>{t.name}</SelectItem>)}
        </SelectContent>
      </Select>
      {withType && <Select value={type || ALL} onValueChange={(v) => set('type', v)}>
        <SelectTrigger aria-label="店铺类型" className={cls}><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>全部类型</SelectItem>
          {home.data?.types.map((t) => <SelectItem key={t.name} value={t.name}>{t.name}</SelectItem>)}
        </SelectContent>
      </Select>}
      <Select value={sort} onValueChange={(v) => set('sort', v)}>
        <SelectTrigger aria-label="排序" className={cls}><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="price-asc">最低价从低到高</SelectItem>
          <SelectItem value="price-desc">最低价从高到低</SelectItem>
          <SelectItem value="recent">最近更新</SelectItem>
          <SelectItem value="name">店名</SelectItem>
        </SelectContent>
      </Select>
    </>
  )

  return (
    <>
      <div className="mt-8 mb-6 md:mt-10">
        <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">全部店铺</h1>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground md:text-base">按店铺查看在卖的商品和最低起价，想比同一规格的价格，请从商品页进入。</p>
      </div>
      <div className="flex items-center gap-2 md:gap-3">
        <div className="min-w-0 flex-1"><SearchInput key={q} initial={q} /></div>
        <div className="hidden gap-3 md:flex">{selects('h-10 w-40 bg-card', false)}</div>
        <Sheet open={sheet} onOpenChange={setSheet}>
          <SheetTrigger asChild>
            <Button variant="outline" size="lg" className="h-10 md:hidden"><SlidersHorizontalIcon />筛选</Button>
          </SheetTrigger>
          <SheetContent side="bottom" className="rounded-t-2xl">
            <SheetHeader>
              <SheetTitle>筛选和排序</SheetTitle>
              <SheetDescription className="sr-only">按商品、店铺类型筛选，并选择排序方式</SheetDescription>
            </SheetHeader>
            <div className="flex flex-col gap-3 px-4 pb-6">{selects('h-11 w-full')}<Button size="lg" className="mt-1 h-11" onClick={() => setSheet(false)}>完成</Button></div>
          </SheetContent>
        </Sheet>
      </div>

      <div role="group" aria-label="按店铺类型筛选" className="mt-4 flex gap-2 overflow-x-auto pb-1">
        {[{ name: '', count: home.data?.types.reduce((a, t) => a + t.count, 0) ?? 0, label: '全部' }, ...(home.data?.types.map((t) => ({ ...t, label: t.name })) ?? [])].map((t) => (
          <button key={t.name} type="button" aria-pressed={type === t.name} onClick={() => set('type', t.name)}
            className={cn('inline-flex h-10 shrink-0 items-center gap-2 rounded-full border px-4 text-sm outline-none transition-colors focus-visible:ring-3 focus-visible:ring-ring/50', type === t.name ? 'border-foreground bg-foreground text-background' : 'bg-card hover:border-foreground/40')}>
            {t.label}<span className="fig text-base opacity-70">{t.count}</span>
          </button>
        ))}
      </div>

      {list.error ? <div className="mt-6"><ErrorState message={list.error} retry={list.reload} /></div> : (
        <>
          <p className="mt-5 mb-3 min-h-5 text-sm text-muted-foreground" aria-live="polite">{list.data ? (q ? `“${q}” 共 ${list.data.total} 家店铺` : `共 ${list.data.total} 家店铺`) : ''}</p>
          {!list.data ? <RowsSkeleton />
            : !list.data.items.length ? <EmptyState title="没有找到匹配的店铺" hint="换个关键词，或者把商品、类型改回“全部”。" />
            : (
              <div className="overflow-hidden rounded-2xl border bg-card" aria-busy={list.loading}>
                <ul className="divide-y">
                  {list.data.items.map((s) => (
                    <li key={s.id} className="row flex flex-col gap-3 p-4 sm:grid sm:grid-cols-[minmax(0,1fr)_14rem_auto] sm:items-center sm:gap-6 sm:p-5">
                      <div className="flex min-w-0 items-start gap-3">
                        <span aria-hidden="true" className="grid size-11 shrink-0 place-items-center rounded-xl bg-muted text-lg font-semibold text-muted-foreground">{[...s.name][0]}</span>
                        <div className="min-w-0">
                          <p className="font-semibold break-words"><Link to={`/shop/${s.id}`} className="underline-offset-4 hover:underline">{s.name}</Link></p>
                          <p className="text-xs text-muted-foreground">{s.type}，{s.domain}</p>
                          <p className="mt-2 flex flex-wrap gap-1">
                            {s.products.slice(0, 4).map((p) => <Badge key={p} variant="outline">{p}</Badge>)}
                            {s.products.length > 4 && <Badge variant="ghost" className="text-muted-foreground">另有 {s.products.length - 4} 种</Badge>}
                            {!s.products.length && <span className="text-sm text-muted-foreground">暂未识别到商品</span>}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center justify-between gap-3 sm:contents">
                        <div className="min-w-0 sm:text-right">
                          {s.price != null ? (
                            <>
                              <Price value={s.price} suffix="起" />
                              <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{[s.price_product, specText(s.price_spec)].filter(Boolean).join('，')}</p>
                            </>
                          ) : <p className="text-sm text-muted-foreground">暂未采到价格</p>}
                        </div>
                        <GoButton href={s.go} label={`去店铺：${s.name}`} className="sm:w-28" />
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          {list.data && <Pager page={page} total={list.data.total} size={list.data.size} href={pageHref} onPage={(p) => { set('page', String(p)); window.scrollTo({ top: 0 }) }} />}
        </>
      )}
    </>
  )
}
