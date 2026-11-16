"""重新应用归类规则到已采证据，不生成或修改价格。"""
import argparse
import hashlib
import json
from pathlib import Path
from .normalize import classify, specification, comparison_exclusion
from .run import report


def main():
    p = argparse.ArgumentParser()
    p.add_argument('path')
    a = p.parse_args()
    path = Path(a.path)
    data = json.loads(path.read_text())
    for shop in data['shops']:
        crawl = shop.get('crawl', {})
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
        for r in shop.get('listings', []):
            import re
            r['title'] = re.sub(r' / en-US:.*? / zh-CN:(.*?)(?: / zh-TW:.*)?$', r' / \1', r['title'])
            r['product'] = classify(r['title'], r.get('category', ''))
            r['spec'] = specification(r['title'], r['product'])
            r['risk'] = r['spec']['risk']
            r['classified_product'] = r['product']
            r['standard_product'] = r['classified_product']
            r['comparison_exclusion'] = comparison_exclusion(r['title'], r['product'], r['spec'], r['price'])
            if r['comparison_exclusion']:
                r['product'] = None
            identity = r.get('external_id') or r['url'] + '|' + r['title']
            r['listing_key'] = hashlib.sha256(identity.encode()).hexdigest()
    text = json.dumps(data, ensure_ascii=False, indent=2)
    data['scope']['product_notes'] = json.loads((Path(__file__).parent / 'product_notes.json').read_text())
    text = json.dumps(data, ensure_ascii=False, indent=2)
    previous = json.loads((path.parent / 'latest.json').read_text()) if (path.parent / 'latest.json').exists() else {}
    path.write_text(text)
    (path.parent / 'latest.json').write_text(text)
    report(data, previous, path.with_suffix('.md'))


if __name__ == '__main__': main()
