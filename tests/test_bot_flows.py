"""Bot handlerlarini Telegram'ga ulanmasdan (soxta sessiya bilan) tekshirish. Xabarlar rich formatda."""
import datetime as dt
import itertools
import json

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import TelegramMethod
from aiogram.types import CallbackQuery, Chat, Contact, File, Message, PhotoSize, Update, User

from app import chat, db, inventory, products
from app.handlers import setup_routers
from app.notify import notify_new_order, notify_restocked
from app.rich import RichSessionMiddleware
from tests.conftest import variant_of

ADMIN, STAFF, CUSTOMER = 1, 2, 3
_ids = itertools.count(1000)


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls = []
        self.reject_rich = False

    async def make_request(self, bot, method: TelegramMethod, timeout=None):
        name = type(method).__name__
        if self.reject_rich and getattr(method, "rich_message", None) is not None:
            raise TelegramBadRequest(method=method, message="Bad Request: rich messages are not supported")
        self.calls.append(method)
        if name == "GetFile":
            return File(file_id="f", file_unique_id="u", file_path="photos/f.jpg")
        if method.__returning__ is Message or name == "EditMessageText":
            chat_id = getattr(method, "chat_id", 0) or 0
            return Message(message_id=next(_ids), date=dt.datetime.now(), chat=Chat(id=chat_id, type="private"),
                           text=getattr(method, "text", None))
        return True

    async def stream_content(self, *a, **kw):
        yield b"\xff\xd8fakejpeg"

    async def close(self):
        pass

    def texts(self, chat_id=None) -> list[str]:
        out = []
        for c in self.calls:
            if chat_id is not None and getattr(c, "chat_id", None) != chat_id:
                continue
            rich = getattr(c, "rich_message", None)
            if rich is not None:
                out.append(rich.html if rich.html else json.dumps(rich.model_dump(exclude_none=True), ensure_ascii=False))
            else:
                out.append(getattr(c, "text", None) or getattr(c, "caption", None) or "")
        return out

    def markups(self, chat_id=None) -> str:
        return " ".join(str(getattr(c, "reply_markup", "")) for c in self.calls
                        if chat_id is None or getattr(c, "chat_id", None) == chat_id)


@pytest.fixture
async def env(tmp_path, monkeypatch):
    from app.config import config
    monkeypatch.setattr(config, "admin_ids", {ADMIN})
    monkeypatch.setattr(config, "uploads_dir", tmp_path / "uploads")
    from app.handlers import admin, common, shop, staff
    for r in (shop.router, admin.router, staff.router, common.router, common.fallback_router):
        r._parent_router = None
    session = FakeSession()
    bot = Bot("42:TEST", session=session, default=DefaultBotProperties(parse_mode="HTML"))
    bot.session.middleware(RichSessionMiddleware())
    dp = Dispatcher()
    dp.include_router(setup_routers())
    await db.init_db(str(tmp_path / "bot.db"))
    await db.set_setting("mode", "open")
    yield bot, dp, session
    await db.close_db()


def user(uid):
    return User(id=uid, is_bot=False, first_name=f"U{uid}", username=f"u{uid}")


async def send(bot, dp, uid, text=None, **kw):
    msg = Message(message_id=next(_ids), date=dt.datetime.now(), chat=Chat(id=uid, type="private"),
                  from_user=user(uid), text=text, **kw)
    await dp.feed_update(bot, Update(update_id=next(_ids), message=msg))


async def click(bot, dp, uid, data):
    msg = Message(message_id=next(_ids), date=dt.datetime.now(), chat=Chat(id=uid, type="private"), text="x")
    cq = CallbackQuery(id=str(next(_ids)), from_user=user(uid), chat_instance="c", data=data, message=msg)
    await dp.feed_update(bot, Update(update_id=next(_ids), callback_query=cq))


def photo():
    return [PhotoSize(file_id="PHOTO1", file_unique_id="u1", width=10, height=10)]


