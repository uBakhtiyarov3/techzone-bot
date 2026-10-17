"""Buyurtma chati (mijoz <-> do'kon) va holat rasmlari — ma'lumotlar qatlami."""
from . import db
from .utils import now_str


async def add_message(order_id: int, sender: str, user_id: int | None, text: str = "", path: str = "",
                      file_id: str = "") -> int:
    assert sender in ("customer", "staff")
    return await db.execute(
        "INSERT INTO order_chat(order_id, sender, user_id, text, path, file_id, at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        order_id, sender, user_id, text.strip()[:2000], path, file_id, now_str(),
    )


async def get_messages(order_id: int) -> list[dict]:
    return await db.fetchall(
        "SELECT c.*, COALESCE(u.full_name, u.first_name) AS name FROM order_chat c"
        " LEFT JOIN users u ON u.id = c.user_id WHERE c.order_id = ? ORDER BY c.id", order_id)


async def mark_seen(order_id: int, reader: str) -> None:
    """reader tomoni o'qidi: qarshi tomon xabarlari 'seen' bo'ladi."""
    other = "staff" if reader == "customer" else "customer"
    await db.execute("UPDATE order_chat SET seen = 1 WHERE order_id = ? AND sender = ? AND seen = 0", order_id, other)


async def unread_count(order_id: int, reader: str) -> int:
    other = "staff" if reader == "customer" else "customer"
    return await db.scalar("SELECT COUNT(*) FROM order_chat WHERE order_id = ? AND sender = ? AND seen = 0",
                           order_id, other)


async def unread_orders_for_staff() -> list[dict]:
    """Mijoz yozgan, hali javob berilmagan buyurtmalar (admin panel uchun)."""
    return await db.fetchall(
        "SELECT o.id, o.code, o.customer_name, COUNT(c.id) AS unread, MAX(c.at) AS last_at FROM order_chat c"
        " JOIN orders o ON o.id = c.order_id WHERE c.sender = 'customer' AND c.seen = 0"
        " GROUP BY o.id ORDER BY last_at DESC")


async def add_media(order_id: int, status: str, path: str = "", file_id: str = "", caption: str = "",
                    by_user: int | None = None) -> int:
    return await db.execute(
        "INSERT INTO order_media(order_id, status, path, file_id, caption, by_user, at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        order_id, status, path, file_id, caption.strip()[:500], by_user, now_str(),
    )


async def get_media(order_id: int) -> list[dict]:
    return await db.fetchall("SELECT * FROM order_media WHERE order_id = ? ORDER BY id", order_id)
