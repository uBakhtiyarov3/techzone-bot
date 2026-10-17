from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .. import chat, db, rich, tickets
from ..keyboards import B, cancel_kb, ikb, order_staff_kb, staff_kb
from ..notify import (
    add_chat_and_relay, notify_restocked, notify_status_change, notify_ticket_decision, refresh_staff_messages,
    save_telegram_photo, send_status_photo, ticket_staff_kb, ticket_view,
)
from ..order_card import send_order_card
from ..orders import cancel_order, decide_ticket
from ..roles import IsStaff
from ..utils import ACTIVE_STATUSES, h, item_title, money, next_status, now, status_label

router = Router(name="staff")
router.message.filter(IsStaff)
router.callback_query.filter(IsStaff)

CANCEL_REASONS = [
    "Mijoz bekor qildi",
    "Mijoz bilan bog'lanib bo'lmadi",
    "Mahsulot omborda qolmagan",
    "Manzil yetkazish hududidan tashqarida",
    "Boshqa sabab",
]


class StaffInput(StatesGroup):
    photo = State()
    chat = State()
    serial = State()
    reject_note = State()


@router.message(StateFilter(None), F.text == B.STAFF)
@router.message(Command("staff"))
async def staff_home(message: Message) -> None:
    new = len(await db.get_orders_by_status(("new",), limit=100))
    active = len(await db.get_orders_by_status(("accepted", "packing", "shipping"), limit=100))
    unread = len(await chat.unread_orders_for_staff())
    await message.answer(
        "👷 <b>Xodim kabineti</b>\n\n"
        f"🆕 Yangi buyurtmalar: <b>{new}</b>\n"
        f"🔄 Jarayondagi: <b>{active}</b>\n"
        f"💬 Javobsiz chatlar: <b>{unread}</b>\n\n"
        "Yangi buyurtma tushganda sizga avtomatik xabar keladi. Kartadagi tugmalar orqali holatni yangilang, "
        "📸 rasm yuboring (masalan, yig'ilgan buyurtma) va mijoz bilan yozishing.",
        reply_markup=staff_kb(),
    )


async def _send_order_list(message: Message, orders: list[dict], empty: str) -> None:
    if not orders:
        await message.answer(empty)
        return
    for o in reversed(orders[:10]):
        items = await db.get_order_items(o["id"])
        msg = await send_order_card(message.bot, message.chat.id, o, items, reply_markup=order_staff_kb(o))
        # shu karta ham holat o'zgarganda yangilanib turadi
        await db.save_order_message(o["id"], msg.chat.id, msg.message_id)
    if len(orders) > 10:
        await message.answer(f"... va yana {len(orders) - 10} ta buyurtma.")


@router.message(StateFilter(None), F.text == B.NEW_ORDERS)
async def new_orders(message: Message) -> None:
    await _send_order_list(message, await db.get_orders_by_status(("new",)), "✅ Yangi buyurtmalar yo'q.")


@router.message(StateFilter(None), F.text == B.ACTIVE_ORDERS)
async def active_orders(message: Message) -> None:
    orders = await db.get_orders_by_status(("accepted", "packing", "shipping"))
    await _send_order_list(message, orders, "Jarayondagi buyurtmalar yo'q.")


@router.message(StateFilter(None), F.text == B.MY_TASKS)
async def my_tasks(message: Message) -> None:
    orders = await db.get_orders_by_status(ACTIVE_STATUSES, staff_id=message.from_user.id)
    await _send_order_list(message, orders, "Sizga biriktirilgan faol buyurtmalar yo'q.")


@router.message(StateFilter(None), F.text == B.TODAY)
async def today(message: Message) -> None:
    since = now().strftime("%Y-%m-%d 00:00:00")
    uid = message.from_user.id
    mine = await db.fetchone(
        "SELECT COUNT(*) c, COALESCE(SUM(total), 0) s FROM orders"
        " WHERE staff_id = ? AND status = 'delivered' AND created_at >= ?", uid, since,
    )
    allc = await db.fetchone(
        "SELECT COUNT(*) c, COALESCE(SUM(total), 0) s FROM orders"
        " WHERE status = 'delivered' AND created_at >= ?", since,
    )
    await message.answer(
        "📈 <b>Bugungi natija</b>\n\n"
        f"Siz yakunlagan: <b>{mine['c']}</b> ta · {money(mine['s'])}\n"
        f"Jami yakunlangan: <b>{allc['c']}</b> ta · {money(allc['s'])}"
    )


@router.message(Command("order"))
async def show_order(message: Message, command: CommandObject) -> None:
    if not command.args:
        await message.answer("Foydalanish: /order TZ-482917 (yoki faqat 482917)")
        return
    order = await db.find_order(command.args)
    if not order:
        await message.answer("Buyurtma topilmadi.")
        return
    await _send_order_list(message, [order], "")


@router.callback_query(F.data.startswith("ov:"))
async def view_order(call: CallbackQuery) -> None:
    order = await db.get_order(int(call.data.split(":")[1]))
    if not order:
        await call.answer("Topilmadi", show_alert=True)
        return
    await call.answer()
    await _send_order_list(call.message, [order], "")