async def setup_people(bot, dp):
    for uid in (ADMIN, STAFF, CUSTOMER):
        await send(bot, dp, uid, "/start")
        await click(bot, dp, uid, "lang:uz")
    await click(bot, dp, ADMIN, "sadd:staff")
    await send(bot, dp, ADMIN, str(STAFF))
    assert (await db.get_user(STAFF))["role"] == "staff"


async def test_start_rich_and_language(env):
    bot, dp, s = env
    await send(bot, dp, CUSTOMER, "/start")
    assert await db.get_user(CUSTOMER)
    await click(bot, dp, CUSTOMER, "lang:ru")
    assert (await db.get_user(CUSTOMER))["lang"] == "ru"
    rich_calls = [c for c in s.calls if type(c).__name__ == "SendRichMessage"]
    assert rich_calls, "xabarlar rich formatda yuborilishi kerak"
    welcome = next(c for c in rich_calls if "Tech.Zone" in (c.rich_message.html or ""))
    assert '<img src="tg://photo?id=m0"/>' in welcome.rich_message.html  # logo
    assert welcome.rich_message.media[0].id == "m0"
    assert any("автоматически создан" in x for x in s.texts(CUSTOMER))
    s.calls.clear()
    await send(bot, dp, CUSTOMER, "📱 Каталог")
    assert "Смартфоны" in s.markups(CUSTOMER)


async def test_rich_fallback_to_plain(env):
    bot, dp, s = env
    s.reject_rich = True
    await send(bot, dp, CUSTOMER, "/start")
    await click(bot, dp, CUSTOMER, "lang:uz")
    sent = [c for c in s.calls if type(c).__name__ == "SendMessage"]
    assert any("Tech.Zone" in c.text for c in sent)  # rich rad etilsa — oddiy matn


async def test_catalog_product_cart_checkout(env):
    bot, dp, s = env
    await setup_people(bot, dp)
    v = await variant_of("iPhone 15", "Qora", "128 GB")
    pid = v["product_id"]
    s.calls.clear()
    await click(bot, dp, CUSTOMER, "sh:cat:1:0:0")
    assert "iPhone 15" in " ".join(s.texts(CUSTOMER)) and "<table" in s.texts(CUSTOMER)[-1]
    assert "Apple" in s.markups(CUSTOMER)  # brend filtri
    s.calls.clear()
    await click(bot, dp, CUSTOMER, "sh:cat:1:3:0")  # Xiaomi
    assert "Redmi" in s.texts(CUSTOMER)[-1] and "iPhone" not in s.texts(CUSTOMER)[-1]

    # mahsulot: galereya (slaydshou), narx, xarakteristikalar
    s.calls.clear()
    await click(bot, dp, CUSTOMER, f"sh:p:{pid}:0:1")
    html = s.texts(CUSTOMER)[-1]
    assert "<tg-slideshow>" not in html  # bitta rangda bitta rasm
    assert "<img" in html and "10 990 000 so'm" in html and "A16 Bionic" in html
    # rang o'zgartirish -> boshqa variant va rasm
    p = await products.get_product(pid)
    s.calls.clear()
    await click(bot, dp, CUSTOMER, f"sh:po:{pid}:{v['id']}:0:2")  # Pushti
    assert "Pushti, 128 GB" in s.texts(CUSTOMER)[-1]
    pink = next(x for x in p["variants"] if x["vals"] == ["Pushti", "128 GB"])
    assert f"sh:add:{pink['id']}:1" in s.markups(CUSTOMER)

    await click(bot, dp, CUSTOMER, f"sh:add:{v['id']}:2")
    cart = await db.cart_get(CUSTOMER)
    assert cart[0]["qty"] == 2 and cart[0]["variant_name"] == "Qora, 128 GB"

    # rasmiylashtirish: yetkazish -> ism -> telefon -> hudud -> manzil -> izoh -> promo -> to'lov
    await click(bot, dp, CUSTOMER, "sh:co")
    await click(bot, dp, CUSTOMER, "sh:ot:delivery")
    await send(bot, dp, CUSTOMER, "Ali Valiyev")
    await send(bot, dp, CUSTOMER, contact=Contact(phone_number="998901234567", first_name="Ali", user_id=CUSTOMER))
    assert "Toshkent shahri" in s.texts(CUSTOMER)[-1]  # hududlar jadvali
    await click(bot, dp, CUSTOMER, "sh:rg:11")  # Samarqand
    await send(bot, dp, CUSTOMER, "Samarqand, Registon ko'chasi 5")
    await send(bot, dp, CUSTOMER, "➡️ O'tkazib yuborish")
    await send(bot, dp, CUSTOMER, "➡️ O'tkazib yuborish")
    s.calls.clear()
    await click(bot, dp, CUSTOMER, "sh:pay:cash")
    check = s.texts(CUSTOMER)[-1]
    assert "Samarqand" in check and "21 980 000 so'm" in check and "bepul" in check
    await click(bot, dp, CUSTOMER, "sh:ok")
    order = (await db.get_user_orders(CUSTOMER))[0]
    assert order["region_name"] == "Samarqand" and order["total"] == 21_980_000 and order["delivery_eta"] == "2–3 kun"
    assert await db.cart_get(CUSTOMER) == []
    assert (await products.get_variant(v["id"]))["stock"] == v["stock"] - 2
    assert any("YANGI BUYURTMA" in x for x in s.texts(STAFF))
    assert not any("YANGI BUYURTMA" in x for x in s.texts(ADMIN))


