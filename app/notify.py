import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup

from . import chat, db, inventory, products, rich
from .brand import shop_name
from .catalog import variant_label
from .config import config
from .i18n import status_text, t
from .keyboards import order_staff_kb, order_track_kb, rating_kb, webapp_ready, webapp_url
from .order_card import edit_order_card, send_order_card
from .rich import Rich
from .roles import lang_of
from .utils import h, money, now, status_label

log = logging.getLogger(__name__)
SAFE = (TelegramForbiddenError, TelegramBadRequest)


async def manager_ids() -> set[int]:
    return set(config.admin_ids) | {u["id"] for u in await db.get_staff() if u["role"] == "manager"}


async def staff_recipients() -> list[int]:
    """Buyurtma kartalari (holat tugmalari bilan) faqat xodimlarga boradi.
    Menejerlarga bormaydi — ular faqat bajarilgan buyurtma haqida hisobot oladi.
    Bitta ham xodim bo'lmasa, buyurtma yo'qolmasligi uchun menejerlarga yuboriladi."""
    managers = await manager_ids()
    ids = {u["id"] for u in await db.get_staff() if u["role"] == "staff"} - managers
    return sorted(ids or managers)


async def _send_many(bot: Bot, chat_ids, text: str, **kw) -> None:
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, text, **kw)
        except SAFE:
            pass


async def notify_managers_done(bot: Bot, order: dict) -> None:
    """Buyurtma bajarilganda menejerlarga qisqa hisobot: summa, foyda va bugungi tushum."""
    since = now().strftime("%Y-%m-%d 00:00:00")
    row = await db.fetchone(
        "SELECT COUNT(*) c, COALESCE(SUM(total), 0) s FROM orders WHERE status = 'delivered' AND created_at >= ?",
        since,
    )
    cost = await db.scalar("SELECT COALESCE(SUM(qty * cost), 0) FROM order_items WHERE order_id = ?", order["id"])
    profit = order["subtotal"] - order["discount"] - cost
    otype = order.get("order_type") or "delivery"
    text = (
        f"✅ <b>Buyurtma bajarildi</b> — <code>{order['code']}</code>\n"
        f"{status_label('delivered', otype)}\n\n"
        f"💰 Tushum: <b>{money(order['total'])}</b>"
        + (f" (chegirma {money(order['discount'])})" if order.get("discount") else "")
        + (f"\n📈 Yalpi foyda: <b>{money(profit)}</b>" if cost else "")
        + (f"\n👷 Xodim: {h(order['staff_name'])}" if order.get("staff_name") else "")
        + f"\n\n📊 Bugun: <b>{row['c']}</b> ta buyurtma, jami <b>{money(row['s'])}</b>"
    )
    await _send_many(bot, await manager_ids(), text)


async def notify_low_stock(bot: Bot, items: list[dict]) -> None:
    low = int(await db.get_setting("low_stock") or 3)
    lines = []
    for it in items:
        v = await products.get_variant(it["variant_id"])
        if v and v["stock"] <= low:
            name = it["name"] + (f" ({it['variant']})" if it.get("variant") else "")
            lines.append(f"• {h(name)} — <b>{v['stock']}</b> ta" + (" ⛔️" if v["stock"] <= 0 else ""))
    if lines:
        await _send_many(bot, await manager_ids(), "⚠️ <b>Omborda kam qoldi</b>\n\n" + "\n".join(lines)
                         + "\n\nKirim qilish: Web panel → Ombor → Kirim")


async def notify_new_order(bot: Bot, order_id: int, notify_customer: bool = True) -> None:
    order = await db.get_order(order_id)
    items = await db.get_order_items(order_id)
    kb = order_staff_kb(order)
    for chat_id in await staff_recipients():
        try:
            msg = await send_order_card(bot, chat_id, order, items, "🔔 YANGI BUYURTMA", kb)
            await db.save_order_message(order_id, chat_id, msg.message_id)
        except SAFE as e:
            log.warning("Xodimga yuborib bo'lmadi %s: %s", chat_id, e)
    await notify_low_stock(bot, items)
    if order["payment_method"] == "card":
        await send_card_instructions(bot, order)

    if not notify_customer:  # bot ichidagi savatdan berilganda mijozga tasdiq allaqachon ko'rsatilgan
        return
    lang = await lang_of(order["user_id"])
    try:
        await bot.send_message(order["user_id"], t("sent_new", lang, code=order["code"]),
                               reply_markup=order_track_kb(order["code"], lang))
    except SAFE as e:
        log.warning("Mijozga yuborib bo'lmadi %s: %s", order["user_id"], e)


