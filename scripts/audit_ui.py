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
        pg = b.new_context(viewport={"width": w, "height": 700}, extra_http_headers={"X-Forwarded-For": "203.0.113.%d" % w}).new_page()
        for path, sel in [("/", "a.card"), ("/tool/Claude%20Pro", ".row"), ("/shops", ".row"), ("/shop/1", ".row, .state"), ("/about", "article")]:
            pg.goto(base + path); pg.wait_for_selector(sel); pg.wait_for_timeout(300)
            sw = pg.evaluate("document.documentElement.scrollWidth")
            ok = sw <= w; fails += not ok
            print(f"{'PASS' if ok else 'FAIL'} {w}px {path} scrollWidth={sw}")
    pg = b.new_context(viewport={"width": 1280, "height": 800}, extra_http_headers={"X-Forwarded-For": "203.0.113.9"}).new_page()
    pg.goto(base + "/tool/Claude%20Pro"); pg.wait_for_selector(".row")
    bad = []
    for _ in range(18):
        pg.keyboard.press("Tab")
        info = pg.evaluate("""()=>{const e=document.activeElement,r=e.getBoundingClientRect();
          const mark=(x)=>{const c=getComputedStyle(x);return (c.outlineStyle!=='none'&&parseFloat(c.outlineWidth)>0)||c.boxShadow!=='none'};
          // 焦点指示可以在元素自身（轮廓或 ring 阴影），也可以在包住它的 label / 搜索表单上（原生单选藏在 label 里、搜索框用外层高亮）
          const shown=mark(e)||['label','form'].some(s=>e.closest(s)&&mark(e.closest(s)));
          return {tag:e.tagName,txt:(e.getAttribute('aria-label')||e.textContent||'').trim().slice(0,18),shown,top:Math.round(r.top),bottom:Math.round(r.bottom),inHeader:!!e.closest('header'),isSkip:e.getAttribute('href')==='#main'}}""")
        # 顶栏自身的元素不会被顶栏遮挡；跳过链接聚焦时会浮在顶栏上
        if info["inHeader"] and not info["isSkip"]: 
            if not info["shown"]: bad.append(info)
            continue
        if not info["shown"] or (not info["isSkip"] and info["bottom"] < 65): bad.append(info)
    print("PASS 键盘焦点可见" if not bad else f"FAIL 焦点样式缺失或被顶栏遮挡 {bad}"); fails += bool(bad)
    pg.goto(base + "/tool/Claude%20Pro"); pg.wait_for_selector("[role=radio]")
    # 用真实的 Tab 键进入单选组，再按方向键（按键要持续一瞬间，Radix 靠它判断「是方向键触发的聚焦」）
    pg.focus("#main")
    for _ in range(14):
        pg.keyboard.press("Tab")
        if pg.evaluate("document.activeElement.getAttribute('role')") == "radio": break
    pg.keyboard.press("ArrowDown", delay=80); pg.wait_for_timeout(500)
    idx = pg.evaluate("[...document.querySelectorAll('[role=radio]')].findIndex(e=>e.getAttribute('aria-checked')==='true')")
    print(f"{'PASS' if idx == 1 else 'FAIL'} 规格单选支持方向键 选中序号={idx}"); fails += idx != 1
    # 路由切换后焦点移到正文
    pg.goto(base + "/"); pg.wait_for_selector("a.card"); pg.click("a.card"); pg.wait_for_selector(".app-head")
    tag = pg.evaluate("document.activeElement.id || document.activeElement.tagName")
    print(f"{'PASS' if tag == 'main' else 'FAIL'} 路由切换后焦点在正文 activeElement={tag}"); fails += tag != "main"
    css = pg.evaluate("[...document.styleSheets].flatMap(s=>[...s.cssRules]).map(r=>r.cssText).join('')")
    import re
    # main:focus 是路由切换后用程序把焦点放到 <main> 上，它本身不可键盘聚焦，所以允许 outline:none
    bad = re.findall(r"100vw|transition: ?all|(?<!main:focus \{ )outline: ?none", css)
    print("PASS 样式里没有 100vw / transition:all / outline:none" if not bad else f"FAIL {bad}"); fails += bool(bad)
    b.close()
sys.exit(1 if fails else 0)
