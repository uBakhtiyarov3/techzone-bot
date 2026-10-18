"""Mijoz bekor qilishi (yig'ish boshlanguncha) va admin paneldagi tahrirlash/o'chirish."""
from app import chat, db, inventory, products
from app.orders import place_order
from tests.conftest import H, admin_headers, variant_of
from tests.test_bot_flows import env  # noqa: F401


async def make_order(uid: int, status: str = "new") -> dict:
    v = await variant_of("AirPods Pro 2")
    await db.upsert_user(uid, f"U{uid}", None, None)
    oid = await place_order(uid, {"name": "Ali", "phone": "+998901234567", "order_type": "pickup",
                                  "payment_method": "cash"}, [{"variant_id": v["id"], "qty": 1}])
    for st in ("accepted", "packing", "shipping", "delivered"):
        if (await db.get_order(oid))["status"] == status:
            break
        await db.set_order_status(oid, st, 2)
    return await db.get_order(oid)


async def test_customer_cancel_until_packing(client):
    acc = await make_order(80, "accepted")
    o = (await (await client.get(f"/api/orders/{acc['code']}", headers=H(80))).json())["order"]
    assert o["can_cancel"]
    r = await client.post(f"/api/orders/{acc['code']}/cancel", headers=H(80))
    assert r.status == 200 and (await r.json())["order"]["status"] == "cancelled"

    pk = await make_order(81, "packing")
    o = (await (await client.get(f"/api/orders/{pk['code']}", headers=H(81))).json())["order"]
    assert not o["can_cancel"] and not o["can_return"]
    r = await client.post(f"/api/orders/{pk['code']}/cancel", headers=H(81))
    assert r.status == 400
    dl = await make_order(82, "delivered")
    o = (await (await client.get(f"/api/orders/{dl['code']}", headers=H(82))).json())["order"]
    assert not o["can_cancel"] and o["can_return"]


async def test_admin_edit_and_delete(client):
    hdr = await admin_headers(client)
    order = await make_order(83, "delivered")
    # buyurtma ma'lumotlarini tahrirlash
    r = await client.patch(f"/api/admin/orders/{order['id']}", headers=hdr,
                           json={"customer_name": "Vali", "phone": "90 111 22 33", "comment": "Eshik oldida"})
    d = (await r.json())["order"]
    assert d["customer_name"] == "Vali" and d["phone"] == "+998901112233" and d["comment"] == "Eshik oldida"
    r = await client.patch(f"/api/admin/orders/{order['id']}", headers=hdr, json={"phone": "123"})
    assert r.status == 400
    # chat xabari va holat rasmi
    await chat.add_message(order["id"], "customer", 83, "salom")
    mid = (await chat.get_messages(order["id"]))[0]["id"]
    await chat.add_media(order["id"], "packing", "uploads/x.jpg", "", "", 2)
    media_id = (await chat.get_media(order["id"]))[0]["id"]
    d = await (await client.delete(f"/api/admin/orders/{order['id']}/chat/{mid}", headers=hdr)).json()
    assert d["chat"] == []
    d = await (await client.delete(f"/api/admin/orders/{order['id']}/media/{media_id}", headers=hdr)).json()
    assert d["media"] == []
    # baho va murojaat
    await db.execute("INSERT INTO reviews(order_id, user_id, rating, comment, created_at) VALUES (?, 83, 1, 'yomon', '2026-01-01')",
                     order["id"])
    rid = await db.scalar("SELECT id FROM reviews WHERE order_id = ?", order["id"])
    assert (await client.delete(f"/api/admin/reviews/{rid}", headers=hdr)).status == 200
    assert not await db.get_review(order["id"])
    from app import tickets
    tid = await tickets.create(order, "issue", "Savolim bor edi, iltimos", [])
    assert (await client.delete(f"/api/admin/tickets/{tid}", headers=hdr)).status == 200
    assert not await tickets.get(tid)
    # buyurtmasi bor mijozni o'chirib bo'lmaydi, buyurtmasizni — mumkin
    assert (await client.delete("/api/admin/customers/83", headers=hdr)).status == 400
    await db.upsert_user(84, "Bo'sh", None, None)
    r = await client.patch("/api/admin/customers/84", headers=hdr, json={"full_name": "Yangi ism", "phone": ""})
    assert r.status == 200 and (await db.get_user(84))["full_name"] == "Yangi ism"
    assert (await client.delete("/api/admin/customers/84", headers=hdr)).status == 200
    assert not await db.get_user(84)


