import sys
from playwright.sync_api import sync_playwright
base = "http://127.0.0.1:8000"
with sync_playwright() as p:
    b = p.chromium.launch()
    d = b.new_context(viewport={"width": 1366, "height": 900}); pg = d.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.goto(base); pg.wait_for_selector(".card"); pg.wait_for_timeout(500)
    pg.screenshot(path="shots/v2_desktop_home.png")
    pg.screenshot(path="shots/v2_desktop_home_full.png", full_page=True)
    pg.goto(base + "/#/tool/Claude%20Pro"); pg.wait_for_selector(".item"); pg.wait_for_timeout(400)
    pg.screenshot(path="shots/v2_desktop_detail.png")
    pg.goto(base + "/#/tool/Grok"); pg.wait_for_selector(".item"); pg.screenshot(path="shots/v2_desktop_detail_grok.png")
    pg.goto(base + "/#/shops"); pg.wait_for_selector(".item"); pg.locator("[data-more]").first.click(); pg.wait_for_selector(".extra .xcols"); pg.wait_for_timeout(300)
    pg.screenshot(path="shots/v2_desktop_shops.png")
    print("desktop errors", errs)
    m = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True); pg = m.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m_: m_.type == "error" and errs.append(m_.text))
    pg.goto(base); pg.wait_for_selector(".card"); pg.wait_for_timeout(500)
    pg.screenshot(path="shots/v2_mobile_home.png")
    pg.goto(base + "/#/tool/Claude%20Pro"); pg.wait_for_selector(".item"); pg.wait_for_timeout(400)
    pg.screenshot(path="shots/v2_mobile_detail.png")
    pg.goto(base + "/#/shops"); pg.wait_for_selector(".item"); pg.screenshot(path="shots/v2_mobile_shops.png")
    print("mobile errors", errs)
    b.close()
