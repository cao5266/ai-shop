import { useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from '@/components/ui/breadcrumb'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { EmptyState, ErrorState, GoButton, Price } from '@/components/Bits'
import { useApi } from '@/lib/useApi'
import { money, specText, when } from '@/lib/format'
import type { Listing, ShopDetail } from '@/lib/types'

function ListingRows({ items }: { items: Listing[] }) {
  if (!items.length) return <EmptyState title="这里还没有商品" />
  return (
    <Card className="gap-0 rounded-2xl py-0">
      <ul className="divide-y">
        {items.map((l) => (
          <li key={l.id} className="row flex flex-col gap-3 p-4 sm:grid sm:grid-cols-[minmax(0,1fr)_11rem_auto] sm:items-center sm:gap-6 sm:p-5">
            <div className="min-w-0">
              <p className="font-medium break-words">{l.title}</p>
              <p className="mt-1 flex flex-wrap gap-1">
                {l.product && <Badge variant="outline">{l.product}</Badge>}
                {l.spec && <Badge variant="secondary">{specText(l.spec)}</Badge>}
              </p>
              <p className="mt-1 flex flex-wrap gap-x-4 text-xs text-muted-foreground">
                <span>更新于 {when(l.observed_at)}</span>{l.stock && <span>库存 {l.stock}</span>}
                {l.history.length > 1 && <span>价格变动 {l.history.map((h) => money(h.price)).join(' 到 ')}</span>}
              </p>
            </div>
            <div className="flex items-center justify-between gap-3 sm:contents">
              <Price value={l.price} currency={l.currency} suffix="" className="text-xl" />
              <div>{l.active && <GoButton href={l.go} label={`查看商品：${l.title}`}>查看商品</GoButton>}</div>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}

export default function ShopPage() {
  const id = useParams().id ?? ''
  const { data, error, reload } = useApi<ShopDetail>(`/api/v4/shops/${encodeURIComponent(id)}`)
  useEffect(() => { document.title = data ? `${data.name} | AI 订阅比价` : 'AI 订阅比价' }, [data])
  const crumbs = (name?: string) => (
    <Breadcrumb className="my-4">
      <BreadcrumbList>
        <BreadcrumbItem><BreadcrumbLink asChild><Link to="/shops">全部店铺</Link></BreadcrumbLink></BreadcrumbItem>
        <BreadcrumbSeparator />
        <BreadcrumbItem><BreadcrumbPage className="max-w-[60vw] truncate">{name ?? '店铺'}</BreadcrumbPage></BreadcrumbItem>
      </BreadcrumbList>
    </Breadcrumb>
  )
  if (error) return <>{crumbs()}<ErrorState message={error} retry={reload} /></>
  const on = data?.listings.filter((l) => l.active) ?? [], off = data?.listings.filter((l) => !l.active) ?? []
  return (
    <>
      {crumbs(data?.name)}
      <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          {data ? <h1 className="text-2xl font-semibold tracking-tight break-words md:text-3xl">{data.name}</h1> : <Skeleton className="h-9 w-64" />}
          <p className="mt-1 min-h-5 text-sm text-muted-foreground">{data ? `${data.domain}，${data.type}，更新于 ${when(data.updated_at, true)}` : ''}</p>
        </div>
        {data && <GoButton href={data.go} className="h-11 shrink-0 px-6" />}
      </header>
      {data && !data.listings.length && <EmptyState title="暂未采到这家店铺的商品价格" hint={data.crawl_status ?? undefined} />}
      {data && data.listings.length > 0 && (
        <Tabs defaultValue="on">
          <TabsList>
            <TabsTrigger value="on">在售商品（{on.length}）</TabsTrigger>
            <TabsTrigger value="off">已售罄或下架（{off.length}）</TabsTrigger>
          </TabsList>
          <TabsContent value="on" className="mt-4"><ListingRows items={on} /></TabsContent>
          <TabsContent value="off" className="mt-4"><ListingRows items={off} /></TabsContent>
        </Tabs>
      )}
    </>
  )
}
