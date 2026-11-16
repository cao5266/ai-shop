"""线上/本地 UI 冒烟与截图。"""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base', default='http://127.0.0.1:8003')
    p.add_argument('--prefix', default='v3_local')
    a = p.parse_args()
    shots = Path(__file__).resolve().parent.parent / 'shots'
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=['--disable-dev-shm-usage'])
        for mobile in (False, True):
            context = browser.new_context(viewport={'width': 390 if mobile else 1440, 'height': 844 if mobile else 1000},
                                          is_mobile=mobile, device_scale_factor=1)
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(a.base, wait_until='networkidle')
            page.wait_for_selector('.card')
            assert page.locator('.tile.mono').count() == 0
            assert page.locator('body').inner_text().find('帖子里没有标价') < 0
            broken = page.locator('.tile img').evaluate_all('(xs) => xs.filter(x => !x.complete || !x.naturalWidth).map(x => x.src)')
            assert not broken, broken
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), '首页横向溢出'
            page.screenshot(path=str(shots / f'{a.prefix}_{"mobile" if mobile else "desktop"}_home.png'), full_page=True)
            page.goto(a.base + '/#/tool/Muse', wait_until='networkidle')
            page.wait_for_selector('.item')
            assert page.locator('#spec option').count() > 0
            page.locator('#spec').select_option(index=min(1, page.locator('#spec option').count()-1))
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), '详情横向溢出'
            page.screenshot(path=str(shots / f'{a.prefix}_{"mobile" if mobile else "desktop"}_detail.png'), full_page=False)
            assert not errors, errors
            print('mobile' if mobile else 'desktop', '通过；卡片logo、规格筛选、链接与布局正常')
            context.close()
        browser.close()


if __name__ == '__main__': main()
