"""给 React 前端用的接口（全部签名 + 加密，必须分页，不含任何真实链接）。"""
from __future__ import annotations
import datetime as dt
import json
import statistics
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select

from crawler.normalize import representative_rank
from .db import SessionLocal
from .models import (CrawlRun, Listing, ListingPriceHistory, Product, Shop, ShopCrawlResult, ShopProduct)
from .secure import Ctx, go_token, guard, new_session, secure_ctx

router = APIRouter(prefix="/api/v4")
ROOT = Path(__file__).resolve().parent.parent
PRODUCT_NOTES = json.loads((ROOT / "crawler/product_notes.json").read_text())
FRESH_DAYS = 7
PAGE_MAX = 30
MAX_PAGE = 40


def iso(d):
    if d is None:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def num(x):
    return None if x is None else float(x)


def spec_groups(rows):
    groups, shops, seen = {}, {}, set()
    for row in rows:
        identity = (row.url, row.title, row.currency)
        if identity in seen:
            continue
        seen.add(identity)
        key = (row.product_id, row.spec_key, row.currency)
        g = groups.setdefault(key, {"key": f"{row.product_id}:{row.spec_key}:{row.currency}", "label": row.spec.get("label", ""),
                                    "currency": row.currency, "spec": row.spec, "product": getattr(row, "product_name", ""),
                                    "title": row.title if row.spec.get("incomplete") else None,
                                    "min": float(row.price), "max": float(row.price), "n_prices": 0})
        g["min"] = min(g["min"], float(row.price))
        g["max"] = max(g["max"], float(row.price))
        g["n_prices"] += 1
        shops.setdefault(key, set()).add(row.shop_id)
        g["n_shops"] = len(shops[key])
    return sorted(groups.values(), key=representative_rank)


def public_spec(g):
    return {"key": g["key"], "label": g["label"], "currency": g["currency"], "product": g["product"], "title": g["title"],
            "min": g["min"], "max": g["max"], "n_prices": g["n_prices"], "n_shops": g["n_shops"]}


def groups_of(s):
    out: dict[str, list[Product]] = {}
    for p in s.scalars(select(Product).order_by(Product.sort_order, Product.name)):
        out.setdefault(p.family or p.name, []).append(p)
    return out


def fresh_rows(s, ids, names):
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=FRESH_DAYS)
    rows = s.scalars(select(Listing).where(Listing.product_id.in_(ids), Listing.active.is_(True),
                                           Listing.observed_at >= cutoff).order_by(Listing.price)).all()
    for r in rows:
        r.product_name = names[r.product_id]
    return rows


_cache: dict = {}


def cached(key, ttl, fn):
    hit = _cache.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    val = fn()
    _cache[key] = (time.time() + ttl, val)
    return val


def tool_summary(s, key, members):
    ids = [m.id for m in members]
    names = {m.id: m.name for m in members}
    n = s.scalar(select(func.count(func.distinct(ShopProduct.shop_id))).where(ShopProduct.product_id.in_(ids)))
    rows = fresh_rows(s, ids, names)
    specs = spec_groups(rows)
    main = next((g for g in specs if g["currency"] == "CNY"), specs[0] if specs else None)
    status, sold = None, []
    if not rows:
        old = s.scalars(select(Listing).where(Listing.product_id.in_(ids), Listing.active.is_(False))).all()
        for r in old:
            r.product_name = names[r.product_id]
        sold = [public_spec(g) for g in spec_groups(old)][:2]
        results = [s.scalar(select(ShopCrawlResult).where(ShopCrawlResult.shop_id == sid)
                            .order_by(ShopCrawlResult.id.desc()).limit(1))
                   for sid in s.scalars(select(ShopProduct.shop_id).where(ShopProduct.product_id.in_(ids)).distinct())]
        status = ("店铺访问受限，尚未核实页面价格" if any(r and r.result.get("status") == "failed" for r in results)
                  else "店铺页未找到对应在售商品")
        status = PRODUCT_NOTES.get(key, {}).get("status", status)
        if sold:
            status = "已采到标价，当前商品已售罄"
    return {"name": key, "members": [m.name for m in members], "n_shops": n, "n_selling": len({r.shop_id for r in rows}), "n_offers": len(rows),
            "price": main["min"] if main else None, "currency": main["currency"] if main else None,
            "spec": main["label"] if main else None, "n_specs": len(specs), "status": status, "sold_out": sold,
            "specs": [public_spec(g) for g in specs]}


