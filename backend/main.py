"""FastAPI：JSON 接口 + 静态前端。"""
from __future__ import annotations
import datetime as dt
import os
import json
import statistics
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, or_, select, text

from .db import SessionLocal, init_db, engine
from .models import (CrawlRun, Price, PriceHistory, Product, PromoterAccount, RiskFlag, Shop,
                     ShopProduct, ShopSnapshot, XPost, Listing, ListingPriceHistory, ShopCrawlResult)

STATIC = Path(__file__).resolve().parent.parent / "static"
PRODUCT_NOTES = json.loads((STATIC.parent / "crawler/product_notes.json").read_text())
app = FastAPI(title="AI 订阅店铺导航", docs_url=None, redoc_url=None, openapi_url=None)


@app.on_event("startup")
def _startup():
    init_db()


def iso(d: dt.datetime | None):
    if d is None:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def num(x):
    return None if x is None else float(x)


def latest_run(s):
    return s.scalar(select(CrawlRun).where(CrawlRun.status == "success").order_by(CrawlRun.id.desc()).limit(1))


@app.get("/healthz")
def healthz():
    with engine.connect() as c:
        c.execute(text("select 1"))
    return {"ok": True}


@app.get("/api/meta")
def meta():
    with SessionLocal() as s:
        run = latest_run(s)
        total = s.scalar(select(func.count(Shop.id)))
        risk = dict(s.execute(select(Shop.risk_level, func.count()).group_by(Shop.risk_level)).all())
        types = s.execute(select(Shop.platform_type, func.count()).group_by(Shop.platform_type)
                          .order_by(func.count().desc())).all()
        prods = s.execute(
            select(Product.name, Product.family, Product.sort_order, func.count(ShopProduct.shop_id))
            .join(ShopProduct, ShopProduct.product_id == Product.id, isouter=True)
            .group_by(Product.id).order_by(Product.sort_order, Product.name)).all()
        runs_n = s.scalar(select(func.count(CrawlRun.id)).where(CrawlRun.status == "success"))
        return {
            "total_shops": total,
            "risk_counts": {"高": risk.get("高", 0), "中": risk.get("中", 0), "低": risk.get("低", 0)},
            "types": [{"name": n, "count": c} for n, c in types],
            "products": [{"name": n, "family": f, "count": c} for n, f, _, c in prods if c],
            "updated_at": iso(run.finished_at) if run else None,
            "source_generated_at": run.source_generated_at if run else None,
            "runs": runs_n,
            "scope": run.scope if run else None,
        }


def _shop_ids_query(q, product, risk, typ):
    stmt = select(Shop)
    if risk:
        stmt = stmt.where(Shop.risk_level == risk)
    if typ:
        stmt = stmt.where(Shop.platform_type == typ)
    if product:
        sub = (select(ShopProduct.shop_id).join(Product, Product.id == ShopProduct.product_id)
               .where(or_(Product.name == product, Product.family == product)))
        stmt = stmt.where(Shop.id.in_(sub))
    if q:
        like = f"%{q.strip().lower()}%"
        psub = (select(ShopProduct.shop_id).join(Product, Product.id == ShopProduct.product_id)
                .where(func.lower(Product.name).like(like)))
        lsub = select(Price.shop_id).where(func.lower(Price.label).like(like))
        stmt = stmt.where(or_(func.lower(Shop.name).like(like), func.lower(Shop.domain).like(like),
                              func.lower(Shop.shop_key).like(like), func.lower(Shop.primary_url).like(like),
                              func.lower(Shop.platform_type).like(like), Shop.id.in_(psub), Shop.id.in_(lsub)))
    return stmt


def _card(shop, prods, prices, flags):
    return {
        "id": shop.id, "name": shop.name, "domain": shop.domain, "type": shop.platform_type,
        "url": shop.primary_url, "n_posts": shop.n_posts, "n_accounts": shop.n_accounts,
        "risk": shop.risk_level, "flags": flags, "products": prods, "min_price": num(shop.min_price),
        "prices": prices, "http_code": shop.http_code, "page_status": shop.page_status,
        "example_post_url": shop.example_post_url,
        "first_seen_at": iso(shop.first_seen_at), "last_seen_at": iso(shop.last_seen_at),
    }


