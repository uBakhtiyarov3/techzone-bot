"""Bot API 10.4 HTML widgetlari: jonli buyurtma kuzatuvchisi.

Buyurtma berilganda bitta widget-xabar yuboriladi; holat o'zgarganda yangi xabar o'rniga shu widgetning
ma'lumoti (`chat_data`) yangilanadi va u chatda o'zi qayta chiziladi.

Widget — tarmoqsiz, sandbox ichidagi bitta HTML hujjat (≤ 32 KB, siqilganda ≤ 4 KB). Holatni faqat bot
o'zgartiradi. Hozircha Telegram widgetlarni faqat bot bilan shaxsiy chatda ko'rsatadi.

aiogram 3.31 (Bot API 10.3) da bu metodlar yo'q — shu yerda e'lon qilingan. «live_tracker» sozlamasi
yoqilgandagina ishlaydi; Telegram rad etsa, bot odatdagi rasm-kartaga qaytadi.
"""
from __future__ import annotations

import json
import logging
import zlib

from aiogram import Bot
from aiogram.methods import TelegramMethod
from aiogram.types import InlineKeyboardMarkup, Message

from . import db
from .i18n import money_l, t

log = logging.getLogger(__name__)


class SendWidget(TelegramMethod[Message]):
    __returning__ = Message
    __api_method__ = "sendWidget"

    chat_id: int
    html: str
    height: int | None = None
    chat_data: str | None = None
    caption: str | None = None
    parse_mode: str | None = None
    reply_markup: InlineKeyboardMarkup | None = None


class EditMessageWidgetData(TelegramMethod[bool]):
    __returning__ = bool
    __api_method__ = "editMessageWidgetData"

    chat_id: int
    message_id: int
    chat_data: str | None = None


# Kuzatuvchi: ma'lumot chat_data (JSON) dan o'qiladi, o'zgarsa qayta chiziladi. Ranglar — Telegram mavzusidan.
TRACKER_HTML = """<!doctype html><meta charset="utf-8"><style>
*{box-sizing:border-box;margin:0}body{font:15px/1.35 system-ui,sans-serif;color:var(--tg-theme-text-color,#fff);
background:var(--tg-theme-bg-color,#17212b);padding:14px 16px}
.top{display:flex;justify-content:space-between;align-items:center;font-size:12px;letter-spacing:.06em;
text-transform:uppercase;color:var(--tg-theme-hint-color,#8a9aa9)}
.code{padding:3px 9px;border-radius:99px;background:var(--tg-theme-secondary-bg-color,#232e3c);
color:var(--tg-theme-text-color,#fff);font-weight:600;letter-spacing:0;text-transform:none}
h1{font-size:26px;line-height:1.15;margin:8px 0 2px}.sub{color:var(--tg-theme-subtitle-text-color,#8a9aa9)}
.sum{font-weight:700;margin-top:2px}.bar{display:flex;align-items:center;margin:16px 4px 6px}
.d{width:14px;height:14px;border-radius:50%;border:2px solid var(--tg-theme-hint-color,#8a9aa9);flex:none}
.l{flex:1;height:3px;background:var(--tg-theme-secondary-bg-color,#232e3c)}
.d.on,.l.on{background:var(--c);border-color:var(--c)}.d.cur{width:20px;height:20px;box-shadow:0 0 0 5px var(--g)}
.lab{display:flex;justify-content:space-between;font-size:11px;color:var(--tg-theme-hint-color,#8a9aa9)}
.lab b{color:var(--tg-theme-text-color,#fff)}.x h1{color:var(--tg-theme-destructive-text-color,#ff5b52)}
</style><div id="r"></div><script>
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return'&#'+c.charCodeAt(0)+';'})}
function draw(){var d={};try{d=JSON.parse(TelegramWidget.chatData||'{}')}catch(e){}
var c=/^#[0-9a-f]{6}$/i.test(d.c||'')?d.c:'#E0382B',n=(d.steps||[]).length,i=d.i,h='';
h+='<div class="top"><span>'+esc(d.cap)+'</span><span class="code">'+esc(d.code)+'</span></div>';
h+='<h1>'+esc(d.t)+'</h1><div class="sub">'+esc(d.sub)+'</div><div class="sum">'+esc(d.sum)+'</div>';
if(i!=null&&n){h+='<div class="bar">';for(var k=0;k<n;k++){if(k)h+='<div class="l'+(k<=i?' on':'')+'"></div>';
h+='<div class="d'+(k<=i?' on':'')+(k==i&&i<n-1?' cur':'')+'"></div>'}
h+='</div><div class="lab">';for(k=0;k<n;k++)h+=k==i?'<b>'+esc(d.steps[k])+'</b>':'<span>'+esc(d.steps[k])+'</span>';
h+='</div>'}var r=document.getElementById('r');r.className=i==null?'x':'';
r.style.setProperty('--c',c);r.style.setProperty('--g',c+'40');r.innerHTML=h}
draw();TelegramWidget.onEvent('chatDataChanged',draw);TelegramWidget.ready&&TelegramWidget.ready();
</script>"""

