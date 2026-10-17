"""Qaytarish va "muammo haqida xabar berish": muddat, rasm, flooddan himoya, chat yopilishi, qaror."""
import io

from aiohttp import FormData

from app import db, products, tickets
from app.orders import place_order
from tests.conftest import H, admin_headers, variant_of
from tests.test_bot_flows import ADMIN, CUSTOMER, STAFF, click, env, photo, send, setup_people  # noqa: F401


def png() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (300, 300), (200, 200, 200)).save(buf, "JPEG")
    return buf.getvalue()


async def delivered_order(uid: int, qty: int = 1) -> tuple[dict, dict]:
    v = await variant_of("AirPods Pro 2")
    await db.upsert_user(uid, f"U{uid}", None, None)
    oid = await place_order(uid, {"name": "Ali", "phone": "+998901234567", "order_type": "pickup",
                                  "payment_method": "cash"}, [{"variant_id": v["id"], "qty": qty}])
    for st in ("accepted", "packing", "shipping", "delivered"):
        await db.set_order_status(oid, st, 2)
    return await db.get_order(oid), v


def ticket_form(kind: str, reason: str, with_photo: bool = True) -> FormData:
    form = FormData()
    form.add_field("kind", kind)
    form.add_field("reason", reason)
    if with_photo:
        form.add_field("photo", png(), filename="p.jpg", content_type="image/jpeg")
    return form


async def test_return_flow_api(client):
    hdr = await admin_headers(client)
    order, v = await delivered_order(60)
    stock = (await products.get_variant(v["id"]))["stock"]
    o = (await (await client.get(f"/api/orders/{order['code']}", headers=H(60))).json())["order"]
    assert o["can_return"] and o["return_until"] and not o["chat_open"]
    # chat yopilgan
    r = await client.post(f"/api/orders/{order['code']}/chat", headers=H(60), json={"text": "salom"})
    assert r.status == 409
    # rasmsiz qaytarish va qisqa sabab rad etiladi
    r = await client.post(f"/api/orders/{order['code']}/tickets", headers=H(60),
                          data=ticket_form("return", "Ishlamayapti, chap quloqchin ovoz bermaydi", False))
    assert r.status == 400
    r = await client.post(f"/api/orders/{order['code']}/tickets", headers=H(60), data=ticket_form("return", "yomon"))
    assert r.status == 400
    r = await client.post(f"/api/orders/{order['code']}/tickets", headers=H(60),
                          data=ticket_form("return", "Ishlamayapti, chap quloqchin ovoz bermaydi"))
    d = await r.json()
    assert r.status == 200 and d["order"]["has_open_ticket"] and d["order"]["tickets"][0]["status"] == "open"
    # flood: ochiq murojaat bor ekan — yangisi qabul qilinmaydi
    r = await client.post(f"/api/orders/{order['code']}/tickets", headers=H(60),
                          data=ticket_form("issue", "Yana bir savolim bor edi, iltimos"))
    assert r.status == 409

    lst = (await (await client.get("/api/admin/tickets", headers=hdr)).json())
    assert lst["open"] == 1 and lst["tickets"][0]["photos"][0].startswith("uploads/")
    tid = lst["tickets"][0]["id"]
    r = await client.post(f"/api/admin/tickets/{tid}", headers=hdr, json={"action": "reject"})
    assert r.status == 400  # sababsiz rad etib bo'lmaydi
    r = await client.post(f"/api/admin/tickets/{tid}", headers=hdr, json={"action": "approve", "restock": True})
    assert (await r.json())["ticket"]["status"] == "approved"
    assert (await db.get_order(order["id"]))["status"] == "returned"
    assert (await products.get_variant(v["id"]))["stock"] == stock + 1
    # takroriy qaror va qayta qaytarish yo'q
    r = await client.post(f"/api/admin/tickets/{tid}", headers=hdr, json={"action": "approve"})
    assert r.status == 400
    o = (await (await client.get(f"/api/orders/{order['code']}", headers=H(60))).json())["order"]
    assert not o["can_return"] and o["status"] == "returned"
    # qaytarilgan buyurtma tushumga kirmaydi
    dash = await (await client.get("/api/admin/dashboard?period=today", headers=hdr)).json()
    assert dash["stats"]["revenue"] == 0 and dash["open_tickets"] == 0


