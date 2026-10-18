"""Do'kon paneli API: katalog, variantlar, ombor, xaridlar, hududlar, buyurtmalar, brend (white-label)."""
import io

from aiohttp import FormData

from app import chat, db, inventory, products
from app.i18n import t
from tests.conftest import H, admin_headers, variant_of

PRODUCT = {
    "name": "Pixel 9", "category_id": 1, "brand_id": None, "warranty_months": 12, "badges": ["new"],
    "options": [{"name": "Rang", "name_ru": "Цвет", "values": ["Qora", "Oq"], "values_ru": ["Чёрный", "Белый"]},
                {"name": "Xotira", "values": ["128 GB"]}],
    "variants": [{"vals": ["Qora", "128 GB"], "price": 9_000_000, "stock": 3, "sku": "PX9-B"},
                 {"vals": ["Oq", "128 GB"], "price": 9_100_000, "stock": 0}],
    "specs": [{"k": "Ekran", "v": "6.3\" OLED"}, {"k": "", "v": "bo'sh"}],
    "images": [{"path": "img/demo/x14t-black.jpg", "color": "Qora"}, {"path": "img/demo/x14t-gray.jpg", "color": "Yashil"}],
}


def png(w=800, h=400, color=(255, 0, 0, 255)) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


async def test_access_control(client):
    r = await client.get("/api/admin/dashboard")
    assert r.status == 401
    r = await client.get("/api/admin/dashboard", headers=H(1))  # menejerning Telegram initData si
    assert r.status == 200
    await db.upsert_user(55, "Oddiy", None, None)
    r = await client.get("/api/admin/dashboard", headers=H(55))
    assert r.status == 401
    hdr = await admin_headers(client)
    r = await client.get("/api/admin/me", headers=hdr)
    assert (await r.json())["brand"]["name"] == "Tech.Zone"
    # kirish sahifasi brendi ochiq
    assert (await (await client.get("/api/admin/brand")).json())["brand"]["logo"] == "brand/logo.png"


async def test_product_crud_with_variants(client):
    hdr = await admin_headers(client)
    r = await client.post("/api/admin/products", headers=hdr, json=PRODUCT)
    data = await r.json()
    assert r.status == 200, data
    p = data["product"]
    assert [v["label"] for v in p["variants"]] == ["Qora, 128 GB", "Oq, 128 GB"]
    assert p["stock"] == 3 and p["specs"] == [{"k": "Ekran", "k_ru": "", "v": "6.3\" OLED", "v_ru": ""}]
    assert p["images"][1]["color"] == ""  # mavjud bo'lmagan rang olib tashlandi
    first = p["variants"][0]
    moves = await inventory.moves(first["id"])
    assert moves[0]["delta"] == 3 and moves[0]["note"] == "Boshlang'ich qoldiq"

    # narxni o'zgartirish, variantni olib tashlash; qoldiq tahrir orqali o'zgarmaydi
    upd = {"variants": [{"id": first["id"], "vals": ["Qora", "128 GB"], "price": 8_500_000, "stock": 99}],
           "discount_percent": 10}
    r = await client.put(f"/api/admin/products/{p['id']}", headers=hdr, json={**PRODUCT, **upd})
    p2 = (await r.json())["product"]
    assert len(p2["variants"]) == 1 and p2["variants"][0]["price"] == 8_500_000 and p2["variants"][0]["stock"] == 3
    assert p2["variants"][0]["price_now"] == 7_650_000
    removed = await products.get_variant(p["variants"][1]["id"])
    assert removed["is_deleted"] == 1

    # xatolar
    bad = {**PRODUCT, "variants": [{"vals": ["Ko'k", "128 GB"], "price": 1000}]}
    r = await client.post("/api/admin/products", headers=hdr, json=bad)
    assert r.status == 400 and "mos emas" in (await r.json())["error"]
    r = await client.post("/api/admin/products", headers=hdr, json={**PRODUCT, "variants": []})
    assert r.status == 400
    r = await client.post("/api/admin/products", headers=hdr, json={**PRODUCT, "category_id": 999})
    assert (await r.json())["error"] == "Kategoriyani tanlang"

    # Mini App'da ko'rinadi, o'chirilgach yo'qoladi
    boot = await (await client.get("/api/bootstrap", headers=H(5))).json()
    assert any(x["name"] == "Pixel 9" for x in boot["products"])
    await client.delete(f"/api/admin/products/{p['id']}", headers=hdr)
    boot = await (await client.get("/api/bootstrap", headers=H(5))).json()
    assert not any(x["name"] == "Pixel 9" for x in boot["products"])


