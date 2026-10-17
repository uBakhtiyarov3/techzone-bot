"""SQLite: ulanish, sxema, sozlamalar, foydalanuvchilar, buyurtmalar, promo, baholar, statistika.

Katalog so'rovlari — products.py, ombor — inventory.py, hududlar — regions.py, chat — chat.py.
"""
import json
import secrets
from pathlib import Path

import aiosqlite

from .utils import ACTIVE_STATUSES, now_str

_db: aiosqlite.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    username TEXT,
    full_name TEXT,
    phone TEXT,
    address TEXT,
    region_id INTEGER,
    lang TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT 'user',          -- user | staff | manager
    is_blocked INTEGER NOT NULL DEFAULT 0,      -- botni bloklagan
    created_at TEXT NOT NULL,
    last_active TEXT
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    name_ru TEXT NOT NULL DEFAULT '',
    emoji TEXT NOT NULL DEFAULT '',
    spec_template TEXT NOT NULL DEFAULT '[]',   -- JSON: [{"k": "Ekran", "k_ru": "Экран"}]
    sort INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS brands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    logo TEXT NOT NULL DEFAULT '',
    sort INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    brand_id INTEGER REFERENCES brands(id),
    name TEXT NOT NULL,
    name_ru TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    description_ru TEXT NOT NULL DEFAULT '',
    options TEXT NOT NULL DEFAULT '[]',         -- JSON: [{"name": "Rang", "name_ru": "Цвет", "values": ["Qora"]}]
    specs TEXT NOT NULL DEFAULT '[]',           -- JSON: [{"k": "Ekran", "k_ru": "", "v": "6.1\\"", "v_ru": ""}]
    warranty_months INTEGER NOT NULL DEFAULT 12,
    badges TEXT NOT NULL DEFAULT '',            -- hit,new,top
    discount_percent INTEGER NOT NULL DEFAULT 0,
    discount_until TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,       -- vitrinada ko'rinadi
    is_deleted INTEGER NOT NULL DEFAULT 0,
    is_demo INTEGER NOT NULL DEFAULT 0,
    sort INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS product_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    path TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '',             -- variant rangi (bo'sh — umumiy rasm)
    sort INTEGER NOT NULL DEFAULT 0
);

-- mahsulotning har bir kombinatsiyasi (rang × xotira) o'z narxi va qoldig'i bilan
CREATE TABLE IF NOT EXISTS variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    vals TEXT NOT NULL DEFAULT '[]',            -- JSON: ["Qora", "256 GB"] (options tartibida)
    sku TEXT NOT NULL DEFAULT '',
    price INTEGER NOT NULL,
    cost INTEGER NOT NULL DEFAULT 0,            -- o'rtacha tannarx
    stock INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    is_deleted INTEGER NOT NULL DEFAULT 0,      -- admin olib tashlagan (buyurtma tarixi uchun saqlanadi)
    sort INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stock_moves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_id INTEGER NOT NULL,
    delta INTEGER NOT NULL,
    reason TEXT NOT NULL,                       -- purchase | order | cancel | adjust
    ref TEXT NOT NULL DEFAULT '',               -- buyurtma yoki xarid kodi
    note TEXT NOT NULL DEFAULT '',
    by_user INTEGER,
    at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    supplier_id INTEGER,
    total INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    by_user INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS purchase_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id INTEGER NOT NULL,
    variant_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    qty INTEGER NOT NULL,
    cost INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS regions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    name_ru TEXT NOT NULL DEFAULT '',
    fee INTEGER NOT NULL DEFAULT 0,
    free_from INTEGER NOT NULL DEFAULT 0,       -- 0 = bepul chegara yo'q
    days_min INTEGER NOT NULL DEFAULT 1,
    days_max INTEGER NOT NULL DEFAULT 3,
    sort INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,                  -- unikal ID: TZ-482917
    user_id INTEGER NOT NULL REFERENCES users(id),
    order_type TEXT NOT NULL DEFAULT 'delivery',-- delivery | pickup
    customer_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    region_id INTEGER,
    region_name TEXT NOT NULL DEFAULT '',
    delivery_eta TEXT NOT NULL DEFAULT '',      -- "1–2 kun"
    address TEXT NOT NULL DEFAULT '',
    comment TEXT NOT NULL DEFAULT '',
    payment_method TEXT NOT NULL,
    subtotal INTEGER NOT NULL,
    discount INTEGER NOT NULL DEFAULT 0,
    promo_code TEXT NOT NULL DEFAULT '',
    delivery_fee INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    staff_id INTEGER,
    cancel_reason TEXT,
    lang TEXT NOT NULL DEFAULT 'uz',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER,
    variant_id INTEGER,
    name TEXT NOT NULL,
    variant TEXT NOT NULL DEFAULT '',
    price INTEGER NOT NULL,
    cost INTEGER NOT NULL DEFAULT 0,            -- sotilgan paytdagi tannarx (foyda uchun)
    qty INTEGER NOT NULL,
    warranty_months INTEGER NOT NULL DEFAULT 0,
    serial TEXT NOT NULL DEFAULT ''             -- IMEI / seriya raqami
);

CREATE TABLE IF NOT EXISTS order_status_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    by_user INTEGER,
    at TEXT NOT NULL
);

