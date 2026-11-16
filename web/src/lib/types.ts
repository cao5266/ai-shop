export interface Spec { key: string; label: string; currency: string; product: string; title: string | null; min: number; max: number; n_prices: number; n_shops: number }
export interface Tool {
  name: string; members: string[]; n_shops: number; n_selling: number; n_offers: number
  price: number | null; currency: string | null; spec: string | null; n_specs: number
  status: string | null; sold_out: Spec[]
}
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
