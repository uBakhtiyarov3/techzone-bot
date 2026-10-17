"""Ombor: qoldiqni band qilish/qaytarish, kirim (xaridlar), tuzatishlar, harakatlar tarixi, "kelganda xabar berish".

Qoldiq faqat shu modul orqali o'zgaradi va har bir o'zgarish `stock_moves` ga yoziladi.
"""
import asyncio
import secrets

from . import db
from .utils import now_str

# Bitta ulanishda ishlaymiz: band qilish/qaytarish bir-biriga aralashmasligi uchun
STOCK_LOCK = asyncio.Lock()


class OutOfStock(Exception):
    def __init__(self, variant_id: int, left: int):
        super().__init__(variant_id)
        self.variant_id = variant_id
        self.left = left


async def _move(variant_id: int, delta: int, reason: str, ref: str = "", note: str = "",
                by_user: int | None = None) -> None:
    await db.db().execute(
        "INSERT INTO stock_moves(variant_id, delta, reason, ref, note, by_user, at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (variant_id, delta, reason, ref, note[:200], by_user, now_str()),
    )


async def adjust(variant_id: int, delta: int, reason: str = "adjust", ref: str = "", note: str = "",
                 by_user: int | None = None) -> bool:
    """Qoldiqni o'zgartiradi (manfiyga tushmaydi). Mahsulot qayta sotuvga chiqsa True."""
    before = await db.scalar("SELECT stock FROM variants WHERE id = ?", variant_id) or 0
    delta = max(delta, -before)
    if not delta:
        return False
    await db.db().execute("UPDATE variants SET stock = stock + ? WHERE id = ?", (delta, variant_id))
    await _move(variant_id, delta, reason, ref, note, by_user)
    await db.db().commit()
    return before <= 0 < before + delta


async def set_stock(variant_id: int, stock: int, note: str = "", by_user: int | None = None) -> bool:
    """Inventarizatsiya: qoldiqni aniq songa tenglashtiradi."""
    before = await db.scalar("SELECT stock FROM variants WHERE id = ?", variant_id) or 0
    return await adjust(variant_id, max(0, stock) - before, "adjust", note=note or "Inventarizatsiya", by_user=by_user)


async def reserve(items: list[dict], ref: str, by_user: int | None) -> None:
    """Buyurtma uchun qoldiqni ayiradi. Biror pozitsiya yetmasa hech narsa o'zgarmaydi (OutOfStock)."""
    done: list[tuple[int, int]] = []
    try:
        for it in items:
            cur = await db.db().execute(
                "UPDATE variants SET stock = stock - ? WHERE id = ? AND stock >= ?",
                (it["qty"], it["variant_id"], it["qty"]),
            )
            if cur.rowcount == 0:
                left = await db.scalar("SELECT stock FROM variants WHERE id = ?", it["variant_id"]) or 0
                raise OutOfStock(it["variant_id"], left)
            done.append((it["variant_id"], it["qty"]))
            await _move(it["variant_id"], -it["qty"], "order", ref, by_user=by_user)
        await db.db().commit()
    except Exception:
        await db.db().rollback()
        raise


async def release(order_id: int, ref: str, by_user: int | None, reason: str = "cancel") -> list[int]:
    """Bekor qilingan (yoki qaytarilgan) buyurtma qoldig'ini qaytaradi. Qayta sotuvga chiqqan variantlar."""
    restocked = []
    for it in await db.get_order_items(order_id):
        if not it["variant_id"]:
            continue
        before = await db.scalar("SELECT stock FROM variants WHERE id = ?", it["variant_id"])
        if before is None:
            continue
        await db.db().execute("UPDATE variants SET stock = stock + ? WHERE id = ?", (it["qty"], it["variant_id"]))
        await _move(it["variant_id"], it["qty"], reason, ref, by_user=by_user)
        if before <= 0:
            restocked.append(it["variant_id"])
    await db.db().commit()
    return restocked


# ---------------- kirim (xaridlar) ----------------

async def create_purchase(items: list[dict], supplier_id: int | None = None, note: str = "",
                          by_user: int | None = None) -> tuple[int, list[int]]:
    """Kirim: qoldiq oshadi, tannarx o'rtacha og'irlik bilan qayta hisoblanadi.
    items: [{variant_id, qty, cost}]. (purchase_id, qayta sotuvga chiqqan variantlar) qaytaradi."""
    code = f"K-{secrets.randbelow(900_000) + 100_000}"
    total = sum(i["qty"] * i["cost"] for i in items)
    cur = await db.db().execute(
        "INSERT INTO purchases(code, supplier_id, total, note, by_user, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (code, supplier_id, total, note[:300], by_user, now_str()),
    )
    purchase_id = cur.lastrowid
    restocked = []
    for it in items:
        v = await db.fetchone(
            "SELECT v.stock, v.cost, p.name, v.vals FROM variants v JOIN products p ON p.id = v.product_id"
            " WHERE v.id = ?", it["variant_id"])
        if not v:
            continue
        stock = max(0, v["stock"])
        new_cost = (stock * v["cost"] + it["qty"] * it["cost"]) // (stock + it["qty"])
        await db.db().execute("UPDATE variants SET stock = stock + ?, cost = ? WHERE id = ?",
                              (it["qty"], new_cost, it["variant_id"]))
        await db.db().execute(
            "INSERT INTO purchase_items(purchase_id, variant_id, name, qty, cost) VALUES (?, ?, ?, ?, ?)",
            (purchase_id, it["variant_id"], _variant_title(v), it["qty"], it["cost"]),
        )
        await _move(it["variant_id"], it["qty"], "purchase", code, note, by_user)
        if v["stock"] <= 0:
            restocked.append(it["variant_id"])
    await db.db().commit()
    return purchase_id, restocked


