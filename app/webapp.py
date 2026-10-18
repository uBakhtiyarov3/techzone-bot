"""Mini App uchun HTTP server: statik fayllar + JSON API."""
import asyncio
import json
import logging
import time

from aiogram import Bot
from aiogram.utils.web_app import safe_parse_webapp_init_data
from aiohttp import web

from . import admin_api, chat, db, inventory, payments, products, regions, tickets
from .brand import public_brand
from .catalog import category_name, norm_lang, product_card, product_full, variant_label, variant_price
from .config import config
from .i18n import status_text, t, web_texts
from .notify import add_chat_and_relay, notify_new_order, notify_restocked, notify_review, order_eta, \
    refresh_staff_messages
from .orders import OrderError, can_customer_cancel, cancel_order, place_order, public_settings, quote
from .utils import ACTIVE_STATUSES, STATUSES

log = logging.getLogger(__name__)

INIT_DATA_TTL = 24 * 3600


def api_error(message: str, status: int = 400) -> web.Response:
    return web.json_response({"ok": False, "error": message}, status=status)


# ---------------- auth ----------------

CORS_HEADERS = "Content-Type, X-Telegram-Init-Data, X-Admin-Token, X-Dev-User"


@web.middleware
async def cors_middleware(request: web.Request, handler):
    """Mini App / admin panel boshqa domenda (masalan shared hosting) joylashganda API ga ruxsat."""
    origin = request.headers.get("Origin", "").rstrip("/")
    allowed = origin and (origin in config.cors_origins or "*" in config.cors_origins
                          or request.path.startswith("/api/public/"))
    if request.method == "OPTIONS" and request.path.startswith("/api/"):
        resp = web.Response(status=204)
    else:
        try:
            resp = await handler(request)
        except web.HTTPException as e:
            resp = e
    if allowed:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = CORS_HEADERS
        resp.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
        resp.headers["Access-Control-Max-Age"] = "86400"
        resp.headers["Vary"] = "Origin"
    if isinstance(resp, web.HTTPException) and resp.status >= 400:
        raise resp
    return resp


@web.middleware
async def auth_middleware(request: web.Request, handler):
    if not request.path.startswith("/api/") or request.path.startswith(("/api/admin/", "/api/public/")):
        return await handler(request)
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    tg_user = None
    if init_data:
        try:
            data = safe_parse_webapp_init_data(config.bot_token, init_data)
            if time.time() - data.auth_date.timestamp() > INIT_DATA_TTL:
                return api_error("Sessiya eskirgan. Ilovani qayta oching.", 401)
            tg_user = data.user
        except ValueError:
            return api_error("Telegram ma'lumotlari tasdiqlanmadi", 401)
    elif config.debug and request.headers.get("X-Dev-User", "").isdigit():
        # Faqat DEBUG=1 da: brauzerda test qilish uchun
        uid = int(request.headers["X-Dev-User"])
        user, _ = await db.upsert_user(uid, "Test", None, None)
        request["user"] = user
        return await handler(request)
    if not tg_user:
        return api_error("Ilovani Telegram ichida oching", 401)
    # Mini app ochilganda ham akkaunt avtomatik yaratiladi
    user, _ = await db.upsert_user(tg_user.id, tg_user.first_name, tg_user.last_name, tg_user.username)
    if not user.get("lang"):
        await db.set_lang(tg_user.id, norm_lang(tg_user.language_code))
        user = await db.get_user(tg_user.id)
    request["user"] = user
    return await handler(request)


# ---------------- helpers ----------------

def user_lang(request: web.Request) -> str:
    return norm_lang(request["user"].get("lang"))


def order_error(e: OrderError, request: web.Request) -> web.Response:
    return api_error(e.text(user_lang(request)), e.status)


def _bot(request: web.Request) -> Bot | None:
    return request.app.get("bot")


