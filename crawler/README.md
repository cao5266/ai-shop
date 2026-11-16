# 每日店铺商品采集

版本管理源码在 `app/crawler/`；工作区每日入口是 `/workspace/ai_shops/crawler/run_daily.sh`，它调用本目录的版本化入口。

```bash
cd /workspace/ai_shops/app
.venv/bin/pip install -r crawler/requirements.txt
.venv/bin/python -m playwright install chromium
bash /workspace/ai_shops/crawler/run_daily.sh
```

默认检查 `../shops.json` 全部记录，生成 `../crawler/reports/YYYY-MM-DD.json`、中文报告和证据，随后调用 `../deploy/push_update.sh` 导入线上。以北京时间命名，锁防止重复运行。失败店铺不删除上次成功报价；成功完整列表中的下架/售罄商品退出比价。历史与新报价均保留采集时间。

仅采集（不上推）：`AI_SHOPS_SKIP_PUSH=1 bash /workspace/ai_shops/crawler/run_daily.sh`。

单店诊断：`AI_SHOPS_SKIP_PUSH=1 bash /workspace/ai_shops/crawler/run_daily.sh --only S430922 --output /tmp/opencode/shop-probe`。诊断用独立输出目录，避免覆盖当日全量快照。

定时示例（宿主机拥有既有 SSH 密钥与 Python 环境）：

```cron
15 7 * * * /bin/bash /workspace/ai_shops/crawler/run_daily.sh >> /workspace/ai_shops/crawler/reports/daily.log 2>&1
```

环境变量：`AI_SHOPS_INPUT`、`AI_SHOPS_REPORT_DIR`、`AI_SHOPS_PYTHON`，以及部署脚本的 `AI_SHOPS_SSH_HOST/KEY/REMOTE_DIR`。每次报告末尾记录线上导入成功或失败，失败退出非零；可直接用 `push_update.sh 当天.json` 重试。

适配器：

- `platform.py`：16688 新鲸发系统，商品详情入口反查商店编号，读取全部分类和商品。
- `catfk.py`：catfk/wzyp 旧鲸发系统，按商品类型分页。
- `public_api.py:NextAdapter`：Dujiao Next 公开 products API，逐页、逐 SKU 读取，保留规格、库存及图。
- `public_api.py:YiciAdapter`：异次元类公开分类与商品接口，遍历子分类，去重。
- `generic.py:DujiaoAdapter`：独角数卡 HTML 商品卡与 GET 商品链接。
- `generic.py:GenericAdapter`：独立站 JSON-LD 和明确商品卡，静态失败后 Chromium 渲染。
- Telegram：仅记录，不发网络采集。

`registry.json` 的 `domains` 指定同系统复用；`shops[shop_key]` 支持 `adapter/card/title/price/category` 覆盖。新增系统应先检查 `reports/evidence/日期/*.network.json`，只加入已确认只读的商品查询。浏览器不点击按钮、不填表，POST 只允许明确列出的商品查询接口，访问统计/订单/支付/注册/登录请求阻止。全局默认 8 并发，每域串行且间隔 650ms；Chromium 单并发以控制资源。

接口证据 `*.api.json`、浏览器 HTML/网络响应、逐店 `*.result.json` 保存在证据目录。失败原因写入 JSON 的 `crawl`，导入 `shop_crawl_results`。首次及涨跌入 `listing_price_history`；重复价格不重复追加。价格比较键含商品、期限、额度、套餐、区域和交付，信息不完整时加原标题隔离。裸金额和 X 帖报价不参与商品规格比价。

验证：`.venv/bin/python -m unittest crawler.test_pipeline -v`；`.venv/bin/python -m crawler.verify_ui --base http://101.34.76.198 --prefix v3`。

代表规格优先人民币入门月付（Grok Plus、其次 Premium），同档同周期按覆盖店铺数量选取；库存为零退出在售统计。售罄标价仍可在卡片和详情查看。Copilot 的两条历史关联经商品页核实均不证明在售，详见 `product_notes.json`，前端显示具体原因。

抽查：`.venv/bin/python -m crawler.audit_prices`，重新读取10个标准商品代表规格的最低价详情，输出 `YYYY-MM-DD-audit.md/json`，包含标题、金额、规格、URL及实际响应。遇到本机出口间歇拦截，可从已配置的部署机执行同一只读详情查询。此次归类修正规则的回归测试覆盖 Netflix/MiniMax、普号/白号、接🐎/注册号、多品牌组合与售后时长。