async def test_categories_and_brands(client):
    hdr = await admin_headers(client)
    r = await client.post("/api/admin/categories", headers=hdr,
                          json={"name": "Televizorlar", "emoji": "📺", "spec_template": [{"k": "Diagonal"}, {"k": ""}]})
    cat = (await r.json())["category"]
    assert cat["spec_template"] == [{"k": "Diagonal", "k_ru": ""}]
    r = await client.delete(f"/api/admin/categories/{cat['id']}", headers=hdr)
    assert r.status == 200
    r = await client.delete("/api/admin/categories/1", headers=hdr)
    assert r.status == 400  # ichida mahsulot bor
    r = await client.post("/api/admin/brands", headers=hdr, json={"name": "apple"})
    assert "allaqachon" in (await r.json())["error"]
    r = await client.post("/api/admin/brands", headers=hdr, json={"name": "Huawei"})
    bid = (await r.json())["brand"]["id"]
    r = await client.delete(f"/api/admin/brands/{bid}", headers=hdr)
    assert r.status == 200
    cat_data = await (await client.get("/api/admin/catalog", headers=hdr)).json()
    assert cat_data["demo"] == 16 and len(cat_data["brands"]) == 7
    r = await client.delete("/api/admin/demo", headers=hdr)
    assert (await r.json())["deleted"] == 16
    boot = await (await client.get("/api/bootstrap", headers=H(5))).json()
    assert boot["products"] == [] and boot["categories"] == []


async def test_purchase_and_stock(client):
    hdr = await admin_headers(client)
    v = await variant_of("Anker PowerCore 20000")
    assert v["stock"] == 0 and v["cost"] == 483_000
    await inventory.subscribe_alert(77, v["id"])
    r = await client.post("/api/admin/suppliers", headers=hdr, json={"name": "Optom Tech", "phone": "+998 71 200 00 00"})
    sid = (await r.json())["id"]
    r = await client.post("/api/admin/purchases", headers=hdr, json={
        "supplier_id": sid, "note": "Oktyabr partiyasi", "items": [{"variant_id": v["id"], "qty": 10, "cost": 450_000}]})
    assert r.status == 200
    v2 = await products.get_variant(v["id"])
    assert v2["stock"] == 10 and v2["cost"] == 450_000
    # o'rtacha tannarx
    await client.post("/api/admin/purchases", headers=hdr,
                      json={"items": [{"variant_id": v["id"], "qty": 10, "cost": 550_000}]})
    assert (await products.get_variant(v["id"]))["cost"] == 500_000
    data = await (await client.get("/api/admin/purchases", headers=hdr)).json()
    assert data["purchases"][0]["units"] == 10 and data["suppliers"][0]["purchases"] == 1
    # inventarizatsiya
    r = await client.post(f"/api/admin/stock/{v['id']}", headers=hdr, json={"stock": 15, "note": "Sanash"})
    assert (await r.json())["variant"]["stock"] == 15
    r = await client.post(f"/api/admin/stock/{v['id']}", headers=hdr, json={"delta": -2})
    assert (await r.json())["variant"]["stock"] == 13
    moves = (await (await client.get(f"/api/admin/moves?variant_id={v['id']}", headers=hdr)).json())["moves"]
    assert [m["reason"] for m in moves][:4] == ["adjust", "adjust", "purchase", "purchase"]
    low = (await (await client.get("/api/admin/stock?low=1", headers=hdr)).json())["items"]
    assert all(x["stock"] <= 3 for x in low)
    r = await client.post("/api/admin/purchases", headers=hdr, json={"items": []})
    assert r.status == 400
    csv = await (await client.get("/api/admin/stock.csv", headers=hdr)).text()
    assert "Anker PowerCore 20000" in csv and "Qoldiq tannarxi" in csv


