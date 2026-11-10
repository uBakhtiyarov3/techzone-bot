"""Bot ko'rinishi: tugma ranglari, xabar effektlari va rasm-kartalar uchun ma'lumot yig'ish (bitta joyda)."""
from __future__ import annotations

import re

from aiogram.types import InlineKeyboardMarkup

from . import cards, db
from .i18n import money_l, status_text, t
from .utils import STATUSES

# Telegram xabar effektlari (faqat shaxsiy chatda ishlaydi)
FX_PARTY = "5046509860389126442"   # 🎉
FX_HEART = "5044134455711629726"   # ❤️
FX_LIKE = "5107584321108051014"    # 👍

# callback_data → tugma rangi. Birinchi mos kelgan qoida ishlaydi.
# primary — asosiy harakat (ko'k), success — tasdiqlash (yashil), danger — bekor qilish/o'chirish (qizil)
STYLE_RULES: list[tuple[str, str]] = [
    (r"^sh:(ok)$", "success"),
    (r"^sh:(add:|rc:)", "primary"),
    (r"^sh:(no$|oc:|clr$)", "danger"),
    (r"^ost:", "success"),
    (r"^(py|tk):(ok|okn|done):", "success"),
    (r"^(py|tk):no:", "danger"),
    (r"^(ocn|ocr):", "danger"),
    (r"^(opw):", "primary"),
]
_RULES = [(re.compile(p), s) for p, s in STYLE_RULES]


def style_markup(markup) -> None:
    """Inline tugmalarga rang beradi (rangi qo'lda berilganlariga tegmaydi)."""
    if not isinstance(markup, InlineKeyboardMarkup):
        return
    for row in markup.inline_keyboard:
        for b in row:
            if b.style:
                continue
            if b.web_app:
                b.style = "primary"
            elif b.callback_data:
                b.style = next((s for rx, s in _RULES if rx.search(b.callback_data)), None)


async def brand_info() -> dict:
    s = await db.get_settings()
    return {"name": s.get("shop_name") or "", "mark": s.get("shop_mark") or "", "color": s.get("brand_color") or ""}


def _label(status: str, otype: str, lang: str) -> str:
    """Holat nomi emoji belgisiz (rasmda emoji chizilmaydi)."""
    text = t("step_new", lang) if status == "new" else status_text(status, otype, lang)
    return re.sub(r"^[^\w«(]+", "", text).strip()


async def order_card(order: dict, lang: str, eta: str = "") -> str:
    """Buyurtma holati kartasi (rasm yo'li). Chizib bo'lmasa — bo'sh satr."""
    otype = order.get("order_type") or "delivery"
    items = await db.get_order_items(order["id"])
    images = []
    for it in items:
        if it["product_id"]:
            img = await db.fetchone("SELECT path FROM product_images WHERE product_id = ? ORDER BY sort, id",
                                    it["product_id"])
            if img:
                images.append(img["path"])
    status = order["status"]
    closed = status in ("cancelled", "returned")
    units = sum(i["qty"] for i in items)
    if closed:
        subtitle = ""
    elif otype == "delivery":
        subtitle = " · ".join(x for x in (order.get("region_name"), eta if status != "delivered" else "") if x)
    else:
        subtitle = _label("shipping", "pickup", lang) if status == "shipping" else t("type_pickup", lang).lstrip("🏬 ")
    return await cards.render("order", {
        "brand": await brand_info(), "code": order["code"],
        "caption": t("card_order_caption", lang),
        "title": _label(status, otype, lang) if status != "shipping" or otype != "pickup" else t("card_ready", lang),
        "subtitle": subtitle,
        "total": f"{money_l(order['total'], lang)} · {t('pcs', lang, n=units)}",
        "steps": [t("card_step_new", lang) if s == "new" else t("card_step_accepted", lang) if s == "accepted"
                  else t("card_ready", lang) if s == "shipping" and otype == "pickup" else _label(s, otype, lang)
                  for s in STATUSES],
        "reached": None if closed else STATUSES.index(status),
        "state": "cancelled" if closed else "done" if status == "delivered" else "active",
        "note": (order.get("cancel_reason") or "")[:80],
        "images": images[:3],
    })


async def cover(lang: str, title: str, caption: str, subtitle: str, images: list[str]) -> str:
    return await cards.render("cover", {"brand": await brand_info(), "caption": caption, "title": title,
                                        "subtitle": subtitle, "images": images[:3]})
