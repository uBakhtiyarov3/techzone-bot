import asyncio
import re
from datetime import timedelta

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestUsers,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from .. import db, hours, inventory, rich
from ..backup import send_backup
from ..brand import shop_name
from ..config import config
from ..i18n import t
from ..keyboards import B, cancel_kb, ikb, main_kb, manager_kb
from ..notify import broadcast, send_post
from ..orders import public_settings
from ..rich import Rich
from ..roles import IsManager, lang_of
from ..utils import STATUS_LABELS, h, money, now, status_label

router = Router(name="admin")
router.message.filter(IsManager)
router.callback_query.filter(IsManager)


class Broadcast(StatesGroup):
    message = State()
    preview = State()
    buttons = State()


class AddStaff(StatesGroup):
    user = State()


class FindUser(StatesGroup):
    query = State()


# ====================== umumiy ======================

@router.message(F.text == B.CANCEL)
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=manager_kb())


@router.message(StateFilter(None), F.text == B.MANAGER)
@router.message(Command("admin"))
async def panel(message: Message, state: FSMContext) -> None:
    await state.clear()
    s = await db.stats(now().strftime("%Y-%m-%d 00:00:00"))
    active = len(await db.get_active_orders())
    low = len(await inventory.stock_list(only_low=True))
    view = Rich().h(f"👑 {h(shop_name())} — menejer paneli").p(f"Holat: {await _status_line()}")
    view.table([
        ["📦 Buyurtmalar", f"<b>{s['total_orders']}</b> (faol: {active})"],
        ["💰 Tushum", f"<b>{money(s['revenue'])}</b>"],
        ["📈 Yalpi foyda", f"<b>{money(s['gross_profit'])}</b>"],
        ["🙋 Yangi mijozlar", str(s["new_users"])],
    ] + ([["⚠️ Kam qolgan mahsulotlar", f"<b>{low}</b>"]] if low else []), align=["left", "right"],
        caption="Bugun")
    view.footer("Mahsulotlar, ombor, xaridlar, narxlar va barcha sozlamalar — 🖥 Do'kon paneli")
    await rich.answer(message, view, manager_kb())


async def _status_line() -> str:
    s = public_settings(await db.get_settings())
    if not s["accepting"]:
        return "🔴 Buyurtma qabul qilish to'xtatilgan"
    return "🟢 Buyurtma qabul qilinmoqda · " + ("operatorlar ishda" if s["is_open"] else "ish vaqtidan tashqari")


# ====================== statistika ======================

PERIODS = {"today": "Bugun", "week": "7 kun", "month": "30 kun", "all": "Barcha vaqt"}