def last_update(s):
    run = s.scalar(select(CrawlRun).where(CrawlRun.status == "success").order_by(CrawlRun.id.desc()).limit(1))
    return iso(run.finished_at) if run else None


@router.get("/session")
def session(request: Request):
    guard(request, "session")
    return new_session(request)


@router.get("/home")
def home(ctx: Ctx = Depends(secure_ctx)):
    def build():
        with SessionLocal() as s:
            tools = [tool_summary(s, k, m) for k, m in groups_of(s).items()]
            tools = [t for t in tools if t["n_shops"]]
            for t in tools:
                t.pop("specs")
            types = s.execute(select(Shop.platform_type, func.count()).group_by(Shop.platform_type)
                              .order_by(func.count().desc())).all()
            return {"updated_at": last_update(s), "total_shops": s.scalar(select(func.count(Shop.id))),
                    "tools": tools, "types": [{"name": n, "count": c} for n, c in types]}
    return ctx.seal(cached("home", 60, build))


@router.get("/tools/{name}")
def tool(name: str, ctx: Ctx = Depends(secure_ctx)):
    with SessionLocal() as s:
        members = groups_of(s).get(name)
        if not members:
            raise HTTPException(404, "商品不存在")
        out = tool_summary(s, name, members)
        out["note"] = PRODUCT_NOTES.get(name, {}).get("reason")
        out["updated_at"] = last_update(s)
        return ctx.seal(out)


@router.get("/tools/{name}/offers")
def offers(name: str, spec: str = "", sort: str = "price-asc", page: int = Query(1, ge=1, le=MAX_PAGE),
           size: int = Query(20, ge=1, le=PAGE_MAX), ctx: Ctx = Depends(secure_ctx)):
    with SessionLocal() as s:
        members = groups_of(s).get(name)
        if not members:
            raise HTTPException(404, "商品不存在")
        ids = [m.id for m in members]
        rows = fresh_rows(s, ids, {m.id: m.name for m in members})
        groups = spec_groups(rows)
        g = next((x for x in groups if x["key"] == spec), groups[0] if groups else None)
        if not g:
            return ctx.seal({"total": 0, "page": page, "items": [], "spec": None})
        pid, skey, cur = g["key"].split(":", 2)
        seen, picked = set(), []
        for r in rows:
            if (str(r.product_id), r.spec_key, r.currency) != (pid, skey, cur):
                continue
            ident = (r.url, r.title, r.currency)
            if ident in seen:
                continue
            seen.add(ident)
            picked.append(r)
        if sort == "price-desc":
            picked.sort(key=lambda r: -float(r.price))
        elif sort == "recent":
            picked.sort(key=lambda r: r.observed_at, reverse=True)
        else:
            picked.sort(key=lambda r: float(r.price))
        total = len(picked)
        part = picked[(page - 1) * size: page * size]
        shops = {x.id: x for x in s.scalars(select(Shop).where(Shop.id.in_({r.shop_id for r in part})))}
        low = g["min"]
        items = [{"id": r.id, "shop": {"id": r.shop_id, "name": shops[r.shop_id].name, "domain": shops[r.shop_id].domain,
                                       "type": shops[r.shop_id].platform_type},
                  "title": r.title, "price": num(r.price), "currency": r.currency, "stock": r.stock,
                  "observed_at": iso(r.observed_at), "lowest": float(r.price) == low, "go": "/go/" + go_token(r.shop_id, r.id)}
                 for r in part]
        return ctx.seal({"total": total, "page": page, "size": size, "spec": public_spec(g), "items": items})


