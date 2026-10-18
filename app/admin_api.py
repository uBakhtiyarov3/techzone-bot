"""Do'kon paneli API (/api/admin/*). Faqat menejerlar uchun.

Kirish: bot bergan bir martalik havola kodi -> sessiya tokeni (X-Admin-Token),
yoki panel Telegram ichida ochilsa — Telegram initData (menejer bo'lsa).
Barcha o'zgarishlar bazaga yoziladi va bot darhol shu ma'lumotlardan foydalanadi.
"""
import asyncio
import csv
import io
import json
import logging
import re
import time
import uuid
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.web_app import safe_parse_webapp_init_data
from aiohttp import web

from . import chat, db, hours, inventory, payments, products, regions, tickets
from .backup import make_backup
from .brand import BRAND_KEYS, HEX_RE, public_brand, shop_name
from .catalog import BADGES, badges_of, discount_active, variant_label, variant_price
from .config import config
from .i18n import OVERRIDES
from .notify import (
    add_chat_and_relay, delete_order, notify_restocked, notify_status_change, notify_ticket_decision,
    refresh_staff_messages, send_status_photo,
)
from .orders import cancel_order, decide_ticket, normalize_phone, public_settings
from .roles import get_role
from .texts_admin import catalog, validate
from .utils import (
    ACTIVE_STATUSES, PAYMENT_LABELS, TYPE_LABELS, h, next_status, now, now_str, status_label,
)

log = logging.getLogger(__name__)
SESSION_MINUTES = 14 * 24 * 60
LOGIN_CODE_MINUTES = 15


def err(message: str, status: int = 400) -> web.Response:
    return web.json_response({"ok": False, "error": message}, status=status)


def ok(**data) -> web.Response:
    return web.json_response({"ok": True, **data})


async def _body(request: web.Request) -> dict:
    try:
        data = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise web.HTTPBadRequest(text=json.dumps({"ok": False, "error": "JSON kutilgan"}),
                                 content_type="application/json")
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(text=json.dumps({"ok": False, "error": "JSON obyekt kutilgan"}),
                                 content_type="application/json")
    return data


def _bot(request: web.Request) -> Bot | None:
    return request.app.get("bot")


def _bg(request: web.Request, coro_fn, *args) -> None:
    """Bot bo'lsa bildirishnomani fonda yuboradi (API javobini kutdirmaslik uchun)."""
    bot = _bot(request)
    if bot:
        asyncio.create_task(coro_fn(bot, *args))


# ====================== kirish ======================

async def _admin_user(request: web.Request) -> int | None:
    token = request.headers.get("X-Admin-Token", "")
    uid = None
    if token:
        uid = await db.check_admin_token(token, "session")
    elif request.headers.get("X-Telegram-Init-Data"):
        try:
            data = safe_parse_webapp_init_data(config.bot_token, request.headers["X-Telegram-Init-Data"])
            if time.time() - data.auth_date.timestamp() < 24 * 3600:
                uid = data.user.id
        except ValueError:
            uid = None
    elif config.debug and request.headers.get("X-Dev-User", "").isdigit():
        uid = int(request.headers["X-Dev-User"])
    if uid and await get_role(uid) == "manager":
        return uid
    return None


def admin_only(handler):
    async def wrapper(request: web.Request):
        uid = await _admin_user(request)
        if not uid:
            return err("Kirish huquqi yo'q. Botda «🖥 Do'kon paneli» tugmasini bosing.", 401)
        request["admin_id"] = uid
        try:
            return await handler(request)
        except (ValueError, TypeError, KeyError) as e:
            return err(str(e) or "Ma'lumot noto'g'ri")
    return wrapper


async def make_login_link(user_id: int) -> str:
    code = await db.create_admin_token(user_id, "login", LOGIN_CODE_MINUTES)
    base = config.admin_url or f"{config.webapp_url}/admin"
    return f"{base}/#code={code}"


async def login(request: web.Request) -> web.Response:
    data = await _body(request)
    uid = await db.check_admin_token(str(data.get("code") or ""), "login", consume=True)
    if not uid or await get_role(uid) != "manager":
        return err("Havola eskirgan yoki noto'g'ri. Botdan yangi havola oling.", 401)
    token = await db.create_admin_token(uid, "session", SESSION_MINUTES)
    return ok(token=token, user=await _user_info(uid))


async def logout(request: web.Request) -> web.Response:
    token = request.headers.get("X-Admin-Token", "")
    if token:
        await db.delete_admin_token(token)
    return ok()


async def _user_info(uid: int) -> dict:
    u = await db.get_user(uid) or {}
    return {"id": uid, "name": u.get("full_name") or u.get("first_name") or str(uid), "username": u.get("username")}


async def public_brand_info(request: web.Request) -> web.Response:
    """Kirish sahifasi uchun brend (nom, logo, rang) — maxfiy ma'lumotsiz."""
    return ok(brand=public_brand(await db.get_settings()))


@admin_only
async def me(request: web.Request) -> web.Response:
    return ok(user=await _user_info(request["admin_id"]), bot_username=request.app.get("bot_username", ""),
              brand=public_brand(await db.get_settings()))


# ====================== dashboard ======================

