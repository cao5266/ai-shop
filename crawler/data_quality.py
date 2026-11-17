"""Versioned, repeatable rules for cleaning offer data and choosing entry prices."""
from __future__ import annotations

import csv
import re
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path


HITS_PATH = Path(__file__).with_name("data_quality_hits.csv")


def _text(value: str) -> str:
    return re.sub(r"[\s\u3000]+", "", str(value or "").casefold())


def _price(value) -> str:
    try:
        return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")
    except (InvalidOperation, ValueError):
        return str(value)


@lru_cache(maxsize=1)
def _hit_index():
    index = {}
    if not HITS_PATH.exists():
        return index
    with HITS_PATH.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = (_text(row.get("shop")), _text(row.get("title")), _price(row.get("price")))
            index.setdefault(key, []).append(row)
    return index


def reviewed_hit(shop_key: str, shop_name: str, title: str, price):
    """Match the reviewed 449-row audit against either store key or display name."""
    index = _hit_index()
    title_key, amount = _text(title), _price(price)
    for store in (shop_key, shop_name):
        hits = index.get((_text(store), title_key, amount))
        if hits:
            return hits[0]
    return None


HARD_EXCLUSION_PATTERNS = (
    (re.compile(r"暂时下架|已下架|占位|充值成功|真实用户反馈|开通成功截图"), "下架占位或反馈内容，不是有效商品报价"),
    (re.compile(r"学生|教育认证|sheerid|认证可得|一次卡|激活链接|兑换链接|领取链接|优惠链接|自己绑卡|需绑定手机|仅提取|非成品号|不是成品|非账号|非会员|不含会员|不带会员"), "学生资格、链接或非账号权益，不是可交付商品"),
    (re.compile(r"定金|订金|押金|补差|差价|尾款|续费专用|升级费|手续费|邮费|运费|补款"), "定金、续费或附加费用，不是新购完整商品"),
    (re.compile(r"试用|体验|日抛|速刷|按次|单次|一次卡|天卡|周卡|小时卡"), "试用或短期按次商品，不参与订阅比较"),
    (re.compile(r"批发专用|\d+个起发|起发|量大|代理价|渠道价|拿货|批量发"), "批发/起发单价，不是零售可比价"),
)


# R11. Floors are separated by product, normalized tier and delivery type.
PRICE_FLOORS = {
    ("ChatGPT Plus", "plus", "代充"): 75, ("ChatGPT Plus", "plus", "成品号"): 35,
    ("ChatGPT Pro", "pro100", "代充"): 600, ("ChatGPT Pro", "pro100", "兑换码"): 600,
    ("ChatGPT Pro", "pro100", "成品号"): 550,
    ("ChatGPT Pro", "pro200", "代充"): 950, ("ChatGPT Pro", "pro200", "兑换码"): 950,
    ("ChatGPT Pro", "pro200", "成品号"): 800,
    ("ChatGPT Pro", "pro500", "代充"): 3000, ("ChatGPT Pro", "pro500", "兑换码"): 3000,
    ("ChatGPT Pro", "pro500", "成品号"): 2500,
    ("Claude Pro", "pro", "代充"): 130, ("Claude Pro", "pro", "成品号"): 200,
    ("Claude Max", "max5x", "代充"): 750, ("Claude Max", "max5x", "成品号"): 750,
    ("Claude Max", "max20x", "代充"): 1400, ("Claude Max", "max20x", "成品号"): 1200,
    ("Grok Plus", "plus", "代充"): 50, ("Grok Plus", "plus", "成品号"): 35,
    ("Grok Premium", "premium", "代充"): 100, ("Grok Premium", "premium", "成品号"): 60,
    ("Grok Super", "super", "代充"): 150, ("Grok Super", "super", "成品号"): 150,
    ("Grok Ultra", "ultra", "代充"): 450, ("Grok Ultra", "ultra", "成品号"): 400,
    ("Gemini", "pro", "代充"): 15, ("Gemini", "pro", "成品号"): 15,
    ("Gemini", "ultra5x", "代充"): 450, ("Gemini", "ultra5x", "成品号"): 250,
    ("Gemini", "ultra20x", "代充"): 900, ("Gemini", "ultra20x", "成品号"): 500,
    ("Codex", "go", "代充"): 29, ("Codex", "go", "兑换码"): 29,
    ("Codex", "plus", "代充"): 75, ("Codex", "plus", "成品号"): 60,
    ("Codex", "pro100", "代充"): 600, ("Codex", "pro100", "兑换码"): 600,
    ("Codex", "pro100", "成品号"): 438,
    ("Codex", "pro200", "代充"): 950, ("Codex", "pro200", "兑换码"): 950,
    ("Codex", "pro200", "成品号"): 800,
    ("Codex", "pro500", "代充"): 3000, ("Codex", "pro500", "兑换码"): 3000,
    ("Muse", "credit", "成品号"): 1.5, ("Muse", "credit", "Token号"): 1.5,
}


