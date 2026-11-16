"""保守归类：规格不明时保留原商品标题，绝不拿不同规格混比。"""
import hashlib
import re


def classify(title, category=""):
    t = re.sub(r"[\s'’,，.·•。_-]", "", title.lower())
    c = category.lower()
    if re.search(r"接码|接马|接吗|接🐎|接🐴|接过码|接\*码|验证码|手机验证|登录验证|登陆验证|手机号|换绑邮箱|邮箱号|助力|代注册|注册号|注册服务|激活服务|邀请|补差价|升级差价|私人代充|白号|普号|free|虚拟卡|资格|绿色软件|镜像站|除codex|不是成品|不含|不包含|不带会员|没有会员", t): return None
    # 组合套餐不属于任一单品，避免 Grok 捆绑的 Cursor 权益变成 Cursor 订阅低价。
    brands = [bool(re.search(rx, t)) for rx in (r"grok|gr0k|gork|supergrk", r"cursor", r"gemini", r"muse", r"claude", r"copilot", r"perplexity")]
    if sum(brands) > 1: return None
    for rx, name in [(r"codex", "Codex"), (r"muse", "Muse"), (r"cursor", "Cursor"),
                     (r"perplexity", "Perplexity"), (r"copilot", "Copilot"),
                     (r"midjourney|\bmj\b", "Midjourney"), (r"gemini", "Gemini"),
                     (r"telegram.*(?:premium|会员)|电报会员|tg会员", "Telegram会员")]:
        if re.search(rx, t):
            return name
    if "claude" in t:
        if "max" in t: return "Claude Max"
        if "pro" in t: return "Claude Pro"
    if "grok" in t or "gr0k" in t:
        for tier in ("ultra", "super", "premium", "plus"):
            if tier in t: return "Grok " + tier.capitalize()
        return "Grok"
    if re.search(r"(?:^|[【（(])x(?:[)）】]|会员|premium)|x[（(]推特|推特.*(?:会员|蓝标)|twitter.*(?:会员|premium)|xpremium", t) and not re.search(r"netflix|minimax", t): return "X会员"
    if re.search(r"gpt|openai", t) or ("plus" in t and not re.search(r"claude|grok|gemini|office|microsoft|youtube|notion|netflix|spotify", t)):
        if "plus" in t and re.search(r"升级pro|升级到pro", t): return "ChatGPT Plus"
        if "pro" in t: return "ChatGPT Pro"
        if "plus" in t: return "ChatGPT Plus"
    return None


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
    return (group.get("currency") != "CNY", period, tier, spec.get("incomplete", True),
            -group.get("n_shops", group.get("n_prices", 0)), group.get("label", ""), group.get("key", ""))


def specification(title, product=None):
    # 售后「质保30天」并非订阅30天，不用它推断时长。
    t = re.sub(r"(?:质保(?:订阅)?|首登|售后|保修|注册|登录|使用稳定|已稳定)\s*[:：]?\s*(?:\d+|一|两|三|半)\s*(?:个)?(?:天|小时|月|年)", "", title.lower())
    t = re.sub(r"(?:\d+|一|两|三)\s*(?:天|小时|月)(?=\s*(?:质保|售后|自助|全自动))", "", t)
    delivery = "成品号" if re.search(r"成品|独享号|共享|账号密码|帐号|手搓号", t) else "代充" if re.search(r"代充|直充|直冲|充值|自充|卡充", t) else "未注明交付"
    duration = None
    m = re.search(r"(\d+\s*[-–~至到]\s*\d+|\d+)\s*(天|日|个自然月|个月|月|年|小时)", t)
    if m: duration = re.sub(r"\s", "", m[0]).replace("个自然月", "月").replace("个月", "月").replace("日", "天")
    if not duration:
        for rx, val in [(r"半年", "6月"), (r"年卡|年付|年费|一年", "1年"), (r"季卡|季付", "3月"), (r"月卡|月付|月费|一个月|一月", "1月"), (r"周卡", "7天")]:
            if re.search(rx, t): duration = val; break
    if not duration:
        for cn, n in [("两", 2), ("三", 3), ("六", 6)]:
            if cn + "个月" in t: duration = f"{n}月"; break
    duration = {"30天": "1月", "365天": "1年", "12月": "1年"}.get(duration, duration)
    quotas = re.findall(r"\d+(?:\.\d+)?(?:\s*[-–~至到]\s*\d+(?:\.\d+)?)?\s*(?:亿|万|[kmb])?\s*(?:tokens?|积分|额度|刀|美元|credits?|倍|x\b)", t)
    tier = re.findall(r"(?:pro|max)\s*\+?\s*(?:100|200|500|5x|20x)?|ultra|premium\+?|plus|\d+\s*[倍x]", t)
    tier = [re.sub(r'\s+', '', x) for x in tier]
    region = re.findall(r"美区|菲区|土区|越南|印度|尼区|全球|国区|尼日利亚", t)
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
