import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from './secureApi'

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