def _tier(spec: dict, title: str = "") -> str:
    values = spec.get("tier") or []
    if isinstance(values, str): values = [values]
    text = " ".join(str(x).lower() for x in values) + " " + str(title).lower()
    compact = re.sub(r"[\s_-]+", "", text)
    if re.search(r"max\s*20x|20x\s*max", text): return "max20x"
    if re.search(r"max\s*5x|5x\s*max", text): return "max5x"
    for n, tier in ((500, "pro500"), (200, "pro200"), (100, "pro100")):
        if re.search(rf"pro\s*{n}|{n}\s*(?:刀|美元|\$)|(?:{n//10}|{n//10+5})x", text): return tier
    if re.search(r"ultra\s*(?:5x|x5)|(?:5x|x5)\s*ultra", text): return "ultra5x"
    if re.search(r"ultra\s*(?:20x|x20)|(?:20x|x20)\s*ultra", text): return "ultra20x"
    if re.search(r"grok\s*super|gr0k\s*super|supergrk", text): return "super"
    if "ultra" in compact or "ulrta" in compact or "uitra" in compact or "heavy" in compact: return "ultra"
    if "premium" in compact: return "premium"
    if re.search(r"\bgo\b|codexgo", text): return "go"
    for value in values:
        item = re.sub(r"\s+", "", str(value).lower())
        if item in {"plus", "pro", "max", "super", "ultra", "premium"}: return item
    return ""


def price_floor_reason(product: str, spec: dict, title: str, price, currency="CNY"):
    if currency != "CNY": return None
    tier = _tier(spec, title)
    delivery = str(spec.get("delivery") or "未注明交付")
    p = float(price)
    if product == "Muse":
        quota = " ".join(map(str, spec.get("quota") or [])) + " " + title
        if re.search(r"10亿|1b", quota, re.I) and p < 1.5: return "低于 Muse 10 亿 token 成品号底价 ¥1.50"
        if re.search(r"310亿|31b", quota, re.I) and p < 4.5: return "低于 Muse 310 亿 token 底价 ¥4.50"
    floor = PRICE_FLOORS.get((product, tier, delivery))
    if floor is None or p >= floor: return None
    text = re.sub(r"\s+", "", title.lower())
    if re.search(r"菲区|菲律宾|美区|越南|尼区|尼日利亚|半价|促销|优惠|账号|成品号|车位|家庭组|拼车", text):
        return f"低于该商品/档位/交付底价 ¥{floor:g}，属区域、促销、账号或共享规格，不计标准起价"
    return f"低于该商品/档位/交付底价 ¥{floor:g}，需剔除"


def assess_listing(shop_key: str, shop_name: str, title: str, price, product: str | None, spec: dict, currency="CNY"):
    """Return deterministic quality fields; never edits/deletes the source evidence."""
    result = {"keep": True, "comparison_exclusion": None, "price_anomaly": False,
              "price_anomaly_reason": None, "quality_action": None,
              "quality_review_required": False, "quality_review_reason": None,
              "quality_flags": []}
    hit = reviewed_hit(shop_key, shop_name, title, price)
    if hit:
        action, reason = hit["action"], hit["reason"]
        result["quality_action"] = action
        result["quality_flags"].append(reason)
        if action == "剔除":
            result["keep"] = False; result["comparison_exclusion"] = reason
        elif action in {"不计起价", "复核"}:
            result["price_anomaly"] = True; result["price_anomaly_reason"] = reason
            if action == "复核":
                result["quality_review_required"] = True; result["quality_review_reason"] = reason

    if not product:
        return result
    normalized = _text(title)
    if float(price) >= 9999 and not re.search(r"(?:年卡|年付|12个月|12月)", normalized):
        result["keep"] = False; result["comparison_exclusion"] = "价格达到 ¥9999 且非年付，按占位价剔除"
    for pattern, reason in HARD_EXCLUSION_PATTERNS:
        if pattern.search(normalized):
            result["keep"] = False; result["comparison_exclusion"] = reason
            break
    if result["keep"] and re.search(r"(?:\d+\s*[,，/、]\s*\d+\s*(?:个月|月|年|天)|\d+\s*[-–~至]\s*\d+\s*(?:天|月|年)|(?:5x\s*/\s*20x|20x\s*/\s*50x)|\d+\s*/\s*\d+\s*个月)", title, re.I):
        result["keep"] = False
        result["comparison_exclusion"] = "单标题包含多个周期/档位但无独立 SKU 价格，不能将单价挂到任一档位"
    floor_reason = price_floor_reason(product, spec, title, price, currency)
    if floor_reason:
        result["price_anomaly"] = True; result["price_anomaly_reason"] = result["price_anomaly_reason"] or floor_reason
        if "需剔除" in floor_reason:
            result["keep"] = False; result["comparison_exclusion"] = floor_reason
    return result


