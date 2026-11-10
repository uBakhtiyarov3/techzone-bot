"""Bot ko'rinishi: rangli tugmalar, rasm-kartalar, holat xabarlaridagi karta va effekt."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from PIL import Image

from app import bot_ui, cards, db
from app.config import config
from app.orders import place_order
from tests.conftest import variant_of
from tests.test_bot_flows import CUSTOMER, STAFF, click, env, setup_people  # noqa: F401


def test_button_styles():
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="a", callback_data="sh:ok"), InlineKeyboardButton(text="b", callback_data="sh:no"),
        InlineKeyboardButton(text="c", callback_data="sh:add:5:1"), InlineKeyboardButton(text="d", callback_data="sh:cats"),
        InlineKeyboardButton(text="e", web_app=WebAppInfo(url="https://x.uz")),
        InlineKeyboardButton(text="f", callback_data="sh:no", style="primary")]])
    bot_ui.style_markup(kb)
    assert [b.style for b in kb.inline_keyboard[0]] == ["success", "danger", "primary", None, "primary", "primary"]


def test_cards_render(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "uploads_dir", tmp_path)
    brand = {"name": "Do'kon", "mark": "brand/mark.png", "color": "#1E6BFF"}
    data = {"brand": brand, "code": "GH-1", "caption": "Статус заказа", "title": "Доставляется", "subtitle": "Ташкент",
            "total": "1 000 сум", "steps": ["a", "b", "c", "d", "e"], "reached": 3, "state": "active",
            "images": ["img/demo/airpods.jpg", "yoq.jpg"]}
    path = cards.render_sync("order", data)
    assert path.startswith("uploads/cards/order_") and Image.open(tmp_path / path.removeprefix("uploads/")).size == (1280, 640)
    assert cards.render_sync("order", data) == path  # kesh
    assert cards.render_sync("order", {**data, "reached": None, "state": "cancelled", "note": "Sabab"}) != path
    cover = cards.render_sync("cover", {"brand": brand, "caption": "Katalog", "title": "Juda uzun kategoriya nomi " * 3,
                                        "subtitle": "6 ta", "images": []})
    assert Image.open(tmp_path / cover.removeprefix("uploads/")).size == (1280, 520)


async def test_status_message_has_card_and_effect(env):
    bot, dp, s = env
    await setup_people(bot, dp)
    v = await variant_of("AirPods Pro 2")
    oid = await place_order(CUSTOMER, {"name": "Ali", "phone": "+998901234567", "order_type": "pickup",
                                       "payment_method": "cash"}, [{"variant_id": v["id"], "qty": 1}])
    s.calls.clear()
    await click(bot, dp, STAFF, f"ost:{oid}:accepted")
    msg = next(c for c in s.calls if getattr(c, "chat_id", 0) == CUSTOMER and getattr(c, "rich_message", None))
    assert "<img" in msg.rich_message.html and msg.rich_message.media and not msg.message_effect_id
    for st in ("packing", "shipping"):
        await db.set_order_status(oid, st, STAFF)
    s.calls.clear()
    await click(bot, dp, STAFF, f"ost:{oid}:delivered")
    done = next(c for c in s.calls if getattr(c, "chat_id", 0) == CUSTOMER and getattr(c, "rich_message", None))
    assert done.message_effect_id == bot_ui.FX_PARTY
    # katalogda muqova rasmi, tanlangan variant ko'k tugma
    s.calls.clear()
    await click(bot, dp, CUSTOMER, "sh:cats")
    assert "<img" in s.texts(CUSTOMER)[-1]
    iphone = await variant_of("iPhone 15", "Qora", "128 GB")
    s.calls.clear()
    await click(bot, dp, CUSTOMER, f"sh:p:{iphone['product_id']}:{iphone['id']}:1")
    kb = next(c.reply_markup for c in reversed(s.calls) if getattr(c, "reply_markup", None))
    styles = {b.text: b.style for row in kb.inline_keyboard for b in row}
    assert styles["Qora"] == "primary" and styles["Ko'k"] is None
    assert any(st == "primary" for text, st in styles.items() if "Savatga" in text)


async def test_live_tracker_widget(env):
    """Yoqilganda: buyurtma — widget xabar, holat o'zgarishi — widget ma'lumoti yangilanadi (rasmsiz xabar)."""
    import json

    from app import widgets
    from app.notify import notify_status_change
    bot, dp, s = env
    await setup_people(bot, dp)
    v = await variant_of("AirPods Pro 2")
    oid = await place_order(CUSTOMER, {"name": "Ali", "phone": "+998901234567", "region_id": 1, "address": "Chilonzor 7",
                                       "payment_method": "cash"}, [{"variant_id": v["id"], "qty": 1}])
    order = await db.get_order(oid)
    assert not await widgets.send_tracker(bot, order, "uz", "", "x")  # o'chiq — widget yuborilmaydi
    await db.set_setting("live_tracker", "1")
    s.calls.clear()
    assert await widgets.send_tracker(bot, order, "uz", "bugun", "Buyurtma berildi")
    sent = next(c for c in s.calls if type(c).__name__ == "SendWidget")
    data = json.loads(sent.chat_data)
    assert data["code"] == order["code"] and data["i"] == 0 and len(data["steps"]) == 5 and len(sent.chat_data.encode()) <= 1024
    assert (await db.get_order(oid))["widget_msg_id"]
    await db.set_order_status(oid, "accepted", STAFF)
    s.calls.clear()
    await notify_status_change(bot, oid)
    edit = next(c for c in s.calls if type(c).__name__ == "EditMessageWidgetData")
    assert json.loads(edit.chat_data)["i"] == 1
    note = next(c for c in s.calls if getattr(c, "chat_id", 0) == CUSTOMER and getattr(c, "rich_message", None))
    assert "<img" not in note.rich_message.html