@router.callback_query(F.data.startswith("ost:"))
async def change_status(call: CallbackQuery, bot: Bot) -> None:
    _, order_id, new_status = call.data.split(":")
    order = await db.get_order(int(order_id))
    if not order:
        await call.answer("Buyurtma topilmadi", show_alert=True)
        return
    otype = order.get("order_type") or "delivery"
    expected = (next_status(order["status"], otype) or (None,))[0]
    if expected != new_status:
        # boshqa xodim allaqachon o'zgartirgan
        await call.answer(f"Holat allaqachon: {status_label(order['status'], otype)}", show_alert=True)
        await refresh_staff_messages(bot, order["id"])
        return
    await db.set_order_status(order["id"], new_status, call.from_user.id)
    await call.answer(status_label(new_status, otype))
    await notify_status_change(bot, order["id"])


@router.callback_query(F.data.startswith("ocn:"))
async def cancel_ask(call: CallbackQuery) -> None:
    order_id = int(call.data.split(":")[1])
    rows = [[(r, f"ocr:{order_id}:{i}")] for i, r in enumerate(CANCEL_REASONS)]
    rows.append([("⬅️ Ortga", f"ocb:{order_id}")])
    await call.message.edit_reply_markup(reply_markup=ikb(rows))
    await call.answer("Bekor qilish sababini tanlang")


@router.callback_query(F.data.startswith("ocb:"))
async def cancel_back(call: CallbackQuery) -> None:
    order = await db.get_order(int(call.data.split(":")[1]))
    await call.message.edit_reply_markup(reply_markup=order_staff_kb(order))
    await call.answer()


@router.callback_query(F.data.startswith("ocr:"))
async def cancel_confirm(call: CallbackQuery, bot: Bot) -> None:
    _, order_id, idx = call.data.split(":")
    order = await db.get_order(int(order_id))
    if not order or order["status"] not in ACTIVE_STATUSES:
        await call.answer("Bu buyurtmani bekor qilib bo'lmaydi", show_alert=True)
        return
    restocked = await cancel_order(order, call.from_user.id, CANCEL_REASONS[int(idx)])
    await call.answer("Buyurtma bekor qilindi, qoldiq omborga qaytdi")
    await notify_status_change(bot, order["id"])
    await notify_restocked(bot, restocked)


# ---------------- holat rasmi, chat, IMEI ----------------

async def _start_input(call: CallbackQuery, state: FSMContext, kind: State, prompt: str) -> dict | None:
    order = await db.get_order(int(call.data.split(":")[1]))
    if not order:
        await call.answer("Buyurtma topilmadi", show_alert=True)
        return None
    await state.set_state(kind)
    await state.update_data(order_id=order["id"])
    await call.answer()
    await call.message.answer(prompt.format(code=order["code"]), reply_markup=cancel_kb())
    return order


@router.callback_query(F.data.startswith("oph:"))
async def photo_start(call: CallbackQuery, state: FSMContext) -> None:
    await _start_input(call, state, StaffInput.photo,
                       "📸 <b>{code}</b> uchun rasm yuboring (masalan, yig'ilgan buyurtma, qadoq yoki yuk xati).\n"
                       "Rasm izohi (caption) mijozga ham ko'rinadi.")


@router.callback_query(F.data.startswith("och:"))
async def chat_start(call: CallbackQuery, state: FSMContext) -> None:
    current = await db.get_order(int(call.data.split(":")[1]))
    if current and not tickets.chat_open(current):
        await call.answer("Buyurtma yakunlangan — chat yopilgan. Mijoz bilan telefon orqali bog'laning.",
                          show_alert=True)
        return
    order = await _start_input(call, state, StaffInput.chat, "💬 <b>{code}</b> — mijozga xabar yozing (matn yoki rasm):")
    if order:
        await chat.mark_seen(order["id"], "staff")
        history = (await chat.get_messages(order["id"]))[-6:]
        if history:
            lines = [f"{'👤' if m['sender'] == 'customer' else '🏬'} {h(m['text'] or '📷')}" for m in history]
            await call.message.answer("<b>Oxirgi xabarlar:</b>\n" + "\n".join(lines))


@router.callback_query(F.data.startswith("osn:"))
async def serial_start(call: CallbackQuery, state: FSMContext) -> None:
    order = await db.get_order(int(call.data.split(":")[1]))
    items = await db.get_order_items(order["id"]) if order else []
    lines = "\n".join(f"{i}. {h(item_title(it))} × {it['qty']}" + (f" — <code>{h(it['serial'])}</code>" if it["serial"] else "")
                      for i, it in enumerate(items, 1))
    await _start_input(call, state, StaffInput.serial,
                       "🔢 <b>{code}</b> — IMEI yoki seriya raqamlarini har bir pozitsiya uchun alohida qatorda yuboring "
                       "(tartib bo'yicha). Kafolat kartasida ko'rinadi.\n\n" + lines.replace("{", "(").replace("}", ")"))


@router.message(StateFilter(StaffInput), F.text == B.CANCEL)
async def input_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=staff_kb())