@router.get("/shops")
def shops(q: str = Query("", max_length=60), product: str = "", type: str = "", sort: str = "price-asc",
          page: int = Query(1, ge=1, le=MAX_PAGE), size: int = Query(20, ge=1, le=PAGE_MAX), ctx: Ctx = Depends(secure_ctx)):
    with SessionLocal() as s:
        stmt = select(Shop)
        if type:
            stmt = stmt.where(Shop.platform_type == type)
        if product:
            pids = [p.id for p in groups_of(s).get(product, [])]
            stmt = stmt.where(Shop.id.in_(select(ShopProduct.shop_id).where(ShopProduct.product_id.in_(pids))))
        q = q.strip().lower()
        if q:
            like = f"%{q}%"
            psub = select(ShopProduct.shop_id).join(Product, Product.id == ShopProduct.product_id).where(func.lower(Product.name).like(like))
            lsub = select(Listing.shop_id).where(func.lower(Listing.title).like(like))
            stmt = stmt.where(or_(func.lower(Shop.name).like(like), Shop.domain == q, func.lower(Shop.platform_type).like(like),
                                  Shop.id.in_(psub), Shop.id.in_(lsub)))
        total = s.scalar(select(func.count()).select_from(stmt.subquery()))
        # 只看已归类到某个 AI 商品的在售标价；教程、优惠券、测试商品（product_id 为空）不算最低价
        minp = (select(func.min(Listing.price)).where(Listing.shop_id == Shop.id, Listing.active.is_(True),
                Listing.currency == "CNY", Listing.product_id.is_not(None)).correlate(Shop).scalar_subquery())
        order = {"price-asc": [minp.asc().nulls_last(), Shop.name],
                 "price-desc": [minp.desc().nulls_last(), Shop.name],
                 "recent": [Shop.last_seen_at.desc(), Shop.name], "name": [Shop.name]}.get(sort, [Shop.name])
        rows = s.scalars(stmt.order_by(*order, Shop.id).limit(size).offset((page - 1) * size)).all()
        ids = [r.id for r in rows]
        cheapest, prods = {}, {}
        for l in s.scalars(select(Listing).where(Listing.shop_id.in_(ids), Listing.active.is_(True), Listing.currency == "CNY",
                                                 Listing.product_id.is_not(None)).order_by(Listing.price)):
            cheapest.setdefault(l.shop_id, l)
            prods.setdefault(l.shop_id, [])
            if l.product_id and l.product_id not in prods[l.shop_id]:
                prods[l.shop_id].append(l.product_id)
        pname = {p.id: p.name for p in s.scalars(select(Product))}
        for sid, pid in s.execute(select(ShopProduct.shop_id, ShopProduct.product_id).where(ShopProduct.shop_id.in_(ids))):
            if sid not in cheapest:
                prods.setdefault(sid, [])
                if pid not in prods[sid]:
                    prods[sid].append(pid)
        items = []
        for r in rows:
            c = cheapest.get(r.id)
            items.append({"id": r.id, "name": r.name, "domain": r.domain, "type": r.platform_type,
                          "products": [pname[i] for i in prods.get(r.id, []) if i in pname],
                          "price": num(c.price) if c else None, "price_title": c.title if c else None,
                          "price_spec": c.spec.get("label") if c else None, "price_product": pname.get(c.product_id) if c else None,
                          "updated_at": iso(c.observed_at) if c else iso(r.last_seen_at),
                          "go": "/go/" + go_token(r.id, c.id if c else None)})
        return ctx.seal({"total": total, "page": page, "size": size, "items": items})


@router.get("/shops/{shop_id}")
def shop_detail(shop_id: int, ctx: Ctx = Depends(secure_ctx)):
    with SessionLocal() as s:
        shop = s.get(Shop, shop_id)
        if not shop:
            raise HTTPException(404, "店铺不存在")
        pname = {p.id: p.name for p in s.scalars(select(Product))}
        listings = []
        for l in s.scalars(select(Listing).where(Listing.shop_id == shop_id).order_by(Listing.active.desc(), Listing.price).limit(200)):
            hist = [{"price": num(h.price), "at": iso(h.observed_at)} for h in
                    s.scalars(select(ListingPriceHistory).where(ListingPriceHistory.listing_id == l.id).order_by(ListingPriceHistory.id))]
            listings.append({"id": l.id, "title": l.title, "product": pname.get(l.product_id), "price": num(l.price),
                             "currency": l.currency, "spec": l.spec.get("label"), "active": l.active, "stock": l.stock,
                             "observed_at": iso(l.observed_at), "history": hist if len(hist) > 1 else [],
                             "go": "/go/" + go_token(shop_id, l.id)})
        crawl = s.scalar(select(ShopCrawlResult).where(ShopCrawlResult.shop_id == shop_id).order_by(ShopCrawlResult.id.desc()).limit(1))
        return ctx.seal({"id": shop.id, "name": shop.name, "domain": shop.domain, "type": shop.platform_type,
                         "go": "/go/" + go_token(shop.id, None), "listings": listings,
                         "crawl_status": (crawl.result.get("reason") or crawl.result.get("status")) if crawl else None,
                         "updated_at": iso(shop.last_seen_at)})
