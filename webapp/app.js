/* Tech.Zone Mini App — vanilla JS, build talab qilmaydi.
   Marshrutlar (hash): #home #catalog #catalog/c3 #p12 #cart #checkout #fav #compare #orders #oTZ-123456 #placed/TZ-1 */
(() => {
  "use strict";

  const tg = window.Telegram && window.Telegram.WebApp;
  const initData = (tg && tg.initData) || "";
  const devUser = new URLSearchParams(location.search).get("dev_user");
  const API = (((window.SHOP_CONFIG || window.YG_CONFIG) || {}).api || "").replace(/\/$/, "");
  const view = document.getElementById("view");
  const dock = document.getElementById("dock");
  const sheetEl = document.getElementById("sheet");
  const backdrop = document.getElementById("sheet-backdrop");
  const store = { get(k, d) { try { return JSON.parse(localStorage.getItem("shop_" + k)) ?? d; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem("shop_" + k, JSON.stringify(v)); } catch (e) { /* private mode */ } } };

  const S = {
    boot: null, texts: {}, lang: "uz", byId: {}, favs: new Set(),
    cart: store.get("cart", []), compare: store.get("cmp", []), draft: store.get("draft", {}),
    f: { cat: 0, brands: [], q: "", sort: "popular", min: "", max: "", stock: false, sale: false },
    pcache: {}, orders: null, timers: [], heroIdx: 0,
  };

  // ---------------- yordamchilar ----------------
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const img = (p) => (!p ? "" : /^https?:/.test(p) ? p : (API ? API + "/" : "") + p);
  const T = (k, vars) => {
    let s = S.texts[k] || k;
    if (vars) for (const [a, b] of Object.entries(vars)) s = s.split("{" + a + "}").join(b);
    return s;
  };
  const num = (n) => String(Math.round(n || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  const priceHtml = (n) => `${num(n)}<span class="cur">${S.lang === "ru" ? "сум" : "so'm"}</span>`;
  const money = (n) => String(Math.round(n || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, " ") + (S.lang === "ru" ? " сум" : " so'm");
  const ico = (name, cls = "") => `<svg class="${cls}"><use href="#i-${name}"/></svg>`;
  const haptic = (t = "light") => { try { tg && tg.HapticFeedback && (t === "ok" ? tg.HapticFeedback.notificationOccurred("success") : t === "err" ? tg.HapticFeedback.notificationOccurred("error") : t === "sel" ? tg.HapticFeedback.selectionChanged() : tg.HapticFeedback.impactOccurred(t)); } catch (e) { /* eski klient */ } };
  const clearTimers = () => { S.timers.forEach(clearInterval); S.timers = []; };

  function toast(text, bad = false) {
    const el = document.getElementById("toast");
    el.textContent = text;
    el.className = "toast" + (bad ? " bad" : "");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.add("hidden"), 2400);
    haptic(bad ? "err" : "ok");
  }

  async function api(path, opts = {}) {
    const headers = opts.body instanceof FormData ? {} : { "Content-Type": "application/json" };
    if (initData) headers["X-Telegram-Init-Data"] = initData;
    else if (devUser) headers["X-Dev-User"] = devUser;
    let res;
    try {
      res = await fetch(API + path, { ...opts, headers: { ...headers, ...(opts.headers || {}) },
        body: opts.body && !(opts.body instanceof FormData) ? JSON.stringify(opts.body) : opts.body });
    } catch (e) { throw new Error(T("network")); }
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) throw new Error(data.error || T("network"));
    return data;
  }

  // ---------------- sheet ----------------
  function openSheet(html, onMount) {
    sheetEl.innerHTML = `<div class="grab"></div>${html}`;
    sheetEl.classList.remove("hidden");
    backdrop.classList.remove("hidden");
    onMount && onMount(sheetEl);
  }
  function closeSheet() { sheetEl.classList.add("hidden"); backdrop.classList.add("hidden"); sheetEl.innerHTML = ""; }
  backdrop.addEventListener("click", closeSheet);

  // ---------------- savat / solishtirish ----------------
  const saveCart = () => { store.set("cart", S.cart); updateBadges(); };
  const cartCount = () => S.cart.reduce((a, i) => a + i.qty, 0);
  function addToCart(variantId, qty, max) {
    const it = S.cart.find((x) => x.variant_id === variantId);
    const cur = it ? it.qty : 0;
    const want = Math.min(cur + qty, max || 20, 20);
    if (want <= cur) { toast(T("maxQty"), true); return false; }
    if (it) it.qty = want; else S.cart.push({ variant_id: variantId, qty: want });
    saveCart();
    const b = document.getElementById("cart-badge");
    b.classList.remove("bump"); void b.offsetWidth; b.classList.add("bump");
    toast("✓ " + T("added"));
    return true;
  }
  function toggleCompare(pid) {
    const i = S.compare.indexOf(pid);
    if (i >= 0) S.compare.splice(i, 1);
    else {
      if (S.compare.length >= 4) { toast(T("compareLimit"), true); return false; }
      S.compare.push(pid);
      toast(T("compareAdded"));
    }
    store.set("cmp", S.compare);
    return true;
  }
  async function toggleFav(pid) {
    haptic("sel");
    const was = S.favs.has(pid);
    was ? S.favs.delete(pid) : S.favs.add(pid);
    document.querySelectorAll(`[data-fav="${pid}"]`).forEach((b) => b.classList.toggle("on", !was));
    if (!was) toast(T("favAdded"));
    try { const r = await api(`/api/favorites/${pid}`, { method: "POST" }); S.favs = new Set(r.favorites); }
    catch (e) { toast(e.message, true); }
  }
  function updateBadges() {
    const n = cartCount();
    const b = document.getElementById("cart-badge");
    b.textContent = n; b.classList.toggle("hidden", !n);
    const active = (S.orders || []).some((o) => o.unread || ["new", "accepted", "packing", "shipping"].includes(o.status));
    document.getElementById("orders-badge").classList.toggle("hidden", !active);
  }

  // ---------------- mahsulot kartochkasi ----------------
  function stockLabel(st) {
    return st === "out" ? `<span class="stock-dot out">${T("outOfStock")}</span>`
      : st === "low" ? `<span class="stock-dot low">${T("lowStockShort")}</span>` : `<span class="stock-dot">${T("inStock")}</span>`;
  }
  function badgesHtml(p) {
    const b = [];
    if (p.discount) b.push(`<span class="badge-s sale">-${p.discount}%</span>`);
    if (p.badges.includes("hit")) b.push(`<span class="badge-s">🔥 HIT</span>`);
    if (p.badges.includes("new")) b.push(`<span class="badge-s new">NEW</span>`);
    if (p.badges.includes("top")) b.push(`<span class="badge-s">⭐ TOP</span>`);
    return b.join("");
  }
  function card(p) {
    const fav = S.favs.has(p.id);
    return `<article class="card glass" data-go="#p${p.id}">
      <div class="ph"><img loading="lazy" src="${esc(img(p.image))}" alt="">
        <div class="badges">${badgesHtml(p)}</div>
        <button class="fav ${fav ? "on" : ""}" data-fav="${p.id}" aria-label="fav">${ico("heart")}</button>
        ${p.stock === "out" ? `<div class="out">${T("outOfStock")}</div>` : ""}</div>
      <div class="meta"><span class="brand">${esc(p.brand)}</span><span class="name">${esc(p.name)}</span>
        <div class="row"><div class="price-b">${p.old_price ? `<small>${money(p.old_price)}</small>` : p.price_from ? `<span class="from">${T("from")}</span>` : ""}${priceHtml(p.price)}</div>
        ${p.stock !== "out" ? `<button class="add" data-quick="${p.id}" aria-label="add">${ico("plus")}</button>` : ""}</div>
      </div></article>`;
  }

  // ---------------- marshrutlash ----------------
  const TABS = { home: "home", catalog: "catalog", cart: "cart", fav: "fav", compare: "fav", orders: "orders" };
  function parseRoute() {
    const h = decodeURIComponent(location.hash.slice(1));
    if (!h || h === "home") return { name: "home" };
    if (h.startsWith("catalog")) {
      const m = h.match(/c(\d+)/), b = h.match(/b(\d+)/);
      return { name: "catalog", cat: m ? +m[1] : null, brand: b ? +b[1] : null };
    }
    if (/^p\d+$/.test(h)) return { name: "product", id: +h.slice(1) };
    if (h.startsWith("placed/")) return { name: "placed", code: h.slice(7) };
    if (/^o[A-Z]+-\d+$/.test(h)) return { name: "order", code: h.slice(1) };
    return { name: ["cart", "checkout", "fav", "compare", "orders"].includes(h) ? h : "home" };
  }
  const go = (hash) => { if (location.hash === hash) render(); else location.hash = hash; };
  function back() { if (history.length > 1) history.back(); else go("#home"); }

  async function render() {
    clearTimers();
    closeSheet();
    const r = parseRoute();
    const tab = TABS[r.name];
    dock.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    resetDock();
    const fullscreen = ["product", "checkout", "placed"].includes(r.name);
    dock.classList.toggle("away", fullscreen);
    view.classList.toggle("no-dock", fullscreen);
    if (tg && tg.BackButton) (tab === "home" ? tg.BackButton.hide() : tg.BackButton.show());
    view.style.animation = "none"; void view.offsetWidth; view.style.animation = "";
    window.scrollTo(0, 0);
    try {
      await ({ home: renderHome, catalog: renderCatalog, product: renderProduct, cart: renderCart,
        checkout: renderCheckout, fav: renderFav, compare: renderCompare, orders: renderOrders,
        order: renderOrder, placed: renderPlaced }[r.name])(r);
    } catch (e) {
      view.innerHTML = `<div class="empty"><div class="big glass">${ico("alert")}</div><h3>${esc(e.message)}</h3>
        <button class="btn btn-white" data-act="reload">${T("retry")}</button></div>`;
    }
  }

  // ---------------- Dock: faol bo'lim kattaroq ----------------
  function resetDock() {
    const btns = [...dock.querySelectorAll("button")];
    const ai = btns.findIndex((b) => b.classList.contains("active"));
    btns.forEach((b, i) => b.style.setProperty("--s", i === ai ? 1.28 : Math.abs(i - ai) === 1 && ai >= 0 ? 1.08 : 1));
  }
  dock.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-tab]");
    if (!b) return;
    haptic("sel");
    go("#" + b.dataset.tab);
  });

  // ---------------- BOSH SAHIFA ----------------
  function topProducts(kind, n = 10) {
    const all = S.boot.products.filter((p) => p.stock !== "out");
    if (kind === "deals") return all.filter((p) => p.discount).slice(0, n);
    if (kind === "new") return [...all].sort((a, b) => (b.badges.includes("new") - a.badges.includes("new")) || b.created_at.localeCompare(a.created_at)).slice(0, n);
    return [...all].sort((a, b) => (b.badges.includes("hit") - a.badges.includes("hit")) || b.sold - a.sold).slice(0, n);
  }
  function rail(title, items, hash) {
    if (!items.length) return "";
    return `<div class="section-h"><h2>${title}</h2><button data-go="${hash}">${T("seeAll")}${ico("chev")}</button></div>
      <div class="rail">${items.map(card).join("")}</div>`;
  }
  function renderHome() {
    const b = S.boot.brand;
    const heroes = S.boot.products.filter((p) => p.stock !== "out" && (p.discount || p.badges.includes("top") || p.badges.includes("hit"))).slice(0, 5);
    view.innerHTML = `
      <div class="brandbar">${b.logo ? `<img class="logo" src="${esc(img(b.logo))}" alt="${esc(b.name)}">` : `<h1>${esc(b.name)}</h1>`}
        <span class="spacer"></span>
        <div class="lang glass"><button data-lang="uz" class="${S.lang === "uz" ? "on" : ""}">UZ</button><button data-lang="ru" class="${S.lang === "ru" ? "on" : ""}">RU</button></div></div>
      <label class="search glass">${ico("search")}<input id="home-q" type="search" placeholder="${esc(T("search"))}" autocomplete="off"></label>
      ${S.boot.settings.accepting ? "" : `<div class="note glass">${ico("alert")}<span>${T("notAccepting")}</span></div>`}
      ${heroes.length ? `<div class="rail hero-rail" id="hero">${heroes.map((p) => `
        <div class="hero glass" data-go="#p${p.id}" style="width:calc(100vw - 32px);max-width:608px;flex:none;scroll-snap-align:center">
          <div><div class="eyebrow">${p.discount ? `-${p.discount}% · ` : ""}${esc(p.brand)}</div><h3>${esc(p.name)}</h3>
            <span class="price">${p.price_from ? T("from") + " " : ""}${money(p.price)}</span>${p.old_price ? `<span class="old">${money(p.old_price)}</span>` : ""}
            <div><span class="cta">${T("show")}${ico("chev")}</span></div></div>
          <img src="${esc(img(p.image))}" alt=""></div>`).join("")}</div>
        <div class="hero-dots" id="hero-dots">${heroes.map((_, i) => `<i class="${i ? "" : "on"}"></i>`).join("")}</div>` : ""}
      <div class="section-h"><h2>${T("categories")}</h2></div>
      <div class="cats">${S.boot.categories.map((c) => `<button class="cat glass" data-go="#catalog/c${c.id}"><span class="emoji">${esc(c.emoji || "📦")}</span><b>${esc(c.name)}</b><small>${c.count}</small></button>`).join("")}</div>
      ${S.boot.brands.length ? `<div class="section-h"><h2>${T("brands")}</h2></div>
        <div class="chips">${S.boot.brands.map((x) => `<button class="chip glass" data-go="#catalog/b${x.id}">${esc(x.name)}</button>`).join("")}</div>` : ""}
      ${rail("🔥 " + T("hits"), topProducts("hits"), "#catalog")}
      ${rail("% " + T("deals"), topProducts("deals"), "#catalog")}
      ${rail("✨ " + T("newArrivals"), topProducts("new"), "#catalog")}
      <div class="perks">
        <div class="perk glass">${ico("shield")}${T("perk1")}</div>
        <div class="perk glass">${ico("truck")}${T("perk2")}</div>
        <div class="perk glass">${ico("chat")}${T("perk3")}</div></div>
      ${S.boot.settings.phone ? `<p class="center muted" style="margin-top:22px;font-size:13px">${T("questions")}: <a href="tel:${esc(S.boot.settings.phone.replace(/\s/g, ""))}">${esc(S.boot.settings.phone)}</a></p>` : ""}`;
    const q = document.getElementById("home-q");
    q.addEventListener("keydown", (e) => { if (e.key === "Enter" && q.value.trim()) { S.f.q = q.value.trim(); go("#catalog"); } });
    q.addEventListener("input", () => { if (q.value.trim().length >= 2) { S.f.q = q.value.trim(); go("#catalog"); } });
    const hero = document.getElementById("hero");
    if (hero && heroes.length > 1) {
      const dots = [...document.querySelectorAll("#hero-dots i")];
      const sync = () => { const i = Math.round(hero.scrollLeft / hero.clientWidth); S.heroIdx = i; dots.forEach((d, j) => d.classList.toggle("on", i === j)); };
      hero.addEventListener("scroll", () => requestAnimationFrame(sync), { passive: true });
      S.timers.push(setInterval(() => { const i = (S.heroIdx + 1) % heroes.length; hero.scrollTo({ left: i * hero.clientWidth, behavior: "smooth" }); }, 4500));
    }
  }

  // ---------------- KATALOG ----------------
  function filtered() {
    const f = S.f;
    const words = f.q.toLowerCase().split(/\s+/).filter(Boolean);
    let items = S.boot.products.filter((p) => (!f.cat || p.category_id === f.cat)
      && (!f.brands.length || f.brands.includes(p.brand_id))
      && (!words.length || words.every((w) => p.search.includes(w)))
      && (!f.stock || p.stock !== "out") && (!f.sale || p.discount)
      && (!f.min || p.price >= +f.min) && (!f.max || p.price <= +f.max));
    const sorters = { popular: (a, b) => b.sold - a.sold, new: (a, b) => b.created_at.localeCompare(a.created_at),
      cheap: (a, b) => a.price - b.price, expensive: (a, b) => b.price - a.price };
    items.sort((a, b) => ((a.stock === "out") - (b.stock === "out")) || sorters[f.sort](a, b));
    return items;
  }
  function renderCatalog(r) {
    if (r.cat !== null && r.cat !== undefined) S.f.cat = r.cat;
    if (r.brand) { S.f.brands = [r.brand]; S.f.cat = 0; }
    const f = S.f;
    const activeFilters = f.brands.length + (f.stock ? 1 : 0) + (f.sale ? 1 : 0) + (f.min || f.max ? 1 : 0);
    view.innerHTML = `
      <div class="topbar"><h1>${T("tabCatalog")}</h1>${S.compare.length ? `<button class="icon-btn glass" data-go="#compare">${ico("compare")}</button>` : ""}</div>
      <div class="search-row"><label class="search glass">${ico("search")}<input id="q" type="search" value="${esc(f.q)}" placeholder="${esc(T("search"))}" autocomplete="off"></label>
        <button class="icon-btn glass" data-act="filters" style="width:50px;height:50px">${ico("filter")}${activeFilters ? `<em class="badge" style="top:-2px;right:-2px">${activeFilters}</em>` : ""}</button></div>
      <div class="chips" style="margin-top:14px">
        <button class="chip glass ${!f.cat ? "on" : ""}" data-cat="0">${T("allProducts")}</button>
        ${S.boot.categories.map((c) => `<button class="chip glass ${f.cat === c.id ? "on" : ""}" data-cat="${c.id}">${esc(c.emoji)} ${esc(c.name)}</button>`).join("")}</div>
      <div class="chips" style="margin-top:8px">
        ${["popular", "new", "cheap", "expensive"].map((s) => `<button class="chip glass ${f.sort === s ? "on" : ""}" data-sort="${s}">${T("sort" + s[0].toUpperCase() + s.slice(1))}</button>`).join("")}</div>
      <p class="muted" id="found" style="margin:14px 2px 10px;font-size:13px"></p>
      <div class="grid" id="grid"></div>`;
    const draw = () => {
      const items = filtered();
      document.getElementById("found").textContent = T("found", { n: items.length });
      document.getElementById("grid").innerHTML = items.length ? items.map(card).join("")
        : `<div class="empty" style="grid-column:1/-1"><div class="big glass">${ico("search")}</div><h3>${T("searchEmpty")}</h3></div>`;
    };
    draw();
    const q = document.getElementById("q");
    q.addEventListener("input", () => { S.f.q = q.value; draw(); });
    if (f.q) { q.focus(); q.setSelectionRange(q.value.length, q.value.length); }
    view.querySelectorAll("[data-cat]").forEach((b) => b.addEventListener("click", () => { S.f.cat = +b.dataset.cat; haptic("sel"); renderCatalog({}); }));
    view.querySelectorAll("[data-sort]").forEach((b) => b.addEventListener("click", () => { S.f.sort = b.dataset.sort; haptic("sel"); renderCatalog({}); }));
  }
  function filterSheet() {
    const f = S.f;
    openSheet(`<h3>${T("filters")}</h3>
      <div class="field"><span>${T("price")}</span><div class="range">
        <input class="input" id="fmin" inputmode="numeric" placeholder="${T("priceFrom")}" value="${esc(f.min)}">
        <input class="input" id="fmax" inputmode="numeric" placeholder="${T("priceTo")}" value="${esc(f.max)}"></div></div>
      <div class="field"><span>${T("brands")}</span><div class="chips" style="flex-wrap:wrap;margin:0;padding:0">
        ${S.boot.brands.map((b) => `<button class="chip glass ${f.brands.includes(b.id) ? "on" : ""}" data-fb="${b.id}">${esc(b.name)}</button>`).join("")}</div></div>
      <label class="check"><input type="checkbox" id="fstock" ${f.stock ? "checked" : ""}>${T("inStockOnly")}</label>
      <label class="check"><input type="checkbox" id="fsale" ${f.sale ? "checked" : ""}>${T("withDiscount")}</label>
      <div style="display:flex;gap:10px;margin-top:16px"><button class="btn btn-ghost glass" data-fx="reset" style="flex:1">${T("reset")}</button>
        <button class="btn btn-primary" data-fx="apply" style="flex:2">${T("show")}</button></div>`, (el) => {
      const sel = new Set(f.brands);
      el.querySelectorAll("[data-fb]").forEach((b) => b.addEventListener("click", () => {
        const id = +b.dataset.fb; sel.has(id) ? sel.delete(id) : sel.add(id); b.classList.toggle("on"); haptic("sel");
      }));
      el.querySelector('[data-fx="reset"]').addEventListener("click", () => {
        Object.assign(S.f, { brands: [], min: "", max: "", stock: false, sale: false }); closeSheet(); renderCatalog({});
      });
      el.querySelector('[data-fx="apply"]').addEventListener("click", () => {
        const num = (id) => el.querySelector(id).value.replace(/\D/g, "");
        Object.assign(S.f, { brands: [...sel], min: num("#fmin"), max: num("#fmax"),
          stock: el.querySelector("#fstock").checked, sale: el.querySelector("#fsale").checked });
        closeSheet(); renderCatalog({});
      });
    });
  }

  // ---------------- MAHSULOT ----------------
  async function loadProduct(id) {
    if (!S.pcache[id]) S.pcache[id] = await api(`/api/products/${id}`);
    return S.pcache[id];
  }
  async function renderProduct(r) {
    view.innerHTML = `<div class="sk" style="height:100vw;max-height:520px;margin:-14px -16px 0;border-radius:0 0 34px 34px"></div>
      <div class="sk" style="height:28px;width:60%;margin-top:22px"></div><div class="sk" style="height:40px;width:40%;margin-top:14px"></div>`;
    const { product: p, alerts } = await loadProduct(r.id);
    const variants = p.variants;
    let v = variants.find((x) => x.stock !== "out") || variants[0];
    let sel = v ? [...v.vals] : [];
    let qty = 1;
    const imgsFor = (vals) => {
      const own = p.images.filter((i) => i.color && vals.includes(i.color));
      const common = p.images.filter((i) => !i.color);
      const list = own.concat(common);
      return (list.length ? list : p.images).map((i) => i.path);
    };
    const findVariant = (vals) => variants.find((x) => x.vals.every((val, i) => val === vals[i]));
    const draw = () => {
      v = findVariant(sel) || v;
      const images = imgsFor(sel);
      const out = !v || v.stock === "out";
      const inCart = v && S.cart.find((x) => x.variant_id === v.id);
      const inCmp = S.compare.includes(p.id);
      view.innerHTML = `
        <div class="pd-top"><button class="icon-btn glass" data-act="back">${ico("back")}</button>
          <div class="acts"><button class="icon-btn glass ${inCmp ? "on" : ""}" data-act="cmp">${ico("compare")}</button>
          <button class="icon-btn glass ${S.favs.has(p.id) ? "on" : ""}" data-fav="${p.id}">${ico("heart")}</button></div></div>
        <div class="gallery"><div class="track" id="gal">${images.map((s) => `<img src="${esc(img(s))}" alt="">`).join("")}</div>
          ${images.length > 1 ? `<div class="dots">${images.map((_, i) => `<i class="${i ? "" : "on"}"></i>`).join("")}</div>` : ""}</div>
        <div class="pd-head"><div class="brand">${esc(p.brand)}</div><h1>${esc(p.name)}</h1>
          <div class="pd-tags">
            ${out ? `<span class="tag glass out">${T("outOfStock")}</span>` : v.stock === "low" ? `<span class="tag glass low">${ico("bolt")}${v.left ? T("lowStock", { n: v.left }) : T("lowStockShort")}</span>` : `<span class="tag glass ok">${ico("check")}${T("inStock")}</span>`}
            ${p.warranty ? `<span class="tag glass">${ico("shield")}${T("warranty")}: ${esc(p.warranty)}</span>` : ""}
            ${p.badges.includes("hit") ? `<span class="tag glass">🔥 Hit</span>` : ""}</div></div>
        <div class="pd-price"><b>${money(v ? v.price : p.price)}</b>${v && v.old_price ? `<s>${money(v.old_price)}</s><span class="save">-${p.discount}%</span>` : ""}</div>
        ${p.options.map((o, oi) => `<div class="opt"><div class="opt-h">${esc(o.name)}: <b>${esc((o.values.find((x) => x.value === sel[oi]) || {}).label || "")}</b></div>
          <div class="opt-vals">${o.values.map((val) => {
            const test = sel.slice(); test[oi] = val.value;
            const exact = findVariant(test);
            const any = variants.some((x) => x.vals[oi] === val.value);
            if (!any) return "";
            const na = !exact || exact.stock === "out";
            const pic = o.is_color ? (p.images.find((i) => i.color === val.value) || {}).path : "";
            return `<button class="opt-v glass ${o.is_color && pic ? "color" : ""} ${sel[oi] === val.value ? "on" : ""} ${na ? "na" : ""}" data-oi="${oi}" data-val="${esc(val.value)}">
              ${pic ? `<img src="${esc(img(pic))}" alt="">` : ""}${esc(val.label)}</button>`;
          }).join("")}</div></div>`).join("")}
        ${p.specs.length ? `<div class="card-box glass"><h3>${ico("grid")}${T("specs")}</h3><table class="specs" id="specs">
          ${p.specs.map((s, i) => `<tr class="${i >= 6 ? "hidden more" : ""}"><td>${esc(s.k)}</td><td>${esc(s.v)}</td></tr>`).join("")}</table>
          ${p.specs.length > 6 ? `<button class="link-btn" data-act="allspecs" style="margin-top:10px">${T("showAll")} (${p.specs.length})</button>` : ""}</div>` : ""}
        ${p.description ? `<div class="card-box glass"><h3>${ico("box")}${T("description")}</h3><p class="desc">${esc(p.description)}</p></div>` : ""}
        <div class="buybar glass">
          ${out ? `<div class="total"><small>${T("outOfStock")}</small><b>${money(v ? v.price : p.price)}</b></div>
              <button class="btn btn-white" data-act="notify" ${alerts.includes(v && v.id) ? "disabled" : ""}>${ico("bell")}${T("notify")}</button>`
            : inCart ? `<div class="qty glass"><button data-cq="-1">${ico("minus")}</button><span id="qn">${inCart.qty}</span><button data-cq="1">${ico("plus")}</button></div>
              <button class="btn btn-primary two" data-act="gocart">${ico("cart")}<span><b>${T("goCart")}</b><small id="qt">${T("inCart")}: ${money(v.price * inCart.qty)}</small></span></button>`
            : `<div class="qty glass"><button data-q="-1">${ico("minus")}</button><span id="qn">${qty}</span><button data-q="1">${ico("plus")}</button></div>
              <button class="btn btn-primary two" data-act="buy">${ico("cart")}<span><b>${T("addToCart")}</b><small id="qt">${money(v.price * qty)}</small></span></button>`}</div>`;
      const gal = document.getElementById("gal");
      const dots = [...view.querySelectorAll(".gallery .dots i")];
      gal.addEventListener("scroll", () => { const i = Math.round(gal.scrollLeft / gal.clientWidth); dots.forEach((d, j) => d.classList.toggle("on", i === j)); }, { passive: true });
      view.querySelectorAll("[data-oi]").forEach((b) => b.addEventListener("click", () => {
        const oi = +b.dataset.oi, val = b.dataset.val;
        const test = sel.slice(); test[oi] = val;
        if (!findVariant(test)) {
          // shu qiymatli eng mos (sotuvdagi) variantga o'tamiz
          const alt = variants.filter((x) => x.vals[oi] === val).sort((a, c) => (a.stock === "out") - (c.stock === "out"))[0];
          sel = alt ? [...alt.vals] : test;
        } else sel = test;
        qty = 1; haptic("sel"); draw();
      }));
      view.querySelectorAll("[data-q]").forEach((b) => b.addEventListener("click", () => {
        const max = v.left || 20;
        qty = Math.max(1, Math.min(max, qty + +b.dataset.q));
        haptic("sel");
        document.getElementById("qn").textContent = qty;
        document.getElementById("qt").textContent = money(v.price * qty);
      }));
      const act = (name, fn) => { const el = view.querySelector(`[data-act="${name}"]`); el && el.addEventListener("click", fn); };
      act("buy", () => { if (addToCart(v.id, qty, v.left || 20)) draw(); });
      act("gocart", () => { haptic("sel"); go("#cart"); });
      view.querySelectorAll("[data-cq]").forEach((b) => b.addEventListener("click", () => {
        const it = S.cart.find((x) => x.variant_id === v.id);
        if (!it) return draw();
        const max = Math.min(v.left || 20, 20);
        const n = it.qty + +b.dataset.cq;
        if (n > max) { toast(T("maxQty"), true); return; }
        if (n <= 0) S.cart = S.cart.filter((x) => x !== it); else it.qty = n;
        haptic("sel"); saveCart(); draw();
      }));
      act("cmp", () => { toggleCompare(p.id) && draw(); });
      act("allspecs", (e) => { view.querySelectorAll("#specs .more").forEach((x) => x.classList.remove("hidden")); e.target.remove(); });
      act("notify", async () => {
        try { await api("/api/alerts", { method: "POST", body: { variant_id: v.id } }); alerts.push(v.id); toast("🔔 " + T("notifyOn")); draw(); }
        catch (e) { toast(e.message, true); }
      });
    };
    draw();
  }

  // ---------------- SAVAT ----------------
  async function renderCart() {
    if (!S.cart.length) {
      view.innerHTML = `<div class="topbar"><h1>${T("cart")}</h1></div>
        <div class="empty"><div class="big glass">${ico("cart")}</div><h3>${T("emptyCart")}</h3><p>${T("emptyCartSub")}</p>
        <button class="btn btn-white" data-go="#catalog">${T("toCatalog")}</button></div>`;
      return;
    }
    view.innerHTML = `<div class="topbar"><h1>${T("cart")}</h1></div>${'<div class="sk" style="height:98px;margin-bottom:10px"></div>'.repeat(Math.min(3, S.cart.length))}`;
    const { items } = await api("/api/cart", { method: "POST", body: { items: S.cart } });
    const info = Object.fromEntries(items.map((i) => [i.variant_id, i]));
    // ombordagi qoldiqqa moslash
    let changed = false;
    S.cart = S.cart.filter((c) => info[c.variant_id]);
    S.cart.forEach((c) => { const i = info[c.variant_id]; if (!i.gone && c.qty > i.stock) { c.qty = Math.max(1, i.stock); changed = true; } });
    saveCart();
    if (changed) toast(T("maxQty"));
    const draw = () => {
      const live = S.cart.filter((c) => !info[c.variant_id].gone);
      const subtotal = live.reduce((a, c) => a + info[c.variant_id].price * c.qty, 0);
      const minOrder = S.boot.settings.min_order;
      view.innerHTML = `<div class="topbar"><h1>${T("cart")}</h1><button class="link-btn" data-act="clear">${T("clear")}</button></div>
        ${S.cart.map((c) => { const i = info[c.variant_id]; return `<div class="ci glass ${i.gone ? "gone" : ""}">
          <img src="${esc(img(i.image))}" alt="" data-go="#p${i.product_id || ""}">
          <div class="info"><b>${esc(i.name || "—")}</b><small>${esc(i.label || "")}${i.gone ? " · " + T("outOfStock") : i.low ? " · " + T("lowStock", { n: i.stock }) : ""}</small>
            <div class="row"><div class="price-b">${i.old_price ? `<small>${money(i.old_price * c.qty)}</small>` : ""}${money((i.price || 0) * c.qty)}</div>
            ${i.gone ? `<button class="icon-btn glass" data-rm="${c.variant_id}">${ico("trash")}</button>`
              : `<div class="qty glass"><button data-cq="${c.variant_id}:-1">${ico(c.qty === 1 ? "trash" : "minus")}</button><span>${c.qty}</span><button data-cq="${c.variant_id}:1">${ico("plus")}</button></div>`}</div></div></div>`; }).join("")}
        <div class="summary glass"><div class="sum-row"><span>${T("items")}</span><b>${money(subtotal)}</b></div>
          <div class="sum-row total"><span>${T("total")}</span><b>${money(subtotal)}</b></div></div>
        ${minOrder && subtotal < minOrder ? `<div class="note glass">${ico("alert")}<span>${T("minOrder", { sum: money(minOrder), left: money(minOrder - subtotal) })}</span></div>` : ""}
        ${!S.boot.settings.accepting ? `<div class="note glass">${ico("alert")}<span>${T("notAccepting")}</span></div>` : ""}
        <button class="btn btn-primary btn-block" style="margin-top:16px" data-go="#checkout" ${!live.length || !S.boot.settings.accepting || (minOrder && subtotal < minOrder) ? "disabled" : ""}>${T("checkout")} · ${money(subtotal)}</button>`;
      view.querySelectorAll("[data-cq]").forEach((b) => b.addEventListener("click", () => {
        const [vid, d] = b.dataset.cq.split(":").map(Number);
        const c = S.cart.find((x) => x.variant_id === vid);
        const max = Math.min(20, info[vid].stock);
        if (d > 0 && c.qty >= max) { toast(T("maxQty"), true); return; }
        c.qty += d; if (c.qty <= 0) S.cart = S.cart.filter((x) => x !== c);
        haptic("sel"); saveCart(); S.cart.length ? draw() : renderCart();
      }));
      view.querySelectorAll("[data-rm]").forEach((b) => b.addEventListener("click", () => {
        S.cart = S.cart.filter((x) => x.variant_id !== +b.dataset.rm); saveCart(); S.cart.length ? draw() : renderCart();
      }));
      const clr = view.querySelector('[data-act="clear"]');
      clr && clr.addEventListener("click", () => confirmDo(T("clearConfirm"), () => { S.cart = []; saveCart(); renderCart(); }));
    };
    draw();
  }
  function confirmDo(text, cb) {
    if (tg && tg.showConfirm && initData) tg.showConfirm(text, (ok) => ok && cb());
    else if (confirm(text)) cb();
  }

  // ---------------- RASMIYLASHTIRISH ----------------
  const phoneDigits = (s) => (s || "").replace(/\D/g, "").replace(/^998/, "").slice(0, 9);
  const phoneFmt = (d) => [d.slice(0, 2), d.slice(2, 5), d.slice(5, 7), d.slice(7, 9)].filter(Boolean).join(" ");
  async function renderCheckout() {
    if (!S.cart.length) return go("#cart");
    const st = S.boot.settings, u = S.boot.user;
    const types = ["delivery", "pickup"].filter((x) => st[x + "_enabled"]);
    const d = S.draft;
    const co = {
      type: types.includes(d.type) ? d.type : types[0], name: d.name || u.full_name || u.first_name || "",
      phone: phoneDigits(d.phone || u.phone), region: d.region || u.region_id || null, address: d.address || u.address || "",
      comment: "", promo: "", pay: "cash", quote: null, promoErr: "", sending: false,
    };
    const save = () => { S.draft = { type: co.type, name: co.name, phone: co.phone, region: co.region, address: co.address }; store.set("draft", S.draft); };
    const region = () => S.boot.regions.find((x) => x.id === co.region);
    const quote = async () => {
      try {
        const r = await api("/api/quote", { method: "POST", body: { items: S.cart, order_type: co.type, region_id: co.region, promo_code: co.promo } });
        co.quote = r.quote; co.promoErr = "";
      } catch (e) { if (co.promo) { co.promoErr = e.message; co.promo = ""; return quote(); } toast(e.message, true); }
      drawSummary();
    };
    const drawSummary = () => {
      const q = co.quote, el = document.getElementById("sum");
      if (!q || !el) return;
      el.innerHTML = `<div class="sum-row"><span>${T("items")}</span><b>${money(q.subtotal)}</b></div>
        ${q.discount ? `<div class="sum-row"><span>${T("discount")} (${esc(q.promo_code)})</span><b>−${money(q.discount)}</b></div>` : ""}
        ${co.type === "delivery" ? `<div class="sum-row"><span>${T("deliveryFee")}${q.region ? ` · ${esc(q.region.eta)}` : ""}</span><b>${q.region ? (q.delivery_fee ? money(q.delivery_fee) : T("free")) : "—"}</b></div>` : ""}
        <div class="sum-row total"><span>${T("total")}</span><b>${money(q.total)}</b></div>`;
      document.getElementById("pay-total").textContent = money(q.total);
      const sub = document.getElementById("rg-sub");
      if (sub && q.region) sub.textContent = `${q.delivery_fee ? money(q.delivery_fee) : T("free")} · ${q.region.eta}`;
      const pm = document.getElementById("promo-msg");
      pm.innerHTML = co.promoErr ? `<p class="err-msg">${esc(co.promoErr)}</p>` : q.promo_code ? `<p class="ok-msg">✓ ${esc(q.promo_code)} — ${esc(q.promo_label)}</p>` : "";
    };
    const draw = () => {
      const rg = region();
      view.innerHTML = `
        <div class="topbar"><button class="icon-btn glass" data-act="back">${ico("back")}</button><h1>${T("checkoutTitle")}</h1></div>
        ${types.length > 1 ? `<div class="seg glass">${types.map((x) => `<button data-type="${x}" class="${co.type === x ? "on" : ""}">${ico(x === "delivery" ? "truck" : "store")}${T(x)}</button>`).join("")}</div>` : ""}
        ${co.type === "pickup" ? `<div class="note glass" style="margin:0 0 16px">${ico("pin")}<span>${T("pickupFrom")}${st.shop_address ? `<br><b style="color:var(--text)">${esc(st.shop_address)}</b>` : ""}${st.shop_map_url ? `<br><a href="${esc(st.shop_map_url)}" target="_blank">${T("openMap")} →</a>` : ""}</span></div>` : ""}
        <label class="field"><span>${T("name")}</span><input class="input" id="f-name" value="${esc(co.name)}" placeholder="${esc(T("namePh"))}" autocomplete="name"></label>
        <label class="field"><span>${T("phone")}</span><div class="input phone"><em>+998</em><input id="f-phone" inputmode="tel" value="${esc(phoneFmt(co.phone))}" placeholder="90 123 45 67" autocomplete="tel"></div></label>
        ${co.type === "delivery" ? `
          <div class="field"><span>${T("region")}</span><button class="input select" data-act="region"><span>${rg ? esc(rg.name) : `<span class="muted">${T("regionPh")}</span>`}</span>
            <span class="sub" id="rg-sub"></span></button></div>
          <label class="field"><span>${T("address")}</span><textarea class="input" id="f-addr" rows="2" placeholder="${esc(T("addressPh"))}">${esc(co.address)}</textarea>
            <button class="link-btn" data-act="geo" style="margin:8px 4px 0;display:inline-flex;gap:6px;align-items:center">${ico("pin")}${T("geo")}</button></label>` : ""}
        <label class="field"><span>${T("comment")}</span><textarea class="input" id="f-comment" rows="2" placeholder="${esc(T("commentPh"))}">${esc(co.comment)}</textarea></label>
        <div class="field"><span>${T("promo")}</span><div class="promo"><input class="input" id="f-promo" placeholder="${esc(T("promoPh"))}" value="${esc(co.quote && co.quote.promo_code || "")}">
          <button class="btn btn-white" data-act="promo">${co.quote && co.quote.promo_code ? T("remove") : T("apply")}</button></div><div id="promo-msg"></div></div>
        <div class="field"><span>${T("payment")}</span><div class="pay">
          <button class="pay-o glass ${co.pay === "cash" ? "on" : ""}" data-pay="cash">${ico("cash")}<span class="t"><b>${T("cash")}</b><small>${T("cashSub")}</small></span><span class="radio"></span></button>
          ${st.card_enabled ? `<button class="pay-o glass ${co.pay === "card" ? "on" : ""}" data-pay="card">${ico("card")}<span class="t"><b>${T("card")}</b><small>${T("cardSub")}</small></span><span class="radio"></span></button>`
            : `<button class="pay-o glass soon" data-pay="card">${ico("card")}<span class="t"><b>${T("card")}</b><small>${T("cardSoon")}</small></span><span class="pill-soon">${T("soon")}</span></button>`}</div></div>
        <div class="summary glass" id="sum"></div>
        ${st.is_open ? "" : `<div class="note glass">${ico("bell")}<span>${T("afterHours", { time: st.next_open || "" })}</span></div>`}
        <div class="buybar glass"><div class="total"><small>${T("total")}</small><b id="pay-total">—</b></div>
          <button class="btn btn-primary" data-act="place">${T("confirm")}</button></div>`;
      const bind = (id, key, fn) => { const el = document.getElementById(id); el && el.addEventListener("input", () => { co[key] = fn ? fn(el) : el.value; save(); }); };
      bind("f-name", "name"); bind("f-addr", "address"); bind("f-comment", "comment");
      const ph = document.getElementById("f-phone");
      ph.addEventListener("input", () => { co.phone = phoneDigits(ph.value); ph.value = phoneFmt(co.phone); save(); });
      view.querySelectorAll("[data-type]").forEach((b) => b.addEventListener("click", () => { co.type = b.dataset.type; save(); haptic("sel"); draw(); quote(); }));
      if (!st.card_enabled && co.pay === "card") co.pay = "cash";
      view.querySelectorAll("[data-pay]").forEach((b) => b.addEventListener("click", () => {
        if (b.dataset.pay === "card" && !st.card_enabled) return toast(T("cardSoon"));
        co.pay = b.dataset.pay; save(); haptic("sel");
        view.querySelectorAll("[data-pay]").forEach((x) => x.classList.toggle("on", x === b));
      }));
      const on = (name, fn) => { const el = view.querySelector(`[data-act="${name}"]`); el && el.addEventListener("click", fn); };
      on("region", () => openSheet(`<h3>${T("region")}</h3><div class="opt-list">${S.boot.regions.map((x) => `<button data-rg="${x.id}" class="${x.id === co.region ? "on" : ""}">
          <span>${esc(x.name)}<br><small>${T("eta")}: ${esc(x.eta)}</small></span><span>${x.fee ? money(x.fee) : T("free")}</span></button>`).join("")}</div>
          ${S.boot.regions[0] && S.boot.regions[0].free_from ? `<p class="muted" style="font-size:13px;margin-top:12px">${T("freeFrom", { sum: money(S.boot.regions[0].free_from) })}</p>` : ""}`, (el) => {
        el.querySelectorAll("[data-rg]").forEach((b) => b.addEventListener("click", () => { co.region = +b.dataset.rg; save(); closeSheet(); draw(); quote(); }));
      }));
      on("promo", () => {
        if (co.quote && co.quote.promo_code) { co.promo = ""; } else { co.promo = document.getElementById("f-promo").value.trim(); }
        quote().then(draw);
      });
      on("geo", () => {
        if (!navigator.geolocation) return toast(T("geoFail"), true);
        toast(T("geoLoading"));
        navigator.geolocation.getCurrentPosition((pos) => {
          const link = `https://maps.google.com/?q=${pos.coords.latitude.toFixed(6)},${pos.coords.longitude.toFixed(6)}`;
          co.address = (co.address ? co.address + "\n" : "") + "📍 " + link; save(); draw(); toast(T("geoAdded"));
        }, () => toast(T("geoFail"), true), { enableHighAccuracy: true, timeout: 10000 });
      });
      on("place", place);
      drawSummary();
    };
    const place = async () => {
      if (co.sending) return;
      const err = (id, msg) => { const el = document.getElementById(id); el && el.classList.add("err"); toast(msg, true); };
      if (co.name.trim().length < 2) return err("f-name", T("errName"));
      if (co.phone.length !== 9) return err("f-phone", T("errPhone"));
      if (co.type === "delivery" && !co.region) return toast(T("errRegion"), true);
      if (co.type === "delivery" && co.address.trim().length < 5) return err("f-addr", T("errAddress"));
      co.sending = true;
      const btn = view.querySelector('[data-act="place"]');
      btn.disabled = true; btn.textContent = T("sending");
      try {
        const r = await api("/api/orders", { method: "POST", body: { items: S.cart, order_type: co.type, name: co.name.trim(),
          phone: "+998" + co.phone, region_id: co.region, address: co.address.trim(), comment: co.comment.trim(),
          promo_code: co.quote && co.quote.promo_code || "", payment_method: co.pay } });
        S.cart = []; saveCart(); S.orders = null; S.pcache = {};
        haptic("ok");
        location.replace(co.pay === "card" ? "#o" + r.order.code : "#placed/" + r.order.code);
      } catch (e) {
        toast(e.message, true); co.sending = false; btn.disabled = false; btn.textContent = T("confirm");
      }
    };
    draw();
    quote();
  }
  function renderPlaced(r) {
    view.innerHTML = `<div class="placed"><div class="ok">${ico("check")}</div><h2>${T("placed")}</h2>
      <p class="muted">${T("orderId")}</p><code class="glass">${esc(r.code)}</code><p class="muted" style="max-width:320px;margin:10px auto 26px">${T("placedSub")}</p>
      <div class="actions"><button class="btn btn-primary" data-go="#o${esc(r.code)}">${ico("box")}${T("track")}</button>
      <button class="btn btn-ghost glass" data-go="#home">${T("continueShopping")}</button></div></div>`;
    refreshBoot();
  }

  // ---------------- SEVIMLILAR va SOLISHTIRISH ----------------
  function renderFav() {
    const items = S.boot.products.filter((p) => S.favs.has(p.id));
    view.innerHTML = `<div class="topbar"><h1>${T("tabFav")}</h1>${S.compare.length ? `<button class="chip glass on" data-go="#compare">⇄ ${T("compare")} · ${S.compare.length}</button>` : ""}</div>
      ${items.length ? `<div class="grid">${items.map(card).join("")}</div>`
        : `<div class="empty"><div class="big glass">${ico("heart")}</div><h3>${T("tabFav")}</h3><p>${T("favEmpty")}</p>
          <button class="btn btn-white" data-go="#catalog">${T("toCatalog")}</button></div>`}`;
  }
  async function renderCompare() {
    if (!S.compare.length) {
      view.innerHTML = `<div class="topbar"><button class="icon-btn glass" data-act="back">${ico("back")}</button><h1>${T("compare")}</h1></div>
        <div class="empty"><div class="big glass">${ico("compare")}</div><p>${T("compareEmpty")}</p></div>`;
      return;
    }
    view.innerHTML = `<div class="sk" style="height:300px"></div>`;
    const list = (await Promise.all(S.compare.map((id) => loadProduct(id).catch(() => null)))).filter(Boolean).map((x) => x.product);
    let onlyDiff = false;
    const keys = [...new Set(list.flatMap((p) => p.specs.map((s) => s.k)))];
    const draw = () => {
      const rows = [[T("price"), list.map((p) => money(p.price))], [T("warranty"), list.map((p) => p.warranty || "—")],
        ...keys.map((k) => [k, list.map((p) => (p.specs.find((s) => s.k === k) || {}).v || "—")])];
      view.innerHTML = `<div class="topbar"><button class="icon-btn glass" data-act="back">${ico("back")}</button><h1>${T("compare")}</h1>
          <button class="link-btn" data-act="cmpclear">${T("compareClear")}</button></div>
        <label class="check" style="margin-bottom:8px"><input type="checkbox" id="diff" ${onlyDiff ? "checked" : ""}>${T("onlyDiff")}</label>
        <div class="cmp-wrap"><table class="cmp"><tr><th></th>${list.map((p) => `<td class="p" data-go="#p${p.id}"><img src="${esc(img(p.image))}" alt=""><b>${esc(p.name)}</b>
          <button class="link-btn" data-rmc="${p.id}">✕</button></td>`).join("")}</tr>
          ${rows.map(([k, vals]) => { const diff = new Set(vals).size > 1; return onlyDiff && !diff ? "" : `<tr class="${diff ? "diff" : ""}"><td>${esc(k)}</td>${vals.map((x) => `<td>${esc(x)}</td>`).join("")}</tr>`; }).join("")}
        </table></div>`;
      document.getElementById("diff").addEventListener("change", (e) => { onlyDiff = e.target.checked; draw(); });
      view.querySelectorAll("[data-rmc]").forEach((b) => b.addEventListener("click", (e) => { e.stopPropagation(); toggleCompare(+b.dataset.rmc); renderCompare(); }));
      view.querySelector('[data-act="cmpclear"]').addEventListener("click", () => { S.compare = []; store.set("cmp", []); renderCompare(); });
    };
    draw();
  }

  // ---------------- BUYURTMALAR ----------------
  const ACTIVE = ["new", "accepted", "packing", "shipping"];
  const stClass = (s) => (ACTIVE.includes(s) ? "active" : s === "delivered" ? "done" : s);
  async function renderOrders() {
    view.innerHTML = `<div class="topbar"><h1>${T("myOrders")}</h1></div>${'<div class="sk" style="height:130px;margin-bottom:10px"></div>'.repeat(3)}`;
    S.orders = (await api("/api/orders")).orders;
    updateBadges();
    view.innerHTML = `<div class="topbar"><h1>${T("myOrders")}</h1></div>
      ${S.orders.length ? S.orders.map((o) => `<button class="oc glass" data-go="#o${esc(o.code)}">
        <div class="top"><span class="code">${esc(o.code)}</span><span class="st ${stClass(o.status)}">${esc(o.status_label)}</span></div>
        <div class="thumbs">${o.items.slice(0, 5).map((i) => `<img src="${esc(img(i.image))}" alt="">`).join("")}</div>
        <div class="bottom"><span>${o.created_at.slice(0, 16)}${o.unread ? ` · 💬 ${o.unread}` : ""}</span><b>${money(o.total)}</b></div></button>`).join("")
        : `<div class="empty"><div class="big glass">${ico("box")}</div><h3>${T("noOrders")}</h3><button class="btn btn-white" data-go="#catalog">${T("toCatalog")}</button></div>`}`;
  }

  function payBox(o) {
    if (o.payment_method !== "card" || !o.pay_status || ["cancelled", "returned"].includes(o.status)) return "";
    if (o.pay_status === "paid") return `<div class="pay-state paid glass">${ico("check")}<span><b>${T("payPaid")}</b><small>${T("card")} · ${money(o.total)}</small></span></div>`;
    if (o.pay_status === "review") return `<div class="pay-state review glass">${ico("clock")}<span><b>${T("payReview")}</b><small>${T("payReviewSub")}</small></span></div>`;
    const c = o.card;
    return `<div class="card-box glass paybox"><h3>${ico("card")}${T("payTitle")}</h3>
      ${o.pay_status === "rejected" ? `<div class="pay-state rejected">${ico("alert")}<span><b>${T("payRejected")}</b><small>${T("reason")}: ${esc(o.pay_note)}</small></span></div>` : ""}
      ${c ? `<div class="bank-card"><small>${esc(c.bank || T("card"))}</small><div class="num">${esc(c.number)}</div>
        <div class="row"><span>${esc(c.holder)}</span><button class="copy" data-act="copycard">${ico("copy")}${T("copy")}</button></div></div>` : ""}
      <div class="sum-row total" style="margin-top:12px"><span>${T("total")}</span><b>${money(o.total)}</b></div>
      <p class="muted" style="font-size:13px;margin:6px 0 12px">${T("payHint")}</p>
      <label class="upload glass"><input type="file" id="rc-file" accept="image/*" hidden>${ico("camera")}<span id="rc-name">${T("chooseReceipt")}</span></label>
      <button class="btn btn-primary btn-block" id="rc-send" data-act="rcsend" disabled style="margin-top:10px">${o.pay_status === "rejected" ? T("resend") : T("sendReceipt")}</button></div>`;
  }

  async function renderOrder(r) {
    view.innerHTML = `<div class="sk" style="height:220px"></div>`;
    let o = (await api(`/api/orders/${encodeURIComponent(r.code)}`)).order;
    let messages = [];
    const steps = ["new", "accepted", "packing", "shipping", "delivered"];
    const draw = () => {
      const reached = steps.indexOf(o.status);
      view.innerHTML = `
        <div class="topbar"><button class="icon-btn glass" data-act="back">${ico("back")}</button><h1>${esc(o.code)}</h1><span class="st ${stClass(o.status)}">${esc(o.status_label)}</span></div>
        <div class="card-box glass" style="margin-top:0">
          ${["cancelled", "returned"].includes(o.status) ? `<p style="margin:0"><b>${esc(o.status_label)}</b>${o.cancel_reason ? `<br><span class="muted">${T("reason")}: ${esc(o.cancel_reason)}</span>` : ""}</p>`
          : `<ul class="timeline">${steps.map((s, i) => `<li class="${i < reached || (i === reached && s === "delivered") ? "done" : i === reached ? "cur" : ""}">
              <span class="dot">${i < reached || s === "delivered" && i === reached ? ico("check") : ""}</span>${esc(s === "new" ? T("stepNew") : statusName(s, o.order_type))}
              ${o.timeline[s] ? `<small>${o.timeline[s].slice(5, 16).replace("-", ".")}</small>` : ""}</li>`).join("")}</ul>`}
          ${o.order_type === "delivery" && o.eta && ACTIVE.includes(o.status) ? `<div class="note glass" style="margin-top:14px">${ico("truck")}<span>${esc(o.region)} · ${T("eta")}: <b style="color:var(--text)">${esc(o.eta)}</b></span></div>` : ""}</div>
        ${payBox(o)}
        ${o.media.length ? `<div class="card-box glass"><h3>${ico("camera")}${T("statusPhotos")}</h3><div class="media-row">${o.media.map((m) => `<figure><a href="${esc(img(m.path))}" target="_blank"><img src="${esc(img(m.path))}" alt=""></a><figcaption>${esc(statusName(m.status, o.order_type))}${m.caption ? " · " + esc(m.caption) : ""}</figcaption></figure>`).join("")}</div></div>` : ""}
        <div class="card-box glass"><h3>${ico("box")}${T("items")}</h3>
          ${o.items.map((i) => `<div class="oi"><img src="${esc(img(i.image))}" alt=""><div class="t"><b>${esc(i.name)}</b><small>${i.variant ? esc(i.variant) + " · " : ""}×${i.qty}</small></div><b>${money(i.price * i.qty)}</b></div>`).join("")}
          <div style="margin-top:10px">${o.discount ? `<div class="sum-row"><span>${T("discount")} (${esc(o.promo_code)})</span><b>−${money(o.discount)}</b></div>` : ""}
          ${o.order_type === "delivery" ? `<div class="sum-row"><span>${T("deliveryFee")}</span><b>${o.delivery_fee ? money(o.delivery_fee) : T("free")}</b></div>` : ""}
          <div class="sum-row total"><span>${T("total")}</span><b>${money(o.total)}</b></div></div>
          <p class="muted" style="font-size:13px;margin:10px 0 0">${o.order_type === "delivery" ? `📍 ${esc(o.region)}, ${esc(o.address)}` : `🏬 ${T("pickupFrom")}${S.boot.settings.shop_address ? ": " + esc(S.boot.settings.shop_address) : ""}`}</p></div>
        ${o.status === "delivered" && o.items.some((i) => i.warranty_months) ? `<div class="warranty glass"><h3 style="margin:0 0 10px;font:600 16px var(--display);display:flex;gap:8px;align-items:center">${ico("shield")}${T("warrantyCard")}</h3>
          ${o.items.filter((i) => i.warranty_months).map((i) => `<div class="w"><span>${esc(i.name)}${i.serial ? `<br><code>${T("serial")}: ${esc(i.serial)}</code>` : ""}</span><b>${T("warrantyUntil", { date: addMonths(o.timeline.delivered || o.created_at, i.warranty_months) })}</b></div>`).join("")}</div>` : ""}
        ${o.tickets.length ? `<div class="card-box glass"><h3>${ico("alert")}${T("tickets")}</h3>${o.tickets.map((tk) => `<div class="sum-row"><span>${T("ticketKind_" + tk.kind)} · ${tk.created_at.slice(5, 16)}${tk.note ? `<br><small>${esc(tk.note)}</small>` : ""}</span><b>${T("ticketSt_" + tk.status)}</b></div>`).join("")}</div>` : ""}
        <div class="card-box glass" id="chatbox"><h3>${ico("chat")}${T("chatTitle")}</h3>
          ${o.chat_open ? `<div class="chat" id="chat"></div><div class="chat-in"><input class="input" id="chat-in" placeholder="${esc(T("chatPh"))}" maxlength="2000"><button class="icon-btn" data-act="send">${ico("send")}</button></div>`
            : `<div class="closed-chat">${ico("alert")}${T("chatClosed")}</div>`}</div>
        ${o.status === "delivered" && !o.review ? `<div class="card-box glass center"><h3 style="justify-content:center">${T("rateTitle")}</h3><div class="stars" id="stars">${[1, 2, 3, 4, 5].map((n) => `<button data-star="${n}">${ico("star")}</button>`).join("")}</div>
          <textarea class="input" id="rate-c" rows="2" placeholder="${esc(T("ratePh"))}"></textarea><button class="btn btn-white btn-block" style="margin-top:10px" data-act="rate">${T("rateSend")}</button></div>` : ""}
        ${o.review ? `<p class="center muted">${T("yourRating")}: ${"⭐".repeat(o.review.rating)}</p>` : ""}
        <div class="actions">
          ${o.can_return && !o.has_open_ticket ? `<button class="btn btn-white" data-act="return">${ico("return")}${T("returnOrder")}<small style="font-weight:500;opacity:.6">· ${T("returnUntil", { date: o.return_until })}</small></button>` : ""}
          <button class="btn btn-ghost glass" data-act="issue" ${o.has_open_ticket ? "disabled" : ""}>${ico("alert")}${T("issue")}</button>
          ${o.status === "new" ? `<button class="btn btn-ghost" data-act="cancel" style="color:#ff7b72">${T("cancelOrder")}</button>` : ""}
        </div>`;
      const on = (name, fn) => { const el = view.querySelector(`[data-act="${name}"]`); el && el.addEventListener("click", fn); };
      on("cancel", () => confirmDo(T("cancelConfirm"), async () => {
        try { o = (await api(`/api/orders/${o.code}/cancel`, { method: "POST" })).order; toast(T("cancelledToast")); S.pcache = {}; draw(); } catch (e) { toast(e.message, true); }
      }));
      on("issue", () => ticketSheet("issue"));
      on("return", () => ticketSheet("return"));
      on("copycard", async () => {
        const num = o.card.number.replace(/\s/g, "");
        try { await navigator.clipboard.writeText(num); } catch (e) {
          const ta = document.createElement("textarea"); ta.value = num; document.body.appendChild(ta); ta.select();
          try { document.execCommand("copy"); } catch (_) { /* eski brauzer */ } ta.remove();
        }
        haptic("ok"); toast("✓ " + T("copied"));
      });
      const rcIn = document.getElementById("rc-file");
      if (rcIn) rcIn.addEventListener("change", () => {
        const f = rcIn.files[0];
        const lab = document.getElementById("rc-name");
        lab.textContent = f ? f.name : T("chooseReceipt");
        document.getElementById("rc-send").disabled = !f;
      });
      on("rcsend", async (e) => {
        const f = rcIn && rcIn.files[0];
        if (!f) return;
        const btn = e.currentTarget; btn.disabled = true; btn.textContent = T("sending");
        try {
          const fd = new FormData(); fd.append("photo", f, f.name || "receipt.jpg");
          o = (await api(`/api/orders/${o.code}/receipt`, { method: "POST", body: fd })).order;
          haptic("ok"); toast("🧾 " + T("receiptSent")); draw();
        } catch (err) { toast(err.message, true); btn.disabled = false; btn.textContent = T("sendReceipt"); }
      });
      let stars = 0;
      view.querySelectorAll("[data-star]").forEach((b) => b.addEventListener("click", () => {
        stars = +b.dataset.star; haptic("sel");
        view.querySelectorAll("[data-star]").forEach((x) => x.classList.toggle("on", +x.dataset.star <= stars));
      }));
      on("rate", async () => {
        if (!stars) return;
        try { o = (await api(`/api/orders/${o.code}/review`, { method: "POST", body: { rating: stars, comment: document.getElementById("rate-c").value } })).order; toast(T("rateThanks")); draw(); }
        catch (e) { toast(e.message, true); }
      });
      if (o.chat_open) {
        drawChat();
        const input = document.getElementById("chat-in");
        const send = async () => {
          const text = input.value.trim();
          if (!text) return;
          input.value = "";
          try { messages = (await api(`/api/orders/${o.code}/chat`, { method: "POST", body: { text } })).messages; drawChat(); }
          catch (e) { toast(e.message, true); input.value = text; }
        };
        on("send", send);
        input.addEventListener("keydown", (e) => e.key === "Enter" && send());
      }
    };
    const drawChat = () => {
      const el = document.getElementById("chat");
      if (!el) return;
      el.innerHTML = messages.length ? messages.map((m) => `<div class="msg ${m.from === "customer" ? "me" : "them"}">${m.image ? `<img src="${esc(img(m.image))}" alt="">` : ""}${esc(m.text)}<small>${m.at.slice(11, 16)}</small></div>`).join("")
        : `<p class="muted" style="font-size:13px;margin:0">${T("chatEmpty")}</p>`;
      el.scrollTop = el.scrollHeight;
    };
    const ticketSheet = (kind) => {
      const files = [];
      openSheet(`<h3>${kind === "return" ? T("returnOrder") : T("issue")}</h3>
        <p class="muted" style="margin-top:-6px;font-size:13.5px">${kind === "return" ? T("returnHint") + " " + T("returnUntil", { date: o.return_until }) : T("issueHint")}</p>
        <textarea class="input" id="tk-reason" rows="4" placeholder="${esc(T("reasonPh"))}"></textarea>
        <div class="field" style="margin-top:14px"><span>${T("addPhotos")} (≤5)</span><div class="pics" id="tk-pics"></div></div>
        <button class="btn btn-primary btn-block" data-tk="send">${ico("send")}${T("send")}</button>`, (el) => {
        const pics = el.querySelector("#tk-pics");
        const drawPics = () => {
          pics.innerHTML = files.map((f, i) => `<div class="pic"><img src="${URL.createObjectURL(f)}" alt=""><button data-rmp="${i}">${ico("close")}</button></div>`).join("")
            + (files.length < 5 ? `<label>${ico("camera")}<input type="file" accept="image/*" multiple hidden></label>` : "");
          const inp = pics.querySelector("input");
          inp && inp.addEventListener("change", () => { files.push(...[...inp.files].slice(0, 5 - files.length)); drawPics(); });
          pics.querySelectorAll("[data-rmp]").forEach((b) => b.addEventListener("click", () => { files.splice(+b.dataset.rmp, 1); drawPics(); }));
        };
        drawPics();
        el.querySelector('[data-tk="send"]').addEventListener("click", async (e) => {
          const reason = el.querySelector("#tk-reason").value.trim();
          if (reason.length < 10) return toast(T("reasonShort"), true);
          if (kind === "return" && !files.length) return toast(T("photoRequired"), true);
          const fd = new FormData();
          fd.append("kind", kind); fd.append("reason", reason);
          files.forEach((f) => fd.append("photo", f, f.name || "photo.jpg"));
          e.currentTarget.disabled = true;
          try { o = (await api(`/api/orders/${o.code}/tickets`, { method: "POST", body: fd })).order; closeSheet(); toast(T("ticketSent")); draw(); }
          catch (err) { toast(err.message, true); e.currentTarget.disabled = false; }
        });
      });
    };
    if (o.chat_open) messages = (await api(`/api/orders/${o.code}/chat`)).messages;
    draw();
    // faol buyurtma: holat va chat avtomatik yangilanadi
    if (ACTIVE.includes(o.status)) {
      S.timers.push(setInterval(async () => {
        if (document.hidden || !sheetEl.classList.contains("hidden")) return;
        try {
          const fresh = (await api(`/api/orders/${o.code}`)).order;
          const msgs = fresh.chat_open ? (await api(`/api/orders/${o.code}/chat`)).messages : [];
          const typing = document.activeElement && document.activeElement.id === "chat-in";
          if (fresh.status !== o.status || fresh.media.length !== o.media.length) { o = fresh; messages = msgs; if (!typing) draw(); }
          else if (msgs.length !== messages.length) { messages = msgs; drawChat(); }
        } catch (e) { /* tarmoq vaqtincha yo'q */ }
      }, 10000));
    }
  }
  function statusName(s, type) {
    const map = S.lang === "ru"
      ? { new: "Заказ оформлен", accepted: "Принят", packing: "Собирается", shipping: type === "pickup" ? "Готов — можно забирать" : "В пути", delivered: type === "pickup" ? "Выдан" : "Доставлен" }
      : { new: "Buyurtma berildi", accepted: "Qabul qilindi", packing: "Yig'ilmoqda", shipping: type === "pickup" ? "Tayyor — olib ketishingiz mumkin" : "Yo'lda", delivered: type === "pickup" ? "Topshirildi" : "Yetkazildi" };
    return map[s] || s;
  }
  function addMonths(dateStr, months) {
    const d = new Date(dateStr.slice(0, 10) + "T00:00:00");
    const day = d.getDate();
    d.setMonth(d.getMonth() + months);
    if (d.getDate() < day) d.setDate(0);
    return d.toLocaleDateString("ru-RU");
  }

  // ---------------- umumiy hodisalar ----------------
  document.addEventListener("click", (e) => {
    const fav = e.target.closest("[data-fav]");
    if (fav) { e.stopPropagation(); e.preventDefault(); toggleFav(+fav.dataset.fav); return; }
    const quick = e.target.closest("[data-quick]");
    if (quick) {
      e.stopPropagation();
      const p = S.byId[+quick.dataset.quick];
      // bitta variantli mahsulot darhol savatga, aks holda variant tanlash uchun sahifasi ochiladi
      loadProduct(p.id).then(({ product }) => {
        const sellable = product.variants.filter((v) => v.stock !== "out");
        if (sellable.length === 1 && product.variants.length === 1) addToCart(sellable[0].id, 1, sellable[0].left || 20);
        else { toast(T("chooseOption")); go("#p" + p.id); }
      }).catch((err) => toast(err.message, true));
      return;
    }
    const lang = e.target.closest("[data-lang]");
    if (lang && lang.dataset.lang !== S.lang) { setLang(lang.dataset.lang); return; }
    const act = e.target.closest("[data-act]");
    if (act && act.dataset.act === "back") { back(); return; }
    if (act && act.dataset.act === "filters") { filterSheet(); return; }
    if (act && act.dataset.act === "reload") { location.reload(); return; }
    const g = e.target.closest("[data-go]");
    if (g && !e.target.closest("button:not([data-go])")) { haptic("light"); go(g.dataset.go); }
  });
  window.addEventListener("hashchange", render);

  async function setLang(lang) {
    try { await api("/api/me/lang", { method: "POST", body: { lang } }); } catch (e) { /* oflayn */ }
    S.pcache = {};
    await boot();
    render();
  }

  function applyBrand(b) {
    const hex = /^#[0-9a-f]{6}$/i.test(b.color) ? b.color : "#e0382b";
    const rgb = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(", ");
    document.documentElement.style.setProperty("--brand", hex);
    document.documentElement.style.setProperty("--brand-rgb", rgb);
    document.title = b.name;
  }

  async function boot() {
    const data = await api("/api/bootstrap");
    S.boot = data; S.texts = data.texts; S.lang = data.lang;
    S.byId = Object.fromEntries(data.products.map((p) => [p.id, p]));
    S.favs = new Set(data.favorites);
    applyBrand(data.brand);
    document.documentElement.lang = data.lang;
    document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = T(el.dataset.i18n); });
    updateBadges();
  }
  async function refreshBoot() { try { await boot(); } catch (e) { /* keyingi safar */ } }

  async function start() {
    if (tg) {
      tg.ready(); tg.expand();
      try { tg.setHeaderColor("#0a0a0b"); tg.setBackgroundColor("#0a0a0b"); tg.setBottomBarColor && tg.setBottomBarColor("#0a0a0b"); } catch (e) { /* eski klient */ }
      try { tg.disableVerticalSwipes && tg.disableVerticalSwipes(); } catch (e) { /* eski klient */ }
      tg.BackButton && tg.BackButton.onClick(back);
    }
    if (!initData && !devUser) {
      view.innerHTML = `<div class="empty"><div class="big glass">${ico("alert")}</div><h3>Telegram</h3><p>Iltimos, ilovani Telegram bot orqali oching.<br>Пожалуйста, откройте приложение через Telegram-бота.</p></div>`;
      return;
    }
    view.innerHTML = `<div class="sk" style="height:46px;width:50%;margin-bottom:16px"></div><div class="sk" style="height:50px;border-radius:999px"></div><div class="sk" style="height:200px;margin-top:14px"></div>`;
    try { await boot(); } catch (e) {
      view.innerHTML = `<div class="empty"><div class="big glass">${ico("alert")}</div><h3>${esc(e.message)}</h3><button class="btn btn-white" data-act="reload">Qayta urinish</button></div>`;
      return;
    }
    render();
    api("/api/orders").then((r) => { S.orders = r.orders; updateBadges(); }).catch(() => {});
  }
  start();
})();
