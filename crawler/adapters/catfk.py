"""catfk 旧鲸发系统，接口大小写和 16688 新系统不同，逐页读公开商品。"""
from urllib.parse import urlsplit
from ..normalize import listing


class CatfkAdapter:
    async def crawl(self, ctx, shop, rule):
        url = shop["primary_url"]
        u = urlsplit(url)
        origin = f"{u.scheme}://{u.netloc}"
        token = u.path.strip("/").split("/")[1]
        await ctx.get(url)
        info = (await ctx.query(origin + "/shopApi/Shop/info", {"token": token})).json()
        if info.get("code") != 1: raise ValueError(str(info.get("msg")))
        token = info["data"].get("token", token)
        out = []
        complete = True
        for kind in ("card", "resource", "equity", "article"):
            if info["data"].get(kind + "_count") == 0: continue
            categories = {}
            try:
                cats = (await ctx.query(origin + "/shopApi/Shop/categoryList", {"token": token, "goods_type": kind})).json()
                categories = {str(c["id"]): c["name"] for c in cats.get("data", [])}
            except Exception: pass
            for page in range(1, 101):
                for attempt in range(2):
                    try:
                        body = (await ctx.query(origin + "/shopApi/Shop/goodsList", {"token": token, "goods_type": kind,
                                 "keywords": "", "current": page, "pageSize": 50})).json()
                        break
                    except Exception:
                        if attempt: raise
                if body.get("code") != 1: raise ValueError(str(body.get("msg")))
                rows = body["data"]["list"]
                for r in rows:
                    title = r.get("name") or r.get("title")
                    price = r.get("price")
                    if title and price is not None:
                        key = r.get("goods_key") or r.get("key")
                        out.append(listing(title, price, r.get("link") or origin + "/item/" + str(key),
                                           (r.get("category") or {}).get("name", categories.get(str(r.get("category_id")), "")), external_id=str(key),
                                           image=r.get("image"), stock=(r.get("extend") or {}).get("stock_count"), sales=r.get("sales"),
                                           source_url=origin + "/shopApi/Shop/goodsList", description=r.get("description", "")))
                if len(rows) < 50: break
            else: complete = False
        return out, {"status": "success" if out else "empty", "reason": "" if out else "商品接口返回空列表", "method": "api", "complete": complete}
