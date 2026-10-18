"""Mini Appsiz — bot ichida inline tugmalar orqali xarid (o'zbek/rus): katalog, savat, buyurtma, chat.

Barcha ekranlar Telegram rich message ko'rinishida: galereya (slaydshou), jadvallar, yig'iladigan bloklar.
"""
import logging
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from .. import chat, db, inventory, payments, products, regions, rich, tickets
from ..catalog import (
    badge_labels, category_name, discount_active, option_value, product_desc, product_name, specs_public,
    variant_label, variant_price, warranty_text,
)
from ..filters import Btn
from ..i18n import both, money_l, stars, status_text, t, ticket_status
from ..keyboards import ikb, main_kb, webapp_ready, webapp_url
from ..notify import (
    add_chat_and_relay, notify_new_order, notify_receipt, notify_restocked, notify_review, notify_ticket_new,
    refresh_staff_messages, save_telegram_photo,
)
from ..orders import OrderError, cancel_order, normalize_phone, place_order, public_settings, quote
from ..rich import Rich
from ..roles import get_role, lang_of
from ..utils import h, phone_fmt

router = Router(name="shop")
log = logging.getLogger(__name__)
PAGE = 8


class Checkout(StatesGroup):
    name = State()
    phone = State()
    region = State()
    address = State()
    comment = State()
    promo = State()
    payment = State()
    confirm = State()


class Search(StatesGroup):
    query = State()


class OrderChat(StatesGroup):
    message = State()


class ReviewComment(StatesGroup):
    text = State()


class TicketForm(StatesGroup):
    reason = State()
    photos = State()


class ReceiptForm(StatesGroup):
    photo = State()


# ====================== ko'rsatish yordamchilari ======================

async def show(event: Message | CallbackQuery, view: Rich, kb: InlineKeyboardMarkup | None) -> None:
    """Callbackda mavjud xabarni tahrirlaydi, aks holda yangi rich xabar yuboradi."""
    if isinstance(event, Message):
        await rich.answer(event, view, kb)
    else:
        await rich.edit(event.message, view, kb)


def _kb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return ikb([r for r in rows if r])


def _title(text: str) -> str:
    """i18n sarlavhasidan <b> ni olib tashlaydi (h2 o'zi qalin)."""
    return text.replace("<b>", "").replace("</b>", "")


def _price_html(price: int, old: int | None, lang: str) -> str:
    if old:
        return f"<s>{money_l(old, lang)}</s> <b>{money_l(price, lang)}</b>"
    return f"<b>{money_l(price, lang)}</b>"


def _with_header(view: Rich, header: str) -> Rich:
    if header:
        view.quote(header)
    return view


async def _cart_button(user_id: int, lang: str) -> tuple[str, str] | None:
    items = await db.cart_get(user_id)
    if not items:
        return None
    count = sum(i["qty"] for i in items)
    total = sum(i["qty"] * i["price"] for i in items)
    return t("cart_btn", lang, count=count, sum=money_l(total, lang)), "sh:cart"


def _min_price(p: dict) -> tuple[int, bool]:
    """(eng arzon sotuvdagi narx, narxlar har xilmi)."""
    variants = [v for v in p["variants"] if v["is_active"]]
    selling = [v for v in variants if v["stock"] > 0] or variants
    prices = [variant_price(p, v)[0] for v in selling]
    return (min(prices) if prices else 0), len(set(prices)) > 1


def _in_stock(p: dict) -> bool:
    return any(v["stock"] > 0 and v["is_active"] for v in p["variants"])


def _product_button(p: dict, lang: str) -> tuple[str, str]:
    price, many = _min_price(p)
    label = f"{product_name(p, lang)} · {t('from', lang) if many else ''}{money_l(price, lang)}"
    if discount_active(p):
        label = "🔥 " + label
    if not _in_stock(p):
        label = "⛔️ " + label
    return label, f"sh:p:{p['id']}:0:1"


def _products_table(view: Rich, items: list[dict], lang: str) -> Rich:
    rows = []
    for p in items:
        price, many = _min_price(p)
        mark = "🔥 " if discount_active(p) else ""
        state = "✅" if _in_stock(p) else "⛔️"
        brand = (p.get("brand") or {}).get("name") or ""
        rows.append([f"{mark}<b>{h(product_name(p, lang))}</b>" + (f"<br><i>{h(brand)}</i>" if brand else ""),
                     f"{t('from', lang) if many else ''}{money_l(price, lang)}", state])
    return view.table(rows, align=["left", "right", "center"])


# ====================== katalog ======================

async def categories_view(user_id: int, header: str = "") -> tuple[Rich, InlineKeyboardMarkup]:
    lang = await lang_of(user_id)
    settings = public_settings(await db.get_settings())
    cats = await products.get_categories(only_active=True)
    items = await products.get_products(only_active=True)
    counts: dict[int, int] = {}
    for p in items:
        counts[p["category_id"]] = counts.get(p["category_id"], 0) + 1
    shown = [c for c in cats if counts.get(c["id"])]
    view = _with_header(Rich(), header).h(_title(t("catalog_title", lang).split("\n")[0]))
    view.p(t("catalog_title", lang).split("\n\n", 1)[-1])
    if not settings["accepting"]:
        view.quote(t("closed_now", lang))
    buttons = [(f"{c['emoji']} {category_name(c, lang)} · {counts[c['id']]}", f"sh:cat:{c['id']}:0:0") for c in shown]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    cart_btn = await _cart_button(user_id, lang)
    rows.append([cart_btn] if cart_btn else [])
    rows.append([(t("orders_btn", lang), "sh:orders")])
    kb = _kb(rows)
    if webapp_ready():
        kb.inline_keyboard.append([InlineKeyboardButton(text=t("mini_inline", lang),
                                                        web_app=WebAppInfo(url=webapp_url()))])
    return view, kb


