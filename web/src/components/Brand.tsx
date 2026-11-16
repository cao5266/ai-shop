import { Link } from 'react-router-dom'
import { LOGO } from '@/lib/logos'
import { cn } from '@/lib/utils'

/** 站点 logo：亮色用深色字标，暗色用提亮的图形和浅色字标 */
export function Logo({ className }: { className?: string }) {
  return (
    <Link to="/" className={cn('block shrink-0 rounded-md', className)} aria-label="AI 订阅比价，返回首页">
      <img src="/logo.svg" alt="AI 订阅比价" height="32" className="h-8 w-auto dark:hidden" />
      <img src="/logo-dark.svg" alt="" aria-hidden="true" height="32" className="hidden h-8 w-auto dark:block" />
    </Link>
  )
}

const SIZES = { xs: 'size-9 rounded-[22%]', sm: 'size-11 rounded-[22%]', md: 'size-14 rounded-[22%]', lg: 'size-24 rounded-[22%] md:size-28' } as const
const IMG = { xs: 'size-5', sm: 'size-6', md: 'size-8', lg: 'size-14 md:size-16' } as const

/** 商品图标：像应用图标一样固定白底，所以黑色 logo（OpenAI、Grok、Cursor、X）在暗色主题里也看得清 */
export function Tile({ name, size = 'md' }: { name: string; size?: keyof typeof SIZES }) {
  const f = LOGO[name]
  return (
    <span aria-hidden="true" className={cn('grid shrink-0 place-items-center border border-black/10 bg-white', SIZES[size])}>
      {f ? <img src={`/logos/${f}.svg`} alt="" className={IMG[size]} />
        : <span className="text-xl font-semibold text-neutral-600">{[...name][0].toUpperCase()}</span>}
    </span>
  )
}