async def refresh_staff_messages(bot: Bot, order_id: int) -> None:
    """Holat o'zgarganda barcha xodimlardagi kartani yangilaydi."""
    order = await db.get_order(order_id)
    items = await db.get_order_items(order_id)
    kb: InlineKeyboardMarkup | None = order_staff_kb(order)
    for m in await db.get_order_messages(order_id):
        try:
            await edit_order_card(bot, m["chat_id"], m["message_id"], order, items, kb)
        except TelegramBadRequest as e:
            if "not modified" not in str(e):
                log.debug("Edit failed: %s", e)
        except TelegramForbiddenError:
            pass


async def delete_order(bot: Bot | None, order: dict) -> None:
    """Buyurtmani o'chiradi (faol bo'lsa qoldiq qaytariladi) va xodimlardagi kartani «o'chirildi» qiladi."""
    if order["status"] != "cancelled":
        async with inventory.STOCK_LOCK:
            await inventory.release(order["id"], order["code"], None)
    messages = await db.delete_order(order["id"])
    if not bot:
        return
    text = f"🗑 <s>Buyurtma {order['code']}</s>\n\nMenejer tomonidan o'chirildi."
    from aiogram.types import InputRichBlockParagraph, InputRichMessage, RichTextStrikethrough

    rich = InputRichMessage(blocks=[InputRichBlockParagraph(text=[
        "🗑 ", RichTextStrikethrough(text=f"Buyurtma {order['code']}"), " — menejer tomonidan o'chirildi."])])
    for m in messages:
        for kwargs in ({"rich_message": rich}, {"text": text}):  # rich kartani rich bilan, eskisini matn bilan
            try:
                await bot.edit_message_text(chat_id=m["chat_id"], message_id=m["message_id"], reply_markup=None,
                                            **kwargs)
                break
            except TelegramBadRequest:
                continue
            except TelegramForbiddenError:
                break


def customer_status_text(order: dict, lang: str, shop_address: str = "", eta: str = "") -> str | None:
    status, otype = order["status"], order.get("order_type") or "delivery"
    if status not in ("accepted", "packing", "shipping", "delivered", "cancelled"):
        return None
    key = f"st_{status}"
    if otype == "pickup" and status in ("shipping", "delivered"):
        key += "_pickup"
    reason = ""
    if status == "cancelled" and order.get("cancel_reason"):
        reason = "\n" + t("reason", lang, reason=h(order["cancel_reason"]))
    address = f"\n📍 {h(shop_address)}" if shop_address else ""
    eta_line = "\n" + t("eta_line", lang, eta=eta) if eta and status == "shipping" and otype == "delivery" else ""
    return t(key, lang, code=order["code"], reason=reason, address=address, eta=eta_line)


async def order_eta(order: dict, lang: str) -> str:
    """Hudud bo'yicha yetkazish muddati mijoz tilida (hudud o'chirilgan bo'lsa saqlangan matn)."""
    from . import regions

    region = await regions.get_region(order["region_id"]) if order.get("region_id") else None
    return regions.eta_text(region, lang) if region else order.get("delivery_eta") or ""


async def notify_status_change(bot: Bot, order_id: int) -> None:
    order = await db.get_order(order_id)
    await refresh_staff_messages(bot, order_id)
    if order["status"] == "delivered":
        await notify_managers_done(bot, order)
    lang = await lang_of(order["user_id"])
    text = customer_status_text(order, lang, await db.get_setting("shop_address"), await order_eta(order, lang))
    if not text:
        return
    try:
        await bot.send_message(order["user_id"], text, reply_markup=order_track_kb(order["code"], lang))
        if order["status"] == "shipping" and (order.get("order_type") or "delivery") == "pickup":
            await send_pickup_location(bot, order["user_id"], lang)
        if order["status"] == "delivered" and not await db.get_review(order_id):
            await bot.send_message(order["user_id"], t("rate_ask", lang), reply_markup=rating_kb(order_id))
    except SAFE as e:
        log.warning("Mijozga holat yuborilmadi %s: %s", order["user_id"], e)