-- xodimlarga yuborilgan kartalar (holat o'zgarsa hammasida yangilash uchun)
CREATE TABLE IF NOT EXISTS order_messages (
    order_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL
);

-- holat rasmlari (masalan "yig'ilmoqda" bosqichidagi surat)
CREATE TABLE IF NOT EXISTS order_media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    path TEXT NOT NULL DEFAULT '',
    file_id TEXT NOT NULL DEFAULT '',
    caption TEXT NOT NULL DEFAULT '',
    by_user INTEGER,
    at TEXT NOT NULL
);

-- buyurtma ichidagi yozishma: mijoz <-> do'kon
CREATE TABLE IF NOT EXISTS order_chat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    sender TEXT NOT NULL,                       -- customer | staff
    user_id INTEGER,
    text TEXT NOT NULL DEFAULT '',
    path TEXT NOT NULL DEFAULT '',
    file_id TEXT NOT NULL DEFAULT '',
    seen INTEGER NOT NULL DEFAULT 0,            -- qarshi tomon o'qidi
    at TEXT NOT NULL
);

-- murojaatlar: buyurtmani qaytarish va "muammo haqida xabar berish"
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    kind TEXT NOT NULL,                         -- return | issue
    reason TEXT NOT NULL,
    photos TEXT NOT NULL DEFAULT '[]',          -- JSON: ["uploads/..."]
    status TEXT NOT NULL DEFAULT 'open',        -- open | approved | rejected | resolved
    note TEXT NOT NULL DEFAULT '',              -- xodim izohi (mijozga ham yuboriladi)
    handled_by INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- bot ichidagi savat (Mini App savati brauzerda saqlanadi)
CREATE TABLE IF NOT EXISTS cart_items (
    user_id INTEGER NOT NULL,
    variant_id INTEGER NOT NULL,
    qty INTEGER NOT NULL,
    PRIMARY KEY (user_id, variant_id)
);

CREATE TABLE IF NOT EXISTS favorites (
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, product_id)
);

-- "kelganda xabar berish"
CREATE TABLE IF NOT EXISTS stock_alerts (
    user_id INTEGER NOT NULL,
    variant_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, variant_id)
);

CREATE TABLE IF NOT EXISTS promo_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,                         -- percent | fixed | free_delivery
    value INTEGER NOT NULL DEFAULT 0,
    min_order INTEGER NOT NULL DEFAULT 0,
    max_discount INTEGER NOT NULL DEFAULT 0,    -- 0 = cheklovsiz (foiz uchun)
    usage_limit INTEGER NOT NULL DEFAULT 0,     -- 0 = cheklovsiz
    per_user_limit INTEGER NOT NULL DEFAULT 1,  -- 0 = cheklovsiz
    first_order_only INTEGER NOT NULL DEFAULT 0,
    starts_at TEXT NOT NULL DEFAULT '',
    ends_at TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL UNIQUE,
    user_id INTEGER NOT NULL,
    rating INTEGER NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

