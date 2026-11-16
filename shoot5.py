"""v5 截图与自测（shadcn 版）：亮/暗首页、展开的排序下拉、暗色详情、手机；检查控制台/CSP 报错、主题持久化与防闪白。"""
import sys
from playwright.sync_api import sync_playwright
base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
fails = 0
def check(name, ok, extra=""):
    global fails; fails += not ok; print(("PASS " if ok else "FAIL ") + name + (f"  {extra}" if extra else ""))
def watch(pg, errs):
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: m.type in ("error", "warning") and errs.append(m.text))
with sync_playwright() as p:
    b = p.chromium.launch()
    # 亮色
    ctx = b.new_context(viewport={"width": 1366, "height": 900}, color_scheme="light", extra_http_headers={"X-Forwarded-For": "198.51.100.1"}); pg = ctx.new_page(); errs = []; watch(pg, errs)
    pg.goto(base); pg.wait_for_selector("a.card"); pg.wait_for_timeout(500); pg.screenshot(path="shots/v5_light_home.png")
    pg.goto(base + "/tool/Claude%20Pro"); pg.wait_for_selector(".row"); pg.wait_for_timeout(300)
    pg.click("[aria-label=排序]"); pg.wait_for_selector("[role=listbox]"); pg.wait_for_timeout(300); pg.screenshot(path="shots/v5_sort_open.png")
    opts = pg.locator("[role=option]").all_inner_texts(); check("排序下拉选项", opts == ["价格从低到高", "价格从高到低", "最近更新"], str(opts))
    pg.get_by_role("option", name="价格从高到低").click(); pg.wait_for_timeout(700)
    check("选择排序后列表刷新（价格从高到低）", "价格从高到低" in pg.inner_text("[aria-label=排序]"))
    # 主题切换与持久化
    pg.click("[aria-label=切换主题]"); pg.get_by_role("menuitemradio", name="暗色").click(); pg.wait_for_timeout(200)
    check("选择暗色后 html.dark 且写入 localStorage", pg.evaluate("document.documentElement.classList.contains('dark')") and pg.evaluate("localStorage.getItem('theme')") == "dark")
    pg.reload(); pg.wait_for_selector(".row"); check("刷新后仍是暗色", pg.evaluate("document.documentElement.classList.contains('dark')"))
    pg.screenshot(path="shots/v5_dark_detail.png")
    pg.click("[aria-label=切换主题]"); pg.get_by_role("menuitemradio", name="跟随系统").click(); pg.wait_for_timeout(200)
    check("选择跟随系统后清除 localStorage，并按系统（亮色）显示", pg.evaluate("localStorage.getItem('theme')") is None and not pg.evaluate("document.documentElement.classList.contains('dark')"))
    check("亮色流程无控制台/CSP 报错", not errs, "; ".join(errs)[:300]); ctx.close()
    # 暗色（系统）+ 防闪白：先挂起 JS 包，只剩 HTML+CSS 时页面背景就必须已经是暗色
    ctx = b.new_context(viewport={"width": 1366, "height": 900}, color_scheme="dark", extra_http_headers={"X-Forwarded-For": "198.51.100.2"}); pg = ctx.new_page(); errs = []; watch(pg, errs)
    held = []
    pg.route("**/assets/*.js", lambda r: held.append(r))      # 挂起 JS 请求：此时页面只有 HTML 和 CSS
    pg.goto(base, wait_until="commit"); pg.wait_for_timeout(1200)
    bg = pg.evaluate("getComputedStyle(document.body).backgroundColor"); dark_early = pg.evaluate("document.documentElement.classList.contains('dark')")
    check("JS 未加载时已是暗色（无白屏闪烁）", dark_early and bg == "rgb(17, 19, 18)", f"html.dark={dark_early} body={bg}")
    for r in held: r.continue_()
    pg.wait_for_selector("a.card"); pg.wait_for_timeout(500); pg.screenshot(path="shots/v5_dark_home.png")
    check("暗色流程无控制台/CSP 报错", not errs, "; ".join(errs)[:300]); ctx.close()
    # 手机
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme="light", extra_http_headers={"X-Forwarded-For": "198.51.100.3"}); pg = ctx.new_page(); errs = []; watch(pg, errs)
    pg.goto(base); pg.wait_for_selector("a.card"); pg.wait_for_timeout(500); pg.screenshot(path="shots/v5_mobile.png")
    pg.goto(base + "/shops"); pg.wait_for_selector(".row"); pg.wait_for_timeout(300); pg.screenshot(path="shots/v5_mobile_shops.png")
    pg.get_by_role("button", name="筛选").click(); pg.wait_for_selector("[role=dialog]"); pg.wait_for_timeout(400); pg.screenshot(path="shots/v5_mobile_filter_sheet.png")
    check("手机端无控制台/CSP 报错", not errs, "; ".join(errs)[:300]); ctx.close(); b.close()
sys.exit(1 if fails else 0)
