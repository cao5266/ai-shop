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
    c = category.lower()
    if re.search(r"接码|接马|接吗|接🐎|接🐴|接过码|接\*码|验证码|手机验证|登录验证|登陆验证|手机号|换绑邮箱|邮箱号|助力|代注册|注册号|注册服务|激活服务|邀请|补差价|升级差价|私人代充|白号|普号|free|虚拟卡|资格|绿色软件|镜像站|除codex|不是成品|不含|不包含|不带会员|没有会员", t): return None
    brands = [bool(re.search(rx, t)) for rx in (r"grok|gr0k|gork|supergrk", r"cursor", r"gemini", r"muse", r"claude", r"copilot", r"perplexity")]
    if sum(brands) > 1: return None
    # 组合套餐不属于任一单品，避免 Grok 捆绑的 Cursor 权益变成 Cursor 订阅低价。
    for rx, name in [(r"codex", "Codex"), (r"muse", "Muse"), (r"cursor", "Cursor"),
                     (r"perplexity", "Perplexity"), (r"copilot", "Copilot"),
                     (r"midjourney|\bmj\b", "Midjourney"), (r"gemini", "Gemini"),
                     (r"telegram.*(?:premium|会员)|电报会员|tg会员", "Telegram会员")]:
        if re.search(rx, t):
            return name
    if "claude" in t:
        if "max" in t: return "Claude Max"
        if "pro" in t: return "Claude Pro"
    if re.search(r"grok|gr0k|gork|supergrk", t):
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
    # 售后「质保30天」并非订阅30天，不用它推断时长。
    t = re.sub(r"(?:质保(?:订阅)?|首登|售后|保修|注册|登录|使用稳定|已稳定)\s*[:：]?\s*(?:\d+|一|两|三|半)\s*(?:个)?(?:天|小时|月|年)", "", title.lower())
    t = re.sub(r"(?:\d+|一|两|三)\s*(?:天|小时|月)(?=\s*(?:质保|售后|自助|全自动))", "", t)
    if len(combo_products(title)) > 1 or re.search(r"组合|套餐包|联合会员|多合一|三合一|\+.*(?:会员|pro|plus)|(?:会员|pro|plus).*\+", t):
        delivery = "组合"
    elif re.search(r"token号|token账号|成品token|api号", t):
        delivery = "Token号"
    elif re.search(r"兑换码|兑换卡|cdkey|cdk|卡密|激活码", t):
        delivery = "兑换码"
    elif re.search(r"成品|独享号|共享|账号密码|帐号|手搓号", t):
        delivery = "成品号"
    elif re.search(r"代充|直充|直冲|充值|自充|卡充", t):
        delivery = "代充"
    else:
        delivery = "未注明交付"
    duration = None
    duration_text = re.sub(r"(?:pro|max)\s*\d+", "", t)
    m = re.search(r"(\d+\s*[-–~至到]\s*\d+|\d+)\s*(天|日|个自然月|个月|月|年|小时)", duration_text)
    if m: duration = re.sub(r"\s", "", m[0]).replace("个自然月", "月").replace("个月", "月").replace("日", "天")
    if not duration:
        for rx, val in [(r"半年", "6月"), (r"年卡|年付|年费|一年|一整年", "1年"), (r"季卡|季付", "3月"), (r"月卡|月付|月费|月订阅|一个月|一月", "1月"), (r"周卡", "7天")]:
            if re.search(rx, t): duration = val; break
    if not duration:
        for cn, n in [("两", 2), ("三", 3), ("六", 6)]:
            if cn + "个月" in t: duration = f"{n}月"; break
    duration = {"30天": "1月", "365天": "1年", "12月": "1年"}.get(duration, duration)
    quotas = re.findall(r"\d+(?:\.\d+)?(?:\s*[-–~至到]\s*\d+(?:\.\d+)?)?\s*(?:亿|万|[kmb])?\s*(?:tokens?|积分|额度|刀|美元|credits?|倍|x\b)", t)
    quotas = list(dict.fromkeys(quotas))
    tier = re.findall(r"(?:pro|max)\s*\+?\s*(?:100|200|500|5x|20x)?|ultra|premium\+?|plus|\d+\s*[倍x]", t)
    tier = list(dict.fromkeys(re.sub(r'\s+', '', x) for x in tier))
    region = re.findall(r"美区|菲区|土区|越南|印度|尼区|全球|国区|尼日利亚", t)
    region = list(dict.fromkeys(region))
    features = re.findall(r"api|中转|家庭组|独享|共享|带手机|不带手机|无积分|有积分|续费|新购|首月半价|首月|半价|试用", t)
    unknown = (not duration and not quotas) or delivery == "未注明交付" or bool(re.search(r"套餐.*可选|多档|随机|以.*报价|补差价|升级pro|\d+\s*/\s*\d+", t))
    label = " / ".join(dict.fromkeys([duration or "时长未注明", *quotas, *tier, *region, *features, delivery]))
    # 不完整规格只有完全同标题才能比较，避免「未知」成为混价桶。
    key = label + (" / " + title if unknown else "")
    return {"duration": duration, "quota": quotas, "tier": tier, "region": region,
            "delivery": delivery, "label": label, "key": hashlib.sha256(key.encode()).hexdigest()[:32],
            "incomplete": unknown, "risk": "高" if delivery == "成品号" else "中" if delivery == "代充" else "未判定"}


def listing(title, price, url, category="", **extra):
    product = classify(title, category)
    spec = specification(title, product)
    return dict(title=title.strip(), price=str(price), currency="CNY", url=url, category=category,
                product=product, spec=spec, risk=spec["risk"], **extra)