async def _json_body(request: web.Request) -> dict | None:
    if (request.content_length or 0) > 64 * 1024:  # mijoz so'rovlari kichik bo'ladi
        return None
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return body if isinstance(body, dict) else None


async def _low() -> int:
    return int(await db.get_setting("low_stock") or 3)


async def order_json(order: dict, lang: str = "uz") -> dict:
    items = await db.get_order_items(order["id"])
    log_rows = await db.get_order_log(order["id"])
    review = await db.get_review(order["id"])
    images, names = {}, {}
    for i in items:
        pid = i["product_id"]
        if pid and pid not in images:
            p = await db.fetchone("SELECT name_ru FROM products WHERE id = ?", pid)
            img = await db.fetchone("SELECT path FROM product_images WHERE product_id = ? ORDER BY sort, id", pid)
            names[pid] = (p or {}).get("name_ru") or ""
            images[pid] = (img or {}).get("path") or ""
    otype = order.get("order_type") or "delivery"
    timeline = {}
    for r in log_rows:
        timeline.setdefault(r["status"], r["at"])
    return {
        "id": order["id"],
        "code": order["code"],
        "status": order["status"],
        "status_label": status_text(order["status"], otype, lang),
        "order_type": otype,
        "promo_code": order.get("promo_code") or "",
        "discount": order.get("discount") or 0,
        "review": {"rating": review["rating"], "comment": review["comment"]} if review else None,
        "created_at": order["created_at"],
        "customer_name": order["customer_name"],
        "phone": order["phone"],
        "region": order.get("region_name") or "",
        "eta": await order_eta(order, lang) if otype == "delivery" else "",
        "address": order["address"],
        "comment": order["comment"],
        "payment_method": order["payment_method"],
        "pay_status": order.get("pay_status") or "",
        "pay_note": order.get("pay_note") or "",
        "pay_receipt": order.get("pay_receipt") or "",
        "can_upload_receipt": payments.can_upload(order),
        "card": (_card_public(await db.get_settings()) if payments.can_upload(order) else None),
        "subtotal": order["subtotal"],
        "delivery_fee": order["delivery_fee"],
        "total": order["total"],
        "cancel_reason": order["cancel_reason"],
        "items": [
            {"name": (names.get(i["product_id"]) if lang == "ru" else "") or i["name"], "variant": i["variant"],
             "price": i["price"], "qty": i["qty"], "image": images.get(i["product_id"], ""),
             "product_id": i["product_id"], "warranty_months": i["warranty_months"], "serial": i["serial"]}
            for i in items
        ],
        "timeline": timeline,
        "media": [{"status": m["status"], "path": m["path"], "caption": m["caption"], "at": m["at"]}
                  for m in await chat.get_media(order["id"]) if m["path"]],
        "unread": await chat.unread_count(order["id"], "customer"),
        "chat_open": tickets.chat_open(order),
        "can_return": await tickets.can_return(order),
        "can_cancel": can_customer_cancel(order),
        "return_until": (until.strftime("%d.%m.%Y") if (until := await tickets.return_until(order)) else ""),
        "has_open_ticket": bool(await tickets.open_ticket(order["id"])),
        "tickets": [{"id": tk["id"], "kind": tk["kind"], "status": tk["status"], "note": tk["note"],
                     "created_at": tk["created_at"]} for tk in await tickets.order_tickets(order["id"])],
    }


async def _own_order(request: web.Request) -> dict | None:
    order = await db.get_order_by_code(request.match_info["code"])
    if not order or order["user_id"] != request["user"]["id"]:
        return None
    return order


# ---------------- katalog ----------------

