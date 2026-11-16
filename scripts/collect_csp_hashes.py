"""收集页面在各种交互下触发的 CSP 违规及内联样式哈希（升级 radix-ui 后用）。用法：.venv/bin/python scripts/collect_csp_hashes.py"""
from playwright.sync_api import sync_playwright
base="http://127.0.0.1:8000"; found={}; hashes=set()
import re
with sync_playwright() as p:
    b=p.chromium.launch()
    for vp,mob in (({"width":1366,"height":900},False),({"width":390,"height":844},True)):
        ctx=b.new_context(viewport=vp,is_mobile=mob,has_touch=mob,extra_http_headers={"X-Forwarded-For":"192.0.2.%d"%(77 if mob else 66)}); pg=ctx.new_page()
        pg.on('console',lambda m: hashes.update(re.findall(r"sha256-[A-Za-z0-9+/=]+",m.text)))
        pg.add_init_script("window.__v=[];document.addEventListener('securitypolicyviolation',e=>window.__v.push([e.violatedDirective,e.effectiveDirective,(e.sample||'').slice(0,80),e.blockedURI]))")
        def grab():
            for v in pg.evaluate("window.__v"): found[tuple(v)]=1
        pg.goto(base+"/tool/Claude%20Pro"); pg.wait_for_selector(".row"); grab()
        pg.click("[aria-label=排序]"); pg.wait_for_selector("[role=listbox]"); pg.keyboard.press("Escape"); grab()
        pg.click("[aria-label=切换主题]"); pg.wait_for_selector("[role=menu]"); pg.keyboard.press("Escape"); grab()
        pg.get_by_role("button",name="价格怎么比").click(); pg.wait_for_selector("[role=dialog]"); pg.keyboard.press("Escape"); grab()
        pg.hover(".row >> text=最低") if pg.locator(".row >> text=最低").count() else None; grab()
        pg.goto(base+"/shops"); pg.wait_for_selector(".row")
        if mob: pg.get_by_role("button",name="筛选").click(); pg.wait_for_selector("[role=dialog]"); pg.keyboard.press("Escape")
        else: pg.click("[aria-label=商品]"); pg.wait_for_selector("[role=listbox]"); pg.keyboard.press("Escape")
        grab()
        if mob: pg.get_by_role("button",name="打开菜单").click(); pg.wait_for_selector("[role=dialog]"); pg.keyboard.press("Escape"); grab()
        pg.goto(base+"/shop/1"); pg.wait_for_selector("[role=tab]"); pg.click("[role=tab] >> nth=1"); grab()
        ctx.close()
    b.close()
for k in found: print(k)
print(sorted(hashes))