def _since(period: str) -> str | None:
    n = now()
    days = {"today": 0, "week": 6, "month": 29, "quarter": 89}.get(period)
    if days is None:
        return None
    return (n - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")


@admin_only
async def dashboard(request: web.Request) -> web.Response:
    period = request.query.get("period", "today")
    since = _since(period)
    raw = await db.get_settings()
    return ok(
        period=period,
        stats=await db.stats(since),
        staff=await db.staff_stats(since),
        daily=await db.daily_revenue({"quarter": 90, "all": 90, "month": 30}.get(period, 14)),
        active_orders=len(await db.get_active_orders()),
        new_orders=len(await db.get_orders_by_status(("new",), limit=200)),
        low_stock=(await inventory.stock_list(only_low=True))[:12],
        stock_value=await inventory.stock_value(),
        unread_chats=await chat.unread_orders_for_staff(),
        open_tickets=await tickets.open_count(),
        pay_review=await payments.review_count(),
        status=public_settings(raw),
    )


# ====================== katalog ======================

def _str(data: dict, key: str, limit: int, required: bool = False) -> str:
    value = str(data.get(key) or "").strip()
    if required and not value:
        raise ValueError(f"«{key}» maydoni majburiy")
    if len(value) > limit:
        raise ValueError(f"«{key}» juda uzun (maks. {limit})")
    return value


def _int(data: dict, key: str, lo: int, hi: int, label: str | None = None) -> int:
    try:
        v = int(data.get(key) or 0)
    except (TypeError, ValueError):
        raise ValueError(f"{label or key}: raqam kiriting")
    if not lo <= v <= hi:
        raise ValueError(f"{label or key}: {lo:,} – {hi:,} oralig'ida bo'lsin".replace(",", " "))
    return v


IMAGE_RE = re.compile(r"^(uploads/[\w.-]+|img/[\w/.-]+|brand/[\w.-]+)$")


def _image(value: str) -> str:
    value = str(value or "").strip()
    if value and not IMAGE_RE.match(value):
        raise ValueError("Rasm manzili noto'g'ri")
    return value


def product_admin_json(p: dict, cats: dict | None = None) -> dict:
    variants = []
    for v in p["variants"]:
        price, _old = variant_price(p, v)
        variants.append({
            "id": v["id"], "vals": v["vals"], "label": variant_label(p, v), "sku": v["sku"], "price": v["price"],
            "price_now": price, "cost": v["cost"], "stock": v["stock"], "is_active": bool(v["is_active"]),
            "is_deleted": bool(v["is_deleted"]),
        })
    live = [v for v in variants if not v["is_deleted"]]
    return {
        "id": p["id"], "category_id": p["category_id"], "brand_id": p["brand_id"],
        "category": (cats or {}).get(p["category_id"], ""), "brand": (p.get("brand") or {}).get("name") or "",
        "name": p["name"], "name_ru": p["name_ru"], "description": p["description"],
        "description_ru": p["description_ru"], "options": p["options"], "specs": p["specs"],
        "warranty_months": p["warranty_months"], "badges": badges_of(p),
        "discount_percent": p["discount_percent"], "discount_until": p["discount_until"],
        "discount_active": discount_active(p), "is_active": bool(p["is_active"]), "is_demo": bool(p["is_demo"]),
        "sort": p["sort"], "images": [{"path": i["path"], "color": i["color"]} for i in p["images"]],
        "variants": [v for v in variants if not v["is_deleted"]],
        "stock": sum(v["stock"] for v in live if v["is_active"]),
        "price_min": min((v["price_now"] for v in live if v["is_active"]), default=0),
        "sold": p.get("sold", 0), "created_at": p["created_at"],
    }


@admin_only
async def catalog_all(request: web.Request) -> web.Response:
    cats = await products.get_categories()
    names = {c["id"]: c["name"] for c in cats}
    items = await products.get_products()
    counts: dict[int, int] = {}
    for p in items:
        counts[p["category_id"]] = counts.get(p["category_id"], 0) + 1
    brand_counts: dict[int, int] = {}
    for p in items:
        if p["brand_id"]:
            brand_counts[p["brand_id"]] = brand_counts.get(p["brand_id"], 0) + 1
    return ok(
        categories=[{**c, "is_active": bool(c["is_active"]), "count": counts.get(c["id"], 0)} for c in cats],
        brands=[{**b, "is_active": bool(b["is_active"]), "count": brand_counts.get(b["id"], 0)}
                for b in await products.get_brands()],
        products=[product_admin_json(p, names) for p in items],
        badges={k: v["uz"] for k, v in BADGES.items()},
        demo=await db.scalar("SELECT COUNT(*) FROM products WHERE is_demo = 1 AND is_deleted = 0"),
    )


def _spec_template(raw) -> list[dict]:
    out = []
    for row in (raw or [])[:40]:
        k = str(row.get("k") or "").strip()[:60]
        if k:
            out.append({"k": k, "k_ru": str(row.get("k_ru") or "").strip()[:60]})
    return out


def _parse_category(data: dict, partial: bool) -> dict:
    fields = {}
    if "name" in data or not partial:
        fields["name"] = _str(data, "name", 40, True)
    if "name_ru" in data:
        fields["name_ru"] = _str(data, "name_ru", 40)
    if "emoji" in data:
        fields["emoji"] = _str(data, "emoji", 8)
    if "is_active" in data:
        fields["is_active"] = 1 if data["is_active"] else 0
    if "spec_template" in data:
        fields["spec_template"] = _spec_template(data["spec_template"])
    return fields


@admin_only
async def category_create(request: web.Request) -> web.Response:
    fields = _parse_category(await _body(request), partial=False)
    cid = await products.add_category(fields.pop("name"))
    await products.update_category(cid, **fields)
    return ok(category=await products.get_category(cid))


@admin_only
async def category_update(request: web.Request) -> web.Response:
    cid = int(request.match_info["id"])
    if not await products.get_category(cid):
        return err("Kategoriya topilmadi", 404)
    await products.update_category(cid, **_parse_category(await _body(request), partial=True))
    return ok(category=await products.get_category(cid))


@admin_only
async def category_delete(request: web.Request) -> web.Response:
    cid = int(request.match_info["id"])
    if await products.get_products(cid):
        return err("Kategoriyada mahsulotlar bor. Avval ularni ko'chiring yoki o'chiring (yoki kategoriyani yashiring).")
    if await db.scalar("SELECT 1 FROM products WHERE category_id = ?", cid):
        # o'chirilgan mahsulotlar (buyurtma tarixi uchun) qolgan — kategoriyani yashiramiz
        await products.update_category(cid, is_active=0)
        return ok(hidden=True)
    await db.execute("DELETE FROM categories WHERE id = ?", cid)
    return ok()


async def _reorder(request: web.Request, table: str) -> web.Response:
    ids = (await _body(request)).get("ids") or []
    for pos, row_id in enumerate(ids):
        await db.db().execute(f"UPDATE {table} SET sort = ? WHERE id = ?", (pos, int(row_id)))
    await db.db().commit()
    return ok()


@admin_only
async def category_order(request: web.Request) -> web.Response:
    return await _reorder(request, "categories")


@admin_only
async def brand_create(request: web.Request) -> web.Response:
    data = await _body(request)
    name = _str(data, "name", 40, True)
    if await products.brand_by_name(name):
        return err("Bunday brend allaqachon bor")
    bid = await products.add_brand(name, _image(data.get("logo")))
    return ok(brand=await products.get_brand(bid))


@admin_only
async def brand_update(request: web.Request) -> web.Response:
    bid = int(request.match_info["id"])
    brand = await products.get_brand(bid)
    if not brand:
        return err("Brend topilmadi", 404)
    data = await _body(request)
    fields = {}
    if "name" in data:
        fields["name"] = _str(data, "name", 40, True)
        other = await products.brand_by_name(fields["name"])
        if other and other["id"] != bid:
            return err("Bunday brend allaqachon bor")
    if "logo" in data:
        fields["logo"] = _image(data["logo"])
    if "is_active" in data:
        fields["is_active"] = 1 if data["is_active"] else 0
    await products.update_brand(bid, **fields)
    return ok(brand=await products.get_brand(bid))


@admin_only
async def brand_delete(request: web.Request) -> web.Response:
    bid = int(request.match_info["id"])
    if await db.scalar("SELECT COUNT(*) FROM products WHERE brand_id = ? AND is_deleted = 0", bid):
        return err("Bu brendda mahsulotlar bor. Avval mahsulotlarni boshqa brendga o'tkazing yoki brendni yashiring.")
    await db.execute("UPDATE products SET brand_id = NULL WHERE brand_id = ?", bid)
    await db.execute("DELETE FROM brands WHERE id = ?", bid)
    return ok()


@admin_only
async def brand_order(request: web.Request) -> web.Response:
    return await _reorder(request, "brands")


def _clean_options(raw) -> list[dict]:
    if not isinstance(raw, list) or len(raw) > 3:
        raise ValueError("Variant turlari 3 tagacha bo'lishi mumkin (masalan: Rang, Xotira)")
    out = []
    for o in raw:
        name = str(o.get("name") or "").strip()[:30]
        values = [str(v).strip()[:40] for v in (o.get("values") or []) if str(v).strip()]
        if not name or not values:
            raise ValueError("Har bir variant turining nomi va kamida bitta qiymati bo'lsin")
        if len(set(values)) != len(values):
            raise ValueError(f"«{name}» qiymatlari takrorlanmasin")
        values_ru = [str(v).strip()[:40] for v in (o.get("values_ru") or [])][:len(values)]
        out.append({"name": name, "name_ru": str(o.get("name_ru") or "").strip()[:30], "values": values,
                    "values_ru": values_ru + [""] * (len(values) - len(values_ru))})
    return out


def _clean_specs(raw) -> list[dict]:
    out = []
    for s in (raw or [])[:60]:
        k, v = str(s.get("k") or "").strip()[:60], str(s.get("v") or "").strip()[:200]
        if k and v:
            out.append({"k": k, "k_ru": str(s.get("k_ru") or "").strip()[:60], "v": v,
                        "v_ru": str(s.get("v_ru") or "").strip()[:200]})
    return out


def _clean_variants(raw, options: list[dict]) -> list[dict]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= 60:
        raise ValueError("Kamida bitta variant (narx) bo'lishi kerak")
    seen, out = set(), []
    for v in raw:
        vals = [str(x) for x in (v.get("vals") or [])]
        if len(vals) != len(options) or any(val not in o["values"] for val, o in zip(vals, options)):
            raise ValueError("Variant qiymatlari variant turlariga mos emas. Jadvalni qayta yarating.")
        if tuple(vals) in seen:
            raise ValueError("Bir xil variant ikki marta kiritilgan: " + ", ".join(vals))
        seen.add(tuple(vals))
        price = _int(v, "price", 1000, 1_000_000_000, "Narx")
        out.append({
            "id": int(v["id"]) if v.get("id") else None, "vals": vals, "price": price,
            "sku": str(v.get("sku") or "").strip()[:40], "is_active": bool(v.get("is_active", True)),
            "stock": max(0, int(v.get("stock") or 0)), "cost": max(0, int(v.get("cost") or 0)),
        })
    return out


def _parse_product(data: dict, partial: bool) -> dict:
    fields = {}
    if "name" in data or not partial:
        fields["name"] = _str(data, "name", 80, True)
    for key, limit in (("name_ru", 80), ("description", 2000), ("description_ru", 2000)):
        if key in data:
            fields[key] = _str(data, key, limit)
    if "category_id" in data or not partial:
        fields["category_id"] = int(data.get("category_id") or 0)
    if "brand_id" in data:
        fields["brand_id"] = int(data["brand_id"]) if data.get("brand_id") else None
    if "warranty_months" in data:
        fields["warranty_months"] = _int(data, "warranty_months", 0, 120, "Kafolat (oy)")
    if "options" in data or not partial:
        fields["options"] = _clean_options(data.get("options") or [])
    if "specs" in data:
        fields["specs"] = _clean_specs(data["specs"])
    if "badges" in data:
        badges = [b for b in (data.get("badges") or []) if b in BADGES]
        fields["badges"] = ",".join(dict.fromkeys(badges))
    if "discount_percent" in data:
        fields["discount_percent"] = _int(data, "discount_percent", 0, 90, "Chegirma %")
    if "discount_until" in data:
        until = str(data.get("discount_until") or "").strip()
        if until:
            try:
                until = datetime.strptime(until[:10], "%Y-%m-%d").strftime("%Y-%m-%d 23:59:59")
            except ValueError:
                raise ValueError("Chegirma tugash sanasi noto'g'ri")
        fields["discount_until"] = until
    if "is_active" in data:
        fields["is_active"] = 1 if data["is_active"] else 0
    return fields


def _clean_images(raw, options: list[dict]) -> list[dict]:
    colors = set(options[0]["values"]) if options else set()
    out = []
    for img in (raw or [])[:15]:
        path = _image(img.get("path"))
        if path:
            color = str(img.get("color") or "")
            out.append({"path": path, "color": color if color in colors else ""})
    return out


async def _save_product(request: web.Request, pid: int | None) -> web.Response:
    data = await _body(request)
    fields = _parse_product(data, partial=pid is not None)
    if "category_id" in fields and not await products.get_category(fields["category_id"]):
        return err("Kategoriyani tanlang")
    if fields.get("brand_id") and not await products.get_brand(fields["brand_id"]):
        return err("Brend topilmadi")
    current = await products.get_product(pid) if pid else None
    if pid and not current:
        return err("Mahsulot topilmadi", 404)
    options = fields.get("options", current["options"] if current else [])
    variants = _clean_variants(data["variants"], options) if "variants" in data else None
    if variants is None and "options" in fields and current and fields["options"] != current["options"]:
        return err("Variant turlari o'zgardi — narxlar jadvalini ham yuboring")
    images = _clean_images(data["images"], options) if "images" in data else None
    if pid is None:
        if variants is None:
            return err("Narx(lar)ni kiriting")
        pid = await products.create_product(fields)
    else:
        await products.update_product(pid, **fields)
    if variants is not None:
        await products.save_variants(pid, variants, request["admin_id"])
    if images is not None:
        await products.save_images(pid, images)
    cats = {c["id"]: c["name"] for c in await products.get_categories()}
    return ok(product=product_admin_json(await products.get_product(pid), cats))


@admin_only
async def product_create(request: web.Request) -> web.Response:
    return await _save_product(request, None)


@admin_only
async def product_update(request: web.Request) -> web.Response:
    return await _save_product(request, int(request.match_info["id"]))


@admin_only
async def product_delete(request: web.Request) -> web.Response:
    await products.update_product(int(request.match_info["id"]), is_deleted=1, is_active=0)
    return ok()


@admin_only
async def product_order(request: web.Request) -> web.Response:
    return await _reorder(request, "products")


@admin_only
async def demo_delete(request: web.Request) -> web.Response:
    return ok(deleted=await products.delete_demo())


# ====================== rasm yuklash ======================

MAX_UPLOAD = 10 * 1024 * 1024
PRODUCT_W, PRODUCT_H = 900, 1200   # mahsulot rasmi: 3:4 (tik), oq fon (kesilmaydi)
PHOTO_MAX = 1600                   # chek, chat va boshqa rasmlar: nisbati saqlanadi


def process_image(raw: bytes, kind: str = "product") -> tuple[bytes, str, dict]:
    """Rasmni tayyorlaydi. product — kesmasdan 3:4 ga joylaydi (oq fon), photo — nisbati saqlanadi,
    brand/logo — PNG shaffofligi bilan."""
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img)
    ow, oh = img.size
    warnings = []
    if kind in ("brand", "logo"):
        img = img.convert("RGBA")
        limit = (400, 400) if kind == "brand" else (1200, 600)
        img.thumbnail(limit, Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, "PNG", optimize=True)
        return out.getvalue(), "png", {"width": img.width, "height": img.height, "original": [ow, oh],
                                       "warnings": warnings}
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        img = bg
    img = img.convert("RGB")
    if kind == "photo":
        img.thumbnail((PHOTO_MAX, PHOTO_MAX), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, "JPEG", quality=86, optimize=True, progressive=True)
        return out.getvalue(), "jpg", {"width": img.width, "height": img.height, "original": [ow, oh],
                                       "warnings": warnings}
    if abs(ow / oh - 3 / 4) > 0.03:
        warnings.append(f"Rasm {ow}×{oh} — 3:4 emas. Kesilmadi, 3:4 ga oq fon bilan joylandi.")
    w, h = img.size
    cw, ch = (w, round(w * 4 / 3)) if w / h >= 3 / 4 else (round(h * 3 / 4), h)
    canvas = Image.new("RGB", (cw, ch), (255, 255, 255))
    canvas.paste(img, ((cw - w) // 2, (ch - h) // 2))
    if cw > PRODUCT_W:
        canvas = canvas.resize((PRODUCT_W, PRODUCT_H), Image.LANCZOS)
    if ow < 600:
        warnings.append(f"Rasm kichik ({ow}×{oh}). Sifatli ko'rinishi uchun kamida 900×1200 tavsiya qilinadi.")
    out = io.BytesIO()
    canvas.save(out, "JPEG", quality=86, optimize=True, progressive=True)
    return out.getvalue(), "jpg", {"width": canvas.width, "height": canvas.height, "original": [ow, oh],
                                   "warnings": warnings}


async def _read_upload(request: web.Request) -> tuple[bytes | None, dict]:
    reader = await request.multipart()
    raw, form = None, {}
    while (part := await reader.next()) is not None:
        if part.name in ("file", "photo") and part.filename:
            raw = await part.read(decode=False)
        else:
            form[part.name] = (await part.read(decode=True)).decode()
    return raw, form


async def save_upload(raw: bytes, kind: str = "product") -> tuple[str, dict]:
    data, ext, info = await asyncio.to_thread(process_image, raw, kind)
    config.uploads_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex[:16]}.{ext}"
    (config.uploads_dir / name).write_bytes(data)
    return f"uploads/{name}", {**info, "size": len(data)}


@admin_only
async def upload(request: web.Request) -> web.Response:
    raw, form = await _read_upload(request)
    if not raw:
        return err("Fayl topilmadi")
    if len(raw) > MAX_UPLOAD:
        return err("Fayl juda katta (maks. 10 MB)")
    kind = form.get("kind") if form.get("kind") in ("product", "brand", "logo", "photo") else "product"
    try:
        path, info = await save_upload(raw, kind)
    except Exception:
        return err("Rasmni o'qib bo'lmadi. JPG, PNG yoki WebP yuklang.")
    return ok(path=path, **info)


# ====================== ombor va xaridlar ======================

@admin_only
async def stock(request: web.Request) -> web.Response:
    rows = await inventory.stock_list(request.query.get("q", "").strip(), request.query.get("low") == "1")
    return ok(items=rows, value=await inventory.stock_value(), low=int(await db.get_setting("low_stock") or 3))


@admin_only
async def stock_set(request: web.Request) -> web.Response:
    vid = int(request.match_info["id"])
    if not await products.get_variant(vid):
        return err("Variant topilmadi", 404)
    data = await _body(request)
    note = _str(data, "note", 200)
    async with inventory.STOCK_LOCK:
        if "delta" in data:
            restocked = await inventory.adjust(vid, int(data["delta"]), "adjust", note=note or "Tuzatish",
                                               by_user=request["admin_id"])
        else:
            restocked = await inventory.set_stock(vid, _int(data, "stock", 0, 1_000_000, "Qoldiq"), note,
                                                  request["admin_id"])
    if restocked:
        _bg(request, notify_restocked, [vid])
    return ok(variant=await products.get_variant(vid))


@admin_only
async def moves(request: web.Request) -> web.Response:
    vid = int(request.query["variant_id"]) if request.query.get("variant_id", "").isdigit() else None
    rows = await inventory.moves(vid)
    for r in rows:
        r["vals"] = json.loads(r["vals"] or "[]")
    return ok(moves=rows)


@admin_only
async def purchases(request: web.Request) -> web.Response:
    return ok(purchases=await inventory.get_purchases(), suppliers=await inventory.get_suppliers())


@admin_only
async def purchase_detail(request: web.Request) -> web.Response:
    pid = int(request.match_info["id"])
    p = await db.fetchone("SELECT p.*, s.name AS supplier FROM purchases p LEFT JOIN suppliers s"
                          " ON s.id = p.supplier_id WHERE p.id = ?", pid)
    if not p:
        return err("Topilmadi", 404)
    return ok(purchase=p, items=await inventory.get_purchase_items(pid))


@admin_only
async def purchase_create(request: web.Request) -> web.Response:
    data = await _body(request)
    items = []
    for it in (data.get("items") or [])[:200]:
        vid = int(it.get("variant_id") or 0)
        if not await products.get_variant(vid):
            return err("Variant topilmadi")
        items.append({"variant_id": vid, "qty": _int(it, "qty", 1, 100_000, "Soni"),
                      "cost": _int(it, "cost", 0, 1_000_000_000, "Kelish narxi")})
    if not items:
        return err("Kamida bitta mahsulot qo'shing")
    supplier_id = int(data["supplier_id"]) if data.get("supplier_id") else None
    async with inventory.STOCK_LOCK:
        purchase_id, restocked = await inventory.create_purchase(items, supplier_id, _str(data, "note", 300),
                                                                 request["admin_id"])
    if restocked:
        _bg(request, notify_restocked, restocked)
    return ok(id=purchase_id)


@admin_only
async def supplier_create(request: web.Request) -> web.Response:
    data = await _body(request)
    sid = await inventory.add_supplier(_str(data, "name", 80, True), _str(data, "phone", 40), _str(data, "note", 300))
    return ok(id=sid)


@admin_only
async def supplier_update(request: web.Request) -> web.Response:
    data = await _body(request)
    fields = {k: _str(data, k, lim, k == "name") for k, lim in (("name", 80), ("phone", 40), ("note", 300)) if k in data}
    await inventory.update_supplier(int(request.match_info["id"]), **fields)
    return ok()


# ====================== hududlar ======================

def _parse_region(data: dict, partial: bool) -> dict:
    fields = {}
    if "name" in data or not partial:
        fields["name"] = _str(data, "name", 60, True)
    if "name_ru" in data:
        fields["name_ru"] = _str(data, "name_ru", 60)
    for key, lo, hi, label in (("fee", 0, 10_000_000, "Narx"), ("free_from", 0, 1_000_000_000, "Bepul chegarasi"),
                               ("days_min", 0, 60, "Muddat (dan)"), ("days_max", 0, 60, "Muddat (gacha)")):
        if key in data:
            fields[key] = _int(data, key, lo, hi, label)
    if "is_active" in data:
        fields["is_active"] = 1 if data["is_active"] else 0
    if fields.get("days_max", 99) < fields.get("days_min", 0):
        raise ValueError("Muddat: «gacha» «dan»dan kichik bo'lmasin")
    return fields


@admin_only
async def regions_list(request: web.Request) -> web.Response:
    return ok(regions=await regions.get_regions())


@admin_only
async def region_create(request: web.Request) -> web.Response:
    rid = await regions.add_region(**_parse_region(await _body(request), partial=False))
    return ok(region=await regions.get_region(rid))


@admin_only
async def region_update(request: web.Request) -> web.Response:
    rid = int(request.match_info["id"])
    if not await regions.get_region(rid):
        return err("Hudud topilmadi", 404)
    await regions.update_region(rid, **_parse_region(await _body(request), partial=True))
    return ok(region=await regions.get_region(rid))


@admin_only
async def region_delete(request: web.Request) -> web.Response:
    await db.execute("DELETE FROM regions WHERE id = ?", int(request.match_info["id"]))
    return ok()


@admin_only
async def region_order(request: web.Request) -> web.Response:
    return await _reorder(request, "regions")


# ====================== matnlar ======================

@admin_only
async def texts(request: web.Request) -> web.Response:
    return ok(texts=catalog(dict(OVERRIDES)), shop=shop_name())


@admin_only
async def text_save(request: web.Request) -> web.Response:
    data = await _body(request)
    key, lang = str(data.get("key") or ""), str(data.get("lang") or "")
    value = str(data.get("value") or "")
    if lang not in ("uz", "ru"):
        return err("Til noto'g'ri")
    if value.strip():
        problems = validate(key, lang, value)
        if problems:
            return err("; ".join(problems))
        await db.set_text(key, lang, value)
    else:
        await db.set_text(key, lang, None)  # asl matnga qaytarish
    return ok()


# ====================== sozlamalar (do'kon + brend) ======================

async def _settings_payload() -> web.Response:
    raw = await db.get_settings()
    return ok(settings={
        **{k: raw.get(k) or "" for k in BRAND_KEYS},
        "mode": raw.get("mode") or "auto",
        "schedule": hours.load_schedule(raw),
        "min_order": int(raw.get("min_order") or 0),
        "low_stock": int(raw.get("low_stock") or 3),
        "return_days": int(raw.get("return_days") or 0),
        "phone": raw.get("phone") or "",
        "shop_address": raw.get("shop_address") or "",
        "shop_map_url": raw.get("shop_map_url") or "",
        "shop_lat": raw.get("shop_lat") or "",
        "shop_lng": raw.get("shop_lng") or "",
        "delivery_enabled": raw.get("delivery_enabled", "1") == "1",
        "pickup_enabled": raw.get("pickup_enabled", "1") == "1",
        "card_enabled": raw.get("card_enabled", "0") == "1",
        "card_number": raw.get("card_number") or "",
        "card_holder": raw.get("card_holder") or "",
        "card_bank": raw.get("card_bank") or "",
    }, status=public_settings(raw))


@admin_only
async def settings_get(request: web.Request) -> web.Response:
    return await _settings_payload()


@admin_only
async def settings_save(request: web.Request) -> web.Response:
    data = await _body(request)
    updates: dict[str, str] = {}
    if "mode" in data:
        if data["mode"] not in ("auto", "open", "closed"):
            raise ValueError("Rejim noto'g'ri")
        updates["mode"] = data["mode"]
    if "schedule" in data:
        sch = data["schedule"] or {}
        clean = {}
        for d in hours.DAYS:
            v = sch.get(d)
            if not v:
                clean[d] = None
                continue
            o, c = hours.parse_hhmm(str(v[0])), hours.parse_hhmm(str(v[1]))
            if not o or not c or o == c:
                raise ValueError(f"{d}: vaqt noto'g'ri")
            clean[d] = [f"{o[0]:02d}:{o[1]:02d}", f"{c[0] % 24:02d}:{c[1]:02d}"]
        updates["schedule"] = json.dumps(clean)
    for key, lo, hi in (("min_order", 0, 100_000_000), ("low_stock", 0, 1000), ("return_days", 0, 365)):
        if key in data:
            updates[key] = str(_int(data, key, lo, hi))
    for key, limit in (("phone", 40), ("shop_address", 200), ("shop_name", 40), ("shop_tagline", 80),
                       ("about_uz", 600), ("about_ru", 600), ("instagram", 120), ("telegram_channel", 120),
                       ("website", 200)):
        if key in data:
            updates[key] = _str(data, key, limit, key == "shop_name")
    if "card_number" in data:
        number = _str(data, "card_number", 30)
        digits = re.sub(r"\D", "", number)
        if number and not 12 <= len(digits) <= 19:
            raise ValueError("Karta raqami 16 xonali bo'lsin")
        updates["card_number"] = " ".join(digits[i:i + 4] for i in range(0, len(digits), 4))
    for key, limit in (("card_holder", 60), ("card_bank", 40)):
        if key in data:
            updates[key] = _str(data, key, limit)
    if "card_enabled" in data:
        updates["card_enabled"] = "1" if data["card_enabled"] else "0"
    for key in ("shop_logo", "shop_mark", "shop_banner"):
        if key in data:
            updates[key] = _image(data[key])
    if "brand_color" in data:
        color = _str(data, "brand_color", 7)
        if not HEX_RE.match(color):
            raise ValueError("Rang #RRGGBB ko'rinishida bo'lsin, masalan #E0382B")
        updates["brand_color"] = color.upper()
    if "order_prefix" in data:
        prefix = _str(data, "order_prefix", 4).upper()
        if not re.match(r"^[A-Z]{1,4}$", prefix):
            raise ValueError("Buyurtma prefiksi: 1–4 ta lotin harfi (masalan TZ)")
        updates["order_prefix"] = prefix
    for key in ("delivery_enabled", "pickup_enabled"):
        if key in data:
            updates[key] = "1" if data[key] else "0"
    if "shop_map_url" in data:
        url = _str(data, "shop_map_url", 500)
        if url and not re.match(r"^https://\S+$", url):
            raise ValueError("Xarita havolasi https:// bilan boshlanishi kerak")
        updates["shop_map_url"] = url
    for key, lo, hi in (("shop_lat", -90, 90), ("shop_lng", -180, 180)):
        if key in data:
            raw_v = str(data[key] or "").strip().replace(",", ".")
            if raw_v and not lo <= float(raw_v) <= hi:
                raise ValueError("Koordinata noto'g'ri")
            updates[key] = f"{float(raw_v):.6f}" if raw_v else ""
    current = await db.get_settings()
    merged = {**current, **updates}
    if merged.get("delivery_enabled", "1") != "1" and merged.get("pickup_enabled", "1") != "1":
        return err("Yetkazib berish yoki olib ketishdan kamida bittasi yoqilgan bo'lishi kerak")
    if updates.get("shop_map_url", current.get("shop_map_url")) != current.get("shop_map_url") \
            and "shop_lat" not in data:
        updates["shop_lat"] = updates["shop_lng"] = ""  # yangi havola — koordinata qaytadan aniqlanadi
    for k, v in updates.items():
        await db.set_setting(k, v)
    if updates.get("shop_map_url"):
        from .geo import shop_location

        await shop_location(force=True)
    return await _settings_payload()


# ====================== promo-kodlar ======================

def _parse_promo(data: dict, partial: bool) -> dict:
    fields = {}
    if "code" in data or not partial:
        code = str(data.get("code") or "").strip().upper()
        if not re.match(r"^[A-Z0-9_-]{3,20}$", code):
            raise ValueError("Kod: lotin harflari, raqamlar, «-» va «_» (3–20 belgi)")
        fields["code"] = code
    if "kind" in data or not partial:
        if data.get("kind") not in ("percent", "fixed", "free_delivery"):
            raise ValueError("Chegirma turini tanlang")
        fields["kind"] = data["kind"]
    for key in ("value", "min_order", "max_discount", "usage_limit", "per_user_limit"):
        if key in data:
            v = int(data.get(key) or 0)
            if v < 0:
                raise ValueError(f"{key} manfiy bo'lmasin")
            fields[key] = v
    for key in ("first_order_only", "is_active"):
        if key in data:
            fields[key] = 1 if data[key] else 0
    for key in ("starts_at", "ends_at"):
        if key in data:
            v = str(data.get(key) or "").strip().replace("T", " ")
            if v:
                try:
                    dt = datetime.strptime(v[:16], "%Y-%m-%d %H:%M") if len(v) > 10 else \
                        datetime.strptime(v, "%Y-%m-%d").replace(hour=23 if key == "ends_at" else 0,
                                                                  minute=59 if key == "ends_at" else 0)
                except ValueError:
                    raise ValueError("Sana noto'g'ri")
                v = dt.strftime("%Y-%m-%d %H:%M:00")
            fields[key] = v
    return fields


@admin_only
async def promos(request: web.Request) -> web.Response:
    return ok(promos=await db.get_promos())


@admin_only
async def promo_create(request: web.Request) -> web.Response:
    fields = _parse_promo(await _body(request), partial=False)
    if fields["kind"] != "free_delivery" and not fields.get("value"):
        return err("Chegirma qiymatini kiriting")
    if fields["kind"] == "percent" and fields.get("value", 0) > 100:
        return err("Foiz 1–100 oralig'ida bo'lsin")
    if await db.get_promo_by_code(fields["code"]):
        return err("Bunday kod allaqachon bor")
    fields.setdefault("per_user_limit", 1)
    pid = await db.add_promo(**fields)
    return ok(promo=await db.get_promo(pid))


@admin_only
async def promo_update(request: web.Request) -> web.Response:
    pid = int(request.match_info["id"])
    promo = await db.get_promo(pid)
    if not promo:
        return err("Topilmadi", 404)
    fields = _parse_promo(await _body(request), partial=True)
    if "code" in fields and fields["code"] != promo["code"] and await db.get_promo_by_code(fields["code"]):
        return err("Bunday kod allaqachon bor")
    kind = fields.get("kind", promo["kind"])
    if kind == "percent" and fields.get("value", promo["value"]) > 100:
        return err("Foiz 1–100 oralig'ida bo'lsin")
    await db.update_promo(pid, **fields)
    return ok(promo=await db.get_promo(pid))


@admin_only
async def promo_delete(request: web.Request) -> web.Response:
    await db.delete_promo(int(request.match_info["id"]))
    return ok()


# ====================== buyurtmalar ======================

def _order_row(o: dict) -> dict:
    return {
        **o,
        "status_label": status_label(o["status"], o["order_type"]),
        "type_label": TYPE_LABELS.get(o["order_type"], ""),
        "payment_label": PAYMENT_LABELS.get(o["payment_method"], ""),
        "pay_label": payments.PAY_LABELS.get(o.get("pay_status") or "", ""),
        "next": next_status(o["status"], o["order_type"]),
        "pay_block": payments.blocks_accept(o),
        "can_to_cash": payments.can_switch_to_cash(o),
    }


@admin_only
async def orders(request: web.Request) -> web.Response:
    kind = request.query.get("status", "active")
    q = request.query.get("q", "").strip()
    sql = db.ORDER_SELECT.replace(
        "SELECT o.*,", "SELECT o.*, (SELECT COUNT(*) FROM order_chat c WHERE c.order_id = o.id"
                       " AND c.sender = 'customer' AND c.seen = 0) AS unread,"
                       " (SELECT SUM(qty) FROM order_items i WHERE i.order_id = o.id) AS units,") + " WHERE 1=1"
    args: list = []
    if kind == "active":
        sql += f" AND o.status IN ({','.join('?' * len(ACTIVE_STATUSES))})"
        args += list(ACTIVE_STATUSES)
    elif kind == "payreview":
        sql += " AND o.pay_status = 'review'"
    elif kind in ("delivered", "cancelled", "returned", "new", "accepted", "packing", "shipping"):
        sql += " AND o.status = ?"
        args.append(kind)
    if q:
        sql += " AND (o.code LIKE ? OR o.phone LIKE ? OR o.customer_name LIKE ?)"
        args += [f"%{q.upper()}%", f"%{re.sub(r'[^0-9]', '', q) or q}%", f"%{q}%"]
    rows = await db.fetchall(sql + " ORDER BY o.id DESC LIMIT 300", *args)
    return ok(orders=[_order_row(o) for o in rows])


async def _order_payload(order_id: int) -> dict:
    order = await db.get_order(order_id)
    await chat.mark_seen(order_id, "staff")
    return {
        "order": _order_row(order),
        "items": await db.get_order_items(order_id),
        "log": await db.get_order_log(order_id),
        "review": await db.get_review(order_id),
        "chat": await chat.get_messages(order_id),
        "chat_open": tickets.chat_open(order),
        "media": await chat.get_media(order_id),
        "tickets": await tickets.order_tickets(order_id),
    }


@admin_only
async def order_detail(request: web.Request) -> web.Response:
    oid = int(request.match_info["id"])
    if not await db.get_order(oid):
        return err("Topilmadi", 404)
    return ok(**await _order_payload(oid))


@admin_only
async def order_payment(request: web.Request) -> web.Response:
    """Chekni tasdiqlash yoki rad etish: {action: approve|reject, note}."""
    order = await db.get_order(int(request.match_info["id"]))
    if not order:
        return err("Topilmadi", 404)
    data = await _body(request)
    try:
        order, accepted = await payments.decide(order, data.get("action") == "approve", request["admin_id"],
                                                str(data.get("note") or ""))
    except payments.PaymentError as e:
        return err({"e_receipt_not_review": "Chek allaqachon ko'rib chiqilgan. Sahifani yangilang.",
                    "e_reject_reason": "Rad etish sababini yozing"}.get(str(e), str(e)), 409)
    from .notify import notify_pay_decision

    _bg(request, notify_pay_decision, order, accepted)
    return ok(**await _order_payload(order["id"]))


@admin_only
async def order_to_cash(request: web.Request) -> web.Response:
    """Mijoz iltimosiga ko'ra karta to'lovini naqdga o'zgartirish."""
    order = await db.get_order(int(request.match_info["id"]))
    if not order:
        return err("Topilmadi", 404)
    try:
        order = await payments.switch_to_cash(order)
    except payments.PaymentError:
        return err("Bu buyurtmani naqdga o'tkazib bo'lmaydi (to'langan yoki yopilgan)", 409)
    from .notify import notify_switched_cash

    _bg(request, notify_switched_cash, order)
    return ok(**await _order_payload(order["id"]))


@admin_only
async def order_status(request: web.Request) -> web.Response:
    order = await db.get_order(int(request.match_info["id"]))
    if not order:
        return err("Topilmadi", 404)
    data = await _body(request)
    new = data.get("status")
    if new == "cancelled":
        if order["status"] not in ACTIVE_STATUSES:
            return err("Bu buyurtmani bekor qilib bo'lmaydi")
        restocked = await cancel_order(order, request["admin_id"],
                                       str(data.get("reason") or "Do'kon tomonidan bekor qilindi")[:200])
        _bg(request, notify_restocked, restocked)
    else:
        step = next_status(order["status"], order["order_type"])
        if not step or step[0] != new:
            return err("Holat allaqachon o'zgargan. Sahifani yangilang.", 409)
        if payments.blocks_accept(order):
            return err("Karta orqali to'lov hali tasdiqlanmagan. Chek tasdiqlangach buyurtma avtomatik qabul "
                       "qilinadi yoki to'lovni naqdga o'tkazing.", 409)
        await db.set_order_status(order["id"], new, request["admin_id"])
    _bg(request, notify_status_change, order["id"])
    return ok(**await _order_payload(order["id"]))


@admin_only
async def order_delete(request: web.Request) -> web.Response:
    order = await db.get_order(int(request.match_info["id"]))
    if not order:
        return err("Topilmadi", 404)
    await delete_order(_bot(request), order)
    log.info("Buyurtma %s o'chirildi (menejer %s)", order["code"], request["admin_id"])
    return ok()


@admin_only
async def order_serials(request: web.Request) -> web.Response:
    oid = int(request.match_info["id"])
    data = await _body(request)
    items = {it["id"]: it for it in await db.get_order_items(oid)}
    for item_id, serial in (data.get("serials") or {}).items():
        if int(item_id) in items:
            await db.set_item_serial(int(item_id), str(serial or ""))
    return ok(**await _order_payload(oid))


@admin_only
async def order_chat_send(request: web.Request) -> web.Response:
    order = await db.get_order(int(request.match_info["id"]))
    if not order:
        return err("Topilmadi", 404)
    if request.content_type.startswith("multipart/"):
        raw, form = await _read_upload(request)
        text = form.get("text", "").strip()[:2000]
        path = (await save_upload(raw, "photo"))[0] if raw else ""
    else:
        data = await _body(request)
        text, path = str(data.get("text") or "").strip()[:2000], ""
    if not text and not path:
        return err("Xabar bo'sh")
    if not tickets.chat_open(order):
        return err("Buyurtma yakunlangan — chat yopilgan. Mijoz bilan telefon orqali bog'laning.", 409)
    await add_chat_and_relay(_bot(request), order, "staff", request["admin_id"], text, path)
    return ok(**await _order_payload(order["id"]))


@admin_only
async def order_media_upload(request: web.Request) -> web.Response:
    """Holat rasmi: saqlanadi, mijozga botda yuboriladi va Mini App'da ko'rinadi."""
    order = await db.get_order(int(request.match_info["id"]))
    if not order:
        return err("Topilmadi", 404)
    raw, form = await _read_upload(request)
    if not raw:
        return err("Rasm tanlang")
    path, _info = await save_upload(raw, "photo")
    media_id = await chat.add_media(order["id"], order["status"], path, "", form.get("caption", ""),
                                    request["admin_id"])
    media = next(m for m in await chat.get_media(order["id"]) if m["id"] == media_id)
    _bg(request, send_status_photo, order, media)
    return ok(**await _order_payload(order["id"]))


@admin_only
async def tickets_list(request: web.Request) -> web.Response:
    return ok(tickets=await tickets.listing(request.query.get("status", "open")), open=await tickets.open_count())


@admin_only
async def ticket_decide(request: web.Request) -> web.Response:
    ticket = await tickets.get(int(request.match_info["id"]))
    if not ticket:
        return err("Murojaat topilmadi", 404)
    data = await _body(request)
    action = data.get("action")
    note = _str(data, "note", 500)
    if action == "reject" and not note:
        return err("Rad etish sababini yozing — u mijozga yuboriladi")
    restocked = await decide_ticket(ticket, action, request["admin_id"], note, bool(data.get("restock", True)))
    ticket = await tickets.get(ticket["id"])
    bot = _bot(request)
    if bot:
        asyncio.create_task(notify_ticket_decision(bot, ticket))
        if ticket["status"] == "approved":
            asyncio.create_task(refresh_staff_messages(bot, ticket["order_id"]))
            asyncio.create_task(notify_restocked(bot, restocked))
    return ok(ticket=ticket)


@admin_only
async def chats(request: web.Request) -> web.Response:
    return ok(chats=await chat.unread_orders_for_staff())


# ====================== baholar, mijozlar, xodimlar ======================

@admin_only
async def reviews(request: web.Request) -> web.Response:
    low = request.query.get("low") == "1"
    since = (now() - timedelta(days=29)).strftime("%Y-%m-%d 00:00:00")
    return ok(reviews=await db.get_reviews(100, 3 if low else None),
              total=await db.review_stats(), month=await db.review_stats(since))


@admin_only
async def customers(request: web.Request) -> web.Response:
    q = request.query.get("q", "").strip().lstrip("@")
    sql = ("SELECT u.id, u.first_name, u.username, u.full_name, u.phone, u.address, u.lang, u.role, u.is_blocked,"
           " u.created_at, r.name AS region, COUNT(o.id) AS orders,"
           " COALESCE(SUM(CASE WHEN o.status='delivered' THEN o.total END), 0) AS spent,"
           " MAX(o.created_at) AS last_order FROM users u LEFT JOIN orders o ON o.user_id = u.id"
           " LEFT JOIN regions r ON r.id = u.region_id")
    args: list = []
    if q:
        sql += " WHERE CAST(u.id AS TEXT) = ? OR lower(u.username) = lower(?) OR u.phone LIKE ? OR u.full_name LIKE ?" \
               " OR u.first_name LIKE ?"
        args = [q, q, f"%{re.sub(r'[^0-9]', '', q) or q}%", f"%{q}%", f"%{q}%"]
    rows = await db.fetchall(sql + " GROUP BY u.id ORDER BY spent DESC, u.id DESC LIMIT 200", *args)
    total = await db.scalar("SELECT COUNT(*) FROM users")
    buyers = await db.scalar("SELECT COUNT(DISTINCT user_id) FROM orders WHERE status = 'delivered'")
    return ok(customers=rows, total=total, buyers=buyers)


# ---------------- tahrirlash va o'chirish (faqat menejer) ----------------

@admin_only
async def review_delete(request: web.Request) -> web.Response:
    await db.execute("DELETE FROM reviews WHERE id = ?", int(request.match_info["id"]))
    return ok()


@admin_only
async def ticket_delete(request: web.Request) -> web.Response:
    await db.execute("DELETE FROM tickets WHERE id = ?", int(request.match_info["id"]))
    return ok()


@admin_only
async def order_edit(request: web.Request) -> web.Response:
    """Mijoz ma'lumotlarini tuzatish: ism, telefon, manzil, izoh."""
    order = await db.get_order(int(request.match_info["id"]))
    if not order:
        return err("Topilmadi", 404)
    data = await _body(request)
    fields: dict = {}
    if "customer_name" in data:
        fields["customer_name"] = _str(data, "customer_name", 64, True)
    if "phone" in data:
        phone = normalize_phone(str(data.get("phone") or ""))
        if not phone:
            raise ValueError("Telefon raqami noto'g'ri")
        fields["phone"] = phone
    if "address" in data:
        fields["address"] = _str(data, "address", 300)
    if "comment" in data:
        fields["comment"] = _str(data, "comment", 300)
    if fields:
        fields["updated_at"] = now_str()
        await db.update_row("orders", order["id"], fields, {*fields})
        _bg(request, refresh_staff_messages, order["id"])
    return ok(**await _order_payload(order["id"]))


@admin_only
async def order_chat_delete(request: web.Request) -> web.Response:
    oid, mid = int(request.match_info["id"]), int(request.match_info["mid"])
    await db.execute("DELETE FROM order_chat WHERE id = ? AND order_id = ?", mid, oid)
    return ok(**await _order_payload(oid))


@admin_only
async def order_media_delete(request: web.Request) -> web.Response:
    oid, mid = int(request.match_info["id"]), int(request.match_info["mid"])
    await db.execute("DELETE FROM order_media WHERE id = ? AND order_id = ?", mid, oid)
    return ok(**await _order_payload(oid))


@admin_only
async def customer_edit(request: web.Request) -> web.Response:
    uid = int(request.match_info["id"])
    if not await db.get_user(uid):
        return err("Topilmadi", 404)
    data = await _body(request)
    fields: dict = {}
    if "full_name" in data:
        fields["full_name"] = _str(data, "full_name", 64)
    if "phone" in data:
        raw = str(data.get("phone") or "").strip()
        phone = normalize_phone(raw) if raw else ""
        if raw and not phone:
            raise ValueError("Telefon raqami noto'g'ri")
        fields["phone"] = phone
    if "address" in data:
        fields["address"] = _str(data, "address", 300)
    await db.update_row("users", uid, fields, {"full_name", "phone", "address"})
    return ok()


@admin_only
async def customer_delete(request: web.Request) -> web.Response:
    uid = int(request.match_info["id"])
    user = await db.get_user(uid)
    if not user:
        return err("Topilmadi", 404)
    if user["role"] != "user" or uid in config.admin_ids:
        return err("Xodim yoki menejerni bu yerdan o'chirib bo'lmaydi — avval «Xodimlar» dan olib tashlang")
    if await db.scalar("SELECT COUNT(*) FROM orders WHERE user_id = ?", uid):
        return err("Bu mijozning buyurtmalari bor. Avval buyurtmalarini o'chiring (statistika uchun saqlash tavsiya qilinadi).")
    for table in ("cart_items", "favorites", "stock_alerts", "reviews", "tickets", "admin_sessions"):
        await db.execute(f"DELETE FROM {table} WHERE user_id = ?", uid)
    await db.execute("DELETE FROM users WHERE id = ?", uid)
    return ok()


@admin_only
async def supplier_delete(request: web.Request) -> web.Response:
    await inventory.delete_supplier(int(request.match_info["id"]))
    return ok()


@admin_only
async def purchase_delete(request: web.Request) -> web.Response:
    await inventory.delete_purchase(int(request.match_info["id"]), request["admin_id"])
    return ok()


@admin_only
async def staff(request: web.Request) -> web.Response:
    return ok(staff=await db.get_staff(), admins=sorted(config.admin_ids))


@admin_only
async def staff_add(request: web.Request) -> web.Response:
    data = await _body(request)
    role = data.get("role")
    if role not in ("staff", "manager"):
        return err("Rolni tanlang")
    query = str(data.get("query") or "").strip()
    user = await db.find_user(query)
    if not user and query.isdigit():
        await db.upsert_user(int(query), "", None, None)
        user = await db.get_user(int(query))
    if not user:
        return err("Foydalanuvchi topilmadi. U avval botga /start bosishi kerak yoki Telegram ID kiriting.")
    await db.set_role(user["id"], role)
    bot = _bot(request)
    if bot:
        try:
            await bot.send_message(user["id"], f"🎉 Sizga <b>{h(shop_name())}</b> botida "
                                   f"{'👷 Xodim' if role == 'staff' else '👑 Menejer'} huquqi berildi! /start bosing.")
        except Exception:  # noqa: BLE001
            pass
    return ok()


@admin_only
async def staff_remove(request: web.Request) -> web.Response:
    uid = int(request.match_info["id"])
    if uid == request["admin_id"]:
        return err("O'zingizni olib tashlay olmaysiz")
    await db.set_role(uid, "user")
    return ok()


# ====================== rassilka ======================

BROADCAST: dict = {"running": False, "sent": 0, "failed": 0, "total": 0, "finished_at": None}


def _bc_markup(buttons: list, catalog_btn: bool) -> InlineKeyboardMarkup | None:
    rows = []
    for b in buttons or []:
        text, url = str(b.get("text") or "").strip()[:40], str(b.get("url") or "").strip()
        if text and re.match(r"^(https?|tg)://\S+$", url):
            rows.append([InlineKeyboardButton(text=text, url=url)])
    if catalog_btn:
        rows.append([InlineKeyboardButton(text="🛍 Katalogni ochish", callback_data="sh:cats")])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


async def _bc_send(bot: Bot, chat_id: int, text: str, photo, markup) -> str | None:
    """Bitta rich xabar (rasm + matn). Rasm bo'lsa file_id qaytaradi (keyingilariga qayta yuklamaslik uchun)."""
    from aiogram.types import InputMediaPhoto, InputRichMessage, InputRichMessageMedia

    from .rich import legacy_to_rich

    body = legacy_to_rich(text) if text else ""
    media = None
    if photo is not None:
        body = '<img src="tg://photo?id=post"/>' + body
        media = [InputRichMessageMedia(id="post", media=InputMediaPhoto(media=photo))]
    try:
        msg = await bot.send_rich_message(chat_id, InputRichMessage(html=body, media=media), reply_markup=markup)
    except TelegramBadRequest:
        if photo is not None:
            msg = await bot.send_photo(chat_id, photo, caption=text or None, reply_markup=markup)
            return msg.photo[-1].file_id
        await bot.send_message(chat_id, text, reply_markup=markup)
        return None
    if photo is not None and msg.rich_message:
        for b in msg.rich_message.blocks or []:
            if getattr(b, "type", "") == "photo" and getattr(b, "photo", None):
                return b.photo[-1].file_id
    return None


@admin_only
async def broadcast(request: web.Request) -> web.Response:
    bot = _bot(request)
    if not bot:
        return err("Bot ulanmagan")
    if BROADCAST["running"]:
        return err("Rassilka hali davom etmoqda")
    reader = await request.multipart()
    form, photo_bytes = {}, None
    while (part := await reader.next()) is not None:
        if part.name == "photo" and part.filename:
            photo_bytes = await part.read(decode=False)
        else:
            form[part.name] = (await part.read(decode=True)).decode()
    text = form.get("text", "").strip()
    if not text and not photo_bytes:
        return err("Matn yoki rasm kerak")
    problems = []
    if text:
        from .texts_admin import _Checker

        checker = _Checker()
        checker.feed(text)
        checker.close()
        problems = checker.errors + ([f"Yopilmagan teg: <{checker.stack[-1]}>"] if checker.stack else [])
    if len(text) > 4000:
        problems.append("Matn juda uzun (4000 belgigacha)")
    if problems:
        return err("; ".join(problems))
    markup = _bc_markup(json.loads(form.get("buttons") or "[]"), form.get("catalog_btn") == "1")
    photo = BufferedInputFile(photo_bytes, "post.jpg") if photo_bytes else None

    if form.get("test") == "1":
        try:
            await _bc_send(bot, request["admin_id"], text, photo, markup)
        except TelegramBadRequest as e:
            return err(f"Telegram xatosi: {e.message}")
        return ok(test=True)

    user_ids = await db.all_user_ids()
    BROADCAST.update(running=True, sent=0, failed=0, total=len(user_ids), finished_at=None)

    async def run():
        file = photo
        try:
            for uid in user_ids:
                for attempt in range(2):
                    try:
                        fid = await _bc_send(bot, uid, text, file, markup)
                        if fid:
                            file = fid
                        BROADCAST["sent"] += 1
                    except TelegramRetryAfter as e:
                        if attempt == 0:
                            await asyncio.sleep(e.retry_after + 1)
                            continue
                        BROADCAST["failed"] += 1
                    except TelegramForbiddenError:
                        await db.set_blocked(uid, True)
                        BROADCAST["failed"] += 1
                    except Exception as e:  # noqa: BLE001
                        log.warning("Broadcast %s: %s", uid, e)
                        BROADCAST["failed"] += 1
                    break
                await asyncio.sleep(0.05)
        finally:
            BROADCAST.update(running=False, finished_at=now_str())

    asyncio.create_task(run())
    return ok(total=len(user_ids))


@admin_only
async def broadcast_status(request: web.Request) -> web.Response:
    return ok(**BROADCAST, users=len(await db.all_user_ids()))


# ====================== hisobot va zaxira ======================

def _csv_bytes(header: list[str], rows: list[list]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(header)
    w.writerows(rows)
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM — Excel to'g'ri ochishi uchun


async def orders_csv(since: str | None) -> tuple[bytes, int]:
    rows = await db.all_orders_for_export(since)
    data = _csv_bytes(
        ["Buyurtma ID", "Sana", "Turi", "Holat", "Mijoz", "Telefon", "Hudud", "Manzil", "Mahsulotlar",
         "Summa", "Promo-kod", "Chegirma", "Yetkazish", "Jami", "Tannarx", "Yalpi foyda", "To'lov", "Xodim", "Izoh"],
        [[o["code"], o["created_at"], TYPE_LABELS.get(o["order_type"], "").split(" ", 1)[-1],
          status_label(o["status"], o["order_type"]).split(" ", 1)[-1], o["customer_name"], o["phone"],
          o["region_name"], o["address"], o["items"], o["subtotal"], o["promo_code"], o["discount"],
          o["delivery_fee"], o["total"], o["cost"], o["subtotal"] - o["discount"] - o["cost"],
          PAYMENT_LABELS.get(o["payment_method"], ""), o["staff_name"] or "", o["comment"] or ""] for o in rows],
    )
    return data, len(rows)


def _file(data: bytes, name: str, ctype: str) -> web.Response:
    return web.Response(body=data, content_type=ctype, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@admin_only
async def export_csv(request: web.Request) -> web.Response:
    period = request.query.get("period", "month")
    data, _n = await orders_csv(_since(period))
    return _file(data, f"buyurtmalar_{period}_{now().strftime('%Y%m%d_%H%M')}.csv", "text/csv")


@admin_only
async def export_stock_csv(request: web.Request) -> web.Response:
    rows = await inventory.stock_list()
    data = _csv_bytes(
        ["SKU", "Mahsulot", "Variant", "Brend", "Kategoriya", "Narx", "Tannarx", "Qoldiq", "Qoldiq tannarxi"],
        [[r["sku"], r["name"], ", ".join(r["vals"]), r["brand"] or "", r["category"] or "", r["price"], r["cost"],
          r["stock"], r["stock"] * r["cost"]] for r in rows],
    )
    return _file(data, f"ombor_{now().strftime('%Y%m%d_%H%M')}.csv", "text/csv")


@admin_only
async def backup(request: web.Request) -> web.Response:
    data, name = await make_backup()
    return _file(data, name, "application/zip")


# ====================== marshrutlar ======================

def setup(app: web.Application) -> None:
    r = app.router
    r.add_post("/api/admin/login", login)
    r.add_post("/api/admin/logout", logout)
    r.add_get("/api/admin/brand", public_brand_info)
    r.add_get("/api/admin/me", me)
    r.add_get("/api/admin/dashboard", dashboard)
    r.add_get("/api/admin/catalog", catalog_all)
    r.add_post("/api/admin/categories", category_create)
    r.add_post("/api/admin/categories/order", category_order)
    r.add_patch("/api/admin/categories/{id:\\d+}", category_update)
    r.add_delete("/api/admin/categories/{id:\\d+}", category_delete)
    r.add_post("/api/admin/brands", brand_create)
    r.add_post("/api/admin/brands/order", brand_order)
    r.add_patch("/api/admin/brands/{id:\\d+}", brand_update)
    r.add_delete("/api/admin/brands/{id:\\d+}", brand_delete)
    r.add_post("/api/admin/products", product_create)
    r.add_post("/api/admin/products/order", product_order)
    r.add_put("/api/admin/products/{id:\\d+}", product_update)
    r.add_delete("/api/admin/products/{id:\\d+}", product_delete)
    r.add_delete("/api/admin/demo", demo_delete)
    r.add_post("/api/admin/upload", upload)
    r.add_get("/api/admin/stock", stock)
    r.add_post("/api/admin/stock/{id:\\d+}", stock_set)
    r.add_get("/api/admin/moves", moves)
    r.add_get("/api/admin/purchases", purchases)
    r.add_post("/api/admin/purchases", purchase_create)
    r.add_get("/api/admin/purchases/{id:\\d+}", purchase_detail)
    r.add_post("/api/admin/suppliers", supplier_create)
    r.add_patch("/api/admin/suppliers/{id:\\d+}", supplier_update)
    r.add_get("/api/admin/regions", regions_list)
    r.add_post("/api/admin/regions", region_create)
    r.add_post("/api/admin/regions/order", region_order)
    r.add_patch("/api/admin/regions/{id:\\d+}", region_update)
    r.add_delete("/api/admin/regions/{id:\\d+}", region_delete)
    r.add_get("/api/admin/texts", texts)
    r.add_put("/api/admin/texts", text_save)
    r.add_get("/api/admin/settings", settings_get)
    r.add_put("/api/admin/settings", settings_save)
    r.add_get("/api/admin/promos", promos)
    r.add_post("/api/admin/promos", promo_create)
    r.add_patch("/api/admin/promos/{id:\\d+}", promo_update)
    r.add_delete("/api/admin/promos/{id:\\d+}", promo_delete)
    r.add_get("/api/admin/orders", orders)
    r.add_get("/api/admin/orders/{id:\\d+}", order_detail)
    r.add_post("/api/admin/orders/{id:\\d+}/status", order_status)
    r.add_post("/api/admin/orders/{id:\\d+}/serials", order_serials)
    r.add_post("/api/admin/orders/{id:\\d+}/payment", order_payment)
    r.add_post("/api/admin/orders/{id:\\d+}/to-cash", order_to_cash)
    r.add_post("/api/admin/orders/{id:\\d+}/chat", order_chat_send)
    r.add_post("/api/admin/orders/{id:\\d+}/media", order_media_upload)
    r.add_delete("/api/admin/orders/{id:\\d+}", order_delete)
    r.add_get("/api/admin/chats", chats)
    r.add_get("/api/admin/tickets", tickets_list)
    r.add_post("/api/admin/tickets/{id:\\d+}", ticket_decide)
    r.add_get("/api/admin/reviews", reviews)
    r.add_delete("/api/admin/reviews/{id:\\d+}", review_delete)
    r.add_delete("/api/admin/tickets/{id:\\d+}", ticket_delete)
    r.add_patch("/api/admin/orders/{id:\\d+}", order_edit)
    r.add_delete("/api/admin/orders/{id:\\d+}/chat/{mid:\\d+}", order_chat_delete)
    r.add_delete("/api/admin/orders/{id:\\d+}/media/{mid:\\d+}", order_media_delete)
    r.add_patch("/api/admin/customers/{id:\\d+}", customer_edit)
    r.add_delete("/api/admin/customers/{id:\\d+}", customer_delete)
    r.add_delete("/api/admin/suppliers/{id:\\d+}", supplier_delete)
    r.add_delete("/api/admin/purchases/{id:\\d+}", purchase_delete)
    r.add_get("/api/admin/customers", customers)
    r.add_get("/api/admin/staff", staff)
    r.add_post("/api/admin/staff", staff_add)
    r.add_delete("/api/admin/staff/{id:\\d+}", staff_remove)
    r.add_post("/api/admin/broadcast", broadcast)
    r.add_get("/api/admin/broadcast", broadcast_status)
    r.add_get("/api/admin/export.csv", export_csv)
    r.add_get("/api/admin/stock.csv", export_stock_csv)
    r.add_get("/api/admin/backup", backup)