-- admin web panel sessiyalari (token xeshi saqlanadi)
CREATE TABLE IF NOT EXISTS admin_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    kind TEXT NOT NULL,                         -- login (bir martalik kod) | session
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- admin paneldan tahrirlangan bot/Mini App matnlari
CREATE TABLE IF NOT EXISTS texts (
    key TEXT NOT NULL,
    lang TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (key, lang)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_products_cat ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_variants_product ON variants(product_id);
CREATE INDEX IF NOT EXISTS idx_images_product ON product_images(product_id);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_chat_order ON order_chat(order_id);
CREATE INDEX IF NOT EXISTS idx_moves_variant ON stock_moves(variant_id);
CREATE INDEX IF NOT EXISTS idx_tickets_order ON tickets(order_id);
"""

# Kelajakdagi yangi ustunlar shu yerga: (jadval, ustun, ta'rif) — eski bazalar ham buzilmasdan yangilanadi
MIGRATIONS: list[tuple[str, str, str]] = []

DEFAULT_SETTINGS = {
    # --- brend (white-label: boshqa do'kon uchun shu yerdan o'zgaradi) ---
    "shop_name": "Tech.Zone",
    "shop_tagline": "Smart choices. Better tomorrow.",
    "shop_logo": "brand/logo.png",
    "shop_mark": "brand/mark.png",
    "brand_color": "#E0382B",
    "order_prefix": "TZ",
    "about_uz": "Smartfonlar, noutbuklar, planshetlar, quloqchinlar va aksessuarlar — rasmiy kafolat bilan.",
    "about_ru": "Смартфоны, ноутбуки, планшеты, наушники и аксессуары — с официальной гарантией.",
    "instagram": "",
    "telegram_channel": "",
    "website": "",
    # --- do'kon ---
    "mode": "auto",                 # auto (jadval bo'yicha) | open | closed (buyurtma to'xtatilgan)
    "schedule": json.dumps({d: ["09:00", "21:00"] for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}),
    "phone": "",
    "shop_address": "",
    "shop_map_url": "",
    "shop_lat": "",
    "shop_lng": "",
    "delivery_enabled": "1",
    "pickup_enabled": "1",
    "min_order": "0",
    "low_stock": "3",               # shu sondan kam qolsa "oz qoldi" va menejerga ogohlantirish
    "card_enabled": "0",            # Click/Payme ulanganda yoqiladi
    "return_days": "14",            # yetkazilgandan keyin necha kun ichida qaytarish mumkin (0 — o'chirilgan)
}


def db() -> aiosqlite.Connection:
    assert _db is not None, "DB is not initialised"
    return _db


async def init_db(path: str, seed_demo: bool = True) -> None:
    global _db
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(path)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA foreign_keys=ON")
    await _db.executescript(SCHEMA)
    await _migrate()
    for k, v in DEFAULT_SETTINGS.items():
        await _db.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (k, v))
    await _db.commit()
    from . import seed

    await seed.seed_regions()
    if seed_demo:
        await seed.seed_demo_catalog()
    await reload_texts()


async def _migrate() -> None:
    for table, column, ddl in MIGRATIONS:
        cur = await db().execute(f"PRAGMA table_info({table})")
        cols = {r[1] for r in await cur.fetchall()}
        if column not in cols:
            await db().execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    await db().commit()


async def close_db() -> None:
    global _db
    if _db:
        await _db.close()
        _db = None


def _row(r) -> dict | None:
    return dict(r) if r else None


async def fetchone(sql: str, *args) -> dict | None:
    cur = await db().execute(sql, args)
    return _row(await cur.fetchone())


async def fetchall(sql: str, *args) -> list[dict]:
    cur = await db().execute(sql, args)
    return [dict(r) for r in await cur.fetchall()]


async def scalar(sql: str, *args):
    cur = await db().execute(sql, args)
    row = await cur.fetchone()
    return row[0] if row else None


async def execute(sql: str, *args) -> int:
    cur = await db().execute(sql, args)
    await db().commit()
    return cur.lastrowid


async def update_row(table: str, row_id: int, fields: dict, allowed: set[str]) -> None:
    """Ruxsat etilgan ustunlarni yangilaydi (ustun nomlari faqat oq ro'yxatdan)."""
    cols = [k for k in fields if k in allowed]
    if not cols:
        return
    await execute(f"UPDATE {table} SET {', '.join(c + ' = ?' for c in cols)} WHERE id = ?",
                  *[fields[c] for c in cols], row_id)


# ---------------- settings ----------------

async def get_settings() -> dict:
    rows = await fetchall("SELECT key, value FROM settings")
    return {r["key"]: r["value"] for r in rows}


async def get_setting(key: str) -> str:
    return await scalar("SELECT value FROM settings WHERE key = ?", key) or ""


async def set_setting(key: str, value) -> None:
    await execute(
        "INSERT INTO settings(key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        key, str(value),
    )
    if key == "shop_name":
        from . import brand

        brand.SHOP["name"] = str(value)


# ---------------- matnlar ----------------

async def reload_texts() -> None:
    from . import brand
    from .i18n import set_overrides

    set_overrides(await fetchall("SELECT key, lang, value FROM texts"))
    brand.SHOP["name"] = await get_setting("shop_name") or DEFAULT_SETTINGS["shop_name"]


async def set_text(key: str, lang: str, value: str | None) -> None:
    """value=None yoki bo'sh — asl matnga qaytarish."""
    if value:
        await execute(
            "INSERT INTO texts(key, lang, value, updated_at) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(key, lang) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            key, lang, value, now_str(),
        )
    else:
        await execute("DELETE FROM texts WHERE key = ? AND lang = ?", key, lang)
    await reload_texts()


# ---------------- admin sessiyalari ----------------

def _hash(token: str) -> str:
    import hashlib

    return hashlib.sha256(token.encode()).hexdigest()


async def create_admin_token(user_id: int, kind: str, ttl_minutes: int) -> str:
    from datetime import timedelta

    from .utils import now

    token = secrets.token_urlsafe(32)
    expires = (now() + timedelta(minutes=ttl_minutes)).strftime("%Y-%m-%d %H:%M:%S")
    await execute("DELETE FROM admin_sessions WHERE expires_at < ?", now_str())
    await execute(
        "INSERT INTO admin_sessions(token_hash, user_id, kind, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
        _hash(token), user_id, kind, expires, now_str(),
    )
    return token


async def check_admin_token(token: str, kind: str, consume: bool = False) -> int | None:
    row = await fetchone(
        "SELECT user_id FROM admin_sessions WHERE token_hash = ? AND kind = ? AND expires_at > ?",
        _hash(token), kind, now_str(),
    )
    if row and consume:
        await execute("DELETE FROM admin_sessions WHERE token_hash = ?", _hash(token))
    return row["user_id"] if row else None


async def delete_admin_token(token: str) -> None:
    await execute("DELETE FROM admin_sessions WHERE token_hash = ?", _hash(token))


# ---------------- users ----------------

async def upsert_user(user_id: int, first_name: str, last_name: str | None, username: str | None) -> tuple[dict, bool]:
    """Foydalanuvchini yaratadi yoki yangilaydi. (user, is_new) qaytaradi."""
    existing = await get_user(user_id)
    if existing:
        await execute(
            "UPDATE users SET first_name=?, last_name=?, username=?, last_active=?, is_blocked=0 WHERE id=?",
            first_name, last_name, username, now_str(), user_id,
        )
    else:
        await execute(
            "INSERT INTO users(id, first_name, last_name, username, created_at, last_active)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            user_id, first_name, last_name, username, now_str(), now_str(),
        )
    return await get_user(user_id), existing is None


async def get_user(user_id: int) -> dict | None:
    return await fetchone("SELECT * FROM users WHERE id = ?", user_id)


async def find_user(query: str) -> dict | None:
    query = query.strip().lstrip("@")
    if query.lstrip("-").isdigit():
        return await get_user(int(query))
    return await fetchone("SELECT * FROM users WHERE lower(username) = lower(?)", query)


async def update_user_profile(user_id: int, full_name: str, phone: str, address: str,
                              region_id: int | None = None) -> None:
    await execute(
        "UPDATE users SET full_name=?, phone=?, address=COALESCE(NULLIF(?, ''), address),"
        " region_id=COALESCE(?, region_id) WHERE id=?",
        full_name, phone, address, region_id, user_id,
    )


async def set_lang(user_id: int, lang: str) -> None:
    await execute("UPDATE users SET lang=? WHERE id=?", lang, user_id)


async def set_role(user_id: int, role: str) -> None:
    await execute("UPDATE users SET role=? WHERE id=?", role, user_id)


async def get_staff() -> list[dict]:
    return await fetchall("SELECT * FROM users WHERE role IN ('staff', 'manager') ORDER BY role, id")


async def set_blocked(user_id: int, blocked: bool) -> None:
    await execute("UPDATE users SET is_blocked=? WHERE id=?", int(blocked), user_id)


async def all_user_ids() -> list[int]:
    rows = await fetchall("SELECT id FROM users WHERE is_blocked = 0")
    return [r["id"] for r in rows]


# ---------------- sevimlilar ----------------

async def get_favorites(user_id: int) -> list[int]:
    rows = await fetchall("SELECT product_id FROM favorites WHERE user_id = ? ORDER BY created_at DESC", user_id)
    return [r["product_id"] for r in rows]


async def toggle_favorite(user_id: int, product_id: int) -> bool:
    """Qo'shilsa True, olib tashlansa False."""
    if await scalar("SELECT 1 FROM favorites WHERE user_id = ? AND product_id = ?", user_id, product_id):
        await execute("DELETE FROM favorites WHERE user_id = ? AND product_id = ?", user_id, product_id)
        return False
    await execute("INSERT INTO favorites(user_id, product_id, created_at) VALUES (?, ?, ?)",
                  user_id, product_id, now_str())
    return True


# ---------------- bot savati ----------------

async def cart_add(user_id: int, variant_id: int, qty: int) -> None:
    await execute(
        "INSERT INTO cart_items(user_id, variant_id, qty) VALUES (?, ?, ?)"
        " ON CONFLICT(user_id, variant_id) DO UPDATE SET qty = MIN(20, qty + excluded.qty)",
        user_id, variant_id, qty,
    )


async def cart_change(user_id: int, variant_id: int, delta: int) -> None:
    await db().execute(
        "UPDATE cart_items SET qty = MIN(20, qty + ?) WHERE user_id = ? AND variant_id = ?",
        (delta, user_id, variant_id),
    )
    await db().execute("DELETE FROM cart_items WHERE user_id = ? AND qty <= 0", (user_id,))
    await db().commit()


async def cart_clear(user_id: int) -> None:
    await execute("DELETE FROM cart_items WHERE user_id = ?", user_id)


async def cart_get(user_id: int) -> list[dict]:
    """Savat pozitsiyalari joriy narxlar bilan; sotuvda yo'qlari avtomatik olib tashlanadi."""
    from . import products
    from .catalog import variant_label, variant_price

    rows = await fetchall("SELECT * FROM cart_items WHERE user_id = ? ORDER BY rowid", user_id)
    items = []
    for r in rows:
        v = await products.get_variant(r["variant_id"])
        p = await products.get_product(v["product_id"]) if v else None
        if not v or not p or not products.sellable(p, v):
            await execute("DELETE FROM cart_items WHERE user_id = ? AND variant_id = ?", user_id, r["variant_id"])
            continue
        qty = min(r["qty"], v["stock"])
        price, old = variant_price(p, v)
        items.append({
            "variant_id": v["id"], "product_id": p["id"], "qty": qty, "stock": v["stock"],
            "name": p["name"], "variant_name": variant_label(p, v), "price": price, "old_price": old,
            "product": p, "variant": v,
        })
    return items


# ---------------- orders ----------------

async def generate_order_code() -> str:
    """Qisqa va o'qish oson ID: TZ-482917 (prefiks brend sozlamasidan)."""
    prefix = (await get_setting("order_prefix") or "TZ").upper()
    while True:
        code = f"{prefix}-{secrets.randbelow(900_000) + 100_000}"
        if not await scalar("SELECT 1 FROM orders WHERE code = ?", code):
            return code


ORDER_COLS = ("order_type", "customer_name", "phone", "region_id", "region_name", "delivery_eta", "address",
              "comment", "payment_method", "subtotal", "discount", "promo_code", "delivery_fee", "total", "lang")


async def create_order(user_id: int, data: dict, items: list[dict]) -> int:
    """Buyurtma va pozitsiyalarni bitta tranzaksiyada yozadi. Qoldiqni chaqiruvchi band qiladi."""
    ts = now_str()
    code = await generate_order_code()
    cols = ("code", "user_id", "status", "created_at", "updated_at") + ORDER_COLS
    values = (code, user_id, "new", ts, ts) + tuple(data[c] for c in ORDER_COLS)
    cur = await db().execute(f"INSERT INTO orders({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", values)
    order_id = cur.lastrowid
    await db().executemany(
        "INSERT INTO order_items(order_id, product_id, variant_id, name, variant, price, cost, qty, warranty_months)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(order_id, i["product_id"], i["variant_id"], i["name"], i["variant"], i["price"], i["cost"], i["qty"],
          i["warranty_months"]) for i in items],
    )
    await db().execute(
        "INSERT INTO order_status_log(order_id, status, by_user, at) VALUES (?, 'new', ?, ?)",
        (order_id, user_id, ts),
    )
    await db().commit()
    return order_id