async def category_view(user_id: int, cat_id: int, brand_id: int = 0, page: int = 0,
                        header: str = "") -> tuple[Rich, InlineKeyboardMarkup]:
    lang = await lang_of(user_id)
    cat = await products.get_category(cat_id)
    items = await products.get_products(cat_id, only_active=True) if cat and cat["is_active"] else []
    if not items:
        return await categories_view(user_id, t("cat_empty", lang))
    items.sort(key=lambda p: not _in_stock(p))  # sotuvdagilar oldinda
    brands = {}
    for p in items:
        if p["brand"]:
            brands[p["brand"]["id"]] = p["brand"]["name"]
    shown = [p for p in items if not brand_id or p.get("brand_id") == brand_id]
    pages = max(1, -(-len(shown) // PAGE))
    page = max(0, min(page, pages - 1))
    chunk = shown[page * PAGE:(page + 1) * PAGE]

    title = f"{cat['emoji']} {h(category_name(cat, lang))}"
    if brand_id and brand_id in brands:
        title += f" · {h(brands[brand_id])}"
    view = _with_header(Rich(), header).h(title)
    _products_table(view, chunk, lang).p(t("choose_product", lang))

    rows = []
    if len(brands) > 1:
        chips = [((("• " if not brand_id else "") + t("all_brands", lang)), f"sh:cat:{cat_id}:0:0")]
        chips += [(("• " if bid == brand_id else "") + name, f"sh:cat:{cat_id}:{bid}:0") for bid, name in brands.items()]
        rows += [chips[i:i + 4] for i in range(0, len(chips), 4)]
    rows += [[_product_button(p, lang)] for p in chunk]
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(("◀️", f"sh:cat:{cat_id}:{brand_id}:{page - 1}"))
        nav.append((f"{page + 1}/{pages}", "sh:noop"))
        if page < pages - 1:
            nav.append(("▶️", f"sh:cat:{cat_id}:{brand_id}:{page + 1}"))
        rows.append(nav)
    cart_btn = await _cart_button(user_id, lang)
    rows.append([(t("back_cats", lang), "sh:cats")] + ([cart_btn] if cart_btn else []))
    return view, _kb(rows)


def _default_variant(p: dict) -> dict | None:
    active = [v for v in p["variants"] if v["is_active"]]
    return next((v for v in active if v["stock"] > 0), active[0] if active else None)


def _pick_variant(p: dict, current: dict, opt_index: int, value: str) -> dict:
    """Bitta opsiya o'zgarganda eng mos variant: aniq moslik, bo'lmasa shu qiymatli sotuvdagi variant."""
    active = [v for v in p["variants"] if v["is_active"]]
    target = list(current["vals"])
    if opt_index < len(target):
        target[opt_index] = value
    exact = next((v for v in active if v["vals"] == target), None)
    if exact:
        return exact
    same = [v for v in active if len(v["vals"]) > opt_index and v["vals"][opt_index] == value]
    same.sort(key=lambda v: (v["stock"] <= 0, -sum(a == b for a, b in zip(v["vals"], target))))
    return same[0] if same else current


def _variant_images(p: dict, v: dict) -> list[str]:
    """Galereya: tanlangan rang rasmlari oldinda, keyin umumiy rasmlar."""
    vals = v["vals"] or []
    own = [i["path"] for i in p["images"] if i["color"] and i["color"] in vals]
    common = [i["path"] for i in p["images"] if not i["color"]]
    return (own + common) or [i["path"] for i in p["images"][:1]]


async def product_view(user_id: int, pid: int, vid: int, q: int, header: str = ""):
    lang = await lang_of(user_id)
    p = await products.get_product(pid)
    if not p or not p["is_active"] or not await products.category_visible(p["category_id"]):
        return None
    v = next((x for x in p["variants"] if x["id"] == vid and x["is_active"]), None) or _default_variant(p)
    if not v:
        return None
    low = int(await db.get_setting("low_stock") or 3)
    q = max(1, min(q, max(1, v["stock"]), 20))
    price, old = variant_price(p, v)
    label = variant_label(p, v, lang)

    view = _with_header(Rich(), header)
    view.gallery(_variant_images(p, v), h(label))
    view.h(h(product_name(p, lang)), 2)
    brand = (p.get("brand") or {}).get("name")
    head = ([f"<i>{h(brand)}</i>"] if brand else []) + badge_labels(p, lang)
    if head:
        view.p(" · ".join(head))
    view.h(_price_html(price, old, lang), 3)
    if v["stock"] <= 0:
        stock_line = t("out_of_stock", lang)
    elif v["stock"] <= low:
        stock_line = t("low_stock", lang, n=v["stock"])
    else:
        stock_line = t("in_stock", lang)
    facts = [stock_line]
    if label:
        facts.insert(0, f"🎨 {h(label)}")
    if p["warranty_months"]:
        facts.append(t("warranty", lang, w=warranty_text(p["warranty_months"], lang)))
    view.lines(facts)
    specs = specs_public(p, lang)
    if specs:
        view.table([[h(s["k"]), f"<b>{h(s['v'])}</b>"] for s in specs[:4]])
        if len(specs) > 4:
            view.details(t("specs_btn", lang), Rich().table([[h(s["k"]), h(s["v"])] for s in specs]))
    desc = product_desc(p, lang)
    if desc:
        view.details("📝 " + ("Описание" if lang == "ru" else "Tavsif"), Rich().p(h(desc)))

    rows = []
    active = [x for x in p["variants"] if x["is_active"]]
    for oi, o in enumerate(p["options"]):
        buttons = []
        for val in o.get("values") or []:
            exists = [x for x in active if len(x["vals"]) > oi and x["vals"][oi] == val]
            if not exists:
                continue
            mark = "✅ " if v["vals"][oi:oi + 1] == [val] else ("" if any(x["stock"] > 0 for x in exists) else "⛔️ ")
            vi = o["values"].index(val)
            buttons.append((mark + option_value(o, val, lang), f"sh:po:{pid}:{v['id']}:{oi}:{vi}"))
        if len(buttons) > 1:
            rows += [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    if v["stock"] > 0:
        rows.append([("➖", f"sh:p:{pid}:{v['id']}:{q - 1}"), (t("pcs", lang, n=q), "sh:noop"),
                     ("➕", f"sh:p:{pid}:{v['id']}:{q + 1}")])
        rows.append([(t("add_btn", lang, sum=money_l(price * q, lang)), f"sh:add:{v['id']}:{q}")])
    else:
        rows.append([(t("alert_btn", lang), f"sh:al:{pid}:{v['id']}")])
    fav = p["id"] in await db.get_favorites(user_id)
    rows.append([(t("fav_del_btn" if fav else "fav_add_btn", lang), f"sh:fv:{pid}:{v['id']}")])
    cart_btn = await _cart_button(user_id, lang)
    rows.append([(t("back", lang), f"sh:cat:{p['category_id']}:0:0")] + ([cart_btn] if cart_btn else []))
    kb = _kb(rows)
    if webapp_ready():
        kb.inline_keyboard.append([InlineKeyboardButton(text=t("mini_inline", lang),
                                                        web_app=WebAppInfo(url=webapp_url(f"p{pid}")))])
    return view, kb


@router.message(StateFilter(None), Btn("b_catalog"))
@router.message(Command("catalog", "menu"))
async def catalog_cmd(message: Message, state: FSMContext) -> None:
    await state.clear()
    await show(message, *await categories_view(message.from_user.id))


@router.callback_query(F.data == "sh:noop")
async def noop(call: CallbackQuery) -> None:
    await call.answer()


@router.callback_query(F.data == "sh:cats")
async def cats_cb(call: CallbackQuery) -> None:
    await show(call, *await categories_view(call.from_user.id))
    await call.answer()


@router.callback_query(F.data.startswith("sh:cat:"))
async def cat_cb(call: CallbackQuery) -> None:
    parts = call.data.split(":")
    cid, bid, page = int(parts[2]), int(parts[3]) if len(parts) > 3 else 0, int(parts[4]) if len(parts) > 4 else 0
    await show(call, *await category_view(call.from_user.id, cid, bid, page))
    await call.answer()


async def _show_product(call: CallbackQuery, pid: int, vid: int, q: int, toast: str | None = None) -> None:
    lang = await lang_of(call.from_user.id)
    view = await product_view(call.from_user.id, pid, vid, q)
    if not view:
        await call.answer(t("unavailable", lang), show_alert=True)
        await show(call, *await categories_view(call.from_user.id))
        return
    await show(call, *view)
    await call.answer(toast)


@router.callback_query(F.data.startswith("sh:p:"))
async def product_cb(call: CallbackQuery) -> None:
    _, _, pid, vid, q = call.data.split(":")
    if int(q) < 1:
        await call.answer()
        return
    v = await products.get_variant(int(vid)) if int(vid) else None
    if v and int(q) > max(1, v["stock"]):
        await call.answer(t("qty_limit", await lang_of(call.from_user.id)))
        return
    await _show_product(call, int(pid), int(vid), int(q))


@router.callback_query(F.data.startswith("sh:po:"))
async def option_cb(call: CallbackQuery) -> None:
    _, _, pid, vid, oi, vi = call.data.split(":")
    p = await products.get_product(int(pid))
    current = next((v for v in (p or {}).get("variants", []) if v["id"] == int(vid)), None)
    if not p or not current or int(oi) >= len(p["options"]):
        await call.answer()
        return
    values = p["options"][int(oi)]["values"]
    if int(vi) >= len(values):
        await call.answer()
        return
    v = _pick_variant(p, current, int(oi), values[int(vi)])
    await _show_product(call, p["id"], v["id"], 1)


@router.callback_query(F.data.startswith("sh:fv:"))
async def favorite_cb(call: CallbackQuery) -> None:
    lang = await lang_of(call.from_user.id)
    _, _, pid, vid = call.data.split(":")
    added = await db.toggle_favorite(call.from_user.id, int(pid))
    await _show_product(call, int(pid), int(vid), 1, t("fav_added" if added else "fav_removed", lang))


@router.callback_query(F.data.startswith("sh:al:"))
async def alert_cb(call: CallbackQuery) -> None:
    _, _, pid, vid = call.data.split(":")
    await inventory.subscribe_alert(call.from_user.id, int(vid))
    await call.answer(t("alert_on", await lang_of(call.from_user.id)), show_alert=True)


@router.callback_query(F.data.startswith("sh:add:"))
async def add_cb(call: CallbackQuery) -> None:
    lang = await lang_of(call.from_user.id)
    _, _, vid, q = call.data.split(":")
    v = await products.get_variant(int(vid))
    p = await products.get_product(v["product_id"]) if v else None
    if not v or not p or not products.sellable(p, v):
        await call.answer(t("unavailable", lang), show_alert=True)
        return
    in_cart = next((i["qty"] for i in await db.cart_get(call.from_user.id) if i["variant_id"] == v["id"]), 0)
    qty = min(int(q), v["stock"] - in_cart)
    if qty <= 0:
        await call.answer(t("qty_limit", lang), show_alert=True)
        return
    await db.cart_add(call.from_user.id, v["id"], qty)
    label = variant_label(p, v, lang)
    item = f"{product_name(p, lang)}{f' ({label})' if label else ''} × {qty}"
    await call.answer(t("added_toast", lang))
    await show(call, *await category_view(call.from_user.id, p["category_id"], header=t("added", lang, item=h(item))))


# ====================== qidiruv va sevimlilar ======================

@router.message(StateFilter(None), Btn("b_search"))
@router.message(Command("search"))
async def search_start(message: Message, state: FSMContext) -> None:
    await state.set_state(Search.query)
    await message.answer(t("search_ask", await lang_of(message.from_user.id)))


@router.message(Search.query, F.text)
async def search_run(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user.id)
    query = message.text.strip().lower()
    await state.clear()
    if query in {x.lower() for k in ("b_catalog", "b_cart", "b_orders", "b_back") for x in both(k)}:
        return
    words = query.split()
    found = []
    for p in await products.get_products(only_active=True):
        hay = " ".join([p["name"], p.get("name_ru") or "", (p.get("brand") or {}).get("name") or ""]).lower()
        if all(w in hay for w in words):
            found.append(p)
    q = h(message.text.strip()[:40])
    if not found:
        await rich.answer(message, Rich().p(t("search_empty", lang, q=q)),
                          _kb([[(t("catalog_btn", lang), "sh:cats")]]))
        return
    view = Rich().h(f"🔍 {q}").p(t("search_results", lang, q=q))
    _products_table(view, found[:12], lang)
    rows = [[_product_button(p, lang)] for p in found[:12]]
    rows.append([(t("catalog_btn", lang), "sh:cats")])
    await rich.answer(message, view, _kb(rows))


async def favorites_view(user_id: int) -> tuple[Rich, InlineKeyboardMarkup]:
    lang = await lang_of(user_id)
    ids = await db.get_favorites(user_id)
    items = [p for pid in ids if (p := await products.get_product(pid)) and p["is_active"]]
    if not items:
        return Rich().p(t("favorites_empty", lang)), _kb([[(t("catalog_btn", lang), "sh:cats")]])
    view = _products_table(Rich().h(_title(t("favorites_title", lang))), items[:20], lang)
    rows = [[_product_button(p, lang)] for p in items[:20]]
    rows.append([(t("catalog_btn", lang), "sh:cats")])
    return view, _kb(rows)


@router.message(StateFilter(None), Btn("b_favorites"))
async def favorites_cmd(message: Message) -> None:
    await show(message, *await favorites_view(message.from_user.id))


# ====================== savat ======================

def _items_table(view: Rich, lines: list[tuple[str, int, int, int | None]], lang: str,
                 totals: list[tuple[str, str]] = ()) -> Rich:
    """lines: (nom HTML, soni, summa, eski summa). totals: (yorliq, qiymat HTML)."""
    rows = []
    for name, qty, amount, old in lines:
        price = f"<s>{money_l(old, lang)}</s><br>" if old else ""
        rows.append([name, f"×{qty}", f"{price}{money_l(amount, lang)}"])
    for label, value in totals:
        rows.append([(label, 2), value])
    return view.table(rows, align=["left", "center", "right"])


async def cart_view(user_id: int, header: str = "") -> tuple[Rich, InlineKeyboardMarkup]:
    lang = await lang_of(user_id)
    items = await db.cart_get(user_id)
    if not items:
        return _with_header(Rich(), header).p(t("cart_empty", lang)), _kb([[(t("to_catalog", lang), "sh:cats")]])
    settings = public_settings(await db.get_settings())
    subtotal = sum(i["qty"] * i["price"] for i in items)
    view = _with_header(Rich(), header).h(_title(t("cart_title", lang)))
    lines = []
    for i in items:
        vn = variant_label(i["product"], i["variant"], lang)
        name = f"<b>{h(product_name(i['product'], lang))}</b>" + (f"<br>{h(vn)}" if vn else "")
        lines.append((name, i["qty"], i["qty"] * i["price"], i["qty"] * i["old_price"] if i["old_price"] else None))
    _items_table(view, lines, lang, [(f"<b>{t('items_sum', lang)}</b>", f"<b>{money_l(subtotal, lang)}</b>")])
    notes = []
    if settings["min_order"] and subtotal < settings["min_order"]:
        notes.append(t("min_order_warn", lang, min=money_l(settings["min_order"], lang)))
    if not settings["accepting"]:
        notes.append(t("closed_now", lang))
    if notes:
        view.quote("\n".join(notes))

    rows = []
    for n, i in enumerate(items, 1):
        rows.append([("➖", f"sh:ci:{i['variant_id']}:-1"),
                     (f"{n}. {product_name(i['product'], lang)[:18]} × {i['qty']}", "sh:noop"),
                     ("➕", f"sh:ci:{i['variant_id']}:1")])
    rows.append([(t("clear", lang), "sh:clr"), (t("catalog_btn", lang), "sh:cats")])
    if settings["accepting"]:
        rows.append([(t("checkout_btn", lang, sum=money_l(subtotal, lang)), "sh:co")])
    return view, _kb(rows)


@router.message(StateFilter(None), Btn("b_cart"))
@router.message(Command("cart"))
async def cart_cmd(message: Message, state: FSMContext) -> None:
    await state.clear()
    await show(message, *await cart_view(message.from_user.id))


@router.callback_query(F.data == "sh:cart")
async def cart_cb(call: CallbackQuery) -> None:
    await show(call, *await cart_view(call.from_user.id))
    await call.answer()


@router.callback_query(F.data.startswith("sh:ci:"))
async def cart_item_cb(call: CallbackQuery) -> None:
    _, _, vid, delta = call.data.split(":")
    if int(delta) > 0:
        v = await products.get_variant(int(vid))
        in_cart = next((i["qty"] for i in await db.cart_get(call.from_user.id) if i["variant_id"] == int(vid)), 0)
        if not v or in_cart >= v["stock"]:
            await call.answer(t("qty_limit", await lang_of(call.from_user.id)))
            return
    await db.cart_change(call.from_user.id, int(vid), int(delta))
    await show(call, *await cart_view(call.from_user.id))
    await call.answer()


@router.callback_query(F.data == "sh:clr")
async def cart_clear_cb(call: CallbackQuery) -> None:
    await db.cart_clear(call.from_user.id)
    await show(call, *await cart_view(call.from_user.id, t("cart_cleared", await lang_of(call.from_user.id))))
    await call.answer()


# ====================== rasmiylashtirish ======================

def _reply_kb(*rows: list[KeyboardButton]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[r for r in rows if r], resize_keyboard=True)


def _short(text: str, n: int = 40) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def _cancel_row(lang: str) -> list[KeyboardButton]:
    return [KeyboardButton(text=t("co_cancel", lang))]


async def _back_to_main(message: Message, text: str, user_id: int) -> None:
    lang = await lang_of(user_id)
    await message.answer(text, reply_markup=main_kb(await get_role(user_id), lang))


async def _ask_name(message: Message, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    saved = data.get("saved_name")
    await state.set_state(Checkout.name)
    await message.answer(
        t("ask_name", lang),
        reply_markup=_reply_kb([KeyboardButton(text=_short(saved))] if saved else [], _cancel_row(lang)),
    )


@router.callback_query(F.data == "sh:co")
async def checkout_start(call: CallbackQuery, state: FSMContext) -> None:
    lang = await lang_of(call.from_user.id)
    items = await db.cart_get(call.from_user.id)
    settings = public_settings(await db.get_settings())
    if not items:
        await call.answer(t("e_empty_cart", lang), show_alert=True)
        return
    if not settings["accepting"]:
        await call.answer(t("e_closed_full", lang), show_alert=True)
        return
    subtotal = sum(i["qty"] * i["price"] for i in items)
    if settings["min_order"] and subtotal < settings["min_order"]:
        await call.answer(t("e_min_order", lang, min=money_l(settings["min_order"], lang)), show_alert=True)
        return
    await call.answer()
    u = call.from_user
    user, _ = await db.upsert_user(u.id, u.first_name, u.last_name, u.username)
    await state.clear()
    await state.update_data(
        saved_name=user.get("full_name") or call.from_user.full_name,
        saved_phone=user.get("phone") or "", saved_address=user.get("address") or "",
        saved_region=user.get("region_id"),
    )
    await call.message.answer(t("co_title", lang))
    types = [x for x in ("delivery", "pickup") if settings[f"{x}_enabled"]]
    if len(types) == 2:
        await call.message.answer(t("ask_type", lang), reply_markup=ikb([
            [(t("type_delivery", lang), "sh:ot:delivery")], [(t("type_pickup", lang), "sh:ot:pickup")],
        ]))
        return
    await state.update_data(order_type=types[0] if types else "delivery")
    await _ask_name(call.message, state, lang)


@router.callback_query(F.data.startswith("sh:ot:"))
async def checkout_type(call: CallbackQuery, state: FSMContext) -> None:
    lang = await lang_of(call.from_user.id)
    otype = call.data.split(":")[2]
    await state.update_data(order_type=otype)
    await call.message.edit_text(t("type_delivery" if otype == "delivery" else "type_pickup", lang) + " ✅")
    await call.answer()
    await _ask_name(call.message, state, lang)


@router.message(StateFilter(Checkout), Btn("co_cancel"))
async def checkout_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _back_to_main(message, t("co_cancelled", await lang_of(message.from_user.id)), message.from_user.id)


@router.message(Checkout.name, F.text)
async def checkout_name(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user.id)
    data = await state.get_data()
    name = message.text.strip()
    if data.get("saved_name") and name == _short(data["saved_name"]):
        name = data["saved_name"]
    if not 2 <= len(name) <= 64:
        await message.answer(t("bad_name", lang))
        return
    await state.update_data(name=name)
    await state.set_state(Checkout.phone)
    saved = data.get("saved_phone")
    await message.answer(
        t("ask_phone", lang),
        reply_markup=_reply_kb(
            [KeyboardButton(text=t("send_phone_btn", lang), request_contact=True)],
            [KeyboardButton(text=phone_fmt(saved))] if saved else [],
            _cancel_row(lang),
        ),
    )


async def _region_kb(lang: str, saved: int | None) -> InlineKeyboardMarkup:
    buttons = []
    for r in await regions.get_regions(only_active=True):
        mark = "📍 " if r["id"] == saved else ""
        buttons.append((f"{mark}{regions.region_name(r, lang)}", f"sh:rg:{r['id']}"))
    return ikb([buttons[i:i + 2] for i in range(0, len(buttons), 2)])


async def _regions_table(lang: str, subtotal: int) -> Rich:
    rows = []
    for r in await regions.get_regions(only_active=True):
        fee = regions.delivery_fee(r, subtotal)
        rows.append([h(regions.region_name(r, lang)), money_l(fee, lang) if fee else t("free", lang),
                     regions.eta_text(r, lang)])
    return Rich().p(t("ask_region", lang)).table(rows, align=["left", "right", "center"])


@router.message(Checkout.phone)
async def checkout_phone(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user.id)
    raw = message.contact.phone_number if message.contact else (message.text or "")
    phone = normalize_phone(raw)
    if not phone:
        await message.answer(t("bad_phone", lang))
        return
    await state.update_data(phone=phone)
    data = await state.get_data()
    if data.get("order_type") == "pickup":
        await _ask_comment(message, state, lang)
        return
    await state.set_state(Checkout.region)
    await message.answer("🗺", reply_markup=_reply_kb(_cancel_row(lang)))
    subtotal = sum(i["qty"] * i["price"] for i in await db.cart_get(message.from_user.id))
    await rich.answer(message, await _regions_table(lang, subtotal), await _region_kb(lang, data.get("saved_region")))


@router.callback_query(F.data.startswith("sh:rg:"), Checkout.region)
async def checkout_region(call: CallbackQuery, state: FSMContext) -> None:
    lang = await lang_of(call.from_user.id)
    region = await regions.get_region(int(call.data.split(":")[2]))
    if not region or not region["is_active"]:
        await call.answer(t("e_region", lang), show_alert=True)
        return
    subtotal = sum(i["qty"] * i["price"] for i in await db.cart_get(call.from_user.id))
    fee = regions.delivery_fee(region, subtotal)
    await state.update_data(region_id=region["id"])
    await call.message.edit_text("🗺 " + t("region_line", lang, name=h(regions.region_name(region, lang)),
                                          fee=money_l(fee, lang) if fee else t("free", lang),
                                          eta=regions.eta_text(region, lang)) + " ✅")
    await call.answer()
    data = await state.get_data()
    await state.set_state(Checkout.address)
    saved = data.get("saved_address")
    await call.message.answer(
        t("ask_address", lang),
        reply_markup=_reply_kb(
            [KeyboardButton(text=t("send_location_btn", lang), request_location=True)],
            [KeyboardButton(text="🏠 " + _short(saved))] if saved else [],
            _cancel_row(lang),
        ),
    )


@router.callback_query(F.data.startswith("sh:rg:"))
async def region_stale(call: CallbackQuery) -> None:
    await call.answer(t("form_stale", await lang_of(call.from_user.id)), show_alert=True)


@router.message(Checkout.address)
async def checkout_address(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user.id)
    data = await state.get_data()
    if message.location:
        loc = message.location
        address = f"{t('location_label', lang)}: https://maps.google.com/?q={loc.latitude:.6f},{loc.longitude:.6f}"
        await message.answer(t("location_ok", lang))
    elif message.text:
        address = message.text.strip()
        saved = data.get("saved_address") or ""
        if saved and address == "🏠 " + _short(saved):
            address = saved
        if not 5 <= len(address) <= 300:
            await message.answer(t("bad_address", lang))
            return
    else:
        await message.answer(t("bad_address", lang))
        return
    await state.update_data(address=address)
    await _ask_comment(message, state, lang)


async def _ask_comment(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(Checkout.comment)
    await message.answer(
        t("ask_comment", lang),
        reply_markup=_reply_kb([KeyboardButton(text=t("co_skip", lang))], _cancel_row(lang)),
    )


# ---------- izoh, promo, to'lov ----------

@router.message(Checkout.comment, F.text)
async def checkout_comment(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user.id)
    comment = "" if message.text in both("co_skip") else message.text.strip()[:300]
    await state.update_data(comment=comment)
    await state.set_state(Checkout.promo)
    await message.answer(
        t("ask_promo", lang),
        reply_markup=_reply_kb([KeyboardButton(text=t("co_skip", lang))], _cancel_row(lang)),
    )


async def _raw_cart(user_id: int) -> list[dict]:
    return [{"variant_id": i["variant_id"], "qty": i["qty"]} for i in await db.cart_get(user_id)]


async def _quote(user_id: int, data: dict, lang: str, promo: str | None = None) -> dict:
    return await quote(user_id, await _raw_cart(user_id), data.get("order_type", "delivery"), data.get("region_id"),
                       data.get("promo_code", "") if promo is None else promo, lang)


@router.message(Checkout.promo, F.text)
async def checkout_promo(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user.id)
    code = "" if message.text in both("co_skip") else message.text.strip().upper()[:32]
    if code:
        try:
            q = await _quote(message.from_user.id, await state.get_data(), lang, code)
        except OrderError as e:
            await message.answer("❗️ " + e.text(lang) + "\n\n" + t("ask_promo", lang))
            return
        await state.update_data(promo_code=q["promo_code"])
        await message.answer(t("promo_ok", lang, code=h(q["promo_code"]), label=h(q["promo_label"])))
    await state.set_state(Checkout.payment)
    await message.answer(t("ask_payment", lang), reply_markup=_reply_kb(_cancel_row(lang)))
    await message.answer(
        t("payment_hint", lang),
        reply_markup=ikb([[(t("pay_cash", lang), "sh:pay:cash"), (t("pay_card", lang), "sh:pay:card")]]),
    )


@router.callback_query(F.data.in_({"sh:pay:cash", "sh:pay:card"}), Checkout.payment)
async def pay_cash(call: CallbackQuery, state: FSMContext) -> None:
    lang = await lang_of(call.from_user.id)
    method = call.data.rsplit(":", 1)[1]
    if method == "card" and not payments.card_info(await db.get_settings()):
        await call.answer(t("pay_card_alert", lang), show_alert=True)
        return
    await state.update_data(payment_method=method)
    await state.set_state(Checkout.confirm)
    data = await state.get_data()
    try:
        q = await _quote(call.from_user.id, data, lang)
    except OrderError as e:
        await call.answer(e.text(lang), show_alert=True)
        await state.clear()
        await show(call, *await cart_view(call.from_user.id, "⚠️ " + h(e.text(lang))))
        return
    items = await db.cart_get(call.from_user.id)
    otype = data.get("order_type", "delivery")
    view = Rich().h(_title(t("check_title", lang)))
    lines = []
    for i in items:
        vn = variant_label(i["product"], i["variant"], lang)
        lines.append((f"<b>{h(product_name(i['product'], lang))}</b>" + (f"<br>{h(vn)}" if vn else ""),
                      i["qty"], i["qty"] * i["price"], None))
    totals = [(t("items_sum", lang), money_l(q["subtotal"], lang))]
    if q["promo_code"]:
        disc = f"−{money_l(q['discount'], lang)}" if q["discount"] else h(q["promo_label"])
        totals.append((f"🎁 {t('discount', lang)} ({h(q['promo_code'])})", disc))
    if otype == "delivery":
        totals.append((t("delivery", lang), money_l(q["delivery_fee"], lang) if q["delivery_fee"] else t("free", lang)))
    totals.append((f"<b>{t('total', lang)}</b>", f"<b>{money_l(q['total'], lang)}</b>"))
    _items_table(view, lines, lang, totals)
    info = [[t("payment", lang), t("pay_card" if data.get("payment_method") == "card" else "pay_cash", lang)],
            ["🚚" if otype == "delivery" else "🏬", t("type_delivery" if otype == "delivery" else "type_pickup", lang)],
            ["👤", h(data["name"])], ["📞", phone_fmt(data["phone"])]]
    if otype == "delivery" and q["region"]:
        info += [["🗺", f"{h(q['region']['name'])} · {q['region']['eta']}"], ["📍", h(data["address"])]]
    elif otype == "pickup":
        shop = await db.get_setting("shop_address")
        info.append(["📍", h(shop or t("pickup_shop", lang))])
    if data.get("comment"):
        info.append(["💬", h(data["comment"])])
    view.table(info, striped=False)
    await rich.edit(call.message, view, ikb([[(t("confirm_btn", lang), "sh:ok")],
                                             [(t("refill_btn", lang), "sh:co"), (t("cancel_btn", lang), "sh:no")]]))
    await call.answer()


@router.callback_query(F.data.in_({"sh:pay:cash", "sh:pay:card"}))
async def pay_cash_stale(call: CallbackQuery) -> None:
    await call.answer(t("form_stale", await lang_of(call.from_user.id)), show_alert=True)


@router.callback_query(F.data == "sh:ok", Checkout.confirm)
async def checkout_confirm(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    lang = await lang_of(call.from_user.id)
    data = await state.get_data()
    raw = await _raw_cart(call.from_user.id)
    try:
        order_id = await place_order(call.from_user.id, {**data, "lang": lang}, raw)
    except OrderError as e:
        await call.answer(e.text(lang), show_alert=True)
        if e.status == 409 or not raw or e.key.startswith(("e_promo", "e_closed", "e_min", "e_region")):
            await state.clear()
            await show(call, *await cart_view(call.from_user.id, "⚠️ " + h(e.text(lang))))
        return
    await state.clear()
    await db.cart_clear(call.from_user.id)
    await call.answer(t("order_sent_toast", lang))
    order = await db.get_order(order_id)
    await rich.edit(call.message, Rich().p(t("order_placed", lang, code=order["code"],
                                             total=money_l(order["total"], lang))),
                    ikb([[(t("track_btn", lang), f"sh:o:{order['code']}"),
                          (t("chat_btn", lang), f"sh:ch:{order['code']}")]]))
    await _back_to_main(call.message, t("thanks", lang), call.from_user.id)
    await notify_new_order(bot, order_id, notify_customer=False)


@router.callback_query(F.data == "sh:no")
async def checkout_abort(call: CallbackQuery, state: FSMContext) -> None:
    lang = await lang_of(call.from_user.id)
    await state.clear()
    await show(call, *await cart_view(call.from_user.id, t("co_cancelled", lang)))
    await _back_to_main(call.message, t("main_menu", lang), call.from_user.id)
    await call.answer()


@router.callback_query(F.data == "sh:ok")
async def checkout_confirm_stale(call: CallbackQuery) -> None:
    await call.answer(t("form_stale", await lang_of(call.from_user.id)), show_alert=True)


# ====================== buyurtmalarim ======================

STEPS = ["new", "accepted", "packing", "shipping", "delivered"]


async def orders_view(user_id: int) -> tuple[Rich, InlineKeyboardMarkup]:
    lang = await lang_of(user_id)
    orders = await db.get_user_orders(user_id, limit=10)
    if not orders:
        return Rich().p(t("no_orders", lang)), _kb([[(t("catalog_btn", lang), "sh:cats")]])
    view = Rich().h(_title(t("orders_title", lang).split("\n")[0]))
    view.table([[f"<code>{o['code']}</code>", status_text(o["status"], o["order_type"], lang),
                 money_l(o["total"], lang)] for o in orders], align=["left", "left", "right"])
    view.p(t("orders_title", lang).split("\n\n", 1)[-1])
    rows = []
    for o in orders:
        st = status_text(o["status"], o["order_type"], lang).split(" ", 1)[0]
        rows.append([(f"{st} {o['code']} · {money_l(o['total'], lang)}", f"sh:o:{o['code']}")])
    rows.append([(t("catalog_btn", lang), "sh:cats")])
    return view, _kb(rows)


async def _item_name(it: dict, lang: str) -> str:
    if lang == "ru" and it.get("product_id"):
        p = await db.fetchone("SELECT name_ru FROM products WHERE id = ?", it["product_id"])
        if p and p["name_ru"]:
            return p["name_ru"]
    return it["name"]


def add_months(date_str: str, months: int) -> str:
    """'2026-10-17 ...' + 12 oy -> '17.10.2027'."""
    dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
    y, m = divmod(dt.month - 1 + months, 12)
    year, month = dt.year + y, m + 1
    day = min(dt.day, [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28,
                       31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return f"{day:02d}.{month:02d}.{year}"


async def order_detail_view(order: dict, lang: str) -> tuple[Rich, InlineKeyboardMarkup]:
    items = await db.get_order_items(order["id"])
    log_rows: dict[str, str] = {}
    for r in await db.get_order_log(order["id"]):
        log_rows.setdefault(r["status"], r["at"])
    otype = order.get("order_type") or "delivery"
    view = Rich().h(_title(t("order_title", lang, code=order["code"])))
    view.p(f"🕒 {order['created_at'][:16]} · " + t("type_delivery" if otype == "delivery" else "type_pickup", lang))
    if order["status"] in ("cancelled", "returned"):
        view.quote(f"<b>{t('s_' + order['status'], lang)}</b>" + (
            "\n" + t("reason", lang, reason=h(order["cancel_reason"])) if order["cancel_reason"] else ""))
    else:
        reached = STEPS.index(order["status"])
        steps, checks = [], []
        for i, key in enumerate(STEPS):
            label = t("step_new", lang) if key == "new" else status_text(key, otype, lang).split(" ", 1)[1]
            at = f" — {log_rows[key][5:16].replace('-', '.')}" if key in log_rows else ""
            steps.append((f"<b>{label}</b>" if i == reached else label) + at)
            checks.append(i <= reached)
        view.ul(steps, checks)

    lines = [(f"<b>{h(await _item_name(it, lang))}</b>" + (f"<br>{h(it['variant'])}" if it["variant"] else ""),
              it["qty"], it["price"] * it["qty"], None) for it in items]
    totals = []
    if order.get("discount"):
        totals.append((f"🎁 {t('discount', lang)} ({h(order['promo_code'])})", f"−{money_l(order['discount'], lang)}"))
    if otype == "delivery":
        fee = order["delivery_fee"]
        totals.append((t("delivery", lang), money_l(fee, lang) if fee else t("free", lang)))
    totals.append((f"<b>{t('total', lang)}</b>", f"<b>{money_l(order['total'], lang)}</b>"))
    _items_table(view, lines, lang, totals)
    if otype == "delivery":
        view.p(f"🗺 {h(order['region_name'])}, {h(order['address'])}")
    else:
        shop = await db.get_setting("shop_address")
        view.p(t("pickup_from", lang, address=h(shop or t("pickup_shop", lang))))
    if order.get("comment"):
        view.p(f"💬 {h(order['comment'])}")
    if order["payment_method"] == "card" and order.get("pay_status"):
        pay = t("pay_card", lang) + " · " + t("pay_" + order["pay_status"], lang)
        if order["pay_status"] == "rejected" and order.get("pay_note"):
            pay += "\n" + t("reason", lang, reason=h(order["pay_note"]))
        view.quote(pay)

    media = await chat.get_media(order["id"])
    if media:
        view.gallery([m["path"] for m in media if m["path"]][-10:], t("media_btn", lang, n=len(media)).split(" (")[0])

    if order["status"] == "delivered":
        done = log_rows.get("delivered") or order["updated_at"]
        warranty = []
        for it in items:
            if it["warranty_months"]:
                warranty.append([h(await _item_name(it, lang)), add_months(done, it["warranty_months"]),
                                 f"<code>{h(it['serial'])}</code>" if it["serial"] else "—"])
        if warranty:
            view.h(_title(t("warranty_card", lang)), 3).table(warranty, header=[
                "", "⏳", "IMEI / SN"], align=["left", "center", "left"])

    own_tickets = await tickets.order_tickets(order["id"])
    if own_tickets:
        view.table([[t(f"ticket_kind_{tk['kind']}", lang), ticket_status(tk["status"], lang),
                     h(tk["note"]) or "—"] for tk in own_tickets])

    review = await db.get_review(order["id"])
    if review:
        view.footer(t("your_rating", lang, stars=stars(review["rating"])))

    rows = []
    code = order["code"]
    if payments.can_upload(order):
        rows.append([(t("receipt_btn", lang), f"sh:rc:{code}")])
    if tickets.chat_open(order):
        rows.append([(t("refresh", lang), f"sh:o:{code}")])
        unread = await chat.unread_count(order["id"], "customer")
        rows.append([(t("chat_btn_unread", lang, n=unread) if unread else t("chat_btn", lang), f"sh:ch:{code}")])
    if await tickets.can_return(order):
        until = await tickets.return_until(order)
        rows.append([(t("return_btn", lang, date=until.strftime("%d.%m")), f"sh:rt:{code}")])
    rows.append([(t("issue_btn", lang), f"sh:is:{code}")])
    if order["status"] == "new":
        rows.append([(t("cancel_order_btn", lang), f"sh:oc:{order['code']}")])
    if order["status"] == "delivered" and not review:
        rows.append([(f"{n}⭐", f"rv:{order['id']}:{n}") for n in range(1, 6)])
    if order["status"] in ("delivered", "cancelled", "returned"):
        rows.append([(t("repeat_btn", lang), f"sh:rp:{order['code']}")])
    rows.append([(t("back_orders", lang), "sh:orders")])
    return view, _kb(rows)


@router.message(StateFilter(None), Btn("b_orders"))
@router.message(Command("orders"))
async def orders_cmd(message: Message) -> None:
    await show(message, *await orders_view(message.from_user.id))


@router.callback_query(F.data == "sh:orders")
async def orders_cb(call: CallbackQuery) -> None:
    await show(call, *await orders_view(call.from_user.id))
    await call.answer()


async def _own_order(call: CallbackQuery, lang: str) -> dict | None:
    order = await db.get_order_by_code(call.data.split(":", 2)[2])
    if not order or order["user_id"] != call.from_user.id:
        await call.answer(t("order_not_found", lang), show_alert=True)
        return None
    return order


@router.callback_query(F.data.startswith("sh:o:"))
async def order_cb(call: CallbackQuery) -> None:
    lang = await lang_of(call.from_user.id)
    order = await _own_order(call, lang)
    if not order:
        return
    await show(call, *await order_detail_view(order, lang))
    await call.answer(t("refreshed", lang) if tickets.chat_open(order) else None)


@router.callback_query(F.data.startswith("sh:oc:"))
async def order_cancel_cb(call: CallbackQuery, bot: Bot) -> None:
    lang = await lang_of(call.from_user.id)
    order = await _own_order(call, lang)
    if not order:
        return
    if order["status"] != "new":
        await call.answer(t("cancel_not_allowed", lang), show_alert=True)
        return
    restocked = await cancel_order(order, call.from_user.id, "Mijoz bekor qildi")
    await refresh_staff_messages(bot, order["id"])
    await notify_restocked(bot, restocked)
    await show(call, *await order_detail_view(await db.get_order(order["id"]), lang))
    await call.answer(t("order_cancelled_toast", lang))


@router.callback_query(F.data.startswith("sh:rp:"))
async def order_repeat_cb(call: CallbackQuery) -> None:
    lang = await lang_of(call.from_user.id)
    order = await _own_order(call, lang)
    if not order:
        return
    added = 0
    for it in await db.get_order_items(order["id"]):
        v = await products.get_variant(it["variant_id"]) if it["variant_id"] else None
        p = await products.get_product(v["product_id"]) if v else None
        if not v or not p or not products.sellable(p, v):
            continue
        await db.cart_add(call.from_user.id, v["id"], min(it["qty"], v["stock"]))
        added += 1
    await show(call, *await cart_view(call.from_user.id, t("repeat_added" if added else "repeat_none", lang)))
    await call.answer()


# ====================== buyurtma chati ======================

@router.callback_query(F.data.startswith("sh:ch:"))
async def order_chat_start(call: CallbackQuery, state: FSMContext) -> None:
    lang = await lang_of(call.from_user.id)
    order = await _own_order(call, lang)
    if not order:
        return
    if not tickets.chat_open(order):
        await call.answer(t("chat_closed", lang), show_alert=True)
        return
    await chat.mark_seen(order["id"], "customer")
    await state.set_state(OrderChat.message)
    await state.update_data(chat_order=order["id"])
    await call.answer()
    history = (await chat.get_messages(order["id"]))[-8:]
    view = Rich().h(_title(t("chat_history", lang, code=order["code"])), 3)
    if history:
        view.table([[t("chat_you", lang) if m["sender"] == "customer" else f"🏬 {h(m['name'] or '')}".strip(),
                     h(m["text"]) or "📷", m["at"][11:16]] for m in history], align=["left", "left", "right"])
    view.p(t("chat_ask", lang, code=order["code"]))
    await rich.answer(call.message, view, _reply_kb([KeyboardButton(text=t("co_cancel", lang))]))


@router.message(OrderChat.message, Btn("co_cancel"))
async def order_chat_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _back_to_main(message, t("main_menu", await lang_of(message.from_user.id)), message.from_user.id)


@router.message(OrderChat.message, F.text | F.photo)
async def order_chat_send(message: Message, state: FSMContext, bot: Bot) -> None:
    lang = await lang_of(message.from_user.id)
    order = await db.get_order((await state.get_data()).get("chat_order") or 0)
    await state.clear()
    if not order or order["user_id"] != message.from_user.id:
        await _back_to_main(message, t("order_not_found", lang), message.from_user.id)
        return
    if not tickets.chat_open(order):
        await _back_to_main(message, t("chat_closed", lang), message.from_user.id)
        return
    path, file_id = "", ""
    if message.photo:
        file_id = message.photo[-1].file_id
        path = await save_telegram_photo(bot, file_id)
    text = (message.text or message.caption or "").strip()
    await add_chat_and_relay(bot, order, "customer", message.from_user.id, text, path, file_id)
    await _back_to_main(message, t("chat_sent", lang), message.from_user.id)


# ====================== qaytarish va muammo xabari ======================

@router.callback_query(F.data.startswith(("sh:is:", "sh:rt:")))
async def ticket_start(call: CallbackQuery, state: FSMContext) -> None:
    lang = await lang_of(call.from_user.id)
    order = await _own_order(call, lang)
    if not order:
        return
    kind = "return" if call.data.startswith("sh:rt:") else "issue"
    if await tickets.open_ticket(order["id"]):
        await call.answer(t("ticket_exists", lang), show_alert=True)
        return
    if kind == "return" and not await tickets.can_return(order):
        await call.answer(t("return_not_allowed", lang), show_alert=True)
        return
    await state.set_state(TicketForm.reason)
    await state.update_data(ticket_order=order["id"], ticket_kind=kind, ticket_photos=[])
    await call.answer()
    await call.message.answer(t("return_ask" if kind == "return" else "issue_ask", lang, code=order["code"]),
                              reply_markup=_reply_kb(_cancel_row(lang)))


@router.message(StateFilter(TicketForm), Btn("co_cancel"))
async def ticket_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _back_to_main(message, t("main_menu", await lang_of(message.from_user.id)), message.from_user.id)


@router.message(TicketForm.reason, F.text)
async def ticket_reason(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user.id)
    reason = message.text.strip()
    if len(reason) < 10:
        await message.answer(t("ticket_short", lang))
        return
    data = await state.get_data()
    await state.update_data(ticket_reason=reason[:2000])
    await state.set_state(TicketForm.photos)
    key = "ticket_photos" if data["ticket_kind"] == "return" else "ticket_photos_issue"
    await message.answer(t(key, lang), reply_markup=_reply_kb([KeyboardButton(text=t("ticket_send_btn", lang))],
                                                             _cancel_row(lang)))


@router.message(TicketForm.photos, F.photo)
async def ticket_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    lang = await lang_of(message.from_user.id)
    photos = (await state.get_data()).get("ticket_photos") or []
    if len(photos) >= tickets.MAX_PHOTOS:
        return
    path = await save_telegram_photo(bot, message.photo[-1].file_id, "ticket")
    if path:
        photos.append(path)
        await state.update_data(ticket_photos=photos)
    if not message.media_group_id or len(photos) == 1:
        await message.answer(t("ticket_photo_ok", lang, n=len(photos)))


@router.message(TicketForm.photos, Btn("ticket_send_btn"))
async def ticket_submit(message: Message, state: FSMContext, bot: Bot) -> None:
    lang = await lang_of(message.from_user.id)
    data = await state.get_data()
    if data["ticket_kind"] == "return" and not data.get("ticket_photos"):
        await message.answer(t("ticket_need_photo", lang))
        return
    await state.clear()
    order = await db.get_order(data["ticket_order"])
    if not order or order["user_id"] != message.from_user.id:
        await _back_to_main(message, t("order_not_found", lang), message.from_user.id)
        return
    if await tickets.open_ticket(order["id"]) or (data["ticket_kind"] == "return" and not await tickets.can_return(order)):
        await _back_to_main(message, t("ticket_exists", lang), message.from_user.id)
        return
    tid = await tickets.create(order, data["ticket_kind"], data["ticket_reason"], data.get("ticket_photos") or [])
    await _back_to_main(message, t("ticket_sent", lang, id=tid), message.from_user.id)
    await notify_ticket_new(bot, tid)


@router.message(TicketForm.photos)
async def ticket_photo_hint(message: Message) -> None:
    lang = await lang_of(message.from_user.id)
    await message.answer(t("ticket_photos", lang))


# ====================== baholash ======================

@router.callback_query(F.data.startswith("rv:"))
async def rate_cb(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    lang = await lang_of(call.from_user.id)
    _, order_id, rating = call.data.split(":")
    order = await db.get_order(int(order_id))
    if not order or order["user_id"] != call.from_user.id:
        await call.answer(t("order_not_found", lang), show_alert=True)
        return
    if order["status"] != "delivered":
        await call.answer(t("rate_not_ready", lang), show_alert=True)
        return
    rating = max(1, min(5, int(rating)))
    if not await db.add_review(order["id"], call.from_user.id, rating):
        await call.answer(t("already_rated", lang), show_alert=True)
        return
    await call.answer("⭐" * rating)
    await state.set_state(ReviewComment.text)
    await state.update_data(review_order=order["id"])
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await call.message.answer(
        t("rate_thanks", lang, stars=stars(rating)),
        reply_markup=ikb([[(t("co_skip", lang), f"rvs:{order['id']}")]]),
    )


async def _finish_review(message: Message, state: FSMContext, bot: Bot, order_id: int, user_id: int) -> None:
    await state.clear()
    await message.answer(t("review_saved", await lang_of(user_id)))
    await notify_review(bot, order_id)


@router.message(ReviewComment.text, F.text)
async def review_comment(message: Message, state: FSMContext, bot: Bot) -> None:
    order_id = (await state.get_data()).get("review_order")
    if order_id:
        await db.set_review_comment(order_id, message.text.strip())
    await _finish_review(message, state, bot, order_id, message.from_user.id)


@router.callback_query(F.data.startswith("rvs:"))
async def review_skip(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await call.answer()
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await _finish_review(call.message, state, bot, int(call.data.split(":")[1]), call.from_user.id)


# ====================== karta orqali to'lov: chek ======================

@router.callback_query(F.data.startswith("sh:rc:"))
async def receipt_start(call: CallbackQuery, state: FSMContext) -> None:
    lang = await lang_of(call.from_user.id)
    order = await db.get_order_by_code(call.data.split(":", 2)[2])
    if not order or order["user_id"] != call.from_user.id:
        await call.answer(t("order_not_found", lang), show_alert=True)
        return
    if not payments.can_upload(order):
        await call.answer(t("pay_review", lang) if order.get("pay_status") == "review" else t("e_receipt_closed", lang),
                          show_alert=True)
        return
    await state.set_state(ReceiptForm.photo)
    await state.update_data(receipt_code=order["code"])
    await call.answer()
    card = payments.card_info(await db.get_settings())
    pre = (f"💳 <code>{h(payments.format_number(card['number']))}</code> · <b>{money_l(order['total'], lang)}</b>\n\n"
           if card else "")
    await call.message.answer(pre + t("receipt_ask", lang), reply_markup=_reply_kb(_cancel_row(lang)))


@router.message(ReceiptForm.photo, F.photo | F.document)
async def receipt_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    lang = await lang_of(message.from_user.id)
    if message.document and not (message.document.mime_type or "").startswith("image/"):
        await message.answer(t("receipt_need_photo", lang))
        return
    code = (await state.get_data()).get("receipt_code") or ""
    order = await db.get_order_by_code(code)
    await state.clear()
    if not order or order["user_id"] != message.from_user.id or not payments.can_upload(order):
        await _back_to_main(message, t("e_receipt_closed", lang), message.from_user.id)
        return
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    path = await save_telegram_photo(bot, file_id, "receipt")
    if not path:
        await _back_to_main(message, t("receipt_need_photo", lang), message.from_user.id)
        return
    order = await payments.submit_receipt(order, path)
    await _back_to_main(message, t("receipt_sent", lang), message.from_user.id)
    await notify_receipt(bot, order)
    await refresh_staff_messages(bot, order["id"])


@router.message(ReceiptForm.photo)
async def receipt_other(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user.id)
    if message.text and message.text in (t("co_cancel", "uz"), t("co_cancel", "ru")):
        await state.clear()
        await _back_to_main(message, t("main_menu", lang), message.from_user.id)
        return
    await message.answer(t("receipt_need_photo", lang))
