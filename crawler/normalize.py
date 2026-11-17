"""保守归类：规格不明时保留原商品标题，绝不拿不同规格混比。"""
import hashlib
import re
from decimal import Decimal, InvalidOperation


def comparison_exclusion(title, product, spec, price):
    """只排除与标准商品无关的误匹配；价格异常不改变商品归属。"""
    if not product:
        return None
    t = re.sub(r"\s+", "", title.lower())
    if re.search(r"教程|教学|使用指南|支持列表|支持工具|工具导航|非卖品|仅展示|非商品", t):
        return "页面为教程/工具支持说明，不是该商品的在售报价"
    if product == "ChatGPT Plus" and re.search(r"minimax|真实用户反馈|开通成功截图|拼车.*(?:课程|教程)", t):
        return "商品标题主体属于其他工具或用户反馈内容，不是 ChatGPT Plus 商品"
    if spec.get("delivery") == "组合":
        return None
    # 标题主体已明确属于另一个产品，描述正文或分类里的提及不能算报价。
    other_patterns = {
        "Claude Pro": r"(?:gemini|grok|cursor|chatgpt|copilot|perplexity|midjourney|codex)",
        "Claude Max": r"(?:gemini|grok|cursor|chatgpt|copilot|perplexity|midjourney|codex)",
        "Copilot": r"(?:chatgpt|claude|cursor|gemini|grok|perplexity|midjourney|codex)",
        "Cursor": r"(?:chatgpt|claude|gemini|grok|perplexity|midjourney|copilot)",
        "Perplexity": r"(?:chatgpt|claude|cursor|gemini|grok|midjourney|copilot)",
    }
    if product in other_patterns and re.search(other_patterns[product], t):
        return "商品标题主体属于其他产品，当前标准商品仅为附带提及"
    return None


def classify(title, category=""):
    t = re.sub(r"[\s'’,，.·•。_-]", "", title.lower())
    t = re.sub(r"g\|p\|t", "gpt", t)
    c = category.lower()
    if re.search(r"接码|接马|接吗|接🐎|接🐴|接过码|接\*码|验证码|手机验证|登录验证|登陆验证|手机号|换绑邮箱|邮箱号|助力|代注册|注册号|注册服务|激活服务|邀请|补差价|升级差价|私人代充|白号|普号|free|虚拟卡|资格|绿色软件|镜像站|除codex|不是成品|不含|不包含|不带会员|没有会员", t): return None
    brands = [bool(re.search(rx, t)) for rx in (r"grok|gr0k|gork|supergrk|格洛克", r"cursor", r"gemini", r"muse", r"claude", r"copilot", r"perplexity")]
    if sum(brands) > 1: return None
    # 组合套餐不属于任一单品，避免 Grok 捆绑的 Cursor 权益变成 Cursor 订阅低价。
    for rx, name in [(r"codex", "Codex"), (r"muse", "Muse"), (r"cursor", "Cursor"),
                     (r"perplexity", "Perplexity"), (r"copilot", "Copilot"),
                     (r"midjourney|\bmj\b", "Midjourney"), (r"gemini", "Gemini"),
                     (r"telegram.*(?:premium|会员)|电报会员|tg会员", "Telegram会员")]:
        if re.search(rx, t):
            return name
    if re.search(r"grok|gr0k|gork|supergrk|格洛克|groplus", t):
        if re.search(r"(?:ulrta|uitra|heavy|ultra)", t): return "Grok Ultra"
        if re.search(r"(?:supergrk|grok\s*super|gr0k\s*super)", t): return "Grok Super"
        if re.search(r"premium", t): return "Grok Premium"
        if re.search(r"(?:plus|groplus|格洛克)", t): return "Grok Plus"
        return "Grok"
    if "claude" in t:
        if "max" in t: return "Claude Max"
        if "pro" in t: return "Claude Pro"
    if re.search(r"grok|gr0k|gork|supergrk|格洛克|groplus", t):
        matches = [(m.start(), m.group(1)) for m in re.finditer(r"(ultra|super|premium|plus)", t)]
        if matches: return "Grok " + min(matches)[1].capitalize()
        return "Grok"
    if re.search(r"(?:^|[【（(])x(?:[)）】]|会员|premium)|x[（(]推特|推特.*(?:会员|蓝标)|twitter.*(?:会员|premium)|xpremium|x推特.*(?:蓝标|会员)", t) and not re.search(r"netflix|minimax", t): return "X会员"
    if re.search(r"gpt|openai", t) or ("plus" in t and not re.search(r"claude|grok|gr0k|gork|gemini|office|microsoft|youtube|notion|netflix|spotify|minimax", t)):
        if "plus" in t and re.search(r"升级pro|升级到pro", t): return "ChatGPT Plus"
        if "pro" in t: return "ChatGPT Pro"
        if "plus" in t: return "ChatGPT Plus"
    return None


