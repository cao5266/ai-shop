// =====================================================================
// 示例数据（设计稿专用）——不是真实价格，也不来自线上接口。
// 仅在 VITE_MOCK=1 时由 secureApi.ts 接管 /api/v4/* 请求；正式构建不会走到这里。
//
// 默认前端走真实接口；这里只在离线演示（npm run dev -- --mode mock）时按真实接口的形状造数据：
//   /api/v4/home, /api/v4/tools/:name, /api/v4/catalog/:name/specs, /api/v4/tools/:name/offers
// =====================================================================
import type { Home, OfferItem, Offers, ShopItem, Shops, SpecInfo, ToolSpecs } from '@/lib/types'

interface MockSpec {
  key: string; kind: string; duration: string | null; tier: string | null; delivery: string | null
  min: number; max: number; currency: string; n_shops: number; n_offers: number; lowest_shop: string | null
}
type MockTool = { name: string; vendor: string; category: string; tagline: string; specs: MockSpec[]; members: string[] }
const DUR: Record<string, string> = { '1 个月': '1月', '12 个月': '1年', '3 个月': '3月' }
const toInfo = (name: string, s: MockSpec): SpecInfo => {
  const delivery = s.delivery ?? '未注明交付'
  return {
    key: s.key, label: [DUR[s.duration ?? ''] ?? s.duration, s.tier?.toLowerCase(), delivery].filter(Boolean).join(' / '),
    currency: s.currency, product: name, title: null, min: s.min, max: s.max, n_prices: s.n_offers, n_shops: s.n_shops,
    duration: s.duration ? DUR[s.duration] ?? s.duration : null, tier: s.tier ? [s.tier.toLowerCase()] : [],
    delivery_type: delivery, quota: [], region: [], incomplete: false,
  }
}

let seq = 0
const sp = (tool: string, kind: string, duration: string | null, tier: string | null, delivery: string | null,
  min: number, max: number, n_shops: number, lowest_shop: string): MockSpec => ({
  key: `${tool}|${++seq}`, kind, duration, tier, delivery, min, max, currency: 'CNY',
  n_shops, n_offers: n_shops + Math.round(n_shops * 0.4), lowest_shop,
})

const T = (name: string, vendor: string, category: string, tagline: string, specs: MockSpec[]): MockTool => ({
  name, vendor, category, tagline, members: [name], specs: specs.sort((a, b) => a.min - b.min),
})

