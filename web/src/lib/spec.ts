import type { Spec, Tool } from './types'

const cap = (s: string) => s.replace(/^[a-z]/, (c) => c.toUpperCase())

const UNK = '时长未注明' // 仅用于识别接口里的占位值，绝不显示
/** 周期分组名：1月→月卡，1年→年卡，3月→季卡，其余原样；缺失 → 其他规格 */
export function durationGroup(d?: string | null): string {
  if (!d || d === UNK) return '其他规格'
  if (d === '1月') return '月卡'
  if (d === '1年') return '年卡'
  if (d === '3月') return '季卡'
  return d
}

/** 规格名（不含周期）：取 label 去掉开头的周期，再逐段首字母大写；缺失时用 tier + delivery 兜底 */
export function specName(s: Pick<Spec, 'label' | 'tier' | 'delivery'>): string {
  const parts = (s.label ?? '').split(' / ').map((x) => x.trim()).filter(Boolean)
  if (parts[0] === UNK || /^\d+(天|月|年)$/.test(parts[0] ?? '')) parts.shift()
  const name = parts.map(cap).join(' ')
  return name || [s.tier ? cap(s.tier) : '', s.delivery && s.delivery !== '未注明交付' ? s.delivery : ''].filter(Boolean).join(' ') || '未命名规格'
}

/** 时长文本，未知返回空串 */
export const periodText = (s: { period?: string | null }) => (s.period && s.period !== UNK ? s.period : '')
export const lowestShopName = (s: Spec) => s.lowest_shop?.name || null

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

/** 至少有一家店铺报价；没有报价的商品不在首页、分类、搜索筛选里展示（有报价后自动出现） */
export const hasOffer = (t: Pick<Tool, 'price' | 'starting_price'>) => (t.starting_price ?? t.price) != null