def combo_products(title):
    """识别明确组合商品，把同一组合报价挂到其涉及的标准商品下。"""
    t = title.lower()
    if not re.search(r"\+|三合一|多合一|组合|联合会员|打包", t):
        return []
    found = []
    if re.search(r"grok|gr0k|gork|supergrk", t):
        matches = [(m.start(), m.group(1)) for m in re.finditer(r"(ultra|super|premium|plus)", t)]
        tier = min(matches)[1] if matches else None
        found.append("Grok " + tier.capitalize() if tier else "Grok")
    if "cursor" in t: found.append("Cursor")
    if "gemini" in t: found.append("Gemini")
    if "muse" in t: found.append("Muse")
    if "claude" in t:
        found.append("Claude Max" if "max" in t else "Claude Pro" if "pro" in t else "Claude Pro")
    if "copilot" in t: found.append("Copilot")
    if "perplexity" in t: found.append("Perplexity")
    if re.search(r"twitter|推特|x会员|x蓝标", t): found.append("X会员")
    if re.search(r"gpt|openai", t): found.append("ChatGPT Pro" if "pro" in t and "plus" not in t else "ChatGPT Plus")
    if "midjourney" in t or re.search(r"mj(?:会员|代充|月卡|年卡|充值|订阅)", t): found.append("Midjourney")
    return list(dict.fromkeys(found))


def representative_rank(group):
    """入门月付优先；同档同周期内按覆盖店铺数选代表，价格不决定档位。"""
    spec = group.get("spec", {})
    tier_text = " ".join(spec.get("tier", [])).lower()
    product = group.get("product", "")
    advanced = bool(re.search(r"ultra|max|super|premium\+", product.lower() + " " + tier_text))
    # Grok Plus 是入口，Premium 次之；不让高档覆盖数压过入门月卡。
    if product == "Grok Plus": tier = 0
    elif product == "Grok Premium": tier = 1
    elif product.startswith("Grok"): tier = 3 if advanced else 2
    else: tier = 2 if advanced else 0
    monthly = spec.get("duration") == "1月"
    period = 0 if monthly else 1 if spec.get("duration") is None else 2
    return (group.get("currency") != "CNY", tier, period, spec.get("incomplete", True),
            -group.get("n_shops", group.get("n_prices", 0)), group.get("label", ""), group.get("key", ""))


