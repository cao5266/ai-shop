"""前端 401 自动重试与「换 IP 不失效」的浏览器测试。用法：.venv/bin/python scripts/test_retry_ui.py
（本机自测；用 X-Forwarded-For 模拟不同 IP，需要服务以 ALLOW_HEADLESS_UA=1 启动）"""
import sys
from playwright.sync_api import sync_playwright
base = "http://127.0.0.1:8000"; fails = 0
def check(name, ok, extra=""):
    global fails; fails += not ok; print(("PASS " if ok else "FAIL ") + name + (f"  {extra}" if extra else ""))
with sync_playwright() as p:
    b = p.chromium.launch()
    # 1. 第一次数据请求返回 401：自动换会话并重试一次，页面正常显示
    ctx = b.new_context(extra_http_headers={"X-Forwarded-For": "192.0.2.11"}); pg = ctx.new_page()
    n = {"session": 0, "home": 0}
    pg.on("request", lambda r: n.__setitem__("session", n["session"] + 1) if r.url.endswith("/api/v4/session") else None)
    def once401(route):
        n["home"] += 1
        route.fulfill(status=401, content_type="application/json", body='{"error":"session_invalid"}') if n["home"] == 1 else route.continue_()
    pg.route("**/api/v4/home", once401)
    pg.goto(base); pg.wait_for_selector("a.card", timeout=10000)
    check("首次 401 后自动重试成功，页面显示商品卡片", True, f"session 请求 {n['session']} 次，home 请求 {n['home']} 次")
    check("只多换了一次会话（共 2 次）", n["session"] == 2 and n["home"] == 2)
    ctx.close()
    # 2. 一直 401：只重试一次，之后显示错误，不死循环
    ctx = b.new_context(extra_http_headers={"X-Forwarded-For": "192.0.2.12"}); pg = ctx.new_page()
    m = {"home": 0}
    def always401(route):
        m["home"] += 1; route.fulfill(status=401, content_type="application/json", body='{"error":"bad_signature"}')
    pg.route("**/api/v4/home", always401)
    pg.goto(base); pg.wait_for_selector(".state[role=alert]", timeout=10000); pg.wait_for_timeout(1500)
    check("持续 401 时只请求 2 次（原请求 + 重试 1 次），随后显示错误和重试按钮", m["home"] == 2 and pg.locator(".state button").count() == 1, f"home 请求 {m['home']} 次")
    ctx.close()
    # 3. 会话中途换 IP（Wi-Fi 切流量）：不需要重新取会话，请求照常成功
    ctx = b.new_context(); pg = ctx.new_page(); ip = {"v": "192.0.2.21"}; s = {"n": 0}
    pg.on("request", lambda r: s.__setitem__("n", s["n"] + 1) if r.url.endswith("/api/v4/session") else None)
    pg.route("**/*", lambda route: route.continue_(headers={**route.request.headers, "x-forwarded-for": ip["v"]}))
    pg.goto(base); pg.wait_for_selector("a.card")
    ip["v"] = "198.51.100.33"
    pg.click("a.card"); pg.wait_for_selector(".app-head .price", timeout=10000); pg.wait_for_selector(".row")
    check("会话中途换 IP 后继续浏览，不报错且没有重新取会话", s["n"] == 1, f"session 请求 {s['n']} 次")
    ctx.close(); b.close()
sys.exit(1 if fails else 0)