async def send_pickup_location(bot: Bot, chat_id: int, lang: str) -> None:
    """Olib ketish buyurtmasi tayyor bo'lganda do'kon joylashuvini Telegram lokatsiyasi sifatida yuboradi."""
    from .geo import shop_location

    s = await db.get_settings()
    url = (s.get("shop_map_url") or "").strip()
    address = (s.get("shop_address") or "").strip()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("map_btn", lang), url=url)]]) if url else None
    coords = await shop_location()
    try:
        if coords:
            await bot.send_venue(chat_id, coords[0], coords[1], title=shop_name(),
                                 address=address or t("pickup_shop", lang), reply_markup=kb)
        elif url or address:
            await bot.send_message(chat_id, t("pickup_location", lang, address=f"\n{h(address)}" if address else ""),
                                   reply_markup=kb, disable_web_page_preview=True)
    except SAFE as e:
        log.warning("Lokatsiya yuborilmadi %s: %s", chat_id, e)


async def notify_review(bot: Bot, order_id: int) -> None:
    """Yangi baho haqida menejerlarga xabar (past baholar ajratib ko'rsatiladi)."""
    review = await db.get_review(order_id)
    order = await db.get_order(order_id)
    if not review or not order:
        return
    head = "⚠️ <b>PAST BAHO!</b>" if review["rating"] <= 3 else "⭐ <b>Yangi baho</b>"
    text = (
        f"{head}\n\n{'⭐' * review['rating']}{'☆' * (5 - review['rating'])} ({review['rating']}/5)\n"
        f"Buyurtma: <code>{order['code']}</code>\n👤 {h(order['customer_name'])} · {h(order['phone'])}"
    )
    if review["comment"]:
        text += f"\n💬 {h(review['comment'])}"
    await _send_many(bot, await manager_ids(), text)


# ---------------- kelganda xabar berish ----------------

async def notify_restocked(bot: Bot, variant_ids: list[int]) -> None:
    """Qayta sotuvga chiqqan variantlar uchun obuna bo'lgan mijozlarga xabar."""
    for vid in variant_ids:
        v = await products.get_variant(vid)
        p = await products.get_product(v["product_id"]) if v else None
        if not p or not products.sellable(p, v):
            continue
        for uid in await inventory.pop_alerts(vid):
            lang = await lang_of(uid)
            label = variant_label(p, v, lang)
            item = f"<b>{h(p['name'])}</b>" + (f" ({h(label)})" if label else "")
            rows = [[InlineKeyboardButton(text=t("view_btn", lang), callback_data=f"sh:p:{p['id']}:{vid}:1")]]
            if webapp_ready():
                from aiogram.types import WebAppInfo

                rows.append([InlineKeyboardButton(text=t("mini_inline", lang),
                                                  web_app=WebAppInfo(url=webapp_url(f"p{p['id']}")))])
            image = next((i["path"] for i in p["images"] if i["color"] and i["color"] in v["vals"]),
                         p["images"][0]["path"] if p["images"] else "")
            view = Rich().img(image).p(t("back_in_stock", lang, item=item))
            try:
                await rich.send(bot, uid, view, InlineKeyboardMarkup(inline_keyboard=rows))
            except SAFE:
                pass


# ---------------- buyurtma chati va holat rasmlari ----------------

def _chat_staff_kb(order: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="↩️ Javob berish", callback_data=f"och:{order['id']}"),
        InlineKeyboardButton(text="🧾 Buyurtma", callback_data=f"ov:{order['id']}"),
    ]])


async def chat_recipients(order: dict) -> list[int]:
    """Mijoz xabari buyurtmaga mas'ul xodimga, u bo'lmasa barcha xodimlarga boradi."""
    if order.get("staff_id"):
        return [order["staff_id"]]
    return await staff_recipients()


async def relay_customer_message(bot: Bot, order: dict, text: str = "", photo_path: str = "") -> None:
    view = Rich().h(f"💬 Mijoz xabari · <code>{order['code']}</code>", 3)
    view.p(f"👤 {h(order['customer_name'])} · {h(order['phone'])}")
    if photo_path:
        view.img(photo_path)
    if text:
        view.quote(h(text))
    kb = _chat_staff_kb(order)
    for chat_id in await chat_recipients(order):
        try:
            await rich.send(bot, chat_id, view, kb)
        except SAFE:
            pass


