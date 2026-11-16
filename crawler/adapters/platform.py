"""鲸发系统：接口来自商店 JS bundle；POST 仅白名单商品查询，非表单。"""
import re
from urllib.parse import urlsplit
from ..normalize import listing


class PlatformAdapter:
    async def crawl(self, ctx, shop, rule):
        u = urlsplit(shop["primary_url"])
        origin = f"{u.scheme}://{u.netloc}"
        if "16688.com.cn" in origin: origin = "https://www.16688.com.cn"
        code = u.path.rstrip("/").split("/")[-1]
        if "/goods/" in u.path:
            detail = (await ctx.query(origin + "/shopApi/goods/detail", {"goods_no": code})).json()
            if detail.get("code") != 1: raise ValueError(str(detail.get("msg")))
            code = detail["data"]["shop_no"]
        page_url = origin + "/shop/" + code
        await ctx.get(page_url)
        payload = {"shop_no": code, "goods_category_no": "", "keywords": "", "sort": "default"}
        rows = None
        categories = {}
        for attempt in range(2):
            try:
                r = await ctx.query(origin + "/shopApi/goods/list", payload)
                body = r.json()
                if body.get("code") != 1: raise ValueError(str(body.get("msg", body))[:180])
                rows = body["data"]["list"]
                break
            except Exception as e:
                error = f"商品接口失败：{type(e).__name__} {str(e)[:180]}"
        if rows is None:
            return await ctx.render(page_url, rule, error)
        try:
            cat = (await ctx.query(origin + "/shopApi/goodsCategory/list", {"shop_no": code})).json()
            categories = {r["goods_category_no"]: r["name"] for r in cat.get("data", [])}
        except Exception: pass
        result = []
        for r in rows:
            if r.get("price") is None or not r.get("name"): continue
            result.append(listing(r["name"], r["price"], origin + "/goods/" + r["goods_no"],
                                  categories.get(r.get("goods_category_no"), r.get("goods_category_no", "")),
                                  external_id=r["goods_no"], image=r.get("image"),
                                  stock=r.get("stock_available_quantity"), stock_status=r.get("stock_available_status"),
                                  sales=r.get("sales_count_text"), source_url=origin + "/shopApi/goods/list",
                                  description=r.get("description", "")))
        return result, {"status": "success" if result else "empty", "reason": "商品接口返回空列表" if not result else "", "method": "api", "complete": True}
