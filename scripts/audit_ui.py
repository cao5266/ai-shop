"""界面自审：320/375 宽度横向溢出、键盘焦点可见且不被顶栏遮挡、规格单选的方向键、样式禁用项。
用法：.venv/bin/python scripts/audit_ui.py [http://127.0.0.1:8000]
（本机自测用，需要服务以 ALLOW_HEADLESS_UA=1 启动；会消耗该 IP 的限流额度，跑完稍等一下）"""
import sys
from playwright.sync_api import sync_playwright

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
fails = 0
with sync_playwright() as p:
    b = p.chromium.launch()
    for w in (320, 375):
        pg = b.new_context(viewport={"width": w, "height": 700}).new_page()
        for path, sel in [("/", "a.card"), ("/tool/Claude%20Pro", ".row"), ("/shops", ".row"), ("/shop/1", ".row, .state"), ("/about", "article")]:
            pg.goto(base + path); pg.wait_for_selector(sel); pg.wait_for_timeout(300)
            sw = pg.evaluate("document.documentElement.scrollWidth")
            ok = sw <= w; fails += not ok
            print(f"{'PASS' if ok else 'FAIL'} {w}px {path} scrollWidth={sw}")
    pg = b.new_context(viewport={"width": 1280, "height": 800}).new_page()
    pg.goto(base + "/tool/Claude%20Pro"); pg.wait_for_selector(".row")
    bad = []
    for _ in range(16):
        pg.keyboard.press("Tab")
        info = pg.evaluate("""()=>{const e=document.activeElement,cs=getComputedStyle(e),r=e.getBoundingClientRect();
          return {tag:e.tagName,txt:(e.getAttribute('aria-label')||e.textContent||'').trim().slice(0,18),outline:cs.outlineStyle+' '+cs.outlineWidth,top:Math.round(r.top),bottom:Math.round(r.bottom),inHeader:!!e.closest('header,.skip'),inSearch:!!e.closest('.search'),inSpec:!!e.closest('.spec')}}""")
        # 搜索框用外层 :focus-within 的边框高亮、规格单选用外层 label 的轮廓，都算有焦点指示；顶栏自身不会遮挡自己
        if info["inHeader"]: continue
        if (info["outline"].startswith("none") and not info["inSearch"] and not info["inSpec"]) or info["bottom"] < 65: bad.append(info)
    print("PASS 键盘焦点可见" if not bad else f"FAIL 焦点样式缺失或被顶栏遮挡 {bad}"); fails += bool(bad)
    pg.goto(base + "/tool/Claude%20Pro"); pg.wait_for_selector(".spec")
    pg.focus("input[name=spec]:checked"); pg.keyboard.press("ArrowDown")
    idx = pg.evaluate("[...document.querySelectorAll('input[name=spec]')].findIndex(e=>e.checked)")
    print(f"{'PASS' if idx == 1 else 'FAIL'} 规格单选支持方向键 选中序号={idx}"); fails += idx != 1
    # 路由切换后焦点移到正文
    pg.goto(base + "/"); pg.wait_for_selector("a.card"); pg.click("a.card"); pg.wait_for_selector(".app-head")
    tag = pg.evaluate("document.activeElement.id || document.activeElement.tagName")
    print(f"{'PASS' if tag == 'main' else 'FAIL'} 路由切换后焦点在正文 activeElement={tag}"); fails += tag != "main"
    css = pg.evaluate("[...document.styleSheets].flatMap(s=>[...s.cssRules]).map(r=>r.cssText).join('')")
    import re
    # .page:focus 是路由切换后用程序把焦点放到 <main> 上，它本身不可键盘聚焦，所以允许 outline:none
    bad = re.findall(r"100vw|transition: ?all|(?<!\.page:focus \{ )outline: ?none", css)
    print("PASS 样式里没有 100vw / transition:all / outline:none" if not bad else f"FAIL {bad}"); fails += bool(bad)
    b.close()
sys.exit(1 if fails else 0)
