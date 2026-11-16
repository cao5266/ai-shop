(() => {
const $ = (id) => document.getElementById(id);
const PAGE = 30;
const st = { q: "", product: "", risk: "", type: "", sort: "mentions-desc", page: 1, total: 0, loaded: 0, req: 0 };

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = (u) => { try { const x = new URL(u); return /^https?:$/.test(x.protocol) ? x.href : ""; } catch { return ""; } };
const fmt = (n) => (n == null ? "" : Number.isInteger(n) ? String(n) : n.toFixed(2).replace(/0+$/, "").replace(/\.$/, ""));
const dateFmt = new Intl.DateTimeFormat("zh-CN", { timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
const when = (iso) => (iso ? dateFmt.format(new Date(iso)).replace(/\//g, "-") + "（北京时间）" : "未知");
const api = (p) => fetch(p).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
const riskCls = (r) => (r === "高" ? "r-high" : r === "低" ? "r-low" : "r-mid");
const link = (url, text, cls = "go") => {
  const u = safeUrl(url);
  return u ? `<a class="${cls}" href="${esc(u)}" target="_blank" rel="noopener noreferrer nofollow">${text}</a>` : "";
};

async function init() {
  try {
    const m = await api("/api/meta");
    renderMast(m);
    $("f-type").insertAdjacentHTML("beforeend", m.types.map((t) => `<option value="${esc(t.name)}">${esc(t.name)}（${t.count}）</option>`).join(""));
    const chips = [{ name: "", label: "全部商品", count: m.total_shops }];
    const seenGrok = m.products.filter((p) => p.family === "Grok");
    m.products.forEach((p) => {
      if (p.family === "Grok") return;
      chips.push({ name: p.name, label: p.name, count: p.count });
    });
    if (seenGrok.length) {
      const gi = chips.findIndex((c) => c.name === "Cursor");
      chips.splice(gi < 0 ? chips.length : gi, 0, { name: "Grok", label: "Grok（全部档位）", count: null });
    }
    $("chips").innerHTML = chips.map((c) => `<button type="button" class="chip" data-p="${esc(c.name)}" aria-pressed="${c.name === ""}">${esc(c.label)}${c.count != null ? `<small>${c.count}</small>` : ""}</button>`).join("");
    $("limits").innerHTML = (m.scope?.limitations || []).map((x) => `<li>${esc(x)}</li>`).join("") || "<li>暂无说明</li>";
  } catch (e) {
    $("headline").textContent = "数据暂时读取失败，请稍后刷新页面重试。";
  }
  load(true);
}

function renderMast(m) {
  const c = m.risk_counts;
  $("headline").textContent = c["低"] === 0
    ? `收录 ${m.total_shops} 家店铺，没有一家是官方渠道`
    : `收录 ${m.total_shops} 家店铺，其中 ${c["低"]} 家为官方或正规渠道`;
  const seg = (cls, n, label) => (n ? `<div class="${cls}" style="flex:${n} 1 0" title="${label}风险 ${n} 家">${label}风险 ${n}</div>` : "");
  $("riskbar").innerHTML = seg("hi", c["高"], "高") + seg("mid", c["中"], "中") + seg("low", c["低"], "低");
  $("stamp").textContent = `数据更新于 ${when(m.updated_at)}，已入库 ${m.runs} 批采集。` + (m.source_generated_at ? `采集端时间标注：${m.source_generated_at}。` : "");
}

async function load(reset) {
  const my = ++st.req;
  if (reset) { st.page = 1; st.loaded = 0; $("list").innerHTML = ""; }
  const p = new URLSearchParams({ q: st.q, product: st.product, risk: st.risk, type: st.type, sort: st.sort, page: st.page, page_size: PAGE });
  let d;
  try { d = await api("/api/shops?" + p); } catch { $("count").textContent = "读取失败，请稍后重试。"; return; }
  if (my !== st.req) return;
  st.total = d.total; st.loaded += d.items.length;
  $("list").insertAdjacentHTML("beforeend", d.items.map(rowHtml).join(""));
  $("count").textContent = d.total ? `共 ${d.total} 家，已显示 ${st.loaded} 家` : "";
  if (!d.total) $("list").innerHTML = `<li class="empty">没有符合条件的店铺。试试清空搜索词，或把风险、类型、商品改回「全部」。</li>`;
  $("more").hidden = st.loaded >= st.total;
}

function rowHtml(s) {
  const flags = s.flags.map((f) => f.label).join("、");
  const prods = s.products.length ? s.products.join("、") : "未识别到商品";
  const price = s.min_price != null ? `<p class="price">${fmt(s.min_price)}<small>元起</small></p>` : `<p class="price-none">帖子里没有标价</p>`;
  return `<li class="row ${s.risk === "高" ? "r-high" : "r-mid"}" data-id="${s.id}">
    <div class="row-main">
      <div class="row-risk"><span class="tag ${riskCls(s.risk)}">${esc(s.risk)}风险</span>${flags ? `<p class="row-flags">${esc(flags)}</p>` : ""}</div>
      <div class="row-shop"><h2 class="shop-name"><button type="button" class="toggle-name" aria-expanded="false">${esc(s.name)}</button></h2>
        <p class="shop-sub">${esc(s.domain)}　${esc(s.type)}</p></div>
      <p class="prods row-prods">${esc(prods)}</p>
      <div class="row-price"><span class="lbl">帖文最低价</span>${price}</div>
      <div class="row-ment"><span class="lbl">X 帖提及</span><p class="mentions">${s.n_posts}<small>条帖<br>${s.n_accounts} 个账号</small></p></div>
      <div class="row-go">${link(s.url, "打开店铺")}<button type="button" class="toggle" aria-expanded="false">展开详情</button></div>
    </div></li>`;
}

async function toggleRow(li) {
  const open = li.querySelector(".detail");
  const btns = li.querySelectorAll("[aria-expanded]");
  if (open) { open.remove(); btns.forEach((b) => b.setAttribute("aria-expanded", "false")); li.querySelector(".toggle").textContent = "展开详情"; return; }
  btns.forEach((b) => b.setAttribute("aria-expanded", "true")); li.querySelector(".toggle").textContent = "收起详情";
  const box = document.createElement("div"); box.className = "detail"; box.textContent = "读取中…"; li.appendChild(box);
  try { box.innerHTML = detailHtml(await api("/api/shops/" + li.dataset.id)); } catch { box.textContent = "详情读取失败。"; }
}

function detailHtml(s) {
  const postPrices = s.prices.filter((p) => p.source === "post");
  const pagePrices = s.prices.filter((p) => p.source === "page");
  const hist = (p) => (p.history.length > 1 ? `<span class="src">变动：${p.history.map((h) => fmt(h.amount)).join(" → ")}</span>` : "");
  const li = (p) => `<li><span>${esc(p.label || "页面金额")} ${hist(p)}</span><b>${fmt(p.amount)} 元</b></li>`;
  const flags = s.risk_flags.filter((f) => f.active);
  return `<div class="dgrid"><div>
      <h3>风险提示</h3>
      ${flags.length ? flags.map((f) => `<p class="flag-d ${f.severity === "高" ? "hi" : ""}"><b>${esc(f.label)}</b>　${esc(f.detail)}</p>`).join("") : `<p class="meta-line">没有额外的风险标记，但这不代表安全：它仍是非官方渠道。</p>`}
      <p class="meta-line">页面状态：${esc(s.page_status || "未知")}${s.http_code ? `（HTTP ${esc(s.http_code)}）` : ""}</p>
      <p class="meta-line">首次收录：${when(s.first_seen_at)}<br>最近一次看到：${when(s.last_seen_at)}</p>
      ${s.notes ? `<p class="meta-line">${esc(s.notes)}</p>` : ""}
    </div><div>
      <h3>帖文里的报价</h3>
      ${postPrices.length ? `<ul class="pl">${postPrices.map(li).join("")}</ul>` : `<p class="meta-line">帖子里没有出现标价。</p>`}
      ${pagePrices.length ? `<h3>页面上看到的金额</h3><p class="meta-line">页面金额没有对应商品标注，仅供参考。</p><ul class="pl">${pagePrices.map(li).join("")}</ul>` : ""}
    </div></div>
    ${s.posts.length ? `<h3>示例帖文</h3>${s.posts.map((x) => `<blockquote class="quote">${esc(x.text || "（仅有链接）")}${safeUrl(x.url) ? `<cite>${link(x.url, "在 X 查看（@" + esc(x.author || "") + "）", "xl")}</cite>` : ""}</blockquote>`).join("")}` : ""}
    ${s.promoters.length ? `<h3>推广账号</h3><p class="meta-line">${s.promoters.map((a) => `@${esc(a.username)}（${a.post_count ?? "?"} 条${a.year ? "，" + a.year + " 年注册" : ""}${a.followers != null ? "，" + a.followers + " 粉丝" : ""}）`).join("　")}</p>` : ""}`;
}

// ---- 事件
let timer;
$("q").addEventListener("input", (e) => { clearTimeout(timer); timer = setTimeout(() => { st.q = e.target.value.trim(); load(true); }, 250); });
[["f-risk", "risk"], ["f-type", "type"], ["f-sort", "sort"]].forEach(([id, k]) => $(id).addEventListener("change", (e) => { st[k] = e.target.value; load(true); }));
$("chips").addEventListener("click", (e) => {
  const b = e.target.closest(".chip"); if (!b) return;
  st.product = b.dataset.p;
  document.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", String(c === b)));
  load(true);
});
$("more").addEventListener("click", () => { st.page++; load(false); });
$("list").addEventListener("click", (e) => {
  const t = e.target.closest(".toggle, .toggle-name"); if (t) toggleRow(t.closest(".row"));
});
document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("is-on", x === t));
  ["shops", "products", "about"].forEach((v) => ($("v-" + v).hidden = v !== t.dataset.view));
  if (t.dataset.view === "products" && !$("prodlist").children.length) loadProducts();
}));

// ---- 按商品
const LO = Math.log10(0.5), HI = Math.log10(5000);
const pos = (v) => ((Math.log10(Math.max(v, 0.5)) - LO) / (HI - LO)) * 100;
async function loadProducts() {
  const list = await api("/api/products");
  const ticks = [1, 10, 100, 1000];
  const axis = `<div class="axis" aria-hidden="true">${ticks.map((t) => `<span style="left:${pos(t)}%">${t} 元</span>`).join("")}</div>`;
  const grid = ticks.map((t) => `<i class="grid-l" style="left:${pos(t)}%"></i>`).join("");
  $("prodlist").innerHTML = axis + list.map((p) => {
    const has = p.min != null;
    const sub = has ? `${fmt(p.min)} 至 ${fmt(p.max)} 元，中位 ${fmt(p.median)}，${p.n_prices} 条报价` : "帖子里没有标价";
    const track = has ? `<div class="track">${grid}<span class="range" style="left:${pos(p.min)}%;width:${Math.max(pos(p.max) - pos(p.min), 0.6)}%"></span><span class="med" style="left:${pos(p.median)}%"></span></div>` : `<div class="track"><span class="noprice">${p.n_shops} 家店铺提到，但没有标价</span></div>`;
    return `<button type="button" class="prod" data-n="${esc(p.name)}" aria-expanded="false"><div class="prod-name">${esc(p.name)}<small>${p.n_shops} 家店铺 · ${sub}</small></div>${track}</button>`;
  }).join("");
}
$("prodlist").addEventListener("click", async (e) => {
  const b = e.target.closest(".prod"); if (!b) return;
  document.querySelectorAll(".prod").forEach((x) => x.setAttribute("aria-expanded", String(x === b)));
  const d = await api("/api/products/" + encodeURIComponent(b.dataset.n) + "/offers");
  const box = $("offers"); box.hidden = false;
  box.innerHTML = `<h3>${esc(d.product)}：从低到高的报价</h3>` +
    (d.offers.length ? d.offers.map((o) => `<div class="offer"><span class="o-risk"><span class="tag ${riskCls(o.risk)}">${esc(o.risk)}风险</span></span>
      <div class="o-shop"><b>${esc(o.name)}</b><br><span class="shop-sub">${esc(o.domain)}　帖文标注「${esc(o.label)}」　${o.n_posts} 条帖提及</span></div>
      <div class="o-price">${fmt(o.amount)}<small>元</small></div><div class="o-go">${link(o.url, "打开店铺")}</div></div>`).join("") : `<p class="meta-line">没有带标价的报价。</p>`) +
    (d.no_price.length ? `<h3>提到该商品但没有标价（${d.no_price.length} 家）</h3>` + d.no_price.map((o) => `<div class="offer"><span class="o-risk"><span class="tag ${riskCls(o.risk)}">${esc(o.risk)}风险</span></span><div class="o-shop"><b>${esc(o.name)}</b><br><span class="shop-sub">${esc(o.domain)}　${o.n_posts} 条帖提及</span></div><span></span><div class="o-go">${link(o.url, "打开店铺")}</div></div>`).join("") : "");
  box.scrollIntoView({ behavior: "smooth", block: "start" });
});

init();
})();