async def api_bootstrap(request: web.Request) -> web.Response:
    """Ilova ochilganda bitta so'rovda: matnlar, brend, sozlamalar, katalog, hududlar, profil."""
    lang = user_lang(request)
    raw = await db.get_settings()
    low = int(raw.get("low_stock") or 3)
    cats = await products.get_categories(only_active=True)
    items = await products.get_products(only_active=True)
    cards = [product_card(p, lang, low) for p in items if any(v["is_active"] for v in p["variants"])]
    counts: dict[int, int] = {}
    for c in cards:
        counts[c["category_id"]] = counts.get(c["category_id"], 0) + 1
    used_brands = {c["brand_id"] for c in cards}
    u = request["user"]
    return web.json_response({
        "ok": True,
        "lang": lang,
        "texts": web_texts(lang),
        "brand": public_brand(raw),
        "settings": public_settings(raw),
        "categories": [{"id": c["id"], "name": category_name(c, lang), "emoji": c["emoji"], "count": counts[c["id"]]}
                       for c in cats if counts.get(c["id"])],
        "brands": [{"id": b["id"], "name": b["name"], "logo": b["logo"]}
                   for b in await products.get_brands(only_active=True) if b["id"] in used_brands],
        "products": cards,
        "regions": [regions.region_public(r, lang) for r in await regions.get_regions(only_active=True)],
        "user": {
            "id": u["id"], "first_name": u["first_name"], "full_name": u["full_name"] or "",
            "phone": u["phone"] or "", "address": u["address"] or "", "region_id": u.get("region_id"),
        },
        "favorites": await db.get_favorites(u["id"]),
    })


async def api_product(request: web.Request) -> web.Response:
    lang = user_lang(request)
    p = await products.get_product(int(request.match_info["id"]))
    if not p or not p["is_active"] or not await products.category_visible(p["category_id"]):
        return api_error(t("unavailable", lang), 404)
    data = product_full(p, lang, await _low())
    alerts = [v["id"] for v in p["variants"] if await inventory.has_alert(request["user"]["id"], v["id"])]
    return web.json_response({"ok": True, "product": data, "alerts": alerts})


async def api_cart(request: web.Request) -> web.Response:
    """Savatdagi variantlarning joriy holati: narx, qoldiq, rasm (savat sahifasi uchun)."""
    body = await _json_body(request) or {}
    lang = user_lang(request)
    low = await _low()
    out = []
    for raw in (body.get("items") or [])[:30]:
        try:
            vid = int(raw["variant_id"])
        except (KeyError, TypeError, ValueError):
            continue
        v = await products.get_variant(vid)
        p = await products.get_product(v["product_id"]) if v else None
        if not v or not p:
            out.append({"variant_id": vid, "gone": True})
            continue
        price, old = variant_price(p, v)
        image = next((i["path"] for i in p["images"] if i["color"] and i["color"] in v["vals"]),
                     p["images"][0]["path"] if p["images"] else "")
        sellable = products.sellable(p, v) and await products.category_visible(p["category_id"])
        out.append({
            "variant_id": vid, "product_id": p["id"],
            "name": (p.get("name_ru") or p["name"]) if lang == "ru" else p["name"],
            "label": variant_label(p, v, lang), "image": image, "price": price, "old_price": old,
            "stock": v["stock"] if sellable else 0, "low": 0 < v["stock"] <= low, "gone": not sellable,
        })
    return web.json_response({"ok": True, "items": out})


async def api_favorite(request: web.Request) -> web.Response:
    pid = int(request.match_info["id"])
    if not await products.get_product(pid):
        return api_error("404", 404)
    added = await db.toggle_favorite(request["user"]["id"], pid)
    return web.json_response({"ok": True, "added": added, "favorites": await db.get_favorites(request["user"]["id"])})


async def api_alert(request: web.Request) -> web.Response:
    body = await _json_body(request) or {}
    try:
        v = await products.get_variant(int(body.get("variant_id")))
    except (TypeError, ValueError):
        v = None
    if not v:
        return api_error("404", 404)
    await inventory.subscribe_alert(request["user"]["id"], v["id"])
    return web.json_response({"ok": True})


async def api_set_lang(request: web.Request) -> web.Response:
    body = await _json_body(request) or {}
    lang = norm_lang(body.get("lang"))
    await db.set_lang(request["user"]["id"], lang)
    return web.json_response({"ok": True, "lang": lang})


