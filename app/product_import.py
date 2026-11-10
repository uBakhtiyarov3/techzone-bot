"""Mahsulotlarni Excel fayldan yaratish (shablon → to'ldirish → yuklash).

Har bir satr — bitta SKU (variant). "Guruh" ustuni bir xil bo'lgan satrlar bitta mahsulotga birlashadi.
Biror satrda xato bo'lsa hech narsa yaratilmaydi. Uzum Market shabloni (ruscha sarlavhalar) ham o'qiladi.
"""
from __future__ import annotations

import asyncio
import io
import ipaddress
import logging
import re
import socket
from urllib.parse import urlsplit

import aiohttp

from . import db, products

log = logging.getLogger(__name__)

MAX_ROWS = 500
MAX_FILE = 5 * 1024 * 1024
MAX_IMAGES = 10
MAX_IMAGE_BYTES = 10 * 1024 * 1024
SPEC_PREFIX = "xar:"
REQ, OPT = "✅ Majburiy", "🔘 Ixtiyoriy"

# (kalit, sarlavha, majburiy, izoh, namuna)
COLUMNS = [
    ("group", "Guruh (SKU birlashtirish)", False,
     "Bir xil guruh yozilgan satrlar bitta mahsulotga birlashadi (rang/xotira variantlari). Bo'sh bo'lsa — nom bo'yicha.",
     "iphone15"),
    ("name", "Nomi UZ", True, "Mahsulot nomi (80 belgigacha).", "iPhone 15"),
    ("name_ru", "Nomi RU", False, "Ruscha nomi. Bo'sh bo'lsa o'zbekchasi ko'rsatiladi.", "iPhone 15"),
    ("category", "Kategoriya", True, "Ro'yxatdan tanlang. Yangi nom yozilsa — kategoriya avtomatik yaratiladi.", ""),
    ("brand", "Brend", False, "Ro'yxatdan tanlang yoki yangi nom yozing.", "Apple"),
    ("description", "Tavsif UZ", False, "Mahsulot afzalliklari (2000 belgigacha).", "48 MP kamera, USB-C"),
    ("description_ru", "Tavsif RU", False, "Ruscha tavsif.", ""),
    ("warranty", "Kafolat (oy)", False, "0–120. Bo'sh — kafolatsiz.", 12),
    ("photos", "Rasm havolalari", False,
     "Rasm URL manzillari (https://...), vergul yoki yangi qator bilan. 3:4 nisbat, 10 tagacha. "
     "Rangli variantda shu satr rasmlari o'sha rangga biriktiriladi.", "https://example.com/iphone15-black.jpg"),
    ("sku", "SKU / artikul", False, "Ichki artikulingiz.", "IP15-BLK-128"),
    ("color", "Rang", False, "Variant rangi. Guruhdagi barcha satrlarda bo'lishi kerak.", "Qora"),
    ("size", "O'lcham / xotira", False, "Ikkinchi variant qiymati (128 GB, 45 mm, XL...).", "128 GB"),
    ("size_name", "2-variant nomi", False, "Ikkinchi variant turi nomi: Xotira, O'lcham... (standart: O'lcham).", "Xotira"),
    ("price", "Sotuv narxi (so'm)", True, "Xaridor ko'radigan narx.", 10990000),
    ("old_price", "Chegirmadan oldingi narx (so'm)", False, "Chegirma bo'lsa — eski narx (sotuv narxidan katta).", ""),
    ("stock", "Qoldiq (dona)", False, "Boshlang'ich ombor qoldig'i. Bo'sh — 0.", 5),
    ("cost", "Tannarx (so'm)", False, "Kelish narxi — foyda hisobi uchun.", 9000000),
    ("specs", "Xarakteristikalar", False, "Har qatorda «Nomi: qiymat». Masalan:\nEkran: 6.1\" OLED\nBatareya: 3349 mA/s",
     "Ekran: 6.1\" OLED\nKamera: 48 MP"),
]

# Sarlavha → kalit (o'zimizning va Uzum shablonidagi nomlar)
ALIASES = {
    "название товара ru": "name_ru", "название товара uz": "name", "группировка sku (до 100 символов)": "group",
    "название категории": "category", "бренд": "brand", "описание товара ru": "description_ru",
    "описание товара uz": "description", "ссылки на фото": "photos", "идентификатор от продавца": "sku",
    "цвет": "color", "размер": "size", "цена продажи (som)": "price", "цена до скидки (som)": "old_price",
}
ALIASES.update({re.sub(r"\s+", " ", title.lower()): key for key, title, *_ in COLUMNS})
NO_BRAND = {"", "отсутствует бренд", "brendsiz", "—", "-"}


def _norm(header) -> str:
    return re.sub(r"\s+", " ", str(header or "").replace("*", "").strip().lower())