@app.get("/api/shops")
def shops(q: str = "", product: str = "", risk: str = "", type: str = "", sort: str = "mentions-desc",
          page: int = Query(1, ge=1), page_size: int = Query(30, ge=1, le=100)):
    with SessionLocal() as s:
        stmt = _shop_ids_query(q, product, risk, type)
        total = s.scalar(select(func.count()).select_from(stmt.subquery()))
        nulls_last = lambda col, desc: (col.desc() if desc else col.asc()).nulls_last()
        order = {
            "mentions-desc": [Shop.n_posts.desc(), Shop.name],
            "mentions-asc": [Shop.n_posts.asc(), Shop.name],
            "price-asc": [nulls_last(Shop.min_price, False), Shop.n_posts.desc()],
            "price-desc": [nulls_last(Shop.min_price, True), Shop.n_posts.desc()],
            "recent": [Shop.last_seen_at.desc(), Shop.n_posts.desc()],
        }.get(sort, [Shop.n_posts.desc()])
        rows = s.scalars(stmt.order_by(*order, Shop.id).limit(page_size).offset((page - 1) * page_size)).all()
        ids = [r.id for r in rows]
        prods, prices, flags = {}, {}, {}
        for sid, name in s.execute(select(ShopProduct.shop_id, Product.name).join(Product)
                                   .where(ShopProduct.shop_id.in_(ids)).order_by(Product.sort_order)):
            prods.setdefault(sid, []).append(name)
        for p in s.execute(select(Price.shop_id, Price.label, Price.amount, Price.source)
                           .where(Price.shop_id.in_(ids)).order_by(Price.id)):
            prices.setdefault(p[0], []).append({"label": p[1], "amount": num(p[2]), "source": p[3]})
        for row in s.scalars(select(Listing).where(Listing.shop_id.in_(ids), Listing.active.is_(True)).order_by(Listing.price)):
            prices.setdefault(row.shop_id, []).insert(0, listing_json(row))
        for sid, label, sev in s.execute(select(RiskFlag.shop_id, RiskFlag.label, RiskFlag.severity)
                                         .where(RiskFlag.shop_id.in_(ids), RiskFlag.active.is_(True)).order_by(RiskFlag.id)):
            if label not in [f["label"] for f in flags.setdefault(sid, [])]:
                flags[sid].append({"label": label, "severity": sev})
        return {"total": total, "page": page, "page_size": page_size,
                "items": [_card(r, prods.get(r.id, []), prices.get(r.id, []), flags.get(r.id, [])) for r in rows]}


@app.get("/api/shops/{shop_id}")
def shop_detail(shop_id: int):
    with SessionLocal() as s:
        shop = s.get(Shop, shop_id)
        if not shop:
            raise HTTPException(404, "店铺不存在")
        prods = [n for (n,) in s.execute(select(Product.name).join(ShopProduct).where(ShopProduct.shop_id == shop_id)
                                         .order_by(Product.sort_order))]
        prices = []
        for p in s.scalars(select(Price).where(Price.shop_id == shop_id).order_by(Price.source.desc(), Price.id)):
            hist = [{"amount": num(h.amount), "at": iso(h.observed_at)} for h in
                    s.scalars(select(PriceHistory).where(PriceHistory.price_id == p.id).order_by(PriceHistory.id))]
            prices.append({"label": p.label, "amount": num(p.amount), "source": p.source,
                           "first_seen_at": iso(p.first_seen_at), "last_seen_at": iso(p.last_seen_at), "history": hist})
        flags = [{"label": f.label, "severity": f.severity, "detail": f.detail, "active": f.active}
                 for f in s.scalars(select(RiskFlag).where(RiskFlag.shop_id == shop_id).order_by(RiskFlag.id))]
        posts = [{"url": x.url, "author": x.author, "text": x.text, "kind": x.kind}
                 for x in s.scalars(select(XPost).where(XPost.shop_id == shop_id, XPost.kind.in_(["example", "sample"]))
                                    .order_by(XPost.kind, XPost.id))]
        accts = [{"username": a.username, "post_count": a.post_count, "year": a.created_year, "followers": a.followers}
                 for a in s.scalars(select(PromoterAccount).where(PromoterAccount.shop_id == shop_id)
                                    .order_by(PromoterAccount.post_count.desc().nulls_last()).limit(12))]
        card = _card(shop, prods, [], [])
        card.update({"prices": prices, "risk_flags": flags, "posts": posts, "promoters": accts,
                      "final_url": shop.final_url, "all_urls": shop.all_urls or [], "notes": shop.notes})
        card["listings"] = [listing_json(r, s, history=True) for r in s.scalars(select(Listing).where(
            Listing.shop_id == shop_id).order_by(Listing.active.desc(), Listing.price))]
        result = s.scalar(select(ShopCrawlResult).where(ShopCrawlResult.shop_id == shop_id)
                          .order_by(ShopCrawlResult.id.desc()).limit(1))
        card["crawl"] = result.result if result else None
        return card