# ---------------- buyurtma ----------------

def _order_type(body: dict) -> str:
    return body.get("order_type") if body.get("order_type") in ("delivery", "pickup") else "delivery"


async def api_quote(request: web.Request) -> web.Response:
    """Savat summasini hisoblaydi va promo-kodni tekshiradi (rasmiylashtirishda jonli ko'rsatish uchun)."""
    body = await _json_body(request)
    if body is None:
        return api_error("Bad request")
    lang = user_lang(request)
    try:
        q = await quote(request["user"]["id"], body.get("items"), _order_type(body), body.get("region_id"),
                        str(body.get("promo_code") or "").strip()[:32], lang)
    except OrderError as e:
        return order_error(e, request)
    q.pop("items")
    return web.json_response({"ok": True, "quote": q})


async def api_create_order(request: web.Request) -> web.Response:
    user = request["user"]
    body = await _json_body(request)
    if body is None:
        return api_error("Noto'g'ri so'rov")
    lang = user_lang(request)
    try:
        order_id = await place_order(user["id"], {**body, "lang": lang}, body.get("items"))
    except OrderError as e:
        return order_error(e, request)
    bot = _bot(request)
    if bot:
        asyncio.create_task(notify_new_order(bot, order_id))
    return web.json_response({"ok": True, "order": await order_json(await db.get_order(order_id), lang)})


async def api_review(request: web.Request) -> web.Response:
    lang = user_lang(request)
    order = await _own_order(request)
    if not order:
        return api_error(t("order_not_found", lang), 404)
    if order["status"] != "delivered":
        return api_error(t("rate_not_ready", lang))
    body = await _json_body(request) or {}
    try:
        rating = int(body.get("rating"))
    except (TypeError, ValueError):
        rating = 0
    if not 1 <= rating <= 5:
        return api_error("1–5")
    if not await db.add_review(order["id"], order["user_id"], rating, str(body.get("comment") or "").strip()[:500]):
        return api_error(t("already_rated", lang))
    bot = _bot(request)
    if bot:
        asyncio.create_task(notify_review(bot, order["id"]))
    return web.json_response({"ok": True, "order": await order_json(order, lang)})


async def api_orders(request: web.Request) -> web.Response:
    orders = await db.get_user_orders(request["user"]["id"], limit=30)
    lang = user_lang(request)
    return web.json_response({"ok": True, "orders": [await order_json(o, lang) for o in orders]})


async def api_order(request: web.Request) -> web.Response:
    order = await _own_order(request)
    if not order:
        return api_error(t("order_not_found", user_lang(request)), 404)
    return web.json_response({"ok": True, "order": await order_json(order, user_lang(request))})


async def api_cancel_order(request: web.Request) -> web.Response:
    """Mijoz buyurtmani yig'ish boshlanguncha (yangi yoki qabul qilingan) bekor qila oladi."""
    lang = user_lang(request)
    order = await _own_order(request)
    if not order:
        return api_error(t("order_not_found", lang), 404)
    if not can_customer_cancel(order):
        return api_error(t("cancel_not_allowed", lang))
    restocked = await cancel_order(order, request["user"]["id"], "Mijoz bekor qildi")
    bot = _bot(request)
    if bot:
        from .notify import notify_customer_cancelled

        asyncio.create_task(notify_customer_cancelled(bot, order["id"]))
        asyncio.create_task(notify_restocked(bot, restocked))
    return web.json_response({"ok": True, "order": await order_json(await db.get_order(order["id"]), lang)})


# ---------------- buyurtma chati ----------------

def _chat_json(m: dict) -> dict:
    return {"id": m["id"], "from": m["sender"], "text": m["text"], "image": m["path"], "at": m["at"]}


