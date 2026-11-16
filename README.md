# AI 订阅比价

按 AI 工具比较各家店铺在售价格的导航站。价格来自每天采集的店铺商品页（`crawler/`），按期限、额度和交付方式分规格比较。
所有店铺均为非官方渠道，本站不担保交易。

## 技术栈

- 前端：React 19 + TypeScript + Vite（`web/`），react-router，无 UI 框架，系统中文字体
- 后端：Python 3.13、FastAPI、SQLAlchemy 2、psycopg 3、cryptography
- 数据库：PostgreSQL（生产）；没设置 `DATABASE_URL` 时回退到本地 SQLite（仅开发）
- 部署：Docker Compose（app + postgres），Dockerfile 多阶段构建（node 构建前端，python 运行）
- 采集：`crawler/`（独立维护，本次改版没有改动）

## 目录

```
web/            React 前端（src/ 源码，public/ 含品牌 logo、favicon 与商品 logo，brand/ 生成脚本）
backend/        models 表结构 · importer 导入 · cli 命令行 · api_v4 接口 · secure 防护 · fieldcrypt 字段加密 · main 入口
crawler/        每日商品采集（OpenCode 维护）
scripts/        backup_encrypted.sh / restore_encrypted.sh / luks_volume.sh / selftest_api.py / audit_ui.py
deploy/         redeploy.sh（发布）· nginx/（域名 + HTTPS 模板）
data/seed/      首批数据 shops.json
shots/          截图
```

## 本地开发

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cd web && npm ci && npm run build && cd ..          # 构建前端；开发时可用 npm run dev（代理到 8000）
export FIELD_ENCRYPTION_KEY=$(python -m backend.cli gen-key)
export API_SIGNING_SECRET=$(openssl rand -hex 32)
export DATABASE_URL=postgresql://user:pass@127.0.0.1:5432/aishops   # 不设置则用 SQLite
python -m backend.cli import data/seed/shops.json
uvicorn backend.main:app --port 8000
```

本机用无头浏览器截图时，UA 里的 `HeadlessChrome` 会被拦截，需要设置 `ALLOW_HEADLESS_UA=1`（只在本机自测用，线上不要设置）。
`run_local.sh` 会读取 `.env.local`（已在 .gitignore 里）。

## 服务器部署

```bash
cp .env.example .env && chmod 600 .env
# 编辑 .env：POSTGRES_PASSWORD、FIELD_ENCRYPTION_KEY、API_SIGNING_SECRET 三项必填（缺任何一项 compose 会直接报错，不会启动）
docker compose up -d --build
docker compose exec app python -m backend.cli import data/seed/shops.json
curl http://127.0.0.1:8000/healthz
```

- 构建前端用的 npm 镜像默认是腾讯云 `https://mirrors.cloud.tencent.com/npm/`，Python 依赖默认走腾讯云 PyPI。海外服务器可在 `.env` 里设置 `NPM_REGISTRY=https://registry.npmjs.org/`，PyPI 用 `--build-arg PIP_INDEX_URL=...` 覆盖。
- 发布请用 `deploy/redeploy.sh`：本机把提交推到 GitHub（SSH 经服务器中转，因为本机直连 GitHub 可能被拦），服务器在 `/opt/ai_shops-src` 执行 `git pull`，再在本机 rsync 到 `/opt/ai_shops` 并 `docker compose build && up -d`。不会覆盖 `.env`、`incoming/`、`backups/`、`logs/`、`bin/`。不要用跨境 rsync/scp 传整份代码。
- 构建在服务器上进行，首次构建需要拉取 node 和 python 镜像，耗时取决于网络；`deploy/redeploy.sh` 给 `docker compose build` 的时限是 14 分钟。
- app 默认只监听 `127.0.0.1:8000`，Postgres 不对外开放。对外访问见下面「HTTPS」。
- **升级已有部署前**：先在服务器 `.env` 加上 `FIELD_ENCRYPTION_KEY` 和 `API_SIGNING_SECRET`（缺任何一项 compose 会直接报错），再发布，再执行一次加密迁移。顺序见「字段加密」。