async def relay_staff_message(bot: Bot, order: dict, text: str = "", photo_path: str = "") -> None:
    lang = await lang_of(order["user_id"])
    view = Rich()
    if photo_path:
        view.img(photo_path)
    view.p(t("chat_from_shop", lang, code=order["code"], text=h(text) if text else "📷"))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("chat_reply_btn", lang), callback_data=f"sh:ch:{order['code']}"),
        InlineKeyboardButton(text=t("track_btn", lang), callback_data=f"sh:o:{order['code']}"),
    ]])
    try:
        await rich.send(bot, order["user_id"], view, kb)
    except SAFE as e:
        log.warning("Mijozga chat xabari yuborilmadi %s: %s", order["user_id"], e)


async def send_status_photo(bot: Bot, order: dict, media: dict) -> None:
    """Xodim yuklagan holat rasmini mijozga rich xabar (rasm + izoh) qilib yuboradi."""
    lang = await lang_of(order["user_id"])
    if not media.get("path"):
        return
    caption = h(media["caption"]) if media.get("caption") else ""
    view = Rich().img(media["path"], caption).p(
        t("status_photo", lang, code=order["code"], status=status_text(media["status"], order["order_type"], lang)))
    try:
        await rich.send(bot, order["user_id"], view, order_track_kb(order["code"], lang))
    except SAFE as e:
        log.warning("Holat rasmi yuborilmadi %s: %s", order["user_id"], e)


async def save_telegram_photo(bot: Bot, file_id: str, prefix: str = "chat") -> str:
    """Telegram rasmini uploads/ ga saqlaydi (Mini App va admin panelda ko'rinishi uchun)."""
    import uuid

    config.uploads_dir.mkdir(parents=True, exist_ok=True)
    name = f"{prefix}_{uuid.uuid4().hex[:12]}.jpg"
    try:
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, config.uploads_dir / name)
    except Exception as e:  # noqa: BLE001
        log.warning("Rasmni saqlab bo'lmadi: %s", e)
        return ""
    rich.PHOTO_CACHE[f"uploads/{name}"] = file_id  # rich xabarlarda qayta yuklamasdan ishlatiladi
    return f"uploads/{name}"


async def add_chat_and_relay(bot: Bot | None, order: dict, sender: str, user_id: int | None,
                             text: str = "", photo_path: str = "", file_id: str = "") -> None:
    await chat.add_message(order["id"], sender, user_id, text, photo_path, file_id)
    if not bot:
        return
    if sender == "customer":
        await relay_customer_message(bot, order, text, photo_path)
    else:
        await relay_staff_message(bot, order, text, photo_path)


# ---------------- rassilka ----------------

async def send_post(bot: Bot, chat_id: int, from_chat_id: int, message_ids: list[int],
                    mode: str = "copy", reply_markup: InlineKeyboardMarkup | None = None) -> None:
    """Bitta qabul qiluvchiga post yuboradi: nusxa (copy) yoki forward, albomlar bilan."""
    if mode == "forward":
        if len(message_ids) > 1:
            await bot.forward_messages(chat_id, from_chat_id, message_ids)
        else:
            await bot.forward_message(chat_id, from_chat_id, message_ids[0])
    elif len(message_ids) > 1:
        # albom: Telegram albomga inline tugma biriktirishga ruxsat bermaydi
        await bot.copy_messages(chat_id, from_chat_id, message_ids)
    else:
        await bot.copy_message(chat_id, from_chat_id, message_ids[0], reply_markup=reply_markup)


