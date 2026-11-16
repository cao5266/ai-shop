import sys
from playwright.sync_api import sync_playwright
base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, vw, mob in (("desktop", {"width": 1366, "height": 900}, False), ("mobile", {"width": 390, "height": 844}, True)):
        ctx = b.new_context(viewport=vw, device_scale_factor=2 if mob else 1, is_mobile=mob, has_touch=mob)
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
        pg.goto(base); pg.wait_for_selector(".row"); pg.wait_for_timeout(600)
        pg.screenshot(path=f"shots/{name}_home.png")
        pg.screenshot(path=f"shots/{name}_full.png", full_page=True) if False else None
        pg.locator(".row .toggle").first.click(); pg.wait_for_selector(".detail .dgrid"); pg.wait_for_timeout(300)
        pg.locator(".row").first.scroll_into_view_if_needed(); pg.screenshot(path=f"shots/{name}_detail.png")
        pg.locator(".tab[data-view=products]").click(); pg.wait_for_selector(".prod"); pg.wait_for_timeout(300)
        pg.screenshot(path=f"shots/{name}_products.png")
        print(name, "errors:", errs)
        ctx.close()
    b.close()