def _variant_title(v: dict) -> str:
    import json

    vals = ", ".join(json.loads(v.get("vals") or "[]"))
    return v["name"] + (f" ({vals})" if vals else "")


async def get_purchases(limit: int = 100) -> list[dict]:
    return await db.fetchall(
        "SELECT p.*, s.name AS supplier, (SELECT SUM(qty) FROM purchase_items WHERE purchase_id = p.id) AS units"
        " FROM purchases p LEFT JOIN suppliers s ON s.id = p.supplier_id ORDER BY p.id DESC LIMIT ?", limit)


async def get_purchase_items(purchase_id: int) -> list[dict]:
    return await db.fetchall("SELECT * FROM purchase_items WHERE purchase_id = ? ORDER BY id", purchase_id)


async def get_suppliers() -> list[dict]:
    return await db.fetchall(
        "SELECT s.*, (SELECT COUNT(*) FROM purchases WHERE supplier_id = s.id) AS purchases,"
        " (SELECT COALESCE(SUM(total), 0) FROM purchases WHERE supplier_id = s.id) AS amount"
        " FROM suppliers s ORDER BY s.name")


async def add_supplier(name: str, phone: str = "", note: str = "") -> int:
    return await db.execute("INSERT INTO suppliers(name, phone, note, created_at) VALUES (?, ?, ?, ?)",
                            name.strip()[:80], phone.strip()[:40], note.strip()[:300], now_str())


async def update_supplier(supplier_id: int, **fields) -> None:
    await db.update_row("suppliers", supplier_id, fields, {"name", "phone", "note"})


# ---------------- ko'rsatkichlar ----------------

STOCK_SELECT = (
    "SELECT v.id, v.product_id, v.vals, v.sku, v.price, v.cost, v.stock, v.is_active, p.name, p.is_active AS p_active,"
    " c.name AS category, b.name AS brand FROM variants v JOIN products p ON p.id = v.product_id"
    " LEFT JOIN categories c ON c.id = p.category_id LEFT JOIN brands b ON b.id = p.brand_id"
    " WHERE v.is_deleted = 0 AND p.is_deleted = 0"
)


async def stock_list(q: str = "", only_low: bool = False) -> list[dict]:
    import json

    sql, args = STOCK_SELECT, []
    if q:
        sql += " AND (p.name LIKE ? OR v.sku LIKE ? OR b.name LIKE ?)"
        args += [f"%{q}%"] * 3
    if only_low:
        sql += " AND v.is_active = 1 AND p.is_active = 1 AND v.stock <= ?"
        args.append(int(await db.get_setting("low_stock") or 3))
    rows = await db.fetchall(sql + " ORDER BY p.sort, p.id, v.sort, v.id", *args)
    for r in rows:
        r["vals"] = json.loads(r["vals"] or "[]")
    return rows


async def stock_value() -> dict:
    row = await db.fetchone(
        "SELECT COALESCE(SUM(v.stock), 0) units, COALESCE(SUM(v.stock * v.cost), 0) cost,"
        " COALESCE(SUM(v.stock * v.price), 0) retail FROM variants v JOIN products p ON p.id = v.product_id"
        " WHERE v.is_deleted = 0 AND p.is_deleted = 0 AND v.stock > 0")
    return dict(row)


async def moves(variant_id: int | None = None, limit: int = 200) -> list[dict]:
    sql = ("SELECT m.*, p.name, v.vals, COALESCE(u.full_name, u.first_name) AS user FROM stock_moves m"
           " JOIN variants v ON v.id = m.variant_id JOIN products p ON p.id = v.product_id"
           " LEFT JOIN users u ON u.id = m.by_user")
    args: list = []
    if variant_id:
        sql += " WHERE m.variant_id = ?"
        args.append(variant_id)
    return await db.fetchall(sql + " ORDER BY m.id DESC LIMIT ?", *args, limit)


# ---------------- kelganda xabar berish ----------------

async def subscribe_alert(user_id: int, variant_id: int) -> None:
    await db.execute("INSERT OR IGNORE INTO stock_alerts(user_id, variant_id, created_at) VALUES (?, ?, ?)",
                     user_id, variant_id, now_str())


async def has_alert(user_id: int, variant_id: int) -> bool:
    return bool(await db.scalar("SELECT 1 FROM stock_alerts WHERE user_id = ? AND variant_id = ?",
                                user_id, variant_id))


async def pop_alerts(variant_id: int) -> list[int]:
    rows = await db.fetchall("SELECT user_id FROM stock_alerts WHERE variant_id = ?", variant_id)
    await db.execute("DELETE FROM stock_alerts WHERE variant_id = ?", variant_id)
    return [r["user_id"] for r in rows]
