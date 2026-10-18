"""Buyurtma qoidalari — Mini App va bot ichidagi savat uchun umumiy.

Narx hisoblash (chegirma, promo-kod, hudud bo'yicha yetkazish), qoldiq tekshiruvi va band qilish shu yerda.
"""
import re
from datetime import datetime, timedelta

from . import db, hours, inventory, products, regions
from .catalog import norm_lang, variant_label, variant_price
from .i18n import money_l, t
from .utils import TZ, now

ORDER_COOLDOWN_SEC = 20
MAX_QTY = 20
PHONE_RE = re.compile(r"^\+998\d{9}$")
ORDER_TYPES = ("delivery", "pickup")


class OrderError(Exception):
    """Xato kaliti (i18n) va parametrlari bilan; matn foydalanuvchi tilida olinadi."""

    def __init__(self, key: str, status: int = 400, **params):
        super().__init__(key)
        self.key = key
        self.status = status
        self.params = params

    def text(self, lang: str = "uz") -> str:
        params = {k: (money_l(v, lang) if k in ("min",) else v) for k, v in self.params.items()}
        return t(self.key, lang, **params)

    @property
    def message(self) -> str:
        return self.text("uz")


def normalize_phone(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 9:
        digits = "998" + digits
    phone = "+" + digits
    return phone if PHONE_RE.match(phone) else None


def _when_label(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.strftime("%H:%M") if dt.date() == now().date() else dt.strftime("%d.%m %H:%M")


def public_settings(s: dict) -> dict:
    is_open = hours.is_open_at(s)
    mode = s.get("mode") or "auto"
    return {
        "is_open": is_open,                     # operatorlar hozir ishlayaptimi
        "mode": mode,
        "accepting": mode != "closed",          # buyurtma qabul qilinadimi (24/7)
        "next_open": None if is_open else _when_label(hours.next_opening(s)),
        "min_order": int(s.get("min_order") or 0),
        "phone": s.get("phone") or "",
        "work_hours": hours.today_hours(s) or "",
        "schedule": hours.schedule_summary(s),
        "schedule_ru": hours.schedule_summary(s, "ru"),
        "delivery_enabled": s.get("delivery_enabled", "1") == "1",
        "pickup_enabled": s.get("pickup_enabled", "1") == "1",
        "card_enabled": s.get("card_enabled", "0") == "1" and bool((s.get("card_number") or "").strip()),
        "shop_address": s.get("shop_address") or "",
        "shop_map_url": s.get("shop_map_url") or "",
        "low_stock": int(s.get("low_stock") or 3),
    }


async def resolve_items(raw_items) -> list[dict]:
    """[{variant_id, qty}] -> narxi (chegirma bilan) va tannarxi bazadan olingan pozitsiyalar."""
    if not isinstance(raw_items, list) or not raw_items:
        raise OrderError("e_empty_cart")
    if len(raw_items) > 30:
        raise OrderError("e_too_many")
    merged: dict[int, int] = {}
    for raw in raw_items:
        try:
            vid, qty = int(raw["variant_id"]), int(raw["qty"])
        except (KeyError, TypeError, ValueError):
            raise OrderError("e_cart")
        if not 1 <= qty <= MAX_QTY:
            raise OrderError("e_qty")
        merged[vid] = merged.get(vid, 0) + qty
    items = []
    for vid, qty in merged.items():
        v = await products.get_variant(vid)
        p = await products.get_product(v["product_id"]) if v else None
        if not v or not p or v["is_deleted"] or not v["is_active"] or not p["is_active"] \
                or not await products.category_visible(p["category_id"]):
            raise OrderError("e_unavailable", 409)
        label = variant_label(p, v)
        if v["stock"] < qty:
            if v["stock"] <= 0:
                raise OrderError("e_unavailable", 409)
            raise OrderError("e_stock", 409, item=p["name"] + (f" ({label})" if label else ""), left=v["stock"])
        price, _old = variant_price(p, v)
        items.append({
            "product_id": p["id"], "variant_id": vid, "name": p["name"], "variant": label,
            "price": price, "cost": v["cost"], "qty": qty, "warranty_months": p["warranty_months"],
        })
    return items


# ---------------- promo-kod ----------------

def promo_label(promo: dict, lang: str) -> str:
    if promo["kind"] == "percent":
        return t("promo_percent", lang, value=promo["value"])
    if promo["kind"] == "fixed":
        return t("promo_fixed", lang, value=money_l(promo["value"], lang))
    return t("promo_free_delivery", lang)


def _parse_dt(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ)
    except (ValueError, TypeError):
        return None


async def check_promo(code: str, user_id: int, subtotal: int, order_type: str) -> tuple[dict, int, bool]:
    """(promo, chegirma summasi, bepul_yetkazish). Shartlar bajarilmasa OrderError."""
    promo = await db.get_promo_by_code(code)
    if not promo:
        raise OrderError("e_promo_not_found")
    if not promo["is_active"]:
        raise OrderError("e_promo_inactive")
    start, end = _parse_dt(promo["starts_at"]), _parse_dt(promo["ends_at"])
    if start and now() < start:
        raise OrderError("e_promo_not_started")
    if end and now() >= end:
        raise OrderError("e_promo_expired")
    if promo["min_order"] and subtotal < promo["min_order"]:
        raise OrderError("e_promo_min", min=promo["min_order"])
    if promo["usage_limit"] and await db.promo_uses(promo["code"]) >= promo["usage_limit"]:
        raise OrderError("e_promo_limit")
    if promo["per_user_limit"] and await db.promo_uses(promo["code"], user_id) >= promo["per_user_limit"]:
        raise OrderError("e_promo_user_limit")
    if promo["first_order_only"] and await db.user_order_count(user_id) > 0:
        raise OrderError("e_promo_first")

    if promo["kind"] == "free_delivery":
        if order_type != "delivery":
            raise OrderError("e_promo_pickup")
        return promo, 0, True
    if promo["kind"] == "percent":
        discount = subtotal * promo["value"] // 100
        if promo["max_discount"]:
            discount = min(discount, promo["max_discount"])
    else:
        discount = promo["value"]
    return promo, min(discount, subtotal), False


# ---------------- hisob-kitob ----------------

async def quote(user_id: int, raw_items, order_type: str = "delivery", region_id: int | None = None,
                promo_code: str = "", lang: str = "uz") -> dict:
    """Savat summasi: mahsulotlar, chegirma, yetkazish (hududga qarab), jami. Xato bo'lsa OrderError."""
    settings = public_settings(await db.get_settings())
    items = await resolve_items(raw_items)
    subtotal = sum(i["price"] * i["qty"] for i in items)
    region = await regions.get_region(int(region_id)) if region_id and order_type == "delivery" else None
    if region and not region["is_active"]:
        region = None
    fee = regions.delivery_fee(region, subtotal) if region else 0
    discount, promo, label = 0, None, ""
    if promo_code:
        promo, discount, free_delivery = await check_promo(promo_code, user_id, subtotal, order_type)
        if free_delivery:
            fee = 0
        label = promo_label(promo, lang)
    return {
        "items": items,
        "subtotal": subtotal,
        "discount": discount,
        "delivery_fee": fee,
        "region": regions.region_public(region, lang) if region else None,
        "total": max(0, subtotal - discount) + fee,
        "promo_code": promo["code"] if promo else "",
        "promo_label": label,
        "min_order": settings["min_order"],
    }


async def place_order(user_id: int, data: dict, raw_items) -> int:
    """Tekshiradi, qoldiqni band qiladi va buyurtma yaratadi. Xatoda OrderError. order_id qaytaradi."""
    settings = public_settings(await db.get_settings())
    lang = norm_lang(data.get("lang"))

    order_type = data.get("order_type") or "delivery"
    if order_type not in ORDER_TYPES or not settings[f"{order_type}_enabled"]:
        raise OrderError("e_type")
    if not settings["accepting"]:
        raise OrderError("e_closed_full")

    name = str(data.get("name") or "").strip()
    comment = str(data.get("comment") or "").strip()[:300]
    phone = normalize_phone(str(data.get("phone") or ""))
    payment = data.get("payment_method")
    region, address = None, ""
    if not 2 <= len(name) <= 64:
        raise OrderError("e_name")
    if not phone:
        raise OrderError("e_phone")
    if order_type == "delivery":
        try:
            region = await regions.get_region(int(data.get("region_id") or 0))
        except (TypeError, ValueError):
            region = None
        if not region or not region["is_active"]:
            raise OrderError("e_region")
        address = str(data.get("address") or "").strip()
        if not 5 <= len(address) <= 300:
            raise OrderError("e_address")
    if payment == "card":
        from . import payments

        if not payments.card_info(await db.get_settings()):
            raise OrderError("e_card")
    elif payment != "cash":
        raise OrderError("e_payment")

    last = await db.scalar("SELECT MAX(created_at) FROM orders WHERE user_id = ?", user_id)
    if last:
        last_dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ)
        if now() - last_dt < timedelta(seconds=ORDER_COOLDOWN_SEC):
            raise OrderError("e_cooldown", 429)

    async with inventory.STOCK_LOCK:
        q = await quote(user_id, raw_items, order_type, region["id"] if region else None,
                        str(data.get("promo_code") or "").strip(), lang)
        if q["min_order"] and q["subtotal"] < q["min_order"]:
            raise OrderError("e_min_order", min=q["min_order"])
        order_id = await db.create_order(user_id, {
            "order_type": order_type, "customer_name": name, "phone": phone,
            "region_id": region["id"] if region else None,
            "region_name": region["name"] if region else "",
            "delivery_eta": regions.eta_text(region, "uz") if region else "",
            "address": address, "comment": comment, "payment_method": payment,
            "pay_status": "await" if payment == "card" else "",
            "subtotal": q["subtotal"], "discount": q["discount"], "promo_code": q["promo_code"],
            "delivery_fee": q["delivery_fee"], "total": q["total"], "lang": lang,
        }, q["items"])
        order = await db.get_order(order_id)
        try:
            await inventory.reserve(q["items"], order["code"], user_id)
        except inventory.OutOfStock as e:
            await db.delete_order(order_id)
            item = next(i for i in q["items"] if i["variant_id"] == e.variant_id)
            raise OrderError("e_stock", 409, item=item["name"], left=e.left)
    await db.update_user_profile(user_id, name, phone, address, region["id"] if region else None)
    return order_id


CUSTOMER_CANCEL_STATUSES = ("new", "accepted")  # yig'ish boshlangach mijoz bekor qila olmaydi


def can_customer_cancel(order: dict) -> bool:
    return order.get("status") in CUSTOMER_CANCEL_STATUSES


async def cancel_order(order: dict, by_user: int | None, reason: str) -> list[int]:
    """Buyurtmani bekor qiladi va qoldiqni omborga qaytaradi. Qayta sotuvga chiqqan variantlar ro'yxati."""
    async with inventory.STOCK_LOCK:
        current = await db.get_order(order["id"])
        if not current or current["status"] == "cancelled":
            return []
        await db.set_order_status(order["id"], "cancelled", by_user, reason[:200])
        return await inventory.release(order["id"], order["code"], by_user)


async def decide_ticket(ticket: dict, action: str, by_user: int | None, note: str = "",
                        restock: bool = True) -> list[int]:
    """Murojaat bo'yicha qaror. approve/reject — qaytarish, resolve — muammo xabari.

    Qaytarish tasdiqlansa buyurtma "qaytarildi" bo'ladi va (restock=True) mahsulot omborga qaytadi.
    Qayta sotuvga chiqqan variantlar ro'yxatini qaytaradi.
    """
    from . import tickets

    if ticket["status"] != "open":
        raise ValueError("Murojaat allaqachon ko'rib chiqilgan")
    if ticket["kind"] == "return" and action in ("approve", "reject"):
        if action == "reject":
            await tickets.set_status(ticket["id"], "rejected", by_user, note)
            return []
        order = await db.get_order(ticket["order_id"])
        restocked: list[int] = []
        async with inventory.STOCK_LOCK:
            await db.set_order_status(order["id"], "returned", by_user, note or "Qaytarish tasdiqlandi")
            if restock:
                restocked = await inventory.release(order["id"], order["code"], by_user, "return")
        await tickets.set_status(ticket["id"], "approved", by_user, note)
        return restocked
    if ticket["kind"] == "issue" and action == "resolve":
        await tickets.set_status(ticket["id"], "resolved", by_user, note)
        return []
    raise ValueError("Bu murojaat uchun amal noto'g'ri")