async def test_staff_lifecycle_photo_chat_imei(env):
    bot, dp, s = env
    await setup_people(bot, dp)
    v = await variant_of("AirPods Pro 2")
    from app.orders import place_order
    oid = await place_order(CUSTOMER, {"name": "Ali", "phone": "+998901234567", "region_id": 1, "address": "Chilonzor 7",
                                       "payment_method": "cash"}, [{"variant_id": v["id"], "qty": 1}])
    s.calls.clear()
    await notify_new_order(bot, oid)
    assert any("YANGI BUYURTMA" in x for x in s.texts(STAFF))

    for st in ("accepted", "packing"):
        await click(bot, dp, STAFF, f"ost:{oid}:{st}")
    assert any("yig'ilmoqda" in x for x in s.texts(CUSTOMER))

    # holat rasmi
    await click(bot, dp, STAFF, f"oph:{oid}")
    await send(bot, dp, STAFF, photo=photo(), caption="Qadoqlandi")
    media = await chat.get_media(oid)
    assert media[0]["status"] == "packing" and media[0]["path"].startswith("uploads/")
    photo_msg = [c for c in s.calls if getattr(c, "chat_id", None) == CUSTOMER and getattr(c, "rich_message", None)
                 and "<img" in (c.rich_message.html or "")]
    assert photo_msg and "Qadoqlandi" in photo_msg[-1].rich_message.html

    # IMEI
    await click(bot, dp, STAFF, f"osn:{oid}")
    await send(bot, dp, STAFF, "356789012345678")
    assert (await db.get_order_items(oid))[0]["serial"] == "356789012345678"

    # mijoz <-> xodim chati
    order = await db.get_order(oid)
    await click(bot, dp, CUSTOMER, f"sh:ch:{order['code']}")
    await send(bot, dp, CUSTOMER, "Soat nechida kelasiz?")
    assert any("Soat nechida kelasiz?" in x for x in s.texts(STAFF))
    await click(bot, dp, STAFF, f"och:{oid}")
    await send(bot, dp, STAFF, "Soat 15:00 da")
    assert any("Soat 15:00 da" in x for x in s.texts(CUSTOMER))
    assert [m["sender"] for m in await chat.get_messages(oid)] == ["customer", "staff"]

    for st in ("shipping", "delivered"):
        await click(bot, dp, STAFF, f"ost:{oid}:{st}")
    assert any("yo'lda" in x and "0–1 kun" not in x and "bugun–ertaga" in x for x in s.texts(CUSTOMER))
    done = [x for x in s.texts(ADMIN) if "Buyurtma bajarildi" in x]
    assert len(done) == 1 and "3 220 000 so'm" in done[0] and "Yalpi foyda" in done[0]
    # buyurtma tafsiloti: kafolat kartasi IMEI bilan
    s.calls.clear()
    await click(bot, dp, CUSTOMER, f"sh:o:{order['code']}")
    detail = s.texts(CUSTOMER)[-1]
    assert "356789012345678" in detail and "Kafolat" in detail and 'type="checkbox" checked' in detail
    # eski tugma holatni buzmaydi, mijoz xodim callbackini ishlata olmaydi
    await click(bot, dp, STAFF, f"ost:{oid}:packing")
    await click(bot, dp, CUSTOMER, f"ost:{oid}:accepted")
    assert (await db.get_order(oid))["status"] == "delivered"


