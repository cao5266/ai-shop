"""接口防护自测：用 Python 完整走一遍「取会话 → 签名 → 解密」，并检查各项拦截。
用法：.venv/bin/python scripts/selftest_api.py [http://127.0.0.1:8000]
注意：本机自测的限流项会消耗该 IP 的限额，跑完等一分钟再用浏览器。"""
import base64, hashlib, hmac, json, os, sys, time, urllib.parse
import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
B = {"User-Agent": UA, "X-Requested-With": "aishops-web"}
results = []
def check(name, ok, extra=""):
    results.append(ok); print(("PASS " if ok else "FAIL ") + name + (f"  {extra}" if extra else ""))

c = httpx.Client(base_url=BASE, timeout=20, follow_redirects=False)
sess = c.get("/api/v4/session", headers=B).json(); key = base64.b64decode(sess["key"])

def signed(path, ts=None, nonce=None, sid=None, sig_override=None, key_=None, headers=None):
    ts = str(ts or int(time.time())); nonce = nonce or os.urandom(12).hex()
    sig = sig_override or hmac.new(key_ or key, f"GET\n{path}\n{ts}\n{nonce}".encode(), hashlib.sha256).hexdigest()
    h = {**B, "X-Sid": sid or sess["sid"], "X-Ts": ts, "X-Nonce": nonce, "X-Sig": sig, **(headers or {})}
    return c.get(path, headers=h), nonce

def decrypt(r, nonce):
    env = r.json(); return json.loads(AESGCM(key).decrypt(base64.b64decode(env["iv"]), base64.b64decode(env["ct"]), nonce.encode()))

r, n = signed("/api/v4/home"); home = decrypt(r, n)
check("签名请求可解密", r.status_code == 200 and "tools" in home, f"工具 {len(home['tools'])} 个")
check("响应原文是密文（不含店铺名/价格明文）", "ChatGPT" not in r.text and '"price"' not in r.text)
r2, _ = signed("/api/v4/home", nonce=n)
check("重放同一 nonce 被拒绝", r2.status_code == 401, r2.text)
r, _ = signed("/api/v4/home", sig_override="0" * 64); check("签名错误被拒绝", r.status_code == 401, r.text)
r, _ = signed("/api/v4/home", ts=int(time.time()) - 600); check("过期时间戳被拒绝", r.status_code == 401, r.text)
r, _ = signed("/api/v4/home", key_=os.urandom(32)); check("用错误密钥签名被拒绝", r.status_code == 401)
# 会话不绑定 IP：同一会话从另一个 IP 发请求仍可用（本机 uvicorn 信任 127.0.0.1 传来的 X-Forwarded-For）
r, n = signed("/api/v4/home", headers={"X-Forwarded-For": "203.0.113.7"}); ok1 = r.status_code == 200 and "tools" in decrypt(r, n)
r, n = signed("/api/v4/home", headers={"X-Forwarded-For": "198.51.100.9"}); ok2 = r.status_code == 200 and "tools" in decrypt(r, n)
check("同一会话换 IP 仍可用（模拟 Wi-Fi 切流量）", ok1 and ok2)
r, _ = signed("/api/v4/home", headers={"User-Agent": UA.replace("Chrome/126.0", "Chrome/99.0")}); check("同一会话换 User-Agent 被拒绝（绑定 UA）", r.status_code == 401, r.text)
r = c.get("/api/v4/home", headers=B); check("无签名被拒绝", r.status_code == 401)
r = c.get("/api/v4/session", headers={"User-Agent": "curl/8.5.0", "X-Requested-With": "aishops-web"}); check("curl UA 被拦截", r.status_code == 403)
r = c.get("/api/v4/session", headers={"User-Agent": "python-requests/2.32"}); check("python-requests UA 被拦截", r.status_code == 403)
r = c.get("/api/v4/session", headers={"User-Agent": ""}); check("空 UA 被拦截", r.status_code == 403)
r = c.get("/api/v4/session", headers={**B, "Sec-Fetch-Site": "cross-site"}); check("跨站请求被拦截", r.status_code == 403)
for old in ("/api/shops", "/api/meta", "/api/products", "/api/tools"):
    check(f"旧的未加密接口 {old} 已不存在", c.get(old, headers=B).status_code == 404)

r, n = signed("/api/v4/shops?size=31"); check("page size 超过上限被拒绝", r.status_code == 422)
r, n = signed("/api/v4/shops?size=30&page=41"); check("页码超过上限被拒绝", r.status_code == 422)
r, n = signed("/api/v4/shops?size=30&page=1"); page1 = decrypt(r, n)
check("店铺接口必须分页（单页不超过 30，总数大于单页）", len(page1["items"]) <= 30 and page1["total"] > len(page1["items"]), f"本页 {len(page1['items'])} / 共 {page1['total']}")
blob = json.dumps(page1) + json.dumps(home)
check("接口 JSON 里不出现真实链接（http/https）", "http://" not in blob and "https://" not in blob)
go = page1["items"][0]["go"]
r = c.get(go, headers={**B, "Sec-Fetch-Site": "same-origin"})
check("店铺跳转是后端 302", r.status_code == 302 and r.headers["location"].startswith("http"), r.headers.get("location", "")[:40] + "…")
check("跳转带 no-referrer 与 no-store", r.headers.get("referrer-policy") == "no-referrer" and "no-store" in r.headers.get("cache-control", ""))
check("伪造跳转令牌 404", c.get(go[:-4] + "0000", headers=B).status_code == 404)
check("跨站来源的跳转被拒绝", c.get(go, headers={**B, "Sec-Fetch-Site": "cross-site"}).status_code == 403)
hdr = c.get("/", headers=B).headers
check("安全响应头齐全", all(k in hdr for k in ("content-security-policy", "x-content-type-options", "x-frame-options", "referrer-policy", "permissions-policy")))
# 限流：连续请求 session，最终应出现 429
codes = [c.get("/api/v4/session", headers=B).status_code for _ in range(40)]
check("超限后返回 429", 429 in codes, f"首个 429 出现在第 {codes.index(429) + 1 if 429 in codes else '-'} 次")
print(f"\n{sum(results)}/{len(results)} 通过"); sys.exit(0 if all(results) else 1)
