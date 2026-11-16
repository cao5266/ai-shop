"""重新应用归类规则到已采证据，不生成或修改价格。"""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from .normalize import classify, specification, comparison_exclusion, combo_products
from .run import report


def main():
    p = argparse.ArgumentParser()
    p.add_argument('path')
    a = p.parse_args()
    path = Path(a.path)
    data = json.loads(path.read_text())
    for shop in data['shops']:
        crawl = shop.get('crawl', {})
        adapter = crawl.get('adapter')
        if adapter == '16688': shop['platform_type'] = '独角数卡 / ShopApi'
        elif adapter == 'catfk': shop['platform_type'] = '异次元发卡 / ShopApi'
        elif adapter == 'next': shop['platform_type'] = 'Dujiao Next'
        elif adapter == 'yici': shop['platform_type'] = '异次元'
        elif adapter == 'telegram': shop['platform_type'] = 'Telegram'
        elif adapter == 'generic':
            sources = ' '.join(r.get('source_url', '') for r in shop.get('listings', []))
            if '/api/v1/public/products' in sources: shop['platform_type'] = 'Dujiao Next'
            elif '/user/api/' in sources: shop['platform_type'] = '异次元'
        if crawl.get('evidence'):
            evidence = path.parent / 'evidence' / path.stem / (crawl['evidence'] + '.html')
            if evidence.exists() and ('访问验证' in crawl.get('reason', '') or '店铺关闭' in crawl.get('reason', '')):
                from bs4 import BeautifulSoup
                content = BeautifulSoup(evidence.read_text(), 'html.parser').get_text(' ', strip=True)
                import re
                if not re.search(r'验证您是真人|验证您不是自动程序|请完成以下操作|captcha|验证页面|Access denied|Just a moment', content, re.I):
                    crawl['reason'] = '渲染后未找到对应商品的可验证报价：' + content[:180]
        if shop['shop_key'] == 'lumaoai.com':
            crawl['reason'] = '已核实为工具教程导航站；Copilot 出现在教程，不是商品报价。商城另指向 lumaozhanghao.com。'
        if shop['shop_key'] == 'tt.twitter.plus/item/46510':
            crawl['reason'] = '已核实为 ChatGPT Plus 商品（页面起价¥66）；Copilot 仅在第三方工具支持列表中提及，并无 Copilot 价格。'
        from copy import deepcopy
        expanded = []
        for original in shop.get('listings', []):
            combo = combo_products(original.get('title', ''))
            if len(combo) > 1 and not original.get('combo_member'):
                for product in combo:
                    clone = deepcopy(original)
                    clone['combo_member'] = True
                    clone['combo_member_product'] = product
                    expanded.append(clone)
            else:
                expanded.append(original)
        shop['listings'] = expanded
        for r in shop.get('listings', []):
            import re
            r['title'] = re.sub(r' / en-US:.*? / zh-CN:(.*?)(?: / zh-TW:.*)?$', r' / \1', r['title'])
            r['product'] = classify(r['title'], r.get('category', ''))
            if r.get('combo_member'):
                r['product'] = r['combo_member_product']
            r['spec'] = specification(r['title'], r['product'])
            r['risk'] = r['spec']['risk']
            r['classified_product'] = r['product']
            r['standard_product'] = r['classified_product']
            r['comparison_exclusion'] = comparison_exclusion(r['title'], r['product'], r['spec'], r['price'])
            if r['comparison_exclusion']:
                r['product'] = None
            identity = r.get('external_id') or r['url'] + '|' + r['title']
            if r.get('combo_member'):
                identity += '|combo:' + r['combo_member_product']
            r['listing_key'] = hashlib.sha256(identity.encode()).hexdigest()
    text = json.dumps(data, ensure_ascii=False, indent=2)
    data['scope']['product_notes'] = json.loads((Path(__file__).parent / 'product_notes.json').read_text())
    quote_ids = {(shop['shop_key'], row.get('external_id') or row.get('url'), row.get('title'), row.get('currency', 'CNY'))
                 for shop in data['shops'] for row in shop.get('listings', [])}
    raw_spec_groups = {(row.get('classified_product', row.get('product')), row.get('spec', {}).get('key'), row.get('currency', 'CNY'))
                       for shop in data['shops'] for row in shop.get('listings', [])
                       if row.get('product') and not row.get('comparison_exclusion')
                       and row.get('stock_status') != 'out' and row.get('stock') != 0}
    from backend.api_v4 import spec_groups as build_api_spec_groups
    validation_shops = {shop['shop_key'] for shop in data['shops']
                        if shop.get('crawl', {}).get('retry_result') == '需验证，暂无报价'}
    normalized_rows = []
    row_links = {}
    for shop in data['shops']:
        if shop['shop_key'] in validation_shops: continue
        for row in shop.get('listings', []):
            if not row.get('product') or row.get('comparison_exclusion') or row.get('stock_status') == 'out' or row.get('stock') == 0:
                continue
            obj = SimpleNamespace(product_id=row['product'], shop_id=shop['shop_key'], url=row.get('url', ''),
                                  title=row.get('title', ''), currency=row.get('currency', 'CNY'),
                                  price=float(row['price']), spec=row.get('spec') or {},
                                  product_name=row['product'], shop_name=shop.get('shop_name') or shop['shop_key'],
                                  shop_key=shop['shop_key'])
            normalized_rows.append(obj)
            row_links[id(obj)] = row
    canonical_groups = build_api_spec_groups(normalized_rows)
    anomaly_count = 0
    for obj in normalized_rows:
        row = row_links[id(obj)]
        row['price_anomaly'] = bool(getattr(obj, 'price_anomaly', False))
        row['price_anomaly_reason'] = getattr(obj, 'price_anomaly_reason', None)
        anomaly_count += row['price_anomaly']
    data['scope']['crawler'] = {**data['scope'].get('crawler', {}), 'shops': len(data['shops']),
                                'priced_shops': sum(bool(s.get('listings')) for s in data['shops']),
                                'quotes': len(quote_ids), 'spec_groups_raw': len(raw_spec_groups),
                                'spec_groups': len(canonical_groups), 'price_anomalies': anomaly_count}
    text = json.dumps(data, ensure_ascii=False, indent=2)
    previous = json.loads((path.parent / 'latest.json').read_text()) if (path.parent / 'latest.json').exists() else {}
    path.write_text(text)
    (path.parent / 'latest.json').write_text(text)
    report(data, previous, path.with_suffix('.md'))


if __name__ == '__main__': main()
