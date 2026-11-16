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

// 标准商品使用真实品牌 SVG，来源见 logos/SOURCES.md。
const LOGO = { "ChatGPT Plus": "openai", "ChatGPT Pro": "openai", Codex: "openai", Muse: "muse", Midjourney: "midjourney", "Claude Pro": "claude", "Claude Max": "claude", Grok: "grok", Gemini: "gemini", Cursor: "cursor", Perplexity: "perplexity", Copilot: "copilot", "X会员": "x", "Telegram会员": "telegram" };
const tile = (name) => {
  const f = LOGO[name];
  if (f) return `<span class="tile"><img src="/static/logos/${f}.svg" alt="" width="64" height="64" loading="lazy"></span>`;
  return `<span class="tile"><img src="/static/logos/openai.svg" alt="" width="64" height="64"></span>`;
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
  <p class="tip">报价来自店铺公开商品页，按期限、额度和交付方式分别比较。卡片主价格对应所标规格；售罄商品不参与在售价格统计。</p>`;
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
  const range = !has ? "" : `<p class="range">${esc(t.primary_spec.label)}</p>`;
  const specs = (t.specs || []).slice(0, 3).map(g => `<div class="spec-line"><span>${esc(g.label)}</span><b>${esc(g.currency === "CNY" ? "¥" : g.currency + " ")}${num(g.min)}${g.max !== g.min ? "–" + num(g.max) : ""}</b></div>`).join("");
  return `<a class="card" href="#/tool/${encodeURIComponent(t.name)}" aria-label="${esc(t.name)}，${t.n_shops} 家在售">
    <div class="card-top">${tile(t.name)}<div><h3>${esc(t.name)}</h3><p class="sub">${t.n_shops} 家在售</p></div></div>
    <div class="card-bot">${has ? `<p class="from">入门月卡优先 · 同规格店铺价</p><p class="amt">${yuan(t.min)}${t.max !== t.min ? `<small>–${num(t.max)}</small>` : ""}</p>${range}<div class="spec-list">${specs}</div><p class="range">${t.n_prices} 个在售商品 · ${t.specs.length} 种规格</p>` : `<p class="amt-none">${esc(t.price_status || "店铺页未找到对应在售商品报价")}</p>${(t.sold_out_specs || []).slice(0, 2).map(g => `<p class="range">店铺标价 ${g.currency === "CNY" ? yuan(g.min) : esc(g.currency) + num(g.min)} · 已售罄<br>${esc(g.label)}</p>`).join("")}`}</div></a>`;
}

// ---------- 商品详情
async function tool(name) {
  app.innerHTML = `<a class="crumb" href="#/">${chev}全部商品</a><div class="empty">读取中…</div>`;
  let d;
  try { d = await api("/api/tools/" + encodeURIComponent(name) + "/offers"); } catch { app.innerHTML = `<a class="crumb" href="#/">${chev}全部商品</a><div class="empty">没有找到这个商品。</div>`; return; }
  const st = { tier: "", spec: d.specs?.[0]?.key || "", risk: "", sort: "price-asc" };
  app.innerHTML = `<a class="crumb" href="#/">${chev}全部商品</a>
    <section class="app-head">${tile(d.name)}<div><h1>${esc(d.name)}</h1><p class="lead" id="lead"></p><div class="stats" id="stats"></div></div></section>
    <p class="tip">${d.price_note ? esc(d.price_note.reason) : "先选择期限、额度和交付方式，再比较价格。报价附原始商品链接与采集时间，成品号标为高风险、代充标为中风险。"}</p>
    <div class="sec-h"><h2>在售店铺</h2></div>
    <div class="bar" id="bar"></div><p class="count" id="cnt"></p><ul class="list" id="ol"></ul>`;
  const tiers = d.members.length > 1 ? d.members : [];
  $("#bar").innerHTML = `<label class="sel spec-select"><span>比较规格 </span><select id="spec">${(d.specs || []).map(g => `<option value="${esc(g.key)}">${esc(g.label)}${g.title ? " · " + esc(g.title.slice(0, 65)) : ""}（${g.currency}，${g.n_prices} 件）</option>`).join("")}</select></label>` + (tiers.length ? `<span class="chips" role="group" aria-label="档位">${["", ...tiers].map((t) => `<button class="chip" type="button" data-tier="${esc(t)}" aria-pressed="${t === ""}">${t === "" ? "全部档位" : esc(t)}</button>`).join("")}</span>` : "") +
    `<span class="seg" role="group" aria-label="风险">${[["", "全部风险"], ["高", "高风险"], ["中", "中风险"]].map(([v, l]) => `<button type="button" data-risk="${v}" aria-pressed="${v === ""}">${l}</button>`).join("")}</span>` +
    `<label class="sel"><span class="sr">排序</span><select id="so"><option value="price-asc">价格从低到高</option><option value="price-desc">价格从高到低</option><option value="mentions">提及最多</option></select></label>`;
  const view = () => {
    const quotesOf = (o) => o.quotes.filter((q) => (!st.tier || q.product === st.tier) && q.group_key === st.spec);
    let priced = d.offers.filter((o) => quotesOf(o).length && (!st.risk || o.risk === st.risk));
    let unpriced = st.tier ? [] : d.no_price.filter((o) => !st.risk || o.risk === st.risk);
    const best = (o) => quotesOf(o)[0].amount, worst = (o) => quotesOf(o).at(-1).amount;
    priced.sort(st.sort === "price-desc" ? (a, b) => worst(b) - worst(a) : st.sort === "mentions" ? (a, b) => b.n_posts - a.n_posts : (a, b) => best(a) - best(b));
    const all = d.offers.flatMap((o) => quotesOf(o).map((q) => q.amount));
    const currency = d.specs.find(g => g.key === st.spec)?.currency || "CNY";
    const money = n => currency === "CNY" ? yuan(n) : currency + " " + num(n);
    $("#lead").textContent = `${d.offers.length + d.no_price.length} 家相关店铺，当前规格 ${all.length} 个商品报价` + (!all.length && d.sold_out_specs?.length ? `；已采标价 ${d.sold_out_specs.map(g => (g.currency === "CNY" ? yuan(g.min) : g.currency + num(g.min)) + "（售罄）").join("、")}` : "");
    $("#stats").innerHTML = [["同规格最低", all.length ? money(Math.min(...all)) : "待采集"], ["同规格中位", all.length ? money(median(all)) : "待采集"], ["同规格最高", all.length ? money(Math.max(...all)) : "待采集"], ["当前规格店铺", String(priced.length)]]
      .map(([k, v]) => `<div class="stat"><p class="k">${k}</p><p class="v">${v}</p></div>`).join("");
    $("#cnt").textContent = `${priced.length} 家有当前规格报价${unpriced.length ? `，${unpriced.length} 家待核实商品价格` : ""}`;
    const row = (o, p) => `<li class="item" data-id="${o.id}"><div class="item-main">
      <div class="c-name"><div class="nm-row"><h3 class="nm">${esc(o.name)}</h3>${badge(o.risk)}</div><p class="dm">${esc(o.domain)}，${esc(o.type)}</p></div>
      <div class="c-price">${p ? `<p class="pr">${money(p[0].amount)}</p><p class="pr-sub">${esc(p[0].label || d.name)}${p.length > 1 ? `，同规格另有 ${p.length - 1} 件` : ""}</p>${p.map(q => `<p class="offer-meta">${badge(q.risk)} ${q.stock != null ? "库存 " + esc(q.stock) : ""}${q.sales ? " · 销量 " + esc(q.sales) : ""}<br>${when(q.observed_at)} ${go(q.url, "查看商品")}</p>`).join("")}` : `<p class="pr-none">${esc(o.crawl?.reason || "尚未采到可验证商品价")}</p>`}</div>
      <p class="ment c-ment"><b>${o.n_posts}</b>条 X 帖提及</p>
      <div class="c-go">${go(p?.[0]?.url || o.url)}<button class="btn ghost" type="button" data-more>详情</button></div></div></li>`;
    $("#ol").innerHTML = priced.map((o) => row(o, quotesOf(o))).join("") +
      (unpriced.length ? `<li class="sec-h" style="margin:22px 0 4px"><h2 style="font-size:17px">采集状态待核实（${unpriced.length}）</h2></li>` + unpriced.map((o) => row(o, null)).join("") : "") ||
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
  $("#spec").addEventListener("change", (e) => { st.spec = e.target.value; view(); });
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
    <div class="c-price">${s.min_price != null ? `<p class="pr">${yuan(s.min_price)}</p><p class="pr-sub">店铺商品起价，规格见详情</p>` : `<p class="pr-none">查看采集状态</p>`}</div>
    <p class="ment c-ment"><b>${s.n_posts}</b>条 X 帖提及</p>
    <div class="c-go">${go(s.prices.find(p => p.source === "page" && p.url)?.url || s.url)}<button class="btn ghost" type="button" data-more>详情</button></div></div></li>`;
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
      <div><h4>店铺商品与价格历史</h4>${s.listings?.length ? `<ul class="q">${s.listings.map(l => `<li><span>${esc(l.title)}<br><small>${esc(l.spec.label)} · ${l.active ? "在售" : "售罄/下架"} · ${when(l.observed_at)}${hist(l)}</small>${go(l.url, "查看商品")}</span><b>${l.currency === "CNY" ? yuan(l.amount) : esc(l.currency) + " " + num(l.amount)}</b></li>`).join("")}</ul>` : `<p class="muted">${esc(s.crawl?.reason || "等待采集商品页")}</p>`}${post.length ? `<details><summary>历史 X 帖报价（不参与规格比价）</summary>${q(post)}</details>` : ""}</div></div>
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
