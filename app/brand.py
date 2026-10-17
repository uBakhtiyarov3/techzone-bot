"""Do'kon brendi (white-label): nom, shior, logo, rang, kontaktlar.

Hammasi `settings` jadvalida saqlanadi va admin paneldan o'zgaradi. Bot matnlaridagi `{shop}`
o'zgaruvchisi do'kon nomiga almashtiriladi — boshqa do'konga moslash uchun kodga tegish shart emas.
"""
import re

# Tez-tez kerak bo'ladigan qiymat xotirada (i18n.t har chaqiruvda bazaga murojaat qilmasligi uchun)
SHOP = {"name": "Tech.Zone"}

BRAND_KEYS = ("shop_name", "shop_tagline", "shop_logo", "shop_mark", "shop_banner", "brand_color", "order_prefix",
              "about_uz", "about_ru", "instagram", "telegram_channel", "website")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def shop_name() -> str:
    return SHOP["name"]


def public_brand(s: dict) -> dict:
    """Mini App va admin panel uchun brend ma'lumotlari."""
    color = s.get("brand_color") or "#E0382B"
    return {
        "name": s.get("shop_name") or "Tech.Zone",
        "tagline": s.get("shop_tagline") or "",
        "logo": s.get("shop_logo") or "",
        "mark": s.get("shop_mark") or "",
        "color": color if HEX_RE.match(color) else "#E0382B",
        "about": {"uz": s.get("about_uz") or "", "ru": s.get("about_ru") or ""},
        "instagram": s.get("instagram") or "",
        "telegram": s.get("telegram_channel") or "",
        "website": s.get("website") or "",
        "phone": s.get("phone") or "",
        "address": s.get("shop_address") or "",
        "map_url": s.get("shop_map_url") or "",
    }


def social_url(kind: str, value: str) -> str:
    """'@techzone' yoki to'liq havola -> to'liq havola."""
    value = (value or "").strip()
    if not value or value.startswith("http"):
        return value
    handle = value.lstrip("@")
    return {"instagram": f"https://instagram.com/{handle}", "telegram": f"https://t.me/{handle}"}.get(kind, value)
