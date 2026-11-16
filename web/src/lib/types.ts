export interface Spec { key: string; label: string; currency: string; product: string; title: string | null; min: number; max: number; n_prices: number; n_shops: number }
export interface Tool {
  name: string; members: string[]; n_shops: number; n_selling: number; n_offers: number
  price: number | null; currency: string | null; spec: string | null; n_specs: number
  status: string | null; sold_out: Spec[]
}
/** /api/v4/tools/:name：规格只有 Spec 基础字段；完整规格字段在 /api/v4/catalog/:name/specs */
export interface ToolDetail extends Tool { specs: Spec[]; note: string | null; updated_at: string | null }
export interface Home { updated_at: string | null; total_shops: number; tools: Tool[]; types: { name: string; count: number }[] }
export interface OfferItem {
  id: number; shop: { id: number; name: string; domain: string; type: string }; title: string
  price: number; currency: string; stock: string | null; observed_at: string; lowest: boolean; go: string
}
export interface Offers { total: number; page: number; size: number; spec: Spec | null; items: OfferItem[] }
export interface ShopItem {
  id: number; name: string; domain: string; type: string; products: string[]
  price: number | null; price_title: string | null; price_spec: string | null; price_product: string | null
  updated_at: string | null; go: string
}
export interface Shops { total: number; page: number; size: number; items: ShopItem[] }
export interface Listing {
  id: number; title: string; product: string | null; price: number; currency: string; spec: string | null
  active: boolean; stock: string | null; observed_at: string; history: { price: number; at: string }[]; go: string
}
export interface ShopDetail { id: number; name: string; domain: string; type: string; go: string; listings: Listing[]; crawl_status: string | null; updated_at: string | null }

// ===== GET /api/v4/catalog/{name}/specs（见 crawler/reports/2026-11-16-spec-api.md）=====
// 文档里的字段在旧数据/个别商品上可能缺失，所以扩展字段全部可选，使用处统一走 lib/spec.ts 的容错函数。
export interface SpecInfo extends Spec {
  duration?: string | null        // 1月 / 1年 / 30天；未注明为 null
  tier?: string[]                 // plus / pro100 / max / ultra，可能重复
  delivery_type?: string          // 代充 / 成品号 / 兑换码 / Token号 / 组合 / 未注明交付
  quota?: string[]                // Token、积分、额度
  region?: string[]
  incomplete?: boolean            // true：按原标题（title）单独成组
}
export interface ToolSpecs {
  product: string
  updated_at: string | null
  n_specs: number
  starting_price: number | null   // 所有 CNY 规格的最低价
  currency: string | null
  specs: SpecInfo[]
}
