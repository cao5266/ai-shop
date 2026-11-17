"""把一批采集结果 JSON 导入数据库（幂等 upsert）。

格式与 /workspace/ai_shops/shops.json 相同：{generated_at, scope, shops:[...]}。
每次调用都会新建一条 crawl_runs 记录。
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import re
from collections import Counter
from urllib.parse import urlparse

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from .models import (CrawlRun, Price, PriceHistory, Product, PromoterAccount, RiskFlag, Shop,
                     ShopProduct, ShopSnapshot, XPost, utcnow, Listing, ListingPriceHistory, ShopCrawlResult)

PRODUCT_ORDER = ["ChatGPT Plus", "ChatGPT Pro", "Claude Pro", "Claude Max", "Grok Plus", "Grok Premium",
                 "Grok Super", "Grok Ultra", "Cursor", "Muse", "Gemini", "Perplexity", "Copilot",
                  "X会员", "Telegram会员", "ChatGPT Go", "Codex", "Midjourney", "Grok"]

# 风险标记归类：(正则, code, 短标签, 严重度)。严重度「高」的任意一条 → 店铺风险等级为高。
FLAG_RULES = [
    (r"成品号|共享|来源不明", "shared_account", "成品号/来源不明账号", "高"),
    (r"不质保|不管封号", "no_warranty", "不质保", "高"),
    (r"矩阵|群发|多个账号|2025年后注册", "matrix", "群发推广", "高"),
    (r"代充|直充", "topup", "代充/直充", "中"),
    (r"未能稳定打开|404|JS壳|被拦截|网关错误", "unstable", "无法稳定打开", "提示"),
]


def classify_flag(text: str) -> tuple[str, str, str]:
    for rx, code, label, sev in FLAG_RULES:
        if re.search(rx, text):
            return code, label, sev
    return "other", "其他提示", "提示"


def map_product(label: str) -> str | None:
    """把价格标签映射到标准商品名；含糊的（如单写「Claude」「ChatGPT」）不猜，返回 None。"""
    t = label.lower().replace(" ", "")
    if t.startswith("muse"):
        return "Muse"
    if t.startswith("telegram会员"):
        return "Telegram会员"
    if t.startswith(("gptpro", "chatgptpro")):
        return "ChatGPT Pro"
    if t.startswith(("gpt", "chatgpt")) and "plus" in t:
        return "ChatGPT Plus"
    if t.startswith("claudepro"):
        return "Claude Pro"
    if t.startswith("claudemax"):
        return "Claude Max"
    m = re.match(r"grok(plus|premium|super|ultra)", t)
    if m:
        return "Grok " + m.group(1).capitalize()
    for k in ("cursor", "gemini", "perplexity", "copilot"):
        if t.startswith(k):
            return k.capitalize()
    return None


def split_list(s) -> list[str]:
    if isinstance(s, list):
        return [x for x in s if x]
    return [x.strip() for x in (s or "").split("|") if x.strip()]


def parse_post_prices(s) -> list[tuple[str, float]]:
    out = []
    for item in split_list(s):
        m = re.match(r"^(.*?)\s*(\d+(?:\.\d+)?)\s*元$", item)
        if m:
            out.append((m.group(1).strip(), float(m.group(2))))
    return out


def parse_page_prices(s) -> list[float]:
    out = []
    for item in split_list(s):
        m = re.search(r"(\d+(?:\.\d+)?)", item.replace(",", ""))
        if m and float(m.group(1)) > 0:
            out.append(float(m.group(1)))
    return out


def parse_promoters(s) -> dict[str, int]:
    out = {}
    for m in re.finditer(r"([^,()]+)\((\d+)\)", s or ""):
        out[m.group(1).strip()] = int(m.group(2))
    return out


def author_of(url: str | None) -> str | None:
    if not url:
        return None
    parts = [p for p in urlparse(url).path.split("/") if p]
    return parts[0] if parts and parts[0] != "i" else None


def _aware(d):
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def import_data(session: Session, data: dict, source_file: str | None = None,
                file_sha256: str | None = None, force: bool = False) -> CrawlRun:
    shops_in = data.get("shops")
    if not isinstance(shops_in, list):
        raise ValueError("JSON 缺少 shops 数组")
    if file_sha256 and not force:
        dup = session.scalar(select(CrawlRun).where(CrawlRun.file_sha256 == file_sha256,
                                                    CrawlRun.status == "success"))
        if dup:
            raise ValueError(f"该文件已在 crawl_run #{dup.id} 导入过（内容相同）。如需重复导入请加 --force")

    now = utcnow()
    run = CrawlRun(started_at=now, status="running", source_file=source_file, file_sha256=file_sha256,
                   source_generated_at=data.get("generated_at"), scope=data.get("scope"),
                   shops_in_batch=len(shops_in))
    session.add(run)
    session.flush()

    products = {p.name: p for p in session.scalars(select(Product))}

    def get_product(name: str) -> Product:
        p = products.get(name)
        if not p:
            order = PRODUCT_ORDER.index(name) if name in PRODUCT_ORDER else 999
            p = Product(name=name, family="Grok" if name.startswith("Grok") else None, sort_order=order)
            session.add(p)
            session.flush()
            products[name] = p
        return p

    try:
        for s in shops_in:
            _import_shop(session, run, s, now, get_product)
        run.status = "success"
        run.finished_at = utcnow()
        session.commit()
    except Exception as e:
        session.rollback()
        # 失败也留一条记录，方便排查
        failed = CrawlRun(started_at=now, finished_at=utcnow(), status="failed", source_file=source_file,
                          file_sha256=None, source_generated_at=data.get("generated_at"),
                          shops_in_batch=len(shops_in), error=f"{type(e).__name__}: {e}"[:2000])
        session.add(failed)
        session.commit()
        raise
    return run


def _import_shop(session, run, s, now, get_product):
    key = s["shop_key"]
    shop = session.scalar(select(Shop).where(Shop.shop_key == key))
    fields = dict(
        name=(s.get("shop_name") or key)[:400], domain=s.get("domain") or "",
        platform_type=s.get("platform_type") or "未分类", primary_url=s.get("primary_url") or "",
        final_url=s.get("final_url") or None, all_urls=s.get("all_urls") or [],
        http_code=s.get("http_code") or None, page_status=s.get("page_status") or None,
        page_readable=bool(s.get("page_content_readable")), page_products=s.get("page_products") or None,
        entity_titles=s.get("entity_titles") or None, n_accounts=int(s.get("n_accounts") or 0),
        example_post_url=s.get("example_post_url") or None, notes=s.get("notes") or None,
    )
    if shop is None:
        shop = Shop(shop_key=key, first_seen_at=now, first_seen_run_id=run.id, last_seen_at=now,
                    last_seen_run_id=run.id, n_posts=0, **fields)
        session.add(shop)
        session.flush()
        run.shops_new += 1
    else:
        for k, v in fields.items():
            setattr(shop, k, v)
        shop.last_seen_at = now
        shop.last_seen_run_id = run.id
        run.shops_updated += 1

    # --- 商品关联
    existing_sp = {sp.product_id: sp for sp in session.scalars(select(ShopProduct).where(ShopProduct.shop_id == shop.id))}
    for pname in split_list(s.get("products")):
        p = get_product(pname)
        sp = existing_sp.get(p.id)
        if sp:
            sp.last_seen_at = now
        else:
            session.add(ShopProduct(shop_id=shop.id, product_id=p.id, first_seen_at=now, last_seen_at=now))

    # --- 价格（upsert + 变动历史）
    if "listings" in s:
        _import_listings(session, run, shop, s, now, get_product)
    quotes: list[tuple[str, str, str, float, str | None]] = []  # source,key,label,amount,product
    seen_labels = Counter()
    for label, amount in parse_post_prices(s.get("prices_from_posts")):
        seen_labels[label] += 1
        k = label if seen_labels[label] == 1 else f"{label}#{seen_labels[label]}"
        quotes.append(("post", k, label, amount, map_product(label)))
    for amount in parse_page_prices(s.get("prices_from_page")):
        k = f"{amount:g}"
        if ("page", k) in {(q[0], q[1]) for q in quotes}:
            continue
        quotes.append(("page", k, "", amount, None))
    existing = {(p.source, p.price_key): p for p in session.scalars(select(Price).where(Price.shop_id == shop.id))}
    for source, k, label, amount, pname in quotes:
        pid = get_product(pname).id if pname else None
        row = existing.get((source, k))
        if row is None:
            row = Price(shop_id=shop.id, product_id=pid, source=source, price_key=k, label=label,
                        amount=amount, first_seen_at=now, last_seen_at=now, last_run_id=run.id)
            session.add(row)
            session.flush()
            session.add(PriceHistory(price_id=row.id, amount=amount, observed_at=now, crawl_run_id=run.id))
            run.prices_new += 1
        else:
            if float(row.amount) != amount:
                row.amount = amount
                session.add(PriceHistory(price_id=row.id, amount=amount, observed_at=now, crawl_run_id=run.id))
                run.prices_changed += 1
            row.product_id = pid
            row.label = label
            row.last_seen_at = now
            row.last_run_id = run.id

    # --- 风险标记（本批未再出现的置为 inactive）
    details = [d.strip() for d in (s.get("risk_flags") or "").split("；") if d.strip()]
    flags = {f.detail: f for f in session.scalars(select(RiskFlag).where(RiskFlag.shop_id == shop.id))}
    for d in details:
        code, label, sev = classify_flag(d)
        f = flags.get(d)
        if f:
            f.active, f.last_seen_at, f.code, f.label, f.severity = True, now, code, label, sev
        else:
            session.add(RiskFlag(shop_id=shop.id, code=code, label=label, severity=sev, detail=d,
                                 active=True, first_seen_at=now, last_seen_at=now))
    for d, f in flags.items():
        if d not in details:
            f.active = False
    shop.risk_level = "高" if any(classify_flag(d)[2] == "高" for d in details) else "中"
    # 本站不认定任何店铺为官方渠道，因此没有「低」。

    # --- X 帖：ID、示例帖、抽样文案
    now_posts = {x.uid: x for x in session.scalars(select(XPost).where(XPost.shop_id == shop.id))}

    def upsert_post(uid, **kw):
        x = now_posts.get(uid)
        if x:
            x.last_seen_at, x.last_run_id = now, run.id
            for k, v in kw.items():
                if v and (k == "kind" and v != "ref" or k != "kind" and not getattr(x, k)):
                    setattr(x, k, v)
        else:
            x = XPost(shop_id=shop.id, uid=uid, first_seen_at=now, last_seen_at=now, last_run_id=run.id,
                      post_id=kw.get("post_id"), url=kw.get("url"), author=kw.get("author"),
                      text=kw.get("text"), kind=kw.get("kind", "ref"))
            session.add(x)
            now_posts[uid] = x
            run.posts_new += 1

    for pid in s.get("post_ids") or []:
        upsert_post(str(pid), post_id=str(pid), url=f"https://x.com/i/status/{pid}", kind="ref")
    ex = s.get("example_post_url")
    if ex:
        m = re.search(r"/status/(\d+)", ex)
        if m:
            upsert_post(m.group(1), post_id=m.group(1), url=ex, author=author_of(ex), kind="example")
    for t in s.get("sample_post_texts") or []:
        h = hashlib.sha1(t.encode()).hexdigest()[:24]
        upsert_post("txt:" + h, text=t, kind="sample")
    session.flush()
    n_ids = sum(1 for x in now_posts.values() if x.post_id)
    shop.n_posts = max(int(s.get("n_posts") or 0), n_ids)

    # --- 推广账号
    counts = parse_promoters(s.get("promoter_accounts"))
    details_acc = {a["username"]: a for a in (s.get("account_details") or []) if a.get("username")}
    acc_rows = {a.username: a for a in session.scalars(select(PromoterAccount).where(PromoterAccount.shop_id == shop.id))}
    for u in set(counts) | set(details_acc):
        d = details_acc.get(u, {})
        a = acc_rows.get(u)
        vals = dict(post_count=counts.get(u, d.get("posts_in_sample")), created_year=d.get("year"),
                    followers=d.get("followers"))
        if a:
            for k, v in vals.items():
                if v is not None:
                    setattr(a, k, v)
            a.last_seen_at = now
        else:
            session.add(PromoterAccount(shop_id=shop.id, username=u, first_seen_at=now, last_seen_at=now, **vals))

    # --- 最低价：只取帖文里带标签的报价。页面上的金额没有商品标注（常含 ¥0.13 之类的杂项），不参与排序。
    session.flush()
    post_p = [float(a) for (a,) in session.execute(select(Price.amount).where(
        Price.shop_id == shop.id, Price.source == "post", Price.last_run_id == run.id))]
    shop.min_price = None
    page_p = [float(a) for (a,) in session.execute(select(Listing.price).where(
        Listing.shop_id == shop.id, Listing.active.is_(True), Listing.currency == "CNY"))]
    if page_p: shop.min_price = min(page_p)

    session.add(ShopSnapshot(shop_id=shop.id, crawl_run_id=run.id, n_posts=shop.n_posts,
                             n_accounts=shop.n_accounts, http_code=shop.http_code, risk_level=shop.risk_level))


def _import_listings(session, run, shop, data, now, get_product):
    from decimal import Decimal
    from urllib.parse import urlsplit
    existing = {r.listing_key: r for r in session.scalars(select(Listing).where(Listing.shop_id == shop.id))}
    crawl = data.get("crawl", {})
    session.add(ShopCrawlResult(shop_id=shop.id, crawl_run_id=run.id, result=crawl))
    if crawl.get("status") in ("success", "empty") and crawl.get("complete"):
        for row in existing.values(): row.active = False
    linked = set(session.scalars(select(ShopProduct.product_id).where(ShopProduct.shop_id == shop.id)))
    for item in data.get("listings", []):
        price = Decimal(str(item["price"]))
        if not price.is_finite() or price <= 0: raise ValueError("商品价格必须是正数")
        if urlsplit(item["url"]).scheme not in ("https", "http"): raise ValueError("商品链接协议无效")
        pname = item.get("product")
        pid = get_product(pname).id if pname else None
        if pid and pid not in linked:
            session.add(ShopProduct(shop_id=shop.id, product_id=pid, first_seen_at=now, last_seen_at=now))
            linked.add(pid)
        observed = dt.datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00"))
        row = existing.get(item["listing_key"])
        changed = row is None or Decimal(str(row.price)) != price or row.currency != item.get("currency", "CNY")
        stored_spec = dict(item["spec"])
        for field in ("verification_source", "price_anomaly", "price_anomaly_reason",
                      "quality_action", "quality_flags", "quality_review_required",
                      "quality_review_reason", "comparison_exclusion", "mirror_of",
                      "period_default", "period_na", "codex_source_tier",
                      "codex_mapped_product", "codex_duplicate_of", "catalog_title"):
            if field in item:
                stored_spec[field] = item[field]
        vals = dict(product_id=pid, title=item["title"], price=price, currency=item.get("currency", "CNY"),
                    url=item["url"], category=item.get("category"), image=item.get("image") if isinstance(item.get("image"), str) else None,
                    spec=stored_spec, spec_key=item["spec"]["key"], stock=str(item["stock"]) if item.get("stock") is not None else None,
                    sales=str(item["sales"]) if item.get("sales") is not None else None, risk=item.get("risk", "未判定"),
                    source_url=item.get("source_url") or item["url"], active=item.get("stock_status") != "out" and item.get("stock") != 0,
                    observed_at=observed, last_run_id=run.id)
        if row is None:
            row = Listing(shop_id=shop.id, listing_key=item["listing_key"], **vals)
            session.add(row); session.flush(); run.prices_new += 1
        else:
            for k, v in vals.items(): setattr(row, k, v)
            if changed: run.prices_changed += 1
        if changed:
            session.add(ListingPriceHistory(listing_id=row.id, price=price, currency=row.currency,
                                            observed_at=observed, crawl_run_id=run.id))


def import_file(session: Session, path: str, force: bool = False) -> CrawlRun:
    raw = open(path, "rb").read()
    data = json.loads(raw.decode("utf-8-sig"))
    return import_data(session, data, source_file=path, file_sha256=hashlib.sha256(raw).hexdigest(), force=force)
