"""设计稿截图：先起后端，再 `API_TARGET=http://127.0.0.1:8001 npx vite --port 8100`，再运行本脚本；截图前缀 wired_。"""
import sys
from playwright.sync_api import sync_playwright
base = "http://127.0.0.1:8100"
def shot(b, name, path, scheme="light", w=1366, h=900, full=False, wait=".card", mobile=False):
    ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, device_scale_factor=2 if mobile else 1)
    pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.goto(base + path); pg.wait_for_selector(wait); pg.wait_for_timeout(1800)
    pg.screenshot(path=f"shots/{name}.png", full_page=full)
    print(name, errs[:3]); ctx.close()
with sync_playwright() as p:
    b = p.chromium.launch()
    only = sys.argv[1:] 
    jobs = {
      "wired_desktop_light": dict(path="/", full=True),
      "wired_desktop_dark": dict(path="/", scheme="dark", full=True),
      "wired_mobile": dict(path="/", w=390, h=1700, mobile=True),
      "wired_mobile_dark": dict(path="/", w=390, h=844, scheme="dark", mobile=True),
      "wired_detail_light": dict(path="/tool/ChatGPT%20Plus", wait=".row", full=True),
      "wired_detail_dark": dict(path="/tool/Claude%20Pro", scheme="dark", wait=".row", full=True),
      "wired_detail_mobile": dict(path="/tool/Claude%20Pro", w=390, h=1500, wait=".row", mobile=True),
      "wired_shops_light": dict(path="/shops", wait=".row", full=True),
      "wired_shops_dark": dict(path="/shops", scheme="dark", wait=".row"),
      "wired_shops_mobile": dict(path="/shops", w=390, h=1500, wait=".row", mobile=True),
    }
    for k, v in jobs.items():
        if not only or k in only: shot(b, k, **v)