export const MOCK_TOOLS: MockTool[] = [
  T('ChatGPT Plus', 'OpenAI', '对话', 'GPT 系列对话、读图、语音与 Codex 基础额度', [
    sp('ChatGPT Plus', '月卡', '1 个月', 'Plus', '代充', 106, 168, 64, '星河数卡'),
    sp('ChatGPT Plus', '月卡', '1 个月', 'Plus', '成品号', 128, 210, 38, '极光发卡铺'),
    sp('ChatGPT Plus', '年卡', '12 个月', 'Plus', '代充', 1099, 1480, 17, '星河数卡'),
    sp('ChatGPT Plus', '季卡', '3 个月', 'Plus', '代充', 312, 420, 9, '云杉会员站'),
  ]),
  T('ChatGPT Pro', 'OpenAI', '对话', '最高额度，适合长时间推理与大量调用', [
    sp('ChatGPT Pro', '月卡', '1 个月', 'Pro 100', '代充', 630, 790, 31, '极光发卡铺'),
    sp('ChatGPT Pro', '月卡', '1 个月', 'Pro 200', '代充', 1480, 1720, 22, '星河数卡'),
    sp('ChatGPT Pro', '月卡', '1 个月', 'Pro 200', '成品号', 1620, 1980, 9, '云杉会员站'),
  ]),
  T('Claude Pro', 'Anthropic', '对话', 'Claude 对话、长文档与 Projects', [
    sp('Claude Pro', '月卡', '1 个月', 'Pro', '代充', 139, 215, 34, '星河数卡'),
    sp('Claude Pro', '月卡', '1 个月', 'Pro', '成品号', 230, 300, 34, '拾光会员'),
    sp('Claude Pro', '月卡', '1 个月', 'Pro', '独享成品号', 349, 349, 1, '拾光会员'),
    sp('Claude Pro', '月卡', '1 个月', 'Pro', '美区代充', 163, 163, 1, '云杉会员站'),
    sp('Claude Pro', '年卡', '12 个月', 'Pro', '代充', 1380, 1760, 6, '星河数卡'),
  ]),
  T('Claude Max', 'Anthropic', '对话', '5 倍与 20 倍额度，含 Claude Code', [
    sp('Claude Max', '月卡', '1 个月', 'Max 5x', '代充', 826.9, 1050, 29, '极光发卡铺'),
    sp('Claude Max', '月卡', '1 个月', 'Max 20x', '代充', 1560, 1980, 21, '星河数卡'),
    sp('Claude Max', '月卡', '1 个月', 'Max 5x', '成品号', 905, 1180, 11, '拾光会员'),
  ]),
  T('Cursor', 'Anysphere', '编程', 'AI 编辑器，按档位区分每月请求额度', [
    sp('Cursor', '月卡', '1 个月', 'Pro', '代充', 118, 166, 14, '云杉会员站'),
    sp('Cursor', '年卡', '12 个月', 'Pro', '代充', 1088, 1320, 6, '星河数卡'),
    sp('Cursor', '成品号', '1 个月', 'Ultra', '成品号', 1165.5, 1480, 2, '极光发卡铺'),
    sp('Cursor', '组合套餐', '1 个月', 'Pro + Claude Pro', '代充', 239, 286, 4, '拾光会员'),
  ]),
  T('Grok', 'xAI', '对话', 'SuperGrok 与 X Premium+ 档位', [
    sp('Grok', '月卡', '1 个月', 'Plus', '美区代充', 57.2, 96, 41, '极光发卡铺'),
    sp('Grok', '月卡', '1 个月', 'Heavy', '美区代充', 1480, 1760, 7, '星河数卡'),
    sp('Grok', '年卡', '12 个月', 'Plus', '美区代充', 520, 690, 12, '云杉会员站'),
  ]),
  T('Gemini', 'Google', '对话', 'Google AI Pro 与 Ultra，含 2TB 云盘', [
    sp('Gemini', '月卡', '1 个月', 'Pro', '成品号', 38.5, 88, 52, '拾光会员'),
    sp('Gemini', '年卡', '12 个月', 'Pro', '美区代充', 268, 420, 19, '星河数卡'),
    sp('Gemini', '月卡', '1 个月', 'Ultra', '代充', 1380, 1780, 8, '极光发卡铺'),
  ]),
  T('Perplexity', 'Perplexity', '搜索', '带引用的 AI 搜索，Pro 档位', [
    sp('Perplexity', '年卡', '12 个月', 'Pro', '兑换码', 48, 120, 1, '云杉会员站'),
  ]),
  T('Midjourney', 'Midjourney', '绘图', '图像生成，按快速出图时长分档', [
    sp('Midjourney', '月卡', '1 个月', 'Basic', '代充', 62, 98, 18, '拾光会员'),
    sp('Midjourney', '月卡', '1 个月', 'Standard', '代充', 188, 260, 16, '星河数卡'),
    sp('Midjourney', '月卡', '1 个月', 'Pro', '代充', 380, 520, 9, '极光发卡铺'),
  ]),
  T('Copilot', 'Microsoft', '编程', 'GitHub Copilot 个人版', [
    sp('Copilot', '月卡', '1 个月', 'Pro', '代充', 52, 80, 2, '云杉会员站'),
  ]),
  T('Muse', 'Muse', '绘图', '按 token 额度售卖的图像服务', [
    sp('Muse', '额度包', null, '10 亿 token', '成品号', 1.9, 6.8, 89, '星河数卡'),
    sp('Muse', '额度包', null, '100 亿 token', '成品号', 16, 42, 31, '拾光会员'),
  ]),
  T('X会员', 'X', '社交', 'X Premium 与 Premium+', [
    sp('X会员', '月卡', '1 个月', 'Premium', '代充', 49, 88, 12, '极光发卡铺'),
  ]),
  T('Telegram会员', 'Telegram', '社交', 'Telegram Premium', [
    sp('Telegram会员', '月卡', '1 个月', 'Premium', '代充', 24, 39, 2, '星河数卡'),
  ]),
]


