"""对10个标准商品最低价重新读取商品详情，核对标题/金额/规格与URL。"""
import asyncio
import argparse
import datetime as dt
import json
import subprocess
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from bs4 import BeautifulSoup
from .normalize import specification, representative_rank

ROOT = Path(__file__).resolve().parents[2]


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat())
    parser.add_argument('--refresh', action='store_true', help='重新核实，不复用抽查缓存')
    parser.add_argument('--product', action='append', help='只核实指定商品，可重复')
    args = parser.parse_args()
    path = ROOT / 'crawler/reports' / (args.date + '.json')
    data = json.loads(path.read_text())
    previous_path = path.parent / (args.date + '-audit.json')
    previous = json.loads(previous_path.read_text()) if previous_path.exists() and not args.refresh else []
    products = ['ChatGPT Plus', 'ChatGPT Pro', 'Claude Pro', 'Claude Max', 'Grok Plus',
                'Gemini', 'Cursor', 'Codex', 'Muse', 'Perplexity', 'Copilot', 'X会员', 'Telegram会员', 'Midjourney']
    if args.product:
        products = args.product
    results = []
    row_shops = {id(r): s['shop_key'] for s in data['shops'] for r in s.get('listings', [])}
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        for product in products:
            rows = [r for s in data['shops'] for r in s.get('listings', []) if r.get('classified_product', r.get('product')) == product
                    and not r.get('comparison_exclusion')
                    and r.get('stock_status') != 'out' and r.get('stock') != 0 and r['currency'] == 'CNY']
            groups = {}
            for row in rows:
                g = groups.setdefault(row['spec']['key'], {'product': product, 'spec': row['spec'], 'label': row['spec']['label'], 'n_prices': 0, 'rows': []})
                g['n_prices'] += 1
                g['rows'].append(row)
                g['n_shops'] = len({row_shops[id(x)] for x in g['rows']})
            if not groups and product == 'Grok Plus':
                # Backward compatible with historical reports without exclusion metadata.
                rows = [r for s in data['shops'] for r in s.get('listings', []) if r.get('product') == product
                        and r.get('stock_status') != 'out' and r.get('stock') != 0 and r['currency'] == 'CNY'
                        and r['spec'].get('delivery') != '成品号']
                for row in rows:
                    g = groups.setdefault(row['spec']['key'], {'product': product, 'spec': row['spec'], 'label': row['spec']['label'], 'n_prices': 0, 'rows': []})
                    g['n_prices'] += 1
                    g['rows'].append(row)
                    g['n_shops'] = len({row_shops[id(x)] for x in g['rows']})
            if not groups:
                results.append(dict(product=product, passed=False, unavailable=True,
                                    reason='已有证据没有在售、可验证的入门付费规格'))
                print(product, '无合格报价', flush=True)
                continue
            rows = min(groups.values(), key=representative_rank)['rows']
            r = min(rows, key=lambda x: Decimal(x['price']))
            url = r['url']
            origin = '{0.scheme}://{0.netloc}'.format(urlsplit(url))
            result = dict(product=product, shop=row_shops[id(r)], title=r['title'], price=r['price'], spec=r['spec']['label'],
                          url=url, checked_at=dt.datetime.now(dt.timezone.utc).isoformat())
            cached = next((x for x in previous if x.get('passed') and x['url'] == url and x['title'] == r['title'] and Decimal(x['price']) == Decimal(r['price'])), None)
            if cached:
                cached['spec'] = r['spec']['label']
                results.append(cached)
                print(product, r['price'], '已核对，沿用同日详情证据', flush=True)
                continue
            try:
                html = await client.get(url)
                soup = BeautifulSoup(html.text, 'html.parser')
                if '16688.com.cn' in origin:
                    # 商品页面使用此只读详情接口；响应中的商品编号必须与链接一致。
                    key = urlsplit(url).path.rsplit('/', 1)[-1]
                    for attempt in range(5):
                        try:
                            detail = await client.post(origin + '/shopApi/goods/detail', json={'goods_no': key})
                            body = detail.json()
                            break
                        except ValueError:
                            if attempt == 4:
                                proc = await asyncio.to_thread(subprocess.run, ['curl', '-fsS', '--max-time', '20',
                                    '-H', 'Content-Type: application/json', '--data', json.dumps({'goods_no': key}),
                                    origin + '/shopApi/goods/detail'], capture_output=True, text=True, timeout=25)
                                body = json.loads(proc.stdout)
                                break
                            await asyncio.sleep(2)
                    if body.get('code') != 1: raise ValueError(body.get('msg'))
                    obj = body['data']
                    actual_title, actual_price = obj['name'], obj['price']
                    assert obj['goods_no'] == key, '商品编号与链接不符'
                    result['evidence_url'] = origin + '/shopApi/goods/detail'
                    result['evidence'] = obj
                elif 'catfk.com' in origin or 'wzyp.cn' in origin:
                    key = urlsplit(url).path.rsplit('/', 1)[-1]
                    for attempt in range(4):
                        try:
                            detail = await client.post(origin + '/shopApi/Shop/goodsInfo', json={'goods_key': key})
                            body = detail.json()
                            break
                        except ValueError:
                            if attempt == 3: raise
                            await asyncio.sleep(2)
                    if body.get('code') != 1: raise ValueError(body.get('msg'))
                    obj = body['data']
                    actual_title, actual_price = obj['name'], obj['price']
                    assert obj.get('goods_key') == key, '详情商品编号不符'
                    result['evidence_url'] = origin + '/shopApi/Shop/goodsInfo'
                    result['evidence'] = obj
                elif '/api/v1/public/products' in r.get('source_url', ''):
                    slug = urlsplit(url).path.split('/products/', 1)[1]
                    detail = await client.get(origin + '/api/v1/public/products/' + slug)
                    body = detail.json()
                    obj = body['data']
                    val = obj['title']
                    actual_title = val.get('zh-CN') or next(v for v in val.values() if v) if isinstance(val, dict) else val
                    external = r.get('external_id', '').split(':')[-1]
                    variants = [v for v in obj.get('skus', []) if str(v.get('id')) == external]
                    variant = variants[0] if variants else obj
                    actual_price = variant['price_amount']
                    if ' / ' in r['title']: actual_title = r['title'] if r['title'].startswith(actual_title) else actual_title
                    result['evidence_url'] = str(detail.url)
                    result['evidence'] = obj
                else:
                    text = soup.get_text(' ', strip=True)
                    actual_title = r['title'] if r['title'] in text else (soup.h1.get_text(' ', strip=True) if soup.h1 else '')
                    actual_price = None
                    for node in soup.select('script[type="application/ld+json"]'):
                        try:
                            objs = json.loads(node.get_text())
                            if isinstance(objs, dict): objs = [objs]
                            for obj in objs:
                                if obj.get('@type') == 'Product':
                                    offers = obj.get('offers', [])
                                    if isinstance(offers, dict): offers = [offers]
                                    for o in offers:
                                        if Decimal(str(o.get('price', -1))) == Decimal(r['price']):
                                            actual_price = o['price']
                                            actual_title = obj['name'] + (' / ' + o['name'] if o.get('name') else '')
                        except (ValueError, TypeError): pass
                    if actual_price is None:
                        import re
                        amounts = re.findall(r'[¥￥]\s*(\d+(?:\.\d+)?)', text)
                        if any(Decimal(a) == Decimal(r['price']) for a in amounts): actual_price = r['price']
                    if actual_price is None and '/user/api/index/commodity' in r.get('source_url', ''):
                        detail = await client.get(origin + '/user/api/index/commodity')
                        objs = detail.json()['data']
                        obj = next(o for o in objs if str(o['id']) == urlsplit(url).path.rsplit('/', 1)[-1])
                        actual_title, actual_price = obj['name'], obj['price']
                        result['detail_api'] = str(detail.url)
                        result['detail_api_evidence'] = obj
                    result['evidence_url'] = str(html.url)
                    result['evidence'] = text[:18000]
                result.update(actual_title=actual_title, actual_price=str(actual_price),
                              title_match=actual_title == r['title'], price_match=Decimal(str(actual_price)) == Decimal(r['price']),
                              spec_match=specification(actual_title, product)['key'] == r['spec']['key'],
                              link_match=str(html.url).rstrip('/') == url.rstrip('/') or
                              (urlsplit(str(html.url)).path.rstrip('/') == urlsplit(url).path.rstrip('/') and urlsplit(str(html.url)).netloc.removeprefix('www.') == urlsplit(url).netloc.removeprefix('www.')))
                result['passed'] = all(result[k] for k in ['title_match', 'price_match', 'spec_match', 'link_match'])
            except Exception as e:
                result.update(passed=False, error=type(e).__name__ + ': ' + str(e))
            if not result['passed'] and any(h in origin for h in ['16688.com.cn', 'catfk.com', 'wzyp.cn']):
                # 同一公开详情接口从部署机只读复核，避免本机出口的间歇拦截。
                import shlex
                key = urlsplit(url).path.rsplit('/', 1)[-1]
                is_new = '16688.com.cn' in origin
                endpoint = origin + ('/shopApi/goods/detail' if is_new else '/shopApi/Shop/goodsInfo')
                remote = 'curl -fsS --max-time 20 -H ' + shlex.quote('Content-Type: application/json') + ' --data ' + shlex.quote(json.dumps({'goods_no' if is_new else 'goods_key': key})) + ' ' + shlex.quote(endpoint)
                proc = await asyncio.to_thread(subprocess.run, ['ssh', '-i', str(Path.home()/'.ssh/aishops.pem'),
                    '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', 'ubuntu@101.34.76.198', remote], capture_output=True, text=True, timeout=35)
                try:
                    obj = json.loads(proc.stdout)['data']
                    result.update(actual_title=obj['name'], actual_price=str(obj['price']),
                        title_match=obj['name'] == r['title'], price_match=Decimal(str(obj['price'])) == Decimal(r['price']),
                        spec_match=specification(obj['name'], product)['key'] == r['spec']['key'], link_match=obj.get('goods_no' if is_new else 'goods_key') == key,
                        evidence=obj, evidence_url=endpoint, verification_route='部署机只读详情接口')
                    result['passed'] = all(result[k] for k in ['title_match','price_match','spec_match','link_match'])
                    if result['passed']: result.pop('error', None)
                except Exception: pass
            results.append(result)
            # 每条完成立即保存；外层超时中断后可从已完成证据继续。
            previous_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))
            print(product, r['price'], result['passed'], result.get('error', ''), flush=True)
            await asyncio.sleep(1)
    out = path.parent / (args.date + '-audit.json')
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    lines = ['# 10 条最低价逐条核对', '', '按每个标准商品代表规格的当前在售人民币最低价选样（入门月卡优先），重新读取对应商品页及其只读详情接口。', '',
             '| 商品 | 标题 | 采集价 | 详情价 | 规格 | 标题/价格/规格/链接 |', '|---|---|---:|---:|---|---|']
    for x in results:
        if x.get('unavailable'):
            lines.append(f'| {x["product"]} | 无合格报价 | — | — | — | {x["reason"]} |')
            continue
        lines.append(f'| {x["product"]} | [{x["title"].replace("|", "/")}]({x["url"]}) | {x["price"]} | {x.get("actual_price", "失败")} | {x["spec"].replace("|", "/")} | {"四项一致" if x["passed"] else x.get("error", "存在差异")} |')
    path.with_name(args.date + '-audit.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__': asyncio.run(main())
