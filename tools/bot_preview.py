"""Bot xabarlarini Telegramsiz ko'rish: ssenariyni soxta sessiya bilan o'tkazib, ekranlarni HTML ga chiqaradi.

    python tools/bot_preview.py [chiqish_papkasi]        # → preview.html (+ rasmlar)

Telegram rich xabarlarining taxminiy ko'rinishi (haqiqiy mijozdagi ko'rinish biroz farq qilishi mumkin).
Dizaynni tez tekshirish uchun: HTML ni brauzerda oching yoki Playwright bilan skrinshot oling.
"""
import asyncio
import base64
import datetime as dt
import html
import itertools
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("BOT_TOKEN", "42:PREVIEW")
os.environ.setdefault("ADMIN_IDS", "1")
os.environ.setdefault("WEBAPP_URL", "http://localhost")  # https emas — rasmlar fayl sifatida yuboriladi
os.environ.setdefault("DEBUG", "0")

from aiogram import Bot, Dispatcher  # noqa: E402
from aiogram.client.default import DefaultBotProperties  # noqa: E402
from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.methods import TelegramMethod  # noqa: E402
from aiogram.types import (  # noqa: E402
    CallbackQuery, Chat, Contact, File, InlineKeyboardMarkup, Message, PhotoSize, ReplyKeyboardMarkup, Update, User,
)

from app import db  # noqa: E402
from app.config import config  # noqa: E402
from app.handlers import setup_routers  # noqa: E402
from app.rich import RichSessionMiddleware  # noqa: E402

_ids = itertools.count(1000)
ADMIN, STAFF, CUSTOMER = 1, 2, 3


class PreviewSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls: list[TelegramMethod] = []

    async def make_request(self, bot, method: TelegramMethod, timeout=None):
        self.calls.append(method)
        name = type(method).__name__
        if name == "GetFile":
            return File(file_id="f", file_unique_id="u", file_path="photos/f.jpg")
        if method.__returning__ is Message or name == "EditMessageText":
            return Message(message_id=next(_ids), date=dt.datetime.now(),
                           chat=Chat(id=getattr(method, "chat_id", 0) or 0, type="private"),
                           text=getattr(method, "text", None))
        return True

    async def stream_content(self, *a, **kw):
        yield b"\xff\xd8fakejpeg"

    async def close(self):
        pass


def _user(uid: int) -> User:
    return User(id=uid, is_bot=False, first_name={ADMIN: "Admin", STAFF: "Sardor", CUSTOMER: "Umidjon"}.get(uid, "U"),
                username=f"u{uid}")


async def send(bot, dp, uid, text=None, **kw):
    msg = Message(message_id=next(_ids), date=dt.datetime.now(), chat=Chat(id=uid, type="private"),
                  from_user=_user(uid), text=text, **kw)
    await dp.feed_update(bot, Update(update_id=next(_ids), message=msg))


async def click(bot, dp, uid, data):
    msg = Message(message_id=next(_ids), date=dt.datetime.now(), chat=Chat(id=uid, type="private"), text="x")
    cq = CallbackQuery(id=str(next(_ids)), from_user=_user(uid), chat_instance="c", data=data, message=msg)
    await dp.feed_update(bot, Update(update_id=next(_ids), callback_query=cq))


# ---------------- HTML ----------------

def _data_uri(media) -> str:
    """InputFile / fayl yo'li → data: URI (rasm HTML ichiga joylanadi)."""
    path = getattr(media, "path", None)
    if path is None and isinstance(media, str) and not media.startswith("http"):
        return ""
    if path is None:
        return str(media)
    raw = Path(path).read_bytes()
    kind = "png" if str(path).endswith(".png") else "jpeg"
    return f"data:image/{kind};base64,{base64.b64encode(raw).decode()}"


def _markup_html(markup) -> str:
    if isinstance(markup, InlineKeyboardMarkup):
        rows = []
        for row in markup.inline_keyboard:
            cells = "".join(f'<span class="ib {b.style or ""}">{html.escape(b.text)}'
                            f'{"<i>↗</i>" if (b.web_app or b.url) else ""}</span>' for b in row)
            rows.append(f'<div class="ir">{cells}</div>')
        return f'<div class="ikb">{"".join(rows)}</div>'
    return ""


def _reply_kb_html(markup) -> str:
    if not isinstance(markup, ReplyKeyboardMarkup):
        return ""
    rows = "".join('<div class="ir">' + "".join(f'<span class="rb {b.style or ""}">{html.escape(b.text)}</span>'
                                                 for b in row) + "</div>" for row in markup.keyboard)
    return f'<div class="rkb">{rows}</div>'


