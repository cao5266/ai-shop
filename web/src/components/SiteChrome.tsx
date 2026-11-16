import { Link, useLocation } from 'react-router-dom'
import { MenuIcon } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { Logo } from './Brand'
import { SearchInput } from './SearchInput'
import { ThemeToggle } from './ThemeToggle'
import { cn } from '@/lib/utils'

const LINKS = [{ to: '/', label: '商品', end: true }, { to: '/shops', label: '全部店铺' }, { to: '/about', label: '说明' }]
const isOn = (pathname: string, l: { to: string; end?: boolean }) => (l.end ? pathname === l.to : pathname.startsWith(l.to))
const onCls = 'bg-secondary text-secondary-foreground hover:bg-secondary'

export function SiteHeader() {
  const { pathname } = useLocation()
  const [open, setOpen] = useState(false)
  const showSearch = pathname !== '/' && pathname !== '/shops'
  return (
    <header className="sticky top-0 z-30 border-b bg-background">
      <div className="mx-auto flex h-16 w-full max-w-[1200px] items-center gap-3 px-4 sm:px-6">
        <Logo />
        {showSearch && <div className="hidden max-w-md flex-1 md:block"><SearchInput /></div>}
        <nav aria-label="主导航" className="ml-auto hidden items-center gap-1 md:flex">
          {LINKS.map((l) => (
            <Button key={l.to} asChild variant="ghost" size="lg" className="px-3 text-[15px]">
              <Link to={l.to} aria-current={isOn(pathname, l) ? 'page' : undefined} className={cn(isOn(pathname, l) && onCls)}>{l.label}</Link>
            </Button>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-1 md:ml-0">
          <ThemeToggle />
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon-lg" className="size-11 md:hidden" aria-label="打开菜单"><MenuIcon /></Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-72">
              <SheetHeader>
                <SheetTitle>菜单</SheetTitle>
                <SheetDescription className="sr-only">站内导航与搜索</SheetDescription>
              </SheetHeader>
              <div className="flex flex-col gap-1 px-4">
                {LINKS.map((l) => (
                  <Button key={l.to} asChild variant="ghost" size="lg" className="h-11 justify-start text-base">
                    <Link to={l.to} aria-current={isOn(pathname, l) ? 'page' : undefined} className={cn(isOn(pathname, l) && onCls)} onClick={() => setOpen(false)}>{l.label}</Link>
                  </Button>
                ))}
                <div className="mt-3"><SearchInput onDone={() => setOpen(false)} /></div>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  )
}

export function SiteFooter() {
  return (
    <footer className="border-t">
      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-2 px-4 py-6 text-sm text-muted-foreground sm:flex-row sm:justify-between sm:px-6">
        <p>所有店铺均为非官方渠道，本站不担保交易。</p>
        <Link to="/about" className="inline-flex min-h-11 items-center underline-offset-4 hover:text-foreground hover:underline">数据说明</Link>
      </div>
    </footer>
  )
}
