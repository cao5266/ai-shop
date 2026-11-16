import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState, Price } from '@/components/Bits'
import { Tile } from '@/components/Brand'
import { SearchInput } from '@/components/SearchInput'
import { useApi } from '@/lib/useApi'
import { money, specText, when } from '@/lib/format'
import type { Home as HomeData, Tool } from '@/lib/types'

function ToolCard({ t }: { t: Tool }) {
  return (
    <Link to={`/tool/${encodeURIComponent(t.name)}`} className="card group block rounded-2xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50">
      <Card className="h-full gap-5 rounded-2xl py-4 shadow-xs transition-shadow group-hover:shadow-md md:py-5">
        <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:gap-4">
          <Tile name={t.name} size="md" />
          <div className="min-w-0">
            <CardTitle className="text-base leading-snug font-semibold break-words">{t.name}</CardTitle>
            <CardDescription>{t.n_selling ? `${t.n_selling} 家店铺在售` : `${t.n_shops} 家店铺提到`}</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="mt-auto">
          {t.price != null ? (
            <>
              <Price value={t.price} currency={t.currency ?? 'CNY'} />
              <p className="mt-1 text-sm text-muted-foreground">{specText(t.spec)}</p>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">{t.sold_out[0] ? `曾标价 ${money(t.sold_out[0].min, t.sold_out[0].currency)}，已售罄` : t.status ?? '暂未采到价格'}</p>
          )}
        </CardContent>
      </Card>
    </Link>
  )
}

function CardSkeleton() {
  return (
    <Card className="h-44 gap-5 rounded-2xl py-5" aria-hidden="true">
      <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:gap-4"><Skeleton className="size-14 rounded-[22%]" /><div className="space-y-2"><Skeleton className="h-5 w-24" /><Skeleton className="h-4 w-16" /></div></CardHeader>
      <CardContent className="mt-auto space-y-2"><Skeleton className="h-7 w-20" /><Skeleton className="h-4 w-28" /></CardContent>
    </Card>
  )
}

export default function Home() {
  const { data, error, loading, reload } = useApi<HomeData>('/api/v4/home')
  useEffect(() => { document.title = 'AI 订阅比价' }, [])
  return (
    <>
      <section className="py-10 md:py-14">
        <h1 className="text-3xl font-semibold tracking-tight text-balance md:text-5xl">AI 工具订阅比价</h1>
        <p className="mt-4 mb-7 max-w-xl text-base leading-relaxed text-muted-foreground text-pretty md:text-lg">按工具比较各家店铺的在售价格。价格取自店铺商品页，期限、额度和交付方式不同的商品分开比。</p>
        <div className="max-w-xl"><SearchInput large /></div>
        <p className="mt-4 min-h-5 text-sm text-muted-foreground">{data ? `价格更新于 ${when(data.updated_at, true)}，覆盖 ${data.total_shops} 家店铺` : ''}</p>
      </section>
      <section aria-labelledby="tools-h">
        <h2 id="tools-h" className="mb-4 text-xl font-semibold">全部商品</h2>
        {error ? <ErrorState message={error} retry={reload} /> : (
          <div className="grid grid-cols-2 gap-3 max-[340px]:grid-cols-1 md:grid-cols-3 md:gap-4 lg:grid-cols-4">
            {loading && !data ? Array.from({ length: 8 }, (_, i) => <CardSkeleton key={i} />) : data?.tools.map((t) => <ToolCard key={t.name} t={t} />)}
          </div>
        )}
      </section>
    </>
  )
}
