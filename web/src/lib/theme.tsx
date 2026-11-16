import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

export type Theme = 'light' | 'dark' | 'system'
const KEY = 'theme'   // 与 index.html 里的内联初始化脚本使用同一个 localStorage 键
const Ctx = createContext<{ theme: Theme; setTheme: (t: Theme) => void }>({ theme: 'system', setTheme: () => {} })

const read = (): Theme => {
  try { const v = localStorage.getItem(KEY); return v === 'light' || v === 'dark' ? v : 'system' } catch { return 'system' }
}
const apply = (t: Theme) => {
  const dark = t === 'dark' || (t === 'system' && matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark', dark)
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, set] = useState<Theme>(read)
  const setTheme = useCallback((t: Theme) => {
    try { t === 'system' ? localStorage.removeItem(KEY) : localStorage.setItem(KEY, t) } catch { /* 隐私模式下写不进去也没关系 */ }
    set(t); apply(t)
  }, [])
  // 选「跟随系统」时，系统外观变化要实时跟着变
  useEffect(() => {
    if (theme !== 'system') return
    const mq = matchMedia('(prefers-color-scheme: dark)')
    const on = () => apply('system')
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [theme])
  return <Ctx.Provider value={{ theme, setTheme }}>{children}</Ctx.Provider>
}
export const useTheme = () => useContext(Ctx)
