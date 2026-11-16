import { Link } from 'react-router-dom'
import { AlertCircleIcon, SearchXIcon } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { Pagination, PaginationContent, PaginationEllipsis, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from '@/components/ui/pagination'
import { cn } from '@/lib/utils'
import { money } from '@/lib/format'

export function Price({ value, currency = 'CNY', suffix = '起', className, big = false }: { value: number; currency?: string; suffix?: string; className?: string; big?: boolean }) {
  return (
    <span className={cn('price num inline-flex items-baseline gap-1 font-semibold tracking-tight', big ? 'text-3xl md:text-4xl' : 'text-2xl', className)}>
      {money(value, currency)}
      {suffix && <span className="text-sm font-normal text-muted-foreground">{suffix}</span>}
    </span>
  )
}

export function LowestBadge() {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge className="bg-warning text-warning-foreground">最低</Badge>
      </TooltipTrigger>
      <TooltipContent>这个规格下价格最低的商品</TooltipContent>
    </Tooltip>
  )
}

export function GoButton({ href, children = '去店铺', label, className }: { href: string; children?: string; label?: string; className?: string }) {
  return (
    <Button asChild variant="secondary" size="lg" className={cn('h-10 px-5 text-[15px]', className)}>
      <a href={href} target="_blank" rel="noopener noreferrer nofollow" aria-label={label}>{children}</a>
    </Button>
  )
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <Alert variant="destructive" className="state">
      <AlertCircleIcon />
      <AlertTitle>没能读到数据</AlertTitle>
      <AlertDescription>
        <p>{message}</p>
        {retry && <Button type="button" variant="outline" size="lg" className="mt-3" onClick={retry}>重试</Button>}
      </AlertDescription>
    </Alert>
  )
}

export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: { to: string; label: string } }) {
  return (
    <Empty className="rounded-2xl border bg-card py-12">
      <EmptyHeader>
        <EmptyMedia variant="icon"><SearchXIcon /></EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        {hint && <EmptyDescription>{hint}</EmptyDescription>}
      </EmptyHeader>
      {action && <EmptyContent><Button asChild variant="secondary" size="lg"><Link to={action.to}>{action.label}</Link></Button></EmptyContent>}
    </Empty>
  )
}

export function NotFound() {
  return <EmptyState title="页面不存在" hint="链接可能已经失效。" action={{ to: '/', label: '回到首页' }} />
}

export function RowsSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <ul className="divide-y rounded-2xl border bg-card" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <li key={i} className="flex items-center justify-between gap-6 p-5">
          <div className="flex-1 space-y-2"><Skeleton className="h-5 w-2/5" /><Skeleton className="h-4 w-3/5" /></div>
          <Skeleton className="h-7 w-20" /><Skeleton className="h-10 w-24 rounded-lg" />
        </li>
      ))}
    </ul>
  )
}

/** 分页：真实链接（可新标签打开），普通点击在页内切换 */
export function Pager({ page, total, size, href, onPage }: { page: number; total: number; size: number; href: (p: number) => string; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / size))
  if (pages <= 1) return null
  const nums = [...new Set([1, page - 1, page, page + 1, pages])].filter((n) => n >= 1 && n <= pages).sort((a, b) => a - b)
  const go = (p: number) => (e: React.MouseEvent) => { if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return; e.preventDefault(); onPage(p) }
  return (
    <Pagination className="mt-8">
      <PaginationContent>
        <PaginationItem>{page > 1 ? <PaginationPrevious href={href(page - 1)} onClick={go(page - 1)} /> : <PaginationPrevious aria-disabled="true" className="pointer-events-none opacity-50" tabIndex={-1} />}</PaginationItem>
        {nums.map((n, i) => (
          <PaginationItem key={n} className="contents">
            {i > 0 && n - nums[i - 1] > 1 && <PaginationItem><PaginationEllipsis /></PaginationItem>}
            <PaginationItem><PaginationLink href={href(n)} isActive={n === page} onClick={go(n)} aria-label={`第 ${n} 页`}>{n}</PaginationLink></PaginationItem>
          </PaginationItem>
        ))}
        <PaginationItem>{page < pages ? <PaginationNext href={href(page + 1)} onClick={go(page + 1)} /> : <PaginationNext aria-disabled="true" className="pointer-events-none opacity-50" tabIndex={-1} />}</PaginationItem>
      </PaginationContent>
    </Pagination>
  )
}