// ---------- 店铺与商品报价（按规格伪随机生成，保证每次渲染一致）----------
const SHOPS = [
  ['星河数卡', 'xinghe-shuka.example', '独立站'], ['极光发卡铺', 'jiguang-ka.example', '发卡平台'],
  ['拾光会员', 'shiguang-vip.example', '独立站'], ['云杉会员站', 'yunshan-vip.example', '独立站'],
  ['橙子数码屋', 'chengzi-digital.example', '发卡平台'], ['北辰账号库', 'beichen-acc.example', '独立站'],
  ['小满充值', 'xiaoman-cz.example', '社群店'], ['蓝鲸卖号', 'lanjing-mh.example', '发卡平台'],
  ['山海 AI 铺', 'shanhai-ai.example', '独立站'], ['白鹭数字', 'bailu-digital.example', '发卡平台'],
  ['木槿会员', 'mujin-vip.example', '社群店'], ['海盐充值站', 'haiyan-cz.example', '独立站'],
  ['谷雨数卡', 'guyu-ka.example', '发卡平台'], ['雾灯账号', 'wudeng-acc.example', '独立站'],
  ['长河发卡', 'changhe-fk.example', '发卡平台'], ['知了会员', 'zhiliao-vip.example', '社群店'],
] as const

const rnd = (seed: number) => { let x = seed * 9301 + 49297; x = (x * 233280 + 1) % 2147483647; return (x % 10000) / 10000 }
const fmtDate = (min: number) => new Date(Date.UTC(2026, 10, 16, 7, 55) - min * 60_000).toISOString()
const fmt = (n: number) => Math.round(n * 10) / 10

function offersFor(spec: MockSpec, tool: string): OfferItem[] {
  const n = Math.min(spec.n_offers, 24)
  const out: OfferItem[] = []
  for (let i = 0; i < n; i++) {
    const shop = i === 0 ? SHOPS.find((s) => s[0] === spec.lowest_shop) ?? SHOPS[0] : SHOPS[(i * 5 + spec.key.length) % SHOPS.length]
    const t = n === 1 ? 0 : Math.pow(i / (n - 1), 1.3)
    const price = fmt(spec.min + (spec.max - spec.min) * t + (i && rnd(i + spec.min) > 0.5 ? 0.6 : 0))
    const id = SHOPS.indexOf(shop as never) + 1
    out.push({
      id: Math.round(spec.min * 100) + i, lowest: i === 0,
      shop: { id, name: shop[0], domain: shop[1], type: shop[2] },
      title: `${tool}【官方直充｜${spec.kind}｜${spec.tier ?? ''}${spec.delivery ? '｜' + spec.delivery : ''}】请必详细查看商品介绍`,
      price, currency: 'CNY', stock: rnd(i + 3) > 0.25 ? '充足' : `${Math.round(rnd(i) * 40) + 3} 件`,
      observed_at: fmtDate(Math.round(rnd(i + spec.max) * 600) + 8), go: '#',
    })
  }
  return out
}

export const MOCK_HOME: Home = {
  updated_at: fmtDate(0), total_shops: 224,
  tools: MOCK_TOOLS.map((t) => {
    const lo = t.specs[0]
    return {
      name: t.name, members: t.members, n_shops: t.specs.reduce((a, s) => a + s.n_shops, 0),
      n_selling: Math.max(...t.specs.map((s) => s.n_shops)) + Math.round(t.specs.length * 3),
      n_offers: t.specs.reduce((a, s) => a + s.n_offers, 0), price: lo.min, currency: 'CNY',
      spec: toInfo(t.name, lo).label, n_specs: t.specs.length, status: null, sold_out: [],
    }
  }),
  types: [{ name: '独立站', count: 118 }, { name: '发卡平台', count: 71 }, { name: '社群店', count: 35 }],
}

