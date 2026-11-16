import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from './secureApi'
import type { Spec, ToolSpecs } from './types'

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

const PAGE_SIZE = 100
const MAX_PAGES = 20   // 防御：最多翻 20 页（2000 组），避免后端异常时无限翻页

/**
 * 补全规格：/tools/:name 已带全量 specs 时不请求；少于 n_specs 时才按 total_pages 翻页取全
 * （page_size=100，每页一次请求），用于接口改为只返回部分规格的情况。
 */
export function useAllSpecs(name: string, have: Spec[] | undefined, total: number | undefined) {
  const [full, setFull] = useState<{ name: string; specs: Spec[] } | null>(null)
  const [error, setError] = useState(false)
  const need = !!have && total != null && have.length < total
  useEffect(() => {
    if (!need) return
    let alive = true
    setError(false)
    ;(async () => {
      const out: Spec[] = []
      let pages = 1
      for (let p = 1; p <= Math.min(pages, MAX_PAGES); p++) {
        const r = await api<ToolSpecs>(`/api/v4/catalog/${encodeURIComponent(name)}/specs?page=${p}&page_size=${PAGE_SIZE}`)
        out.push(...r.specs); pages = r.total_pages
      }
      if (alive) setFull({ name, specs: out })
    })().catch(() => alive && setError(true))
    return () => { alive = false }
  }, [name, need])
  return { specs: need ? (full?.name === name ? full.specs : have!) : have, partial: need && full?.name !== name, error }
}
