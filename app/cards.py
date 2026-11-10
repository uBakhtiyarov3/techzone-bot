"""Bot uchun brend uslubidagi rasm-kartalar (Pillow): buyurtma holati va katalog muqovalari.

Rasm brend sozlamalaridan (rang, belgi, nom) chiziladi — boshqa do'konga o'tkazilganda o'zi moslashadi.
Natija `uploads/cards/<hash>.jpg` da keshlanadi; bir xil ma'lumot uchun qayta chizilmaydi.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import config

log = logging.getLogger(__name__)

W, H = 1280, 640
BG = (10, 10, 11)
WHITE = (255, 255, 255)
MUTED = (158, 158, 168)
DIM = (86, 86, 96)
FONTS = Path(__file__).parent / "assets" / "fonts"
VERSION = "4"  # dizayn o'zgarsa — kesh yangilanadi


@lru_cache(maxsize=64)
def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / f"{name}.otf"), size)


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = (hex_color or "#E0382B").lstrip("#")
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return 224, 56, 43


def _mix(a: tuple, b: tuple, k: float) -> tuple[int, int, int]:
    return tuple(round(x + (y - x) * k) for x, y in zip(a, b))


def _local(path: str) -> Path | None:
    if not path:
        return None
    f = config.uploads_dir / path.removeprefix("uploads/") if path.startswith("uploads/") else config.webapp_dir / path
    return f if f.exists() else None


def _fit(draw: ImageDraw.ImageDraw, text: str, name: str, size: int, max_w: int, min_size: int = 30):
    """Matn eniga sig'guncha shriftni kichraytiradi; baribir sig'masa — «…» bilan qisqartiradi."""
    while size > min_size and draw.textlength(text, font=font(name, size)) > max_w:
        size -= 4
    f = font(name, size)
    if draw.textlength(text, font=f) > max_w:
        while len(text) > 2 and draw.textlength(text + "…", font=f) > max_w:
            text = text[:-1]
        text = text.rstrip() + "…"
    return text, f


def _canvas(brand: tuple, glow_at: tuple[float, float] = (0.18, 0.1), w: int = W, h: int = H) -> Image.Image:
    """To'q fon, brend rangidagi yumshoq nur va nozik nuqtali to'r."""
    small = Image.new("RGB", (w // 8, h // 8), BG)
    d = ImageDraw.Draw(small)
    cx, cy = small.width * glow_at[0], small.height * glow_at[1]
    for r, k in ((small.width * 0.60, 0.13), (small.width * 0.38, 0.24), (small.width * 0.18, 0.40)):
        d.ellipse((cx - r, cy - r * 0.8, cx + r, cy + r * 0.8), fill=_mix(BG, brand, k))
    img = small.filter(ImageFilter.GaussianBlur(14)).resize((w, h), Image.BICUBIC)
    d = ImageDraw.Draw(img, "RGBA")
    for y in range(34, h, 34):
        for x in range(w // 2 + (y // 34 % 2) * 17, w, 34):
            d.ellipse((x - 1, y - 1, x + 1, y + 1), fill=(255, 255, 255, 22))
    return img


def _tile(path: str, size: int, angle: float = 0.0) -> Image.Image | None:
    """Mahsulot rasmi: yumaloq burchakli kvadrat plitka (ixtiyoriy burilgan), soyasi bilan."""
    f = _local(path)
    if not f:
        return None
    try:
        im = Image.open(f).convert("RGB")
    except OSError:
        return None
    side = min(im.size)
    im = im.crop(((im.width - side) // 2, (im.height - side) // 2, (im.width + side) // 2, (im.height + side) // 2))
    im = im.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 6, fill=255)
    pad = size // 5
    out = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
    shadow = Image.new("RGBA", out.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((pad, pad + size // 14, pad + size, pad + size + size // 14),
                                             radius=size // 6, fill=(0, 0, 0, 150))
    out.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(size // 14)))
    out.paste(im, (pad, pad), mask)
    return out.rotate(angle, resample=Image.BICUBIC, expand=True) if angle else out


def _tiles(img: Image.Image, paths: list[str], cx: int, cy: int, size: int) -> None:
    """Uchtagacha plitkani yelpig'ich qilib joylaydi (birinchisi oldinda, markazda)."""
    paths = [p for p in dict.fromkeys(paths) if _local(p)][:3]
    layout = {1: [(0, 0, 0, 1.0)], 2: [(0.42, 0.04, -8, 0.86), (-0.2, 0, 5, 1.0)],
              3: [(-0.62, 0.06, 9, 0.8), (0.62, 0.06, -9, 0.8), (0, 0, 0, 1.0)]}[max(1, len(paths))]
    order = paths[1:] + paths[:1] if len(paths) > 1 else paths  # asosiy rasm oxirida chiziladi (ustida)
    for path, (dx, dy, angle, scale) in zip(order, layout):
        tile = _tile(path, round(size * scale), angle)
        if tile:
            img.paste(tile, (round(cx + dx * size - tile.width / 2), round(cy + dy * size - tile.height / 2)), tile)


