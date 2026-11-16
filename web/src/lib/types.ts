/** 规格组（/tools/:name 与 /catalog/:name/specs 通用）。除 key/label/currency/价格/店铺数外，其余字段缺失时前端降级。 */
export interface Spec {
  key: string; label: string; currency: string
  tier?: string | null; period?: string | null; delivery?: string
  lowest_price: number
  lowest_shop?: { name: string; shop_key: string } | null
  shop_count: number; listing_count?: number
}
export interface Tool {
  name: string; members: string[]; n_shops: number; n_selling: number; n_offers: number
  price: number | null; currency: string | null; spec: string | null; n_specs: number
  status: string | null; sold_out: Spec[]
  starting_price?: number | null
  entry_spec?: { name: string; label: string; tier: string | null; period: string | null; delivery: string } | null
  entry_price?: number | null; entry_shop_count?: number
}
/** /api/v4/tools/:name：specs 为全量规格组；note 只是面向用户的状态说明 */
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

// ===== GET /api/v4/catalog/{name}/specs?page=&page_size=（见 crawler/reports/2026-11-16-spec-api.md）=====
export interface ToolSpecs {
  product: string; updated_at: string | null
  n_specs: number; page: number; page_size: number; total_pages: number   // specs 只含当前页
  starting_price: number | null; currency: string | null
  entry_spec: Tool['entry_spec']; entry_price: number | null; entry_shop_count: number
  specs: Spec[]
}