ORDER_SELECT = (
    "SELECT o.*, COALESCE(s.full_name, s.first_name) AS staff_name FROM orders o"
    " LEFT JOIN users s ON s.id = o.staff_id"
)


async def get_order(order_id: int) -> dict | None:
    return await fetchone(ORDER_SELECT + " WHERE o.id = ?", order_id)


async def get_order_by_code(code: str) -> dict | None:
    return await fetchone(ORDER_SELECT + " WHERE o.code = ?", code.strip().upper())


async def find_order(query: str) -> dict | None:
    """Unikal kod (TZ-...), uning raqam qismi yoki ichki raqam bo'yicha qidiradi."""
    q = query.strip().lstrip("#")
    if q.isdigit():
        prefix = (await get_setting("order_prefix") or "TZ").upper()
        return await get_order_by_code(f"{prefix}-{q}") or await get_order(int(q))
    order = await get_order_by_code(q)
    if not order and len(q) >= 4:
        order = await fetchone(ORDER_SELECT + " WHERE o.code LIKE ? ORDER BY o.id DESC", f"%{q.upper()}%")
    return order


async def get_order_items(order_id: int) -> list[dict]:
    return await fetchall("SELECT * FROM order_items WHERE order_id = ? ORDER BY id", order_id)


async def set_item_serial(item_id: int, serial: str) -> None:
    await execute("UPDATE order_items SET serial = ? WHERE id = ?", serial.strip()[:64], item_id)