## 每日数据更新（流程没有变化）

采集器产出与 `shops.json` 同格式的 JSON（含 `listings`），导入入口不变：

```bash
docker compose exec app python -m backend.cli import incoming/2026-11-17.json
```

`deploy/push_update.sh` 和服务器上的 `import_incoming.sh` 就是这么调用的，不用改。每次导入新增一条 `crawl_runs`；相同内容的文件会被拒绝（加 `--force` 强制）。
导入器用 ORM 写库，字段加密对它是透明的：写入时自动加密，读取时自动解密。

## 字段加密（应用层）

| 表.列 | 方式 | 说明 |
|---|---|---|
| shops.primary_url / final_url / all_urls / example_post_url / notes | Fernet（随机） | 店铺链接 |
| listings.url / source_url / image | Fernet（随机） | 商品链接、来源接口、图片地址 |
| x_posts.url / author / text | Fernet（随机） | 帖子链接、作者、正文 |
| shops.shop_key / shops.domain | AES-SIV（确定性） | 仍可做等值匹配、唯一约束，导入器按它 upsert |
| promoter_accounts.username | AES-SIV（确定性） | 是主键的一部分 |

- 密钥：环境变量 `FIELD_ENCRYPTION_KEY`（Fernet 密钥，`python -m backend.cli gen-key` 生成）。AES-SIV 的密钥由它派生。**丢了密钥，加密字段就无法恢复**，请另存一份到密码管理器。
- 密文带前缀 `enc1:` / `encd:`。读取时遇到没有前缀的旧明文会原样返回，所以迁移前后应用都能正常工作。
- 迁移现有明文：

```bash
python -m backend.cli encrypt-existing --dry-run   # 只统计
python -m backend.cli encrypt-existing             # 加密（幂等，可重复执行）
python -m backend.cli verify-encryption            # 检查是否还有明文，全为 0 才退出码 0
# Docker：docker compose exec app python -m backend.cli encrypt-existing
```

  迁移会先把 Postgres 里相关列放宽为 `text`（旧库里有 varchar 和 jsonb）。建议迁移前先备份。
- 局限（请如实看待）：
  - 应用服务器上同时有密钥和数据，应用被攻破时加密不起作用。它防的是数据库被单独拿走（备份泄露、SQL 注入读表、DBA 误操作）。
  - 确定性加密不隐藏「两个值是否相同」。`shops.name`、商品标题、价格、规格没有加密，因为页面要展示和搜索。很多店铺的名字本身就是域名，所以**店铺域名不算秘密**。
  - 轮换密钥：`FIELD_ENCRYPTION_KEY=新密钥,旧密钥`，随机加密的字段读取时会自动兼容旧密钥；但确定性字段（shop_key、domain、username）只认第一个密钥，轮换需要先用旧密钥解密再用新密钥重加密（目前没有写这个脚本）。

### 数据库加密（数据卷与备份）

- **数据卷**：用 LUKS 加密 Postgres 数据目录，见 `scripts/luks_volume.sh`，然后在 `.env` 设置 `PGDATA_PATH` 指向挂载点。**这个脚本在开发机上没有实测**（没有 root 和 cryptsetup），上线前请先在测试机走一遍。它防的是磁盘、快照被整体拿走；服务运行时数据卷处于挂载状态，数据是可读的。口令需要每次开机手动输入，不要把口令放在服务器上。
- **备份**：`scripts/backup_encrypted.sh`，`pg_dump | gzip | gpg 或 age`，明文不落盘，没设置收件人公钥就拒绝运行，默认保留最近 7 份并写 sha256。

