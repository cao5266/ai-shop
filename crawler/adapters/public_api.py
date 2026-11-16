"""网络观察确认的独立站共享系统：Dujiao Next 与 Zibll/异次元商品接口。"""
from urllib.parse import urlsplit, urljoin, quote
from ..normalize import listing


def zh(value):
    if isinstance(value, dict): return value.get("zh-CN") or next((v for v in value.values() if v), "")
    return value or ""


class NextAdapter:
    async def crawl(self, ctx, shop, rule):
        u = urlsplit(shop["primary_url"])
        base = f"{u.scheme}://{u.netloc}"
        out = []
        for page in range(1, 101):
            endpoint = base + f"/api/v1/public/products?page={page}&page_size=100"
            response = await ctx.get(endpoint)
            body = response.json()
            if body.get("status_code") != 0: raise ValueError(str(body.get("msg", "非商品接口")))
            rows = body["data"]
            if not isinstance(rows, list): raise ValueError("商品列表格式不匹配")
            for r in rows:
                title = zh(r.get("title"))
                category = zh((r.get("category") or {}).get("name"))
                variants = [v for v in r.get("skus", []) if v.get("is_active", True)] or [r]
                for v in variants:
                    price = v.get("price_amount", r.get("price_amount"))
                    if price is None: continue
                    spec_values = v.get("spec_values") or {}
                    specs = zh(spec_values) if any(k in spec_values for k in ("zh-CN", "en-US")) else " / ".join(str(k) + ":" + str(zh(val)) for k, val in spec_values.items())
                    image = (r.get("images") or [None])[0]
                    stock = v.get("auto_stock_available") if r.get("fulfillment_type") == "auto" else v.get("manual_stock_available")
                    out.append(listing(title + (" / " + specs if specs else ""), price,
                                       base + "/products/" + quote(r.get("slug") or str(r["id"])), category,
                                       external_id=f'{r["id"]}:{v.get("id", "default")}', image=urljoin(base, image) if image else None,
                                       stock=None if r.get("stock_quantity_hidden") else stock,
                                       stock_status="out" if v.get("is_sold_out", r.get("is_sold_out")) else "in",
                                       source_url=endpoint, description=zh(r.get("content"))))
            if len(rows) < 100: break
        return out, {"status": "success" if out else "empty", "reason": "" if out else "无公开商品", "method": "api", "complete": page < 100}


class YiciAdapter:
    async def crawl(self, ctx, shop, rule):
        u = urlsplit(shop["primary_url"])
        base = f"{u.scheme}://{u.netloc}"
        cats = (await ctx.get(base + "/user/api/index/data")).json()
        if cats.get("code") != 200: raise ValueError(str(cats.get("msg")))
        categories = []
        def walk(rows):
            for r in rows:
                categories.append(r)
                walk(r.get("children") or [])
        walk(cats.get("data") or [])
        out = []
        for cat in categories or [{"id": 0}]:
            endpoint = base + "/user/api/index/commodity?categoryId=" + str(cat["id"])
            body = (await ctx.get(endpoint)).json()
            if body.get("code") != 200: raise ValueError(str(body.get("msg")))
            for r in body.get("data") or []:
                if r.get("price") is None: continue
                out.append(listing(r["name"], r["price"], base + "/item/" + str(r["id"]),
                                   (r.get("category") or {}).get("name", cat.get("name", "")),
                                   external_id=str(r["id"]), image=urljoin(base, r.get("cover") or ""),
                                   stock=r.get("stock"), stock_status="out" if r.get("stock_state") == 0 else "in",
                                   sales=r.get("order_sold"), source_url=endpoint))
        return out, {"status": "success" if out else "empty", "reason": "" if out else "无公开商品", "method": "api", "complete": True}