async def get_order_log(order_id: int) -> list[dict]:
    return await fetchall(
        "SELECT status, at, by_user FROM order_status_log WHERE order_id = ? ORDER BY id", order_id
    )


async def get_user_orders(user_id: int, limit: int = 20) -> list[dict]:
    return await fetchall(
        ORDER_SELECT + " WHERE o.user_id = ? ORDER BY o.id DESC LIMIT ?", user_id, limit
    )


async def get_orders_by_status(statuses: tuple[str, ...], limit: int = 30, staff_id: int | None = None) -> list[dict]:
    marks = ",".join("?" * len(statuses))
    sql = ORDER_SELECT + f" WHERE o.status IN ({marks})"
    args: list = list(statuses)
    if staff_id is not None:
        sql += " AND o.staff_id = ?"
        args.append(staff_id)
    return await fetchall(sql + " ORDER BY o.id DESC LIMIT ?", *args, limit)


async def get_active_orders() -> list[dict]:
    return await get_orders_by_status(ACTIVE_STATUSES, limit=50)


async def set_order_status(order_id: int, status: str, by_user: int | None, cancel_reason: str | None = None) -> None:
    ts = now_str()
    if status == "accepted" and by_user:
        await db().execute(
            "UPDATE orders SET status=?, staff_id=?, updated_at=? WHERE id=?",
            (status, by_user, ts, order_id),
        )
    else:
        await db().execute(
            "UPDATE orders SET status=?, cancel_reason=COALESCE(?, cancel_reason), updated_at=? WHERE id=?",
            (status, cancel_reason, ts, order_id),
        )
    await db().execute(
        "INSERT INTO order_status_log(order_id, status, by_user, at) VALUES (?, ?, ?, ?)",
        (order_id, status, by_user, ts),
    )
    await db().commit()