ENTRY_PROFILES = {
    "ChatGPT Plus": {"tier": "plus", "period": "1月", "delivery": "代充", "no_region": True},
    "ChatGPT Pro": {"tier": "pro100", "period": "1月", "delivery": ("代充", "兑换码"), "no_region": True},
    "ChatGPT Go": {"tier": "go", "period": "1月", "delivery": ("代充", "兑换码")},
    "Claude Pro": {"tier": "pro", "period": "1月", "delivery": "代充", "no_region": True},
    "Muse": {"quota_match": r"(?:10亿|1b)", "delivery": ("成品号", "Token号")},
    "Gemini": {"tier": "pro", "delivery": "成品号", "period_any": True},
}


def canonicalize_codex(product: str | None, title: str, spec: dict) -> tuple[str | None, str | None]:
    """Codex is an OpenAI subscription tier, not a standalone catalog product.

    Returns (catalog product, exclusion reason). Quota packs remain evidence but
    are intentionally outside subscription starting prices.
    """
    if product != "Codex":
        return product, None
    text = str(title or "").casefold()
    tiers = spec.get("tier") or []
    if isinstance(tiers, str): tiers = [tiers]
    tier_text = " ".join([str(x).casefold() for x in tiers] + [text])
    if spec.get("delivery") == "额度包" or re.search(r"\b\d+\s*(?:额度|积分|credits?)\b", text):
        return None, "Codex 额度包不属于 Go/Plus/Pro 订阅档位"
    if re.search(r"\bbusiness\b|\bteam\b|企业|团队", tier_text):
        return "ChatGPT Pro", None
    if re.search(r"\bgo\b|codexgo", tier_text):
        return "ChatGPT Go", None
    if re.search(r"\bplus\b", tier_text):
        return "ChatGPT Plus", None
    if re.search(r"\bpro\b|\b(?:100|200|500)\s*(?:刀|美元|\$)|\b(?:5x|10x|20x|25x|50x)\b", tier_text):
        return "ChatGPT Pro", None
    return None, "Codex 商品无法映射到 Go/Plus/Pro 档位，待人工复核"


def entry_profile_match(requested_product: str, group: dict) -> bool:
    product = str(group.get("product") or "")
    profile = ENTRY_PROFILES.get(product) or ENTRY_PROFILES.get(requested_product)
    if not profile: return False
    if profile.get("tier") and _tier({"tier": [group.get("tier") or ""]}) != profile["tier"]: return False
    if profile.get("period") and group.get("period") != profile["period"]: return False
    if not profile.get("period_any") and group.get("period") == "时长未注明" and profile.get("period"): return False
    delivery = group.get("delivery")
    if profile.get("delivery"):
        choices = profile["delivery"] if isinstance(profile["delivery"], tuple) else (profile["delivery"],)
        if delivery not in choices: return False
    label = str(group.get("label") or "")
    if profile.get("no_region") and (group.get("spec", {}).get("promotion") or "促销" in label or "半价" in label):
        return False
    if profile.get("quota_match") and not re.search(profile["quota_match"], label, re.I): return False
    if profile.get("no_region") and any(x in label for x in ("美区", "菲区", "越南", "尼日利亚", "土区")): return False
    return group.get("lowest_price") is not None