@app.get("/api/products")
def products():
    """按商品浏览：每个商品的店铺数与帖文报价区间（仅统计能明确归到该商品的报价）。"""
    with SessionLocal() as s:
        out = []
        for p in s.scalars(select(Product).order_by(Product.sort_order, Product.name)):
            n = s.scalar(select(func.count()).select_from(ShopProduct).where(ShopProduct.product_id == p.id))
            rows = s.scalars(select(Listing).where(Listing.product_id == p.id, Listing.active.is_(True))).all()
            specs = spec_groups(rows)
            primary = next((g for g in specs if g["currency"] == "CNY"), None)
            amts = [primary["min"], primary["max"]] if primary else []
            out.append({"name": p.name, "family": p.family, "n_shops": n, "n_prices": len(amts),
                        "min": min(amts) if amts else None, "max": max(amts) if amts else None,
                         "median": statistics.median(amts) if amts else None, "specs": specs, "n_prices": len(rows)})
        return [o for o in out if o["n_shops"]]


@app.get("/api/products/{name}/offers")
def product_offers(name: str):
    """某商品下的所有店铺报价，按价格升序；无报价的店铺排在后面。"""
    with SessionLocal() as s:
        p = s.scalar(select(Product).where(Product.name == name))
        if not p:
            raise HTTPException(404, "商品不存在")
        priced = s.execute(select(Shop, Listing).join(Listing, Listing.shop_id == Shop.id)
            .where(Listing.product_id == p.id, Listing.active.is_(True)).order_by(Listing.spec_key, Listing.price)).all()
        priced_ids = {sh.id for sh, _ in priced}
        others = s.scalars(select(Shop).join(ShopProduct, ShopProduct.shop_id == Shop.id)
                           .where(ShopProduct.product_id == p.id).order_by(Shop.n_posts.desc())).all()
        def mini(sh):
            return {"id": sh.id, "name": sh.name, "domain": sh.domain, "type": sh.platform_type, "url": sh.primary_url,
                    "risk": sh.risk_level, "n_posts": sh.n_posts}
        return {"product": p.name,
                 "offers": [{**mini(sh), **listing_json(row)} for sh, row in priced],
                 "specs": spec_groups([row for _, row in priced]),
                "no_price": [mini(sh) for sh in others if sh.id not in priced_ids]}


@app.get("/api/runs")
def runs():
    with SessionLocal() as s:
        return [{"id": r.id, "status": r.status, "finished_at": iso(r.finished_at), "source_generated_at": r.source_generated_at,
                 "shops_in_batch": r.shops_in_batch, "shops_new": r.shops_new, "prices_changed": r.prices_changed}
                for r in s.scalars(select(CrawlRun).order_by(CrawlRun.id.desc()).limit(30))]



def _groups(s):
    """商品分组：同一 family（如 Grok 的各档位）合成一个「工具」，其余各自独立。"""
    groups: dict[str, list[Product]] = {}
    for p in s.scalars(select(Product).order_by(Product.sort_order, Product.name)):
        groups.setdefault(p.family or p.name, []).append(p)
    return groups


def listing_json(r, s=None, history=False):
    obj = {"id": r.id, "title": r.title, "label": r.title, "amount": num(r.price), "currency": r.currency,
           "url": r.url, "category": r.category, "image": r.image, "spec": r.spec, "spec_key": r.spec_key,
           "stock": r.stock, "sales": r.sales, "risk": r.risk, "source": "page", "source_url": r.source_url,
           "active": r.active, "observed_at": iso(r.observed_at)}
    if history:
        obj["history"] = [{"amount": num(h.price), "currency": h.currency, "at": iso(h.observed_at)} for h in
                          s.scalars(select(ListingPriceHistory).where(ListingPriceHistory.listing_id == r.id)
                                    .order_by(ListingPriceHistory.id))]
    return obj


def spec_groups(rows):
    from crawler.normalize import representative_rank
    groups = {}
    shops = {}
    seen = set()
    for row in rows:
        identity = (row.url, row.title, row.currency)
        if identity in seen: continue
        seen.add(identity)
        key = (row.product_id, row.spec_key, row.currency)
        group = groups.setdefault(key, {"key": f"{row.product_id}:{row.spec_key}:{row.currency}",
                                       "label": row.spec.get("label", ""), "currency": row.currency,
                                       "spec": row.spec, "product": getattr(row, "product_name", ""),
                                       "title": row.title if row.spec.get("incomplete") else None,
                                       "min": float(row.price), "max": float(row.price), "n_prices": 0})
        group["min"] = min(group["min"], float(row.price))
        group["max"] = max(group["max"], float(row.price))
        group["n_prices"] += 1
        shops.setdefault(key, set()).add(row.shop_id)
        group["n_shops"] = len(shops[key])
    return sorted(groups.values(), key=representative_rank)