def render_calls(calls: list[TelegramMethod], chat_id: int) -> str:
    out, keyboard = [], ""
    for c in calls:
        if getattr(c, "chat_id", None) != chat_id:
            continue
        name = type(c).__name__
        rich_msg = getattr(c, "rich_message", None)
        markup = getattr(c, "reply_markup", None)
        body = ""
        if rich_msg is not None:
            body = rich_msg.html or "<p><i>[xodim kartasi — bloklardan yig'ilgan]</i></p>"
            for m in rich_msg.media or []:
                body = body.replace(f"tg://photo?id={m.id}", _data_uri(m.media.media))
        elif name in ("SendMessage", "EditMessageText"):
            body = (c.text or "").replace("\n", "<br>")
        elif name == "SendPhoto":
            body = f'<img src="{_data_uri(c.photo)}"/>' + (f"<p>{(c.caption or '').replace(chr(10), '<br>')}</p>"
                                                           if c.caption else "")
        elif name == "SendVenue":
            body = f"<p>📍 <b>{html.escape(c.title)}</b><br>{html.escape(c.address)}</p>"
        elif name == "AnswerCallbackQuery" and c.text:
            out.append(f'<div class="toast">{html.escape(c.text)}</div>')
            continue
        else:
            continue
        effect = getattr(c, "message_effect_id", None)
        out.append(f'<div class="msg{" edited" if name == "EditMessageText" else ""}"><div class="bubble">{body}'
                   f'{"<span class=fx>🎉</span>" if effect else ""}</div>{_markup_html(markup)}</div>')
        keyboard = _reply_kb_html(markup) or keyboard
    return "".join(out) + keyboard


CSS = """
*{box-sizing:border-box} body{margin:0;background:#0b0d10;font:15px/1.42 -apple-system,'Inter','Segoe UI',Roboto,sans-serif;color:#fff}
.screens{display:flex;flex-wrap:wrap;gap:26px;padding:26px;align-items:flex-start}
.screen{width:400px;background:#0e1621 radial-gradient(circle at 20% 0,#16263a 0,#0e1621 60%);border-radius:22px;overflow:hidden;border:1px solid #1e2c3a}
.screen>h4{margin:0;padding:12px 16px;background:#17212b;font-size:13px;font-weight:600;color:#8aa0b4;letter-spacing:.02em}
.chat{padding:12px 10px 14px;display:flex;flex-direction:column;gap:8px}
.you{align-self:flex-end;background:#2b5278;border-radius:16px 16px 4px 16px;padding:7px 12px;max-width:80%}
.msg{align-self:flex-start;max-width:94%;min-width:60%}
.bubble{position:relative;background:#182533;border-radius:16px 16px 16px 4px;padding:9px 12px;overflow:hidden}
.bubble>:first-child{margin-top:0}.bubble>:last-child{margin-bottom:0}
.bubble img{display:block;max-width:calc(100% + 24px);width:calc(100% + 24px);margin:-9px -12px 8px;border-radius:0}
.bubble figure{margin:0 0 8px}.bubble figure img{margin-bottom:0}.bubble figure:first-child img{margin-top:-9px}
.bubble figcaption{font-size:12.5px;color:#8aa0b4;padding-top:5px}
.bubble tg-slideshow{display:block;margin:-9px -12px 8px;position:relative}
.bubble tg-slideshow img{display:none;margin:0;width:100%;max-width:100%}.bubble tg-slideshow img:first-of-type{display:block}
.bubble tg-slideshow::after{content:"● ○ ○";position:absolute;bottom:8px;left:0;right:0;text-align:center;font-size:9px;color:#fff;text-shadow:0 1px 3px #000}
.bubble tg-slideshow figcaption{padding:5px 12px 0}
.bubble h1,.bubble h2{font-size:19px;line-height:1.25;margin:10px 0 6px}.bubble h3{font-size:16.5px;margin:9px 0 5px}.bubble h4{font-size:14.5px;margin:8px 0 4px}
.bubble p{margin:6px 0}.bubble ul{margin:6px 0;padding-left:20px}.bubble li{margin:2px 0}
.bubble li:has(input){list-style:none;margin-left:-20px}.bubble input[type=checkbox]{accent-color:#3390ec;margin:0 8px 0 0;transform:translateY(2px)}
.bubble blockquote{margin:7px 0;padding:6px 10px;border-left:3px solid #3390ec;background:rgba(51,144,236,.12);border-radius:6px}
.bubble aside{margin:7px 0;padding:6px 10px;background:rgba(255,255,255,.06);border-radius:8px;font-size:13.5px}
.bubble footer{margin-top:8px;font-size:12.5px;color:#8aa0b4}.bubble hr{border:0;border-top:1px solid #2a3a4a;margin:9px 0}
.bubble table{border-collapse:collapse;width:100%;margin:7px 0;font-size:13.5px}
.bubble td,.bubble th{border:1px solid #2a3a4a;padding:5px 8px;vertical-align:top;text-align:left}
.bubble th{background:rgba(255,255,255,.06)}.bubble table[striped] tr:nth-child(even) td{background:rgba(255,255,255,.035)}
.bubble td[align=right],.bubble th[align=right]{text-align:right}.bubble td[align=center],.bubble th[align=center]{text-align:center}
.bubble caption{caption-side:top;text-align:left;font-size:12.5px;color:#8aa0b4;padding-bottom:4px}
.bubble details{margin:7px 0;border:1px solid #2a3a4a;border-radius:9px;padding:6px 10px}.bubble summary{cursor:pointer;font-weight:600}
.bubble code{background:rgba(255,255,255,.09);padding:1px 5px;border-radius:5px;font-size:13px}.bubble a{color:#6ab3f3}
.bubble s{color:#8aa0b4}.fx{position:absolute;right:8px;bottom:4px;font-size:18px}
.msg.edited .bubble::after{content:"tahrirlandi";display:block;text-align:right;font-size:10.5px;color:#6d7f8f;margin-top:4px}
.ikb{margin-top:4px;display:flex;flex-direction:column;gap:4px}.ir{display:flex;gap:4px}
.ib{flex:1;text-align:center;background:rgba(255,255,255,.1);border-radius:9px;padding:9px 6px;font-size:13.5px;font-weight:500;position:relative;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.ib i{position:absolute;right:5px;top:2px;font-size:9px;font-style:normal;opacity:.6}
.ib.primary,.rb.primary{background:#3390ec}.ib.success,.rb.success{background:#31b545}.ib.danger,.rb.danger{background:#e53935}
.rkb{margin-top:10px;padding:8px 2px 0;border-top:1px solid #1e2c3a;display:flex;flex-direction:column;gap:5px}
.rb{flex:1;text-align:center;background:#2b3847;border-radius:9px;padding:10px 6px;font-size:13.5px}
.toast{align-self:center;background:rgba(0,0,0,.6);border-radius:12px;padding:6px 12px;font-size:12.5px;max-width:86%;text-align:center}
"""