async def save_order_message(order_id: int, chat_id: int, message_id: int) -> None:
    await execute(
        "INSERT INTO order_messages(order_id, chat_id, message_id) VALUES (?, ?, ?)",
        order_id, chat_id, message_id,
    )


async def get_order_messages(order_id: int) -> list[dict]:
    return await fetchall("SELECT * FROM order_messages WHERE order_id = ?", order_id)


async def delete_order(order_id: int) -> list[dict]:
    """Buyurtmani butunlay o'chiradi (faqat menejer). Xodimlardagi xabarlar ro'yxatini qaytaradi."""
    messages = await get_order_messages(order_id)
    for table in ("order_items", "order_status_log", "order_messages", "reviews", "order_media", "order_chat",
                  "tickets"):
        await db().execute(f"DELETE FROM {table} WHERE order_id = ?", (order_id,))
    await db().execute("DELETE FROM orders WHERE id = ?", (order_id,))
    await db().commit()
    return messages


# ---------------- promo-kodlar ----------------

PROMO_FIELDS = {
    "code", "kind", "value", "min_order", "max_discount", "usage_limit", "per_user_limit",
    "first_order_only", "starts_at", "ends_at", "is_active",
}


async def get_promos() -> list[dict]:
    return await fetchall(
        "SELECT p.*, (SELECT COUNT(*) FROM orders o WHERE o.promo_code = p.code AND o.status != 'cancelled') AS used,"
        " (SELECT COALESCE(SUM(o.discount), 0) FROM orders o WHERE o.promo_code = p.code AND o.status != 'cancelled')"
        " AS discount_sum FROM promo_codes p ORDER BY p.is_active DESC, p.id DESC"
    )