def _header(img: Image.Image, d: ImageDraw.ImageDraw, brand: dict, right: str = "") -> None:
    """Chapda — do'kon belgisi va nomi, o'ngda — kod/yorliq «tabletkasi»."""
    x, y = 64, 52
    mark = _local(brand.get("mark") or "")
    if mark:
        try:
            m = Image.open(mark).convert("RGBA")
            m.thumbnail((150, 62), Image.LANCZOS)
            img.paste(m, (x, y + (62 - m.height) // 2), m)
            x += m.width + 20
        except OSError:
            pass
    d.text((x, y + 31), brand.get("name") or "", font=font("Inter-SemiBold", 38), fill=WHITE, anchor="lm")
    if right:
        f = font("Inter-SemiBold", 36)
        tw = d.textlength(right, font=f)
        box = (W - 64 - tw - 56, y + 2, W - 64, y + 60)
        d.rounded_rectangle(box, radius=29, fill=(255, 255, 255, 30), outline=(255, 255, 255, 60), width=2)
        d.text(((box[0] + box[2]) / 2, y + 31), right, font=f, fill=WHITE, anchor="mm")


def _check(d: ImageDraw.ImageDraw, cx: float, cy: float, s: float, fill=WHITE) -> None:
    d.line([(cx - s * 0.5, cy + s * 0.02), (cx - s * 0.12, cy + s * 0.4), (cx + s * 0.55, cy - s * 0.38)],
           fill=fill, width=max(4, round(s * 0.24)), joint="curve")


def _cross(d: ImageDraw.ImageDraw, cx: float, cy: float, s: float, fill=WHITE) -> None:
    w = max(4, round(s * 0.24))
    d.line([(cx - s * 0.42, cy - s * 0.42), (cx + s * 0.42, cy + s * 0.42)], fill=fill, width=w)
    d.line([(cx - s * 0.42, cy + s * 0.42), (cx + s * 0.42, cy - s * 0.42)], fill=fill, width=w)


def draw_order_card(data: dict) -> Image.Image:
    """Buyurtma holati kartasi.

    data: brand{name, mark, color}, code, caption, title, subtitle, total, steps[str], reached (indeks yoki
    None — bekor qilingan/qaytarilgan), state (active | done | cancelled), images[path].
    """
    brand = _rgb(data["brand"].get("color"))
    state = data.get("state", "active")
    accent = (232, 76, 61) if state == "cancelled" else brand
    img = _canvas(accent if state != "cancelled" else (120, 30, 30))
    d = ImageDraw.Draw(img, "RGBA")  # RGB rasmda RGBA chizish — shaffof ranglar fon bilan aralashadi
    _header(img, d, data["brand"], data["code"])

    has_tiles = any(_local(p) for p in data.get("images") or [])
    text_w = 700 if has_tiles else W - 128
    d.text((66, 176), data["caption"].upper(), font=font("Inter-SemiBold", 28), fill=MUTED)
    title, f = _fit(d, data["title"], "InterDisplay-ExtraBold", 108, text_w, 56)
    d.text((62, 212), title, font=f, fill=WHITE)
    y = 212 + f.size + 22
    if data.get("subtitle"):
        sub, f2 = _fit(d, data["subtitle"], "Inter-Medium", 40, text_w, 28)
        d.text((66, y), sub, font=f2, fill=(214, 214, 222))
        y += f2.size + 14
    if data.get("total"):
        d.text((66, y), data["total"], font=font("Inter-Bold", 44), fill=WHITE)
    if has_tiles:
        _tiles(img, data["images"], 1010, 300, 250)

    steps, reached = data.get("steps") or [], data.get("reached")
    if steps and reached is not None:
        x0, x1, ty = 96, W - 96, 520
        n = len(steps)
        xs = [x0 + (x1 - x0) * i / (n - 1) for i in range(n)]
        d.line([(x0, ty), (x1, ty)], fill=(255, 255, 255, 40), width=8)
        if reached > 0:
            d.line([(x0, ty), (xs[reached], ty)], fill=accent, width=8)
        for i, (x, label) in enumerate(zip(xs, steps)):
            if i < reached or (i == reached and state == "done"):
                d.ellipse((x - 20, ty - 20, x + 20, ty + 20), fill=accent)
                _check(d, x, ty, 20)
            elif i == reached:
                d.ellipse((x - 34, ty - 34, x + 34, ty + 34), fill=accent + (70,))
                d.ellipse((x - 22, ty - 22, x + 22, ty + 22), fill=accent, outline=WHITE, width=5)
            else:
                d.ellipse((x - 14, ty - 14, x + 14, ty + 14), fill=BG, outline=(255, 255, 255, 80), width=4)
            anchor = "la" if i == 0 else "ra" if i == n - 1 else "ma"
            lx = x - 22 if i == 0 else x + 22 if i == n - 1 else x
            name = "Inter-Bold" if i == reached else "Inter-Medium"
            max_w = round((x1 - x0) / (n - 1)) - 16
            label, lf = _fit(d, label, name, 32, max_w, 22)
            d.text((lx, ty + 44), label, font=lf, anchor=anchor,
                   fill=WHITE if i <= reached else DIM)
    elif state == "cancelled":
        d.ellipse((66, 478, 150, 562), fill=accent)
        _cross(d, 108, 520, 40)
        if data.get("note"):
            note, nf = _fit(d, data["note"], "Inter-Medium", 34, W - 300, 26)
            d.text((178, 520), note, font=nf, fill=(230, 200, 200), anchor="lm")
    return img


def draw_cover(data: dict) -> Image.Image:
    """Katalog / kategoriya muqovasi: sarlavha, izoh va mahsulot rasmlaridan yelpig'ich.

    data: brand{...}, caption, title, subtitle, images[path], badge (ixtiyoriy).
    """
    h = 520
    brand = _rgb(data["brand"].get("color"))
    img = _canvas(brand, (0.1, 0.0), W, h)
    d = ImageDraw.Draw(img, "RGBA")
    _header(img, d, data["brand"], data.get("badge") or "")
    has_tiles = any(_local(p) for p in data.get("images") or [])
    text_w = 640 if has_tiles else W - 128
    if data.get("caption"):
        d.text((66, 196), data["caption"].upper(), font=font("Inter-SemiBold", 28), fill=_mix(brand, WHITE, 0.35))
    title, f = _fit(d, data["title"], "InterDisplay-ExtraBold", 104, text_w, 54)
    d.text((62, 234), title, font=f, fill=WHITE)
    if data.get("subtitle"):
        sub, f2 = _fit(d, data["subtitle"], "Inter-Medium", 40, text_w, 28)
        d.text((66, 234 + f.size + 26), sub, font=f2, fill=(214, 214, 222))
    if has_tiles:
        _tiles(img, data["images"], 990, 300, 262)
    return img


DRAWERS = {"order": draw_order_card, "cover": draw_cover}


def _key(kind: str, data: dict) -> str:
    stamps = []
    for p in list(data.get("images") or []) + [data.get("brand", {}).get("mark") or ""]:
        f = _local(p)
        stamps.append(f"{p}:{int(f.stat().st_mtime) if f else 0}")
    raw = json.dumps([VERSION, kind, data, stamps], ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(raw.encode()).hexdigest()[:20]


def render_sync(kind: str, data: dict) -> str:
    out_dir = config.uploads_dir / "cards"
    name = f"{kind}_{_key(kind, data)}.jpg"
    path = out_dir / name
    if not path.exists():
        out_dir.mkdir(parents=True, exist_ok=True)
        DRAWERS[kind](data).save(path, "JPEG", quality=88, optimize=True)
    return f"uploads/cards/{name}"


async def render(kind: str, data: dict) -> str:
    """Kartani chizadi (yoki keshdan oladi). Xato bo'lsa bo'sh satr — xabar rasmsiz yuboriladi."""
    try:
        return await asyncio.to_thread(render_sync, kind, data)
    except Exception as e:  # noqa: BLE001
        log.warning("Karta chizilmadi (%s): %s", kind, e)
        return ""