async def broadcast(bot: Bot, from_chat_id: int, message_ids: list[int], mode: str = "copy",
                    reply_markup: InlineKeyboardMarkup | None = None, progress_cb=None) -> tuple[int, int]:
    """Postni barcha foydalanuvchilarga yuboradi. (yuborildi, xato) qaytaradi."""
    ok = fail = 0
    user_ids = await db.all_user_ids()
    for i, uid in enumerate(user_ids, 1):
        for attempt in range(2):
            try:
                await send_post(bot, uid, from_chat_id, message_ids, mode, reply_markup)
                ok += 1
            except TelegramRetryAfter as e:  # flood limit — kutib qayta urinamiz
                if attempt == 0:
                    await asyncio.sleep(e.retry_after + 1)
                    continue
                fail += 1
            except TelegramForbiddenError:
                await db.set_blocked(uid, True)
                fail += 1
            except TelegramBadRequest:
                fail += 1
            except Exception as e:
                log.warning("Broadcast error %s: %s", uid, e)
                fail += 1
            break
        await asyncio.sleep(0.05)  # Telegram limiti: ~30 xabar/soniya
        if progress_cb and i % 50 == 0:
            await progress_cb(i, len(user_ids))
    return ok, fail


# ---------------- murojaatlar (qaytarish / muammo xabari) ----------------

