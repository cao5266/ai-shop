(() => {
const $ = (s, r = document) => r.querySelector(s);
const app = $("#app");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = (u) => { try { const x = new URL(u); return /^https?:$/.test(x.protocol) ? x.href : ""; } catch { return ""; } };
const num = (n) => (Number.isInteger(n) ? String(n) : n.toFixed(2).replace(/0+$/, "").replace(/\.$/, ""));
const yuan = (n) => "¥" + num(n);
const api = (p) => fetch(p).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
const dtf = new Intl.DateTimeFormat("zh-CN", { timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
const when = (iso) => (iso ? dtf.format(new Date(iso)).replace(/\//g, "-") + "（北京时间）" : "未知");
const median = (a) => { const s = [...a].sort((x, y) => x - y), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const badge = (r) => `<span class="badge ${r === "高" ? "hi" : r === "低" ? "low" : "mid"}">${esc(r)}风险</span>`;
const go = (url, text = "去店铺") => { const u = safeUrl(url); return u ? `<a class="btn" href="${esc(u)}" target="_blank" rel="noopener noreferrer nofollow">${text}</a>` : ""; };
const chev = `<svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true"><path d="M12.5 4.5L7 10l5.5 5.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

// 商品 -> logo 文件（仅使用真实存在的 logo；没有的显示首字母方块）
const LOGO = { "ChatGPT Plus": "openai", "ChatGPT Pro": "openai", "Claude Pro": "claude", "Claude Max": "claude", Grok: "grok", Gemini: "gemini", Cursor: "cursor", Perplexity: "perplexity", Copilot: "copilot", "X会员": "x", "Telegram会员": "telegram" };
const TINTS = ["#4f7a6b", "#b0803f", "#587089", "#7d7a52", "#8c6a5a"];
const tile = (name) => {
  const f = LOGO[name];
  if (f) return `<span class="tile"><img src="/static/logos/${f}.svg" alt="" width="64" height="64" loading="lazy"></span>`;
  let h = 0; for (const c of name) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return `<span class="tile mono" style="background:${TINTS[h % TINTS.length]}" aria-hidden="true">${esc([...name][0].toUpperCase())}</span>`;
};

const S = { meta: null, tools: null, q: "", shops: { risk: "", type: "", product: "", sort: "mentions-desc", page: 1, loaded: 0, total: 0, req: 0 } };

async function ensureMeta() {
  if (!S.meta) S.meta = await api("/api/meta");
  return S.meta;
}
async function ensureTools() {
  if (!S.tools) S.tools = await api("/api/tools");
  return S.tools;
}

// ---------- 首页
async function home() {
  app.innerHTML = `<div class="hero"><h1>按 AI 工具，找在售店铺和价格</h1><p>汇总 X 上推广订阅代充的店铺，每家都标了风险等级。选一个工具，看谁在卖、卖多少钱。</p><div class="hero-meta" id="hm"></div></div>
  <div class="sec-h"><h2>全部商品</h2><a href="#/shops">查看全部店铺</a></div><div class="grid" id="grid"></div>
  <p class="tip">卡片上的价格来自店铺在 X 帖文里写明的数字，档位不一（月卡、年付、不同额度都有），仅供参考。没有标价的店铺不参与价格统计。</p>`;
  try {
    const [m, tools] = await Promise.all([ensureMeta(), ensureTools()]);
    const c = m.risk_counts;
    $("#hm").innerHTML = `<span class="pill">收录 ${m.total_shops} 家店铺</span>` +
      (c["低"] === 0 ? `<span class="pill">其中没有官方渠道</span>` : "") +
      `<span class="badge hi">高风险 ${c["高"]} 家</span><span class="badge mid">中风险 ${c["中"]} 家</span>` +
      `<span class="pill">数据更新于 ${when(m.updated_at)}</span>`;
    $("#grid").innerHTML = tools.map(card).join("");
  } catch { $("#grid").innerHTML = `<div class="empty">数据读取失败，请稍后刷新重试。</div>`; }
}
function card(t) {
  const has = t.min != null;
  const range = !has ? "" : t.min === t.max ? `<p class="range">${t.n_prices} 条报价</p>` : `<p class="range">区间 ${yuan(t.min)} 至 ${yuan(t.max)}</p>`;
  return `<a class="card" href="#/tool/${encodeURIComponent(t.name)}" aria-label="${esc(t.name)}，${t.n_shops} 家在售">
    <div class="card-top">${tile(t.name)}<div><h3>${esc(t.name)}</h3><p class="sub">${t.n_shops} 家在售</p></div></div>
    <div class="card-bot">${has ? `<p class="from">最低价</p><p class="amt">${yuan(t.min)}</p>${range}` : `<p class="from">价格</p><p class="amt-none">帖子里没有标价</p>`}</div></a>`;
}

// ---------- 商品详情
async function tool(name) {
  app.innerHTML = `<a class="crumb" href="#/">${chev}全部商品</a><div class="empty">读取中…</div>`;
  let d;
  try { d = await api("/api/tools/" + encodeURIComponent(name) + "/offers"); } catch { app.innerHTML = `<a class="crumb" href="#/">${chev}全部商品</a><div class="empty">没有找到这个商品。</div>`; return; }
  const st = { tier: "", risk: "", sort: "price-asc" };
  app.innerHTML = `<a class="crumb" href="#/">${chev}全部商品</a>
    <section class="app-head">${tile(d.name)}<div><h1>${esc(d.name)}</h1><p class="lead" id="lead"></p><div class="stats" id="stats"></div></div></section>
    <p class="tip">价格取自店铺在 X 帖文里写明的数字，档位和口径不一，下单前请到店铺页面核实。风险等级按文案规则自动判断，只能参考。</p>
    <div class="sec-h"><h2>在售店铺</h2></div>
    <div class="bar" id="bar"></div><p class="count" id="cnt"></p><ul class="list" id="ol"></ul>`;
  const tiers = d.members.length > 1 ? d.members : [];
  $("#bar").innerHTML = (tiers.length ? `<span class="chips" role="group" aria-label="档位">${["", ...tiers].map((t) => `<button class="chip" type="button" data-tier="${esc(t)}" aria-pressed="${t === ""}">${t === "" ? "全部档位" : esc(t)}</button>`).join("")}</span>` : "") +
    `<span class="seg" role="group" aria-label="风险">${[["", "全部风险"], ["高", "高风险"], ["中", "中风险"]].map(([v, l]) => `<button type="button" data-risk="${v}" aria-pressed="${v === ""}">${l}</button>`).join("")}</span>` +
    `<label class="sel"><span class="sr">排序</span><select id="so"><option value="price-asc">价格从低到高</option><option value="price-desc">价格从高到低</option><option value="mentions">提及最多</option></select></label>`;
  const view = () => {
    const quotesOf = (o) => o.quotes.filter((q) => !st.tier || q.product === st.tier);
    let priced = d.offers.filter((o) => quotesOf(o).length && (!st.risk || o.risk === st.risk));
    let unpriced = st.tier ? [] : d.no_price.filter((o) => !st.risk || o.risk === st.risk);
    const best = (o) => quotesOf(o)[0].amount, worst = (o) => quotesOf(o).at(-1).amount;
    priced.sort(st.sort === "price-desc" ? (a, b) => worst(b) - worst(a) : st.sort === "mentions" ? (a, b) => b.n_posts - a.n_posts : (a, b) => best(a) - best(b));
    const all = d.offers.flatMap((o) => quotesOf(o).map((q) => q.amount));
    $("#lead").textContent = `${d.offers.length + d.no_price.length} 家店铺在卖${all.length ? `，帖文里有 ${all.length} 条报价` : "，帖子里都没有标价"}`;
    $("#stats").innerHTML = [["最低价", all.length ? yuan(Math.min(...all)) : "暂无"], ["中位价", all.length ? yuan(median(all)) : "暂无"], ["最高价", all.length ? yuan(Math.max(...all)) : "暂无"], ["在售店铺", String(st.tier ? priced.length : d.offers.length + d.no_price.length)]]
      .map(([k, v]) => `<div class="stat"><p class="k">${k}</p><p class="v">${v}</p></div>`).join("");
    $("#cnt").textContent = `${priced.length} 家有标价${unpriced.length ? `，${unpriced.length} 家没有标价` : ""}`;
    const row = (o, p) => `<li class="item" data-id="${o.id}"><div class="item-main">
      <div class="c-name"><div class="nm-row"><h3 class="nm">${esc(o.name)}</h3>${badge(o.risk)}</div><p class="dm">${esc(o.domain)}，${esc(o.type)}</p></div>
      <div class="c-price">${p ? `<p class="pr">${yuan(p[0].amount)}</p><p class="pr-sub">${esc(p[0].label || d.name)}${p.length > 1 ? `，另有 ${p.length - 1} 档` : ""}</p>` : `<p class="pr-none">没有标价</p>`}</div>
      <p class="ment c-ment"><b>${o.n_posts}</b>条 X 帖提及</p>
      <div class="c-go">${go(o.url)}<button class="btn ghost" type="button" data-more>详情</button></div></div></li>`;
    $("#ol").innerHTML = priced.map((o) => row(o, quotesOf(o))).join("") +
      (unpriced.length ? `<li class="sec-h" style="margin:22px 0 4px"><h2 style="font-size:17px">提到该商品但没有标价（${unpriced.length}）</h2></li>` + unpriced.map((o) => row(o, null)).join("") : "") ||
      `<li class="empty">没有符合条件的店铺，换一个筛选条件试试。</li>`;
    if (!priced.length && !unpriced.length) $("#ol").innerHTML = `<li class="empty">没有符合条件的店铺，换一个筛选条件试试。</li>`;
  };
  $("#bar").addEventListener("click", (e) => {
    const t = e.target.closest("[data-tier],[data-risk]"); if (!t) return;
    if ("tier" in t.dataset) { st.tier = t.dataset.tier; document.querySelectorAll("[data-tier]").forEach((x) => x.setAttribute("aria-pressed", String(x === t))); }
    else { st.risk = t.dataset.risk; document.querySelectorAll("[data-risk]").forEach((x) => x.setAttribute("aria-pressed", String(x === t))); }
    view();
  });
  $("#so").addEventListener("change", (e) => { st.sort = e.target.value; view(); });
  $("#ol").addEventListener("click", (e) => { if (e.target.closest("[data-more]")) toggleExtra(e.target.closest(".item")); });
  view();
}

// ---------- 全部店铺
async function shopsView() {
  const f = S.shops;
  app.innerHTML = `<div class="hero" style="padding-bottom:0"><h1>全部店铺</h1><p>搜索店名、域名或商品，也可以按风险、类型、商品筛选。</p></div>
    <div class="bar" style="margin-top:20px" id="sbar"></div><p class="count" id="cnt"></p><ul class="list" id="ol"></ul><div class="more"><button class="btn" id="more" type="button" hidden>再显示 30 家</button></div>`;
  const m = await ensureMeta().catch(() => null); const tools = await ensureTools().catch(() => []);
  const opt = (v, l, cur) => `<option value="${esc(v)}"${v === cur ? " selected" : ""}>${esc(l)}</option>`;
  $("#sbar").innerHTML = `<span class="seg" role="group" aria-label="风险">${[["", "全部风险"], ["高", "高风险"], ["中", "中风险"]].map(([v, l]) => `<button type="button" data-risk="${v}" aria-pressed="${v === f.risk}">${l}</button>`).join("")}</span>
    <label class="sel"><span class="sr">店铺类型</span><select id="ft">${opt("", "全部类型", f.type)}${(m?.types || []).map((t) => opt(t.name, `${t.name}（${t.count}）`, f.type)).join("")}</select></label>
    <label class="sel"><span class="sr">商品</span><select id="fp">${opt("", "全部商品", f.product)}${tools.map((t) => opt(t.name, t.name, f.product)).join("")}</select></label>
    <label class="sel"><span class="sr">排序</span><select id="fs">${[["mentions-desc", "提及最多"], ["mentions-asc", "提及最少"], ["price-asc", "最低价从低到高"], ["price-desc", "最低价从高到低"], ["recent", "最近出现"]].map(([v, l]) => opt(v, l, f.sort)).join("")}</select></label>`;
  $("#sbar").addEventListener("click", (e) => { const b = e.target.closest("[data-risk]"); if (!b) return; f.risk = b.dataset.risk; document.querySelectorAll("[data-risk]").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); loadShops(true); });
  [["ft", "type"], ["fp", "product"], ["fs", "sort"]].forEach(([id, k]) => $("#" + id).addEventListener("change", (e) => { f[k] = e.target.value; loadShops(true); }));
  $("#more").addEventListener("click", () => { f.page++; loadShops(false); });
  $("#ol").addEventListener("click", (e) => { if (e.target.closest("[data-more]")) toggleExtra(e.target.closest(".item")); });
  loadShops(true);
}
async function loadShops(reset) {
  const f = S.shops, my = ++f.req;
  if (reset) { f.page = 1; f.loaded = 0; $("#ol").innerHTML = ""; }
  const p = new URLSearchParams({ q: S.q, product: f.product, risk: f.risk, type: f.type, sort: f.sort, page: f.page, page_size: 30 });
  let d; try { d = await api("/api/shops?" + p); } catch { $("#cnt").textContent = "读取失败，请稍后重试。"; return; }
  if (my !== f.req || !$("#ol")) return;
  f.total = d.total; f.loaded += d.items.length;
  $("#cnt").textContent = d.total ? `${S.q ? `「${S.q}」` : ""}共 ${d.total} 家，已显示 ${f.loaded} 家` : "";
  if (!d.total) $("#ol").innerHTML = `<li class="empty">没有符合条件的店铺。清空搜索词，或把筛选改回「全部」试试。</li>`;
  else $("#ol").insertAdjacentHTML("beforeend", d.items.map(shopRow).join(""));
  $("#more").hidden = f.loaded >= f.total;
}
function shopRow(s) {
  const prods = s.products.length ? s.products.join("、") : "未识别到商品";
  return `<li class="item" data-id="${s.id}"><div class="item-main">
    <div class="c-name"><div class="nm-row"><h3 class="nm">${esc(s.name)}</h3>${badge(s.risk)}</div><p class="dm">${esc(s.domain)}，${esc(s.type)}</p><p class="dm">${esc(prods)}</p></div>
    <div class="c-price">${s.min_price != null ? `<p class="pr">${yuan(s.min_price)}</p><p class="pr-sub">帖文最低价</p>` : `<p class="pr-none">没有标价</p>`}</div>
    <p class="ment c-ment"><b>${s.n_posts}</b>条 X 帖提及</p>
    <div class="c-go">${go(s.url)}<button class="btn ghost" type="button" data-more>详情</button></div></div></li>`;
}

// ---------- 展开详情（风险原因、报价、示例帖文）
async function toggleExtra(li) {
  const ex = $(".extra", li), b = $("[data-more]", li);
  if (ex) { ex.remove(); b.textContent = "详情"; return; }
  b.textContent = "收起";
  const box = document.createElement("div"); box.className = "extra"; box.textContent = "读取中…"; li.appendChild(box);
  try {
    const s = await api("/api/shops/" + li.dataset.id);
    const post = s.prices.filter((p) => p.source === "post"), page = s.prices.filter((p) => p.source === "page");
    const hist = (p) => (p.history.length > 1 ? `（变动：${p.history.map((h) => num(h.amount)).join(" → ")}）` : "");
    const q = (a) => `<ul class="q">${a.map((p) => `<li><span>${esc(p.label || "页面金额")}${hist(p)}</span><b>${yuan(p.amount)}</b></li>`).join("")}</ul>`;
    const flags = s.risk_flags.filter((x) => x.active);
    box.innerHTML = `<div class="xcols"><div><h4>风险提示</h4>${flags.length ? flags.map((x) => `<p class="fl ${x.severity === "高" ? "hi" : ""}"><b>${esc(x.label)}</b>${esc(x.detail)}</p>`).join("") : `<p class="muted">没有额外的风险标记，但它仍是非官方渠道。</p>`}
      <p class="muted">页面状态：${esc(s.page_status || "未知")}${s.http_code ? `（HTTP ${esc(s.http_code)}）` : ""}</p><p class="muted">首次收录 ${when(s.first_seen_at)}<br>最近一次看到 ${when(s.last_seen_at)}</p></div>
      <div><h4>帖文里的报价</h4>${post.length ? q(post) : `<p class="muted">帖子里没有出现标价。</p>`}${page.length ? `<h4>页面上看到的金额</h4><p class="muted">没有对应商品标注，仅供参考。</p>${q(page)}` : ""}</div></div>
      ${s.posts.length ? `<h4>示例帖文</h4>${s.posts.map((x) => `<div class="post">${esc(x.text || "（仅有链接）")}${safeUrl(x.url) ? `<a href="${esc(safeUrl(x.url))}" target="_blank" rel="noopener noreferrer nofollow">在 X 查看${x.author ? "（@" + esc(x.author) + "）" : ""}</a>` : ""}</div>`).join("")}` : ""}
      ${s.promoters.length ? `<h4>推广账号</h4><p class="muted">${s.promoters.map((a) => `@${esc(a.username)}（${a.post_count ?? "?"} 条${a.year ? "，" + a.year + " 年注册" : ""}${a.followers != null ? "，" + a.followers + " 粉丝" : ""}）`).join("　")}</p>` : ""}`;
  } catch { box.textContent = "详情读取失败。"; }
}

// ---------- 说明
async function about() {
  const m = await ensureMeta().catch(() => null);
  app.innerHTML = `<div class="about"><h1>风险说明与数据来源</h1><p class="muted">${m ? `数据更新于 ${when(m.updated_at)}，已入库 ${m.runs} 批采集。` : ""}</p>
    <h2>风险等级怎么定的</h2>
    <div class="rule"><span class="badge hi">高风险</span><p>帖子里卖成品号、共享号或来源不明的账号，写明不质保或不管封号，或者用多个账号群发同一店铺。</p></div>
    <div class="rule"><span class="badge mid">中风险</span><p>提供代充或直充，或者是其他非官方店铺，暂时没看到更高风险的文案。</p></div>
    <div class="rule"><span class="badge low">低风险</span><p>官方或正规渠道。本站收录的店铺里没有能认定为官方渠道的，所以这一档是 0 家。</p></div>
    <p class="muted">「无法稳定打开」只是提示，不会单独把店铺升为高风险，因为发卡网常常拦截爬虫。</p>
    <h2>数据来源与局限</h2><ul>${(m?.scope?.limitations || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
    <p>数据由程序从 X 的公开帖子和店铺页面采集，只读，没有下单、注册或提交表单。价格只记录帖子或页面上实际看到的内容，没有的就留空。风险等级是按文案规则自动判断的，可能有误判，请自行核实。</p></div>`;
}

// ---------- 路由与搜索
function route() {
  const h = location.hash.replace(/^#/, "") || "/";
  document.querySelectorAll("[data-nav]").forEach((a) => a.classList.toggle("is-on", (h === "/" || h.startsWith("/tool")) ? a.dataset.nav === "home" : h.startsWith("/" + a.dataset.nav)));
  window.scrollTo(0, 0);
  if (h.startsWith("/tool/")) tool(decodeURIComponent(h.slice(6)));
  else if (h === "/shops") shopsView();
  else if (h === "/about") about();
  else home();
}
let timer;
$("#q").addEventListener("input", (e) => {
  clearTimeout(timer);
  timer = setTimeout(() => {
    S.q = e.target.value.trim();
    if (location.hash !== "#/shops") location.hash = "#/shops"; else loadShops(true);
  }, 300);
});
window.addEventListener("hashchange", route);
route();
})();