# ---------------- shablon ----------------

def build_template(categories: list[dict], brands: list[dict], category: dict | None = None) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    ws = wb.active
    ws.title = "Tovarlar"
    spec_cols = [s["k"] for s in (category or {}).get("spec_template") or []]
    headers = [(title + ("*" if req else ""), req, hint, sample) for _, title, req, hint, sample in COLUMNS]
    headers += [(f"Xar: {k}", False, f"«{k}» xarakteristikasi qiymati.", "") for k in spec_cols]
    keys = [c[0] for c in COLUMNS]
    for col, (title, req, hint, sample) in enumerate(headers, 1):
        cell = ws.cell(1, col, title)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="E0382B" if req else "3A3A40")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        note = ws.cell(2, col, f"{REQ if req else OPT}\n\n{hint}")
        note.alignment = Alignment(wrap_text=True, vertical="top")
        note.font = Font(size=9, color="555555")
        if col <= len(keys) and keys[col - 1] == "category" and category:
            sample = category["name"]
        ws.cell(3, col, sample if sample != "" else None).alignment = Alignment(wrap_text=True, vertical="top")
        ws.column_dimensions[get_column_letter(col)].width = 34 if col <= len(keys) and keys[col - 1] in (
            "photos", "description", "description_ru", "specs") else 22
    ws.row_dimensions[1].height = 32
    ws.row_dimensions[2].height = 120
    ws.freeze_panes = "C3"

    lists = wb.create_sheet("Ro'yxatlar")
    lists.append(["Kategoriyalar", "Brendlar"])
    for i in range(max(len(categories), len(brands))):
        lists.append([categories[i]["name"] if i < len(categories) else None,
                      brands[i]["name"] if i < len(brands) else None])
    for key, letter, count in (("category", "A", len(categories)), ("brand", "B", len(brands))):
        if count:
            dv = DataValidation(type="list", formula1=f"='Ro''yxatlar'!${letter}$2:${letter}${count + 1}",
                                allow_blank=True, showErrorMessage=False)
            col = get_column_letter(keys.index(key) + 1)
            dv.add(f"{col}3:{col}{MAX_ROWS + 2}")
            ws.add_data_validation(dv)

    info = wb.create_sheet("Ko'rsatma")
    info.column_dimensions["A"].width = 110
    for line in (
        "Shablon bilan ishlash",
        "1. Har bir satr — bitta SKU (variant). 3-satrdagi namunani o'chirib, o'z tovarlaringizni yozing.",
        "2. Bitta mahsulotning rang/xotira variantlari uchun «Guruh» ustuniga bir xil qiymat yozing. "
        "Nom, kategoriya, brend, tavsif, kafolat va xarakteristikalar guruhning birinchi satridan olinadi.",
        "3. Yulduzcha (*) qo'yilgan ustunlar majburiy. Ustun nomlari va tartibini o'zgartirmang.",
        "4. Variantli mahsulotda «Rang» va/yoki «O'lcham / xotira» guruhning barcha satrlarida to'ldirilishi shart.",
        "5. Rasmlar: internetdagi to'g'ridan-to'g'ri havola (https://...jpg). 3:4 (tik) nisbat tavsiya qilinadi.",
        "6. Biror satrda xato bo'lsa hech narsa yaratilmaydi — xatolar ro'yxati ko'rsatiladi, tuzatib qayta yuklang.",
        f"7. Bitta faylda {MAX_ROWS} tagacha satr. Mavjud mahsulot nomi takrorlansa — xato sifatida ko'rsatiladi.",
    ):
        info.append([line])
    info["A1"].font = Font(bold=True, size=14)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


# ---------------- faylni o'qish ----------------

def read_rows(raw: bytes) -> list[tuple[int, dict]]:
    """Fayldan [(satr raqami, {kalit: qiymat, "_specs": {...}})]. Sarlavha satri avtomatik topiladi."""
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    except Exception:
        raise ValueError("Faylni o'qib bo'lmadi. Excel (.xlsx) shablonini yuklang.")
    ws = wb.worksheets[0]
    header, start = None, 0
    rows = ws.iter_rows(values_only=True)
    for i, row in enumerate(rows, 1):
        cols = {}
        for j, cell in enumerate(row):
            n = _norm(cell)
            if n in ALIASES:
                cols[j] = ALIASES[n]
            elif n.startswith(SPEC_PREFIX) and n[len(SPEC_PREFIX):].strip():
                cols[j] = "spec:" + str(cell).replace("*", "").split(":", 1)[1].strip()
        if "price" in cols.values() and ("name" in cols.values() or "name_ru" in cols.values()):
            header, start = cols, i
            break
        if i >= 6:
            break
    if not header:
        raise ValueError("Shablon sarlavhalari topilmadi. Shablonni qayta yuklab oling va ustun nomlarini o'zgartirmang.")
    out = []
    for i, row in enumerate(rows, start + 1):
        item: dict = {"_specs": {}}
        for j, key in header.items():
            val = row[j] if j < len(row) else None
            if val is None or str(val).strip() == "":
                continue
            if isinstance(val, float) and val.is_integer():
                val = int(val)
            if key.startswith("spec:"):
                item["_specs"][key[5:]] = str(val).strip()
            else:
                item[key] = str(val).strip() if not isinstance(val, int) else val
        first = next((str(v) for k, v in item.items() if k != "_specs"), "")
        if (len(item) == 1 and not item["_specs"]) or first.startswith(("✅", "🔘")):
            continue  # bo'sh satr yoki izoh satri
        out.append((i, item))
        if len(out) > MAX_ROWS:
            raise ValueError(f"Bitta faylda {MAX_ROWS} tagacha satr bo'lishi mumkin")
    return out


