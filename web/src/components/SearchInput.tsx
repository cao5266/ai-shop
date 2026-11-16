import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { SearchIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

export function SearchInput({ initial = '', large = false, className, onDone }: { initial?: string; large?: boolean; className?: string; onDone?: () => void }) {
  const nav = useNavigate()
  const [q, setQ] = useState(initial)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    const v = q.trim()
    nav(v ? `/shops?q=${encodeURIComponent(v)}` : '/shops')
    onDone?.()
  }
  return (
    <form role="search" onSubmit={submit} className={cn('flex w-full items-center gap-2', className)}>
      <div className="relative flex-1">
        <SearchIcon aria-hidden="true" className={cn('pointer-events-none absolute top-1/2 -translate-y-1/2 text-muted-foreground', large ? 'left-4 size-5' : 'left-3 size-4')} />
        <Input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜索商品或店铺" aria-label="搜索商品或店铺"
          autoComplete="off" maxLength={60} className={cn(large ? 'h-12 rounded-xl pl-11 text-base md:text-base' : 'h-10 pl-9')} />
      </div>
      {large && <Button type="submit" className="h-12 rounded-xl px-6 text-base">搜索</Button>}
    </form>
  )
}