```bash
# 在你自己的电脑上生成密钥对，只把公钥放到服务器：
gpg --quick-generate-key "aishops-backup" rsa3072 encr 2y       # 或：age-keygen -o age-key.txt
gpg --export -a aishops-backup | ssh 服务器 gpg --import        # 只导入公钥
# 服务器上：
BACKUP_GPG_RECIPIENT=aishops-backup ./scripts/backup_encrypted.sh        # 或 BACKUP_AGE_RECIPIENT=age1...
# 定时（每天 03:15）：
15 3 * * * cd /opt/ai_shops && BACKUP_GPG_RECIPIENT=aishops-backup ./scripts/backup_encrypted.sh >> logs/backup.log 2>&1
# 还原（在持有私钥的机器上）：
RESTORE_CMD="psql postgresql://用户:密码@主机/库" ./scripts/restore_encrypted.sh backups/aishops-xxx.sql.gz.gpg
./scripts/restore_encrypted.sh backups/aishops-xxx.sql.gz.gpg -     # 只解密查看，不还原
```

  服务器上现有的 `/opt/ai_shops/bin/backup_db.sh`（明文 gzip）仍在每天运行，切换到加密备份后请停掉它，并删除旧的明文备份。

## 防爬措施（只提高门槛，挡不住一切）

浏览器必须拿到解密密钥才能显示数据，所以任何愿意花功夫的人都能自己实现客户端来抓取；下面这些让「随手写个脚本抓一遍」不再可行，并且让大规模抓取留下痕迹、受到限速。

1. **响应加密**：`GET /api/v4/session` 按会话下发 32 字节密钥（有效期 20 分钟，无状态，由服务端密钥派生；绑定 User-Agent 而不是 IP，所以手机在 Wi-Fi 和流量之间切换不会失效。UA 绑定很弱，伪造 UA 就能绕过，限流仍按 IP 做）。所有数据接口的响应都是 AES-256-GCM 密文，请求随机数作为附加认证数据，响应与请求绑定。
2. **请求签名**：每个请求带 `X-Sid / X-Ts / X-Nonce / X-Sig`，签名为 `HMAC-SHA256(会话密钥, 方法 + 路径含查询 + 时间戳 + 随机数)`。时间戳允许偏差 90 秒（前端按服务器时间校正），随机数一次性，重放会被拒绝。前端遇到 401 会自动换一次会话并重发原请求，只重试一次。
3. **按 IP 限流**：每个 IP 每分钟 `/api/` 120 次、取会话 20 次、`/go/` 40 次，超限返回 429。内存滑动窗口，单进程有效；nginx 模板里还有一层 `limit_req`。
4. **必须分页**：店铺列表、报价列表每页最多 30 条，页码最多 40，没有一次返回全量的接口。
5. **跳转走后端**：接口里只有 `/go/<令牌>`，令牌是 `店铺编号.商品编号.签名`，带签名所以不能枚举；`/go/` 校验后 302 到真实链接，并带 `Referrer-Policy: no-referrer`。接口 JSON 里不出现任何 http/https 链接（自测脚本逐项检查）。
6. **基础 UA / Bot 拦截**：空 UA，以及 curl、wget、python、requests、httpx、scrapy、go-http、java、headless、playwright 等常见抓取工具的 UA，返回 403；跨站来源（`Sec-Fetch-Site: cross-site`）被拒绝。伪造浏览器 UA 就能绕过这一条，它只挡最省事的脚本。
7. 旧的明文接口（`/api/shops`、`/api/tools` 等）已删除。
8. 前端的 AES-GCM / HMAC 用纯 JS（noble）实现，而不是 WebCrypto，因为 WebCrypto 在 http 页面里不可用，而站点可能先用 IP + HTTP 访问。

自测：`.venv/bin/python scripts/selftest_api.py`（25 项：解密、重放、篡改、过期、UA、跨站、旧接口、分页上限、无真实链接、302、令牌伪造、响应头、429）。

## HTTPS 与 nginx（域名最后才配）

> 服务器上已有 OpenSubs 占用 443 端口和 IP 证书。**下面所有步骤都先确认再做，不要覆盖、不要重启它。**

模板在 `deploy/nginx/`：`aishops-domain.conf.template`（80 签发证书与跳转 + 443 站点）、`aishops-proxy.conf`（反代公共配置）。

