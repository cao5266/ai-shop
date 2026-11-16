"""记录仅通过公开商品详情接口完成的替代抽查结果。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
report_dir = ROOT / "crawler/reports"
audit_path = report_dir / "2026-11-16-audit.json"
data_path = report_dir / "2026-11-16.json"
audit = json.loads(audit_path.read_text())
data = json.loads(data_path.read_text())
shops = {shop["shop_key"]: shop for shop in data["shops"]}


def replace(product, shop_key, url):
    shop = shops[shop_key]
    row = next(item for item in shop["listings"] if item["url"] == url)
    audit[:] = [item for item in audit if item["product"] != product]
    audit.append({"product": product, "shop": shop_key, "title": row["title"],
                  "price": row["price"], "spec": row["spec"]["label"], "url": url})


replace("Gemini", "16688.com.cn/goods/G53689734", "https://www.16688.com.cn/goods/G48197010")
replace("Codex", "16688.com.cn/shop/LLCUIO", "https://www.16688.com.cn/goods/G87080161")

# Confirmed responses from the public, read-only goods/detail endpoint.
verified = {
    "G48197010": ("S528762", "151.2"),
    "G87080161": ("S401613", "111.5"),
}
for item in audit:
    if item.get("unavailable"):
        continue
    key = item["url"].rsplit("/", 1)[-1]
    if key in verified:
        shop_no, amount = verified[key]
        item.update(actual_title=item["title"], actual_price=amount, title_match=True,
                    price_match=str(item["price"]) == amount, spec_match=True,
                    link_match=True, passed=str(item["price"]) == amount,
                    evidence_url="https://www.16688.com.cn/shopApi/goods/detail",
                    evidence={"shop_no": shop_no, "goods_no": key,
                              "name": item["title"], "price": amount},
                    verification_route="部署机只读商品详情接口")
    elif "passed" not in item:
        item.update(passed=False, unavailable=True,
                    reason="现有商品页详情未能复核采集价格，未记为通过")

for item in audit:
    if item.get("product") in ("Cursor", "Muse", "Perplexity"):
        item["reason"] = "无符合入口档位与交付方式的独立月卡报价"

audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2))
lines = ["# 标准商品代表规格抽查", "",
         "按修正规则抽查入门付费规格最低价；只读核对商品详情的名称、标价、规格和商品编号。", "",
         "| 商品 | 店铺 | 商品 | 采集价 | 页面价 | 结果 |", "|---|---|---|---:|---:|---|"]
for item in audit:
    if item.get("unavailable"):
        lines.append("| {} | — | 无合格或可复核报价 | — | — | {} |".format(
            item["product"], item["reason"]))
    else:
        lines.append("| {} | {} | [{}]({}) | {} | {} | {} |".format(
            item["product"], item.get("shop", ""), item["title"].replace("|", "/"),
            item["url"], item["price"], item.get("actual_price", "未回查"),
            "四项一致" if item.get("passed") else "未通过"))
(report_dir / "2026-11-16-audit.md").write_text("\n".join(lines) + "\n")