assert len(TRACKER_HTML.encode()) <= 32768 and len(zlib.compress(TRACKER_HTML.encode(), 9)) <= 4096


async def enabled() -> bool:
    return (await db.get_setting("live_tracker")) == "1"


async def tracker_data(order: dict, lang: str, eta: str = "") -> str:
    """Widget holati (≤ 1024 bayt JSON). Karta bilan bir xil ma'lumot."""
    from .bot_ui import _label
    from .utils import STATUSES

    otype = order.get("order_type") or "delivery"
    status = order["status"]
    closed = status in ("cancelled", "returned")
    ready = status == "shipping" and otype == "pickup"
    sub = (order.get("cancel_reason") or "") if closed else " · ".join(
        x for x in (order.get("region_name"), eta if status != "delivered" else "") if x)
    data = {
        "c": await db.get_setting("brand_color") or "", "code": order["code"],
        "cap": t("card_order_caption", lang), "t": t("card_ready", lang) if ready else _label(status, otype, lang),
        "sub": sub[:120], "sum": money_l(order["total"], lang), "i": None if closed else STATUSES.index(status),
        "steps": [t("card_step_new", lang) if s == "new" else t("card_step_accepted", lang) if s == "accepted"
                  else t("card_ready", lang) if s == "shipping" and otype == "pickup" else _label(s, otype, lang)
                  for s in STATUSES],
    }
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if len(raw.encode()) > 1024:  # juda uzun izoh — qisqartiramiz
        data["sub"] = ""
        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return raw


async def send_tracker(bot: Bot, order: dict, lang: str, eta: str, caption: str, reply_markup=None) -> bool:
    """Jonli kuzatuvchini yuboradi va xabar ID sini saqlaydi. Bo'lmasa False (chaqiruvchi kartaga qaytadi)."""
    if not await enabled():
        return False
    try:
        msg = await bot(SendWidget(chat_id=order["user_id"], html=TRACKER_HTML, height=190,
                                   chat_data=await tracker_data(order, lang, eta), caption=caption,
                                   parse_mode="HTML", reply_markup=reply_markup))
    except Exception as e:  # noqa: BLE001 — eski server/mijoz yoki rad etilgan widget
        log.warning("Widget yuborilmadi, rasm-kartaga qaytamiz: %s", e)
        return False
    await db.execute("UPDATE orders SET widget_msg_id = ? WHERE id = ?", msg.message_id, order["id"])
    return True


async def update_tracker(bot: Bot, order: dict, lang: str, eta: str) -> bool:
    """Mavjud kuzatuvchining holatini yangilaydi. Widget yo'q yoki yangilanmasa — False."""
    mid = order.get("widget_msg_id")
    if not mid:
        return False
    try:
        await bot(EditMessageWidgetData(chat_id=order["user_id"], message_id=mid,
                                        chat_data=await tracker_data(order, lang, eta)))
        return True
    except Exception as e:  # noqa: BLE001
        if "not modified" in str(e):
            return True
        log.warning("Widget yangilanmadi: %s", e)
        return False