async def test_purchase_and_supplier_delete(client):
    hdr = await admin_headers(client)
    v = await variant_of("Samsung 25W quvvatlagich")
    before = (await products.get_variant(v["id"]))["stock"]
    sid = await inventory.add_supplier("Ombor MChJ", "", "")
    pid, _ = await inventory.create_purchase([{"variant_id": v["id"], "qty": 5, "cost": 150_000}], sid)
    assert (await products.get_variant(v["id"]))["stock"] == before + 5
    assert (await client.delete(f"/api/admin/suppliers/{sid}", headers=hdr)).status == 200
    assert await db.scalar("SELECT supplier_id FROM purchases WHERE id = ?", pid) is None
    assert (await client.delete(f"/api/admin/purchases/{pid}", headers=hdr)).status == 200
    assert (await products.get_variant(v["id"]))["stock"] == before
    # sotilib bo'lgan kirimni o'chirib bo'lmaydi
    pid2, _ = await inventory.create_purchase([{"variant_id": v["id"], "qty": 2, "cost": 150_000}])
    await inventory.set_stock(v["id"], 1, None)
    r = await client.delete(f"/api/admin/purchases/{pid2}", headers=hdr)
    assert r.status == 400 and "sotilgan" in (await r.json())["error"]


async def test_admin_bans_customer(client):
    hdr = await admin_headers(client)
    assert (await client.get("/api/bootstrap", headers=H(85))).status == 200
    r = await client.post("/api/admin/customers/85/ban", headers=hdr, json={"banned": True, "reason": "Spam"})
    assert r.status == 200
    r = await client.get("/api/bootstrap", headers=H(85))
    assert r.status == 403 and "bloklangan" in (await r.json())["error"] and "Spam" in (await r.json())["error"]
    lst = await (await client.get("/api/admin/customers?banned=1", headers=hdr)).json()
    assert [u["id"] for u in lst["customers"]] == [85] and lst["banned"] == 1
    assert 85 not in await db.all_user_ids()  # rassilkaga ham tushmaydi
    # xodimni bloklab bo'lmaydi
    await db.upsert_user(86, "X", None, None)
    await db.set_role(86, "staff")
    assert (await client.post("/api/admin/customers/86/ban", headers=hdr, json={"banned": True})).status == 400
    await client.post("/api/admin/customers/85/ban", headers=hdr, json={"banned": False})
    assert (await client.get("/api/bootstrap", headers=H(85))).status == 200


async def test_banned_user_ignored_by_bot(env):
    from tests.test_bot_flows import CUSTOMER, click, send, setup_people
    bot, dp, s = env
    await setup_people(bot, dp)
    await db.set_banned(CUSTOMER, True, "Qoidabuzarlik")
    s.calls.clear()
    await send(bot, dp, CUSTOMER, "/start")
    assert any("bloklangan" in x and "Qoidabuzarlik" in x for x in s.texts(CUSTOMER))
    assert not any("Assalomu" in x for x in s.texts(CUSTOMER))
    s.calls.clear()
    await click(bot, dp, CUSTOMER, "sh:cat:1:0:0")
    assert any(type(c).__name__ == "AnswerCallbackQuery" and c.show_alert for c in s.calls)
    await db.set_banned(CUSTOMER, False)
    s.calls.clear()
    await send(bot, dp, CUSTOMER, "/start")
    assert not any("bloklangan" in x for x in s.texts(CUSTOMER))
