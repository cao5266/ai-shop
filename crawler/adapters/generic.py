import json
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from ..normalize import listing


def parse_html(html, url, rule=None):
    rule = rule or {}
    soup = BeautifulSoup(html, "html.parser")
    out = []
    # 标准结构化数据中的 Product/Offer，不拿页面任意数字当商品价格。
    def walk(obj):
        if isinstance(obj, list):
            for x in obj: walk(x)
        elif isinstance(obj, dict):
            if obj.get("@type") == "Product":
                offers = obj.get("offers", [])
                if isinstance(offers, dict): offers = [offers]
                for offer in offers:
                    if offer.get("price") is not None and obj.get("name"):
                        out.append(listing(obj["name"] + (" / " + offer["name"] if offer.get("name") else ""), offer["price"], urljoin(url, offer.get("url") or obj.get("url") or url),
                                           obj.get("category", ""), image=obj.get("image"), currency_source=offer.get("priceCurrency"),
                                           stock_status="out" if "OutOfStock" in offer.get("availability", "") else "in", source_url=url))
            for v in obj.values():
                if isinstance(v, (list, dict)): walk(v)
    for node in soup.select('script[type="application/ld+json"]'):
        try: walk(json.loads(node.string or node.get_text()))
        except (ValueError, TypeError): pass
    selector = rule.get("card", '.goods-card, .goods-item, .product-card, .product-item, .shop-item, [data-goods-id], .block.block-rounded, .card')
    for node in soup.select(selector):
        text = node.get_text(" ", strip=True)
        if len(text) > 1800: continue
        p = node.select_one(rule.get("price", '.price, .goods-price, .product-price, [itemprop="price"]'))
        price_text = p.get("content", p.get_text(" ", strip=True)) if p else text
        m = re.search(r"(?:[¥￥]\s*|(?:售价|价格)\s*[:：]?\s*)(\d+(?:\.\d+)?)|(?<!\d)(\d+(?:\.\d+)?)\s*元", price_text)
        if not m: continue
        title_node = node.select_one(rule.get("title", '.goods-name, .product-name, .card-title, .block-title, h3, h4, h5, [itemprop="name"]'))
        a = node.select_one('a[href*="/buy/"], a[href*="/goods/"], a[href*="/product/"], a[href*="/purchase"], a[href*="/item/"]')
        if not a: continue
        title = title_node.get_text(" ", strip=True) if title_node else a.get("title") or a.get_text(" ", strip=True)
        if not title or title in ("购买", "立即购买", "查看详情"): continue
        image = node.select_one("img")
        stock = re.search(r"库存\s*[:：]?\s*(\d+)", text)
        sales = re.search(r"(?:销量|已售)\s*[:：]?\s*(\d+)", text)
        out.append(listing(title, m[1] or m[2], urljoin(url, a["href"]), rule.get("category", ""),
                           image=urljoin(url, image.get("src", "")) if image else None,
                           stock=int(stock[1]) if stock else None, sales=sales[1] if sales else None, source_url=url))
    return out


class GenericAdapter:
    async def crawl(self, ctx, shop, rule):
        url = shop["primary_url"]
        response = await ctx.get(url)
        html_lower = response.text.lower()
        if "shopify" in html_lower or "cdn.shopify.com" in html_lower:
            platform = "Shopify"
        elif "woocommerce" in html_lower or "wp-content/plugins/woocommerce" in html_lower:
            platform = "WooCommerce"
        elif "萌奶" in response.text or "mengnai" in html_lower:
            platform = "萌奶"
        elif "/shopapi/" in html_lower:
            platform = "ShopApi 类发卡网"
        elif re.search(r"独角数卡|dujiaoka", html_lower):
            platform = "独角数卡"
        elif re.search(r"异次元|yilep|yipay", html_lower):
            platform = "异次元"
        else:
            platform = "通用独立站"
        # 发现独立站共享系统后直接走公开查询，后续可写入域名映射。
        if re.search(r"/api/v1/public|Dujiao|dujiao-next", response.text, re.I):
            from .public_api import NextAdapter
            try: return await NextAdapter().crawl(ctx, shop, rule)
            except Exception: pass
        if re.search(r"/user/api/|/app/View/User/|异次元", response.text, re.I):
            from .public_api import YiciAdapter
            try: return await YiciAdapter().crawl(ctx, shop, rule)
            except Exception: pass
        rows = parse_html(response.text, str(response.url), rule)
        soup = BeautifulSoup(response.text, "html.parser")
        # 发卡类独立商品页的默认公开标价，标题必须来自商品主标题。
        if not rows and re.search(r'/item(?:/|\?)', url):
            title_node = soup.select_one('h1, .product-title, .goods-name')
            text = soup.get_text(' ', strip=True)
            m = re.search(r'价格\s*[¥￥]\s*(\d+(?:\.\d+)?)', text)
            if title_node and m:
                rows.append(listing(title_node.get_text(' ', strip=True), m[1], str(response.url),
                    source_url=str(response.url), stock_status='out' if '暂时无货' in text else 'in'))
        # 多页独立站：只遍历页面实际链接的商品页，不触发购买或表单。
        product_urls = list(dict.fromkeys(urljoin(str(response.url), a["href"]) for a in soup.select('a[href^="/product/"]')))
        for product_url in product_urls[:80]:
            if product_url == str(response.url): continue
            detail = await ctx.get(product_url)
            rows.extend(parse_html(detail.text, str(detail.url), rule))
        if rows: return rows, {"status": "success", "reason": "", "method": "html", "complete": False, "platform": platform}
        rows, status = await ctx.render(url, rule, f"HTTP {response.status_code}，静态页无商品价格")
        status["platform"] = platform
        return rows, status


class DujiaoAdapter(GenericAdapter):
    """独角数卡 /buy/{id} 卡片复用 HTML 解析；只有 GET 商品详情。"""
    pass