async def test_return_window_and_issue(client):
    hdr = await admin_headers(client)
    order, _v = await delivered_order(61)
    await db.set_setting("return_days", "0")
    o = (await (await client.get(f"/api/orders/{order['code']}", headers=H(61))).json())["order"]
    assert not o["can_return"]
    r = await client.post(f"/api/orders/{order['code']}/tickets", headers=H(61),
                          data=ticket_form("return", "Mos kelmadi, qaytarmoqchiman"))
    assert r.status == 409
    await db.set_setting("return_days", "14")
    await db.execute("UPDATE order_status_log SET at = '2020-01-01 10:00:00' WHERE order_id = ?", order["id"])
    assert not await tickets.can_return(order)  # muddat o'tgan
    # muammo xabari istalgan buyurtmada, rasmsiz ham
    r = await client.post(f"/api/orders/{order['code']}/tickets", headers=H(61),
                          data=ticket_form("issue", "Kafolat kartasini qayerdan olaman?", False))
    assert r.status == 200
    tid = (await r.json())["id"]
    r = await client.post(f"/api/admin/tickets/{tid}", headers=hdr, json={"action": "resolve", "note": "Qo'ng'iroq qilindi"})
    assert (await r.json())["ticket"]["status"] == "resolved"
    # boshqa mijoz murojaat qila olmaydi
    r = await client.post(f"/api/orders/{order['code']}/tickets", headers=H(62),
                          data=ticket_form("issue", "Begona buyurtma bo'yicha savol"))
    assert r.status == 404
    # admin yopilgan buyurtmaga chat yoza olmaydi
    r = await client.post(f"/api/admin/orders/{order['id']}/chat", headers=hdr, json={"text": "salom"})
    assert r.status == 409


async def test_return_flow_bot(env):  # noqa: F811
    bot, dp, s = env
    await setup_people(bot, dp)
    order, v = await delivered_order(CUSTOMER)
    stock = (await products.get_variant(v["id"]))["stock"]
    code = order["code"]
    s.calls.clear()
    await click(bot, dp, CUSTOMER, f"sh:o:{code}")
    kb = s.markups(CUSTOMER)
    assert f"sh:rt:{code}" in kb and f"sh:is:{code}" in kb and f"sh:ch:{code}" not in kb
    # chat yopilgan
    s.calls.clear()
    await click(bot, dp, CUSTOMER, f"sh:ch:{code}")
    assert any("chat yopildi" in str(getattr(c, "text", "")) for c in s.calls)

    await click(bot, dp, CUSTOMER, f"sh:rt:{code}")
    await send(bot, dp, CUSTOMER, "qisqa")
    await send(bot, dp, CUSTOMER, "Chap quloqchin ishlamayapti, zaryad olmaydi")
    s.calls.clear()
    await send(bot, dp, CUSTOMER, "✅ Yuborish")
    assert any("kamida bitta rasm" in x for x in s.texts(CUSTOMER))
    await send(bot, dp, CUSTOMER, photo=photo())
    await send(bot, dp, CUSTOMER, "✅ Yuborish")
    t = await tickets.open_ticket(order["id"])
    assert t and t["kind"] == "return" and len(t["photos"]) == 1
    assert any("QAYTARISH ARIZASI" in x for x in s.texts(ADMIN))
    assert any("QAYTARISH ARIZASI" in x for x in s.texts(STAFF))
    # ikkinchi murojaat (flood) qabul qilinmaydi
    s.calls.clear()
    await click(bot, dp, CUSTOMER, f"sh:is:{code}")
    assert await db.scalar("SELECT COUNT(*) FROM tickets") == 1

    # xodim rad etadi (sabab bilan)
    await click(bot, dp, STAFF, f"tk:no:{t['id']}")
    await send(bot, dp, STAFF, "Mahsulotda mexanik shikast bor")
    assert (await tickets.get(t["id"]))["status"] == "rejected"
    assert any("rad etildi" in x and "mexanik shikast" in x for x in s.texts(CUSTOMER))
    assert (await products.get_variant(v["id"]))["stock"] == stock

    # rad etilgandan keyin qayta qaytarish yo'q, lekin muammo xabari bor
    s.calls.clear()
    await click(bot, dp, CUSTOMER, f"sh:o:{code}")
    assert f"sh:rt:{code}" not in s.markups(CUSTOMER) and f"sh:is:{code}" in s.markups(CUSTOMER)
    await click(bot, dp, CUSTOMER, f"sh:is:{code}")
    await send(bot, dp, CUSTOMER, "Kafolat bo'yicha xizmat markazi qayerda?")
    await send(bot, dp, CUSTOMER, "✅ Yuborish")
    issue = await tickets.open_ticket(order["id"])
    assert issue["kind"] == "issue" and issue["photos"] == []
    await click(bot, dp, ADMIN, f"tk:done:{issue['id']}")
    assert (await tickets.get(issue["id"]))["status"] == "resolved"
    assert any("hal qilindi" in x for x in s.texts(CUSTOMER))


async def test_return_approve_bot_without_restock(env):  # noqa: F811
    bot, dp, s = env
    await setup_people(bot, dp)
    order, v = await delivered_order(CUSTOMER)
    stock = (await products.get_variant(v["id"]))["stock"]
    tid = await tickets.create(order, "return", "Nuqsonli mahsulot keldi, ekran singan", ["uploads/x.jpg"])
    await click(bot, dp, STAFF, f"tk:okn:{tid}")
    assert (await db.get_order(order["id"]))["status"] == "returned"
    assert (await products.get_variant(v["id"]))["stock"] == stock  # nuqsonli — omborga qaytmaydi
    assert any("tasdiqlandi" in x for x in s.texts(CUSTOMER))
    s.calls.clear()
    await click(bot, dp, CUSTOMER, f"sh:o:{order['code']}")
    assert "Qaytarildi" in s.texts(CUSTOMER)[-1]
