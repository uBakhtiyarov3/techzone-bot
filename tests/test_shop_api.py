"""Mini App API: katalog, mahsulot, savat, buyurtma, qoldiq, hudud, chat."""
from app import db, inventory, products
from app.i18n import t
from app.orders import normalize_phone
from tests.conftest import H, make_init_data, variant_of


def order_body(vid: int, qty: int = 1, **kw) -> dict:
    return {"name": "Ali Valiyev", "phone": "+998 90 123 45 67", "order_type": "delivery", "region_id": 1,
            "address": "Toshkent, Chilonzor 5-uy", "payment_method": "cash",
            "items": [{"variant_id": vid, "qty": qty}], **kw}


async def test_auth_required(client):
    r = await client.get("/api/bootstrap")
    assert r.status == 401
    bad = make_init_data(5, token="999:WRONG")
    r = await client.get("/api/bootstrap", headers={"X-Telegram-Init-Data": bad})
    assert r.status == 401
    old = make_init_data(5, auth_date=1)
    r = await client.get("/api/bootstrap", headers={"X-Telegram-Init-Data": old})
    assert r.status == 401


async def test_bootstrap(client):
    r = await client.get("/api/bootstrap", headers=H(100))
    data = await r.json()
    assert r.status == 200 and data["ok"]
    assert data["brand"]["name"] == "Tech.Zone" and data["brand"]["color"] == "#E0382B"
    assert [c["name"] for c in data["categories"]][:2] == ["Smartfonlar", "Noutbuklar"]
    assert {"Apple", "Samsung", "Xiaomi"} <= {b["name"] for b in data["brands"]}
    assert len(data["regions"]) == 14 and data["regions"][0]["name"] == "Toshkent shahri"
    iphone = next(p for p in data["products"] if p["name"] == "iPhone 15")
    assert iphone["price"] == 10_990_000 and iphone["price_from"] and iphone["colors"] == 3
    anker = next(p for p in data["products"] if p["name"] == "Anker PowerCore 20000")
    assert anker["stock"] == "out"
    assert data["texts"]["tabCatalog"] == "Katalog"
    # akkaunt avtomatik ochildi
    assert await db.get_user(100)


async def test_product_detail_and_hidden(client):
    v = await variant_of("Galaxy S24 Ultra", "Kulrang titan", "256 GB")
    r = await client.get(f"/api/products/{v['product_id']}", headers=H())
    p = (await r.json())["product"]
    assert p["discount"] == 10 and p["brand"] == "Samsung"
    first = next(x for x in p["variants"] if x["id"] == v["id"])
    assert first["old_price"] == 15_990_000 and first["price"] == 14_391_000 // 1000 * 1000
    assert [o["name"] for o in p["options"]] == ["Rang", "Xotira"]
    assert any(s["k"] == "Protsessor" for s in p["specs"])
    assert len(p["images"]) == 2 and p["images"][0]["color"] == "Kulrang titan"
    # yashirilgan mahsulot
    await products.update_product(v["product_id"], is_active=0)
    r = await client.get(f"/api/products/{v['product_id']}", headers=H())
    assert r.status == 404


async def test_favorites_and_alerts(client):
    v = await variant_of("Anker PowerCore 20000")
    r = await client.post(f"/api/favorites/{v['product_id']}", headers=H(7))
    assert (await r.json())["favorites"] == [v["product_id"]]
    r = await client.post(f"/api/favorites/{v['product_id']}", headers=H(7))
    assert (await r.json())["favorites"] == []
    r = await client.post("/api/alerts", headers=H(7), json={"variant_id": v["id"]})
    assert r.status == 200 and await inventory.has_alert(7, v["id"])
    r = await client.get(f"/api/products/{v['product_id']}", headers=H(7))
    assert (await r.json())["alerts"] == [v["id"]]


async def test_cart_endpoint(client):
    ok = await variant_of("iPhone 15", "Qora", "128 GB")
    out = await variant_of("Anker PowerCore 20000")
    r = await client.post("/api/cart", headers=H(), json={"items": [{"variant_id": ok["id"]}, {"variant_id": out["id"]},
                                                                     {"variant_id": 99999}]})
    items = (await r.json())["items"]
    assert items[0]["stock"] == ok["stock"] and not items[0]["gone"] and items[0]["label"] == "Qora, 128 GB"
    assert items[0]["image"].endswith("iphone15-black.jpg")
    assert items[1]["gone"] and items[2]["gone"]


