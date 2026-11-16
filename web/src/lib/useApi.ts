import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from './secureApi'
import type { ToolSpecs } from './types'

export interface State<T> { data: T | null; error: string | null; loading: boolean; reload: () => void }

export function useApi<T>(path: string | null): State<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(!!path)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    if (!path) return
    const ac = new AbortController()
    setLoading(true); setError(null)
    api<T>(path, ac.signal)
      .then((d) => { setData(d); setLoading(false) })
      .catch((e) => {
        if (ac.signal.aborted) return
        setLoading(false)
        setError(e instanceof ApiError && e.status === 429 ? '请求太频繁，请稍等一会儿再试。'
          : e instanceof ApiError && e.status === 404 ? '没有找到这个页面的数据。'
          : e instanceof ApiError && e.status === 403 ? '当前浏览器被拦截了，请换用常见的浏览器访问。'
          : '数据读取失败，请检查网络后重试。')
      })
    return () => ac.abort()
  }, [path, tick])
  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, error, loading, reload }
}

const catalogPath = (name: string) => `/api/v4/catalog/${encodeURIComponent(name)}/specs`

/** 批量取多个商品的规格目录；某个商品失败只是缺席，不影响其他。 */
export function useCatalogs(names: string[]) {
  const [map, setMap] = useState<Record<string, ToolSpecs>>({})
  const [done, setDone] = useState(false)
  const key = names.join('\n')
  useEffect(() => {
    if (!names.length) return
    let alive = true
    setDone(false)
    Promise.all(names.map((n) => api<ToolSpecs>(catalogPath(n)).then((d) => [n, d] as const).catch(() => null)))
      .then((rs) => { if (alive) { setMap(Object.fromEntries(rs.filter(Boolean) as [string, ToolSpecs][])); setDone(true) } })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  return { catalogs: map, done }
}

export const useCatalog = (name: string, enabled = true) => useApi<ToolSpecs>(enabled ? catalogPath(name) : null)
