"""Mahsulot ko'rinishi: narx (chegirma bilan), variant nomi, belgilar, tarjima — bot va Mini App uchun umumiy.

Bu modul bazaga murojaat qilmaydi: products.py bergan lug'atlar bilan ishlaydi.
"""
from datetime import datetime

from .utils import TZ, now

BADGES = {
    "hit": {"uz": "🔥 Hit", "ru": "🔥 Хит"},
    "new": {"uz": "✨ Yangi", "ru": "✨ Новинка"},
    "top": {"uz": "⭐ Top", "ru": "⭐ Топ"},
}


def norm_lang(lang: str | None) -> str:
    return "ru" if (lang or "").lower().startswith("ru") else "uz"


def badges_of(p: dict) -> list[str]:
    return [b for b in (p.get("badges") or "").split(",") if b in BADGES]


def discount_active(p: dict) -> int:
    """Faol chegirma foizi (0 — chegirma yo'q yoki muddati tugagan)."""
    pct = int(p.get("discount_percent") or 0)
    if pct <= 0:
        return 0
    until = p.get("discount_until") or ""
    if until:
        try:
            if datetime.strptime(until, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ) <= now():
                return 0
        except ValueError:
            return 0
    return min(pct, 90)


def apply_percent(price: int, pct: int) -> int:
    """Chegirmali narx, 1000 so'mgacha yaxlitlangan."""
    return int(round(price * (100 - pct) / 100 / 1000)) * 1000


def variant_price(p: dict, v: dict) -> tuple[int, int | None]:
    """(joriy narx, eski narx yoki None)."""
    base = int(v["price"])
    pct = discount_active(p)
    if not pct:
        return base, None
    return apply_percent(base, pct), base


def product_name(p: dict, lang: str) -> str:
    return (p.get("name_ru") or p["name"]) if lang == "ru" else p["name"]


def product_desc(p: dict, lang: str) -> str:
    return (p.get("description_ru") or p.get("description") or "") if lang == "ru" else (p.get("description") or "")


def category_name(c: dict, lang: str) -> str:
    return (c.get("name_ru") or c["name"]) if lang == "ru" else c["name"]


def option_name(o: dict, lang: str) -> str:
    return (o.get("name_ru") or o["name"]) if lang == "ru" else o["name"]


def option_value(o: dict, value: str, lang: str) -> str:
    """Variant qiymatining tarjimasi (values_ru shu tartibda bo'lsa)."""
    if lang == "ru":
        ru = o.get("values_ru") or []
        values = o.get("values") or []
        if value in values and values.index(value) < len(ru) and ru[values.index(value)]:
            return ru[values.index(value)]
    return value


def variant_label(p: dict, v: dict, lang: str = "uz") -> str:
    """«Qora, 256 GB» — variantning qisqa nomi (bitta variantli mahsulotda bo'sh)."""
    opts = p.get("options") or []
    parts = [option_value(opts[i], val, lang) if i < len(opts) else val for i, val in enumerate(v.get("vals") or [])]
    return ", ".join(x for x in parts if x)


def stock_state(stock: int, low: int) -> str:
    if stock <= 0:
        return "out"
    return "low" if stock <= low else "in"


def badge_labels(p: dict, lang: str) -> list[str]:
    labels = [BADGES[b][lang] for b in badges_of(p)]
    pct = discount_active(p)
    if pct:
        labels.insert(0, f"-{pct}%")
    return labels


def specs_public(p: dict, lang: str) -> list[dict]:
    out = []
    for s in p.get("specs") or []:
        k = (s.get("k_ru") or s.get("k")) if lang == "ru" else s.get("k")
        v = (s.get("v_ru") or s.get("v")) if lang == "ru" else s.get("v")
        if k and v:
            out.append({"k": k, "v": v})
    return out


def warranty_text(months: int, lang: str) -> str:
    if not months:
        return ""
    if months % 12 == 0:
        years = months // 12
        return f"{years} {'год' if years == 1 else 'года' if years < 5 else 'лет'}" if lang == "ru" else f"{years} yil"
    return f"{months} мес." if lang == "ru" else f"{months} oy"


def product_card(p: dict, lang: str, low: int = 3) -> dict:
    """Ro'yxat uchun qisqa kartochka. p — products.get_product() (variants, images, brand bilan)."""
    variants = [v for v in p["variants"] if v["is_active"]]
    selling = [v for v in variants if v["stock"] > 0] or variants
    cheapest = min(selling, key=lambda v: v["price"]) if selling else None
    price, old = variant_price(p, cheapest) if cheapest else (0, None)
    stock = sum(v["stock"] for v in variants)
    return {
        "id": p["id"],
        "name": product_name(p, lang),
        "brand": (p.get("brand") or {}).get("name") or "",
        "brand_id": p.get("brand_id"),
        "category_id": p["category_id"],
        "image": p["images"][0]["path"] if p["images"] else "",
        "price": price,
        "old_price": old,
        "price_from": len({v["price"] for v in variants}) > 1,
        "discount": discount_active(p),
        "badges": badges_of(p),
        "stock": stock_state(stock, low),
        "colors": len(p["options"][0]["values"]) if p["options"] and _is_color(p["options"][0]) else 0,
        "sold": p.get("sold", 0),
        "created_at": p["created_at"],
        "search": " ".join([p["name"], p.get("name_ru") or "", (p.get("brand") or {}).get("name") or ""]).lower(),
    }


def _is_color(o: dict) -> bool:
    return o.get("name", "").lower() in ("rang", "color", "цвет")


def product_full(p: dict, lang: str, low: int = 3) -> dict:
    """Mahsulot sahifasi uchun to'liq ma'lumot."""
    card = product_card(p, lang, low)
    options = [{
        "name": option_name(o, lang),
        "is_color": _is_color(o),
        "values": [{"value": val, "label": option_value(o, val, lang)} for val in o.get("values") or []],
    } for o in p["options"]]
    variants = []
    for v in p["variants"]:
        if not v["is_active"]:
            continue
        price, old = variant_price(p, v)
        variants.append({
            "id": v["id"], "vals": v["vals"], "price": price, "old_price": old,
            "stock": stock_state(v["stock"], low), "left": v["stock"] if 0 < v["stock"] <= low else None,
            "label": variant_label(p, v, lang),
        })
    return {
        **card,
        "description": product_desc(p, lang),
        "options": options,
        "variants": variants,
        "images": [{"path": i["path"], "color": i["color"]} for i in p["images"]],
        "specs": specs_public(p, lang),
        "warranty_months": p["warranty_months"],
        "warranty": warranty_text(p["warranty_months"], lang),
    }
