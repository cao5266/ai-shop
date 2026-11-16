import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { SlidersHorizontalIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { EmptyState, ErrorState, GoButton, Pager, Price, RowsSkeleton } from '@/components/Bits'
import { SearchInput } from '@/components/SearchInput'
import { useApi } from '@/lib/useApi'
import { qs } from '@/lib/secureApi'
import { specText } from '@/lib/format'
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

  const selects = (cls: string) => (
    <>
      <Select value={product || ALL} onValueChange={(v) => set('product', v)}>
        <SelectTrigger aria-label="商品" className={cls}><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>全部商品</SelectItem>
          {home.data?.tools.map((t) => <SelectItem key={t.name} value={t.name}>{t.name}</SelectItem>)}
        </SelectContent>
      </Select>
      <Select value={type || ALL} onValueChange={(v) => set('type', v)}>
        <SelectTrigger aria-label="店铺类型" className={cls}><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>全部类型</SelectItem>
          {home.data?.types.map((t) => <SelectItem key={t.name} value={t.name}>{t.name}</SelectItem>)}
        </SelectContent>
      </Select>
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
      <h1 className="mt-6 mb-5 text-2xl font-semibold tracking-tight md:mt-8 md:mb-6 md:text-4xl">全部店铺</h1>
      <div className="flex items-center gap-2 md:gap-3">
        <div className="min-w-0 flex-1"><SearchInput key={q} initial={q} /></div>
        <div className="hidden gap-3 md:flex">{selects('h-10 w-40')}</div>
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

      {list.error ? <div className="mt-6"><ErrorState message={list.error} retry={list.reload} /></div> : (
        <>
          <p className="mt-6 mb-3 min-h-5 text-sm text-muted-foreground" aria-live="polite">{list.data ? (q ? `“${q}” 共 ${list.data.total} 家店铺` : `共 ${list.data.total} 家店铺`) : ''}</p>
          {!list.data ? <RowsSkeleton />
            : !list.data.items.length ? <EmptyState title="没有找到匹配的店铺" hint="换个关键词，或者把商品、类型改回“全部”。" />
            : (
              <Card className="gap-0 rounded-2xl py-0" aria-busy={list.loading}>
                <ul className="divide-y">
                  {list.data.items.map((s) => (
                    <li key={s.id} className="row flex flex-col gap-3 p-4 sm:grid sm:grid-cols-[minmax(0,1fr)_11rem_auto] sm:items-center sm:gap-6 sm:p-5">
                      <div className="min-w-0">
                        <p className="font-semibold break-words"><Link to={`/shop/${s.id}`} className="underline-offset-4 hover:underline">{s.name}</Link></p>
                        <p className="mt-1 flex flex-wrap gap-1">
                          {s.products.slice(0, 4).map((p) => <Badge key={p} variant="outline">{p}</Badge>)}
                          {s.products.length > 4 && <Badge variant="ghost" className="text-muted-foreground">+{s.products.length - 4}</Badge>}
                          {!s.products.length && <span className="text-sm text-muted-foreground">暂未识别到商品</span>}
                        </p>
                        <p className="mt-1 flex flex-wrap gap-x-4 text-xs text-muted-foreground"><span>{s.domain}</span><span>{s.type}</span></p>
                      </div>
                      <div className="flex items-center justify-between gap-3 sm:contents">
                        <div className="min-w-0">
                          {s.price != null ? (
                            <>
                              <Price value={s.price} className="text-xl" />
                              <p className="text-xs text-muted-foreground">{[s.price_product, specText(s.price_spec)].filter(Boolean).join('，')}</p>
                            </>
                          ) : <p className="text-sm text-muted-foreground">暂未采到价格</p>}
                        </div>
                        <GoButton href={s.go} label={`去店铺：${s.name}`} />
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          {list.data && <Pager page={page} total={list.data.total} size={list.data.size} href={pageHref} onPage={(p) => { set('page', String(p)); window.scrollTo({ top: 0 }) }} />}
        </>
      )}
    </>
  )
}
