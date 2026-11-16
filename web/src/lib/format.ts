const nf = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 })
export const money = (n: number, cur = 'CNY') => (cur === 'CNY' ? '¥' : cur + ' ') + nf.format(n)
// 规格标签 "1月 / plus / 代充" → "1月，plus，代充"
export const specText = (s?: string | null) => (s ?? '').split(' / ').join('，')
const dtf = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
const dtfY = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
export const when = (iso?: string | null, year = false) => (iso ? (year ? dtfY : dtf).format(new Date(iso)) : '未知')
// 店名缺失时接口会把网址当店名：识别出来，标题改显「域名 店铺 编号」，网址放副标题
export const isUrlName = (n?: string | null) => !!n && /^(https?:\/\/)?[\w-]+(\.[\w-]+)+(\/|$)/.test(n.trim())
export function shopTitle(name?: string | null, domain?: string | null) {
  const n = (name ?? '').trim()
  if (!isUrlName(n)) return { title: n || domain || '未命名店铺', url: null as string | null }
  const m = n.replace(/^https?:\/\//, '').split('/').filter(Boolean)
  return { title: `${m[0]} 店铺${m.length > 1 ? ' ' + m[m.length - 1] : ''}`, url: n }
}
// 库存：负数或缺失都当未知
export function stockText(s?: string | null) {
  if (s == null || s === '') return null
  const n = Number(s)
  if (Number.isFinite(n) && n < 0) return '库存未知'
  return `库存 ${s}`
}