async def test_regions(client):
    hdr = await admin_headers(client)
    r = await client.patch("/api/admin/regions/3", headers=hdr, json={"fee": 55_000, "days_min": 1, "days_max": 2})
    assert (await r.json())["region"]["fee"] == 55_000
    r = await client.patch("/api/admin/regions/3", headers=hdr, json={"days_min": 5, "days_max": 2})
    assert r.status == 400
    r = await client.post("/api/admin/regions", headers=hdr, json={"name": "Nukus (express)", "fee": 90_000})
    rid = (await r.json())["region"]["id"]
    await client.patch(f"/api/admin/regions/{rid}", headers=hdr, json={"is_active": False})
    boot = await (await client.get("/api/bootstrap", headers=H(5))).json()
    assert len(boot["regions"]) == 14 and boot["regions"][2]["fee"] == 55_000


async def test_order_management(client):
    hdr = await admin_headers(client)
    v = await variant_of("AirPods Pro 2")
    body = {"name": "Ali", "phone": "+998901234567", "region_id": 1, "address": "Chilonzor 1",
            "payment_method": "cash", "items": [{"variant_id": v["id"], "qty": 2}]}
    code = (await (await client.post("/api/orders", headers=H(40), json=body)).json())["order"]["code"]
    oid = (await db.get_order_by_code(code))["id"]
    orders = (await (await client.get("/api/admin/orders?status=new", headers=hdr)).json())["orders"]
    assert orders[0]["code"] == code and orders[0]["units"] == 2

    # chat faqat faol buyurtmada
    await chat.add_message(oid, "customer", 40, "Rahmat!")
    r = await client.post(f"/api/admin/orders/{oid}/chat", headers=hdr, json={"text": "Marhamat!"})
    d = await r.json()
    assert [m["sender"] for m in d["chat"]] == ["customer", "staff"] and d["chat_open"]
    assert await chat.unread_count(oid, "staff") == 0

    for st in ("accepted", "packing", "shipping", "delivered"):
        r = await client.post(f"/api/admin/orders/{oid}/status", headers=hdr, json={"status": st})
        assert (await r.json())["order"]["status"] == st
    r = await client.post(f"/api/admin/orders/{oid}/status", headers=hdr, json={"status": "packing"})
    assert r.status == 409

    items = await db.get_order_items(oid)
    r = await client.post(f"/api/admin/orders/{oid}/serials", headers=hdr, json={"serials": {str(items[0]["id"]): "SN-123"}})
    assert (await r.json())["items"][0]["serial"] == "SN-123"

    # holat rasmi (yopilgan buyurtmada ham — masalan, topshirish dalolatnomasi)
    form = FormData()
    form.add_field("file", png(), filename="box.png", content_type="image/png")
    form.add_field("caption", "Qadoqlangan")
    r = await client.post(f"/api/admin/orders/{oid}/media", headers=hdr, data=form)
    media = (await r.json())["media"]
    assert media[0]["status"] == "delivered" and media[0]["caption"] == "Qadoqlangan"
    o = (await (await client.get(f"/api/orders/{code}", headers=H(40))).json())["order"]
    assert o["media"][0]["path"].startswith("uploads/") and o["items"][0]["serial"] == "SN-123"

    # foyda: 2 × (3 190 000 − 2 615 000 tannarx)
    dash = await (await client.get("/api/admin/dashboard?period=today", headers=hdr)).json()
    assert dash["stats"]["revenue"] == 6_380_000 and dash["stats"]["gross_profit"] == 2 * (3_190_000 - 2_615_000)
    csv = await (await client.get("/api/admin/export.csv?period=today", headers=hdr)).text()
    assert code in csv and "Yalpi foyda" in csv


