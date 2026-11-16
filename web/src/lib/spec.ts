import type { SpecInfo, Tool } from './types'

const uniq = (a?: string[] | null) => Array.from(new Set((a ?? []).filter(Boolean)))
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

/** 时长分组名：1月→月卡，1年→年卡，其余原样；缺失 → 时长未注明 */
export function durationGroup(d?: string | null): string {
  if (!d) return '时长未注明'
  if (d === '1月') return '月卡'
  if (d === '1年') return '年卡'
  if (d === '3月') return '季卡'
  return d
}

/** 规格名（不含时长）：优先用结构化字段拼，缺失时退回 label，最后给兜底文案 */
export function specName(s: SpecInfo): string {
  if (s.incomplete && s.title) return s.title
  const parts = [...uniq(s.tier).map(cap), ...uniq(s.quota), ...uniq(s.region)]
  const main = parts.join(' ')
  const delivery = s.delivery_type && s.delivery_type !== '未注明交付' ? s.delivery_type : ''
  return [main, delivery].filter(Boolean).join(' ') || (s.label ?? '').split(' / ').filter((x) => x !== '时长未注明').join(' ') || '未命名规格'
}

/** 规格完整描述：时长 + 名称，用于标题或副标题 */
export const specFull = (s: SpecInfo) => `${s.duration ?? '时长未注明'} ${specName(s)}`

/** 同一规格的入门价：已按完整规格过滤，优先 1 月，再取最低价 */
export function entrySpec(specs: SpecInfo[]): SpecInfo | null {
  const ok = specs.filter((s) => !s.incomplete && s.currency === 'CNY' && Number.isFinite(s.min))
  const monthly = ok.filter((s) => s.duration === '1月')
  const pool = monthly.length ? monthly : ok
  return pool.reduce<SpecInfo | null>((m, s) => (!m || s.min < m.min ? s : m), null)
}

// ---- 前端自带的展示元数据：接口目前不返回厂商、分类、简介 ----
const META: Record<string, { vendor: string; category: string; tagline: string }> = {
  'ChatGPT Plus': { vendor: 'OpenAI', category: '对话', tagline: 'GPT 系列对话、读图、语音与 Codex 基础额度' },
  'ChatGPT Pro': { vendor: 'OpenAI', category: '对话', tagline: '最高额度，适合长时间推理与大量调用' },
  'Claude Pro': { vendor: 'Anthropic', category: '对话', tagline: 'Claude 对话、长文档与 Projects' },
  'Claude Max': { vendor: 'Anthropic', category: '对话', tagline: '5 倍与 20 倍额度，含 Claude Code' },
  Cursor: { vendor: 'Anysphere', category: '编程', tagline: 'AI 编辑器，按档位区分每月请求额度' },
  Codex: { vendor: 'OpenAI', category: '编程', tagline: 'OpenAI 的编程代理，含在 ChatGPT 套餐里' },
  Copilot: { vendor: 'Microsoft', category: '编程', tagline: 'GitHub Copilot 个人版' },
  Grok: { vendor: 'xAI', category: '对话', tagline: 'SuperGrok 与 X Premium+ 档位' },
  Gemini: { vendor: 'Google', category: '对话', tagline: 'Google AI Pro 与 Ultra，含云盘空间' },
  Perplexity: { vendor: 'Perplexity', category: '搜索', tagline: '带引用的 AI 搜索，Pro 档位' },
  Midjourney: { vendor: 'Midjourney', category: '绘图', tagline: '图像生成，按快速出图时长分档' },
  Muse: { vendor: 'Muse', category: '绘图', tagline: '按 token 额度售卖的图像服务' },
  'X会员': { vendor: 'X', category: '社交', tagline: 'X Premium 与 Premium+' },
  'Telegram会员': { vendor: 'Telegram', category: '社交', tagline: 'Telegram Premium' },
}
export const toolMeta = (name: string) => META[name] ?? null
export const toolCategory = (t: Pick<Tool, 'name'>) => META[t.name]?.category ?? '其他'
