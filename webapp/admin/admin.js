/* Do'kon paneli — onlayn do'konni to'liq boshqarish (sotuv, katalog, ombor, xaridlar, marketing, sozlamalar) */
(() => {
  "use strict";

  const API = (((window.SHOP_CONFIG || window.YG_CONFIG) || {}).api || "").replace(/\/$/, "");
  const tg = window.Telegram && window.Telegram.WebApp;
  const qs = new URLSearchParams(location.search);
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (e) { /* */ } },
  };

  let TOKEN = store.get("shop_admin_token");
  const S = { page: "", catalog: null, texts: null, textGroup: null, textQuery: "", ordersTab: "active", ordersQ: "",
    period: "today", lastOrderId: 0, timers: [], prodQ: "", prodCat: 0, ticketsTab: "open", stockQ: "", stockLow: false };

  // ---------------- yordamchilar ----------------
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = (n) => String(Math.round(Number(n) || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  const money = (n) => num(n) + " so'm";
  const imgUrl = (p) => (!p ? "" : /^https?:/.test(p) ? p : (API ? API + "/" : "../") + p);
  const dt = (s) => (s ? String(s).slice(0, 16).replace(/^(\d{4})-(\d\d)-(\d\d)/, "$3.$2.$1") : "");
  const phone = (p) => {
    const d = String(p || "").replace(/\D/g, "");
    return d.length === 12 ? `+${d.slice(0, 3)} ${d.slice(3, 5)} ${d.slice(5, 8)} ${d.slice(8, 10)} ${d.slice(10)}` : (p || "");
  };
  const stars = (n) => "★".repeat(n) + "☆".repeat(5 - n);
  const pct = (a, b) => (b ? Math.round((a / b) * 100) : 0);

  function toast(msg, kind = "ok") {
    const el = document.createElement("div");
    el.className = "toast " + kind;
    el.textContent = msg;
    $("#toasts").appendChild(el);
    setTimeout(() => el.remove(), kind === "bad" ? 6000 : 3000);
  }

  function headers() {
    if (TOKEN) return { "X-Admin-Token": TOKEN };
    if (tg && tg.initData) return { "X-Telegram-Init-Data": tg.initData };
    if (qs.get("dev_user")) return { "X-Dev-User": qs.get("dev_user") };
    return {};
  }

  async function api(path, { method = "GET", body, form, blob } = {}) {
    const opts = { method, headers: headers() };
    if (form) opts.body = form;
    else if (body !== undefined) {
      opts.body = JSON.stringify(body);
      opts.headers["Content-Type"] = "application/json";
    }
    let r;
    try {
      r = await fetch(API + "/api/admin/" + path, opts);
    } catch (e) {
      throw new Error("Server bilan aloqa yo'q. Internetni tekshiring.");
    }
    if (r.status === 401) {
      const data = await r.json().catch(() => ({}));
      showLogin(data.error);
      throw new Error(data.error || "Kirish kerak");
    }
    if (blob) {
      if (!r.ok) throw new Error("Yuklab bo'lmadi");
      return r;
    }
    const data = await r.json().catch(() => ({ ok: false, error: "Server javobi noto'g'ri (" + r.status + ")" }));
    if (!data.ok) throw new Error(data.error || "Xatolik");
    return data;
  }

  async function run(fn, okMsg) {
    try {
      const res = await fn();
      if (okMsg) toast(okMsg);
      return res;
    } catch (e) {
      toast(e.message, "bad");
      return null;
    }
  }

  async function download(path) {
    const r = await run(() => api(path, { blob: true }));
    if (!r) return;
    const cd = r.headers.get("Content-Disposition") || "";
    const name = (cd.match(/filename="?([^"]+)"?/) || [])[1] || "fayl";
    const url = URL.createObjectURL(await r.blob());
    const a = Object.assign(document.createElement("a"), { href: url, download: name });
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  }

  // Rasm o'lchamini yuklashdan oldin brauzerda aniqlaydi (3:4 tekshiruvi uchun)
  const imageSize = (file) => new Promise((resolve) => {
    const url = URL.createObjectURL(file), im = new Image();
    im.onload = () => { resolve({ w: im.naturalWidth, h: im.naturalHeight }); URL.revokeObjectURL(url); };
    im.onerror = () => { resolve(null); URL.revokeObjectURL(url); };
    im.src = url;
  });
  async function upload(file, kind = "product") {
    const fd = new FormData();
    fd.append("file", file, file.name || "image.jpg");
    fd.append("kind", kind);
    const r = await api("upload", { method: "POST", form: fd });
    (r.warnings || []).forEach((w) => toast("ℹ️ " + w));
    return r.path;
  }

  // ---------------- modal ----------------
  function openModal(html, wide = false) {
    const m = $("#modal");
    m.className = "modal" + (wide ? " wide" : "");
    m.innerHTML = html;
    $("#modal-backdrop").classList.remove("hidden");
    document.body.style.overflow = "hidden";
    $$("[data-close]", m).forEach((b) => (b.onclick = closeModal));
    return m;
  }
  function closeModal() {
    $("#modal-backdrop").classList.add("hidden");
    $("#modal").innerHTML = "";
    document.body.style.overflow = "";
    if (S.modalTimer) { clearInterval(S.modalTimer); S.modalTimer = null; }
  }
  $("#modal-backdrop").addEventListener("mousedown", (e) => { if (e.target.id === "modal-backdrop") closeModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
  const modalHead = (title) => `<div class="modal-head"><h2>${title}</h2><button class="icon-btn" data-close>✕</button></div>`;

  // ---------------- Telegram HTML ko'rinishi ----------------
  const TG_TAGS = new Set(["b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "pre", "a", "tg-spoiler", "blockquote", "span"]);
  const vars = (s) => s.replace(/\{(\w+)\}/g, '<span class="var">{$1}</span>');
  function tgPreview(text, plain) {
    if (plain) return vars(esc(text));
    const doc = new DOMParser().parseFromString("<div>" + text + "</div>", "text/html");
    const walk = (node) => [...node.childNodes].map((n) => {
      if (n.nodeType === 3) return vars(esc(n.textContent));
      if (n.nodeType !== 1) return "";
      const tag = n.tagName.toLowerCase();
      const inner = walk(n);
      if (!TG_TAGS.has(tag)) return inner;
      let attrs = "";
      if (tag === "a") {
        const href = n.getAttribute("href") || "";
        attrs = /^(https?|tg):/i.test(href) ? ` href="${esc(href)}" target="_blank" rel="noopener"` : "";
      }
      if (tag === "span") return n.getAttribute("class") === "tg-spoiler" ? `<span class="tg-spoiler">${inner}</span>` : inner;
      return `<${tag}${attrs}>${inner}</${tag}>`;
    }).join("");
    return walk(doc.body.firstChild);
  }
  const TOOLS = [
    ["b", "<b>B</b>", "Qalin"], ["i", "<i>I</i>", "Kursiv"], ["u", "<u>U</u>", "Tagiga chizilgan"],
    ["s", "<s>S</s>", "Ustiga chizilgan"], ["code", "&lt;/&gt;", "Kod (nusxa olinadigan)"],
    ["tg-spoiler", "▒", "Yashirin (spoiler)"], ["blockquote", "❝", "Iqtibos"], ["a", "🔗", "Havola"],
  ];
  const toolbarHtml = (target) => `<div class="toolbar" data-target="${target}">` +
    TOOLS.map(([t, label, title]) => `<button type="button" data-tag="${t}" title="${title}">${label}</button>`).join("") + "</div>";
  function wrapSelection(ta, tag) {
    const { selectionStart: a, selectionEnd: b, value } = ta;
    const sel = value.slice(a, b) || "matn";
    let open = `<${tag}>`;
    if (tag === "a") {
      const url = prompt("Havola manzili (https://...)", "https://");
      if (!url || !/^(https?|tg):\/\/\S+$/.test(url)) return;
      open = `<a href="${url.replace(/"/g, "%22")}">`;
    }
    ta.setRangeText(open + sel + `</${tag}>`, a, b, "end");
    ta.focus();
    ta.dispatchEvent(new Event("input", { bubbles: true }));
  }
  function insertAtCursor(ta, text) {
    ta.setRangeText(text, ta.selectionStart, ta.selectionEnd, "end");
    ta.focus();
    ta.dispatchEvent(new Event("input", { bubbles: true }));
  }
  document.addEventListener("click", (e) => {
    const tb = e.target.closest(".toolbar button[data-tag]");
    if (tb) { const ta = document.getElementById(tb.parentElement.dataset.target); if (ta) wrapSelection(ta, tb.dataset.tag); return; }
    const chip = e.target.closest(".chip[data-ins]");
    if (chip) { const ta = document.getElementById(chip.dataset.target); if (ta) insertAtCursor(ta, chip.dataset.ins); }
  });

  // ---------------- kirish ----------------
  function applyBrand(b) {
    if (!b) return;
    const hex = /^#[0-9a-f]{6}$/i.test(b.color) ? b.color : "#e0382b";
    document.documentElement.style.setProperty("--brand", hex);
    document.documentElement.style.setProperty("--brand-rgb", [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(", "));
    document.title = b.name + " — Do'kon paneli";
    $("#brand").innerHTML = `${b.logo ? `<img src="${esc(imgUrl(b.logo))}" alt="">` : `<b>${esc(b.name)}</b>`}<div><small>Do'kon paneli</small></div>`;
    const ll = $("#login-logo");
    if (b.logo) ll.src = imgUrl(b.logo);
  }
  function showLogin(msg) {
    S.timers.forEach(clearInterval);
    S.timers = [];
    $("#shell").classList.add("hidden");
    $("#login").classList.remove("hidden");
    $("#login-msg").textContent = msg || "";
    const bot = store.get("shop_bot");
    if (bot) { const a = $("#login-bot"); a.href = "https://t.me/" + bot; a.classList.remove("hidden"); }
    fetch(API + "/api/admin/brand").then((r) => r.json()).then((d) => d.ok && applyBrand(d.brand)).catch(() => {});
  }

  async function boot() {
    if (tg) { try { tg.ready(); tg.expand(); } catch (e) { /* */ } }
    const code = (location.hash.match(/code=([\w-]+)/) || [])[1];
    if (code) {
      history.replaceState(null, "", location.pathname + location.search + "#dashboard");
      try {
        const r = await fetch(API + "/api/admin/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) });
        const data = await r.json();
        if (!data.ok) return showLogin(data.error);
        TOKEN = data.token;
        store.set("shop_admin_token", TOKEN);
      } catch (e) { return showLogin("Server bilan aloqa yo'q"); }
    }
    if (!TOKEN && !(tg && tg.initData) && !qs.get("dev_user")) return showLogin();
    let me;
    try { me = await api("me"); } catch (e) { return; }
    if (me.bot_username) store.set("shop_bot", me.bot_username);
    applyBrand(me.brand);
    $("#login").classList.add("hidden");
    $("#shell").classList.remove("hidden");
    $("#me").innerHTML = `<div><b>${esc(me.user.name)}</b><div class="muted small">👑 Menejer</div></div><button class="btn sm" id="logout">Chiqish</button>`;
    $("#logout").onclick = async () => {
      await api("logout", { method: "POST" }).catch(() => {});
      TOKEN = null; store.set("shop_admin_token", null);
      showLogin("Siz paneldan chiqdingiz.");
    };
    route();
    poll();
    S.timers.push(setInterval(poll, 20000));
  }

  function beep() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      [0, 0.18].forEach((t) => {
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.frequency.value = 880; g.gain.value = 0.08;
        o.connect(g).connect(ctx.destination);
        o.start(ctx.currentTime + t); o.stop(ctx.currentTime + t + 0.12);
      });
    } catch (e) { /* */ }
  }
  const setPill = (id, n, color) => { const p = $(id); p.textContent = n; p.classList.toggle("hidden", !n); if (color) p.style.background = color; };

  async function poll() {
    let d;
    try { d = await api("dashboard?period=today"); } catch (e) { return; }
    setPill("#nav-orders", d.active_orders, d.new_orders ? "var(--brand)" : "#555");
    setPill("#nav-tickets", d.open_tickets);
    setPill("#nav-low", d.low_stock.length, "#8a5a00");
    const st = d.status;
    const chip = $("#status-chip");
    chip.textContent = (st.accepting ? "🟢 Buyurtma qabul qilinmoqda" : "🔴 Buyurtma to'xtatilgan") + (st.accepting && !st.is_open ? " · ish vaqtidan tashqari" : "");
    chip.onclick = () => go("settings");
    const orders = await api("orders?status=new").catch(() => null);
    if (orders) {
      const maxId = Math.max(0, ...orders.orders.map((o) => o.id));
      if (S.lastOrderId && maxId > S.lastOrderId) {
        toast("🔔 Yangi buyurtma keldi!"); beep();
        if (S.page === "orders" || S.page === "dashboard") route();
      }
      S.lastOrderId = Math.max(S.lastOrderId, maxId);
    }
  }

  // ---------------- marshrut ----------------
  const PAGES = {};
  function go(page) { location.hash = page; }
  window.addEventListener("hashchange", route);
  $("#menu-toggle").onclick = () => { $("#sidebar").classList.add("open"); $("#sidebar-backdrop").classList.remove("hidden"); };
  $("#sidebar-backdrop").onclick = closeSidebar;
  function closeSidebar() { $("#sidebar").classList.remove("open"); $("#sidebar-backdrop").classList.add("hidden"); }
  $$("#nav a").forEach((a) => (a.onclick = () => { go(a.dataset.page); closeSidebar(); }));

  async function route() {
    if ($("#shell").classList.contains("hidden")) return;
    let page = location.hash.replace("#", "").split("?")[0];
    if (!PAGES[page]) page = "dashboard";
    if (S.pageTimer) { clearInterval(S.pageTimer); S.pageTimer = null; }
    S.page = page;
    $$("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.page === page));
    $("#page-title").textContent = $(`#nav a[data-page="${page}"] span`).textContent;
    const root = $("#page");
    if (root.dataset.page !== page) root.innerHTML = '<div class="loader">Yuklanmoqda…</div>';
    root.dataset.page = page;
    try { await PAGES[page](root); } catch (e) {
      root.innerHTML = `<div class="card glass empty">⚠️ ${esc(e.message)}<br><br><button class="btn" onclick="location.reload()">Qayta urinish</button></div>`;
    }
  }

  const PERIODS = { today: "Bugun", week: "7 kun", month: "30 kun", quarter: "90 kun", all: "Barcha vaqt" };
  const periodTabs = (cur, attr = "data-period") =>
    `<div class="tabs">${Object.entries(PERIODS).map(([k, v]) => `<button ${attr}="${k}" class="${k === cur ? "active" : ""}">${v}</button>`).join("")}</div>`;

  const STATUS = { new: "🕐 Yangi", accepted: "✅ Qabul qilindi", packing: "📦 Yig'ilmoqda", shipping: "🚚 Yo'lda",
    delivered: "🎉 Yetkazildi", cancelled: "❌ Bekor qilingan", returned: "↩️ Qaytarilgan" };
  const stBadge = (o) => `<span class="badge ${o.status === "new" ? "st-new" : o.status === "delivered" ? "green" : ["cancelled", "returned"].includes(o.status) ? "off" : "yellow"}">${esc(o.status_label || STATUS[o.status])}</span>`;

  // ================= DASHBOARD =================
  PAGES.dashboard = async (root) => {
    const d = await api("dashboard?period=" + S.period);
    const s = d.stats;
    const days = [...d.daily].reverse();
    const max = Math.max(1, ...days.map((x) => x.amount));
    const margin = pct(s.gross_profit, s.revenue - (s.revenue ? 0 : 0));
    root.innerHTML = `
      <div class="card-head">${periodTabs(S.period)}<div class="btn-row"><button class="btn sm" data-goto="orders">📦 Buyurtmalar (${d.active_orders} faol)</button>
        <button class="btn sm" data-goto="purchases">🛒 Kirim qilish</button></div></div>
      <div class="kpis">
        <div class="kpi glass accent"><span>💰 Tushum</span><b>${money(s.revenue)}</b><small>${s.by_status.delivered || 0} ta yakunlangan buyurtma</small></div>
        <div class="kpi glass"><span>📈 Yalpi foyda</span><b>${money(s.gross_profit)}</b><small>marja ${margin}% · tannarx ${money(s.cogs)}</small></div>
        <div class="kpi glass"><span>🧾 O'rtacha chek</span><b>${money(s.avg_check)}</b><small>${s.units} dona sotildi</small></div>
        <div class="kpi glass"><span>📦 Buyurtmalar</span><b>${s.total_orders}</b><small>${d.new_orders} yangi · ${d.active_orders} faol</small></div>
        <div class="kpi glass"><span>⏳ Jarayonda</span><b>${money(s.pending_sum)}</b><small>yetkazilmagan buyurtmalar</small></div>
        <div class="kpi glass"><span>🛒 Xaridlar (kirim)</span><b>${money(s.purchases)}</b><small>ombor: ${money(d.stock_value.cost)}</small></div>
      </div>
      <div class="grid two">
        <div class="card glass"><div class="card-head"><h3>📅 Kunlik tushum va foyda</h3><div class="legend"><span><i></i>Tushum</span><span><i class="p"></i>Foyda</span></div></div>
          ${days.length ? `<div class="chart">${days.map((x) => `<div class="col" title="${x.day}: ${money(x.amount)} · foyda ${money(x.profit)} · ${x.orders} ta">
            <div class="bars"><div class="bar" style="height:${(x.amount / max) * 100}%"></div><div class="bar p" style="height:${(Math.max(0, x.profit) / max) * 100}%"></div></div>
            <small>${x.day.slice(8, 10)}.${x.day.slice(5, 7)}</small></div>`).join("")}</div>` : '<div class="empty">Hali yakunlangan buyurtma yo\'q</div>'}</div>
        <div class="card glass"><h3>🏆 Top mahsulotlar</h3>${s.top.length ? s.top.map((t, i) => `<div class="list-row"><span>${i + 1}. ${esc(t.name)}</span><span class="muted small">${t.qty} ta · <b class="gold">${money(t.amount)}</b></span></div>`).join("") : '<div class="empty">—</div>'}
          ${s.top_brands.length ? `<div class="section-title">Brendlar</div>${s.top_brands.map((b) => `<div class="list-row"><span>${esc(b.name)}</span><span class="small"><b>${money(b.amount)}</b> <span class="muted">· ${pct(b.amount, s.revenue)}%</span></span></div>
            <div class="meter"><i style="width:${pct(b.amount, Math.max(...s.top_brands.map((x) => x.amount)))}%"></i></div>`).join("")}` : ""}</div>
      </div>
      <div class="grid three">
        <div class="card glass"><div class="card-head"><h3>⚠️ Kam qolgan</h3><button class="btn sm" data-goto="stock">Ombor →</button></div>
          ${d.low_stock.length ? d.low_stock.map((v) => `<div class="list-row"><span>${esc(v.name)}${v.vals.length ? ` <span class="muted small">${esc(v.vals.join(", "))}</span>` : ""}</span><span class="badge ${v.stock <= 0 ? "red" : "yellow"}">${v.stock} ta</span></div>`).join("") : '<div class="empty">Hammasi yetarli ✅</div>'}</div>
        <div class="card glass"><div class="card-head"><h3>💬 Javobsiz chatlar</h3></div>
          ${d.unread_chats.length ? d.unread_chats.map((c) => `<div class="list-row"><a href="javascript:void 0" data-order="${c.id}">${esc(c.code)}</a><span class="small">${esc(c.customer_name)} · <span class="badge red">${c.unread}</span></span></div>`).join("") : '<div class="empty">Yangi xabar yo\'q</div>'}
          ${d.pay_review ? `<div class="section-title">To'lovlar</div><div class="list-row"><span>🧾 Tekshiriladigan cheklar</span><button class="btn sm primary" data-paycheck>${d.pay_review} ta →</button></div>` : ""}
          <div class="section-title">Murojaatlar</div><div class="list-row"><span>↩️ Ochiq murojaatlar</span><button class="btn sm" data-goto="tickets">${d.open_tickets} ta →</button></div></div>
        <div class="card glass"><h3>👥 Mijozlar va baho</h3>
          <div class="list-row"><span>Buyurtma bergan mijozlar</span><b>${s.customers}</b></div>
          <div class="list-row"><span>Yangi foydalanuvchilar</span><b>${s.new_users}</b></div>
          <div class="list-row"><span>Jami foydalanuvchilar</span><b>${s.users_total}</b></div>
          <div class="list-row"><span>O'rtacha baho</span><b>${s.rating.count ? s.rating.avg.toFixed(2) + " ★" : "—"}</b></div>
          ${d.staff.length ? `<div class="section-title">Xodimlar</div>${d.staff.map((x) => `<div class="list-row"><span>${esc(x.name)}</span><span class="small">${x.c} ta · ${money(x.amount)}</span></div>`).join("")}` : ""}</div>
      </div>`;
    $$("[data-period]", root).forEach((b) => (b.onclick = () => { S.period = b.dataset.period; route(); }));
    $$("[data-goto]", root).forEach((b) => (b.onclick = () => go(b.dataset.goto)));
    $$("[data-paycheck]", root).forEach((b) => (b.onclick = () => { S.ordersTab = "payreview"; go("orders"); }));
    $$("[data-order]", root).forEach((a) => (a.onclick = () => orderModal(a.dataset.order)));
  };

  // ================= BUYURTMALAR =================
  const ORDER_TABS = { active: "🔄 Faol", payreview: "🧾 Chek tekshiruvi", new: "🕐 Yangi", packing: "📦 Yig'ilmoqda", shipping: "🚚 Yo'lda",
    delivered: "🎉 Yakunlangan", cancelled: "❌ Bekor", returned: "↩️ Qaytarilgan", all: "Hammasi" };
  PAGES.orders = async (root) => {
    if (!$("#or-list", root)) {
      root.innerHTML = `<div class="card-head"><div class="tabs" id="or-tabs">${Object.entries(ORDER_TABS).map(([k, v]) => `<button data-tab="${k}">${v}</button>`).join("")}</div>
          <input id="or-q" class="search-in" placeholder="🔍 ID, telefon yoki ism" value="${esc(S.ordersQ)}"></div>
        <div class="card glass table-wrap" id="or-list"></div>`;
      $$("#or-tabs button", root).forEach((b) => (b.onclick = () => { S.ordersTab = b.dataset.tab; loadOrders(); }));
      let tmr;
      $("#or-q", root).oninput = (e) => { clearTimeout(tmr); tmr = setTimeout(() => { S.ordersQ = e.target.value.trim(); loadOrders(); }, 350); };
      S.pageTimer = setInterval(loadOrders, 30000);
    }
    await loadOrders();
  };
  async function loadOrders() {
    const list = $("#or-list");
    if (!list) return;
    $$("#or-tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === S.ordersTab));
    const d = await api(`orders?status=${S.ordersTab}&q=${encodeURIComponent(S.ordersQ)}`);
    list.innerHTML = d.orders.length ? `<table class="t"><tr><th>ID</th><th>Holat</th><th>Mijoz</th><th>Turi</th><th class="right">Summa</th><th>Vaqt</th><th></th></tr>
      ${d.orders.map((o) => `<tr class="click" data-id="${o.id}">
        <td><b class="mono">${esc(o.code)}</b>${o.unread ? ` <span class="badge red">💬 ${o.unread}</span>` : ""}</td><td>${stBadge(o)}${o.pay_status === "review" ? ' <span class="badge yellow">🧾 chek</span>' : o.pay_status === "await" ? ' <span class="badge off">💳 to\'lanmagan</span>' : o.pay_status === "paid" ? ' <span class="badge green">💳 to\'langan</span>' : ""}</td>
        <td>${esc(o.customer_name)}<div class="muted small">${esc(phone(o.phone))}</div></td>
        <td class="small">${o.order_type === "pickup" ? "🏬 Olib ketish" : `🚚 ${esc(o.region_name)}`}<div class="muted">${o.units} dona</div></td>
        <td class="right nowrap"><b>${money(o.total)}</b></td><td class="small nowrap">${esc(dt(o.created_at))}</td>
        <td class="right">${o.next ? `<button class="btn sm primary" data-next="${o.id}:${o.next[0]}">${esc(o.next[1])}</button>` : ""}</td></tr>`).join("")}</table>`
      : '<div class="empty">Bu bo\'limda buyurtma yo\'q</div>';
    $$("tr[data-id]", list).forEach((tr) => (tr.onclick = (e) => { if (!e.target.closest("button")) orderModal(tr.dataset.id); }));
    $$("[data-next]", list).forEach((b) => (b.onclick = async () => {
      const [id, st] = b.dataset.next.split(":");
      if (await run(() => api(`orders/${id}/status`, { method: "POST", body: { status: st } }), "Holat yangilandi, mijozga xabar yuborildi")) loadOrders();
    }));
  }

  async function orderModal(id) {
    const d = await run(() => api("orders/" + id));
    if (!d) return;
    const o = d.order;
    const isPickup = o.order_type === "pickup";
    const m = openModal(modalHead(`🧾 ${esc(o.code)} ${stBadge(o)}`) + `
      <div class="od-grid">
        <div>
          <div class="card glass"><h3>Mahsulotlar</h3><table class="t">
            ${d.items.map((it) => `<tr class="it"><td><b>${esc(it.name)}</b>${it.variant ? `<div class="muted small">${esc(it.variant)}</div>` : ""}</td>
              <td class="nowrap">× ${it.qty}</td><td class="right nowrap">${money(it.price * it.qty)}<div class="muted small">tannarx ${money(it.cost * it.qty)}</div></td></tr>
              <tr><td colspan="3" class="it-serial"><input class="small" data-serial="${it.id}" placeholder="IMEI / seriya raqami" value="${esc(it.serial)}"></td></tr>`).join("")}
            <tr><td colspan="2">Mahsulotlar</td><td class="right">${money(o.subtotal)}</td></tr>
            ${o.discount ? `<tr><td colspan="2">🎁 ${esc(o.promo_code)}</td><td class="right">−${money(o.discount)}</td></tr>` : ""}
            ${!isPickup ? `<tr><td colspan="2">Yetkazish (${esc(o.region_name)})</td><td class="right">${o.delivery_fee ? money(o.delivery_fee) : "bepul"}</td></tr>` : ""}
            <tr><td colspan="2"><b>JAMI</b></td><td class="right"><b>${money(o.total)}</b></td></tr></table>
            <div class="btn-row" style="margin-top:10px"><button class="btn sm" id="od-serial">💾 IMEI ni saqlash</button><span class="muted small">Kafolat kartasida mijozga ko'rinadi</span></div></div>
          <div class="card glass"><h3>💬 Chat</h3>
            <div class="chatbox" id="od-chat">${chatHtml(d.chat)}</div>
            ${d.chat_open ? `<div class="btn-row" style="margin-top:10px;flex-wrap:nowrap"><input id="od-msg" placeholder="Mijozga xabar…"><label class="btn" title="Rasm">📷<input type="file" id="od-msg-photo" accept="image/*" hidden></label><button class="btn primary" id="od-send">Yuborish</button></div>`
              : '<p class="muted small">Buyurtma yakunlangan — chat yopilgan. Mijoz bilan telefon orqali bog\'laning yoki «Murojaatlar» bo\'limidan foydalaning.</p>'}</div>
          <div class="card glass"><h3>📸 Holat rasmlari</h3>
            <div class="media-grid">${d.media.map((x) => `<a href="${esc(imgUrl(x.path))}" target="_blank" title="${esc(STATUS[x.status] || x.status)} ${esc(x.caption)}"><img src="${esc(imgUrl(x.path))}" alt=""></a>`).join("") || '<span class="muted small">Hali rasm yo\'q</span>'}</div>
            <div class="row" style="margin-top:10px;align-items:end"><label class="f"><span>Rasm (mijozga botda yuboriladi)</span><input type="file" id="od-photo" accept="image/*"></label>
              <label class="f"><span>Izoh</span><input id="od-photo-cap" placeholder="Masalan: qadoqlandi"></label></div>
            <button class="btn sm" id="od-photo-send">📤 Yuklash va yuborish</button></div>
        </div>
        <div>
          <div class="card glass"><h3>👤 Mijoz</h3>
            <div class="list-row"><span>Ism</span><b>${esc(o.customer_name)}</b></div>
            <div class="list-row"><span>Telefon</span><a href="tel:${esc(o.phone)}">${esc(phone(o.phone))}</a></div>
            <div class="list-row"><span>Olish usuli</span><span>${isPickup ? "🏬 Do'kondan" : "🚚 Yetkazib berish"}</span></div>
            ${!isPickup ? `<div class="list-row"><span>Hudud</span><span>${esc(o.region_name)} · ${esc(o.delivery_eta)}</span></div><div class="small" style="padding:8px 0">📍 ${esc(o.address).replace(/(https:\/\/maps\S+)/, '<a href="$1" target="_blank">xaritada</a>')}</div>` : ""}
            <div class="list-row"><span>To'lov</span><span>${esc(o.payment_label)}${o.pay_label ? " · " + esc(o.pay_label) : ""}</span></div>
            ${o.comment ? `<div class="preview" style="margin-top:8px">💬 ${esc(o.comment)}</div>` : ""}
            ${o.staff_name ? `<div class="list-row"><span>Mas'ul</span><span>${esc(o.staff_name)}</span></div>` : ""}</div>
          ${o.payment_method === "card" ? `<div class="card glass ${o.pay_status === "review" ? "pay-review" : ""}"><h3>💳 Karta orqali to'lov</h3>
            <div class="list-row"><span>Holat</span><b>${esc(o.pay_label || "—")}</b></div>
            ${o.pay_note ? `<div class="list-row"><span>Rad etish sababi</span><span class="red">${esc(o.pay_note)}</span></div>` : ""}
            ${o.pay_receipt ? `<a href="${esc(imgUrl(o.pay_receipt))}" target="_blank" class="receipt"><img src="${esc(imgUrl(o.pay_receipt))}" alt="Chek"></a>` : '<p class="muted small">Mijoz hali chek yubormagan.</p>'}
            ${o.pay_status === "review" ? `<div class="hint">Summani (${money(o.total)}) hisobingizga tushganini tekshiring.</div><div class="btn-row" style="margin-top:10px">
              <button class="btn primary" id="od-pay-ok">✅ To'lovni tasdiqlash</button><button class="btn danger" id="od-pay-no">❌ Rad etish</button></div>` : ""}</div>` : ""}
          <div class="card glass"><h3>🕒 Tarix</h3><div class="timeline-mini">${d.log.map((l) => `<div>${esc(dt(l.at))} — ${esc(STATUS[l.status] || l.status)}</div>`).join("")}</div>
            ${o.cancel_reason ? `<p class="small red">Sabab: ${esc(o.cancel_reason)}</p>` : ""}</div>
          ${d.tickets.length ? `<div class="card glass"><h3>↩️ Murojaatlar</h3>${d.tickets.map((t) => `<div class="list-row"><span>${t.kind === "return" ? "Qaytarish" : "Muammo"} №${t.id}</span>${ticketBadge(t)}</div>`).join("")}
            <button class="btn sm" data-goto-t>Murojaatlar →</button></div>` : ""}
          ${d.review ? `<div class="card glass"><h3>⭐ Baho</h3><div class="yellow">${stars(d.review.rating)}</div>${d.review.comment ? `<p class="small">${esc(d.review.comment)}</p>` : ""}</div>` : ""}
          <div class="card glass"><h3>Amallar</h3><div class="btn-row">
            ${o.next ? `<button class="btn primary" id="od-next">${esc(o.next[1])}</button>` : ""}
            ${["new", "accepted", "packing", "shipping"].includes(o.status) ? '<button class="btn danger" id="od-cancel">❌ Bekor qilish</button>' : ""}
            <button class="btn danger" id="od-del">🗑 O'chirish</button></div>
            <div class="hint">Bekor qilish va o'chirishda mahsulotlar omborga qaytadi.</div></div>
        </div>
      </div>`, true);
    const reopen = () => { closeModal(); orderModal(id); if (S.page === "orders") loadOrders(); };
    const act = async (fn, msg) => { if (await run(fn, msg)) reopen(); };
    if (o.next) $("#od-next", m).onclick = () => act(() => api(`orders/${id}/status`, { method: "POST", body: { status: o.next[0] } }), "Holat yangilandi, mijozga xabar yuborildi");
    const c = $("#od-cancel", m);
    if (c) c.onclick = () => { const reason = prompt("Bekor qilish sababi (mijozga yuboriladi):", "Mahsulot omborda qolmagan"); if (reason) act(() => api(`orders/${id}/status`, { method: "POST", body: { status: "cancelled", reason } }), "Bekor qilindi"); };
    $("#od-del", m).onclick = async () => {
      if (confirm(`${o.code} butunlay o'chirilsinmi? Statistikadan ham o'chadi.`) && await run(() => api("orders/" + id, { method: "DELETE" }), "O'chirildi")) { closeModal(); route(); }
    };
    $("#od-serial", m).onclick = () => {
      const serials = Object.fromEntries($$("[data-serial]", m).map((x) => [x.dataset.serial, x.value]));
      act(() => api(`orders/${id}/serials`, { method: "POST", body: { serials } }), "IMEI saqlandi");
    };
    const send = $("#od-send", m);
    if (send) send.onclick = async () => {
      const text = $("#od-msg", m).value.trim(), file = $("#od-msg-photo", m).files[0];
      if (!text && !file) return;
      const fd = new FormData();
      fd.append("text", text);
      if (file) fd.append("file", file, file.name);
      const r = await run(() => api(`orders/${id}/chat`, { method: "POST", form: fd }), "Mijozga yuborildi");
      if (r) { $("#od-chat", m).innerHTML = chatHtml(r.chat); $("#od-msg", m).value = ""; $("#od-msg-photo", m).value = ""; scrollChat(m); }
    };
    $("#od-photo-send", m).onclick = async () => {
      const file = $("#od-photo", m).files[0];
      if (!file) return toast("Rasm tanlang", "bad");
      const fd = new FormData();
      fd.append("file", file, file.name);
      fd.append("caption", $("#od-photo-cap", m).value);
      act(() => api(`orders/${id}/media`, { method: "POST", form: fd }), "Rasm mijozga yuborildi");
    };
    const pok = $("#od-pay-ok", m), pno = $("#od-pay-no", m);
    if (pok) pok.onclick = () => act(() => api(`orders/${id}/payment`, { method: "POST", body: { action: "approve" } }), "To'lov tasdiqlandi, mijozga xabar yuborildi");
    if (pno) pno.onclick = () => {
      const note = prompt("Rad etish sababi (mijozga yuboriladi):", "Summa hisobga tushmadi");
      if (note && note.trim().length >= 3) act(() => api(`orders/${id}/payment`, { method: "POST", body: { action: "reject", note: note.trim() } }), "Chek rad etildi, mijozga sabab yuborildi");
    };
    const gt = $("[data-goto-t]", m);
    if (gt) gt.onclick = () => { closeModal(); go("tickets"); };
    scrollChat(m);
    if (d.chat_open) S.modalTimer = setInterval(async () => {
      const fresh = await api("orders/" + id).catch(() => null);
      const box = $("#od-chat");
      if (fresh && box && fresh.chat.length !== box.children.length) { box.innerHTML = chatHtml(fresh.chat); scrollChat(document); }
    }, 8000);
  }
  const chatHtml = (msgs) => msgs.map((x) => `<div class="msg ${x.sender}">${x.path ? `<a href="${esc(imgUrl(x.path))}" target="_blank"><img src="${esc(imgUrl(x.path))}" alt=""></a>` : ""}${esc(x.text)}
    <small>${x.sender === "customer" ? "Mijoz" : esc(x.name || "Do'kon")} · ${esc(dt(x.at))}</small></div>`).join("") || '<span class="muted small">Xabarlar yo\'q</span>';
  const scrollChat = (root) => { const b = $("#od-chat", root); if (b) b.scrollTop = b.scrollHeight; };

  // ================= MUROJAATLAR =================
  const TICKET_ST = { open: "🕐 Ochiq", approved: "✅ Tasdiqlangan", rejected: "❌ Rad etilgan", resolved: "✅ Hal qilingan" };
  const ticketBadge = (t) => `<span class="badge ${t.status === "open" ? "red" : t.status === "rejected" ? "off" : "green"}">${TICKET_ST[t.status]}</span>`;
  PAGES.tickets = async (root) => {
    const d = await api("tickets?status=" + S.ticketsTab);
    root.innerHTML = `<div class="card-head"><div class="tabs">${Object.entries({ open: `🕐 Ochiq (${d.open})`, approved: "✅ Tasdiqlangan", rejected: "❌ Rad etilgan", resolved: "✅ Hal qilingan", all: "Hammasi" })
        .map(([k, v]) => `<button data-tt="${k}" class="${k === S.ticketsTab ? "active" : ""}">${v}</button>`).join("")}</div>
        <span class="muted small">Mijoz bilan telefon orqali bog'laning, so'ng qaror qabul qiling — mijozga botda xabar boradi.</span></div>
      ${d.tickets.length ? d.tickets.map((t) => `<div class="card glass">
        <div class="card-head"><h3>${t.kind === "return" ? "↩️ Qaytarish arizasi" : "⚠️ Muammo xabari"} №${t.id} ${ticketBadge(t)}</h3>
          <span class="muted small">${esc(dt(t.created_at))}</span></div>
        <div class="grid two"><div>
          <div class="list-row"><span>Buyurtma</span><a href="javascript:void 0" data-order="${t.order_id}">${esc(t.code)}</a></div>
          <div class="list-row"><span>Mijoz</span><b>${esc(t.customer_name)}</b></div>
          <div class="list-row"><span>Telefon</span><a href="tel:${esc(t.phone)}">📞 ${esc(phone(t.phone))}</a></div>
          <div class="list-row"><span>Buyurtma summasi</span><span>${money(t.total)} · ${esc(STATUS[t.order_status] || t.order_status)}</span></div>
          <div class="preview" style="margin-top:10px">${esc(t.reason)}</div>
          ${t.note ? `<p class="small muted">Izoh: ${esc(t.note)}${t.handler ? " — " + esc(t.handler) : ""}</p>` : ""}</div>
          <div><div class="media-grid">${t.photos.map((p) => `<a href="${esc(imgUrl(p))}" target="_blank"><img src="${esc(imgUrl(p))}" alt=""></a>`).join("") || '<span class="muted small">Rasm yo\'q</span>'}</div>
          ${t.status === "open" ? `<label class="f" style="margin-top:12px"><span>Izoh (mijozga yuboriladi)</span><input data-note="${t.id}" placeholder="${t.kind === "return" ? "Masalan: kuryer ertaga mahsulotni olib ketadi" : "Masalan: muammo hal qilindi"}"></label>
            <div class="btn-row">${t.kind === "return" ? `<button class="btn primary" data-tk="${t.id}:approve:1">✅ Qaytarish (omborga)</button>
              <button class="btn" data-tk="${t.id}:approve:0">✅ Qaytarish (nuqsonli)</button><button class="btn danger" data-tk="${t.id}:reject:0">❌ Rad etish</button>`
              : `<button class="btn primary" data-tk="${t.id}:resolve:0">✅ Hal qilindi</button>`}</div>` : ""}</div></div></div>`).join("")
        : '<div class="card glass empty">Bu bo\'limda murojaat yo\'q</div>'}`;
    $$("[data-tt]", root).forEach((b) => (b.onclick = () => { S.ticketsTab = b.dataset.tt; route(); }));
    $$("[data-order]", root).forEach((a) => (a.onclick = () => orderModal(a.dataset.order)));
    $$("[data-tk]", root).forEach((b) => (b.onclick = async () => {
      const [id, action, restock] = b.dataset.tk.split(":");
      const note = $(`[data-note="${id}"]`, root).value.trim();
      if (action === "reject" && !note) return toast("Rad etish sababini yozing — u mijozga yuboriladi", "bad");
      if (action === "approve" && !confirm(restock === "1" ? "Qaytarish tasdiqlansinmi? Mahsulot omborga qaytadi." : "Qaytarish tasdiqlansinmi? Mahsulot nuqsonli — omborga qaytmaydi.")) return;
      if (await run(() => api("tickets/" + id, { method: "POST", body: { action, note, restock: restock === "1" } }), "Saqlandi, mijozga xabar yuborildi")) { route(); poll(); }
    }));
  };

  // ================= MAHSULOTLAR =================
  async function loadCatalog() { S.catalog = await api("catalog"); return S.catalog; }
  const BADGES = { hit: "🔥 Hit", new: "✨ Yangi", top: "⭐ Top" };
  PAGES.products = async (root) => {
    const c = await loadCatalog();
    root.innerHTML = `<div class="card-head"><div class="btn-row"><input id="pr-q" class="search-in" placeholder="🔍 Nomi, brend yoki SKU" value="${esc(S.prodQ)}">
        <select id="pr-cat" style="width:auto"><option value="0">Barcha kategoriyalar</option>${c.categories.map((x) => `<option value="${x.id}" ${S.prodCat === x.id ? "selected" : ""}>${esc(x.emoji)} ${esc(x.name)} (${x.count})</option>`).join("")}</select></div>
        <div class="btn-row">${c.demo ? `<button class="btn danger sm" id="pr-demo">🧹 Demo mahsulotlarni o'chirish (${c.demo})</button>` : ""}<button class="btn primary" id="pr-add">＋ Yangi mahsulot</button></div></div>
      <div class="card glass table-wrap" id="pr-list"></div>`;
    const draw = () => {
      const q = S.prodQ.toLowerCase();
      const items = c.products.filter((p) => (!S.prodCat || p.category_id === S.prodCat)
        && (!q || [p.name, p.name_ru, p.brand, ...p.variants.map((v) => v.sku)].some((x) => (x || "").toLowerCase().includes(q))));
      $("#pr-list", root).innerHTML = items.length ? `<table class="t"><tr><th>Mahsulot</th><th>Kategoriya</th><th>Variantlar</th><th class="right">Narx</th><th class="right">Qoldiq</th><th class="right">Sotilgan</th><th>Holat</th></tr>
        ${items.map((p) => `<tr class="click" data-id="${p.id}"><td><div class="cell-prod"><img class="thumb" src="${esc(imgUrl(p.images[0] && p.images[0].path))}" alt="">
            <div><b>${esc(p.name)}</b><div class="muted small">${esc(p.brand || "—")} ${p.badges.map((b) => BADGES[b]).join(" ")} ${p.is_demo ? '<span class="badge off">demo</span>' : ""}</div></div></div></td>
          <td class="small">${esc(p.category)}</td><td class="small">${p.variants.length}</td>
          <td class="right nowrap">${money(p.price_min)}${p.discount_active ? ` <span class="badge red">-${p.discount_active}%</span>` : ""}</td>
          <td class="right"><span class="badge ${p.stock <= 0 ? "red" : p.stock <= 3 ? "yellow" : "green"}">${p.stock}</span></td>
          <td class="right">${p.sold}</td><td>${!p.is_active ? '<span class="badge off">Yashirin</span>' : p.stock <= 0 ? '<span class="badge red">Sotuvda yo\'q</span>' : '<span class="badge green">Sotuvda</span>'}</td></tr>`).join("")}</table>`
        : '<div class="empty">Mahsulot topilmadi</div>';
      $$("tr[data-id]", root).forEach((tr) => (tr.onclick = () => productEditor(c.products.find((p) => p.id === +tr.dataset.id))));
    };
    draw();
    let tmr;
    $("#pr-q", root).oninput = (e) => { clearTimeout(tmr); tmr = setTimeout(() => { S.prodQ = e.target.value.trim(); draw(); }, 200); };
    $("#pr-cat", root).onchange = (e) => { S.prodCat = +e.target.value; draw(); };
    $("#pr-add", root).onclick = () => productEditor(null);
    const demo = $("#pr-demo", root);
    if (demo) demo.onclick = async () => { if (confirm("Barcha demo mahsulotlar o'chirilsinmi? (O'zingiz qo'shganlar qoladi)") && await run(() => api("demo", { method: "DELETE" }), "Demo mahsulotlar o'chirildi")) route(); };
  };

  function productEditor(p) {
    const c = S.catalog;
    const st = {
      options: p ? JSON.parse(JSON.stringify(p.options)) : [],
      variants: p ? p.variants.map((v) => ({ ...v })) : [{ vals: [], price: "", sku: "", stock: 0, cost: 0, is_active: true }],
      images: p ? p.images.map((i) => ({ ...i })) : [],
      specs: p ? p.specs.map((s) => ({ ...s })) : [],
    };
    const catTpl = (cid) => ((c.categories.find((x) => x.id === cid) || {}).spec_template || []);
    if (!p) st.specs = catTpl(c.categories[0] && c.categories[0].id).map((t) => ({ k: t.k, k_ru: t.k_ru, v: "", v_ru: "" }));
    const m = openModal(modalHead(p ? "✏️ " + esc(p.name) : "＋ Yangi mahsulot") + `
      <div class="pe-grid"><div>
        <div class="card glass"><h3>Asosiy</h3>
          <div class="row"><label class="f"><span>Nomi (uz) *</span><input id="pe-name" maxlength="80" value="${esc(p ? p.name : "")}" placeholder="iPhone 15"></label>
            <label class="f"><span>Nomi (ru)</span><input id="pe-name-ru" maxlength="80" value="${esc(p ? p.name_ru : "")}" placeholder="bo'sh — uz bilan bir xil"></label></div>
          <div class="row"><label class="f"><span>Kategoriya *</span><select id="pe-cat">${c.categories.map((x) => `<option value="${x.id}" ${p && p.category_id === x.id ? "selected" : ""}>${esc(x.emoji)} ${esc(x.name)}</option>`).join("")}</select></label>
            <label class="f"><span>Brend</span><select id="pe-brand"><option value="">—</option>${c.brands.map((b) => `<option value="${b.id}" ${p && p.brand_id === b.id ? "selected" : ""}>${esc(b.name)}</option>`).join("")}</select></label>
            <label class="f"><span>Kafolat, oy</span><input id="pe-war" type="number" min="0" max="120" value="${p ? p.warranty_months : 12}"></label></div>
          <label class="f"><span>Tavsif (uz)</span><textarea id="pe-desc" rows="3" maxlength="2000">${esc(p ? p.description : "")}</textarea></label>
          <label class="f"><span>Tavsif (ru)</span><textarea id="pe-desc-ru" rows="3" maxlength="2000">${esc(p ? p.description_ru : "")}</textarea></label></div>
        <div class="card glass"><div class="card-head"><h3>🎨 Variant turlari</h3><button class="btn sm" id="pe-opt-add">＋ Tur qo'shish</button></div>
          <div class="hint" style="margin:-8px 0 10px">Masalan: <b>Rang</b> — Qora, Oq · <b>Xotira</b> — 128 GB, 256 GB. Har bir kombinatsiya pastdagi jadvalda o'z narxi va qoldig'iga ega. Variantsiz mahsulot uchun bo'sh qoldiring.</div>
          <div id="pe-opts"></div></div>
        <div class="card glass"><h3>💰 Narx va qoldiq</h3><div class="table-wrap" id="pe-vars"></div>
          <div class="hint">Qoldiq faqat yangi variant uchun kiritiladi. Keyingi o'zgarishlar — <b>Ombor</b> (inventarizatsiya) yoki <b>Xaridlar</b> (kirim) orqali, tarix saqlanadi.</div></div>
        <div class="card glass"><div class="card-head"><h3>📋 Xarakteristikalar</h3><div class="btn-row"><button class="btn sm" id="pe-spec-tpl">Shablondan</button><button class="btn sm" id="pe-spec-add">＋ Qator</button></div></div>
          <div class="spec-row muted small"><span>Nomi</span><span>Qiymat (uz)</span><span>Qiymat (ru)</span><span></span></div><div id="pe-specs"></div></div>
      </div><div>
        <div class="card glass"><h3>🖼 Galereya</h3><div class="imgs" id="pe-imgs"></div>
          <div class="hint">Birinchi rasm — asosiy. Rang tanlangan rasm shu rangdagi variant tanlanganda ko'rsatiladi. <b>Rasm formati: 3:4 (tik)</b> (masalan 900×1200 yoki 1200×1600), oq yoki och fon. Boshqa nisbatdagi rasm kesilmaydi — 3:4 ga oq fon bilan joylanadi.</div></div>
        <div class="card glass"><h3>🏷 Belgilar va chegirma</h3>
          <div class="btn-row">${Object.entries(BADGES).map(([k, v]) => `<label class="check"><input type="checkbox" data-badge="${k}" ${p && p.badges.includes(k) ? "checked" : ""}>${v}</label>`).join("")}</div>
          <div class="row" style="margin-top:8px"><label class="f"><span>Chegirma, %</span><input id="pe-disc" type="number" min="0" max="90" value="${p ? p.discount_percent : 0}"></label>
            <label class="f"><span>Chegirma tugashi</span><input id="pe-disc-until" type="date" value="${p && p.discount_until ? p.discount_until.slice(0, 10) : ""}"></label></div>
          <label class="switch" style="margin-top:6px"><input type="checkbox" id="pe-active" ${!p || p.is_active ? "checked" : ""}><i></i>Sotuvda (vitrinada ko'rinadi)</label></div>
        ${p ? `<div class="card glass"><h3>📊 Ko'rsatkichlar</h3><div class="list-row"><span>Sotilgan</span><b>${p.sold} dona</b></div><div class="list-row"><span>Qoldiq</span><b>${p.stock} dona</b></div><div class="list-row"><span>Qo'shilgan</span><span>${esc(dt(p.created_at))}</span></div></div>` : ""}
      </div></div>
      <div class="modal-foot">${p ? '<button class="btn danger" id="pe-del">🗑 O\'chirish</button>' : ""}<span style="flex:1"></span>
        <button class="btn" data-close>Bekor</button><button class="btn primary" id="pe-save">💾 Saqlash</button></div>`, true);

    // --- variant turlari ---
    const drawOpts = () => {
      $("#pe-opts", m).innerHTML = st.options.map((o, i) => `<div class="opt-row">
        <input data-on="${i}" placeholder="Nomi (Rang)" value="${esc(o.name)}"><input data-onr="${i}" placeholder="RU (Цвет)" value="${esc(o.name_ru || "")}">
        <div><input data-ov="${i}" placeholder="Qiymatlar vergul bilan: Qora, Oq" value="${esc(o.values.join(", "))}">
          <input data-ovr="${i}" placeholder="RU: Чёрный, Белый" value="${esc((o.values_ru || []).join(", "))}" style="margin-top:4px"></div>
        <button class="icon-btn" data-od="${i}">✕</button></div>`).join("") || '<span class="muted small">Variant turlari yo\'q — bitta narx.</span>';
      $$("[data-on]", m).forEach((x) => (x.oninput = () => (st.options[+x.dataset.on].name = x.value)));
      $$("[data-onr]", m).forEach((x) => (x.oninput = () => (st.options[+x.dataset.onr].name_ru = x.value)));
      $$("[data-ov]", m).forEach((x) => (x.onchange = () => { st.options[+x.dataset.ov].values = x.value.split(",").map((s) => s.trim()).filter(Boolean); rebuildVariants(); }));
      $$("[data-ovr]", m).forEach((x) => (x.onchange = () => (st.options[+x.dataset.ovr].values_ru = x.value.split(",").map((s) => s.trim()))));
      $$("[data-od]", m).forEach((x) => (x.onclick = () => { st.options.splice(+x.dataset.od, 1); rebuildVariants(); drawOpts(); }));
    };
    // kombinatsiyalar: mavjud narx/qoldiqlar saqlanadi
    const rebuildVariants = () => {
      const combos = st.options.reduce((acc, o) => acc.flatMap((a) => o.values.map((v) => [...a, v])), [[]]);
      const old = st.variants;
      const fallback = old.find((v) => v.price) || {};
      st.variants = combos.map((vals) => old.find((v) => v.vals.join("|") === vals.join("|"))
        || { vals, price: fallback.price || "", sku: "", stock: 0, cost: 0, is_active: true });
      drawVars(); drawImgs();
    };
    const drawVars = () => {
      $("#pe-vars", m).innerHTML = `<table class="t vt"><tr>${st.options.length ? "<th>Variant</th>" : ""}<th>Narx, so'm *</th><th>SKU</th><th>Qoldiq</th><th>Tannarx</th><th>Faol</th></tr>
        ${st.variants.map((v, i) => `<tr>${st.options.length ? `<td class="vname">${esc(v.vals.join(" · "))}</td>` : ""}
          <td><input data-vp="${i}" type="number" min="1000" step="1000" value="${esc(v.price)}"></td>
          <td><input data-vs="${i}" maxlength="40" value="${esc(v.sku)}"></td>
          <td>${v.id ? `<b>${v.stock}</b>` : `<input data-vq="${i}" type="number" min="0" value="${v.stock || 0}" style="width:80px">`}</td>
          <td>${v.id ? `<span class="muted">${num(v.cost)}</span>` : `<input data-vc="${i}" type="number" min="0" step="1000" value="${v.cost || ""}" placeholder="0">`}</td>
          <td><input type="checkbox" data-va="${i}" ${v.is_active !== false ? "checked" : ""}></td></tr>`).join("")}</table>
        ${st.variants.length > 1 ? '<button class="btn sm" id="pe-price-all" style="margin-top:8px">Birinchi narxni hammasiga</button>' : ""}`;
      $$("[data-vp]", m).forEach((x) => (x.oninput = () => (st.variants[+x.dataset.vp].price = x.value)));
      $$("[data-vs]", m).forEach((x) => (x.oninput = () => (st.variants[+x.dataset.vs].sku = x.value)));
      $$("[data-vq]", m).forEach((x) => (x.oninput = () => (st.variants[+x.dataset.vq].stock = +x.value || 0)));
      $$("[data-vc]", m).forEach((x) => (x.oninput = () => (st.variants[+x.dataset.vc].cost = +x.value || 0)));
      $$("[data-va]", m).forEach((x) => (x.onchange = () => (st.variants[+x.dataset.va].is_active = x.checked)));
      const all = $("#pe-price-all", m);
      if (all) all.onclick = () => { st.variants.forEach((v) => (v.price = st.variants[0].price)); drawVars(); };
    };
    // --- galereya ---
    const colors = () => (st.options[0] ? st.options[0].values : []);
    const drawImgs = () => {
      $("#pe-imgs", m).innerHTML = st.images.map((img, i) => `<div class="img-tile">${i === 0 ? '<span class="main-tag">Asosiy</span>' : ""}<img src="${esc(imgUrl(img.path))}" alt="">
        <div class="ops">${colors().length ? `<select data-ic="${i}"><option value="">umumiy</option>${colors().map((c) => `<option ${img.color === c ? "selected" : ""}>${esc(c)}</option>`).join("")}</select>` : ""}
          <button data-il="${i}" title="Chapga">◀</button><button data-ix="${i}" title="O'chirish">✕</button></div></div>`).join("")
        + '<label class="drop" id="pe-drop"><span>＋ Rasm yuklash<br><b>3:4 · 900×1200</b><br>yoki shu yerga tashlang</span><input type="file" accept="image/*" multiple hidden id="pe-file"></label>';
      $$("[data-ic]", m).forEach((x) => (x.onchange = () => (st.images[+x.dataset.ic].color = x.value)));
      $$("[data-il]", m).forEach((x) => (x.onclick = () => { const i = +x.dataset.il; if (i > 0) { [st.images[i - 1], st.images[i]] = [st.images[i], st.images[i - 1]]; drawImgs(); } }));
      $$("[data-ix]", m).forEach((x) => (x.onclick = () => { st.images.splice(+x.dataset.ix, 1); drawImgs(); }));
      const drop = $("#pe-drop", m), file = $("#pe-file", m);
      const addFiles = async (files) => {
        for (const f of [...files].slice(0, 15 - st.images.length)) {
          const size = await imageSize(f);
          if (size && Math.abs(size.w / size.h - 3 / 4) > 0.03
              && !confirm(`"${f.name}" — ${size.w}×${size.h}, 3:4 emas.\n\nMahsulot rasmlari 3:4 (tik) nisbatda bo'lishi kerak (masalan 900×1200).\nBaribir yuklansinmi? Rasm kesilmaydi, chetlariga oq fon qo'shiladi.`)) continue;
          toast("⏳ Yuklanmoqda: " + f.name);
          const path = await run(() => upload(f, "product"));
          if (path) st.images.push({ path, color: "" });
        }
        drawImgs();
      };
      file.onchange = () => addFiles(file.files);
      drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
      drop.ondragleave = () => drop.classList.remove("over");
      drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); addFiles(e.dataTransfer.files); };
    };
    // --- xarakteristikalar ---
    const drawSpecs = () => {
      $("#pe-specs", m).innerHTML = st.specs.map((s, i) => `<div class="spec-row"><input data-sk="${i}" value="${esc(s.k)}" placeholder="Ekran">
        <input data-sv="${i}" value="${esc(s.v)}" placeholder="6.1&quot; OLED"><input data-svr="${i}" value="${esc(s.v_ru || "")}" placeholder="ru (ixtiyoriy)">
        <button class="icon-btn" data-sx="${i}">✕</button></div>`).join("") || '<span class="muted small">Xarakteristika yo\'q</span>';
      $$("[data-sk]", m).forEach((x) => (x.oninput = () => (st.specs[+x.dataset.sk].k = x.value)));
      $$("[data-sv]", m).forEach((x) => (x.oninput = () => (st.specs[+x.dataset.sv].v = x.value)));
      $$("[data-svr]", m).forEach((x) => (x.oninput = () => (st.specs[+x.dataset.svr].v_ru = x.value)));
      $$("[data-sx]", m).forEach((x) => (x.onclick = () => { st.specs.splice(+x.dataset.sx, 1); drawSpecs(); }));
    };
    $("#pe-opt-add", m).onclick = () => { if (st.options.length < 3) { st.options.push({ name: "", name_ru: "", values: [], values_ru: [] }); drawOpts(); } };
    $("#pe-spec-add", m).onclick = () => { st.specs.push({ k: "", k_ru: "", v: "", v_ru: "" }); drawSpecs(); };
    $("#pe-spec-tpl", m).onclick = () => {
      catTpl(+$("#pe-cat", m).value).forEach((tpl) => { if (!st.specs.some((s) => s.k === tpl.k)) st.specs.push({ k: tpl.k, k_ru: tpl.k_ru, v: "", v_ru: "" }); });
      drawSpecs();
    };
    drawOpts(); drawVars(); drawImgs(); drawSpecs();

    $("#pe-save", m).onclick = async () => {
      if (st.options.some((o) => !o.name.trim() || !o.values.length)) return toast("Har bir variant turining nomi va qiymatlari bo'lsin", "bad");
      // bo'sh xarakteristika nomlari uchun RU nomini shablondan olamiz
      const tpl = catTpl(+$("#pe-cat", m).value);
      const specs = st.specs.filter((s) => s.k.trim() && s.v.trim()).map((s) => ({ ...s, k_ru: s.k_ru || (tpl.find((x) => x.k === s.k) || {}).k_ru || "" }));
      const body = {
        name: $("#pe-name", m).value, name_ru: $("#pe-name-ru", m).value, category_id: +$("#pe-cat", m).value,
        brand_id: $("#pe-brand", m).value ? +$("#pe-brand", m).value : null, warranty_months: +$("#pe-war", m).value || 0,
        description: $("#pe-desc", m).value, description_ru: $("#pe-desc-ru", m).value,
        options: st.options.map((o) => ({ ...o, name: o.name.trim() })), specs, images: st.images,
        variants: st.variants.map((v) => ({ id: v.id, vals: v.vals, price: +v.price, sku: v.sku, stock: v.stock, cost: v.cost, is_active: v.is_active !== false })),
        badges: $$("[data-badge]", m).filter((x) => x.checked).map((x) => x.dataset.badge),
        discount_percent: +$("#pe-disc", m).value || 0, discount_until: $("#pe-disc-until", m).value, is_active: $("#pe-active", m).checked,
      };
      const btn = $("#pe-save", m);
      btn.disabled = true;
      const r = await run(() => api(p ? "products/" + p.id : "products", { method: p ? "PUT" : "POST", body }), "Saqlandi — bot va Mini App'da yangilandi");
      btn.disabled = false;
      if (r) { closeModal(); route(); }
    };
    if (p) $("#pe-del", m).onclick = async () => {
      if (confirm(`«${p.name}» o'chirilsinmi? (Buyurtmalar tarixida qoladi)`) && await run(() => api("products/" + p.id, { method: "DELETE" }), "O'chirildi")) { closeModal(); route(); }
    };
  }

  // ================= KATEGORIYALAR VA BRENDLAR =================
  PAGES.categories = async (root) => {
    const c = await loadCatalog();
    root.innerHTML = `<div class="grid two">
      <div class="card glass"><div class="card-head"><h3>🗂 Kategoriyalar</h3><button class="btn primary sm" id="cat-add">＋ Kategoriya</button></div>
        <table class="t">${c.categories.map((x, i) => `<tr><td style="font-size:22px;width:40px">${esc(x.emoji)}</td>
          <td><b>${esc(x.name)}</b><div class="muted small">${esc(x.name_ru || "")} · ${x.count} mahsulot · ${x.spec_template.length} xarakteristika</div></td>
          <td>${x.is_active ? '<span class="badge green">Faol</span>' : '<span class="badge off">Yashirin</span>'}</td>
          <td class="right nowrap"><button class="btn sm" data-cu="${i}">▲</button><button class="btn sm" data-cd="${i}">▼</button><button class="btn sm" data-ce="${x.id}">✏️</button></td></tr>`).join("")}</table></div>
      <div class="card glass"><div class="card-head"><h3>🏷 Brendlar</h3><button class="btn primary sm" id="br-add">＋ Brend</button></div>
        <table class="t">${c.brands.map((b, i) => `<tr><td style="width:56px">${b.logo ? `<img class="thumb" src="${esc(imgUrl(b.logo))}" alt="">` : ""}</td>
          <td><b>${esc(b.name)}</b><div class="muted small">${b.count} mahsulot</div></td>
          <td>${b.is_active ? '<span class="badge green">Faol</span>' : '<span class="badge off">Yashirin</span>'}</td>
          <td class="right nowrap"><button class="btn sm" data-bu="${i}">▲</button><button class="btn sm" data-bd="${i}">▼</button><button class="btn sm" data-be="${b.id}">✏️</button></td></tr>`).join("")}</table></div></div>`;
    const reorder = async (kind, list, i, dir) => {
      const j = i + dir;
      if (j < 0 || j >= list.length) return;
      const ids = list.map((x) => x.id);
      [ids[i], ids[j]] = [ids[j], ids[i]];
      if (await run(() => api(kind + "/order", { method: "POST", body: { ids } }))) route();
    };
    $$("[data-cu]", root).forEach((b) => (b.onclick = () => reorder("categories", c.categories, +b.dataset.cu, -1)));
    $$("[data-cd]", root).forEach((b) => (b.onclick = () => reorder("categories", c.categories, +b.dataset.cd, 1)));
    $$("[data-bu]", root).forEach((b) => (b.onclick = () => reorder("brands", c.brands, +b.dataset.bu, -1)));
    $$("[data-bd]", root).forEach((b) => (b.onclick = () => reorder("brands", c.brands, +b.dataset.bd, 1)));
    $("#cat-add", root).onclick = () => categoryModal(null);
    $$("[data-ce]", root).forEach((b) => (b.onclick = () => categoryModal(c.categories.find((x) => x.id === +b.dataset.ce))));
    $("#br-add", root).onclick = () => brandModal(null);
    $$("[data-be]", root).forEach((b) => (b.onclick = () => brandModal(c.brands.find((x) => x.id === +b.dataset.be))));
  };
  function categoryModal(cat) {
    const tpl = cat ? cat.spec_template.map((x) => ({ ...x })) : [];
    const m = openModal(modalHead(cat ? "Kategoriya: " + esc(cat.name) : "Yangi kategoriya") + `
      <div class="row"><label class="f"><span>Emoji</span><input id="ca-emoji" maxlength="8" value="${esc(cat ? cat.emoji : "📦")}"></label>
        <label class="f"><span>Nomi (uz) *</span><input id="ca-name" maxlength="40" value="${esc(cat ? cat.name : "")}"></label>
        <label class="f"><span>Nomi (ru)</span><input id="ca-name-ru" maxlength="40" value="${esc(cat ? cat.name_ru : "")}"></label></div>
      <label class="switch"><input type="checkbox" id="ca-active" ${!cat || cat.is_active ? "checked" : ""}><i></i>Faol (vitrinada ko'rinadi)</label>
      <div class="section-title">Xarakteristikalar shabloni</div><div class="hint" style="margin-top:-6px;margin-bottom:8px">Yangi mahsulot qo'shganda shu maydonlar avtomatik chiqadi (masalan: Ekran, Protsessor, Batareya).</div>
      <div id="ca-tpl"></div><button class="btn sm" id="ca-tpl-add">＋ Maydon</button>
      <div class="modal-foot">${cat ? '<button class="btn danger" id="ca-del">🗑 O\'chirish</button>' : ""}<span style="flex:1"></span><button class="btn" data-close>Bekor</button><button class="btn primary" id="ca-save">💾 Saqlash</button></div>`);
    const draw = () => {
      $("#ca-tpl", m).innerHTML = tpl.map((x, i) => `<div class="btn-edit-row"><input data-tk="${i}" value="${esc(x.k)}" placeholder="Ekran"><input data-tr="${i}" value="${esc(x.k_ru)}" placeholder="Экран"><button class="icon-btn" data-tx="${i}">✕</button></div>`).join("");
      $$("[data-tk]", m).forEach((x) => (x.oninput = () => (tpl[+x.dataset.tk].k = x.value)));
      $$("[data-tr]", m).forEach((x) => (x.oninput = () => (tpl[+x.dataset.tr].k_ru = x.value)));
      $$("[data-tx]", m).forEach((x) => (x.onclick = () => { tpl.splice(+x.dataset.tx, 1); draw(); }));
    };
    draw();
    $("#ca-tpl-add", m).onclick = () => { tpl.push({ k: "", k_ru: "" }); draw(); };
    $("#ca-save", m).onclick = async () => {
      const body = { emoji: $("#ca-emoji", m).value, name: $("#ca-name", m).value, name_ru: $("#ca-name-ru", m).value, is_active: $("#ca-active", m).checked, spec_template: tpl };
      if (await run(() => api(cat ? "categories/" + cat.id : "categories", { method: cat ? "PATCH" : "POST", body }), "Saqlandi")) { closeModal(); route(); }
    };
    if (cat) $("#ca-del", m).onclick = async () => {
      if (confirm("Kategoriya o'chirilsinmi?")) { const r = await run(() => api("categories/" + cat.id, { method: "DELETE" })); if (r) { toast(r.hidden ? "Eski buyurtmalar uchun yashirildi" : "O'chirildi"); closeModal(); route(); } }
    };
  }
  function brandModal(b) {
    let logo = b ? b.logo : "";
    const m = openModal(modalHead(b ? "Brend: " + esc(b.name) : "Yangi brend") + `
      <label class="f"><span>Nomi *</span><input id="bn-name" maxlength="40" value="${esc(b ? b.name : "")}"></label>
      <label class="f"><span>Logo (ixtiyoriy, PNG shaffof fon bilan)</span><input type="file" id="bn-logo" accept="image/*"></label>
      <div id="bn-prev">${logo ? `<img class="logo-prev" src="${esc(imgUrl(logo))}">` : ""}</div>
      ${b ? `<label class="switch" style="margin-top:10px"><input type="checkbox" id="bn-active" ${b.is_active ? "checked" : ""}><i></i>Faol</label>` : ""}
      <div class="modal-foot">${b ? '<button class="btn danger" id="bn-del">🗑 O\'chirish</button>' : ""}<span style="flex:1"></span><button class="btn" data-close>Bekor</button><button class="btn primary" id="bn-save">💾 Saqlash</button></div>`);
    $("#bn-logo", m).onchange = async (e) => {
      const path = await run(() => upload(e.target.files[0], "brand"));
      if (path) { logo = path; $("#bn-prev", m).innerHTML = `<img class="logo-prev" src="${esc(imgUrl(path))}">`; }
    };
    $("#bn-save", m).onclick = async () => {
      const body = { name: $("#bn-name", m).value, logo };
      if (b) body.is_active = $("#bn-active", m).checked;
      if (await run(() => api(b ? "brands/" + b.id : "brands", { method: b ? "PATCH" : "POST", body }), "Saqlandi")) { closeModal(); route(); }
    };
    if (b) $("#bn-del", m).onclick = async () => { if (confirm("Brend o'chirilsinmi?") && await run(() => api("brands/" + b.id, { method: "DELETE" }), "O'chirildi")) { closeModal(); route(); } };
  }

  // ================= OMBOR =================
  PAGES.stock = async (root) => {
    const d = await api(`stock?q=${encodeURIComponent(S.stockQ)}&low=${S.stockLow ? 1 : 0}`);
    root.innerHTML = `<div class="kpis">
        <div class="kpi glass"><span>📦 Jami qoldiq</span><b>${num(d.value.units)} dona</b></div>
        <div class="kpi glass"><span>💵 Tannarx bo'yicha</span><b>${money(d.value.cost)}</b></div>
        <div class="kpi glass"><span>🏷 Sotuv narxida</span><b>${money(d.value.retail)}</b><small>potensial foyda ${money(d.value.retail - d.value.cost)}</small></div></div>
      <div class="card-head"><div class="btn-row"><input id="sk-q" class="search-in" placeholder="🔍 Mahsulot, brend yoki SKU" value="${esc(S.stockQ)}">
        <label class="check"><input type="checkbox" id="sk-low" ${S.stockLow ? "checked" : ""}>Faqat kam qolganlar (≤ ${d.low})</label></div>
        <div class="btn-row"><button class="btn" id="sk-csv">📥 CSV</button><button class="btn primary" data-goto="purchases">🛒 Kirim qilish</button></div></div>
      <div class="card glass table-wrap"><table class="t"><tr><th>Mahsulot</th><th>SKU</th><th class="right">Narx</th><th class="right">Tannarx</th><th class="right">Qoldiq</th><th>Inventarizatsiya</th><th></th></tr>
        ${d.items.map((v) => `<tr><td><b>${esc(v.name)}</b>${v.vals.length ? `<div class="muted small">${esc(v.vals.join(", "))}</div>` : ""}<div class="muted small">${esc(v.brand || "")} · ${esc(v.category || "")}</div></td>
          <td class="mono small">${esc(v.sku)}</td><td class="right nowrap">${money(v.price)}</td><td class="right nowrap muted">${money(v.cost)}</td>
          <td class="right"><span class="badge ${v.stock <= 0 ? "red" : v.stock <= d.low ? "yellow" : "green"}">${v.stock}</span></td>
          <td><div class="btn-row" style="flex-wrap:nowrap"><input type="number" min="0" data-sv="${v.id}" value="${v.stock}" style="width:84px"><button class="btn sm" data-ss="${v.id}">💾</button></div></td>
          <td><button class="btn sm" data-mv="${v.id}" title="Harakatlar tarixi">🕒</button></td></tr>`).join("") || '<tr><td colspan="7" class="empty">Topilmadi</td></tr>'}</table></div>`;
    let tmr;
    $("#sk-q", root).oninput = (e) => { clearTimeout(tmr); tmr = setTimeout(() => { S.stockQ = e.target.value.trim(); route(); }, 400); };
    $("#sk-low", root).onchange = (e) => { S.stockLow = e.target.checked; route(); };
    $("#sk-csv", root).onclick = () => download("stock.csv");
    $$("[data-goto]", root).forEach((b) => (b.onclick = () => go(b.dataset.goto)));
    $$("[data-ss]", root).forEach((b) => (b.onclick = async () => {
      const id = b.dataset.ss, val = +$(`[data-sv="${id}"]`, root).value;
      const note = prompt("Izoh (masalan: inventarizatsiya, shikastlangan)", "Inventarizatsiya");
      if (note === null) return;
      if (await run(() => api("stock/" + id, { method: "POST", body: { stock: val, note } }), "Qoldiq yangilandi")) route();
    }));
    $$("[data-mv]", root).forEach((b) => (b.onclick = () => movesModal(b.dataset.mv)));
  };
  const MOVE = { purchase: "🛒 Kirim", order: "📦 Sotuv", cancel: "↩️ Bekor qilingan", return: "↩️ Qaytarilgan", adjust: "✏️ Tuzatish" };
  async function movesModal(vid) {
    const d = await run(() => api("moves?variant_id=" + vid));
    if (!d) return;
    openModal(modalHead("🕒 Ombor harakatlari") + `<div class="table-wrap"><table class="t"><tr><th>Vaqt</th><th>Turi</th><th class="right">O'zgarish</th><th>Hujjat</th><th>Izoh</th><th>Kim</th></tr>
      ${d.moves.map((x) => `<tr><td class="small nowrap">${esc(dt(x.at))}</td><td>${MOVE[x.reason] || x.reason}</td><td class="right"><b class="${x.delta > 0 ? "green" : "red"}">${x.delta > 0 ? "+" : ""}${x.delta}</b></td>
        <td class="mono small">${esc(x.ref)}</td><td class="small">${esc(x.note)}</td><td class="small">${esc(x.user || "")}</td></tr>`).join("") || '<tr><td colspan="6" class="empty">Harakat yo\'q</td></tr>'}</table></div>`, true);
  }

  // ================= XARIDLAR (KIRIM) =================
  PAGES.purchases = async (root) => {
    const [d, c] = await Promise.all([api("purchases"), loadCatalog()]);
    root.innerHTML = `<div class="grid two">
      <div class="card glass"><h3>🛒 Yangi kirim</h3>
        <div class="row"><label class="f"><span>Yetkazib beruvchi</span><select id="pu-sup"><option value="">—</option>${d.suppliers.map((s) => `<option value="${s.id}">${esc(s.name)}</option>`).join("")}</select></label>
          <label class="f"><span>Izoh</span><input id="pu-note" maxlength="300" placeholder="Masalan: oktyabr partiyasi"></label></div>
        <label class="f"><span>Mahsulot qo'shish</span><select id="pu-pick"><option value="">— variantni tanlang —</option>
          ${c.products.map((p) => p.variants.map((v) => `<option value="${v.id}" data-cost="${v.cost}">${esc(p.name)}${v.label ? " · " + esc(v.label) : ""} (qoldiq ${v.stock})</option>`).join("")).join("")}</select></label>
        <table class="t vt" id="pu-items"></table>
        <div class="list-row"><b>Jami</b><b id="pu-total">0 so'm</b></div>
        <button class="btn primary" id="pu-save" style="margin-top:10px">✅ Kirimni saqlash (qoldiq oshadi)</button>
        <div class="hint">Tannarx o'rtacha og'irlik usulida qayta hisoblanadi va foydada ishlatiladi. Tugagan mahsulotga obuna bo'lgan mijozlarga "sotuvga chiqdi" xabari yuboriladi.</div></div>
      <div class="card glass"><div class="card-head"><h3>🏭 Yetkazib beruvchilar</h3><button class="btn sm" id="su-add">＋ Qo'shish</button></div>
        ${d.suppliers.length ? `<table class="t">${d.suppliers.map((s) => `<tr><td><b>${esc(s.name)}</b><div class="muted small">${esc(s.phone)} ${esc(s.note)}</div></td><td class="right small">${s.purchases} ta kirim<br><b>${money(s.amount)}</b></td></tr>`).join("")}</table>` : '<div class="empty">Hali yo\'q</div>'}</div></div>
      <div class="card glass table-wrap"><h3>📜 Kirimlar tarixi</h3>${d.purchases.length ? `<table class="t"><tr><th>Hujjat</th><th>Sana</th><th>Yetkazib beruvchi</th><th class="right">Dona</th><th class="right">Summa</th><th>Izoh</th></tr>
        ${d.purchases.map((p) => `<tr class="click" data-pid="${p.id}"><td class="mono">${esc(p.code)}</td><td class="small">${esc(dt(p.created_at))}</td><td>${esc(p.supplier || "—")}</td>
          <td class="right">${p.units}</td><td class="right"><b>${money(p.total)}</b></td><td class="small">${esc(p.note)}</td></tr>`).join("")}</table>` : '<div class="empty">Hali kirim yo\'q</div>'}</div>`;
    const rows = [];
    const names = Object.fromEntries(c.products.flatMap((p) => p.variants.map((v) => [v.id, p.name + (v.label ? " · " + v.label : "")])));
    const draw = () => {
      $("#pu-items", root).innerHTML = rows.length ? `<tr><th>Mahsulot</th><th>Soni</th><th>Kelish narxi</th><th></th></tr>` + rows.map((r, i) => `<tr><td class="small">${esc(names[r.variant_id])}</td>
        <td><input type="number" min="1" data-q="${i}" value="${r.qty}" style="width:76px"></td><td><input type="number" min="0" step="1000" data-c="${i}" value="${r.cost}"></td>
        <td><button class="icon-btn" data-x="${i}">✕</button></td></tr>`).join("") : "";
      $("#pu-total", root).textContent = money(rows.reduce((a, r) => a + r.qty * r.cost, 0));
      $$("[data-q]", root).forEach((x) => (x.oninput = () => { rows[+x.dataset.q].qty = +x.value || 0; $("#pu-total", root).textContent = money(rows.reduce((a, r) => a + r.qty * r.cost, 0)); }));
      $$("[data-c]", root).forEach((x) => (x.oninput = () => { rows[+x.dataset.c].cost = +x.value || 0; $("#pu-total", root).textContent = money(rows.reduce((a, r) => a + r.qty * r.cost, 0)); }));
      $$("[data-x]", root).forEach((x) => (x.onclick = () => { rows.splice(+x.dataset.x, 1); draw(); }));
    };
    $("#pu-pick", root).onchange = (e) => {
      const opt = e.target.selectedOptions[0];
      if (opt && opt.value && !rows.some((r) => r.variant_id === +opt.value)) rows.push({ variant_id: +opt.value, qty: 1, cost: +opt.dataset.cost || 0 });
      e.target.value = ""; draw();
    };
    $("#pu-save", root).onclick = async () => {
      if (!rows.length) return toast("Mahsulot qo'shing", "bad");
      const body = { supplier_id: $("#pu-sup", root).value ? +$("#pu-sup", root).value : null, note: $("#pu-note", root).value, items: rows };
      if (await run(() => api("purchases", { method: "POST", body }), "Kirim saqlandi, qoldiq oshdi")) route();
    };
    $("#su-add", root).onclick = () => {
      const m = openModal(modalHead("Yetkazib beruvchi") + `<label class="f"><span>Nomi *</span><input id="su-name"></label>
        <label class="f"><span>Telefon</span><input id="su-phone"></label><label class="f"><span>Izoh</span><input id="su-note"></label>
        <div class="modal-foot"><span style="flex:1"></span><button class="btn" data-close>Bekor</button><button class="btn primary" id="su-save">💾 Saqlash</button></div>`);
      $("#su-save", m).onclick = async () => {
        if (await run(() => api("suppliers", { method: "POST", body: { name: $("#su-name", m).value, phone: $("#su-phone", m).value, note: $("#su-note", m).value } }), "Qo'shildi")) { closeModal(); route(); }
      };
    };
    $$("[data-pid]", root).forEach((tr) => (tr.onclick = async () => {
      const r = await run(() => api("purchases/" + tr.dataset.pid));
      if (r) openModal(modalHead("Kirim " + esc(r.purchase.code)) + `<p class="muted small">${esc(dt(r.purchase.created_at))} · ${esc(r.purchase.supplier || "—")} · ${esc(r.purchase.note)}</p>
        <table class="t"><tr><th>Mahsulot</th><th class="right">Soni</th><th class="right">Narx</th><th class="right">Summa</th></tr>${r.items.map((i) => `<tr><td>${esc(i.name)}</td><td class="right">${i.qty}</td><td class="right">${money(i.cost)}</td><td class="right">${money(i.qty * i.cost)}</td></tr>`).join("")}
        <tr><td colspan="3"><b>Jami</b></td><td class="right"><b>${money(r.purchase.total)}</b></td></tr></table>`);
    }));
  };

  // ================= HUDUDLAR =================
  PAGES.regions = async (root) => {
    const { regions } = await api("regions");
    root.innerHTML = `<div class="card-head"><p class="muted" style="margin:0;flex:1">Mijoz rasmiylashtirishda hududni tanlaydi — yetkazish narxi va muddati shunga qarab hisoblanadi. «Bepul» — buyurtma shu summadan oshsa yetkazish bepul.</p>
        <button class="btn primary" id="rg-add">＋ Hudud</button></div>
      <div class="card glass table-wrap"><table class="t"><tr><th>Hudud (uz / ru)</th><th>Narx, so'm</th><th>Bepul (dan)</th><th>Muddat, kun</th><th>Faol</th><th></th></tr>
        ${regions.map((r, i) => `<tr data-r="${r.id}"><td><input data-f="name" value="${esc(r.name)}" style="margin-bottom:4px"><input data-f="name_ru" value="${esc(r.name_ru)}" placeholder="ru"></td>
          <td><input data-f="fee" type="number" min="0" step="1000" value="${r.fee}"></td><td><input data-f="free_from" type="number" min="0" step="100000" value="${r.free_from}"></td>
          <td><div class="btn-row" style="flex-wrap:nowrap"><input data-f="days_min" type="number" min="0" value="${r.days_min}" style="width:64px">–<input data-f="days_max" type="number" min="0" value="${r.days_max}" style="width:64px"></div></td>
          <td><label class="switch"><input type="checkbox" data-f="is_active" ${r.is_active ? "checked" : ""}><i></i></label></td>
          <td class="nowrap"><button class="btn sm primary" data-save="${r.id}">💾</button> <button class="btn sm" data-up="${i}">▲</button> <button class="btn sm danger" data-del="${r.id}">✕</button></td></tr>`).join("")}</table>
        <div class="hint">0 kun — bugun yetkaziladi. Muddat «0–1» — «bugun–ertaga» ko'rinishida chiqadi.</div></div>`;
    $$("[data-save]", root).forEach((b) => (b.onclick = async () => {
      const tr = $(`tr[data-r="${b.dataset.save}"]`, root);
      const body = Object.fromEntries($$("[data-f]", tr).map((x) => [x.dataset.f, x.type === "checkbox" ? x.checked : x.type === "number" ? +x.value : x.value]));
      await run(() => api("regions/" + b.dataset.save, { method: "PATCH", body }), "Saqlandi");
    }));
    $$("[data-del]", root).forEach((b) => (b.onclick = async () => { if (confirm("Hudud o'chirilsinmi?") && await run(() => api("regions/" + b.dataset.del, { method: "DELETE" }), "O'chirildi")) route(); }));
    $$("[data-up]", root).forEach((b) => (b.onclick = async () => {
      const i = +b.dataset.up; if (!i) return;
      const ids = regions.map((r) => r.id); [ids[i - 1], ids[i]] = [ids[i], ids[i - 1]];
      if (await run(() => api("regions/order", { method: "POST", body: { ids } }))) route();
    }));
    $("#rg-add", root).onclick = async () => {
      const name = prompt("Hudud nomi:");
      if (name && await run(() => api("regions", { method: "POST", body: { name, fee: 70000, days_min: 2, days_max: 4 } }), "Qo'shildi")) route();
    };
  };

  // ================= BOT XABARLARI =================
  PAGES.texts = async (root) => {
    if (!S.texts) S.texts = (await api("texts")).texts;
    const groups = [...new Set(S.texts.map((x) => x.group))];
    if (!S.textGroup || !groups.includes(S.textGroup)) S.textGroup = groups[0];
    const changed = (g) => S.texts.filter((x) => x.group === g && (x.uz.value != null || x.ru.value != null)).length;
    root.innerHTML = `
      <div class="card glass" style="padding:14px"><div class="btn-row"><input id="tx-q" class="search-in" placeholder="🔍 Matn ichidan qidirish…" value="${esc(S.textQuery)}">
        <span class="muted small" style="flex:1">Har bir xabarni o'zbek va rus tilida tahrirlang. <b>{shop}</b> — do'kon nomi, <b>{name}</b> kabi o'zgaruvchilar avtomatik almashtiriladi. Bot xabarlari Telegram rich formatida yuboriladi.</span></div></div>
      <div class="text-groups" id="tx-groups">${groups.map((g) => `<button data-g="${esc(g)}" class="${g === S.textGroup && !S.textQuery ? "active" : ""}">${esc(g)} <small>${changed(g) ? "✎" + changed(g) : ""}</small></button>`).join("")}</div>
      <div id="tx-list"></div>`;
    $$("#tx-groups button", root).forEach((b) => (b.onclick = () => { S.textGroup = b.dataset.g; S.textQuery = ""; PAGES.texts(root); }));
    let tmr;
    $("#tx-q", root).oninput = (e) => { clearTimeout(tmr); tmr = setTimeout(() => { S.textQuery = e.target.value.trim(); drawTexts(); }, 300); };
    drawTexts();
  };
  function drawTexts() {
    const q = S.textQuery.toLowerCase();
    const items = q ? S.texts.filter((x) => [x.key, x.uz.default, x.ru.default, x.uz.value, x.ru.value].some((s) => s && s.toLowerCase().includes(q)))
      : S.texts.filter((x) => x.group === S.textGroup);
    $$("#tx-groups button").forEach((b) => b.classList.toggle("active", !q && b.dataset.g === S.textGroup));
    const list = $("#tx-list");
    if (!items.length) { list.innerHTML = '<div class="card glass empty">Hech narsa topilmadi</div>'; return; }
    list.innerHTML = items.slice(0, 120).map(textItem).join("") + (items.length > 120 ? '<div class="empty">Qidiruvni aniqlashtiring…</div>' : "");
    $$(".text-item", list).forEach(bindTextItem);
  }
  const kind = (x) => (x.key.startsWith("b_") ? "⌨️ Tugma" : x.key.startsWith("w_") ? "✨ Mini ilova" : x.plain ? "🔤 Oddiy matn" : "📝 Formatlanadigan xabar");
  function textItem(x) {
    const side = (lang) => {
      const id = `tx-${x.key}-${lang}`, val = x[lang].value ?? x[lang].default;
      return `<div>
        <div class="text-head"><span class="lang-tag">${lang.toUpperCase()}</span>
          ${x[lang].value != null ? '<span class="badge red">o\'zgartirilgan</span>' : '<span class="badge off">asl</span>'}
          <span class="sp"></span><span class="muted small" data-count="${lang}">${val.length}/${x.max}</span></div>
        ${x.plain ? "" : toolbarHtml(id)}
        <textarea id="${id}" data-lang="${lang}" rows="${Math.min(10, Math.max(2, val.split("\n").length + 1))}" maxlength="${x.max}">${esc(val)}</textarea>
        ${x.vars.length ? `<div class="chips">${x.vars.map((v) => `<button type="button" class="chip" data-target="${id}" data-ins="{${v}}">{${v}}</button>`).join("")}</div>` : ""}
        <div class="f-label" style="margin-top:8px">Ko'rinishi:</div>
        <div class="preview ${x.plain ? "plain" : ""}" data-prev="${lang}">${tgPreview(val, x.plain)}</div>
        <div class="err" data-err="${lang}"></div>
        <div class="btn-row" style="margin-top:8px"><button class="btn sm primary" data-save="${lang}">💾 Saqlash</button>
          <button class="btn sm ${x[lang].value != null ? "" : "hidden"}" data-reset="${lang}">↺ Asl holiga</button></div></div>`;
    };
    return `<div class="text-item glass ${x.uz.value != null || x.ru.value != null ? "changed" : ""}" data-key="${esc(x.key)}">
      <div class="text-head"><code>${esc(x.key)}</code><span class="badge">${kind(x)}</span>${S.textQuery ? `<span class="muted small">${esc(x.group)}</span>` : ""}</div>
      <div class="editor-grid">${side("uz")}${side("ru")}</div></div>`;
  }
  function bindTextItem(el) {
    const x = S.texts.find((t) => t.key === el.dataset.key);
    ["uz", "ru"].forEach((lang) => {
      const ta = $(`textarea[data-lang="${lang}"]`, el);
      ta.oninput = () => {
        $(`[data-prev="${lang}"]`, el).innerHTML = tgPreview(ta.value, x.plain);
        $(`[data-count="${lang}"]`, el).textContent = `${ta.value.length}/${x.max}`;
        const unknown = (ta.value.match(/\{(\w+)\}/g) || []).map((s) => s.slice(1, -1)).filter((v) => !x.vars.includes(v));
        $(`[data-err="${lang}"]`, el).textContent = unknown.length ? "Noma'lum o'zgaruvchi: " + unknown.map((v) => `{${v}}`).join(", ") : "";
      };
      $(`[data-save="${lang}"]`, el).onclick = () => saveText(x, lang, ta.value, el);
      $(`[data-reset="${lang}"]`, el).onclick = () => { if (confirm("Asl matnga qaytarilsinmi?")) saveText(x, lang, "", el); };
    });
  }
  async function saveText(x, lang, value, el) {
    const errEl = $(`[data-err="${lang}"]`, el);
    const isDefault = value === x[lang].default;
    try { await api("texts", { method: "PUT", body: { key: x.key, lang, value: isDefault ? "" : value } }); }
    catch (e) { errEl.textContent = "⚠️ " + e.message; return toast("Saqlanmadi: " + e.message, "bad"); }
    x[lang].value = value && !isDefault ? value : null;
    toast(x[lang].value == null ? "Asl matn tiklandi" : "Saqlandi — bot darhol yangilandi");
    const fresh = document.createElement("div");
    fresh.innerHTML = textItem(x);
    el.replaceWith(fresh.firstElementChild);
    bindTextItem($(`.text-item[data-key="${CSS.escape(x.key)}"]`));
  }

  // ================= SOZLAMALAR (do'kon va brend) =================
  const DAYS = [["mon", "Dushanba"], ["tue", "Seshanba"], ["wed", "Chorshanba"], ["thu", "Payshanba"], ["fri", "Juma"], ["sat", "Shanba"], ["sun", "Yakshanba"]];
  PAGES.settings = async (root) => {
    const { settings: s, status } = await api("settings");
    let logo = s.shop_logo, mark = s.shop_mark, banner = s.shop_banner;
    root.innerHTML = `
      <div class="card glass"><h3>🚦 Buyurtma qabul qilish</h3>
        <div class="tabs" id="mode-tabs"><button data-mode="auto">🕐 Qabul qilinadi (ish vaqti jadval bo'yicha)</button><button data-mode="open">🟢 Doim ochiq</button><button data-mode="closed">🔴 Vaqtincha to'xtatilgan</button></div>
        <p class="muted small">Buyurtmalar 24/7 qabul qilinadi; ish vaqti — operatorlar javob beradigan vaqt (mijozga ko'rsatiladi). Hozir: <b>${status.accepting ? "🟢 qabul qilinmoqda" : "🔴 to'xtatilgan"}</b>${status.accepting && !status.is_open ? " · ish vaqtidan tashqari" : ""}.</p></div>
      <div class="grid two">
        <div class="card glass"><h3>🎨 Brend (white-label)</h3>
          <div class="row"><label class="f"><span>Do'kon nomi *</span><input id="b-name" maxlength="40" value="${esc(s.shop_name)}"></label>
            <label class="f"><span>Buyurtma prefiksi</span><input id="b-prefix" maxlength="4" value="${esc(s.order_prefix)}" style="text-transform:uppercase"><div class="hint">TZ → TZ-482917</div></label></div>
          <label class="f"><span>Shior</span><input id="b-tagline" maxlength="80" value="${esc(s.shop_tagline)}"></label>
          <div class="row"><div class="f"><span class="f-label">Asosiy rang</span><div class="color-row"><input type="color" id="b-color" value="${esc(s.brand_color)}"><input id="b-color-hex" value="${esc(s.brand_color)}" maxlength="7"></div></div>
            <div class="f"><span class="f-label">Logo (to'liq)</span><div id="b-logo-prev">${logo ? `<img class="logo-prev" src="${esc(imgUrl(logo))}">` : ""}</div><input type="file" id="b-logo" accept="image/*" style="margin-top:6px"></div></div>
          <div class="f"><span class="f-label">Belgi (kichik logo / ikonka)</span><div id="b-mark-prev">${mark ? `<img class="logo-prev" src="${esc(imgUrl(mark))}">` : ""}</div><input type="file" id="b-mark" accept="image/*" style="margin-top:6px"></div>
          <div class="f"><span class="f-label">Salomlashuv banneri (/start, 2:1, to'q fon)</span><div id="b-banner-prev">${banner ? `<img class="logo-prev" src="${esc(imgUrl(banner))}">` : ""}</div><input type="file" id="b-banner" accept="image/*" style="margin-top:6px"></div>
          <label class="f"><span>Do'kon haqida (uz)</span><textarea id="b-about-uz" rows="2" maxlength="600">${esc(s.about_uz)}</textarea></label>
          <label class="f"><span>Do'kon haqida (ru)</span><textarea id="b-about-ru" rows="2" maxlength="600">${esc(s.about_ru)}</textarea></label>
          <div class="row"><label class="f"><span>Instagram</span><input id="b-ig" value="${esc(s.instagram)}" placeholder="@techzone"></label>
            <label class="f"><span>Telegram kanal</span><input id="b-tgc" value="${esc(s.telegram_channel)}" placeholder="@techzone_uz"></label>
            <label class="f"><span>Sayt</span><input id="b-web" value="${esc(s.website)}" placeholder="https://"></label></div>
          <div class="hint">Nom, logo va rang bot xabarlari, Mini App va shu panelda darhol almashadi. Bot nomi va avatarini @BotFather'da o'zgartiring.</div></div>
        <div>
          <div class="card glass"><h3>🏬 Do'kon va olib ketish</h3>
            <div class="row"><label class="f"><span>Telefon</span><input id="s-phone" maxlength="40" value="${esc(s.phone)}" placeholder="+998 90 123 45 67"></label>
              <label class="f"><span>Manzil</span><input id="s-addr" maxlength="200" value="${esc(s.shop_address)}"></label></div>
            <label class="f"><span>📍 Google Maps havolasi</span><input id="s-map" maxlength="500" value="${esc(s.shop_map_url)}" placeholder="https://maps.app.goo.gl/..."></label>
            <div class="row"><label class="f"><span>Kenglik (lat)</span><input id="s-lat" value="${esc(s.shop_lat)}"></label><label class="f"><span>Uzunlik (lng)</span><input id="s-lng" value="${esc(s.shop_lng)}"></label></div>
            <div class="hint">Olib ketish buyurtmasi tayyor bo'lganda mijozga shu joy Telegram lokatsiyasi sifatida yuboriladi. Koordinata bo'sh bo'lsa havoladan aniqlanadi.</div></div>
          <div class="card glass"><h3>🚚 Savdo qoidalari</h3>
            <div class="btn-row" style="gap:24px;margin-bottom:12px"><label class="switch"><input type="checkbox" id="s-deliv" ${s.delivery_enabled ? "checked" : ""}><i></i>Yetkazib berish</label>
              <label class="switch"><input type="checkbox" id="s-pick" ${s.pickup_enabled ? "checked" : ""}><i></i>Olib ketish</label></div>
            <div class="row"><label class="f"><span>Minimal buyurtma, so'm</span><input type="number" id="s-min" min="0" step="10000" value="${s.min_order}"></label>
              <label class="f"><span>"Oz qoldi" chegarasi, dona</span><input type="number" id="s-low" min="0" value="${s.low_stock}"></label>
              <label class="f"><span>Qaytarish muddati, kun</span><input type="number" id="s-ret" min="0" max="365" value="${s.return_days}"><div class="hint">0 — qaytarish o'chirilgan</div></label></div>
            <div class="hint">Yetkazish narxlari va muddatlari — <a href="#regions">Yetkazish hududlari</a> bo'limida.</div></div>
          <div class="card glass"><h3>💳 Karta orqali to'lov</h3>
            <label class="switch" style="margin-bottom:12px"><input type="checkbox" id="s-card-on" ${s.card_enabled ? "checked" : ""}><i></i>Kartaga o'tkazma bilan to'lovni yoqish</label>
            <label class="f"><span>Karta raqami</span><input id="s-card-num" inputmode="numeric" maxlength="23" value="${esc(s.card_number)}" placeholder="8600 1234 5678 9012"></label>
            <div class="row"><label class="f"><span>Karta egasi</span><input id="s-card-holder" maxlength="60" value="${esc(s.card_holder)}" placeholder="ISM FAMILIYA"></label>
              <label class="f"><span>Bank / karta turi</span><input id="s-card-bank" maxlength="40" value="${esc(s.card_bank)}" placeholder="Uzcard · Kapitalbank"></label></div>
            <div class="hint">Mijoz buyurtmadan so'ng shu kartani ko'radi (nusxalash tugmasi bilan), pul o'tkazib chek yuklaydi. Chek menejerlarga botda va bu yerda <a href="#orders">Buyurtmalar → 🧾 Chek tekshiruvi</a> da chiqadi.</div></div>
        </div></div>
      <div class="card glass"><div class="card-head"><h3>🕐 Operatorlar ish vaqti</h3><button class="btn sm" id="sch-copy">Dushanbani hamma kunlarga</button></div>
        <div class="sched">${DAYS.map(([d, name]) => { const v = s.schedule[d]; return `<div class="sched-row ${v ? "" : "closed"}" data-day="${d}"><b>${name}</b>
          <label class="check" style="margin:0"><input type="checkbox" data-off ${v ? "" : "checked"}>Dam olish</label>
          <input type="time" data-open value="${v ? v[0] : "09:00"}"><input type="time" data-close value="${v ? v[1] : "21:00"}"></div>`; }).join("")}</div></div>
      <div class="btn-row"><button class="btn primary" id="s-save">💾 Sozlamalarni saqlash</button><span class="muted small">Saqlangach bot va Mini App darhol yangi sozlamalar bilan ishlaydi.</span></div>`;
    let mode = s.mode;
    const drawMode = () => $$("#mode-tabs button", root).forEach((b) => b.classList.toggle("active", b.dataset.mode === mode));
    drawMode();
    $$("#mode-tabs button", root).forEach((b) => (b.onclick = async () => {
      mode = b.dataset.mode; drawMode();
      if (await run(() => api("settings", { method: "PUT", body: { mode } }), "Rejim o'zgartirildi")) poll();
    }));
    $("#b-color", root).oninput = (e) => ($("#b-color-hex", root).value = e.target.value);
    $("#b-color-hex", root).oninput = (e) => { if (/^#[0-9a-f]{6}$/i.test(e.target.value)) $("#b-color", root).value = e.target.value; };
    const up = (id, prev, kind, set) => ($(id, root).onchange = async (e) => {
      const path = await run(() => upload(e.target.files[0], kind));
      if (path) { set(path); $(prev, root).innerHTML = `<img class="logo-prev" src="${esc(imgUrl(path))}">`; }
    });
    up("#b-logo", "#b-logo-prev", "logo", (p) => (logo = p));
    up("#b-mark", "#b-mark-prev", "brand", (p) => (mark = p));
    up("#b-banner", "#b-banner-prev", "photo", (p) => (banner = p));
    $$(".sched-row [data-off]", root).forEach((c) => (c.onchange = () => c.closest(".sched-row").classList.toggle("closed", c.checked)));
    $("#sch-copy", root).onclick = () => {
      const first = $(".sched-row", root);
      $$(".sched-row", root).forEach((r) => {
        ["[data-open]", "[data-close]"].forEach((sel) => ($(sel, r).value = $(sel, first).value));
        $("[data-off]", r).checked = $("[data-off]", first).checked;
        r.classList.toggle("closed", $("[data-off]", first).checked);
      });
    };
    $("#s-save", root).onclick = async () => {
      const schedule = {};
      $$(".sched-row", root).forEach((r) => { schedule[r.dataset.day] = $("[data-off]", r).checked ? null : [$("[data-open]", r).value, $("[data-close]", r).value]; });
      const v = (id) => $(id, root).value;
      const body = {
        schedule, shop_name: v("#b-name"), order_prefix: v("#b-prefix"), shop_tagline: v("#b-tagline"), brand_color: v("#b-color-hex"),
        shop_logo: logo, shop_mark: mark, shop_banner: banner, about_uz: v("#b-about-uz"), about_ru: v("#b-about-ru"), instagram: v("#b-ig"),
        telegram_channel: v("#b-tgc"), website: v("#b-web"), phone: v("#s-phone"), shop_address: v("#s-addr"),
        shop_map_url: v("#s-map").trim(), shop_lat: v("#s-lat").trim(), shop_lng: v("#s-lng").trim(),
        delivery_enabled: $("#s-deliv", root).checked, pickup_enabled: $("#s-pick", root).checked,
        min_order: +v("#s-min") || 0, low_stock: +v("#s-low") || 0, return_days: +v("#s-ret") || 0,
        card_enabled: $("#s-card-on", root).checked, card_number: v("#s-card-num").trim(),
        card_holder: v("#s-card-holder").trim(), card_bank: v("#s-card-bank").trim(),
      };
      if (body.card_enabled && !body.card_number) return toast("Karta raqamini kiriting", "bad");
      const r = await run(() => api("settings", { method: "PUT", body }), "Saqlandi — bot va Mini App darhol yangilandi");
      if (r) { const me = await api("me").catch(() => null); if (me) applyBrand(me.brand); poll(); route(); }
    };
  };

  // ================= PROMO-KODLAR =================
  const PROMO_KIND = { percent: "Foiz (%)", fixed: "Qat'iy summa (so'm)", free_delivery: "Bepul yetkazish" };
  const promoValue = (p) => (p.kind === "percent" ? `−${p.value}%${p.max_discount ? ` (maks. ${money(p.max_discount)})` : ""}` : p.kind === "fixed" ? "−" + money(p.value) : "🚚 Bepul yetkazish");
  PAGES.promos = async (root) => {
    const { promos } = await api("promos");
    root.innerHTML = `
      <div class="card-head"><p class="muted" style="flex:1;margin:0">Mijoz kodni rasmiylashtirishda kiritadi. Shartlar avtomatik tekshiriladi.</p>
        <button class="btn primary" id="pr-add">＋ Yangi promo-kod</button></div>
      <div class="card glass table-wrap">${promos.length ? `<table class="t">
        <tr><th>Kod</th><th>Chegirma</th><th>Shartlar</th><th>Ishlatilgan</th><th>Muddat</th><th>Faol</th><th></th></tr>
        ${promos.map((p) => `<tr><td><b class="mono">${esc(p.code)}</b></td><td class="nowrap">${promoValue(p)}</td>
          <td class="small">${[p.min_order ? `min. ${money(p.min_order)}` : "", p.first_order_only ? "faqat 1-buyurtma" : "", p.per_user_limit ? `har kishi ${p.per_user_limit} marta` : "cheksiz"].filter(Boolean).join(" · ")}</td>
          <td class="nowrap">${p.used}${p.usage_limit ? " / " + p.usage_limit : ""}<div class="muted small">${money(p.discount_sum || 0)}</div></td>
          <td class="small nowrap">${p.starts_at ? esc(dt(p.starts_at)) : "—"}<br>${p.ends_at ? esc(dt(p.ends_at)) : "muddatsiz"}</td>
          <td><label class="switch"><input type="checkbox" data-toggle="${p.id}" ${p.is_active ? "checked" : ""}><i></i></label></td>
          <td><button class="btn sm" data-edit="${p.id}">✏️</button></td></tr>`).join("")}</table>`
        : '<div class="empty">Hali promo-kod yo\'q. «Yangi promo-kod» tugmasini bosing.</div>'}</div>`;
    $("#pr-add", root).onclick = () => promoModal(null);
    $$("[data-edit]", root).forEach((b) => (b.onclick = () => promoModal(promos.find((p) => p.id === +b.dataset.edit))));
    $$("[data-toggle]", root).forEach((c) => (c.onchange = () => run(() => api("promos/" + c.dataset.toggle, { method: "PATCH", body: { is_active: c.checked } }), c.checked ? "Yoqildi" : "O'chirildi")));
  };
  function promoModal(p) {
    const dtl = (s) => (s ? s.slice(0, 16).replace(" ", "T") : "");
    const m = openModal(modalHead(p ? "Promo-kod: " + esc(p.code) : "Yangi promo-kod") + `
      <div class="row"><label class="f"><span>Kod *</span><input id="pm-code" maxlength="20" value="${esc(p ? p.code : "")}" placeholder="TECH10" style="text-transform:uppercase"></label>
        <label class="f"><span>Turi *</span><select id="pm-kind">${Object.entries(PROMO_KIND).map(([k, v]) => `<option value="${k}" ${p && p.kind === k ? "selected" : ""}>${v}</option>`).join("")}</select></label>
        <label class="f" id="pm-value-wrap"><span id="pm-value-label">Qiymat</span><input id="pm-value" type="number" min="0" value="${p ? p.value : ""}"></label>
        <label class="f" id="pm-max-wrap"><span>Maks. chegirma, so'm</span><input id="pm-max" type="number" min="0" value="${p ? p.max_discount || "" : ""}" placeholder="0 — cheklovsiz"></label></div>
      <div class="section-title">Shartlar</div>
      <div class="row"><label class="f"><span>Minimal buyurtma, so'm</span><input id="pm-min" type="number" min="0" value="${p ? p.min_order || "" : ""}" placeholder="0"></label>
        <label class="f"><span>Umumiy limit</span><input id="pm-limit" type="number" min="0" value="${p ? p.usage_limit || "" : ""}" placeholder="0 — cheklovsiz"></label>
        <label class="f"><span>Har bir mijozga</span><input id="pm-per" type="number" min="0" value="${p ? p.per_user_limit : 1}"><div class="hint">0 — cheklovsiz</div></label></div>
      <div class="row"><label class="f"><span>Boshlanish</span><input id="pm-start" type="datetime-local" value="${dtl(p && p.starts_at)}"></label>
        <label class="f"><span>Tugash</span><input id="pm-end" type="datetime-local" value="${dtl(p && p.ends_at)}"></label></div>
      <label class="check"><input type="checkbox" id="pm-first" ${p && p.first_order_only ? "checked" : ""}>Faqat birinchi buyurtma uchun</label>
      <label class="check"><input type="checkbox" id="pm-active" ${!p || p.is_active ? "checked" : ""}>Faol</label>
      <div class="modal-foot">${p ? '<button class="btn danger" id="pm-del">🗑 O\'chirish</button><span style="flex:1"></span>' : ""}
        <button class="btn" data-close>Bekor</button><button class="btn primary" id="pm-save">💾 Saqlash</button></div>`);
    const syncKind = () => {
      const k = $("#pm-kind", m).value;
      $("#pm-value-wrap", m).classList.toggle("hidden", k === "free_delivery");
      $("#pm-max-wrap", m).classList.toggle("hidden", k !== "percent");
      $("#pm-value-label", m).textContent = k === "percent" ? "Foiz, % *" : "Summa, so'm *";
    };
    $("#pm-kind", m).onchange = syncKind;
    syncKind();
    $("#pm-save", m).onclick = async () => {
      const body = {
        code: $("#pm-code", m).value, kind: $("#pm-kind", m).value, value: +$("#pm-value", m).value || 0,
        max_discount: +$("#pm-max", m).value || 0, min_order: +$("#pm-min", m).value || 0,
        usage_limit: +$("#pm-limit", m).value || 0, per_user_limit: +$("#pm-per", m).value || 0,
        starts_at: $("#pm-start", m).value, ends_at: $("#pm-end", m).value,
        first_order_only: $("#pm-first", m).checked, is_active: $("#pm-active", m).checked,
      };
      if (await run(() => api(p ? "promos/" + p.id : "promos", { method: p ? "PATCH" : "POST", body }), "Saqlandi")) { closeModal(); route(); }
    };
    if (p) $("#pm-del", m).onclick = async () => {
      if (confirm(`${p.code} o'chirilsinmi?`) && await run(() => api("promos/" + p.id, { method: "DELETE" }), "O'chirildi")) { closeModal(); route(); }
    };
  }

  // ================= BAHOLAR =================
  PAGES.reviews = async (root) => {
    const low = S.reviewsLow ? "1" : "0";
    const d = await api("reviews?low=" + low);
    const dist = (st) => [5, 4, 3, 2, 1].map((n) => `<div class="btn-row" style="gap:8px;margin-bottom:4px;flex-wrap:nowrap"><span class="yellow" style="width:40px">${n} ★</span>
      <div class="meter" style="flex:1"><i style="width:${st.count ? ((st.dist[n] || 0) / st.count) * 100 : 0}%"></i></div><span class="muted small" style="width:30px">${st.dist[n] || 0}</span></div>`).join("");
    root.innerHTML = `
      <div class="grid two">
        <div class="card glass"><h3>Umumiy: ${d.total.count ? d.total.avg.toFixed(2) : "—"} ★ <span class="muted small">(${d.total.count} ta)</span></h3>${dist(d.total)}</div>
        <div class="card glass"><h3>Oxirgi 30 kun: ${d.month.count ? d.month.avg.toFixed(2) : "—"} ★ <span class="muted small">(${d.month.count} ta)</span></h3>${dist(d.month)}</div></div>
      <div class="card-head"><div class="tabs"><button data-low="0" class="${low === "0" ? "active" : ""}">Hammasi</button><button data-low="1" class="${low === "1" ? "active" : ""}">⚠️ Past baholar (1–3)</button></div></div>
      <div class="card glass">${d.reviews.length ? `<table class="t"><tr><th>Baho</th><th>Izoh</th><th>Buyurtma</th><th>Mijoz</th><th>Sana</th></tr>
        ${d.reviews.map((r) => `<tr><td class="yellow nowrap">${stars(r.rating)}</td><td>${esc(r.comment) || '<span class="muted">—</span>'}</td>
          <td><a href="javascript:void 0" data-order="${r.order_id}">${esc(r.code)}</a></td><td>${esc(r.name || "")}</td><td class="nowrap small">${esc(dt(r.created_at))}</td></tr>`).join("")}</table>`
        : '<div class="empty">Baholar yo\'q</div>'}</div>`;
    $$("[data-low]", root).forEach((b) => (b.onclick = () => { S.reviewsLow = b.dataset.low === "1"; route(); }));
    $$("[data-order]", root).forEach((a) => (a.onclick = () => orderModal(a.dataset.order)));
  };

  // ================= RASSILKA =================
  PAGES.broadcast = async (root) => {
    const st = await api("broadcast");
    const buttons = [];
    let photo = null;
    root.innerHTML = `
      <div class="grid two">
        <div class="card glass"><h3>✍️ Xabar</h3>
          <label class="f"><span>Rasm (ixtiyoriy)</span><input type="file" id="bc-photo" accept="image/jpeg,image/png,image/webp"></label>
          <div class="f-label">Matn</div>${toolbarHtml("bc-text")}
          <textarea id="bc-text" rows="8" placeholder="Masalan: 🔥 <b>iPhone 15 — 10% chegirma!</b>"></textarea>
          <div class="hint" id="bc-count"></div>
          <div class="section-title">Tugmalar (havola)</div><div id="bc-buttons"></div>
          <button class="btn sm" id="bc-btn-add">＋ Havola tugmasi</button>
          <div style="margin-top:12px"><label class="check"><input type="checkbox" id="bc-cat" checked>«🛍 Katalogni ochish» tugmasini qo'shish</label></div></div>
        <div class="card glass"><h3>👁 Ko'rinishi</h3>
          <div style="max-width:380px"><img id="bc-prev-img" class="hidden" style="width:100%;border-radius:14px 14px 0 0;display:block">
            <div class="preview" id="bc-prev">…</div><div id="bc-prev-btns"></div></div>
          <div class="section-title">Yuborish</div>
          <p class="muted small">Qabul qiluvchilar: <b>${st.users}</b> ta foydalanuvchi (botni bloklaganlardan tashqari). Xabar Telegram rich formatida yuboriladi.</p>
          <div class="btn-row"><button class="btn" id="bc-test">🧪 Avval o'zimga test</button><button class="btn primary" id="bc-send">📢 Hammaga yuborish</button></div>
          <div id="bc-status" style="margin-top:14px"></div></div></div>`;
    const ta = $("#bc-text", root);
    const draw = () => {
      $("#bc-prev", root).innerHTML = ta.value ? tgPreview(ta.value) : '<span class="muted">Matn kiriting…</span>';
      $("#bc-count", root).textContent = `${ta.value.length} / 4000 belgi`;
      const btns = buttons.filter((b) => b.text).map((b) => b.text);
      if ($("#bc-cat", root).checked) btns.push("🛍 Katalogni ochish");
      $("#bc-prev-btns", root).innerHTML = btns.map((t) => `<div class="btn sm" style="width:100%;margin-top:4px">${esc(t)}</div>`).join("");
    };
    const drawButtons = () => {
      $("#bc-buttons", root).innerHTML = buttons.map((b, i) => `<div class="btn-edit-row"><input data-bt="${i}" placeholder="Tugma matni" maxlength="40" value="${esc(b.text)}">
        <input data-bu="${i}" placeholder="https://..." value="${esc(b.url)}"><button class="icon-btn" data-bd="${i}">✕</button></div>`).join("");
      $$("[data-bt]", root).forEach((x) => (x.oninput = () => { buttons[+x.dataset.bt].text = x.value; draw(); }));
      $$("[data-bu]", root).forEach((x) => (x.oninput = () => (buttons[+x.dataset.bu].url = x.value)));
      $$("[data-bd]", root).forEach((x) => (x.onclick = () => { buttons.splice(+x.dataset.bd, 1); drawButtons(); draw(); }));
    };
    ta.oninput = draw;
    $("#bc-cat", root).onchange = draw;
    $("#bc-btn-add", root).onclick = () => { if (buttons.length < 5) { buttons.push({ text: "", url: "" }); drawButtons(); } };
    $("#bc-photo", root).onchange = (e) => {
      photo = e.target.files[0] || null;
      const img = $("#bc-prev-img", root);
      img.classList.toggle("hidden", !photo);
      if (photo) img.src = URL.createObjectURL(photo);
      draw();
    };
    draw();
    const send = async (test) => {
      if (!test && !confirm(`Xabar ${st.users} ta foydalanuvchiga yuborilsinmi?`)) return;
      const fd = new FormData();
      fd.append("text", ta.value);
      fd.append("buttons", JSON.stringify(buttons.filter((b) => b.text && b.url)));
      fd.append("catalog_btn", $("#bc-cat", root).checked ? "1" : "0");
      fd.append("test", test ? "1" : "0");
      if (photo) fd.append("photo", photo, photo.name);
      const r = await run(() => api("broadcast", { method: "POST", form: fd }), test ? "Test xabar sizga yuborildi — Telegramni tekshiring" : "Rassilka boshlandi");
      if (r && !test) watchBroadcast(root);
    };
    $("#bc-test", root).onclick = () => send(true);
    $("#bc-send", root).onclick = () => send(false);
    if (st.running || st.finished_at) watchBroadcast(root, st);
  };
  function watchBroadcast(root, first) {
    const show = (st) => {
      const box = $("#bc-status", root);
      if (!box) return false;
      const done = st.sent + st.failed;
      box.innerHTML = `<div class="progress"><i style="width:${st.total ? (done / st.total) * 100 : 0}%"></i></div>
        <div class="small">${st.running ? "⏳ Yuborilmoqda…" : "✅ Yakunlandi " + esc(st.finished_at || "")} · yuborildi: <b class="green">${st.sent}</b> · xato/bloklagan: <b class="red">${st.failed}</b> · jami: ${st.total}</div>`;
      return st.running;
    };
    if (first && !show(first)) return;
    if (S.pageTimer) clearInterval(S.pageTimer);
    S.pageTimer = setInterval(async () => {
      const st = await api("broadcast").catch(() => null);
      if (!st || !show(st)) { clearInterval(S.pageTimer); S.pageTimer = null; }
    }, 2000);
  }

  // ================= MIJOZLAR =================
  PAGES.customers = async (root) => {
    if (!$("#cu-list", root)) {
      root.innerHTML = `<div class="card-head"><input id="cu-q" class="search-in" placeholder="🔍 ID, @username, telefon yoki ism"><span class="muted small" id="cu-total"></span></div>
        <div class="card glass table-wrap" id="cu-list"></div>`;
      let tmr;
      $("#cu-q", root).oninput = (e) => { clearTimeout(tmr); tmr = setTimeout(() => loadCustomers(e.target.value.trim()), 350); };
    }
    await loadCustomers("");
  };
  async function loadCustomers(q) {
    const d = await api("customers?q=" + encodeURIComponent(q));
    $("#cu-total").textContent = `Jami: ${d.total} · xarid qilganlar: ${d.buyers}`;
    $("#cu-list").innerHTML = d.customers.length ? `<table class="t"><tr><th>Mijoz</th><th>Telefon</th><th>Hudud</th><th>Til</th><th class="right">Buyurtma</th><th class="right">Xarid</th><th>Oxirgi buyurtma</th></tr>
      ${d.customers.map((u) => `<tr><td><b>${esc(u.full_name || u.first_name || "—")}</b>${u.username ? ` <a href="https://t.me/${esc(u.username)}" target="_blank" rel="noopener">@${esc(u.username)}</a>` : ""}
        <div class="muted small">ID ${u.id}${u.role !== "user" ? ` · ${u.role === "manager" ? "👑 menejer" : "👷 xodim"}` : ""}${u.is_blocked ? ' · <span class="red">botni bloklagan</span>' : ""}</div></td>
        <td class="nowrap">${esc(phone(u.phone))}</td><td class="small">${esc(u.region || "")}</td><td>${u.lang === "ru" ? "🇷🇺" : "🇺🇿"}</td><td class="right">${u.orders}</td>
        <td class="right nowrap">${money(u.spent)}</td><td class="small nowrap">${esc(dt(u.last_order))}</td></tr>`).join("")}</table>`
      : '<div class="empty">Topilmadi</div>';
  }

  // ================= XODIMLAR =================
  PAGES.staff = async (root) => {
    const d = await api("staff");
    root.innerHTML = `
      <div class="card glass"><h3>➕ Xodim yoki menejer qo'shish</h3>
        <div class="row" style="align-items:end">
          <label class="f"><span>Telegram ID yoki @username</span><input id="st-q" placeholder="123456789 yoki @username"></label>
          <label class="f"><span>Rol</span><select id="st-role"><option value="staff">👷 Xodim — buyurtmalarni yig'adi va yetkazadi</option><option value="manager">👑 Menejer — to'liq boshqaruv</option></select></label>
          <div class="f"><button class="btn primary" id="st-add" style="width:100%">Qo'shish</button></div></div>
        <div class="hint">Odam avval botga /start bosgan bo'lishi kerak (yoki aniq Telegram ID kiriting). Buyurtma kartalari xodimlarga boradi; menejerlar faqat yakunlangan buyurtma hisobotini oladi.</div></div>
      <div class="card glass table-wrap"><h3>👥 Jamoa</h3>
        <table class="t"><tr><th>Ism</th><th>Rol</th><th>ID</th><th></th></tr>
        ${d.admins.map((id) => `<tr><td>Bosh admin (.env)</td><td>👑 Menejer</td><td class="mono">${id}</td><td class="muted small">serverda o'zgaradi</td></tr>`).join("")}
        ${d.staff.filter((u) => !d.admins.includes(u.id)).map((u) => `<tr><td><b>${esc(u.full_name || u.first_name || "—")}</b> ${u.username ? "@" + esc(u.username) : ""}<div class="muted small">${esc(phone(u.phone))}</div></td>
          <td>${u.role === "manager" ? "👑 Menejer" : "👷 Xodim"}</td><td class="mono">${u.id}</td>
          <td class="right"><button class="btn sm danger" data-rm="${u.id}">Olib tashlash</button></td></tr>`).join("")}</table></div>`;
    $("#st-add", root).onclick = async () => {
      if (await run(() => api("staff", { method: "POST", body: { query: $("#st-q", root).value, role: $("#st-role", root).value } }), "Qo'shildi va unga xabar yuborildi")) route();
    };
    $$("[data-rm]", root).forEach((b) => (b.onclick = async () => {
      if (confirm("Bu odamdan huquq olib tashlansinmi?") && await run(() => api("staff/" + b.dataset.rm, { method: "DELETE" }), "Olib tashlandi")) route();
    }));
  };

  // ================= HISOBOT VA ZAXIRA =================
  PAGES.tools = async (root) => {
    root.innerHTML = `
      <div class="grid two">
        <div class="card glass"><h3>📥 Sotuvlar hisoboti (Excel / CSV)</h3>
          <p class="muted small">Barcha buyurtmalar: mahsulotlar, summa, chegirma, yetkazish, tannarx va yalpi foyda, mijoz, xodim. Excel'da ochiladi.</p>
          ${periodTabs("month", "data-exp")}</div>
        <div class="card glass"><h3>🏷 Ombor qoldig'i (CSV)</h3><p class="muted small">Barcha variantlar: SKU, narx, tannarx, qoldiq va qoldiq qiymati.</p>
          <button class="btn" id="stk">📥 Yuklab olish</button></div>
        <div class="card glass"><h3>💾 Zaxira nusxa</h3>
          <p class="muted small">Butun baza (katalog, buyurtmalar, mijozlar, ombor, sozlamalar, matnlar) va yuklangan rasmlar bitta ZIP faylda.
            Har kuni 04:00 da bosh adminga Telegram orqali ham avtomatik yuboriladi.</p>
          <button class="btn primary" id="bk">💾 Zaxira nusxani yuklab olish</button></div></div>`;
    $$("[data-exp]", root).forEach((b) => (b.onclick = () => download("export.csv?period=" + b.dataset.exp)));
    $("#stk", root).onclick = () => download("stock.csv");
    $("#bk", root).onclick = () => download("backup");
  };

  boot();
})();
