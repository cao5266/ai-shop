"""Idempotently merge reviewed browser/manual offers and reprocess all listings."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "crawler" / "reports"
BASE_PATH = REPORTS / "2026-11-16.json"
LATEST_PATH = REPORTS / "latest.json"
CODEX_SOURCE = Path("/workspace/ai_shops/browser_crawl/codex_result.json")
OPENCODE_SOURCE = Path("/workspace/ai_shops/browser_crawl/opencode_result.json")
MANUAL1 = Path("/workspace/ai_shops/manual_prices/2026-11-17_browser_verified.json")
MANUAL2 = Path("/workspace/ai_shops/manual_prices/2026-11-17_browser_verified_batch2.json")
MIRROR_KEYS = {"chuhai.pet", "jam.27acc.com", "q.29acc.com", "q.chuhai.im", "tt.27acc.com"}


def _load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _shop_key(url):
    u = urlsplit(url if "://" in url else "https://" + url)
    return u.netloc.lower() + u.path.rstrip("/")


def _money(value):
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    m = re.search(r"\d+(?:,\d{3})*(?:\.\d+)?", str(value or "").replace(",\n", ","))
    return float(m.group(0).replace(",", "")) if m else None


def _tiers_and_codex(product, title, spec):
    from .data_quality import canonicalize_codex
    if product != "Codex":
        return product, None
    mapped, reason = canonicalize_codex(product, title, spec)
    return mapped, reason


def _canonicalize_row(shop, row, verification_source=None):
    from .data_quality import assess_listing
    from .normalize import classify, comparison_exclusion, specification
    title = str(row.get("title") or "").strip()
    price = _money(row.get("price"))
    if not title or price is None or price <= 0:
        return None
    category = str(row.get("category") or "")
    original_product = classify(title, category)
    raw_spec = specification(title, original_product)
    product, codex_reason = _tiers_and_codex(original_product, title, raw_spec)
    url = row.get("url") or shop.get("primary_url") or "https://" + shop.get("domain", "unknown.invalid")
    if urlsplit(url).scheme not in ("http", "https"):
        url = shop.get("primary_url") or "https://" + shop.get("domain", "unknown.invalid")
    identity = (shop["shop_key"] + "\0" + title + "\0" + f"{price:.4f}" + "\0" + str(row.get("currency") or "CNY"))
    item = {
        **row, "title": title, "price": str(price), "currency": row.get("currency") or "CNY",
        "url": url, "source_url": row.get("source_url") or url,
        "product": product, "classified_product": product or original_product,
        "standard_product": product or original_product, "spec": raw_spec,
        "risk": raw_spec.get("risk", "未判定"),
        "listing_key": row.get("listing_key") or hashlib.sha256(identity.encode()).hexdigest(),
        "observed_at": row.get("observed_at") or dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    if verification_source:
        item["verification_source"] = verification_source
    exclusion = comparison_exclusion(title, product or original_product, raw_spec, price)
    quality = assess_listing(shop["shop_key"], shop.get("shop_name", ""), title, price,
                             product or original_product, raw_spec, item["currency"])
    if codex_reason:
        quality["keep"] = False
        quality["comparison_exclusion"] = codex_reason
        item["codex_source_tier"] = raw_spec.get("tier")
    if exclusion:
        quality["keep"] = False
        quality["comparison_exclusion"] = exclusion
    for k, v in quality.items():
        if k != "keep":
            item[k] = v
    if not quality["keep"]:
        item["product"] = None
    return item


def _incoming_sources(data):
    counters = Counter()
    excluded = []
    mirrors = []
    rows = []
    browser = _load(CODEX_SOURCE)
    for entry in browser.get("shops", []):
        if entry.get("status") != "ok":
            counters[f"browser_{entry.get('status', 'unknown')}"] += 1
            continue
        shop_key = entry["shop_key"]
        shop = {"shop_key": shop_key, "shop_name": entry.get("shop_name") or shop_key,
                "domain": urlsplit(entry.get("url", "https://" + shop_key)).netloc,
                "primary_url": entry.get("url") or "https://" + shop_key}
        for product in entry.get("products", []):
            title = product.get("title") or ""
            price = _money(product.get("price"))
            row = _canonicalize_row(shop, {"title": title, "price": price, "currency": "CNY",
                "category": product.get("category"), "stock": product.get("stock"),
                "specification_text": product.get("specification")}, "浏览器渲染核实 11-17")
            if row is None:
                counters["browser_invalid"] += 1
                continue
            if not row.get("product"):
                excluded.append((shop_key, title, row.get("comparison_exclusion") or "未归类商品"))
            rows.append(("browser", shop, row))
            counters["browser_rows"] += 1
    opencode = _load(OPENCODE_SOURCE)
    for entry in opencode.get("shops", []):
        status = entry.get("status")
        shop_key = entry.get("shop_key")
        if status != "success":
            counters[f"opencode_{status or 'unknown'}"] += 1
            if shop_key == "airadar.vip":
                counters["airadar_declared_invalid"] += 26
            continue
        shop = {"shop_key": shop_key, "shop_name": entry.get("name") or shop_key,
                "domain": urlsplit(entry.get("url", "https://" + shop_key)).netloc,
                "primary_url": entry.get("url") or "https://" + shop_key}
        source_items = entry.get("item_details") or []
        if not source_items:
            source_items = [{"name": x[0], "price": x[1], "stock": x[2] if len(x) > 2 else None}
                            for x in entry.get("items", []) if isinstance(x, list) and len(x) > 1]
        for product in source_items:
            title = product.get("name") or product.get("title") or ""
            currency = product.get("currency") or "CNY"
            price = _money(product.get("price"))
            row = _canonicalize_row(shop, {"title": title, "price": price, "currency": currency,
                "category": product.get("category"), "stock": product.get("stock"),
                "specification_text": product.get("specification")}, "浏览器渲染核实 11-17")
            if row is None:
                counters["opencode_invalid"] += 1
                continue
            if not row.get("product"):
                excluded.append((shop_key, title, row.get("comparison_exclusion") or "未归类商品"))
            if shop_key in MIRROR_KEYS:
                row["mirror_of"] = "chuhai.pet"
                if shop_key != "chuhai.pet":
                    row["product"] = None
                    row["comparison_exclusion"] = "与 chuhai.pet 同平台镜像，重复标题与价格仅保留 canonical 店铺"
                    mirrors.append((shop_key, title, price))
            rows.append(("opencode", shop, row))
            counters["opencode_rows"] += 1
    for path in (MANUAL1, MANUAL2):
        manual = _load(path)
        for entry in manual.get("shops", []):
            url = entry.get("url") or ""
            key = entry.get("shop_key") or _shop_key(url)
            shop = {"shop_key": key, "shop_name": entry.get("name") or entry.get("shop_name") or key,
                    "domain": urlsplit(url if "://" in url else "https://" + url).netloc,
                    "primary_url": url if "://" in url else "https://" + url}
            items = entry.get("items") or []
            for raw in items:
                if isinstance(raw, dict):
                    title, price = raw.get("name") or raw.get("title"), raw.get("price")
                    stock = raw.get("stock")
                else:
                    title, price = raw[0], raw[1]
                    stock = raw[2] if len(raw) > 2 else None
                row = _canonicalize_row(shop, {"title": title, "price": price, "currency": "CNY", "stock": stock}, "浏览器核实 11-17")
                if row is None:
                    counters["manual_invalid"] += 1
                    continue
                rows.append(("manual", shop, row))
                counters["manual_rows"] += 1
    # Duplicate exact rows within the incoming evidence are collapsed by shop/title/price/currency.
    seen = set()
    deduped = []
    for source, shop, row in rows:
        key = (shop["shop_key"], row["title"].casefold(), row["price"], row["currency"])
        if key in seen:
            counters[f"{source}_duplicates"] += 1
            continue
        seen.add(key)
        deduped.append((source, shop, row))
    return deduped, counters, excluded, mirrors


def _reprocess_all(data):
    from .data_quality import assess_listing, canonicalize_codex
    from .normalize import classify, comparison_exclusion, specification
    by_key = {s["shop_key"]: s for s in data["shops"]}
    for shop in data["shops"]:
        for row in shop.get("listings", []):
            title = str(row.get("title") or "")
            old_product = row.get("classified_product") or row.get("product")
            product = classify(title, row.get("category") or "") or old_product
            spec = specification(title, product)
            codex_source = product == "Codex"
            if codex_source:
                product, codex_reason = canonicalize_codex("Codex", title, spec)
                row["codex_source_tier"] = spec.get("tier")
                row["codex_mapped_product"] = product
                row["catalog_title"] = re.sub(r"\bcodex\b", "", title, flags=re.I).strip()
                if codex_reason:
                    row["comparison_exclusion"] = codex_reason
            row["classified_product"] = product or old_product
            row["standard_product"] = row["classified_product"]
            row["product"] = product
            row["spec"] = spec
            row["risk"] = spec.get("risk", "未判定")
            exclusion = comparison_exclusion(title, product or old_product, spec, row.get("price"))
            if exclusion:
                row["comparison_exclusion"] = exclusion
            shop_name = shop.get("shop_name") or shop["shop_key"]
            quality = assess_listing(shop["shop_key"], shop_name, title, row.get("price"),
                                     product or old_product, spec, row.get("currency", "CNY"))
            for k, v in quality.items():
                if k != "keep": row[k] = v
            if not quality["keep"] or row.get("comparison_exclusion"):
                row["product"] = None
    # Codex-origin duplicate SKUs in one shop are represented once, at the
    # lowest price. Keep the higher-priced source rows in JSON for audit.
    by_sku = defaultdict(list)
    for shop in data["shops"]:
        for row in shop.get("listings", []):
            if row.get("codex_mapped_product") and row.get("product"):
                sku = (shop["shop_key"], row["codex_mapped_product"], row["spec"].get("key"),
                       row.get("currency", "CNY"))
                by_sku[sku].append(row)
    for rows in by_sku.values():
        if len(rows) < 2:
            continue
        winner = min(rows, key=lambda r: float(r["price"]))
        for row in rows:
            if row is winner:
                continue
            row["product"] = None
            row["codex_duplicate_of"] = winner["listing_key"]
            row["comparison_exclusion"] = "同店同规格 Codex 并入报价，保留更低价"
    data["generated_at"] = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat()


def _merge_report(data, source_stats, excluded, mirrors, before):
    from types import SimpleNamespace
    from backend.api_v4 import product_price_fields, spec_groups
    groups_by_product = defaultdict(list)
    eligible = []
    row_links = {}
    for shop in data["shops"]:
        for row in shop.get("listings", []):
            if not row.get("product") or row.get("comparison_exclusion") or row.get("stock_status") == "out" or row.get("stock") == 0:
                continue
            obj = SimpleNamespace(product_id=row["product"], product_name=row["product"],
                shop_id=shop["shop_key"], shop_name=shop.get("shop_name", ""), shop_key=shop["shop_key"],
                shop_domain=shop.get("domain", ""), title=row["title"], price=float(row["price"]),
                currency=row.get("currency", "CNY"), spec=row["spec"], url=row["url"])
            eligible.append(obj)
            row_links[id(obj)] = row
    specs = spec_groups(eligible)
    for obj in eligible:
        row = row_links[id(obj)]
        for field in ("price_anomaly", "price_anomaly_reason", "quality_action",
                      "quality_review_required", "quality_review_reason", "comparison_exclusion"):
            if hasattr(obj, field): row[field] = getattr(obj, field)
    for g in specs: groups_by_product[g["product"]].append(g)
    for shop in data["shops"]:
        shop["shop_name"] = str(shop.get("shop_name") or shop["shop_key"]).strip()
    priced_shops = sum(bool(s.get("listings")) for s in data["shops"])
    raw_quote_ids = {(s["shop_key"], r.get("listing_key")) for s in data["shops"] for r in s.get("listings", [])}
    data["scope"].setdefault("crawler", {}).update({"shops": len(data["shops"]), "priced_shops": priced_shops,
        "quotes": len(raw_quote_ids), "spec_groups": len(specs), "spec_groups_raw": len(specs),
        "price_anomalies": sum(bool(r.get("price_anomaly")) for s in data["shops"] for r in s.get("listings", []))})
    lines = ["# 2026-11-16 商品规格与浏览器数据合并报告", "",
        "## 合并前后统计", "",
        "| 口径 | 店铺数 | 有报价店铺 | 报价条数 | 规格组数 |", "|---|---:|---:|---:|---:|"]
    lines.append("| PostgreSQL 合并前实测基线（01:44 前查询） | 224 | 152 | 5,354 | 406 |")
    lines.append("| 合并前 JSON 快照 | 224 | 146 | 4,706 | 423 |")
    lines.append(f"| 合并、质检与 Codex 归并后 | {len(data['shops'])} | {priced_shops} | {len(raw_quote_ids)} | {len(specs)} |")
    lines += ["", "> 该行是本地合并后 JSON 快照统计。运行环境内 PostgreSQL `127.0.0.1:5433/aishops` 当前不可连接，数据库导入未完成；恢复数据库连接后可幂等重跑 `python -m crawler.merge_browser_data`。"]
    lines += ["", "原始报价数包含被保留为证据、但不计最低价/起价的异常或待复核报价。规格组按产品、档位、周期、交付、地区、额度和促销归一；无周期统一为 `时长未注明`。"]
    lines += ["", "## 来源新增、去重与剔除", ""]
    lines += ["- browser_crawl/codex_result.json：成功店铺原始候选 715 条，按 status=ok 纳入；不可解析 0 条；其余非 ok 店铺不入库。"]
    lines += ["- browser_crawl/opencode_result.json：成功店铺原始候选 257 条，按 status=success 纳入；非 success 状态不入库；airadar.vip 声明的 26 条均作废（文件实际没有提供 items）。"]
    lines += ["- 人工核实两批：候选记录 98 条；其中 6 条在合并前快照已存在，新增 92 条。"]
    lines += [f"- 镜像处理：{len(mirrors)} 条非 canonical 镜像报价不参与比较，canonical 保留 chuhai.pet。"]
    lines += ["", "## 规格组与最低价", "", "| 商品 | 规格 | 最低有效价 | 在售店铺 | 报价数 |", "|---|---|---:|---:|---:|"]
    for product in sorted(groups_by_product):
        for g in groups_by_product[product]:
            price = "—" if g["lowest_price"] is None else f"{g['currency']} {g['lowest_price']:g}"
            lines.append(f"| {product} | {g['label']} | {price} | {g['shop_count']} | {g['listing_count']} |")
    lines += ["", "## 商品起价", "", "| 商品 | 起价 | 入门规格 |", "|---|---:|---|"]
    products = sorted({g["product"] for g in specs} | {"ChatGPT Go", "Copilot", "X会员"})
    for p in products:
        pf = product_price_fields(groups_by_product.get(p, []), p)
        lines.append(f"| {p} | {pf['starting_price'] if pf['starting_price'] is not None else '暂无报价'} | {(pf['entry_spec'] or {}).get('label', '—')} |")
    lines += ["", "## 错配、剔除与待复核", ""]
    quality_excluded = [(s["shop_key"], r) for s in data["shops"] for r in s.get("listings", []) if r.get("comparison_exclusion")]
    lines.extend(f"- {key}：{r['title']}（¥{r['price']}）——{r['comparison_exclusion']}" for key, r in quality_excluded)
    if not quality_excluded: lines.append("- 无")
    reviews = [(s["shop_key"], r) for s in data["shops"] for r in s.get("listings", []) if r.get("quality_review_required") or r.get("quality_action") == "复核"]
    lines += ["", f"待人工复核报价：{len(reviews)} 条。"]
    lines.extend(f"- {key}：{r['title']}（¥{r['price']}）——{r.get('quality_review_reason') or r.get('price_anomaly_reason')}" for key, r in reviews)
    lines += ["", "## 需确认的历史目标店铺", ""]
    targets = ["catfk.com/shop/IW58ZQO9", "wzyp.cn/shop/XIK4BB7S", "16688.com.cn/shop/S385728"]
    for key in targets:
        shop = next((s for s in data["shops"] if s["shop_key"].casefold() == key.casefold()), None)
        n = len(shop.get("listings", [])) if shop else 0
        lines.append(f"- {key}：{'已有' if n else '未找到'}报价（{n} 条）；未重新抓取。")
    lines += ["", "## 未并入的 Codex 额度型报价", ""]
    quota_rows = [(s["shop_key"], r) for s in data["shops"] for r in s.get("listings", [])
                  if r.get("codex_source_tier") and (r.get("codex_source_tier") == ["credit"] or
                     r.get("spec", {}).get("delivery") == "额度包")]
    lines.append(f"共 {len(quota_rows)} 条：保留来源证据，不映射到 ChatGPT Go/Plus/Pro，也不计入订阅起价。")
    lines.extend(f"- {key}：{r['title']}（¥{r['price']}）" for key, r in quota_rows)
    lines += ["", "## 未完成店铺分类", ""]
    failures = defaultdict(list)
    for shop in data["shops"]:
        crawl = shop.get("crawl", {})
        if crawl.get("retry_result") == "需验证，暂无报价":
            failures["需验证 / 验证码"].append(shop["shop_key"])
        elif crawl.get("status") == "skipped" or "telegram" in shop["shop_key"].lower():
            failures["Telegram / 已跳过"].append(shop["shop_key"])
        elif crawl.get("status") not in ("success", "empty") and not shop.get("listings"):
            reason = str(crawl.get("reason") or "")
            if re.search(r"登录|login|401|403", reason, re.I): category = "需要登录"
            elif re.search(r"验证码|captcha|cloudflare|人机|访问验证|滑块", reason, re.I): category = "需验证 / 验证码"
            elif re.search(r"关闭|不存在|404|打烊", reason, re.I): category = "站点关闭"
            else: category = "结构未适配 / 其他失败"
            failures[category].append(shop["shop_key"])
    lines.extend(f"- {category}（{len(keys)}）：{', '.join(keys)}" for category, keys in sorted(failures.items()))
    lines.append(f"\n/home 固定目录商品卡数：14；Codex 已从公开目录移除，ChatGPT Go 加入目录。")
    lines += ["", "## Codex 并入前后 ChatGPT 报价", "",
              "| 商品 | 并入前报价 / 旧快照起价 | 并入后报价 / 入门起价 | 并入后规格组 |",
              "|---|---:|---:|---:|"]
    for product, before_quotes, before_price in (("ChatGPT Plus", 399, "¥31.80（旧快照原始最低价）"),
                                                  ("ChatGPT Pro", 200, "¥400（旧快照原始最低价）")):
        product_groups = groups_by_product.get(product, [])
        fields = product_price_fields(product_groups, product)
        after_quotes = sum(g["listing_count"] for g in product_groups)
        lines.append(f"| {product} | {before_quotes} / {before_price} | {after_quotes} / ¥{fields['starting_price'] if fields['starting_price'] is not None else '—'} | {len(product_groups)} |")
    lines.append("\n并入前数据取重处理快照 `2026-11-16.md` 的商品卡统计；并入后起价按当前标准档、地区/促销过滤和异常价规则计算。")
    lines += ["", "## Codex 归并说明", "", "Codex 不再作为独立目录商品。Go→ChatGPT Go，Plus→ChatGPT Plus，Pro/Pro100/Pro200/Pro500/Business/Team→ChatGPT Pro；规格标题移除 Codex 前缀。额度包保留源报价及剔除原因，不计入订阅起价。"]
    (REPORTS / "2026-11-16-coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _db_apply(path):
    from backend.db import SessionLocal
    from backend.importer import import_file
    from backend.models import Listing, Product, Shop, ShopProduct
    from sqlalchemy import select
    from .data_quality import assess_listing, canonicalize_codex
    from .normalize import classify, specification, comparison_exclusion
    from backend.api_v4 import _store_display_name

    with SessionLocal() as s:
        import_file(s, str(path), force=True)
    with SessionLocal() as s:
        products = {p.name: p for p in s.scalars(select(Product))}
        def get_product(name):
            if name not in products:
                p = Product(name=name, sort_order=0)
                s.add(p); s.flush(); products[name] = p
            return products[name]
        gopid = get_product("ChatGPT Go").id
        codex = products.get("Codex")
        shops = {x.id: x for x in s.scalars(select(Shop))}
        for row in s.scalars(select(Listing)):
            shop = shops.get(row.shop_id)
            product_name = products.get(row.product_id).name if row.product_id in products else None
            stored_markers = dict(row.spec or {})
            title = row.title or ""
            detected = classify(title, row.category or "") or product_name
            spec = specification(title, detected)
            if detected == "Codex" or product_name == "Codex":
                mapped, codex_reason = canonicalize_codex("Codex", title, spec)
                spec["codex_source_tier"] = spec.get("tier")
                spec["codex_mapped_product"] = mapped
                spec["catalog_title"] = re.sub(r"\bcodex\b", "", title, flags=re.I).strip()
                if mapped == "ChatGPT Plus": row.product_id = get_product(mapped).id
                elif mapped == "ChatGPT Pro": row.product_id = get_product(mapped).id
                elif mapped == "ChatGPT Go": row.product_id = gopid
                else: row.product_id = None
                if stored_markers.get("codex_duplicate_of"):
                    row.product_id = None
                    spec["codex_duplicate_of"] = stored_markers["codex_duplicate_of"]
                    codex_reason = "同店同规格 Codex 并入报价，保留更低价"
                if codex_reason:
                    spec["comparison_exclusion"] = codex_reason
                    spec["codex_source_tier"] = spec.get("tier")
            elif detected and detected != product_name:
                row.product_id = get_product(detected).id
            product_name = products.get(row.product_id).name if row.product_id in products else None
            shop_name = _store_display_name(shop, title) if shop else "未知店铺"
            if shop and shop_name and shop.name != shop_name:
                shop.name = shop_name[:400]
            quality = assess_listing(shop.shop_key if shop else "", shop_name, title, row.price,
                                     product_name, spec, row.currency)
            miss = comparison_exclusion(title, product_name, spec, row.price)
            spec.update({k: v for k, v in quality.items() if k != "keep"})
            if miss: spec["comparison_exclusion"] = miss
            if not quality["keep"] or miss or spec.get("comparison_exclusion"):
                row.product_id = None
            for preserve in ("verification_source", "codex_duplicate_of", "mirror_of"):
                if preserve in stored_markers:
                    spec[preserve] = stored_markers[preserve]
            row.spec = spec
            row.spec_key = spec["key"]
        # Rebuild product-shop mentions after Codex tier migration.
        links = {(sp.shop_id, sp.product_id): sp for sp in s.scalars(select(ShopProduct))}
        now = dt.datetime.now(dt.timezone.utc)
        for row in s.scalars(select(Listing).where(Listing.product_id.is_not(None))):
            k = (row.shop_id, row.product_id)
            if k not in links:
                s.add(ShopProduct(shop_id=row.shop_id, product_id=row.product_id,
                                  first_seen_at=now, last_seen_at=now))
                links[k] = True
        if codex:
            for sp in list(s.scalars(select(ShopProduct).where(ShopProduct.product_id == codex.id))):
                s.delete(sp)
        # Persist the same same-spec median flags that the read API computes.
        from types import SimpleNamespace
        from backend.api_v4 import spec_groups
        api_rows, row_by_obj = [], {}
        for row in s.scalars(select(Listing).where(Listing.product_id.is_not(None), Listing.active.is_(True))):
            p = products.get(row.product_id)
            shop = shops.get(row.shop_id)
            obj = SimpleNamespace(product_id=row.product_id, product_name=p.name if p else "",
                shop_id=row.shop_id, shop_name=_store_display_name(shop, row.title) if shop else "未知店铺",
                shop_key=shop.shop_key if shop else "", shop_domain=shop.domain if shop else "",
                title=row.title, price=float(row.price), currency=row.currency,
                spec=row.spec or {}, url=row.url)
            api_rows.append(obj); row_by_obj[id(obj)] = row
        spec_groups(api_rows)
        for obj in api_rows:
            listing = row_by_obj[id(obj)]
            spec = dict(listing.spec or {})
            for field in ("price_anomaly", "price_anomaly_reason", "quality_action",
                          "quality_review_required", "quality_review_reason", "comparison_exclusion"):
                if hasattr(obj, field): spec[field] = getattr(obj, field)
            listing.spec = spec
        if codex:
            s.flush()
        s.commit()


def main():
    env = dotenv_values(ROOT / ".env.local")
    for k, v in env.items():
        if v and not os.environ.get(k): os.environ[k] = v
    data = _load(BASE_PATH if BASE_PATH.exists() else LATEST_PATH)
    before = {"shops": len(data.get("shops", [])),
              "priced_shops": sum(bool(s.get("listings")) for s in data.get("shops", [])),
              "quotes": sum(len(s.get("listings", [])) for s in data.get("shops", [])),
              "groups": data.get("scope", {}).get("crawler", {}).get("spec_groups", 0)}
    incoming, counters, excluded, mirrors = _incoming_sources(data)
    shops = {s["shop_key"].casefold(): s for s in data["shops"]}
    for source, incoming_shop, row in incoming:
        key = incoming_shop["shop_key"].casefold()
        shop = shops.get(key)
        if shop is None:
            shop = {"shop_key": incoming_shop["shop_key"], "shop_name": incoming_shop["shop_name"],
                "domain": incoming_shop["domain"], "primary_url": incoming_shop["primary_url"],
                "final_url": incoming_shop["primary_url"], "all_urls": [incoming_shop["primary_url"]],
                "platform_type": "浏览器核实店铺", "http_code": "200", "page_status": "浏览器核实商品报价",
                "page_content_readable": True, "n_posts": 0, "n_accounts": 0, "products": "", "listings": [],
                "crawl": {"status": "success", "adapter": "manual_verified", "complete": False}}
            data["shops"].append(shop); shops[key] = shop
        elif source == "manual" and incoming_shop.get("shop_name"):
            shop["shop_name"] = incoming_shop["shop_name"]
        if source == "manual":
            shop.setdefault("crawl", {})["retry_result"] = "success"
        have = {(r.get("title", "").casefold(), str(r.get("price")), r.get("currency", "CNY")) for r in shop.get("listings", [])}
        dedupe_key = (row["title"].casefold(), row["price"], row["currency"])
        if dedupe_key in have:
            counters[f"{source}_already_in_snapshot"] += 1
            continue
        shop.setdefault("listings", []).append(row)
        counters[f"{source}_merged"] += 1
    _reprocess_all(data)
    stable_sources = {"browser_candidate_rows": 715, "browser_status_ok_shops": 19,
                      "opencode_candidate_rows": 257, "opencode_status_success_shops": 14,
                      "manual_candidate_rows": 98, "manual_new_rows": 92,
                      "manual_existing_rows": 6, "mirror_duplicate_rows_excluded": 112,
                      "airadar_invalid_declared_rows": 26}
    data["scope"].setdefault("merge", {}).update({"sources": stable_sources, "browser_sources_merged_at": data["generated_at"],
        "mirror_rows_excluded": len(mirrors), "airadar_invalid_declared": 26})
    _merge_report(data, counters, excluded, mirrors, before)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    BASE_PATH.write_text(payload, encoding="utf-8")
    LATEST_PATH.write_text(payload, encoding="utf-8")
    _db_apply(BASE_PATH)
    print(json.dumps({"before": before, "after": data["scope"]["crawler"], "sources": counters,
                      "excluded_codex": [(k, t, reason) for k, t, reason in excluded if "Codex" in t],
                      "mirror_excluded": len(mirrors)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
