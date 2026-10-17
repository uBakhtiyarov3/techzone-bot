"""Yetkazish hududlari: narx, bepul chegarasi va muddat (admin paneldan tahrirlanadi)."""
from . import db

REGION_FIELDS = {"name", "name_ru", "fee", "free_from", "days_min", "days_max", "sort", "is_active"}


async def get_regions(only_active: bool = False) -> list[dict]:
    sql = "SELECT * FROM regions" + (" WHERE is_active = 1" if only_active else "")
    return await db.fetchall(sql + " ORDER BY sort, id")


async def get_region(region_id: int) -> dict | None:
    return await db.fetchone("SELECT * FROM regions WHERE id = ?", region_id)


async def add_region(**fields) -> int:
    sort = await db.scalar("SELECT COALESCE(MAX(sort), 0) + 1 FROM regions")
    rid = await db.execute("INSERT INTO regions(name, sort) VALUES (?, ?)", fields["name"], sort)
    await update_region(rid, **{k: v for k, v in fields.items() if k != "name"})
    return rid


async def update_region(region_id: int, **fields) -> None:
    await db.update_row("regions", region_id, fields, REGION_FIELDS)


def region_name(r: dict, lang: str) -> str:
    return (r.get("name_ru") or r["name"]) if lang == "ru" else r["name"]


def eta_text(r: dict, lang: str) -> str:
    """«1–2 kun», «bugun–ertaga»."""
    lo, hi = int(r["days_min"]), int(r["days_max"])
    if hi <= 0:
        return "bugun" if lang == "uz" else "сегодня"
    if lo <= 0:
        return "bugun–ertaga" if lang == "uz" else "сегодня–завтра"
    span = f"{lo}–{hi}" if hi > lo else f"{lo}"
    return f"{span} kun" if lang == "uz" else f"{span} дн."


def delivery_fee(r: dict, subtotal: int) -> int:
    if r["free_from"] and subtotal >= r["free_from"]:
        return 0
    return int(r["fee"])


def region_public(r: dict, lang: str) -> dict:
    return {"id": r["id"], "name": region_name(r, lang), "fee": r["fee"], "free_from": r["free_from"],
            "eta": eta_text(r, lang)}
