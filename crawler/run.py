import argparse
import asyncio
import datetime as dt
import hashlib
import json
import re
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from playwright.async_api import async_playwright
from .adapters import ADAPTERS
from .adapters.generic import parse_html
from .normalize import representative_rank

HERE = Path(__file__).resolve().parent
READ_QUERIES = {"/shopApi/goods/list", "/shopApi/goods/detail", "/shopApi/goodsCategory/list",
                "/shopApi/shop/detail", "/shopApi/system/config", "/shopApi/Shop/info",
                "/shopApi/Shop/goodsList", "/shopApi/Shop/categoryList"}
FORBIDDEN = re.compile(r"/(?:order|orders|buy|pay|payment|checkout|register|login|logout|visit|track|collect|cart)(?:/|\?|$)", re.I)


class Context:
    def __init__(self, client, browser, evidence, browser_sem):
        self.client, self.browser, self.evidence, self.browser_sem = client, browser, evidence, browser_sem
        self.locks = defaultdict(asyncio.Lock)

    async def request(self, method, url, **kwargs):
        if method == "POST" and urlsplit(url).path not in READ_QUERIES:
            raise ValueError("不在只读查询白名单")
        async with self.locks[urlsplit(url).netloc]:
            await asyncio.sleep(0.65)
            response = await self.client.request(method, url, **kwargs)
            if "json" in response.headers.get("content-type", ""):
                key = hashlib.sha256((url + json.dumps(kwargs, sort_keys=True)).encode()).hexdigest()[:20]
                (self.evidence / (key + ".api.json")).write_text(json.dumps({"url": url, "method": method,
                    "query": kwargs.get("json"), "status": response.status_code,
                    "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(), "body": response.text}, ensure_ascii=False))
            return response

    async def get(self, url): return await self.request("GET", url)
    async def query(self, url, data): return await self.request("POST", url, json=data)

    async def render(self, url, rule, prior=""):
        async with self.browser_sem:
            try:
                context = await self.browser.new_context(locale="zh-CN", service_workers="block")
            except Exception as e:
                return [], {"status": "failed", "reason": prior + "；浏览器进程不可用：" + str(e)[:180], "complete": False}
            page = await context.new_page()
            network = []
            captured = []
            async def intercept(route):
                req = route.request
                path = urlsplit(req.url).path
                if FORBIDDEN.search(path) or (req.method not in ("GET", "HEAD") and path not in READ_QUERIES) or re.search(r"chatwoot|/widget/|google-analytics|hm\.baidu", req.url):
                    await route.abort(); return
                if req.resource_type in ("font", "media"): await route.abort(); return
                await route.continue_()
            async def response(r):
                if r.request.resource_type not in ("xhr", "fetch"): return
                try:
                    body = await r.text()
                    network.append({"url": r.url, "method": r.request.method, "query": r.request.post_data,
                                    "status": r.status, "body": body[:2000000]})
                    if urlsplit(r.url).path == "/shopApi/goods/list":
                        obj = json.loads(body)
                        if obj.get("code") == 1: captured.extend(obj.get("data", {}).get("list", []))
                except Exception: pass
            await page.route("**/*", intercept)
            page.on("response", response)
            reason = prior
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(4500)
                html = await page.content()
                rows = parse_html(html, page.url, rule)
                if captured:
                    from .normalize import listing
                    origin = str(httpx.URL(page.url).copy_with(path="/", query=None)).rstrip("/")
                    rows.extend(listing(r["name"], r["price"], origin + "/goods/" + r["goods_no"],
                                        r.get("goods_category_no", ""), image=r.get("image"),
                                        external_id=r["goods_no"], stock=r.get("stock_available_quantity"),
                                        stock_status=r.get("stock_available_status"), sales=r.get("sales_count_text"), source_url=url)
                                for r in captured if r.get("name") and r.get("price") is not None)
                text = await page.locator("body").inner_text()
                if not rows:
                    if re.search(r"验证您是真人|验证您不是自动程序|请完成以下操作|captcha|验证页面|Access denied|Just a moment", text, re.I): reason = "访问验证/验证码拦截"
                    elif re.search(r"店铺已打烊|店铺不存在|商品不存在|店铺已关闭|店铺已停用", text): reason = "店铺关闭或不存在：" + text[-250:]
                    else: reason = prior + "；浏览器渲染后未找到可验证商品价格：" + text[:180]
                key = hashlib.sha256(url.encode()).hexdigest()[:20]
                (self.evidence / (key + ".html")).write_text(html)
                (self.evidence / (key + ".network.json")).write_text(json.dumps(network, ensure_ascii=False))
                return rows, {"status": "success" if rows else "failed", "reason": reason if not rows else "",
                              "method": "browser", "complete": bool(captured), "evidence": key}
            except Exception as e:
                return [], {"status": "failed", "reason": prior + "；浏览器 " + type(e).__name__ + " " + str(e)[:240], "complete": False}
            finally: await context.close()


def report(data, previous, path):
    shops = data["shops"]
    old_shops = {s["shop_key"]: s for s in previous.get("shops", [])}
    changes = []
    grouped = defaultdict(list)
    observed = set()
    success = 0
    for s in shops:
        rows = s.get("listings", [])
        success += bool(rows)
        old = {r["listing_key"]: r for r in old_shops.get(s["shop_key"], {}).get("listings", [])}
        for r in rows:
            if r.get("product"):
                identity = (r["url"], r["title"], r["currency"])
                if identity not in observed and r.get("stock_status") != "out" and r.get("stock") != 0:
                    observed.add(identity)
                    # 包含完整比较键：信息不足的不同标题也必须分行。
                    spec_label = r["spec"]["label"] + ("（" + r["title"] + "）" if r["spec"].get("incomplete") else "")
                    grouped[(r["product"], spec_label, r["currency"])].append(Decimal(r["price"]))
            before = old.get(r["listing_key"])
            if before and Decimal(before["price"]) != Decimal(r["price"]):
                changes.append(f'- {s["shop_key"]}：{r["title"]}，{before["price"]} → {r["price"]}')
    lines = [f'# {data["generated_at"][:10]} 店铺采集报告', '',
             f'共检查 {len(shops)} 家；采到价格 {success} 家 / {sum(len(s.get("listings", [])) for s in shops)} 个商品；Telegram 仅记录 {sum(s["crawl"]["status"] == "skipped" for s in shops)} 家。',
             f'新增店：{sum(s["shop_key"] not in old_shops for s in shops) if old_shops else 0}（相对上次快照；首次以输入店铺为基线）；价格变化：{len(changes)}。', '',
             '## 规格价格区间', '', '| 标准商品 | 规格 | 币种 | 最低 | 最高 | 商品数 |', '|---|---|---|---:|---:|---:|']
    for (product, spec, currency), prices in sorted(grouped.items()):
        lines.append(f'| {product} | {spec.replace("|", "/")} | {currency} | {min(prices)} | {max(prices)} | {len(prices)} |')
    lines += ['', '规格信息不完整时，线上只按同一商品标题比较；库存为零的商品不参与在售最低价。', '', '## 价格变化', '', *(changes or ['- 无已知变化（首次采集不视为涨跌）']), '', '## 失败店铺及原因', '']
    lines += ['## 代表规格与最低价', '', '| 标准商品 | 代表规格 | 最低价（元） | 结果 |', '|---|---|---:|---|']
    products = sorted({r.get('classified_product', r.get('product')) for s in shops for r in s.get('listings', [])
                       if r.get('classified_product', r.get('product'))})
    for product in products:
        candidates = [r for s in shops for r in s.get('listings', [])
                      if r.get('classified_product', r.get('product')) == product and not r.get('comparison_exclusion')
                      and r.get('currency') == 'CNY' and r.get('stock_status') != 'out' and r.get('stock') != 0]
        groups = {}
        for row in candidates:
            key = row['spec']['key']
            group = groups.setdefault(key, {'product': product, 'spec': row['spec'], 'label': row['spec']['label'],
                                            'currency': 'CNY', 'n_shops': 0, 'shops': set(), 'rows': []})
            group['rows'].append(row)
            group['shops'].add(next(s['shop_key'] for s in shops if any(x['listing_key'] == row['listing_key'] for x in s.get('listings', []))))
            group['n_shops'] = len(group['shops'])
        if not groups:
            lines.append(f"| {product} | — | — | 无合格入门付费规格 |")
            continue
        chosen = min(groups.values(), key=representative_rank)
        price = min(Decimal(r['price']) for r in chosen['rows'])
        lines.append(f"| {product} | {chosen['label'].replace('|', '/')} | {price} | 已按入门规格筛选 |")
    covered = {r.get("classified_product", r.get("product")) for s in shops for r in s.get("listings", [])}
    missing = [p for p in ["ChatGPT Plus", "ChatGPT Pro", "Claude Pro", "Claude Max", "Grok", "Gemini", "Cursor", "Codex", "Muse", "Perplexity", "Copilot", "X会员", "Telegram会员", "Midjourney"] if p not in covered]
    if missing: lines.insert(4, '尚未采到可验证商品价的标准商品：' + '、'.join(missing) + '。')
    lines += [f'- {s["shop_key"]}：{s["crawl"].get("reason", "")}' for s in shops if s["crawl"]["status"] not in ("success", "skipped")]
    lines += ['', '## 按域名/系统分组', '', '| 域名 | 适配器 | 店铺数 |', '|---|---|---:|']
    for (domain, adapter), count in sorted(Counter((s["domain"], s["crawl"]["adapter"]) for s in shops).items()):
        lines.append(f'| {domain} | {adapter} | {count} |')
    path.write_text('\n'.join(lines) + '\n')


async def run(args):
    source = json.loads(Path(args.input).read_text())
    registry = json.loads((HERE / "registry.json").read_text())
    date = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    evidence = output / "evidence" / date
    evidence.mkdir(parents=True, exist_ok=True)
    previous_path = output / "latest.json"
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
    shops = source["shops"]
    if args.only: shops = [s for s in shops if args.only in s["shop_key"]]
    if args.limit: shops = shops[:args.limit]
    sem = asyncio.Semaphore(args.concurrency)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (compatible; AIShopsPriceObserver/1.0)"}) as client:
            ctx = Context(client, browser, evidence, asyncio.Semaphore(1))
            async def crawl(s):
                if args.retry_failed and s.get("listings"):
                    return s
                domain = s["domain"].removeprefix("www.")
                rule = registry["shops"].get(s["shop_key"], {})
                adapter = rule.get("adapter", registry["domains"].get(domain, "generic"))
                async with sem:
                    if adapter == "telegram": rows, status = [], {"status": "skipped", "reason": "Telegram 店仅记录，不采集", "complete": False}
                    else:
                        try:
                            for attempt in range(2):
                                try:
                                    rows, status = await ADAPTERS[adapter]().crawl(ctx, s, rule)
                                    break
                                except Exception:
                                    if attempt: raise
                                    await asyncio.sleep(2)
                        except Exception as e:
                            rows, status = await ctx.render(s["primary_url"], rule, type(e).__name__ + " " + str(e)[:150])
                    clean = {}
                    for r in rows:
                        try:
                            amount = Decimal(r["price"])
                            if not amount.is_finite() or amount <= 0: continue
                        except (InvalidOperation, TypeError): continue
                        if r.get("currency_source") not in (None, "CNY", "RMB"): r["currency"] = r["currency_source"]
                        identity = r.get("external_id") or r["url"] + "|" + r["title"]
                        r["listing_key"] = hashlib.sha256(identity.encode()).hexdigest()
                        r["observed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
                        clean[r["listing_key"]] = r
                    s["listings"] = list(clean.values())
                    s["crawl"] = dict(status, adapter=adapter, observed_at=dt.datetime.now(dt.timezone.utc).isoformat())
                    s["page_status"] = status.get("reason") or "店铺商品价格已采集"
                    s["page_content_readable"] = bool(clean)
                    # 原始抽取的裸页面金额无法归属商品，不再沿用为商品报价。
                    s["prices_from_page"] = ""
                    print(f'{s["shop_key"]}: {len(clean)} 商品，{status["status"]}', flush=True)
                    # 逐店落盘，长任务中断也能继续审核已完成结果。
                    (evidence / (hashlib.sha256(s["shop_key"].encode()).hexdigest()[:20] + ".result.json")).write_text(json.dumps(s, ensure_ascii=False))
                    return s
            results = await asyncio.gather(*(crawl(dict(s)) for s in shops))
        await browser.close()
    data = {**source, "generated_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(), "shops": results}
    data["scope"] = {**source.get("scope", {}), "source": "店铺公开商品接口与只读浏览器页面；X 历史报价仅供溯源", "limitations": ["价格为采集时公开展示金额，库存与价格可能随时变化。", "访问验证、关闭、超时等失败保留原因；Telegram 店仅记录。", "未标明期限或额度的商品不与已知规格混合比较。"], "crawler": {"shops": len(results), "priced_shops": sum(bool(s["listings"]) for s in results)}}
    for shop in results:
        for row in shop.get("listings", []):
            from .normalize import classify, specification, comparison_exclusion
            row["product"] = classify(row["title"], row.get("category", ""))
            row["spec"] = specification(row["title"], row["product"])
            row["risk"] = row["spec"]["risk"]
            row['classified_product'] = row['product']
            row['standard_product'] = row['classified_product']
            row['comparison_exclusion'] = comparison_exclusion(row['title'], row['product'], row['spec'], row['price'])
            if row['comparison_exclusion']:
                row['product'] = None
            identity = row.get("external_id") or row["url"] + "|" + row["title"]
            row["listing_key"] = hashlib.sha256(identity.encode()).hexdigest()
    # 诊断过的历史关联只说明提及，不等于在售。明确记录以供详情解释。
    notes = json.loads((HERE / "product_notes.json").read_text())
    data["scope"]["product_notes"] = notes
    target = output / (date + ".json")
    serialized = json.dumps(data, ensure_ascii=False, indent=2)
    target.write_text(serialized)
    report(data, previous, output / (date + ".md"))
    previous_path.write_text(serialized)
    print(f'报告：{output / (date + ".md")}\n导入文件：{target}', flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--input", default=str(HERE.parent.parent / "shops.json"))
    p.add_argument("--output", default=str(HERE.parent.parent / "crawler/reports"))
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--limit", type=int)
    p.add_argument("--only")
    p.add_argument("--retry-failed", action="store_true", help="输入上次全量 JSON，只重新采失败店铺，保留成功报价与原采集时间")
    asyncio.run(run(p.parse_args()))