共存方式：只新增 `server_name` 为你域名的 server 块，**不写 `default_server`**，不改任何已有配置。同一个 nginx 会按 SNI/Host 分流：OpenSubs 的域名和 `https://IP` 仍走它原来的块，本站域名走新块。

1. 先查看现状（只读）：`sudo ss -ltnp | grep -E ':(80|443)\b'`、`sudo nginx -T | grep -nE "listen|server_name|ssl_certificate"`。确认 443 是不是同一个 nginx、已有的 server_name 里有没有你的域名、有没有 `default_server`。**不确定就停下来先问。**
2. 域名 A 记录指向服务器。
3. 复制模板：把 `YOUR_DOMAIN` 全部替换成域名，放到 `/etc/nginx/conf.d/aishops-domain.conf`；`aishops-proxy.conf` 放到 `/etc/nginx/aishops-proxy.conf`。
4. 先只启用 80 的块拿证书（暂时注释掉 443 那个 server 块，因为证书还不存在），`sudo nginx -t && sudo systemctl reload nginx`。
5. 用 certbot 的 webroot 方式签发（**不要用 `certbot --nginx`**，它会改写其他站点的配置）：
   ```bash
   sudo mkdir -p /var/www/certbot
   sudo certbot certonly --webroot -w /var/www/certbot -d YOUR_DOMAIN
   ```
6. 取消注释 443 块，`sudo nginx -t`（通过才继续），`sudo systemctl reload nginx`（不要 restart）。
7. 验证：`curl -I https://YOUR_DOMAIN/healthz`；同时确认 `https://服务器IP` 和 OpenSubs 的域名行为没变。
8. HSTS 模板里先是 `max-age=300`，确认一切正常后再改成 `31536000`。没有加 `includeSubDomains` 和 `preload`，避免波及同域名下 OpenSubs 的子域名。
9. 证书续期：certbot 自带定时任务，`sudo certbot renew --dry-run` 验证一次。
10. 不想碰 443：把模板里的 `listen 443` 改成其他端口（例如 8443），用 `https://域名:8443` 访问。

安全响应头：CSP、`X-Content-Type-Options`、`X-Frame-Options`、`Referrer-Policy`、`Permissions-Policy`、`Cross-Origin-Opener-Policy` 由应用返回（`backend/main.py`），HSTS 由 nginx 返回。

## 品牌与 logo

- 站名「AI 订阅比价」。logo 是三根递减的价格柱，最低的一根用琥珀色，字标「AI 订阅比价」取自 Noto Sans CJK SC Bold（SIL OFL 1.1）并转成轮廓，不依赖字体文件。
- 文件在 `web/public/`：`logo.svg`（图形+字标）、`logo-light.svg`（反白）、`logo-mark.svg`、`favicon.svg`、`favicon.ico`、`favicon-16/32/48.png`、`apple-touch-icon.png`、`icon-192/512.png`、`site.webmanifest`。
- 重新生成：`python web/brand/make_brand.py`（需要 fonttools、pillow、playwright）。
- 商品 logo 在 `web/public/logos/`，来源与许可见该目录的 `README.md` 和 `SOURCES.md`。

## 测试

```bash
python -m unittest crawler.test_pipeline            # 采集/导入的回归测试（有无加密密钥都应通过）
python scripts/selftest_api.py                      # 接口防护
python scripts/audit_ui.py                          # 320/375 宽度溢出、键盘焦点、方向键、路由焦点
python shoot4.py                                    # 截图到 shots/v4_*.png
```

## 已知限制

- 限流是内存里的，单进程有效；多进程或多实例部署需要换成共享存储（例如 Redis）。
- `crawler/verify_ui.py` 是旧界面的验证脚本，依赖旧页面的结构，新界面下不能直接用（采集器本身不受影响）。
- 没有迁移工具：表由 `create_all` 创建，字段加密需要的列类型放宽由 `init_db()` 自动处理，其余结构改动要手写 SQL。