async def _state_order(state: FSMContext) -> dict | None:
    return await db.get_order((await state.get_data()).get("order_id") or 0)


@router.message(StaffInput.photo, F.photo)
async def photo_save(message: Message, state: FSMContext, bot: Bot) -> None:
    order = await _state_order(state)
    await state.clear()
    if not order:
        await message.answer("Buyurtma topilmadi.", reply_markup=staff_kb())
        return
    file_id = message.photo[-1].file_id
    path = await save_telegram_photo(bot, file_id, "status")
    media_id = await chat.add_media(order["id"], order["status"], path, file_id, message.caption or "",
                                    message.from_user.id)
    media = next(m for m in await chat.get_media(order["id"]) if m["id"] == media_id)
    await send_status_photo(bot, order, media)
    await message.answer(f"✅ Rasm mijozga yuborildi ({status_label(order['status'], order['order_type'])}).",
                         reply_markup=staff_kb())


@router.message(StaffInput.photo)
async def photo_wrong(message: Message) -> None:
    await message.answer("Iltimos, rasm yuboring yoki «🚫 Bekor qilish» ni bosing.")


@router.message(StaffInput.chat, F.text | F.photo)
async def chat_send(message: Message, state: FSMContext, bot: Bot) -> None:
    order = await _state_order(state)
    await state.clear()
    if not order or not tickets.chat_open(order):
        await message.answer("Buyurtma topilmadi yoki chat yopilgan.", reply_markup=staff_kb())
        return
    path, file_id = "", ""
    if message.photo:
        file_id = message.photo[-1].file_id
        path = await save_telegram_photo(bot, file_id)
    await add_chat_and_relay(bot, order, "staff", message.from_user.id, (message.text or message.caption or ""),
                             path, file_id)
    await message.answer(f"✅ Xabar mijozga yuborildi ({order['code']}).", reply_markup=staff_kb())


@router.message(StaffInput.serial, F.text)
async def serial_save(message: Message, state: FSMContext, bot: Bot) -> None:
    order = await _state_order(state)
    await state.clear()
    if not order:
        await message.answer("Buyurtma topilmadi.", reply_markup=staff_kb())
        return
    items = await db.get_order_items(order["id"])
    values = [x.strip() for x in message.text.splitlines() if x.strip()]
    for it, serial in zip(items, values):
        await db.set_item_serial(it["id"], serial)
    await refresh_staff_messages(bot, order["id"])
    await message.answer(f"✅ {min(len(items), len(values))} ta pozitsiyaga IMEI/seriya saqlandi.",
                         reply_markup=staff_kb())


# ---------------- murojaatlar: qaytarish / muammo xabari ----------------

async def _apply_ticket(bot: Bot, ticket: dict, action: str, by_user: int, note: str = "",
                        restock: bool = True) -> dict:
    restocked = await decide_ticket(ticket, action, by_user, note, restock)
    ticket = await tickets.get(ticket["id"])
    await notify_ticket_decision(bot, ticket)
    if ticket["kind"] == "return" and ticket["status"] == "approved":
        await refresh_staff_messages(bot, ticket["order_id"])
        await notify_restocked(bot, restocked)
    return ticket


@router.callback_query(F.data.startswith("tk:"))
async def ticket_action(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    _, action, tid = call.data.split(":")
    ticket = await tickets.get(int(tid))
    if not ticket:
        await call.answer("Murojaat topilmadi", show_alert=True)
        return
    if ticket["status"] != "open":
        await call.answer("Murojaat allaqachon ko'rib chiqilgan", show_alert=True)
        await rich.edit(call.message, ticket_view(ticket), None)
        return
    if action == "no":
        await state.set_state(StaffInput.reject_note)
        await state.update_data(ticket_id=ticket["id"])
        await call.answer()
        await call.message.answer(f"❌ №{ticket['id']} — rad etish sababini yozing (mijozga yuboriladi):",
                                  reply_markup=cancel_kb())
        return
    mapping = {"ok": ("approve", True), "okn": ("approve", False), "done": ("resolve", True)}
    if action not in mapping:
        await call.answer()
        return
    act, restock = mapping[action]
    ticket = await _apply_ticket(bot, ticket, act, call.from_user.id, restock=restock)
    await rich.edit(call.message, ticket_view(ticket), ticket_staff_kb(ticket))
    await call.answer("Saqlandi, mijozga xabar yuborildi")


@router.message(StaffInput.reject_note, F.text)
async def ticket_reject_note(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.text == B.CANCEL:
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=staff_kb())
        return
    tid = (await state.get_data()).get("ticket_id")
    await state.clear()
    ticket = await tickets.get(tid or 0)
    if not ticket or ticket["status"] != "open":
        await message.answer("Murojaat topilmadi yoki allaqachon ko'rib chiqilgan.", reply_markup=staff_kb())
        return
    await _apply_ticket(bot, ticket, "reject", message.from_user.id, message.text.strip())
    await message.answer(f"❌ №{ticket['id']} rad etildi, mijozga sabab bilan xabar yuborildi.", reply_markup=staff_kb())
