"""下载经核实的品牌 SVG，拒绝 HTML 错误页。"""
from pathlib import Path
import httpx

if __name__ == '__main__':
    url = 'https://raw.githubusercontent.com/lobehub/lobe-icons/master/packages/static-svg/icons/midjourney.svg'
    r = httpx.get(url, timeout=25)
    r.raise_for_status()
    if not r.text.lstrip().startswith('<svg'): raise ValueError('非 SVG')
    (Path(__file__).resolve().parent.parent / 'static/logos/midjourney.svg').write_text(r.text)