async def get_promo(promo_id: int) -> dict | None:
    return await fetchone("SELECT * FROM promo_codes WHERE id = ?", promo_id)


async def get_promo_by_code(code: str) -> dict | None:
    return await fetchone("SELECT * FROM promo_codes WHERE code = ?", code.strip().upper())


async def add_promo(**fields) -> int:
    assert set(fields) <= PROMO_FIELDS
    fields["code"] = fields["code"].strip().upper()
    cols = ", ".join(fields) + ", created_at"
    marks = ", ".join("?" * (len(fields) + 1))
    return await execute(f"INSERT INTO promo_codes({cols}) VALUES ({marks})", *fields.values(), now_str())


async def update_promo(promo_id: int, **fields) -> None:
    await update_row("promo_codes", promo_id, fields, PROMO_FIELDS)


async def delete_promo(promo_id: int) -> None:
    await execute("DELETE FROM promo_codes WHERE id = ?", promo_id)


async def promo_uses(code: str, user_id: int | None = None) -> int:
    sql = "SELECT COUNT(*) FROM orders WHERE promo_code = ? AND status != 'cancelled'"
    args: list = [code]
    if user_id is not None:
        sql += " AND user_id = ?"
        args.append(user_id)
    return await scalar(sql, *args)


async def user_order_count(user_id: int) -> int:
    return await scalar("SELECT COUNT(*) FROM orders WHERE user_id = ? AND status != 'cancelled'", user_id)


# ---------------- baholar ----------------

async def add_review(order_id: int, user_id: int, rating: int, comment: str = "") -> bool:
    """Har bir buyurtmaga bitta baho. Yangi qo'shilsa True."""
    cur = await db().execute(
        "INSERT OR IGNORE INTO reviews(order_id, user_id, rating, comment, created_at) VALUES (?, ?, ?, ?, ?)",
        (order_id, user_id, rating, comment, now_str()),
    )
    await db().commit()
    return cur.rowcount > 0


async def set_review_comment(order_id: int, comment: str) -> None:
    await execute("UPDATE reviews SET comment = ? WHERE order_id = ?", comment[:500], order_id)


async def get_review(order_id: int) -> dict | None:
    return await fetchone("SELECT * FROM reviews WHERE order_id = ?", order_id)


async def get_reviews(limit: int = 10, max_rating: int | None = None) -> list[dict]:
    sql = ("SELECT r.*, o.code, COALESCE(u.full_name, u.first_name) AS name FROM reviews r"
           " JOIN orders o ON o.id = r.order_id LEFT JOIN users u ON u.id = r.user_id")
    args: list = []
    if max_rating is not None:
        sql += " WHERE r.rating <= ?"
        args.append(max_rating)
    return await fetchall(sql + " ORDER BY r.id DESC LIMIT ?", *args, limit)


async def review_stats(since: str | None = None) -> dict:
    where, args = ("WHERE created_at >= ?", [since]) if since else ("", [])
    row = await fetchone(f"SELECT COUNT(*) c, COALESCE(AVG(rating), 0) avg FROM reviews {where}", *args)
    dist = {r["rating"]: r["c"] for r in await fetchall(
        f"SELECT rating, COUNT(*) c FROM reviews {where} GROUP BY rating", *args)}
    return {"count": row["c"], "avg": round(row["avg"], 2), "dist": dist}


# ---------------- statistika ----------------