async def test_quote_regions(client):
    v = await variant_of("Redmi Note 13 Pro", "Qora", "256 GB")
    body = {"items": [{"variant_id": v["id"], "qty": 1}], "order_type": "delivery", "region_id": 3}
    q = (await (await client.post("/api/quote", headers=H(), json=body)).json())["quote"]
    assert q["delivery_fee"] == 70_000 and q["total"] == 3_990_000 + 70_000 and q["region"]["eta"] == "2–4 kun"
    body["items"][0]["qty"] = 2  # 7 980 000 >= 5 mln — bepul
    q = (await (await client.post("/api/quote", headers=H(), json=body)).json())["quote"]
    assert q["delivery_fee"] == 0
    body["order_type"] = "pickup"
    q = (await (await client.post("/api/quote", headers=H(), json=body)).json())["quote"]
    assert q["delivery_fee"] == 0 and q["region"] is None


async def test_order_reserves_stock_and_cancel_returns(client):
    v = await variant_of("iPhone 15", "Qora", "128 GB")
    before = v["stock"]
    r = await client.post("/api/orders", headers=H(100), json=order_body(v["id"], 2, comment="Qo'ng'iroq qiling"))
    data = await r.json()
    assert r.status == 200, data
    o = data["order"]
    assert o["code"].startswith("TZ-") and o["status"] == "new" and o["region"] == "Toshkent shahri"
    assert o["delivery_fee"] == 0 and o["total"] == 2 * 10_990_000  # 5 mln dan bepul
    assert o["items"][0]["variant"] == "Qora, 128 GB" and o["items"][0]["warranty_months"] == 12
    assert (await products.get_variant(v["id"]))["stock"] == before - 2
    moves = await inventory.moves(v["id"])
    assert moves[0]["delta"] == -2 and moves[0]["reason"] == "order" and moves[0]["ref"] == o["code"]
    # profil saqlandi
    u = await db.get_user(100)
    assert u["phone"] == "+998901234567" and u["region_id"] == 1
    # mijoz bekor qiladi -> qoldiq qaytadi
    r = await client.post(f"/api/orders/{o['code']}/cancel", headers=H(100))
    assert (await r.json())["order"]["status"] == "cancelled"
    assert (await products.get_variant(v["id"]))["stock"] == before
    # boshqa mijoz ko'ra olmaydi
    r = await client.get(f"/api/orders/{o['code']}", headers=H(200))
    assert r.status == 404


async def test_order_stock_limits(client):
    v = await variant_of("TUF Gaming F15")
    r = await client.post("/api/orders", headers=H(), json=order_body(v["id"], v["stock"] + 1))
    data = await r.json()
    assert r.status == 409 and str(v["stock"]) in data["error"]
    out = await variant_of("Anker PowerCore 20000")
    r = await client.post("/api/orders", headers=H(), json=order_body(out["id"]))
    assert r.status == 409 and (await r.json())["error"] == t("e_unavailable")
    # oxirgi dona: birinchisi oladi, ikkinchisiga yetmaydi
    await inventory.set_stock(v["id"], 1)
    r1 = await client.post("/api/orders", headers=H(301), json=order_body(v["id"]))
    r2 = await client.post("/api/orders", headers=H(302), json=order_body(v["id"]))
    assert r1.status == 200 and r2.status == 409
    assert (await products.get_variant(v["id"]))["stock"] == 0
    assert await db.scalar("SELECT COUNT(*) FROM orders") == 1


async def test_order_validation(client):
    v = await variant_of("AirPods Pro 2")
    cases = [
        ({"phone": "12345"}, "e_phone"), ({"name": "A"}, "e_name"), ({"region_id": None}, "e_region"),
        ({"region_id": 999}, "e_region"), ({"address": "abc"}, "e_address"), ({"payment_method": "card"}, "e_card"),
        ({"items": []}, "e_empty_cart"), ({"items": [{"variant_id": v["id"], "qty": 99}]}, "e_qty"),
        ({"order_type": "teleport"}, "e_type"),
    ]
    for patch, key in cases:
        r = await client.post("/api/orders", headers=H(), json=order_body(v["id"], **patch))
        assert (await r.json())["error"] == t(key), patch
    # olib ketishda hudud va manzil shart emas
    r = await client.post("/api/orders", headers=H(), json=order_body(v["id"], order_type="pickup", region_id=None,
                                                                       address=""))
    assert r.status == 200
    # tez-tez buyurtma
    r = await client.post("/api/orders", headers=H(), json=order_body(v["id"]))
    assert r.status == 429