def _since(period: str) -> str | None:
    n = now()
    days = {"today": 0, "week": 6, "month": 29}.get(period)
    if days is None:
        return None
    return (n - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")


def _period_kb(prefix: str, current: str | None = None):
    return ikb([[((f"• {v} •" if k == current else v), f"{prefix}:{k}") for k, v in PERIODS.items()]])


async def _stats_view(period: str) -> Rich:
    since = _since(period)
    s = await db.stats(since)
    bs = s["by_status"]
    view = Rich().h(f"📊 Statistika — {PERIODS[period]}")
    view.table([
        ["💰 Tushum (yakunlangan)", f"<b>{money(s['revenue'])}</b>"],
        ["📈 Yalpi foyda", f"<b>{money(s['gross_profit'])}</b>"],
        ["🏷 Tannarx", money(s["cogs"])],
        ["🧾 O'rtacha chek", money(s["avg_check"])],
        ["📦 Sotilgan", f"{s['units']} dona"],
        ["⏳ Jarayondagi summa", money(s["pending_sum"])],
        ["🛒 Xaridlar (kirim)", money(s["purchases"])],
        ["🎁 Promo chegirmalar", money(s["promo_sum"])],
    ], align=["left", "right"], striped=False)
    view.h(f"📦 Buyurtmalar: {s['total_orders']}", 3)
    rows = [[STATUS_LABELS[st], str(bs[st])] for st in ("new", "accepted", "packing", "shipping", "delivered",
                                                         "cancelled") if bs.get(st)]
    bt = s["by_type"]
    if bt:
        rows.append(["🚚 Yetkazish / 🏬 Olib ketish", f"{bt.get('delivery', 0)} / {bt.get('pickup', 0)}"])
    view.table(rows, align=["left", "right"])
    r = s["rating"]
    people = [f"🙋 Buyurtma bergan mijozlar: <b>{s['customers']}</b>",
              f"🆕 Yangi foydalanuvchilar: <b>{s['new_users']}</b>",
              f"👥 Jami foydalanuvchilar: <b>{s['users_total']}</b>"]
    if r["count"]:
        people.append(f"⭐ O'rtacha baho: <b>{r['avg']}</b> / 5 ({r['count']} ta)")
    view.lines(people)
    if s["top"]:
        view.h("🏆 Top mahsulotlar", 3).table(
            [[f"{i}. {h(row['name'])}", f"{row['qty']} ta", money(row["amount"])] for i, row in enumerate(s["top"], 1)],
            align=["left", "center", "right"])
    if s["top_brands"]:
        view.h("🏷 Brendlar", 3).table([[h(b["name"]), f"{b['qty']} ta", money(b["amount"])] for b in s["top_brands"]],
                                       align=["left", "center", "right"])
    staff = await db.staff_stats(since)
    if staff:
        view.h("👷 Xodimlar (yakunlangan)", 3).table(
            [[h(st["name"]), f"{st['c']} ta", money(st["amount"])] for st in staff], align=["left", "center", "right"])
    return view


@router.message(StateFilter(None), F.text == B.STATS)
async def stats(message: Message) -> None:
    await rich.answer(message, await _stats_view("today"), _period_kb("st", "today"))


@router.callback_query(F.data.startswith("st:"))
async def stats_period(call: CallbackQuery) -> None:
    period = call.data.split(":")[1]
    await rich.edit(call.message, await _stats_view(period), _period_kb("st", period))
    await call.answer()


# ====================== buyurtmalar ======================

@router.message(StateFilter(None), F.text == B.ORDERS)
async def orders(message: Message) -> None:
    await _orders_list(message, "active")


async def _orders_list(message: Message, kind: str, edit: bool = False) -> None:
    if kind == "active":
        rows = await db.get_active_orders()
        title = "🔄 Faol buyurtmalar"
    elif kind == "done":
        rows = await db.get_orders_by_status(("delivered",), limit=20)
        title = "🎉 Oxirgi yakunlanganlar"
    else:
        rows = await db.get_orders_by_status(("cancelled",), limit=20)
        title = "❌ Oxirgi bekor qilinganlar"
    buttons = [
        [(f"{'🏬' if o['order_type'] == 'pickup' else '🚚'} {o['code']} · "
          f"{status_label(o['status'], o['order_type']).split(' ', 1)[1]} · {money(o['total'])}", f"ov:{o['id']}")]
        for o in rows[:30]
    ]
    buttons.append([("🔄 Faol", "ol:active"), ("🎉 Yakunlangan", "ol:done"), ("❌ Bekor", "ol:cancel")])
    text = f"<b>{title}</b> ({len(rows)})\n\nBatafsil ko'rish uchun buyurtmani tanlang.\n" \
           "ID bo'yicha qidirish: /order TZ-482917"
    if not rows:
        text = f"<b>{title}</b>\n\nHozircha bo'sh."
    if edit:
        await message.edit_text(text, reply_markup=ikb(buttons))
    else:
        await message.answer(text, reply_markup=ikb(buttons))


@router.callback_query(F.data.startswith("ol:"))
async def orders_kind(call: CallbackQuery) -> None:
    await _orders_list(call.message, call.data.split(":")[1], edit=True)
    await call.answer()


# ====================== ombor ======================

@router.message(StateFilter(None), F.text == B.STOCK)
async def stock(message: Message) -> None:
    value = await inventory.stock_value()
    low = await inventory.stock_list(only_low=True)
    lines = [
        "🏷 <b>Ombor</b>\n",
        f"📦 Jami qoldiq: <b>{value['units']}</b> dona",
        f"💵 Tannarx bo'yicha: <b>{money(value['cost'])}</b>",
        f"🏷 Sotuv narxida: <b>{money(value['retail'])}</b>",
    ]
    if low:
        lines.append(f"\n⚠️ <b>Kam qolgan / tugagan ({len(low)}):</b>")
        for v in low[:25]:
            vals = ", ".join(v["vals"])
            lines.append(f"• {h(v['name'])}{' (' + h(vals) + ')' if vals else ''} — "
                         f"<b>{v['stock']}</b>{' ⛔️' if v['stock'] <= 0 else ''}")
    lines.append("\nKirim (xarid), inventarizatsiya va harakatlar tarixi — 🖥 Do'kon paneli → Ombor.")
    await message.answer("\n".join(lines))


# ====================== hisobot (CSV) ======================

@router.message(StateFilter(None), F.text == B.EXPORT)
async def export(message: Message) -> None:
    await message.answer("📥 Qaysi davr uchun hisobot kerak?", reply_markup=_period_kb("ex"))


@router.callback_query(F.data.startswith("ex:"))
async def export_period(call: CallbackQuery) -> None:
    from ..admin_api import orders_csv

    period = call.data.split(":")[1]
    data, count = await orders_csv(_since(period))
    fname = f"buyurtmalar_{period}_{now().strftime('%Y%m%d_%H%M')}.csv"
    await call.message.answer_document(BufferedInputFile(data, filename=fname),
                                       caption=f"📥 {PERIODS[period]}: {count} ta buyurtma")
    await call.answer()


# ====================== buyurtmani o'chirish ======================

@router.message(Command("delorder"))
async def delorder_ask(message: Message) -> None:
    query = (message.text or "").split(maxsplit=1)[1:] or [""]
    order = await db.find_order(query[0]) if query[0] else None
    if not order:
        await message.answer("🗑 Buyurtmani o'chirish: <code>/delorder TZ-123456</code>\n"
                             "(yoki admin web panel → Buyurtmalar → buyurtma → «O'chirish»)")
        return
    await message.answer(
        f"🗑 <b>{order['code']}</b> buyurtmasi butunlay o'chirilsinmi?\n"
        f"{h(order['customer_name'])} · {money(order['total'])} · {status_label(order['status'], order['order_type'])}\n\n"
        "Statistika va hisobotlardan ham o'chadi. Qaytarib bo'lmaydi.",
        reply_markup=ikb([[("✅ Ha, o'chirish", f"odl:{order['id']}"), ("❌ Yo'q", "odl:no")]]),
    )


@router.callback_query(F.data.startswith("odl:"))
async def delorder_do(call: CallbackQuery, bot: Bot) -> None:
    from ..notify import delete_order

    arg = call.data.split(":")[1]
    order = await db.get_order(int(arg)) if arg.isdigit() else None
    if not order:
        await call.message.edit_text("Bekor qilindi." if arg == "no" else "Buyurtma topilmadi.")
        await call.answer()
        return
    await delete_order(bot, order)
    await call.message.edit_text(f"🗑 Buyurtma <b>{order['code']}</b> o'chirildi.")
    await call.answer()


# ====================== do'kon paneli (web) ======================

@router.message(StateFilter(None), F.text == B.WEB_PANEL)
@router.message(Command("panel"))
async def web_panel(message: Message) -> None:
    from ..admin_api import LOGIN_CODE_MINUTES, make_login_link

    link = await make_login_link(message.from_user.id)
    rows = []
    if link.startswith("https://"):
        rows.append([InlineKeyboardButton(text="🌐 Brauzerda ochish", url=link)])
        rows.append([InlineKeyboardButton(text="📱 Telegram ichida ochish",
                                          web_app=WebAppInfo(url=link.split("#", 1)[0]))])
    await message.answer(
        "🖥 <b>Do'kon paneli</b>\n\n"
        "Onlayn do'konni to'liq boshqarish: sotuvlar va foyda, buyurtmalar (holat, rasm, chat), mahsulotlar, "
        "variantlar va narxlar, ombor va xaridlar, mijozlar, promo-kodlar, hududlar, rassilka, bot matnlari "
        "va brend sozlamalari. Saqlash bilan bot darhol yangilanadi.\n\n"
        f"🔐 Havola bir martalik va {LOGIN_CODE_MINUTES} daqiqa amal qiladi. Uni hech kimga bermang!"
        + ("" if rows else f"\n\n<code>{h(link)}</code>"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows) if rows else None,
        disable_web_page_preview=True,
    )


# ====================== zaxira nusxa ======================

@router.message(StateFilter(None), F.text == B.BACKUP)
async def backup(message: Message, bot: Bot) -> None:
    await message.answer("⏳ Zaxira nusxa tayyorlanmoqda...")
    await send_backup(bot, [message.chat.id])
    await message.answer("ℹ️ Har kuni soat 04:00 da zaxira nusxa bosh menejerga avtomatik yuboriladi.")


# ====================== mijozlar ======================

@router.message(StateFilter(None), F.text == B.USERS)
async def users(message: Message, state: FSMContext) -> None:
    total = await db.scalar("SELECT COUNT(*) FROM users")
    blocked = await db.scalar("SELECT COUNT(*) FROM users WHERE is_blocked = 1")
    with_orders = await db.scalar("SELECT COUNT(DISTINCT user_id) FROM orders")
    top = await db.fetchall(
        "SELECT u.id, COALESCE(u.full_name, u.first_name) name, u.phone, COUNT(o.id) c, SUM(o.total) s"
        " FROM orders o JOIN users u ON u.id = o.user_id WHERE o.status = 'delivered'"
        " GROUP BY u.id ORDER BY s DESC LIMIT 10"
    )
    lines = [
        "🙋 <b>Mijozlar</b>\n",
        f"Jami: <b>{total}</b>",
        f"Buyurtma berganlar: <b>{with_orders}</b>",
        f"Botni bloklaganlar: {blocked}",
    ]
    if top:
        lines.append("\n🏆 <b>Eng faol mijozlar:</b>")
        for i, u in enumerate(top, 1):
            lines.append(f"{i}. {h(u['name'])} ({h(u['phone'] or '-')}) — {u['c']} ta, {money(u['s'])}")
    await message.answer("\n".join(lines), reply_markup=ikb([[("🔍 Mijozni qidirish", "ufind")]]))


@router.callback_query(F.data == "ufind")
async def user_find_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(FindUser.query)
    await call.message.answer("Mijoz ID si, @username yoki telefon raqamini yuboring:", reply_markup=cancel_kb())
    await call.answer()


@router.message(FindUser.query, F.text)
async def user_find(message: Message, state: FSMContext) -> None:
    q = message.text.strip()
    user = await db.find_user(q)
    if not user:
        digits = re.sub(r"\D", "", q)
        if digits:
            user = await db.fetchone("SELECT * FROM users WHERE phone LIKE ?", f"%{digits[-9:]}")
    if not user:
        await message.answer("Topilmadi. Qaytadan yuboring yoki bekor qiling.")
        return
    await state.clear()
    st = await db.fetchone(
        "SELECT COUNT(*) c, COALESCE(SUM(total), 0) s FROM orders WHERE user_id = ? AND status = 'delivered'",
        user["id"],
    )
    last = await db.get_user_orders(user["id"], limit=5)
    lines = [
        f"👤 <b>{h(user['full_name'] or user['first_name'])}</b>",
        f"ID: <code>{user['id']}</code>",
        f"Username: @{h(user['username'])}" if user["username"] else "Username: -",
        f"Telefon: {h(user['phone'] or '-')}",
        f"Manzil: {h(user['address'] or '-')}",
        f"Rol: {user['role']}",
        f"Ro'yxatdan o'tgan: {user['created_at'][:16]}",
        f"Yetkazilgan buyurtmalar: {st['c']} ta, {money(st['s'])}",
    ]
    if last:
        lines.append("\nOxirgi buyurtmalar:")
        lines += [f"{o['code']} — {money(o['total'])} — {status_label(o['status'], o['order_type'])}" for o in last]
    await message.answer("\n".join(lines), reply_markup=manager_kb())


# ====================== rassilka ======================

_album_buffer: dict[tuple[int, str], list[int]] = {}
URL_RE = re.compile(r"^(.+?)\s*[-|–—]\s*((?:https?://|tg://)\S+)$")


def _broadcast_markup(data: dict) -> InlineKeyboardMarkup | None:
    rows = [[InlineKeyboardButton(text=t, url=u)] for t, u in data.get("buttons", [])]
    if data.get("order_btn"):
        rows.append([InlineKeyboardButton(text="🛍 Katalogni ochish", callback_data="sh:cats")])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def _url_buttons(markup: InlineKeyboardMarkup | None) -> list[list[str]]:
    """Kanal postidagi URL tugmalarni saqlab qolish uchun."""
    if not markup:
        return []
    return [[b.text, b.url] for row in markup.inline_keyboard for b in row if b.url]


@router.message(StateFilter(None), F.text == B.BROADCAST)
async def broadcast_start(message: Message, state: FSMContext) -> None:
    count = len(await db.all_user_ids())
    await state.set_state(Broadcast.message)
    await message.answer(
        f"📢 <b>Barchaga xabar yuborish</b> ({count} ta foydalanuvchi)\n\n"
        "Postni shu yerga yuboring — u qanday bo'lsa, foydalanuvchilarga xuddi shunday boradi:\n"
        "• matn, rasm yoki video (izohi bilan)\n"
        "• 🖼 albom — bir nechta rasm/video birga\n"
        "• ↪️ kanaldagi <b>tayyor rasmli postni forward qiling</b> (tugmalari ham saqlanadi)\n\n"
        "Keyin xohlasangiz havola tugma yoki «Katalog» tugmasini qo'shasiz.",
        reply_markup=cancel_kb(),
    )


@router.message(Broadcast.message)
async def broadcast_receive(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.media_group_id:
        key = (message.chat.id, message.media_group_id)
        first = key not in _album_buffer
        _album_buffer.setdefault(key, []).append(message.message_id)
        if not first:
            return
        await asyncio.sleep(1.5)  # albomning qolgan qismlari kelishini kutamiz
        ids = sorted(_album_buffer.pop(key, []))
    else:
        ids = [message.message_id]
    forwarded = bool(message.forward_origin)
    await state.update_data(
        chat_id=message.chat.id, message_ids=ids, mode="copy", order_btn=False,
        buttons=_url_buttons(message.reply_markup), forwarded=forwarded,
    )
    await state.set_state(Broadcast.preview)
    await _broadcast_preview(message, state, bot)


async def _broadcast_preview(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    album = len(data["message_ids"]) > 1
    markup = _broadcast_markup(data)
    await message.answer("👇 <b>Foydalanuvchilar ko'radigan ko'rinish:</b>", reply_markup=cancel_kb())
    await send_post(bot, message.chat.id, data["chat_id"], data["message_ids"], data["mode"], markup)

    count = len(await db.all_user_ids())
    notes = [f"👥 Qabul qiluvchilar: <b>{count}</b>",
             f"Turi: {'🖼 albom (' + str(len(data['message_ids'])) + ' ta)' if album else '📄 bitta post'}",
             f"Rejim: {'↪️ Forward (manba ko`rinadi)' if data['mode'] == 'forward' else '📋 Nusxa (bot nomidan)'}"]
    can_buttons = data["mode"] == "copy" and not album
    if not can_buttons:
        notes.append("ℹ️ Albom va forward rejimida qo'shimcha tugmalar biriktirilmaydi.")
    rows = [[(f"✅ Yuborish ({count} ta)", "bc:send")]]
    if can_buttons:
        rows.append([("🔗 Havola tugma qo'shish", "bc:link"),
                     (("✅ " if data.get("order_btn") else "➕ ") + "«Katalog» tugmasi", "bc:order")])
        if data.get("buttons"):
            rows.append([("🗑 Havola tugmalarni o'chirish", "bc:clear")])
    rows.append([("📋 Nusxa rejimi" if data["mode"] == "forward" else "↪️ Forward rejimi", "bc:mode")])
    rows.append([("🚫 Bekor qilish", "bc:no")])
    await message.answer("\n".join(notes), reply_markup=ikb(rows))


@router.callback_query(F.data.in_({"bc:order", "bc:mode", "bc:clear"}), Broadcast.preview)
async def broadcast_toggle(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    if call.data == "bc:order":
        await state.update_data(order_btn=not data.get("order_btn"))
    elif call.data == "bc:mode":
        await state.update_data(mode="copy" if data["mode"] == "forward" else "forward")
    else:
        await state.update_data(buttons=[])
    await call.message.delete()
    await call.answer()
    await _broadcast_preview(call.message, state, bot)


@router.callback_query(F.data == "bc:link", Broadcast.preview)
async def broadcast_link_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Broadcast.buttons)
    await call.message.answer(
        "🔗 Tugmalarni yuboring — har bir qatorda bitta:\n"
        "<code>Matn - https://havola</code>\n\n"
        "Masalan:\n<code>Instagram - https://instagram.com/techzone\n"
        "Kanalimiz - https://t.me/techzone</code>",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.message(Broadcast.buttons, F.text)
async def broadcast_link_save(message: Message, state: FSMContext, bot: Bot) -> None:
    buttons = []
    for line in message.text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        m = URL_RE.match(line)
        if not m:
            await message.answer(f"❗️ Format noto'g'ri: <code>{h(line)}</code>\nTo'g'ri: <code>Matn - https://havola</code>")
            return
        buttons.append([m.group(1)[:40], m.group(2)])
    data = await state.get_data()
    await state.update_data(buttons=(data.get("buttons") or []) + buttons)
    await state.set_state(Broadcast.preview)
    await _broadcast_preview(message, state, bot)


@router.callback_query(F.data.in_({"bc:send", "bc:no"}), Broadcast.preview)
async def broadcast_confirm(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    if call.data == "bc:no":
        await call.message.edit_text("Rassilka bekor qilindi.")
        await call.message.answer("Menejer paneli", reply_markup=manager_kb())
        await call.answer()
        return
    await call.message.edit_text("⏳ Yuborilmoqda...")
    await call.message.answer("Rassilka fonda ketmoqda, tugagach xabar beraman.", reply_markup=manager_kb())
    await call.answer()
    markup = _broadcast_markup(data)

    async def run():
        async def progress(i, total):
            try:
                await call.message.edit_text(f"⏳ Yuborilmoqda... {i}/{total}")
            except Exception:
                pass
        ok, fail = await broadcast(bot, data["chat_id"], data["message_ids"], data["mode"], markup, progress)
        await call.message.edit_text(f"✅ Rassilka tugadi!\n\nYuborildi: {ok}\nYetib bormadi: {fail}")

    asyncio.create_task(run())


@router.callback_query(F.data.startswith("bc:"))
async def broadcast_stale(call: CallbackQuery) -> None:
    await call.answer("Bu rassilka eskirgan. «📢 Xabar yuborish» ni qaytadan bosing.", show_alert=True)


# ====================== xodimlar ======================

ROLE_NAMES = {"staff": "👷 Xodim", "manager": "👑 Menejer"}


async def _staff_view() -> tuple[str, list]:
    staff = await db.get_staff()
    lines = ["👥 <b>Xodimlar</b>\n"]
    lines += [f"👑 Bosh menejer: <code>{a}</code>" for a in sorted(config.admin_ids)]
    buttons = []
    for u in staff:
        name = h(u["full_name"] or u["first_name"] or u["id"])
        lines.append(f"{ROLE_NAMES[u['role']]}: {name} (<code>{u['id']}</code>)")
        buttons.append([(f"🗑 {u['first_name'] or u['id']} ni olib tashlash", f"srm:{u['id']}")])
    if not staff:
        lines.append("\nHali xodim qo'shilmagan.")
    lines.append("\nYangi buyurtma kartalari xodimlarga boradi; menejerlar bajarilgan buyurtma hisobotini oladi.")
    buttons.append([("➕ Xodim qo'shish", "sadd:staff"), ("➕ Menejer qo'shish", "sadd:manager")])
    return "\n".join(lines), buttons


@router.message(StateFilter(None), F.text == B.STAFF_LIST)
async def staff_list(message: Message) -> None:
    text, buttons = await _staff_view()
    await message.answer(text, reply_markup=ikb(buttons))


@router.callback_query(F.data.startswith("sadd:"))
async def staff_add_start(call: CallbackQuery, state: FSMContext) -> None:
    role = call.data.split(":")[1]
    await state.set_state(AddStaff.user)
    await state.update_data(role=role)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Kontaktlardan tanlash",
                            request_users=KeyboardButtonRequestUsers(request_id=1, user_is_bot=False))],
            [KeyboardButton(text=B.CANCEL)],
        ],
        resize_keyboard=True,
    )
    await call.message.answer(
        f"{ROLE_NAMES[role]} qo'shish.\n\n"
        "Pastdagi tugma orqali kontaktlardan tanlang yoki uning Telegram <b>ID</b> raqamini / "
        "<b>@username</b> ini yuboring (username uchun u avval botga /start bosgan bo'lishi kerak).",
        reply_markup=kb,
    )
    await call.answer()


@router.message(AddStaff.user)
async def staff_add(message: Message, state: FSMContext, bot: Bot) -> None:
    role = (await state.get_data())["role"]
    user = None
    if message.users_shared:
        uid = message.users_shared.user_ids[0]
        user = await db.get_user(uid)
        if not user:
            await db.upsert_user(uid, "", None, None)
            user = await db.get_user(uid)
    elif message.text:
        user = await db.find_user(message.text)
        if not user and message.text.strip().isdigit():
            await db.upsert_user(int(message.text.strip()), "", None, None)
            user = await db.get_user(int(message.text.strip()))
    if not user:
        await message.answer("❗️ Foydalanuvchi topilmadi. U avval botga /start bosishi kerak yoki ID yuboring.")
        return
    await db.set_role(user["id"], role)
    await state.clear()
    await message.answer(f"✅ {ROLE_NAMES[role]} qo'shildi: <code>{user['id']}</code>", reply_markup=manager_kb())
    try:
        await bot.send_message(
            user["id"],
            f"🎉 Sizga <b>{h(shop_name())}</b> botida {ROLE_NAMES[role]} huquqi berildi!\n"
            "Endi yangi buyurtmalar haqida xabar olasiz. /start bosing.",
            reply_markup=main_kb(role),
        )
    except Exception:
        await message.answer("ℹ️ Unga xabar yuborib bo'lmadi — u botga /start bosishi kerak.")


@router.callback_query(F.data.startswith("srm:"))
async def staff_remove(call: CallbackQuery, bot: Bot) -> None:
    uid = int(call.data.split(":")[1])
    await db.set_role(uid, "user")
    text, buttons = await _staff_view()
    await call.message.edit_text(text, reply_markup=ikb(buttons))
    await call.answer("Olib tashlandi")
    try:
        await bot.send_message(uid, "Sizning xodim huquqingiz olib tashlandi.", reply_markup=main_kb("user"))
    except Exception:
        pass


# ====================== do'kon holati ======================

MODES = ["auto", "open", "closed"]
MODE_LABELS = {"auto": "🕒 Qabul qilinmoqda (ish vaqti jadval bo'yicha)", "open": "🟢 Qabul qilinmoqda (doim ochiq)",
               "closed": "🔴 Buyurtma to'xtatilgan"}


async def _settings_view() -> tuple[str, list]:
    s = await db.get_settings()
    yes = lambda key: s.get(key, "1") == "1"  # noqa: E731
    text = (
        "⚙️ <b>Do'kon holati</b>\n\n"
        f"Holat: {await _status_line()}\n"
        f"🗓 Operatorlar ish vaqti: {h(hours.schedule_summary(s))}\n\n"
        f"🚚 Yetkazib berish: {'✅ yoqilgan' if yes('delivery_enabled') else '❌ o`chirilgan'}\n"
        f"🏬 Olib ketish: {'✅ yoqilgan' if yes('pickup_enabled') else '❌ o`chirilgan'}\n"
        f"📍 Do'kon manzili: {h(s.get('shop_address') or '-')}\n"
        f"📞 Telefon: {h(s.get('phone') or '-')}\n\n"
        "Hududlar, narxlar, ish jadvali va brend — 🖥 Do'kon paneli → Sozlamalar."
    )
    buttons = [
        [("Rejim: " + MODE_LABELS[s.get("mode") or "auto"] + " 🔁", "set:mode")],
        [(("✅" if yes("delivery_enabled") else "❌") + " Yetkazib berish", "set:tgl:delivery_enabled"),
         (("✅" if yes("pickup_enabled") else "❌") + " Olib ketish", "set:tgl:pickup_enabled")],
    ]
    return text, buttons


async def _refresh_settings(call: CallbackQuery) -> None:
    text, buttons = await _settings_view()
    await call.message.edit_text(text, reply_markup=ikb(buttons))


@router.message(StateFilter(None), F.text == B.SETTINGS)
async def settings(message: Message) -> None:
    text, buttons = await _settings_view()
    await message.answer(text, reply_markup=ikb(buttons))


@router.callback_query(F.data == "set:mode")
async def settings_mode(call: CallbackQuery) -> None:
    cur = await db.get_setting("mode") or "auto"
    new = MODES[(MODES.index(cur) + 1) % len(MODES)] if cur in MODES else "auto"
    await db.set_setting("mode", new)
    await _refresh_settings(call)
    await call.answer(MODE_LABELS[new])


@router.callback_query(F.data.startswith("set:tgl:"))
async def settings_toggle(call: CallbackQuery) -> None:
    key = call.data.split(":")[2]
    if key not in ("delivery_enabled", "pickup_enabled"):
        await call.answer()
        return
    s = await db.get_settings()
    new = "0" if s.get(key, "1") == "1" else "1"
    other = "pickup_enabled" if key == "delivery_enabled" else "delivery_enabled"
    if new == "0" and s.get(other, "1") != "1":
        await call.answer("Kamida bittasi (yetkazish yoki olib ketish) yoqilgan bo'lishi kerak", show_alert=True)
        return
    await db.set_setting(key, new)
    await _refresh_settings(call)
    await call.answer("Saqlandi")


# ====================== mijoz xabarlariga javob ======================

@router.message(StateFilter(None), F.reply_to_message, F.reply_to_message.text.regexp(r"#u(\d+)", mode="search"))
async def reply_to_customer(message: Message, bot: Bot) -> None:
    uid = int(re.search(r"#u(\d+)", message.reply_to_message.text).group(1))
    try:
        await bot.send_message(uid, t("reply_from_shop", await lang_of(uid)))
        await bot.copy_message(uid, message.chat.id, message.message_id)
        await message.reply("✅ Javob yuborildi")
    except Exception:
        await message.reply("❗️ Yuborib bo'lmadi (mijoz botni bloklagan bo'lishi mumkin)")
