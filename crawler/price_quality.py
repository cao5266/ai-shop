"""Early, configurable price-quality flags used for public starting prices."""
from __future__ import annotations

import os
import re
import statistics


def _configured_ratio() -> float:
    try:
        value = float(os.environ.get("AI_SHOPS_LOW_PRICE_MEDIAN_RATIO", "0.45"))
    except (TypeError, ValueError):
        value = 0.45
    return value if 0.05 <= value < 1 else 0.45


LOW_PRICE_MEDIAN_RATIO = _configured_ratio()
def _configured_cny_floor() -> float:
    try:
        value = float(os.environ.get("AI_SHOPS_MIN_CNY_PRICE", "1.0"))
    except (TypeError, ValueError):
        value = 1.0
    return value if 0 <= value < 10000 else 1.0


MIN_CNY_PRICE = _configured_cny_floor()
MIN_MEDIAN_SAMPLES = 3
NON_COMPARABLE_PATTERNS = (
    (re.compile(r"教程|教学|使用指南|仅认证|学生认证|共享车位|拼车|合租|代付|代拍|补差价|升级差价|仅手续费|测试价|批发专用|\d+个起发|upi渠道"),
     "标题表明是教程、认证、共享或非完整商品，需人工质检"),
)


def obvious_price_issue(title: str) -> str | None:
    text = re.sub(r"\s+", "", str(title or "").lower())
    for pattern, reason in NON_COMPARABLE_PATTERNS:
        if pattern.search(text):
            return reason
    return None


def assess_price_group(rows, ratio: float | None = None, currency: str = "CNY") -> list[str | None]:
    """Return a per-row reason. Rows are (price, title) tuples in one spec/currency."""
    ratio = LOW_PRICE_MEDIAN_RATIO if ratio is None else ratio
    obvious = [obvious_price_issue(title) for _, title in rows]
    comparable = [float(price) for (price, _), reason in zip(rows, obvious)
                  if reason is None and price is not None and float(price) > 0]
    median = statistics.median(comparable) if len(comparable) >= MIN_MEDIAN_SAMPLES else None
    reasons = []
    for (price, _), reason in zip(rows, obvious):
        if reason:
            reasons.append(reason)
        elif currency == "CNY" and float(price) > 0 and float(price) < MIN_CNY_PRICE:
            reasons.append(f"低于配置的人民币最低可信价 {MIN_CNY_PRICE:g}")
        elif median is not None and float(price) < median * ratio:
            reasons.append(f"低于同规格中位数的 {ratio:.0%}（中位数 {median:g}）")
        else:
            reasons.append(None)
    return reasons
