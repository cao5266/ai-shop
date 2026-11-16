import { useEffect } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { InfoIcon } from 'lucide-react'
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { EmptyState, ErrorState, GoButton, LowestBadge, Pager, Price, RowsSkeleton } from '@/components/Bits'
import { Tile } from '@/components/Brand'
import { useApi } from '@/lib/useApi'
import { qs } from '@/lib/secureApi'
import { money, specText, when } from '@/lib/format'
import type { Offers, ToolDetail } from '@/lib/types'

export default function ToolPage() {
  const name = decodeURIComponent(useParams().name ?? '')
  const [sp, setSp] = useSearchParams()
  const sort = sp.get('sort') ?? 'price-asc'
  const page = Number(sp.get('page') ?? 1) || 1
  const detail = useApi<ToolDetail>(`/api/v4/tools/${encodeURIComponent(name)}`)
  const d = detail.data
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

  return (
    <>
      {crumbs}
      <header className="app-head mb-10 flex items-center gap-5 md:gap-7">
        <Tile name={name} size="lg" />
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight md:text-4xl">{name}</h1>
          <p className="mt-1 text-sm text-muted-foreground md:text-base">
            {d ? (d.n_selling ? `${d.n_selling} 家店铺在售，价格更新于 ${when(d.updated_at, true)}` : `${d.n_shops} 家店铺提到，暂无在售报价`) : ' '}
          </p>
          {d?.price != null && <div className="mt-2"><Price value={d.price} currency={d.currency ?? 'CNY'} big /></div>}
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="link" className="mt-1 h-auto p-0 text-muted-foreground"><InfoIcon />价格怎么比</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>价格怎么比</DialogTitle>
                <DialogDescription>价格取自店铺公开的商品页，每天更新。期限、额度、套餐、区域和交付方式不同的商品分开比，不会把月卡和年卡放在一起排价格。规格信息不完整的商品只和标题完全相同的商品比。已售罄的商品不计入。下单前请到店铺页面核对价格和售后说明。</DialogDescription>
              </DialogHeader>
            </DialogContent>
          </Dialog>
        </div>
      </header>

      {d && !d.specs.length && (
        <EmptyState title={d.sold_out[0] ? `曾标价 ${money(d.sold_out[0].min, d.sold_out[0].currency)}，已售罄` : d.status ?? '暂未采到价格'} hint={d.note ?? undefined} action={{ to: '/shops', label: '查看全部店铺' }} />
      )}

      {d && d.specs.length > 0 && (
        <>
          <h2 className="mb-3 text-xl font-semibold">选择规格</h2>
          <div className="-mx-4 mb-8 overflow-x-auto px-4 py-1 pb-3 sm:-mx-6 sm:px-6">
            <RadioGroup value={active} onValueChange={(v) => update('spec', v)} aria-label="规格" className="flex w-max gap-3">
              {d.specs.map((s) => (
                <label key={s.key}
                  className="spec flex w-48 shrink-0 cursor-pointer flex-col gap-1 rounded-2xl border bg-card p-3.5 text-left transition-colors hover:border-input has-focus-visible:ring-3 has-focus-visible:ring-ring/50 has-data-checked:border-primary has-data-checked:bg-secondary has-data-checked:ring-1 has-data-checked:ring-primary md:w-52">
                  <RadioGroupItem value={s.key} className="sr-only" />
                  <span className="min-h-10 text-sm leading-snug">{(d.members.length > 1 ? s.product + '，' : '') + (specText(s.label) || '规格未注明')}</span>
                  <Price value={s.min} currency={s.currency} className="text-lg" />
                  <span className="text-xs text-muted-foreground">{s.n_shops} 家店铺</span>
                </label>
              ))}
            </RadioGroup>
          </div>

          <div className="mb-4 flex items-center justify-between gap-4">
            <h2 className="text-xl font-semibold">在售店铺</h2>
            <Select value={sort} onValueChange={(v) => update('sort', v === 'price-asc' ? '' : v)}>
              <SelectTrigger aria-label="排序" className="h-10 w-44"><SelectValue /></SelectTrigger>
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
              <Card className="gap-0 rounded-2xl py-0" aria-busy={offers.loading}>
                <ul className="divide-y">
                  {offers.data.items.map((o) => (
                    <li key={o.id} className="row flex flex-col gap-3 p-4 sm:grid sm:grid-cols-[minmax(0,1fr)_11rem_auto] sm:items-center sm:gap-6 sm:p-5">
                      <div className="min-w-0">
                        <p className="font-semibold break-words">{o.shop.name}</p>
                        <p className="mt-0.5 text-sm text-muted-foreground">{o.title}</p>
                        <p className="mt-1 flex flex-wrap gap-x-4 text-xs text-muted-foreground"><span>{o.shop.type}</span><span>更新于 {when(o.observed_at)}</span>{o.stock && <span>库存 {o.stock}</span>}</p>
                      </div>
                      <div className="flex items-center justify-between gap-3 sm:contents">
                        <p className="flex items-center gap-2"><Price value={o.price} currency={o.currency} suffix="" className="text-xl" />{o.lowest && <LowestBadge />}</p>
                        <GoButton href={o.go} label={`去店铺：${o.shop.name}`} />
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          {offers.data && <Pager page={page} total={offers.data.total} size={offers.data.size} href={pageHref} onPage={(p) => { update('page', p > 1 ? String(p) : '', false); window.scrollTo({ top: 0 }) }} />}
        </>
      )}
    </>
  )
}
