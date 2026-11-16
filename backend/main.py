"""FastAPI：加密接口 + 跳转 + React 构建产物。"""
from __future__ import annotations
import base64
import hashlib
import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy import select, text
from urllib.parse import urlsplit

from .api_v4 import router as api_router
from .db import SessionLocal, engine, init_db
from .models import Listing, Shop
from .secure import guard, parse_go

ROOT = Path(__file__).resolve().parent.parent
WEB_DIST = Path(os.environ.get("WEB_DIST") or ROOT / "web" / "dist")
app = FastAPI(title="AI 订阅比价", docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(api_router)

# Radix（shadcn 的 Select、弹层滚动锁定）会往 <head> 里注入固定内容的 <style> 元素。
# 不用 'unsafe-inline'，而是按内容的 sha256 逐条放行。升级 radix-ui 后如果浏览器控制台出现
# 「Applying inline style violates … style-src」，用 scripts/collect_csp_hashes.py 取新的哈希替换这里。
STYLE_HASHES = (
    "'sha256-441zG27rExd4/il+NvIqyL8zFx5XmyNQtE381kSkUJk='",
    "'sha256-nzTgYzXYDNe6BAHiiI7NNlfK8n/auuOAhh2t92YvuXo='",
)


def build_csp(script_hashes: tuple[str, ...] = ()) -> str:
    # script-src 不含 'unsafe-inline'：页面里唯一的内联脚本（主题初始化，防止暗色主题闪白）用 sha256 哈希放行。
    # 样式：<style> 元素与外链样式只认同源加上面几条哈希；style 属性（Radix 弹层定位会写内联 style）单独放行，见 README。
    scripts = " ".join(("'self'",) + script_hashes)
    styles = " ".join(("'self'",) + STYLE_HASHES)
    return (f"default-src 'self'; script-src {scripts}; style-src {styles}; style-src-attr 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; "
            "form-action 'self'; frame-ancestors 'none'")


CSP = build_csp()
_html_csp: dict = {"mtime": None, "value": CSP}


def html_csp() -> str:
    """读取构建产物 index.html 里的内联脚本，算出 sha256 放进 CSP（文件变化时重新计算）。"""
    index = WEB_DIST / "index.html"
    try:
        mtime = index.stat().st_mtime
    except OSError:
        return CSP
    if _html_csp["mtime"] != mtime:
        html = index.read_text(encoding="utf-8")
        hashes = tuple("'sha256-" + base64.b64encode(hashlib.sha256(s.encode()).digest()).decode() + "'"
                       for s in re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S) if s.strip())
        _html_csp.update(mtime=mtime, value=build_csp(hashes))
    return _html_csp["value"]


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    h = resp.headers
    h.setdefault("Content-Security-Policy", CSP)
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "same-origin")
    h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    if request.url.path.startswith("/api/"):
        h["Cache-Control"] = "no-store"
    return resp


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "error"
    return JSONResponse({"error": detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/healthz")
def healthz():
    with engine.connect() as c:
        c.execute(text("select 1"))
    return {"ok": True}


@app.get("/go/{token}")
def go(token: str, request: Request):
    """店铺跳转：令牌里只有内部编号和签名，真实链接留在服务端，302 到店铺页。"""
    guard(request, "go")
    site = request.headers.get("sec-fetch-site")
    if site and site not in ("same-origin", "none"):
        raise HTTPException(403, "forbidden")
    shop_id, listing_id = parse_go(token)
    with SessionLocal() as s:
        url = None
        if listing_id:
            l = s.get(Listing, listing_id)
            if l and l.shop_id == shop_id:
                url = l.url
        if not url:
            shop = s.get(Shop, shop_id)
            url = shop.primary_url if shop else None
    if not url or urlsplit(url).scheme not in ("http", "https"):
        raise HTTPException(404, "not found")
    return RedirectResponse(url, status_code=302, headers={
        "Referrer-Policy": "no-referrer", "Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"})


@app.get("/{path:path}")
def spa(path: str):
    if path.startswith(("api/", "go/")):
        raise HTTPException(404, "not found")
    f = (WEB_DIST / path).resolve()
    if path and f.is_file() and WEB_DIST.resolve() in f.parents:
        headers = {"Cache-Control": "public, max-age=31536000, immutable"} if path.startswith("assets/") else {}
        return FileResponse(f, headers=headers)
    index = WEB_DIST / "index.html"
    if not index.exists():
        raise HTTPException(503, "前端尚未构建：cd web && npm ci && npm run build")
    return FileResponse(index, headers={"Cache-Control": "no-cache", "Content-Security-Policy": html_csp()})
