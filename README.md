# AI 订阅店铺速查

汇总 X 上推广的 AI 工具订阅代充、发卡店铺，支持搜索、按商品/风险/类型筛选、按提及数或价格排序、按商品比价。
所有数据存在数据库里，通过导入命令更新；页面不写死任何数据。

> 站内所有店铺都是**非官方渠道**，可能违反官方服务协议，本站**不担保任何交易**。页面顶部和底部都有常驻声明，请勿删除。

## 技术栈

- 后端：Python 3.13、FastAPI、SQLAlchemy 2、psycopg 3
- 数据库：PostgreSQL（生产）；未设置 `DATABASE_URL` 时回退到本地 SQLite（仅开发）
- 前端：原生 HTML/CSS/JS，无构建步骤，由 FastAPI 直接托管。标题字体 Noto Serif SC（SIL OFL 1.1，已裁剪为 GB2312 一级字，自托管），正文用系统中文字体
- 部署：Docker Compose（app + postgres）

## 目录

```
backend/        models.py 表结构 · importer.py 导入逻辑 · cli.py 命令行 · main.py 接口与静态托管
static/         前端页面
data/seed/      首批数据 shops.json（224 家）
incoming/       每天的新采集 JSON 放这里（不进 git）
shoot.py        用 Playwright 截图
```

## 服务器部署（Linux + Docker）

1. 安装 Docker 与 Compose 插件（官方文档：docs.docker.com/engine/install）。
2. 上传代码并配置环境变量：
   ```bash
   cd app
   cp .env.example .env
   # 编辑 .env，至少改掉 POSTGRES_PASSWORD
   ```
3. 启动：
   ```bash
   docker compose up -d --build
   docker compose ps          # db 为 healthy、app 为 running
   ```
   表会在 app 启动时自动创建。
4. 首次导入数据：
   ```bash
   docker compose exec app python -m backend.cli import data/seed/shops.json
   ```
5. 验证：`curl http://127.0.0.1:8000/healthz` 返回 `{"ok":true}`，浏览器访问页面能看到 224 家店铺。
6. 对外访问：app 默认只监听 `127.0.0.1:8000`，Postgres 不对外开放。请用 Nginx 或 Caddy 反代并配置 HTTPS，例如 Caddy：
   ```
   your-domain.com {
       reverse_proxy 127.0.0.1:8000
   }
   ```
   防火墙只放行 80、443（和 SSH）。

## 每日增量更新

采集程序产出和 `shops.json` 同格式的 JSON（顶层 `generated_at`、`scope`、`shops[]`），放到 `incoming/` 后导入：

```bash
docker compose exec app python -m backend.cli import incoming/2026-11-17.json
```

每次导入都会新增一条 `crawl_runs` 记录，页面上的「数据更新于」取自最近一次成功的 crawl_run。可以用 cron 每天执行：

```cron
30 9 * * * cd /opt/ai-shops/app && docker compose exec -T app python -m backend.cli import incoming/$(date +\%F).json >> /var/log/ai-shops-import.log 2>&1
```

导入规则：

- 店铺按 `shop_key` upsert，记录 `first_seen_at`、`last_seen_at`；批次里没出现的店铺不会被删除，只是 `last_seen_at` 不再更新。
- 报价按（店铺，来源，标签）upsert，`last_seen_at` 每次更新；首次出现或金额变化时才往 `price_history` 追加一行。
- 风险标记以最新批次为准，不再出现的置为 `active=false`（保留历史），风险等级每次重新计算。
- X 帖子 ID 与抽样文案只增不删；`n_posts` 取「批次里的数字」与「库中已知帖子 ID 数」的较大者，所以每日批次即使覆盖范围较小，提及数也不会倒退。
- 完全相同的文件（SHA-256 相同）再次导入会被拒绝，加 `--force` 可强制。导入失败时整批回滚，并留一条 `status=failed` 的 crawl_run。
- 查看最近几次导入：`docker compose exec app python -m backend.cli runs`

## 备份与升级

```bash
docker compose exec db pg_dump -U aishops aishops | gzip > backup-$(date +%F).sql.gz
git pull && docker compose up -d --build
```

当前没有迁移工具：表由 `create_all` 创建，之后改表结构需要手写 SQL（或引入 Alembic）。

## 本地开发

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
# 用 SQLite：什么都不用设置；用 Postgres：export DATABASE_URL=postgresql://user:pass@127.0.0.1:5432/aishops
python -m backend.cli import data/seed/shops.json
uvicorn backend.main:app --port 8000
```

## 接口

`GET /api/meta`、`/api/shops?q=&product=&risk=&type=&sort=&page=`、`/api/shops/{id}`、`/api/products`、`/api/products/{名称}/offers`、`/api/runs`、`/healthz`。

## 数据说明

- 价格只来自帖文里写明的「商品 + 数字 + 元」和页面上读到的金额，没有的留空，不估算。
- 「最低价」只取帖文里带标签的报价；页面上的金额没有商品标注，只在详情里显示。
- 风险等级由文案规则自动判断（见页面「风险说明与数据来源」），可能有误判。
