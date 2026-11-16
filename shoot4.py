"""v4 截图与自测：电脑首页/详情、手机；同时检查控制台报错、跳转 302、响应加密。"""
import sys, json
from playwright.sync_api import sync_playwright
base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
with sync_playwright() as p:
    b = p.chromium.launch()
    d = b.new_context(viewport={"width": 1366, "height": 900}); pg = d.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    bodies = []
    pg.on("response", lambda r: bodies.append(r) if "/api/v4/" in r.url and "session" not in r.url else None)
    pg.goto(base); pg.wait_for_selector("a.card"); pg.wait_for_timeout(400)
    pg.screenshot(path="shots/v4_desktop_home.png")
    pg.screenshot(path="shots/v4_desktop_home_full.png", full_page=True)
    raw = bodies[0].text()[:120]; print("接口原文（应为密文）:", raw)
    pg.goto(base + "/tool/Claude%20Pro"); pg.wait_for_selector(".row"); pg.wait_for_timeout(400)
    pg.screenshot(path="shots/v4_desktop_detail.png")
    pg.goto(base + "/shops"); pg.wait_for_selector(".row"); pg.wait_for_timeout(300)
    pg.screenshot(path="shots/v4_desktop_shops.png")
    href = pg.eval_on_selector(".row .btn", "e=>[e.getAttribute('href'),e.target,e.rel]"); print("去店铺链接:", href)
    print("desktop errors", errs)
    m = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True); pg = m.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda x: x.type == "error" and errs.append(x.text))
    pg.goto(base); pg.wait_for_selector("a.card"); pg.wait_for_timeout(400)
    pg.screenshot(path="shots/v4_mobile.png")
    pg.screenshot(path="shots/v4_mobile_full.png", full_page=True)
    pg.goto(base + "/tool/Claude%20Pro"); pg.wait_for_selector(".row"); pg.wait_for_timeout(400)
    pg.screenshot(path="shots/v4_mobile_detail.png")
    pg.goto(base + "/shops"); pg.wait_for_selector(".row"); pg.screenshot(path="shots/v4_mobile_shops.png")
    print("mobile errors", errs)
    b.close()