def _num(item: dict, key: str, label: str, lo: int, hi: int, errors: list, row: int, default=None):
    if key not in item:
        return default
    try:
        val = int(float(str(item[key]).replace(" ", "").replace(" ", "").replace(",", ".")))
    except ValueError:
        errors.append(f"{row}-satr: «{label}» son bo'lishi kerak")
        return default
    if not lo <= val <= hi:
        errors.append(f"{row}-satr: «{label}» {lo:,}–{hi:,} oralig'ida bo'lsin".replace(",", " "))
        return default
    return val


async def plan(rows: list[tuple[int, dict]]) -> tuple[list[dict], list[str], list[str]]:
    """Satrlarni mahsulotlarga yig'adi va tekshiradi. (mahsulotlar, xatolar, ogohlantirishlar)."""
    errors: list[str] = []
    warnings: list[str] = []
    if not rows:
        return [], ["Faylda to'ldirilgan satr yo'q"], []
    existing = {r["name"].strip().lower() for r in await db.fetchall("SELECT name FROM products WHERE is_deleted = 0")}
    groups: dict[str, list[tuple[int, dict]]] = {}
    for row, item in rows:
        name = str(item.get("name") or item.get("name_ru") or "").strip()
        if not name:
            errors.append(f"{row}-satr: mahsulot nomi kiritilmagan")
            continue
        item["name"] = name
        groups.setdefault(str(item.get("group") or name).strip().lower(), []).append((row, item))

    out = []
    for group_rows in groups.values():
        row0, first = group_rows[0]
        name = first["name"][:80]
        if name.lower() in existing:
            errors.append(f"{row0}-satr: «{name}» nomli mahsulot allaqachon bor")
        category = str(first.get("category") or "").split(">")[-1].strip()[:40]
        if not category:
            errors.append(f"{row0}-satr: kategoriya kiritilmagan")
        has_color = any(i.get("color") for _, i in group_rows)
        has_size = any(i.get("size") for _, i in group_rows)
        if len(group_rows) > 1 and not (has_color or has_size):
            errors.append(f"{row0}-satr: «{name}» bir necha satrda — variantlarni farqlash uchun «Rang» yoki "
                          "«O'lcham / xotira» ni to'ldiring (yoki «Guruh» ni har xil qiling)")
        if len(group_rows) > 60:
            errors.append(f"{row0}-satr: bitta mahsulotda 60 tagacha variant bo'lishi mumkin")
        options = []
        if has_color:
            options.append({"name": "Rang", "name_ru": "Цвет", "key": "color", "values": []})
        if has_size:
            size_name = str(first.get("size_name") or "O'lcham").strip()[:30]
            options.append({"name": size_name, "name_ru": "", "key": "size", "values": []})
        variants, images, seen, percent = [], [], set(), 0
        for row, item in group_rows:
            vals = []
            for o in options:
                val = str(item.get(o["key"]) or "").strip()[:40]
                if not val:
                    errors.append(f"{row}-satr: «{o['name']}» to'ldirilmagan (guruhdagi boshqa satrlarda bor)")
                elif val not in o["values"]:
                    o["values"].append(val)
                vals.append(val)
            if options and tuple(vals) in seen:
                errors.append(f"{row}-satr: bir xil variant ikki marta: {', '.join(vals)}")
            seen.add(tuple(vals))
            price = _num(item, "price", "Sotuv narxi", 1000, 1_000_000_000, errors, row)
            if price is None and "price" not in item:
                errors.append(f"{row}-satr: sotuv narxi kiritilmagan")
            old = _num(item, "old_price", "Chegirmadan oldingi narx", 1000, 1_000_000_000, errors, row)
            if price and old and old > price:
                pct = min(90, round((1 - price / old) * 100))
                if percent and abs(pct - percent) > 1:
                    warnings.append(f"{row}-satr: «{name}» variantlarida chegirma foizi har xil — {percent}% qo'llandi")
                percent = percent or pct
                price = old
            variants.append({
                "vals": vals, "price": price or 0, "sku": str(item.get("sku") or "")[:40], "is_active": True,
                "stock": _num(item, "stock", "Qoldiq", 0, 1_000_000, errors, row, 0),
                "cost": _num(item, "cost", "Tannarx", 0, 1_000_000_000, errors, row, 0),
            })
            for url in re.split(r"[\s,;]+", str(item.get("photos") or "")):
                if not url:
                    continue
                if not re.match(r"^https?://\S+$", url):
                    errors.append(f"{row}-satr: rasm havolasi noto'g'ri: {url[:60]}")
                elif url not in [u for u, _ in images] and len(images) < MAX_IMAGES:
                    images.append((url, vals[0] if has_color and vals else ""))
        specs = [{"k": k[:60], "k_ru": "", "v": v[:200], "v_ru": ""} for k, v in first["_specs"].items()]
        for line in str(first.get("specs") or "").splitlines():
            k, sep, v = line.partition(":")
            if sep and k.strip() and v.strip():
                specs.append({"k": k.strip()[:60], "k_ru": "", "v": v.strip()[:200], "v_ru": ""})
        brand = str(first.get("brand") or "").strip()[:40]
        out.append({
            "row": row0, "name": name, "name_ru": str(first.get("name_ru") or "")[:80], "category": category,
            "brand": "" if brand.lower() in NO_BRAND else brand,
            "description": str(first.get("description") or "")[:2000],
            "description_ru": str(first.get("description_ru") or "")[:2000],
            "warranty_months": _num(first, "warranty", "Kafolat (oy)", 0, 120, errors, row0, 0),
            "discount_percent": percent, "specs": specs[:60], "variants": variants, "images": images,
            "options": [{"name": o["name"], "name_ru": o["name_ru"], "values": o["values"],
                         "values_ru": [""] * len(o["values"])} for o in options],
        })
        existing.add(name.lower())
    return out, errors, warnings


