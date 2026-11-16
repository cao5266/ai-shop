"""接口防护：会话密钥、请求签名、响应加密、限流、UA/Bot 拦截、跳转令牌。

这些措施只提高自动化抓取的成本，挡不住真正想抓的人：浏览器里必然有解密密钥。
"""
from __future__ import annotations
import base64
import collections
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException, Request
from fastapi.responses import Response

log = logging.getLogger("aishops.secure")
_secret = os.environ.get("API_SIGNING_SECRET", "")
if not _secret:
    _secret = secrets.token_hex(32)
    log.warning("未设置 API_SIGNING_SECRET：使用随机值，重启后所有会话和跳转令牌失效（仅限开发环境）")
SECRET = _secret.encode()
SESSION_TTL = int(os.environ.get("API_SESSION_TTL", "1200"))   # 秒
TS_WINDOW = 90                                                   # 请求时间戳允许的偏差，秒

BOT_UA = re.compile(
    r"curl|wget|python|requests|httpx|aiohttp|urllib|scrapy|go-http|java/|okhttp|libwww|node-fetch|axios|undici|"
    r"postman|insomnia|httpie|spider|crawl|bot\b|scraper|phantom|selenium|puppeteer|playwright|lighthouse|headlesschrome", re.I)
ALLOW_HEADLESS = os.environ.get("ALLOW_HEADLESS_UA", "") == "1"   # 本机自测截图用


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def unb64u(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hm(msg: str, n: int = 32) -> bytes:
    return hmac.new(SECRET, msg.encode(), hashlib.sha256).digest()[:n]


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


# ---------------- 限流（内存滑动窗口，单进程）
class Limiter:
    def __init__(self):
        self.hits: dict[tuple, collections.deque] = {}
        self.lock = threading.Lock()

    def check(self, bucket: str, ip: str, limit: int, per: float = 60.0) -> bool:
        now = time.monotonic()
        with self.lock:
            if len(self.hits) > 50000:
                self.hits = {k: v for k, v in self.hits.items() if v and now - v[-1] < per}
            q = self.hits.setdefault((bucket, ip), collections.deque())
            while q and now - q[0] > per:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True


LIMITER = Limiter()
LIMITS = {"session": int(os.environ.get("RL_SESSION", "20")), "api": int(os.environ.get("RL_API", "120")),
          "go": int(os.environ.get("RL_GO", "40"))}


def guard(request: Request, bucket: str):
    ua = request.headers.get("user-agent", "")
    if not ua or (BOT_UA.search(ua) and not (ALLOW_HEADLESS and "headlesschrome" in ua.lower())):
        raise HTTPException(403, "forbidden")
    site = request.headers.get("sec-fetch-site")
    if site and site not in ("same-origin", "same-site", "none"):
        raise HTTPException(403, "forbidden")
    if not LIMITER.check(bucket, client_ip(request), LIMITS[bucket]):
        raise HTTPException(429, "请求太频繁，请稍后再试", headers={"Retry-After": "30"})


# ---------------- 会话
# 会话绑定的是 User-Agent，不是 IP：手机在 Wi-Fi 与流量之间切换时 IP 会变，但 UA 不变。
# 这个绑定很弱（伪造 UA 就能绕过），它只是让「把密钥拷到别的客户端」多一道手续；限流仍然按 IP 做。
def ua_tag(request: Request) -> str:
    return hm("ua:" + request.headers.get("user-agent", ""), 6).hex()


def new_session(request: Request) -> dict:
    exp = int(time.time()) + SESSION_TTL
    payload = b64u(json.dumps({"e": exp, "u": ua_tag(request), "r": secrets.token_hex(6)},
                              separators=(",", ":")).encode())
    sid = payload + "." + b64u(hm("sid:" + payload, 16))
    return {"sid": sid, "key": b64(hm("key:" + sid)), "exp": exp, "ts": int(time.time())}


def session_key(request: Request, sid: str) -> bytes:
    try:
        payload, tag = sid.split(".")
        if not hmac.compare_digest(b64u(hm("sid:" + payload, 16)), tag):
            raise ValueError
        info = json.loads(unb64u(payload))
        if info["e"] < time.time():
            raise HTTPException(401, "session_expired")
        if info["u"] != ua_tag(request):
            raise HTTPException(401, "session_expired")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "session_invalid")
    return hm("key:" + sid)


_nonces: dict[str, float] = {}
_nlock = threading.Lock()


def _use_nonce(n: str):
    now = time.time()
    with _nlock:
        if len(_nonces) > 20000:
            for k in [k for k, v in _nonces.items() if v < now]:
                del _nonces[k]
        if n in _nonces:
            raise HTTPException(401, "replay")
        _nonces[n] = now + TS_WINDOW * 2


class Ctx:
    def __init__(self, key: bytes, nonce: str):
        self.key, self.nonce = key, nonce

    def seal(self, obj) -> Response:
        iv = os.urandom(12)
        ct = AESGCM(self.key).encrypt(iv, json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str).encode(),
                                      self.nonce.encode())
        return Response(json.dumps({"v": 1, "iv": b64(iv), "ct": b64(ct)}), media_type="application/json",
                        headers={"Cache-Control": "no-store"})


def secure_ctx(request: Request) -> Ctx:
    """FastAPI 依赖：校验 UA、限流、会话、时间戳、随机数与签名。"""
    guard(request, "api")
    h = request.headers
    sid, ts, nonce, sig = h.get("x-sid", ""), h.get("x-ts", ""), h.get("x-nonce", ""), h.get("x-sig", "")
    if not (sid and ts.isdigit() and 8 <= len(nonce) <= 64 and sig) or h.get("x-requested-with") != "aishops-web":
        raise HTTPException(401, "bad_request")
    key = session_key(request, sid)
    if abs(time.time() - int(ts)) > TS_WINDOW:
        raise HTTPException(401, "clock_skew")
    raw_path = request.scope.get("raw_path", b"").decode() or request.url.path
    qs = request.scope.get("query_string", b"").decode()
    msg = f"{request.method}\n{raw_path}{'?' + qs if qs else ''}\n{ts}\n{nonce}"
    want = hmac.new(key, msg.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(want, sig):
        raise HTTPException(401, "bad_signature")
    _use_nonce(nonce)
    return Ctx(key, nonce)


# ---------------- 店铺跳转令牌：接口里只出现 /go/<令牌>，真实链接留在服务端
def go_token(shop_id: int, listing_id: int | None) -> str:
    body = f"{shop_id}.{listing_id or 0}"
    return f"{body}.{hm('go:' + body, 9).hex()}"


def parse_go(token: str) -> tuple[int, int]:
    try:
        s, l, sig = token.split(".")
        if not hmac.compare_digest(hm(f"go:{s}.{l}", 9).hex(), sig):
            raise ValueError
        return int(s), int(l)
    except Exception:
        raise HTTPException(404, "not found")