async def stats(since: str | None) -> dict:
    """Sotuv ko'rsatkichlari: tushum, foyda (tannarx bo'yicha), holatlar, top mahsulot va brendlar."""
    where, args = ("WHERE created_at >= ?", [since]) if since else ("", [])
    and_ = "AND" if since else "WHERE"
    o_since = "AND o.created_at >= ?" if since else ""
    total_orders = await scalar(f"SELECT COUNT(*) FROM orders {where}", *args)
    by_status = {
        r["status"]: r["c"]
        for r in await fetchall(f"SELECT status, COUNT(*) c FROM orders {where} GROUP BY status", *args)
    }
    revenue = await scalar(
        f"SELECT COALESCE(SUM(total), 0) FROM orders {where} {and_} status = 'delivered'", *args
    )
    sold = await fetchone(
        "SELECT COALESCE(SUM(i.qty), 0) units, COALESCE(SUM(i.qty * i.price), 0) goods,"
        " COALESCE(SUM(i.qty * i.cost), 0) cost FROM order_items i JOIN orders o ON o.id = i.order_id"
        f" WHERE o.status = 'delivered' {o_since}", *args,
    )
    discounts = await scalar(
        f"SELECT COALESCE(SUM(discount), 0) FROM orders {where} {and_} status = 'delivered'", *args
    )
    delivered = by_status.get("delivered", 0)
    pending_sum = await scalar(
        f"SELECT COALESCE(SUM(total), 0) FROM orders {where} {and_} status IN "
        f"({','.join('?' * len(ACTIVE_STATUSES))})", *args, *ACTIVE_STATUSES,
    )
    top = await fetchall(
        "SELECT i.name, SUM(i.qty) qty, SUM(i.qty * i.price) amount FROM order_items i"
        " JOIN orders o ON o.id = i.order_id"
        f" WHERE o.status = 'delivered' {o_since} GROUP BY i.name ORDER BY qty DESC, amount DESC LIMIT 5",
        *args,
    )
    top_brands = await fetchall(
        "SELECT COALESCE(b.name, '—') name, SUM(i.qty) qty, SUM(i.qty * i.price) amount FROM order_items i"
        " JOIN orders o ON o.id = i.order_id LEFT JOIN products p ON p.id = i.product_id"
        " LEFT JOIN brands b ON b.id = p.brand_id"
        f" WHERE o.status = 'delivered' {o_since} GROUP BY b.id ORDER BY amount DESC LIMIT 5",
        *args,
    )
    by_type = {
        r["order_type"]: r["c"]
        for r in await fetchall(
            f"SELECT order_type, COUNT(*) c FROM orders {where} {and_} status != 'cancelled' GROUP BY order_type",
            *args)
    }
    purchases = await scalar(f"SELECT COALESCE(SUM(total), 0) FROM purchases {where}", *args)
    return {
        "total_orders": total_orders,
        "by_status": by_status,
        "by_type": by_type,
        "revenue": revenue,
        "units": sold["units"],
        "cogs": sold["cost"],
        "gross_profit": sold["goods"] - discounts - sold["cost"],
        "promo_sum": discounts,
        "avg_check": revenue // delivered if delivered else 0,
        "pending_sum": pending_sum,
        "purchases": purchases,
        "top": top,
        "top_brands": top_brands,
        "new_users": await scalar(f"SELECT COUNT(*) FROM users {where}", *args),
        "customers": await scalar(f"SELECT COUNT(DISTINCT user_id) FROM orders {where}", *args),
        "users_total": await scalar("SELECT COUNT(*) FROM users"),
        "rating": await review_stats(since),
    }


async def daily_revenue(days: int = 7) -> list[dict]:
    return await fetchall(
        "SELECT substr(o.created_at, 1, 10) day, COUNT(DISTINCT o.id) orders, COALESCE(SUM(o.total), 0) amount,"
        " COALESCE((SELECT SUM(i.qty * (i.price - i.cost)) FROM order_items i JOIN orders o2 ON o2.id = i.order_id"
        "   WHERE o2.status = 'delivered' AND substr(o2.created_at, 1, 10) = substr(o.created_at, 1, 10)), 0)"
        " - COALESCE(SUM(o.discount), 0) profit"
        " FROM orders o WHERE o.status = 'delivered' AND o.created_at >= date('now', '+5 hours', ?)"
        " GROUP BY day ORDER BY day DESC",
        f"-{days - 1} days",
    )


async def staff_stats(since: str | None) -> list[dict]:
    extra = "AND o.created_at >= ?" if since else ""
    args = [since] if since else []
    return await fetchall(
        "SELECT COALESCE(u.full_name, u.first_name) name, COUNT(*) c, COALESCE(SUM(o.total), 0) amount"
        " FROM orders o JOIN users u ON u.id = o.staff_id"
        f" WHERE o.status = 'delivered' {extra} GROUP BY o.staff_id ORDER BY c DESC",
        *args,
    )


async def all_orders_for_export(since: str | None) -> list[dict]:
    where, args = ("WHERE o.created_at >= ?", [since]) if since else ("", [])
    return await fetchall(
        ORDER_SELECT.replace("SELECT o.*,", "SELECT o.*, (SELECT GROUP_CONCAT(i.name || "
                             "CASE WHEN i.variant != '' THEN ' (' || i.variant || ')' ELSE '' END"
                             " || ' x' || i.qty, '; ') FROM order_items i WHERE i.order_id = o.id) AS items,"
                             " (SELECT COALESCE(SUM(i.qty * i.cost), 0) FROM order_items i"
                             " WHERE i.order_id = o.id) AS cost,")
        + f" {where} ORDER BY o.id",
        *args,
    )
