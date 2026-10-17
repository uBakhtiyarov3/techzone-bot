"""Katalog so'rovlari: kategoriyalar, brendlar, mahsulotlar, variantlar va galereya."""
import json

from . import db
from .utils import now_str

CATEGORY_FIELDS = {"name", "name_ru", "emoji", "spec_template", "sort", "is_active"}
BRAND_FIELDS = {"name", "logo", "sort", "is_active"}
PRODUCT_FIELDS = {
    "category_id", "brand_id", "name", "name_ru", "description", "description_ru", "options", "specs",
    "warranty_months", "badges", "discount_percent", "discount_until", "is_active", "is_deleted", "sort",
}
VARIANT_FIELDS = {"vals", "sku", "price", "stock", "is_active", "sort"}


# ---------------- kategoriyalar ----------------

def _category(r: dict) -> dict:
    r["spec_template"] = json.loads(r.get("spec_template") or "[]")
    return r


async def get_categories(only_active: bool = False) -> list[dict]:
    sql = "SELECT * FROM categories" + (" WHERE is_active = 1" if only_active else "")
    return [_category(r) for r in await db.fetchall(sql + " ORDER BY sort, id")]


async def get_category(cat_id: int) -> dict | None:
    r = await db.fetchone("SELECT * FROM categories WHERE id = ?", cat_id)
    return _category(r) if r else None


async def add_category(name: str, name_ru: str = "", emoji: str = "", spec_template: list | None = None) -> int:
    sort = await db.scalar("SELECT COALESCE(MAX(sort), 0) + 1 FROM categories")
    return await db.execute(
        "INSERT INTO categories(name, name_ru, emoji, spec_template, sort) VALUES (?, ?, ?, ?, ?)",
        name, name_ru, emoji, json.dumps(spec_template or [], ensure_ascii=False), sort,
    )


async def update_category(cat_id: int, **fields) -> None:
    if "spec_template" in fields:
        fields["spec_template"] = json.dumps(fields["spec_template"], ensure_ascii=False)
    await db.update_row("categories", cat_id, fields, CATEGORY_FIELDS)


# ---------------- brendlar ----------------

async def get_brands(only_active: bool = False) -> list[dict]:
    sql = "SELECT * FROM brands" + (" WHERE is_active = 1" if only_active else "")
    return await db.fetchall(sql + " ORDER BY sort, name")


async def get_brand(brand_id: int) -> dict | None:
    return await db.fetchone("SELECT * FROM brands WHERE id = ?", brand_id)


async def brand_by_name(name: str) -> dict | None:
    return await db.fetchone("SELECT * FROM brands WHERE lower(name) = lower(?)", name.strip())


async def add_brand(name: str, logo: str = "") -> int:
    sort = await db.scalar("SELECT COALESCE(MAX(sort), 0) + 1 FROM brands")
    return await db.execute("INSERT INTO brands(name, logo, sort) VALUES (?, ?, ?)", name.strip(), logo, sort)


async def update_brand(brand_id: int, **fields) -> None:
    await db.update_row("brands", brand_id, fields, BRAND_FIELDS)


# ---------------- mahsulotlar ----------------

def _variant(r: dict) -> dict:
    r["vals"] = json.loads(r.get("vals") or "[]")
    return r


def _assemble(p: dict, variants: list[dict], images: list[dict], brands: dict, sold: dict) -> dict:
    p["options"] = json.loads(p.get("options") or "[]")
    p["specs"] = json.loads(p.get("specs") or "[]")
    p["variants"] = variants
    p["images"] = images
    p["brand"] = brands.get(p.get("brand_id"))
    p["sold"] = sold.get(p["id"], 0)
    return p


async def _sold_map() -> dict[int, int]:
    rows = await db.fetchall(
        "SELECT i.product_id, SUM(i.qty) q FROM order_items i JOIN orders o ON o.id = i.order_id"
        " WHERE o.status != 'cancelled' GROUP BY i.product_id"
    )
    return {r["product_id"]: r["q"] for r in rows}


async def get_products(category_id: int | None = None, only_active: bool = False,
                       with_deleted_variants: bool = False) -> list[dict]:
    """Mahsulotlar variantlari, rasmlari va brendi bilan (4 ta so'rovda)."""
    sql = "SELECT * FROM products WHERE is_deleted = 0"
    args: list = []
    if category_id is not None:
        sql += " AND category_id = ?"
        args.append(category_id)
    if only_active:
        sql += " AND is_active = 1 AND category_id IN (SELECT id FROM categories WHERE is_active = 1)"
    rows = await db.fetchall(sql + " ORDER BY sort, id", *args)
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    marks = ",".join("?" * len(ids))
    vsql = f"SELECT * FROM variants WHERE product_id IN ({marks})"
    if not with_deleted_variants:
        vsql += " AND is_deleted = 0"
    variants: dict[int, list] = {}
    for v in await db.fetchall(vsql + " ORDER BY sort, id", *ids):
        variants.setdefault(v["product_id"], []).append(_variant(v))
    images: dict[int, list] = {}
    for i in await db.fetchall(f"SELECT * FROM product_images WHERE product_id IN ({marks}) ORDER BY sort, id", *ids):
        images.setdefault(i["product_id"], []).append(i)
    brands = {b["id"]: b for b in await get_brands()}
    sold = await _sold_map()
    return [_assemble(r, variants.get(r["id"], []), images.get(r["id"], []), brands, sold) for r in rows]


