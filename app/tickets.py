"""Murojaatlar: buyurtmani qaytarish (return) va muammo haqida xabar (issue).

Qaytarish — faqat yetkazilgan buyurtma uchun, admin belgilagan muddat ichida, bir marta; sabab va kamida bitta
rasm shart. Xodim mijoz bilan telefon orqali bog'lanib, tasdiqlaydi (buyurtma "qaytarildi") yoki rad etadi.
Muammo xabari — istalgan buyurtma uchun; bir vaqtda bitta ochiq murojaat (flooddan himoya).
"""
import json
from datetime import datetime, timedelta

from . import db
from .utils import ACTIVE_STATUSES, TZ, now, now_str

KINDS = ("return", "issue")
MAX_PHOTOS = 5
TICKET_SELECT = (
    "SELECT t.*, o.code, o.customer_name, o.phone, o.total, o.status AS order_status, o.order_type,"
    " COALESCE(u.full_name, u.first_name) AS handler FROM tickets t JOIN orders o ON o.id = t.order_id"
    " LEFT JOIN users u ON u.id = t.handled_by"
)


def _ticket(r: dict | None) -> dict | None:
    if r:
        r["photos"] = json.loads(r.get("photos") or "[]")
    return r


def chat_open(order: dict) -> bool:
    return order["status"] in ACTIVE_STATUSES


async def delivered_at(order: dict) -> datetime | None:
    at = await db.scalar("SELECT MIN(at) FROM order_status_log WHERE order_id = ? AND status = 'delivered'",
                         order["id"])
    return datetime.strptime(at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ) if at else None


async def return_until(order: dict) -> datetime | None:
    """Qaytarish muddati tugaydigan vaqt (qaytarib bo'lmasa None)."""
    days = int(await db.get_setting("return_days") or 0)
    if order["status"] != "delivered" or days <= 0:
        return None
    done = await delivered_at(order)
    return done + timedelta(days=days) if done else None


async def can_return(order: dict) -> bool:
    until = await return_until(order)
    if not until or now() > until:
        return False
    return not await db.scalar("SELECT 1 FROM tickets WHERE order_id = ? AND kind = 'return'", order["id"])


async def open_ticket(order_id: int) -> dict | None:
    return _ticket(await db.fetchone(TICKET_SELECT + " WHERE t.order_id = ? AND t.status = 'open' ORDER BY t.id DESC",
                                     order_id))


async def order_tickets(order_id: int) -> list[dict]:
    return [_ticket(r) for r in await db.fetchall(TICKET_SELECT + " WHERE t.order_id = ? ORDER BY t.id", order_id)]


async def create(order: dict, kind: str, reason: str, photos: list[str]) -> int:
    assert kind in KINDS
    ts = now_str()
    return await db.execute(
        "INSERT INTO tickets(order_id, user_id, kind, reason, photos, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        order["id"], order["user_id"], kind, reason.strip()[:2000], json.dumps(photos[:MAX_PHOTOS]), ts, ts,
    )


async def get(ticket_id: int) -> dict | None:
    return _ticket(await db.fetchone(TICKET_SELECT + " WHERE t.id = ?", ticket_id))


async def listing(status: str = "open", limit: int = 200) -> list[dict]:
    sql, args = TICKET_SELECT, []
    if status in ("open", "approved", "rejected", "resolved"):
        sql += " WHERE t.status = ?"
        args.append(status)
    return [_ticket(r) for r in await db.fetchall(sql + " ORDER BY t.status = 'open' DESC, t.id DESC LIMIT ?",
                                                  *args, limit)]


async def open_count() -> int:
    return await db.scalar("SELECT COUNT(*) FROM tickets WHERE status = 'open'")


async def set_status(ticket_id: int, status: str, by_user: int | None, note: str = "") -> None:
    await db.execute("UPDATE tickets SET status = ?, note = ?, handled_by = ?, updated_at = ? WHERE id = ?",
                     status, note.strip()[:500], by_user, now_str(), ticket_id)