@app.get("/api/tools")
def tools():
    """首页商品卡片：每个工具的在售店铺数（去重）与帖文报价区间。只读聚合，不改表。"""
    with SessionLocal() as s:
        out = []
        for key, members in _groups(s).items():
            ids = [m.id for m in members]
            n = s.scalar(select(func.count(func.distinct(ShopProduct.shop_id))).where(ShopProduct.product_id.in_(ids)))
            rows = s.scalars(select(Listing).where(Listing.product_id.in_(ids), Listing.active.is_(True),
                Listing.observed_at >= dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7))).all()
            names = {p.id: p.name for p in members}
            for row in rows: row.product_name = names[row.product_id]
            specs = spec_groups(rows)
            # 优先入门月付，同档同周期再按覆盖店铺数选择。
            main = next((g for g in specs if g["currency"] == "CNY"), None)
            amts = [main["min"], main["max"]] if main else []
            if not n:
                continue
            reason = None
            sold_specs = []
            if not rows:
                sold = s.scalars(select(Listing).where(Listing.product_id.in_(ids), Listing.active.is_(False))).all()
                for row in sold: row.product_name = names[row.product_id]
                sold_specs = spec_groups(sold)
                related = s.scalars(select(Shop).join(ShopProduct, ShopProduct.shop_id == Shop.id)
                                    .where(ShopProduct.product_id.in_(ids)).distinct()).all()
                results = [s.scalar(select(ShopCrawlResult).where(ShopCrawlResult.shop_id == sh.id)
                           .order_by(ShopCrawlResult.id.desc()).limit(1)) for sh in related]
                reason = "店铺访问受限，尚未核实页面价格" if any(r and r.result.get("status") == "failed" for r in results) else "店铺页未找到对应在售商品报价"
                reason = PRODUCT_NOTES.get(key, {}).get("status", reason)
                if sold_specs: reason = "已采到店铺标价，当前商品已售罄"
            out.append({"name": key, "members": [m.name for m in members], "n_shops": n, "n_prices": len(amts),
                        "min": min(amts) if amts else None, "max": max(amts) if amts else None,
                        "median": statistics.median(amts) if amts else None, "specs": specs,
                        "primary_spec": main, "n_prices": len(rows), "source": "page", "price_status": reason,
                        "sold_out_specs": sold_specs})
        return out


@app.get("/api/tools/{name}/offers")
def tool_offers(name: str):
    """某工具下所有店铺：每店带该工具的全部帖文报价（按价格升序），另附「提到但未标价」的店铺。"""
    with SessionLocal() as s:
        members = _groups(s).get(name)
        if not members:
            raise HTTPException(404, "商品不存在")
        ids = [m.id for m in members]
        quotes: dict[int, list] = {}
        rows = s.scalars(select(Listing).where(Listing.product_id.in_(ids), Listing.active.is_(True),
                         Listing.observed_at >= dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7))
                         .order_by(Listing.price)).all()
        names = {p.id: p.name for p in members}
        for row in rows:
            row.product_name = names[row.product_id]
            quotes.setdefault(row.shop_id, []).append({**listing_json(row), "product": names[row.product_id],
                                                       "group_key": f"{row.product_id}:{row.spec_key}:{row.currency}"})
        shop_rows = s.scalars(select(Shop).join(ShopProduct, ShopProduct.shop_id == Shop.id)
                              .where(ShopProduct.product_id.in_(ids)).distinct()).all()
        def mini(sh):
            results = s.scalar(select(ShopCrawlResult).where(ShopCrawlResult.shop_id == sh.id)
                               .order_by(ShopCrawlResult.id.desc()).limit(1))
            qs = quotes.get(sh.id, [])
            return {"id": sh.id, "name": sh.name, "domain": sh.domain, "type": sh.platform_type, "url": sh.primary_url,
                     "risk": sh.risk_level, "n_posts": sh.n_posts, "last_seen_at": iso(sh.last_seen_at),
                    "quotes": qs, "crawl": results.result if results else None}
        shops_ = [mini(sh) for sh in shop_rows]
        priced = sorted([x for x in shops_ if x["quotes"]], key=lambda x: x["quotes"][0]["amount"])
        unpriced = sorted([x for x in shops_ if not x["quotes"]], key=lambda x: -x["n_posts"])
        sold = s.scalars(select(Listing).where(Listing.product_id.in_(ids), Listing.active.is_(False))).all()
        for row in sold: row.product_name = names[row.product_id]
        return {"name": name, "members": [m.name for m in members], "offers": priced, "no_price": unpriced,
                "specs": spec_groups(rows), "sold_out_specs": spec_groups(sold), "price_note": PRODUCT_NOTES.get(name)}


app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets") if (STATIC / "assets").exists() else None


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
