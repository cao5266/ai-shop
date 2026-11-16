"""给 React 前端用的接口（全部签名 + 加密，必须分页，不含任何真实链接）。"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import re
import statistics
import time
from pathlib import Path
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select

from crawler.normalize import representative_rank
from crawler.normalize import comparison_exclusion
from crawler.price_quality import assess_price_group
from .db import SessionLocal
from .models import (CrawlRun, Listing, ListingPriceHistory, Product, Shop, ShopCrawlResult, ShopProduct)
from .secure import Ctx, go_token, guard, new_session, secure_ctx

router = APIRouter(prefix="/api/v4")
ROOT = Path(__file__).resolve().parent.parent
PRODUCT_NOTES = json.loads((ROOT / "crawler/product_notes.json").read_text())
FRESH_DAYS = 7
PAGE_MAX = 30
MAX_PAGE = 40
STANDARD_PRODUCTS = ["ChatGPT Plus", "ChatGPT Pro", "Claude Pro", "Claude Max", "Grok Plus", "Grok Premium",
                     "Grok Super", "Grok Ultra", "Cursor", "Muse", "Gemini", "Perplexity", "Copilot",
                     "X会员", "Telegram会员", "Codex", "Midjourney", "Grok"]


def iso(d):
    if d is None:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def num(x):
    return None if x is None else float(x)


def _canonical_period(spec: dict, title: str) -> str:
    raw = str(spec.get("duration") or "").strip().lower()
    label = str(spec.get("label") or "").strip().lower()
    text = re.sub(r"(?:pro|max)\s*\d+", "", " ".join((raw, label, title.lower())))
    compact = re.sub(r"\s+", "", text)
    if re.search(r"永久|终身|终生|lifetime|permanent", compact): return "永久"
    if re.search(r"半年|半年度", compact): return "6月"
    if re.search(r"季度|季卡|季付|3months?|3个月|3月|90天", compact): return "3月"
    if re.search(r"月卡|月付|月费|月订阅|一个月|一月|monthly|1month", compact): return "1月"
    if re.search(r"年卡|年付|年费|一年|一整年|annual|1year|12月", compact): return "1年"
    # Read numeric periods from duration, label, and title. Warranty-only days do
    # not describe the subscription term; warranty text that explicitly says
    # "订阅" does.
    period_re = re.compile(r"(?<![a-z0-9])(\d+)\s*(个月|月|months?|年|years?|天|日|days?|周|weeks?|小时|时|hours?)", re.I)
    for match in period_re.finditer(text):
        amount = int(match.group(1))
        unit = match.group(2).lower()
        context = text[max(0, match.start() - 10):min(len(text), match.end() + 5)]
        if any(word in context for word in ("质保", "保修", "售后", "首登")) and "订阅" not in context:
            continue
        if unit in {"年", "year", "years"}: return "1年" if amount == 1 else f"{amount}年"
        if unit in {"月", "个月", "month", "months"}:
            if amount == 12: return "1年"
            return "1月" if amount == 1 else f"{amount}月"
        if unit in {"周", "week", "weeks"}:
            if amount == 4: return "1月"
            return f"{amount * 7}天"
        if unit in {"天", "日", "day", "days"}:
            if amount in (28, 29, 30, 31): return "1月"
            if amount == 90: return "3月"
            if amount == 365: return "1年"
            return f"{amount}天"
        return f"{amount}小时"
    count = re.search(r"(\d+)\s*(?:次卡|次(?:充值|兑换|使用|订阅))", compact)
    if count: return f"{int(count.group(1))}次"
    if re.search(r"一次|单次|一次性|one[- ]?time", compact): return "1次"
    return "未注明周期"


def _canonical_tier(spec: dict) -> tuple[str, ...]:
    values = spec.get("tier") or []
    if isinstance(values, str): values = [values]
    normalized = set()
    for value in values:
        item = re.sub(r"\s+", "", str(value).lower()).replace("＋", "+")
        item = re.sub(r"^(pro|max)(100|200|500|5x|20x)$", r"\1\2", item)
        if item in {"p+", "plus+", "+"}: item = "plus"
        if item: normalized.add(item)
    return tuple(sorted(normalized))


def _canonical_delivery(spec: dict, title: str) -> str:
    raw = re.sub(r"\s+", "", str(spec.get("delivery") or "").lower())
    if raw in {"代充", "直充", "直冲", "充值", "自充", "卡充", "topup"}: return "代充"
    if raw in {"成品号", "成品账号", "账号", "帐号", "共享号", "account"}: return "成品号"
    if raw in {"兑换码", "卡密", "cdk", "cdkey", "激活码"}: return "兑换码"
    if raw in {"组合", "套餐", "组合套餐", "bundle"}: return "组合"
    if raw in {"token号", "token账号"}: return "Token号"
    if raw and raw != "未注明交付": return raw
    t = title.lower()
    if re.search(r"三合一|多合一|组合|联合会员|套餐包|\+.*(?:会员|pro|plus)", t): return "组合"
    if re.search(r"兑换码|卡密|cdk|cdkey|激活码", t): return "兑换码"
    if re.search(r"成品号|成品账号|账号密码|共享号", t): return "成品号"
    if re.search(r"代充|直充|直冲|自充|卡充|充值", t): return "代充"
    return "未注明交付"


def _normalized_spec(row):
    spec = row.spec or {}
    title = row.title or ""
    tier = _canonical_tier(spec)
    period = _canonical_period(spec, title)
    delivery = _canonical_delivery(spec, title)
    quota = tuple(sorted({re.sub(r"\s+", "", str(v).lower()) for v in (spec.get("quota") or []) if v}))
    region = tuple(sorted({re.sub(r"\s+", "", str(v).lower()) for v in (spec.get("region") or []) if v}))
    uncertain = period == "未注明周期" or not tier or delivery == "未注明交付"
    identity = (tier, period, delivery, quota, region)
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()[:32]
    label_parts = [period, *quota, *tier, *region, delivery]
    label = " / ".join(dict.fromkeys(label_parts))
    return {"key": digest, "tier": tier, "period": period, "delivery": delivery,
            "quota": quota, "region": region, "label": label,
            "identity": identity, "incomplete": uncertain}


def spec_group_id(row):
    normalized = _normalized_spec(row)
    return (str(row.product_id), normalized["key"], row.currency)


def _store_display_name(shop):
    name = str(getattr(shop, "name", "") or "").strip()
    domain = str(getattr(shop, "domain", "") or "").strip()
    key = str(getattr(shop, "shop_key", "") or "").strip()
    if not name or name.casefold().startswith("request id") or name == key:
        return domain or "未知店铺"
    # Some item-page records mistakenly stored "product title - store name" as
    # the store name. Keep only the verified storefront suffix in that case.
    if " - " in name:
        suffix = name.rsplit(" - ", 1)[1].strip().strip("「」『』[]（）() ")
        if suffix and re.search(r"gemini|claude|gpt|grok|cursor|copilot|perplexity|codex|muse|会员|成品|代充", name[:name.rfind(" - ")], re.I):
            return suffix
    if re.search(r"(?:gemini|claude|gpt|grok|cursor|copilot|perplexity|codex|muse).{0,35}(?:成品|代充|月卡|会员|ultra|max|pro)", name, re.I):
        return domain or "未知店铺"
    return name


def spec_groups(rows):
    groups, shops, seen = {}, {}, set()
    for row in rows:
        identity = (row.product_id, row.shop_id, row.url, row.title, row.currency)
        if identity in seen:
            continue
        seen.add(identity)
        normalized = _normalized_spec(row)
        key = (row.product_id, normalized["key"], row.currency)
        g = groups.setdefault(key, {"key": f"{row.product_id}:{normalized['key']}:{row.currency}",
                                    "label": normalized["label"], "currency": row.currency,
                                    "product": getattr(row, "product_name", ""),
                                    "tier": "+".join(normalized["tier"]) if normalized["tier"] else None,
                                    "period": normalized["period"], "delivery": normalized["delivery"],
                                    "spec": {"duration": normalized["period"], "tier": list(normalized["tier"]),
                                             "incomplete": normalized["incomplete"]},
                                    "lowest_price": None, "lowest_shop": None,
                                    "shop_count": 0, "listing_count": 0, "_rows": [], "_lowest_order": None})
        g["_rows"].append(row)
        g["listing_count"] += 1
        shops.setdefault(key, set()).add(row.shop_id)
        g["shop_count"] = len(shops[key])
    for g in groups.values():
        price_reasons = assess_price_group([(float(r.price), r.title) for r in g["_rows"]], currency=g["currency"])
        candidates = []
        for row, reason in zip(g["_rows"], price_reasons):
            row.price_anomaly = reason is not None
            row.price_anomaly_reason = reason
            if reason is not None:
                continue
            shop = {"name": str(getattr(row, "shop_name", "") or "未知店铺"),
                    "public_shop_id": str(row.shop_id) if row.shop_id is not None else None}
            candidates.append((float(row.price), shop["name"].casefold(), shop["public_shop_id"] or "", shop))
        if candidates:
            lowest = min(candidates, key=lambda v: v[:3])
            g["lowest_price"] = lowest[0]
            g["lowest_shop"] = lowest[3]
        # Keep the legacy ranker fed while public output uses the structured schema.
        g["min"] = g["lowest_price"] if g["lowest_price"] is not None else float("inf")
        g["n_shops"] = g["shop_count"]
        g.pop("_rows", None)
        g.pop("_lowest_order", None)
    return sorted(groups.values(), key=representative_rank)


def public_spec(g):
    return {"key": g["key"], "label": g["label"], "currency": g["currency"],
            "tier": g["tier"], "period": g["period"], "delivery": g["delivery"],
            "lowest_price": g["lowest_price"], "lowest_shop": g["lowest_shop"],
            "shop_count": g["shop_count"], "listing_count": g["listing_count"]}


def groups_of(s):
    out: dict[str, list[Product]] = {}
    products = list(s.scalars(select(Product).order_by(Product.sort_order, Product.name)))
    present = {p.name for p in products}
    for order, name in enumerate(STANDARD_PRODUCTS):
        if name not in present:
            products.append(SimpleNamespace(id=None, name=name, family="Grok" if name.startswith("Grok") else None,
                                            sort_order=order))
    for p in sorted(products, key=lambda x: (x.sort_order, x.name)):
        out.setdefault(p.family or p.name, []).append(p)
    return out


def fresh_rows(s, ids, names):
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=FRESH_DAYS)
    rows = s.scalars(select(Listing).where(Listing.product_id.in_(ids), Listing.active.is_(True),
                                           Listing.observed_at >= cutoff).order_by(Listing.price)).all()
    latest = select(ShopCrawlResult.shop_id.label("shop_id"),
                    func.max(ShopCrawlResult.id).label("latest_id")).group_by(ShopCrawlResult.shop_id).subquery()
    validation_only = set(s.scalars(select(ShopCrawlResult.shop_id)
                                    .join(latest, ShopCrawlResult.id == latest.c.latest_id)
                                    .where(ShopCrawlResult.result["retry_result"].as_string() == "需验证，暂无报价")))
    shops = {shop.id: shop for shop in s.scalars(select(Shop).where(Shop.id.in_({r.shop_id for r in rows}))) } if rows else {}
    rows = [r for r in rows if r.shop_id not in validation_only
            and not comparison_exclusion(r.title, names[r.product_id], r.spec or {}, r.price)]
    for r in rows:
        r.product_name = names[r.product_id]
        shop = shops.get(r.shop_id)
        r.shop_name = _store_display_name(shop) if shop else "未知店铺"
        r.shop_key = shop.shop_key if shop else ""
    return rows


_cache: dict = {}


def cached(key, ttl, fn):
    hit = _cache.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    val = fn()
    _cache[key] = (time.time() + ttl, val)
    return val


def product_spec_data(s, ids, names):
    latest_run = s.scalar(select(func.max(CrawlRun.id)).where(CrawlRun.status == "success")) or 0
    cache_key = ("product-spec-data", id(s.get_bind()), tuple(sorted(ids, key=lambda value: (value is None, value or 0))), latest_run)
    return cached(cache_key, 60, lambda: (lambda rows: (rows, spec_groups(rows)))(fresh_rows(s, ids, names)))


def product_price_fields(specs):
    """One source for the product starting price and representative entry spec."""
    if not specs:
        return {"starting_price": None, "currency": None, "entry_spec": None,
                "entry_price": None, "entry_shop_count": 0}
    priced_specs = [g for g in specs if g["lowest_price"] is not None]
    if not priced_specs:
        return {"starting_price": None, "currency": None, "entry_spec": None,
                "entry_price": None, "entry_shop_count": 0}
    cny = [g for g in priced_specs if g["currency"] == "CNY"]
    priced = cny or priced_specs
    currency = priced[0]["currency"]
    # The selected entry specification is also the advertised starting price.
    entry = min(priced, key=lambda g: (g["lowest_price"], representative_rank(g)))
    starting_price = entry["lowest_price"]
    entry_spec = {"key": entry["key"], "name": entry["label"], "label": entry["label"], "tier": entry["tier"],
                  "period": entry["period"], "delivery": entry["delivery"]}
    return {"starting_price": starting_price, "currency": currency, "entry_spec": entry_spec,
            "entry_price": entry["lowest_price"], "entry_shop_count": entry["shop_count"]}


def tool_summary(s, key, members, page=1, page_size=50, include_specs=True):
    ids = [m.id for m in members]
    names = {m.id: m.name for m in members}
    rows, specs = product_spec_data(s, ids, names)
    price_fields = product_price_fields(specs)
    status, sold = None, []
    if not rows or price_fields["starting_price"] is None:
        old = s.scalars(select(Listing).where(Listing.product_id.in_(ids), Listing.active.is_(False))).all()
        old_shops = {shop.id: shop for shop in s.scalars(select(Shop).where(Shop.id.in_({r.shop_id for r in old}))) } if old else {}
        for r in old:
            r.product_name = names[r.product_id]
            r.shop_name = _store_display_name(old_shops.get(r.shop_id))
            r.shop_key = old_shops.get(r.shop_id).shop_key if old_shops.get(r.shop_id) else ""
        sold = [public_spec(g) for g in spec_groups(old)][:2]
        status = "暂无可信起价，报价需核验" if rows else "暂无报价"
        if sold:
            status = "已采到标价，当前商品已售罄"
    n_selling = len({r.shop_id for r in rows})
    n_shops = s.scalar(select(func.count(func.distinct(ShopProduct.shop_id)))
                       .where(ShopProduct.product_id.in_(ids))) or 0
    total = len(specs)
    total_pages = (total + page_size - 1) // page_size
    spec_page = [public_spec(g) for g in specs[(page - 1) * page_size:page * page_size]] if include_specs else []
    return {"name": key, "members": [m.name for m in members], "n_shops": n_shops,
            "n_selling": n_selling, "n_offers": sum(g["listing_count"] for g in specs),
            "price": price_fields["starting_price"], "starting_price": price_fields["starting_price"],
            "currency": price_fields["currency"], "spec": price_fields["entry_spec"]["label"] if price_fields["entry_spec"] else None,
            "entry_spec": price_fields["entry_spec"], "entry_price": price_fields["entry_price"],
            "entry_shop_count": price_fields["entry_shop_count"],
            "n_specs": total, "total": total, "page": page, "page_size": page_size,
            "total_pages": total_pages, "status": status, "sold_out": sold,
            "specs": spec_page}


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
            tools = [tool_summary(s, k, m, include_specs=False) for k, m in groups_of(s).items()]
            types = s.execute(select(Shop.platform_type, func.count()).group_by(Shop.platform_type)
                              .order_by(func.count().desc())).all()
            return {"updated_at": last_update(s), "total_shops": s.scalar(select(func.count(Shop.id))),
                    "tools": tools, "types": [{"name": n, "count": c} for n, c in types]}
    return ctx.seal(cached("home", 60, build))


@router.get("/tools/{name}")
def tool(name: str, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
         ctx: Ctx = Depends(secure_ctx)):
    with SessionLocal() as s:
        members = groups_of(s).get(name)
        if not members:
            raise HTTPException(404, "商品不存在")
        out = tool_summary(s, name, members, page=page, page_size=page_size)
        # Only publish the reviewed, user-facing status. Internal research notes
        # and source URLs in PRODUCT_NOTES.reason/urls stay server-side.
        public_note = PRODUCT_NOTES.get(name, {}).get("status")
        if public_note:
            out["note"] = public_note
        out["updated_at"] = last_update(s)
        return ctx.seal(out)


@router.get("/catalog/{name}/specs")
def catalog_specs(name: str, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
                  ctx: Ctx = Depends(secure_ctx)):
    """只读商品规格目录：分页展示起价、报价数及在售店铺数。"""
    with SessionLocal() as s:
        members = groups_of(s).get(name)
        if not members:
            raise HTTPException(404, "商品不存在")
        ids = [m.id for m in members]
        _, groups = product_spec_data(s, ids, {m.id: m.name for m in members})
        price_fields = product_price_fields(groups)
        total = len(groups)
        total_pages = (total + page_size - 1) // page_size
        start = (page - 1) * page_size
        items = [public_spec(g) for g in groups[start:start + page_size]]
        return ctx.seal({"product": name, "updated_at": last_update(s), "n_specs": total,
                         "page": page, "page_size": page_size, "total_pages": total_pages,
                         "starting_price": price_fields["starting_price"], "currency": price_fields["currency"],
                         "entry_spec": price_fields["entry_spec"], "entry_price": price_fields["entry_price"],
                         "entry_shop_count": price_fields["entry_shop_count"],
                         "specs": items})


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
            if spec_group_id(r) != (pid, skey, cur):
                continue
            ident = (r.shop_id, r.url, r.title, r.currency)
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
        low = g["lowest_price"]
        items = [{"id": r.id, "shop": {"id": r.shop_id, "name": shops[r.shop_id].name, "domain": shops[r.shop_id].domain,
                                       "type": shops[r.shop_id].platform_type},
                  "title": r.title, "price": num(r.price), "currency": r.currency, "stock": r.stock,
                  "observed_at": iso(r.observed_at), "lowest": not r.price_anomaly and low is not None and float(r.price) == low,
                  "price_anomaly": bool(r.price_anomaly), "price_anomaly_reason": r.price_anomaly_reason,
                  "verification_source": (r.spec or {}).get("verification_source"),
                  "go": "/go/" + go_token(r.shop_id, r.id)}
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
            escape_char = "\\"
            escaped_q = q.replace(escape_char, escape_char + escape_char).replace("%", escape_char + "%").replace("_", escape_char + "_")
            like = f"%{escaped_q}%"
            psub = select(ShopProduct.shop_id).join(Product, Product.id == ShopProduct.product_id).where(func.lower(Product.name).like(like, escape=escape_char))
            lsub = select(Listing.shop_id).where(func.lower(Listing.title).like(like, escape=escape_char))
            stmt = stmt.where(or_(func.lower(Shop.name).like(like, escape=escape_char), Shop.domain == q,
                                  func.lower(Shop.platform_type).like(like, escape=escape_char),
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


def public_crawl_status(result):
    """Map internal collector diagnostics to a small, non-sensitive public enum."""
    if not result:
        return "未知"
    if result.get("retry_result") == "需验证，暂无报价":
        return "需验证"
    status = str(result.get("status") or "").lower()
    reason = str(result.get("reason") or "").lower()
    if status == "skipped": return "已跳过"
    if status == "success": return "采集成功"
    if status == "empty": return "无报价"
    if re.search(r"captcha|cloudflare|验证码|人机|访问验证|滑块", reason): return "需验证"
    if re.search(r"登录|登陆|login|401|403|unauthorized", reason): return "需要登录"
    if re.search(r"关闭|打烊|不存在|404", reason): return "店铺关闭"
    if re.search(r"timeout|timed out|连接|dns|502|503|504|connection", reason): return "连接失败"
    if status == "failed": return "结构未适配"
    return "未知"


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
                         "crawl_status": public_crawl_status(crawl.result if crawl else None),
                         "updated_at": iso(shop.last_seen_at)})