async def api_chat(request: web.Request) -> web.Response:
    order = await _own_order(request)
    if not order:
        return api_error(t("order_not_found", user_lang(request)), 404)
    await chat.mark_seen(order["id"], "customer")
    return web.json_response({"ok": True, "messages": [_chat_json(m) for m in await chat.get_messages(order["id"])]})


async def api_chat_send(request: web.Request) -> web.Response:
    order = await _own_order(request)
    if not order:
        return api_error(t("order_not_found", user_lang(request)), 404)
    if not tickets.chat_open(order):
        return api_error(t("chat_closed", user_lang(request)), 409)
    body = await _json_body(request) or {}
    text = str(body.get("text") or "").strip()[:2000]
    if not text:
        return api_error("Bo'sh xabar")
    await add_chat_and_relay(_bot(request), order, "customer", request["user"]["id"], text)
    return web.json_response({"ok": True, "messages": [_chat_json(m) for m in await chat.get_messages(order["id"])]})


# ---------------- qaytarish / muammo xabari ----------------

def _card_public(s: dict) -> dict | None:
    card = payments.card_info(s)
    if not card:
        return None
    return {**card, "number": payments.format_number(card["number"])}


async def api_receipt(request: web.Request) -> web.Response:
    """Karta orqali to'lov cheki: multipart (photo)."""
    lang = user_lang(request)
    order = await _own_order(request)
    if not order:
        return api_error(t("order_not_found", lang), 404)
    if not payments.can_upload(order):
        return api_error(t("e_receipt_closed", lang), 409)
    if not request.content_type.startswith("multipart/"):
        return api_error(t("receipt_need_photo", lang))
    path = ""
    reader = await request.multipart()
    while (part := await reader.next()) is not None:
        if part.name == "photo" and part.filename and not path:
            raw = await part.read(decode=False)
            if len(raw) > admin_api.MAX_UPLOAD:
                return api_error("Rasm juda katta")
            try:
                path = (await admin_api.save_upload(raw, "photo"))[0]
            except Exception:  # noqa: BLE001
                return api_error("Rasmni o'qib bo'lmadi")
        else:
            await part.read()
    if not path:
        return api_error(t("receipt_need_photo", lang))
    try:
        order = await payments.submit_receipt(order, path)
    except payments.PaymentError as e:
        return api_error(t(str(e), lang), 409)
    bot = _bot(request)
    if bot:
        from .notify import notify_receipt, refresh_staff_messages

        asyncio.create_task(notify_receipt(bot, order))
        asyncio.create_task(refresh_staff_messages(bot, order["id"]))
    return web.json_response({"ok": True, "order": await order_json(order, lang)})


async def api_ticket(request: web.Request) -> web.Response:
    """Murojaat: multipart (kind, reason, photo...). Qaytarishda kamida bitta rasm shart."""
    lang = user_lang(request)
    order = await _own_order(request)
    if not order:
        return api_error(t("order_not_found", lang), 404)
    form, photos = {}, []
    if not request.content_type.startswith("multipart/"):  # rasmsiz forma (urlencoded)
        form = {k: str(v)[:4000] for k, v in (await request.post()).items()}
    reader = await request.multipart() if request.content_type.startswith("multipart/") else None
    while reader and (part := await reader.next()) is not None:
        if part.name == "photo" and part.filename:
            raw = await part.read(decode=False)
            if len(photos) < tickets.MAX_PHOTOS and len(raw) <= admin_api.MAX_UPLOAD:
                try:
                    photos.append((await admin_api.save_upload(raw, "photo"))[0])
                except Exception:  # noqa: BLE001
                    return api_error("Rasmni o'qib bo'lmadi")
        else:
            form[part.name] = (await part.read(decode=True)).decode()[:4000]
    kind = form.get("kind") if form.get("kind") in tickets.KINDS else "issue"
    reason = form.get("reason", "").strip()
    if len(reason) < 10:
        return api_error(t("ticket_short", lang))
    if await tickets.open_ticket(order["id"]):
        return api_error(t("ticket_exists", lang), 409)
    if kind == "return":
        if not await tickets.can_return(order):
            return api_error(t("return_not_allowed", lang), 409)
        if not photos:
            return api_error(t("ticket_need_photo", lang))
    tid = await tickets.create(order, kind, reason, photos)
    bot = _bot(request)
    if bot:
        from .notify import notify_ticket_new

        asyncio.create_task(notify_ticket_new(bot, tid))
    return web.json_response({"ok": True, "id": tid, "order": await order_json(order, lang)})


