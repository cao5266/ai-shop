// 加密接口客户端：取会话密钥 → 请求签名（HMAC-SHA256）→ 解密响应（AES-GCM）。
// 用纯 JS 实现（noble），因为 WebCrypto 在 http 页面里不可用，而站点可能先用 IP + HTTP 访问。
// 这只会提高自动化抓取的门槛：密钥必须下发到浏览器，真想抓的人照样能抓。
import { gcm } from '@noble/ciphers/aes.js'
import { hmac } from '@noble/hashes/hmac.js'
import { sha256 } from '@noble/hashes/sha2.js'
import { bytesToHex, randomBytes } from '@noble/hashes/utils.js'

interface Session { sid: string; key: Uint8Array; exp: number; skew: number }
export class ApiError extends Error {
  constructor(public status: number, public code: string) { super(code) }
}

const enc = new TextEncoder()
const dec = new TextDecoder()
const fromB64 = (s: string) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0))

let session: Session | null = null
let pending: Promise<Session> | null = null

async function newSession(): Promise<Session> {
  const r = await fetch('/api/v4/session', { headers: { 'X-Requested-With': 'aishops-web' }, cache: 'no-store' })
  if (!r.ok) throw new ApiError(r.status, (await r.json().catch(() => ({}))).error ?? 'session')
  const j = await r.json()
  return { sid: j.sid, key: fromB64(j.key), exp: j.exp, skew: j.ts - Math.floor(Date.now() / 1000) }
}

function getSession(force = false): Promise<Session> {
  const now = Math.floor(Date.now() / 1000)
  if (!force && session && session.exp - 60 > now + session.skew) return Promise.resolve(session)
  pending ??= newSession().then((s) => (session = s)).finally(() => { pending = null })
  return pending
}

async function once<T>(path: string, s: Session, signal?: AbortSignal): Promise<T> {
  const ts = String(Math.floor(Date.now() / 1000) + s.skew)
  const nonce = bytesToHex(randomBytes(12))
  const sig = bytesToHex(hmac(sha256, s.key, enc.encode(`GET\n${path}\n${ts}\n${nonce}`)))
  const r = await fetch(path, {
    signal, cache: 'no-store',
    headers: { 'X-Sid': s.sid, 'X-Ts': ts, 'X-Nonce': nonce, 'X-Sig': sig, 'X-Requested-With': 'aishops-web' },
  })
  if (!r.ok) throw new ApiError(r.status, (await r.json().catch(() => ({}))).error ?? 'error')
  const env = await r.json()
  const plain = gcm(s.key, fromB64(env.iv), enc.encode(nonce)).decrypt(fromB64(env.ct))
  return JSON.parse(dec.decode(plain)) as T
}

const cache = new Map<string, { at: number; data: unknown }>()

// 遇到 401（会话过期、时间偏差、网络切换后服务端不认等）就换一次会话，把原请求重发一次。
// 只重试一次：第二次仍失败就把错误抛给页面，避免死循环。
export async function api<T>(path: string, signal?: AbortSignal): Promise<T> {
  const hit = cache.get(path)
  if (hit && Date.now() - hit.at < 30_000) return hit.data as T
  const used = await getSession()
  let data: T
  try {
    data = await once<T>(path, used, signal)
  } catch (e) {
    if (!(e instanceof ApiError && e.status === 401) || signal?.aborted) throw e
    // 并发请求同时失败时，别人可能已经换好了新会话，直接复用，不重复换
    const fresh = session && session !== used ? session : await getSession(true)
    data = await once<T>(path, fresh, signal)
  }
  cache.set(path, { at: Date.now(), data })
  return data
}

export const qs = (o: Record<string, string | number | undefined>) => {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(o)) if (v !== undefined && v !== '') p.set(k, String(v))
  const s = p.toString()
  return s ? '?' + s : ''
}