def specification(title, product=None):
    from .data_quality import ENTRY_PROFILES
    t = re.sub(r"\s+", " ", title.lower())
    # Support shape is separate from normal access; it must not set subscription period.
    period_text = re.sub(r"(?:质保|保修|售后|首登|稳定|可用|有效期|双保)\s*[:：]?\s*(?:\d+|一|两|三|半)\s*(?:个)?\s*(?:天|日|周|个月|月|年|小时)", " ", t)
    period_text = re.sub(r"(?:质保|保修|保|售后|首登|稳定|可用|有效期|双保)\s*[:：]?\s*(?:一周|两周|半年)", " ", period_text)
    period_text = re.sub(r"\d{4}\s*年(?:\s*\d{1,2}\s*月)?|\d{1,2}\s*月\s*\d{1,2}\s*[号日]", " ", period_text)
    period_text = re.sub(r"\d+\s*小时(?:内)?\s*(?:自动)?\s*(?:充值|发货|到账|发码)", " ", period_text)
    period_text = re.sub(r"\b(?:pro|max)\s*\d+\b", " ", period_text)
    multi = bool(re.search(r"\d+\s*[,，/、]\s*\d+\s*(?:个)?\s*(?:月|年|天)|\d+\s*[-–~至到]\s*\d+\s*(?:个)?\s*(?:月|年|天)|(?:5x\s*/\s*20x|20x\s*/\s*50x)", period_text, re.I))
    duration = None
    if not multi:
        match = re.search(r"(\d+)\s*(?:个自然月|个月|月|年|天|日|周|小时)", period_text, re.I)
        if match:
            amount = int(match.group(1))
            unit = re.sub(r"^\d+\s*", "", match.group(0)).strip().lower()
            unit = unit.replace(" ", "")
            if unit in {"月", "个月", "个自然月"} and amount not in {100, 200, 500}:
                duration = "1年" if amount == 12 else f"{amount}月"
            elif unit == "年": duration = "1年" if amount == 1 else f"{amount}年"
            elif unit in {"天", "日"}:
                duration = {28: "1月", 29: "1月", 30: "1月", 31: "1月", 90: "3月", 360: "1年", 365: "1年"}.get(amount, f"{amount}天")
            elif unit == "周": duration = "7天" if amount == 1 else f"{amount * 7}天"
        if not duration:
            count = re.search(r"(\d+)\s*(?:次卡|次(?:充值|兑换|使用|订阅))", period_text)
            if count: duration = f"{int(count.group(1))}次"
        if not duration:
            for rx, val in [(r"半年|half[- ]?year", "6月"), (r"季度|季卡|季付", "3月"),
                            (r"年卡|年付|年费|一年|一整年|annual", "1年"),
                            (r"月卡|月付|月费|月订阅|包月|一个月|一月|monthly", "1月"),
                            (r"周卡|一周", "7天"), (r"永久|终身|终生|lifetime", "永久")]:
                if re.search(rx, period_text): duration = val; break
    # Chinese text has no word-boundary around these terms; don't use \b here.
    if not duration and not multi and re.search(r"subscription|订阅|官方充值|代充|直充|卡密|充值套餐|月卡|月付", t):
        duration = "1月"
    period_default = duration == "1月" and not re.search(r"\d+\s*(?:月|年|天|日|周)", period_text)
    period_na = not duration and bool(re.search(r"(?:成品号|成品账号|账号|帐号|token)", t))

    shared = bool(re.search(r"拼车|车位|共享|合租|家庭组|子账号|席位|成员位|上车|team", t))
    if re.search(r"非成品号|不是成品|非账号", t): delivery = "非账号/资格"
    elif shared: delivery = "共享/车位"
    elif len(combo_products(title)) > 1 or re.search(r"组合|套餐包|联合会员|多合一|三合一|\+.*(?:会员|pro|plus)|(?:会员|pro|plus).*\+", t): delivery = "组合"
    elif re.search(r"codex.*(?:\d+\s*(?:积分|额度|点数)|额度|积分)", t) and not re.search(r"pro\s*(?:100|200|500)", t): delivery = "额度包"
    elif re.search(r"token号|token账号|成品token|api号", t): delivery = "Token号"
    elif re.search(r"兑换码|兑换卡|cdkey|cdk|卡密|激活码", t): delivery = "兑换码"
    elif re.search(r"成品|独享号|账号密码|帐号|手搓号", t): delivery = "成品号"
    elif re.search(r"代充|直充|直冲|充值|自充|卡充", t): delivery = "代充"
    else: delivery = "未注明交付"

    quota_matches = re.findall(r"\d+(?:\.\d+)?\s*(?:亿|万|[kmb])?\s*(?:tokens?|积分|额度|credits?)", t, re.I)
    quotas = []
    for q in quota_matches:
        q = re.sub(r"\s+", "", q.lower()).replace("tokens", "token")
        quotas.append(q)
    if delivery == "额度包":
        credit = re.search(r"(\d+(?:\.\d+)?)\s*(?:积分|额度|点数|credits?)", t)
        if credit: quotas.append(credit.group(1) + "额度")
    quotas = list(dict.fromkeys(quotas))

    tier_text = t.replace("ulrta", "ultra").replace("uitra", "ultra").replace("格洛克", "grok")
    tier = []
    if delivery == "额度包": tier = ["credit"]
    elif product == "Codex" and re.search(r"\bgo\b|codexgo", tier_text): tier = ["go"]
    else:
        for rx, val in [(r"pro\s*500|50x|500\s*(?:刀|美元)", "pro500"),
                        (r"pro\s*200|20x|200\s*(?:刀|美元)", "pro200"),
                        (r"pro\s*100|10x|100\s*(?:刀|美元)", "pro100"),
                        (r"max\s*20x|20x\s*max", "max20x"), (r"max\s*5x|5x\s*max", "max5x"),
                        (r"ultra\s*20x|20x\s*ultra", "ultra20x"), (r"ultra\s*5x|5x\s*ultra", "ultra5x"),
                        (r"premium\+", "premium+"), (r"grok\s*super|gr0k\s*super", "super"),
                        (r"ultra", "ultra"), (r"premium", "premium"), (r"plus", "plus"), (r"\bpro\b", "pro"), (r"\bmax\b", "max")]:
            if re.search(rx, tier_text): tier = [val]; break
    region = []
    for rx, val in [(r"美区|美国", "美区"), (r"菲区|菲律宾", "菲区"), (r"土区|土耳其", "土区"),
                    (r"越南", "越南"), (r"印度", "印度"), (r"尼区|尼日利亚", "尼日利亚"), (r"全球", "全球"), (r"国区", "国区")]:
        if re.search(rx, t): region.append(val)
    region = list(dict.fromkeys(region))
    promotion = ["促销"] if re.search(r"半价|首月优惠|促销|限时特惠", t) else []
    label_parts = [duration or "时长未注明", *quotas, *tier, *region, *promotion, delivery]
    label = " / ".join(dict.fromkeys(label_parts))
    # Stable key excludes raw title; only real multi-SKU ambiguity remains isolated.
    identity = (tuple(tier), duration or "时长未注明", delivery, tuple(quotas), tuple(region), tuple(promotion), title if multi else "")
    return {"duration": duration, "tier": tier, "quota": quotas, "region": region,
            "promotion": promotion, "delivery": delivery, "label": label,
            "key": hashlib.sha256(repr(identity).encode()).hexdigest()[:32],
            "incomplete": not duration or not tier or delivery == "未注明交付",
            "period_default": period_default, "period_na": period_na, "multi_option": multi,
            "risk": "高" if delivery in {"成品号", "共享/车位"} else "中" if delivery == "代充" else "未判定"}


def listing(title, price, url, category="", **extra):
    product = classify(title, category)
    spec = specification(title, product)
    return dict(title=title.strip(), price=str(price), currency="CNY", url=url, category=category,
                product=product, spec=spec, risk=spec["risk"], **extra)
