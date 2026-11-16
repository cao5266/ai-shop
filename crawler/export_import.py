"""保留全量店铺/商品和溯源字段，商品长描述留原始证据以减少每日传输。"""
import argparse
import json
from pathlib import Path

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('input')
    p.add_argument('output')
    a = p.parse_args()
    data = json.loads(Path(a.input).read_text())
    for shop in data['shops']:
        for row in shop.get('listings', []): row.pop('description', None)
    Path(a.output).write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
