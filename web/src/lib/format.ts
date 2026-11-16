const nf = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 })
export const money = (n: number, cur = 'CNY') => (cur === 'CNY' ? '¥' : cur + ' ') + nf.format(n)
// 规格标签 "1月 / plus / 代充" → "1月，plus，代充"
export const specText = (s?: string | null) => (s ?? '').split(' / ').join('，')
const dtf = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
const dtfY = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
export const when = (iso?: string | null, year = false) => (iso ? (year ? dtfY : dtf).format(new Date(iso)) : '未知')