const allShops: ShopItem[] = SHOPS.map((s, i) => {
  const mine = MOCK_TOOLS.filter((t, k) => ((k + i) % 3 !== 0 || i < 4) && (!['Muse', 'Telegram会员', 'X会员'].includes(t.name) || i % 5 === 0))
  const best = mine.map((t) => t.specs[0]).sort((a, b) => a.min - b.min)[0]
  const tool = mine.find((t) => t.specs[0] === best)!
  return {
    id: i + 1, name: s[0], domain: s[1], type: s[2], products: mine.map((t) => t.name),
    price: fmt(best.min + i * 1.7), price_title: null, price_spec: toInfo(tool.name, best).label,
    price_product: tool.name, updated_at: fmtDate(10 + i * 37), go: '#',
  }
})

export function mockApi(path: string): unknown {
  const u = new URL(path, 'http://x')
  const p = u.pathname, q = u.searchParams
  if (p === '/api/v4/home') return MOCK_HOME
  let m = p.match(/^\/api\/v4\/tools\/([^/]+)\/offers$/)
  if (m) {
    const t = MOCK_TOOLS.find((x) => x.name === decodeURIComponent(m![1]))!
    const spec = t.specs.find((s) => s.key === q.get('spec')) ?? t.specs[0]
    let items = offersFor(spec, t.name)
    const sort = q.get('sort')
    if (sort === 'price-desc') items = [...items].reverse()
    if (sort === 'recent') items = [...items].sort((a, b) => b.observed_at.localeCompare(a.observed_at))
    return { total: items.length, page: 1, size: 20, spec: null, items: items.slice(0, 20) } satisfies Offers
  }
  m = p.match(/^\/api\/v4\/catalog\/([^/]+)\/specs$/)
  if (m) {
    const name = decodeURIComponent(m[1])
    const t = MOCK_TOOLS.find((x) => x.name === name)
    if (!t) throw Object.assign(new Error('404'), { status: 404 })
    return { product: name, updated_at: MOCK_HOME.updated_at, n_specs: t.specs.length, starting_price: t.specs[0].min, currency: 'CNY',
      specs: t.specs.map((s) => toInfo(name, s)) } satisfies ToolSpecs
  }
  m = p.match(/^\/api\/v4\/tools\/([^/]+)$/)
  if (m) {
    const name = decodeURIComponent(m[1])
    const base = MOCK_HOME.tools.find((x) => x.name === name)
    if (!base) throw Object.assign(new Error('404'), { status: 404 })
    const t = MOCK_TOOLS.find((x) => x.name === name)!
    return { ...base, note: null, updated_at: MOCK_HOME.updated_at, specs: t.specs.map((s) => toInfo(name, s)) }
  }
  if (p === '/api/v4/shops') {
    let items = allShops.filter((s) => (!q.get('type') || s.type === q.get('type')) && (!q.get('product') || s.products.includes(q.get('product')!))
      && (!q.get('q') || (s.name + s.domain + s.products.join('')).toLowerCase().includes(q.get('q')!.toLowerCase())))
    const sort = q.get('sort')
    if (sort === 'price-desc') items = [...items].sort((a, b) => (b.price ?? 0) - (a.price ?? 0))
    else if (sort === 'recent') items = [...items].sort((a, b) => (b.updated_at ?? '').localeCompare(a.updated_at ?? ''))
    else items = [...items].sort((a, b) => (a.price ?? 1e9) - (b.price ?? 1e9))
    return { total: 224, page: 1, size: 20, items } satisfies Shops
  }
  throw Object.assign(new Error('404'), { status: 404 })
}