# ---------------- rasm yuklab olish ----------------

async def fetch_image(url: str) -> bytes:
    """Rasmni URL dan oladi. Ichki tarmoq manzillari rad etiladi."""
    host = urlsplit(url).hostname or ""
    infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("ichki manzil")
    timeout = aiohttp.ClientTimeout(total=25)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, allow_redirects=False) as resp:
            if resp.status != 200:
                raise ValueError(f"HTTP {resp.status}")
            data = await resp.content.read(MAX_IMAGE_BYTES + 1)
            if len(data) > MAX_IMAGE_BYTES:
                raise ValueError("fayl juda katta")
            return data


async def create(plans: list[dict], by_user: int | None) -> tuple[int, int, list[str]]:
    """Tekshirilgan rejani bazaga yozadi. (mahsulotlar soni, SKU soni, ogohlantirishlar)."""
    from .admin_api import save_upload

    warnings: list[str] = []
    cats = {c["name"].lower(): c["id"] for c in await products.get_categories()}
    cats.update({c["name_ru"].lower(): c["id"] for c in await products.get_categories() if c["name_ru"]})
    brands = {b["name"].lower(): b["id"] for b in await products.get_brands()}
    skus = 0
    for p in plans:
        cid = cats.get(p["category"].lower())
        if not cid:
            cid = cats[p["category"].lower()] = await products.add_category(p["category"], "", "📦")
            warnings.append(f"Yangi kategoriya yaratildi: «{p['category']}»")
        bid = brands.get(p["brand"].lower()) if p["brand"] else None
        if p["brand"] and not bid:
            bid = brands[p["brand"].lower()] = await products.add_brand(p["brand"])
        pid = await products.create_product({
            "category_id": cid, "name": p["name"], "name_ru": p["name_ru"], "brand_id": bid,
            "description": p["description"], "description_ru": p["description_ru"],
            "warranty_months": p["warranty_months"], "discount_percent": p["discount_percent"],
            "options": p["options"], "specs": p["specs"], "is_active": 1,
        })
        await products.save_variants(pid, p["variants"], by_user)
        skus += len(p["variants"])
        images = []
        for url, color in p["images"]:
            try:
                path, _ = await save_upload(await fetch_image(url), "product")
                images.append({"path": path, "color": color})
            except Exception as e:  # noqa: BLE001
                log.info("Import rasmi olinmadi %s: %s", url, e)
                warnings.append(f"{p['row']}-satr: rasm yuklab olinmadi ({url[:70]})")
        if images:
            await products.save_images(pid, images)
    return len(plans), skus, warnings