def page(screens: list[tuple[str, str]]) -> str:
    cols = "".join(f'<div class="screen" id="s{i}"><h4>{html.escape(title)}</h4><div class="chat">{body}</div></div>'
                   for i, (title, body) in enumerate(screens))
    return f'<!doctype html><meta charset="utf-8"><title>Bot preview</title><style>{CSS}</style><div class="screens">{cols}</div>'


# ---------------- ssenariy ----------------

async def scenario(bot, dp, s: PreviewSession) -> list[tuple[str, str]]:
    from app import products
    from app.notify import notify_status_change
    from app.orders import place_order

    screens: list[tuple[str, str]] = []

    async def shot(title: str, who: int = CUSTOMER, you: str = "") -> None:
        body = (f'<div class="you">{html.escape(you)}</div>' if you else "") + render_calls(s.calls, who)
        screens.append((title, body))
        s.calls[:] = [c for c in s.calls if getattr(c, "chat_id", who) != who]

    for uid in (ADMIN, STAFF, CUSTOMER):
        await send(bot, dp, uid, "/start")
        s.calls.clear() if uid != CUSTOMER else None
    await shot("1 · /start — til tanlash", you="/start")
    for uid in (ADMIN, STAFF):
        await click(bot, dp, uid, "lang:uz")
    s.calls.clear()
    await click(bot, dp, CUSTOMER, "lang:uz")
    await shot("2 · Salomlashuv")
    await db.set_setting("card_enabled", "1")
    await db.set_setting("card_number", "8600 1234 5678 9012")
    await db.set_setting("card_holder", "TECH ZONE MCHJ")
    await db.set_setting("phone", "+998 90 123 45 67")
    await db.set_setting("shop_address", "Toshkent, Chilonzor 7-mavze, 12-uy")
    await db.set_role(STAFF, "staff")

    await click(bot, dp, CUSTOMER, "sh:cats")
    await shot("3 · Katalog")
    await click(bot, dp, CUSTOMER, "sh:cat:1:0:0")
    await shot("4 · Kategoriya")
    items = await products.get_products(only_active=True)
    iphone = next(p for p in items if p["name"] == "iPhone 15")
    s24 = next(p for p in items if p["name"] == "Galaxy S24 Ultra")
    await click(bot, dp, CUSTOMER, f"sh:p:{iphone['id']}:0:1")
    await shot("5 · Mahsulot")
    await click(bot, dp, CUSTOMER, f"sh:p:{s24['id']}:0:1")
    await shot("6 · Chegirmali mahsulot")
    await click(bot, dp, CUSTOMER, f"sh:add:{iphone['variants'][0]['id']}:1")
    pods = next(p for p in items if p["name"] == "AirPods Pro 2")
    await click(bot, dp, CUSTOMER, f"sh:add:{pods['variants'][0]['id']}:2")
    s.calls.clear()
    await click(bot, dp, CUSTOMER, "sh:cart")
    await shot("7 · Savat")
    await click(bot, dp, CUSTOMER, "sh:co")
    await click(bot, dp, CUSTOMER, "sh:ot:delivery")
    await send(bot, dp, CUSTOMER, "Umidjon Baxtiyorov")
    await send(bot, dp, CUSTOMER, contact=Contact(phone_number="998901234567", first_name="U", user_id=CUSTOMER))
    await shot("8 · Rasmiylashtirish: hudud")
    await click(bot, dp, CUSTOMER, "sh:rg:1")
    await send(bot, dp, CUSTOMER, "Chilonzor 9-kvartal, 14-uy, 23-xonadon")
    await send(bot, dp, CUSTOMER, "➡️ O'tkazib yuborish")
    await send(bot, dp, CUSTOMER, "➡️ O'tkazib yuborish")
    await shot("9 · To'lov usuli")
    await click(bot, dp, CUSTOMER, "sh:pay:card")
    await shot("10 · Tekshirish")
    await click(bot, dp, CUSTOMER, "sh:ok")
    await shot("11 · Buyurtma berildi")
    order = (await db.get_user_orders(CUSTOMER))[0]
    s.calls.clear()
    await click(bot, dp, CUSTOMER, f"sh:rc:{order['code']}")
    await send(bot, dp, CUSTOMER, photo=[PhotoSize(file_id="P", file_unique_id="u", width=9, height=9)])
    await shot("12 · Chek yuborildi")
    await shot("13 · Menejer: chek", ADMIN)
    await click(bot, dp, ADMIN, f"py:ok:{order['id']}")
    await shot("14 · To'lov tasdiqlandi")
    await shot("15 · Xodim kartasi", STAFF)
    for st in ("packing", "shipping", "delivered"):
        await db.set_order_status(order["id"], st, STAFF)
        await notify_status_change(bot, order["id"])
        if st != "packing":
            await shot(f"{16 if st == 'shipping' else 17} · Holat: {st}")
        else:
            s.calls.clear()
    await click(bot, dp, CUSTOMER, f"sh:o:{order['code']}")
    await shot("18 · Buyurtma tafsiloti")
    await click(bot, dp, CUSTOMER, "sh:orders")
    await shot("19 · Buyurtmalarim")
    await send(bot, dp, CUSTOMER, "📞 Aloqa")
    await shot("20 · Aloqa", you="📞 Aloqa")
    v = iphone["variants"][1]
    oid = await place_order(CUSTOMER + 100, {"name": "Test", "phone": "+998901112233", "order_type": "pickup",
                                             "payment_method": "cash"}, [{"variant_id": v["id"], "qty": 1}]) \
        if await db.upsert_user(CUSTOMER + 100, "T", None, None) else 0
    del oid
    await send(bot, dp, ADMIN, "👑 Menejer paneli")
    await send(bot, dp, ADMIN, "📊 Statistika")
    await shot("21 · Menejer: statistika", ADMIN)
    return screens


async def main(out_dir: str) -> None:
    tmp = Path(tempfile.mkdtemp())
    config.admin_ids = {ADMIN}
    config.uploads_dir = tmp / "uploads"
    session = PreviewSession()
    bot = Bot(config.bot_token, session=session, default=DefaultBotProperties(parse_mode="HTML"))
    bot.session.middleware(RichSessionMiddleware())
    dp = Dispatcher()
    dp.include_router(setup_routers())
    await db.init_db(str(tmp / "bot.db"))
    await db.set_setting("mode", "open")
    screens = await scenario(bot, dp, session)
    await db.close_db()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "preview.html").write_text(page(screens), encoding="utf-8")
    print(f"{len(screens)} ta ekran → {out / 'preview.html'}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "dist/bot-preview"))