async def get_product(product_id: int, with_deleted_variants: bool = False) -> dict | None:
    r = await db.fetchone("SELECT * FROM products WHERE id = ? AND is_deleted = 0", product_id)
    if not r:
        return None
    vsql = "SELECT * FROM variants WHERE product_id = ?" + ("" if with_deleted_variants else " AND is_deleted = 0")
    variants = [_variant(v) for v in await db.fetchall(vsql + " ORDER BY sort, id", product_id)]
    images = await db.fetchall("SELECT * FROM product_images WHERE product_id = ? ORDER BY sort, id", product_id)
    brand = await get_brand(r["brand_id"]) if r.get("brand_id") else None
    sold = await db.scalar(
        "SELECT COALESCE(SUM(i.qty), 0) FROM order_items i JOIN orders o ON o.id = i.order_id"
        " WHERE i.product_id = ? AND o.status != 'cancelled'", product_id)
    return _assemble(r, variants, images, {r.get("brand_id"): brand}, {product_id: sold})


async def get_variant(variant_id: int) -> dict | None:
    r = await db.fetchone("SELECT * FROM variants WHERE id = ?", variant_id)
    return _variant(r) if r else None


def sellable(p: dict, v: dict) -> bool:
    return bool(p.get("is_active")) and not p.get("is_deleted") and bool(v.get("is_active")) \
        and not v.get("is_deleted") and v.get("stock", 0) > 0


async def category_visible(cat_id: int) -> bool:
    return bool(await db.scalar("SELECT is_active FROM categories WHERE id = ?", cat_id))


async def create_product(fields: dict) -> int:
    sort = await db.scalar("SELECT COALESCE(MAX(sort), 0) + 1 FROM products WHERE category_id = ?",
                           fields["category_id"])
    pid = await db.execute(
        "INSERT INTO products(category_id, name, sort, created_at) VALUES (?, ?, ?, ?)",
        fields["category_id"], fields["name"], sort, now_str(),
    )
    await update_product(pid, **{k: v for k, v in fields.items() if k not in ("category_id", "name")})
    return pid


async def update_product(product_id: int, **fields) -> None:
    for key in ("options", "specs"):
        if key in fields and not isinstance(fields[key], str):
            fields[key] = json.dumps(fields[key], ensure_ascii=False)
    await db.update_row("products", product_id, fields, PRODUCT_FIELDS)


async def save_variants(product_id: int, variants: list[dict], by_user: int | None = None) -> None:
    """Variantlarni saqlaydi: id bo'lsa yangilaydi, yo'q bo'lsa qo'shadi, ro'yxatda yo'qlarini o'chiradi.

    Qoldiq bu yerda o'zgartirilmaydi — u faqat kirim/tuzatish orqali (inventory.py) harakat sifatida yoziladi,
    yangi variantning boshlang'ich qoldig'i bundan mustasno.
    """
    from . import inventory

    existing = {v["id"]: v for v in
                (_variant(r) for r in await db.fetchall("SELECT * FROM variants WHERE product_id = ?", product_id))}
    keep = set()
    for pos, v in enumerate(variants):
        vals = json.dumps(v.get("vals") or [], ensure_ascii=False)
        vid = v.get("id")
        if vid in existing:
            keep.add(vid)
            await db.execute(
                "UPDATE variants SET vals = ?, sku = ?, price = ?, is_active = ?, is_deleted = 0, sort = ?"
                " WHERE id = ?", vals, v.get("sku", ""), v["price"], 1 if v.get("is_active", True) else 0, pos, vid)
        else:
            vid = await db.execute(
                "INSERT INTO variants(product_id, vals, sku, price, cost, stock, is_active, sort)"
                " VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
                product_id, vals, v.get("sku", ""), v["price"], int(v.get("cost") or 0),
                1 if v.get("is_active", True) else 0, pos)
            keep.add(vid)
            if int(v.get("stock") or 0) > 0:
                await inventory.adjust(vid, int(v["stock"]), "adjust", note="Boshlang'ich qoldiq", by_user=by_user)
    for vid in set(existing) - keep:
        await db.execute("UPDATE variants SET is_deleted = 1, is_active = 0 WHERE id = ?", vid)


async def save_images(product_id: int, images: list[dict]) -> None:
    await db.execute("DELETE FROM product_images WHERE product_id = ?", product_id)
    for pos, img in enumerate(images):
        await db.execute("INSERT INTO product_images(product_id, path, color, sort) VALUES (?, ?, ?, ?)",
                         product_id, img["path"], img.get("color", ""), pos)


async def delete_demo() -> int:
    """Demo mahsulotlarni (seed) olib tashlaydi. O'chirilganlar sonini qaytaradi."""
    n = await db.scalar("SELECT COUNT(*) FROM products WHERE is_demo = 1 AND is_deleted = 0")
    await db.execute("UPDATE products SET is_deleted = 1, is_active = 0 WHERE is_demo = 1")
    return n