async def test_cancel_returns_stock_and_back_in_stock(env):
    bot, dp, s = env
    await setup_people(bot, dp)
    v = await variant_of("TUF Gaming F15")
    await inventory.set_stock(v["id"], 1)
    from app.orders import place_order
    oid = await place_order(CUSTOMER, {"name": "Ali", "phone": "+998901234567", "order_type": "pickup",
                                       "payment_method": "cash"}, [{"variant_id": v["id"], "qty": 1}])
    assert (await products.get_variant(v["id"]))["stock"] == 0
    await click(bot, dp, 50, f"sh:al:{v['product_id']}:{v['id']}")  # boshqa mijoz obuna bo'ladi
    assert await inventory.has_alert(50, v["id"])
    s.calls.clear()
    await click(bot, dp, STAFF, f"ocr:{oid}:2")
    assert (await db.get_order(oid))["status"] == "cancelled"
    assert (await products.get_variant(v["id"]))["stock"] == 1
    assert any("Sotuvga chiqdi" in x for x in s.texts(50))
    assert not await inventory.has_alert(50, v["id"])
    await notify_restocked(bot, [v["id"]])  # takroriy xabar yo'q
    assert sum("Sotuvga chiqdi" in x for x in s.texts(50)) == 1


async def test_search_and_favorites(env):
    bot, dp, s = env
    await setup_people(bot, dp)
    await send(bot, dp, CUSTOMER, "🔍 Qidiruv")
    s.calls.clear()
    await send(bot, dp, CUSTOMER, "galaxy")
    found = s.texts(CUSTOMER)[-1]
    assert "Galaxy S24 Ultra" in found and "Galaxy A55" in found and "iPhone" not in found
    v = await variant_of("Xiaomi 14T", "Qora", "512 GB")
    await click(bot, dp, CUSTOMER, f"sh:fv:{v['product_id']}:{v['id']}")
    assert await db.get_favorites(CUSTOMER) == [v["product_id"]]
    s.calls.clear()
    await send(bot, dp, CUSTOMER, "❤️ Sevimlilar")
    assert "Xiaomi 14T" in s.texts(CUSTOMER)[-1]


async def test_manager_panel_and_stats(env):
    bot, dp, s = env
    await setup_people(bot, dp)
    s.calls.clear()
    await send(bot, dp, ADMIN, "👑 Menejer paneli")
    assert "menejer paneli" in s.texts(ADMIN)[-1] and "<table" in s.texts(ADMIN)[-1]
    await send(bot, dp, ADMIN, "📊 Statistika")
    assert "Yalpi foyda" in s.texts(ADMIN)[-1]
    await send(bot, dp, ADMIN, "🏷 Ombor")
    assert "Anker PowerCore 20000" in s.texts(ADMIN)[-1]
    await send(bot, dp, ADMIN, "⚙️ Do'kon holati")
    await click(bot, dp, ADMIN, "set:mode")
    assert await db.get_setting("mode") == "closed"
    # mijoz endi buyurtma bera olmaydi
    v = await variant_of("AirPods Pro 2")
    await click(bot, dp, CUSTOMER, f"sh:add:{v['id']}:1")
    s.calls.clear()
    await click(bot, dp, CUSTOMER, "sh:co")
    assert any("qabul qilinmayapti" in str(getattr(c, "text", "")) for c in s.calls)
    # oddiy mijoz menejer panelini ocha olmaydi
    s.calls.clear()
    await send(bot, dp, CUSTOMER, "/admin")
    assert not any("menejer paneli" in x for x in s.texts(CUSTOMER))
