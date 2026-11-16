"""FastAPI：加密接口 + 跳转 + React 构建产物。"""
from __future__ import annotations
import os
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

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; "
       "connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")


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
    return FileResponse(index, headers={"Cache-Control": "no-cache"})