async def test_closed_mode_and_after_hours(client):
    v = await variant_of("AirPods Pro 2")
    await db.set_setting("mode", "closed")
    r = await client.post("/api/orders", headers=H(1), json=order_body(v["id"]))
    assert (await r.json())["error"] == t("e_closed_full")
    # ish vaqtidan tashqari ham buyurtma qabul qilinadi (24/7)
    await db.set_setting("mode", "auto")
    await db.set_setting("schedule", '{"mon": null, "tue": null, "wed": null, "thu": null, "fri": null,'
                                     ' "sat": null, "sun": null}')
    r = await client.post("/api/orders", headers=H(2), json=order_body(v["id"]))
    assert r.status == 200
    boot = await (await client.get("/api/bootstrap", headers=H(2))).json()
    assert boot["settings"]["accepting"] and not boot["settings"]["is_open"]


async def test_promo_codes(client):
    v = await variant_of("AirPods Pro 2")
    await db.add_promo(code="TECH10", kind="percent", value=10, max_discount=200_000, min_order=1_000_000)
    await db.add_promo(code="FREESHIP", kind="free_delivery", value=0)
    await db.add_promo(code="FIRST", kind="fixed", value=100_000, first_order_only=1, per_user_limit=0)
    body = {"items": [{"variant_id": v["id"], "qty": 1}], "region_id": 5, "promo_code": "tech10"}
    q = (await (await client.post("/api/quote", headers=H(9), json=body)).json())["quote"]
    assert q["discount"] == 200_000 and q["total"] == 3_190_000 - 200_000 + 70_000
    body["promo_code"] = "FREESHIP"
    q = (await (await client.post("/api/quote", headers=H(9), json=body)).json())["quote"]
    assert q["delivery_fee"] == 0
    r = await client.post("/api/quote", headers=H(9), json={**body, "order_type": "pickup"})
    assert (await r.json())["error"] == t("e_promo_pickup")
    r = await client.post("/api/orders", headers=H(9), json=order_body(v["id"], promo_code="FIRST"))
    assert (await r.json())["order"]["discount"] == 100_000
    r = await client.post("/api/quote", headers=H(9), json={**body, "promo_code": "FIRST"})
    assert (await r.json())["error"] == t("e_promo_first")


async def test_order_chat(client):
    v = await variant_of("AirPods Pro 2")
    code = (await (await client.post("/api/orders", headers=H(50), json=order_body(v["id"]))).json())["order"]["code"]
    r = await client.post(f"/api/orders/{code}/chat", headers=H(50), json={"text": "Qachon yetkazasiz?"})
    msgs = (await r.json())["messages"]
    assert msgs[-1]["from"] == "customer" and msgs[-1]["text"] == "Qachon yetkazasiz?"
    order = await db.get_order_by_code(code)
    from app import chat
    await chat.add_message(order["id"], "staff", 1, "Ertaga 12:00 da")
    o = (await (await client.get(f"/api/orders/{code}", headers=H(50))).json())["order"]
    assert o["unread"] == 1
    r = await client.get(f"/api/orders/{code}/chat", headers=H(50))
    assert [m["from"] for m in (await r.json())["messages"]] == ["customer", "staff"]
    assert await chat.unread_count(order["id"], "customer") == 0
    r = await client.post(f"/api/orders/{code}/chat", headers=H(51), json={"text": "begona"})
    assert r.status == 404


async def test_russian_language(client):
    await client.post("/api/me/lang", headers=H(70), json={"lang": "ru"})
    boot = await (await client.get("/api/bootstrap", headers=H(70))).json()
    assert boot["texts"]["tabCatalog"] == "Каталог" and boot["regions"][0]["name"] == "г. Ташкент"
    v = await variant_of("iPhone 15", "Pushti", "256 GB")
    p = (await (await client.get(f"/api/products/{v['product_id']}", headers=H(70))).json())["product"]
    assert p["options"][0]["values"][2]["label"] == "Розовый" and p["warranty"] == "1 год"


def test_normalize_phone():
    assert normalize_phone("+998 90 123-45-67") == "+998901234567"
    assert normalize_phone("901234567") == "+998901234567"
    assert normalize_phone("12345") is None