def ticket_staff_kb(ticket: dict) -> InlineKeyboardMarkup | None:
    if ticket["status"] != "open":
        return None
    tid = ticket["id"]
    if ticket["kind"] == "return":
        rows = [[InlineKeyboardButton(text="✅ Qaytarish (omborga)", callback_data=f"tk:ok:{tid}")],
                [InlineKeyboardButton(text="✅ Qaytarish (nuqsonli, omborsiz)", callback_data=f"tk:okn:{tid}")],
                [InlineKeyboardButton(text="❌ Rad etish", callback_data=f"tk:no:{tid}")]]
    else:
        rows = [[InlineKeyboardButton(text="✅ Hal qilindi", callback_data=f"tk:done:{tid}")]]
    rows.append([InlineKeyboardButton(text="🧾 Buyurtma", callback_data=f"ov:{ticket['order_id']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ticket_view(ticket: dict) -> Rich:
    from .utils import phone_fmt

    kind = "↩️ QAYTARISH ARIZASI" if ticket["kind"] == "return" else "⚠️ MUAMMO XABARI"
    view = Rich().h(f"{kind} · №{ticket['id']}", 3)
    view.table([["🧾 Buyurtma", f"<code>{ticket['code']}</code> · {money(ticket['total'])}"],
                ["👤 Mijoz", h(ticket["customer_name"])],
                ["📞 Telefon", h(phone_fmt(ticket["phone"]))],
                ["🕒 Vaqt", ticket["created_at"][:16]]], striped=False)
    view.quote(h(ticket["reason"]))
    view.gallery(ticket["photos"])
    if ticket["status"] != "open":
        view.footer(f"Holat: {ticket['status']}" + (f" · {h(ticket['note'])}" if ticket.get("note") else ""))
    else:
        view.footer("Mijoz bilan telefon orqali bog'laning, so'ng qaror qabul qiling.")
    return view


async def notify_ticket_new(bot: Bot, ticket_id: int) -> None:
    from . import tickets

    ticket = await tickets.get(ticket_id)
    if not ticket:
        return
    view, kb = ticket_view(ticket), ticket_staff_kb(ticket)
    for chat_id in sorted(set(await manager_ids()) | set(await staff_recipients())):
        try:
            await rich.send(bot, chat_id, view, kb)
        except SAFE:
            pass


async def notify_ticket_decision(bot: Bot, ticket: dict) -> None:
    lang = await lang_of(ticket["user_id"])
    note = "\n" + t("reason", lang, reason=h(ticket["note"])) if ticket.get("note") else ""
    key = {"approved": "return_approved", "rejected": "return_rejected", "resolved": "issue_resolved"}.get(ticket["status"])
    if not key:
        return
    try:
        await bot.send_message(ticket["user_id"], t(key, lang, code=ticket["code"], note=note),
                               reply_markup=order_track_kb(ticket["code"], lang))
    except SAFE as e:
        log.warning("Murojaat qarori yuborilmadi %s: %s", ticket["user_id"], e)


# ---------------- karta orqali to'lov (chek) ----------------

def receipt_customer_kb(order: dict, lang: str, number: str = "") -> InlineKeyboardMarkup:
    rows = []
    if number:
        rows.append([InlineKeyboardButton(text=t("copy_card_btn", lang), copy_text=CopyTextButton(text=number))])
    rows.append([InlineKeyboardButton(text=t("receipt_btn", lang), callback_data=f"sh:rc:{order['code']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def send_card_instructions(bot: Bot, order: dict, prefix: str = "") -> None:
    """Mijozga karta raqami (nusxalash tugmasi bilan) va «Chekni yuborish» tugmasi."""
    from . import payments

    card = payments.card_info(await db.get_settings())
    if not card or not payments.can_upload(order):
        return
    lang = await lang_of(order["user_id"])
    number = payments.format_number(card["number"])
    holder = " · ".join(x for x in (card["holder"], card["bank"]) if x)
    text = prefix + t("card_pay_info", lang, code=order["code"], total=money(order["total"]),
                      number=h(number), holder=h(holder))
    try:
        await bot.send_message(order["user_id"], text,
                               reply_markup=receipt_customer_kb(order, lang, number.replace(" ", "")))
    except SAFE as e:
        log.warning("Karta ma'lumoti yuborilmadi %s: %s", order["user_id"], e)


def receipt_staff_kb(order: dict) -> InlineKeyboardMarkup | None:
    if order.get("pay_status") != "review":
        return None
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ To'lovni tasdiqlash", callback_data=f"py:ok:{order['id']}"),
         InlineKeyboardButton(text="❌ Rad etish", callback_data=f"py:no:{order['id']}")],
        [InlineKeyboardButton(text="💵 Naqdga o'tkazish", callback_data=f"pcash:{order['id']}"),
         InlineKeyboardButton(text="🧾 Buyurtma", callback_data=f"ov:{order['id']}")]])


def receipt_view(order: dict) -> Rich:
    from .payments import PAY_LABELS
    from .utils import phone_fmt

    view = Rich().h("🧾 TO'LOV CHEKI", 3)
    view.table([["Buyurtma", f"<code>{order['code']}</code>"],
                ["Summa", f"<b>{money(order['total'])}</b>"],
                ["Mijoz", h(order["customer_name"])],
                ["Telefon", h(phone_fmt(order["phone"]))],
                ["Holat", PAY_LABELS.get(order.get("pay_status") or "", "—")]], striped=False)
    if order.get("pay_receipt"):
        view.img(order["pay_receipt"])
    if order.get("pay_status") == "review":
        view.footer("Summani hisobingizda tekshirib, tasdiqlang yoki sababini yozib rad eting.")
    elif order.get("pay_note"):
        view.footer("Sabab: " + h(order["pay_note"]))
    return view


async def notify_receipt(bot: Bot, order: dict) -> None:
    """Yangi chek — menejerlarga (rasm va tasdiqlash tugmalari bilan)."""
    view, kb = receipt_view(order), receipt_staff_kb(order)
    for chat_id in sorted(await manager_ids()):
        try:
            await rich.send(bot, chat_id, view, kb)
        except SAFE as e:
            log.warning("Chek menejerga yuborilmadi %s: %s", chat_id, e)


async def notify_switched_cash(bot: Bot, order: dict) -> None:
    lang = await lang_of(order["user_id"])
    try:
        await bot.send_message(order["user_id"], t("pay_switched_cash", lang, code=order["code"]),
                               reply_markup=order_track_kb(order["code"], lang))
    except SAFE as e:
        log.warning("Naqdga o'tkazish xabari yuborilmadi %s: %s", order["user_id"], e)
    await refresh_staff_messages(bot, order["id"])


async def notify_pay_decision(bot: Bot, order: dict, accepted: bool = False) -> None:
    lang = await lang_of(order["user_id"])
    try:
        if order["pay_status"] == "paid":
            await bot.send_message(order["user_id"], t("pay_paid_msg", lang, code=order["code"]),
                                   reply_markup=order_track_kb(order["code"], lang))
        elif order["pay_status"] == "rejected":
            await bot.send_message(order["user_id"],
                                   t("pay_rejected_msg", lang, code=order["code"], note=h(order["pay_note"])),
                                   reply_markup=receipt_customer_kb(order, lang))
    except SAFE as e:
        log.warning("To'lov qarori yuborilmadi %s: %s", order["user_id"], e)
    if accepted:  # to'lov tasdiqlanishi bilan buyurtma avtomatik qabul qilindi
        await notify_status_change(bot, order["id"])
    else:
        await refresh_staff_messages(bot, order["id"])