async def test_admin_cancel_returns_stock_and_delete(client):
    hdr = await admin_headers(client)
    v = await variant_of("JBL Tune 770NC", "Qora")
    stock = v["stock"]
    body = {"name": "Vali", "phone": "+998901112233", "order_type": "pickup", "payment_method": "cash",
            "items": [{"variant_id": v["id"], "qty": 1}]}
    code = (await (await client.post("/api/orders", headers=H(41), json=body)).json())["order"]["code"]
    oid = (await db.get_order_by_code(code))["id"]
    assert (await products.get_variant(v["id"]))["stock"] == stock - 1
    r = await client.post(f"/api/admin/orders/{oid}/status", headers=hdr, json={"status": "cancelled", "reason": "Test"})
    assert (await r.json())["order"]["status"] == "cancelled"
    assert (await products.get_variant(v["id"]))["stock"] == stock
    # faol buyurtmani o'chirish ham qoldiqni qaytaradi
    code2 = (await (await client.post("/api/orders", headers=H(42), json=body)).json())["order"]["code"]
    oid2 = (await db.get_order_by_code(code2))["id"]
    await client.delete(f"/api/admin/orders/{oid2}", headers=hdr)
    assert await db.get_order(oid2) is None and (await products.get_variant(v["id"]))["stock"] == stock


async def test_brand_settings_white_label(client):
    hdr = await admin_headers(client)
    r = await client.put("/api/admin/settings", headers=hdr, json={
        "shop_name": "Gadget Plus", "shop_tagline": "Texnika — oson", "brand_color": "#1e88e5", "order_prefix": "gp",
        "instagram": "@gadgetplus", "low_stock": 5, "shop_map_url": "https://maps.google.com/?q=41.311081,69.240562"})
    s = (await r.json())["settings"]
    assert s["shop_name"] == "Gadget Plus" and s["brand_color"] == "#1E88E5" and s["order_prefix"] == "GP"
    assert s["shop_lat"] == "41.311081"
    assert "Gadget Plus" in t("greet", "uz", name="Ali")
    boot = await (await client.get("/api/bootstrap", headers=H(5))).json()
    assert boot["brand"]["name"] == "Gadget Plus" and boot["settings"]["low_stock"] == 5
    v = await variant_of("AirPods Pro 2")
    body = {"name": "Ali", "phone": "+998901234567", "order_type": "pickup", "payment_method": "cash",
            "items": [{"variant_id": v["id"], "qty": 1}]}
    code = (await (await client.post("/api/orders", headers=H(5), json=body)).json())["order"]["code"]
    assert code.startswith("GP-")
    for bad in ({"brand_color": "red"}, {"order_prefix": "12"}, {"shop_name": ""},
                {"delivery_enabled": False, "pickup_enabled": False}):
        r = await client.put("/api/admin/settings", headers=hdr, json=bad)
        assert r.status == 400, bad


async def test_texts_and_upload(client):
    hdr = await admin_headers(client)
    r = await client.put("/api/admin/texts", headers=hdr,
                         json={"key": "greet", "lang": "uz", "value": "Salom {name}, <b>{shop}</b>ga xush kelibsiz!"})
    assert r.status == 200
    assert t("greet", "uz", name="Ali") == "Salom Ali, <b>Tech.Zone</b>ga xush kelibsiz!"
    r = await client.put("/api/admin/texts", headers=hdr, json={"key": "greet", "lang": "uz", "value": "<b>yopilmagan"})
    assert r.status == 400
    r = await client.put("/api/admin/texts", headers=hdr, json={"key": "greet", "lang": "uz", "value": "{nomalum}"})
    assert "Noma'lum" in (await r.json())["error"]
    await client.put("/api/admin/texts", headers=hdr, json={"key": "greet", "lang": "uz", "value": ""})

    form = FormData()
    form.add_field("file", png(800, 400), filename="a.png", content_type="image/png")
    r = await client.post("/api/admin/upload", headers=hdr, data=form)
    d = await r.json()
    assert (d["width"], d["height"]) == (800, 600) and d["path"].endswith(".jpg") and d["warnings"]
    form = FormData()
    form.add_field("file", png(600, 600, (0, 0, 0, 0)), filename="logo.png", content_type="image/png")
    form.add_field("kind", "brand")
    d = await (await client.post("/api/admin/upload", headers=hdr, data=form)).json()
    assert d["path"].endswith(".png") and d["width"] == 400
