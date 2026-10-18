"""Kartaga o'tkazma orqali to'lov: mijoz chek yuboradi, menejer tekshirib tasdiqlaydi yoki rad etadi."""
from __future__ import annotations

from . import db
from .utils import PAY_STATUS_LABELS, now_str

# '' — naqd; await — chek kutilmoqda; review — chek tekshirilmoqda; paid — to'landi; rejected — rad etildi
PAY_LABELS = {k: v[:2] + v[2:].capitalize() for k, v in PAY_STATUS_LABELS.items()}
CAN_UPLOAD = ("await", "rejected")


class PaymentError(Exception):
    pass


def card_info(s: dict) -> dict | None:
    """Sozlamalardan karta rekvizitlari (yoqilgan va raqam kiritilgan bo'lsa)."""
    number = (s.get("card_number") or "").strip()
    if s.get("card_enabled", "0") != "1" or not number:
        return None
    return {"number": number, "holder": (s.get("card_holder") or "").strip(), "bank": (s.get("card_bank") or "").strip()}


def format_number(number: str) -> str:
    digits = "".join(ch for ch in number if ch.isdigit())
    return " ".join(digits[i:i + 4] for i in range(0, len(digits), 4)) if len(digits) >= 12 else number


def can_upload(order: dict) -> bool:
    return (order.get("payment_method") == "card" and order.get("pay_status") in CAN_UPLOAD
            and order.get("status") not in ("cancelled", "returned"))


async def submit_receipt(order: dict, path: str) -> dict:
    if not can_upload(order):
        raise PaymentError("e_receipt_closed")
    await db.execute("UPDATE orders SET pay_status = 'review', pay_receipt = ?, pay_note = '', updated_at = ? "
                     "WHERE id = ? AND pay_status IN ('await', 'rejected')", path, now_str(), order["id"])
    return await db.get_order(order["id"])


async def decide(order: dict, approve: bool, by_user: int | None, note: str = "") -> dict:
    if order.get("pay_status") != "review":
        raise PaymentError("e_receipt_not_review")
    note = (note or "").strip()[:300]
    if not approve and len(note) < 3:
        raise PaymentError("e_reject_reason")
    await db.execute("UPDATE orders SET pay_status = ?, pay_note = ?, pay_checked_by = ?, pay_at = ?, updated_at = ? "
                     "WHERE id = ? AND pay_status = 'review'",
                     "paid" if approve else "rejected", "" if approve else note, by_user, now_str(), now_str(),
                     order["id"])
    return await db.get_order(order["id"])


async def review_count() -> int:
    return int(await db.scalar("SELECT COUNT(*) FROM orders WHERE pay_status = 'review'") or 0)