# ---------------- static ----------------

def _html(path, request: web.Request) -> web.Response:
    html = path.read_text(encoding="utf-8").replace("{{v}}", request.app["version"])
    return web.Response(text=html, content_type="text/html", headers={"Cache-Control": "no-cache"})


async def index(request: web.Request) -> web.Response:
    return _html(config.webapp_dir / "index.html", request)


def static_file(name: str):
    async def handler(request: web.Request) -> web.FileResponse:
        return web.FileResponse(config.webapp_dir / name, headers={"Cache-Control": "no-cache"})
    return handler


async def health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "statuses": STATUSES, "active": list(ACTIVE_STATUSES)})


def admin_file(name: str):
    async def handler(request: web.Request) -> web.Response:
        path = config.webapp_dir / "admin" / name
        if name == "index.html":
            return _html(path, request)
        return web.FileResponse(path, headers={"Cache-Control": "no-cache"})
    return handler


async def admin_redirect(request: web.Request) -> web.Response:
    raise web.HTTPFound("/admin/")


async def _bot_username(app: web.Application) -> None:
    bot: Bot | None = app.get("bot")
    if bot and not app.get("bot_username"):
        try:
            app["bot_username"] = (await bot.get_me()).username or ""
        except Exception:  # noqa: BLE001
            app["bot_username"] = ""


def create_app(bot: Bot | None) -> web.Application:
    # 12 MB: admin panelda rasm yuklash va rasmli rassilka uchun
    app = web.Application(middlewares=[cors_middleware, auth_middleware], client_max_size=12 * 1024 * 1024)
    app["bot"] = bot
    app.on_startup.append(_bot_username)
    app["version"] = str(int(time.time()))
    config.uploads_dir.mkdir(parents=True, exist_ok=True)
    r = app.router
    r.add_get("/", index)
    for name in ("app.js", "style.css", "config.js"):
        r.add_get(f"/{name}", static_file(name))
    r.add_get("/health", health)
    r.add_static("/img", config.webapp_dir / "img")
    r.add_static("/brand", config.webapp_dir / "brand")
    r.add_static("/uploads", config.uploads_dir)
    r.add_get("/api/bootstrap", api_bootstrap)
    r.add_get("/api/products/{id:\\d+}", api_product)
    r.add_post("/api/cart", api_cart)
    r.add_post("/api/favorites/{id:\\d+}", api_favorite)
    r.add_post("/api/alerts", api_alert)
    r.add_post("/api/me/lang", api_set_lang)
    r.add_post("/api/quote", api_quote)
    r.add_get("/api/orders", api_orders)
    r.add_post("/api/orders", api_create_order)
    r.add_get("/api/orders/{code}", api_order)
    r.add_post("/api/orders/{code}/cancel", api_cancel_order)
    r.add_post("/api/orders/{code}/review", api_review)
    r.add_get("/api/orders/{code}/chat", api_chat)
    r.add_post("/api/orders/{code}/chat", api_chat_send)
    r.add_post("/api/orders/{code}/tickets", api_ticket)
    r.add_post("/api/orders/{code}/receipt", api_receipt)
    r.add_get("/admin", admin_redirect)
    r.add_get("/admin/", admin_file("index.html"))
    r.add_get("/admin/admin.js", admin_file("admin.js"))
    r.add_get("/admin/admin.css", admin_file("admin.css"))
    admin_api.setup(app)
    return app
