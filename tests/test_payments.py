"""Kartaga o'tkazma: karta sozlamasi, chek yuklash, menejer tasdiqlashi / rad etishi (sabab bilan)."""
from aiohttp import FormData

from app import db
from app.orders import place_order
from tests.conftest import H, admin_headers, variant_of
from tests.test_bot_flows import ADMIN, CUSTOMER, click, env, photo, send, setup_people  # noqa: F401
from tests.test_tickets import png


def receipt_form() -> FormData:
    form = FormData()
    form.add_field("photo", png(), filename="chek.jpg", content_type="image/jpeg")
    return form


async def enable_card(client, hdr) -> None:
    r = await client.put("/api/admin/settings", headers=hdr, json={
        "card_enabled": True, "card_number": "8600123456789012", "card_holder": "ALI VALIYEV", "card_bank": "Uzcard"})
    assert r.status == 200, await r.text()


async def card_order(client, uid: int = 70) -> dict:
    v = await variant_of("AirPods Pro 2")
    r = await client.post("/api/orders", headers=H(uid), json={
        "name": "Ali", "phone": "+998901234567", "order_type": "pickup", "payment_method": "card",
        "items": [{"variant_id": v["id"], "qty": 1}]})
    assert r.status == 200, await r.text()
    return (await r.json())["order"]


async def test_card_disabled_by_default(client):
    v = await variant_of("AirPods Pro 2")
    r = await client.post("/api/orders", headers=H(71), json={
        "name": "Ali", "phone": "+998901234567", "order_type": "pickup", "payment_method": "card",
        "items": [{"variant_id": v["id"], "qty": 1}]})
    assert r.status == 400
    boot = await (await client.get("/api/bootstrap", headers=H(71))).json()
    assert boot["settings"]["card_enabled"] is False


async def test_receipt_approve_flow(client):
    hdr = await admin_headers(client)
    r = await client.put("/api/admin/settings", headers=hdr, json={"card_enabled": True, "card_number": "123"})
    assert r.status == 400  # noto'g'ri karta raqami
    await enable_card(client, hdr)
    boot = await (await client.get("/api/bootstrap", headers=H(70))).json()
    assert boot["settings"]["card_enabled"] is True

    o = await card_order(client)
    assert o["pay_status"] == "await" and o["can_upload_receipt"]
    assert o["card"]["number"] == "8600 1234 5678 9012" and o["card"]["holder"] == "ALI VALIYEV"

    # rasmsiz yuborib bo'lmaydi, begona mijoz yubora olmaydi
    r = await client.post(f"/api/orders/{o['code']}/receipt", headers=H(70), data={"x": "1"})
    assert r.status == 400
    r = await client.post(f"/api/orders/{o['code']}/receipt", headers=H(99), data=receipt_form())
    assert r.status == 404

    r = await client.post(f"/api/orders/{o['code']}/receipt", headers=H(70), data=receipt_form())
    d = await r.json()
    assert r.status == 200 and d["order"]["pay_status"] == "review" and d["order"]["pay_receipt"].startswith("uploads/")
    assert not d["order"]["can_upload_receipt"] and d["order"]["card"] is None
    # tekshiruvdagi chekni qayta yuborib bo'lmaydi
    r = await client.post(f"/api/orders/{o['code']}/receipt", headers=H(70), data=receipt_form())
    assert r.status == 409

    dash = await (await client.get("/api/admin/dashboard?period=today", headers=hdr)).json()
    assert dash["pay_review"] == 1
    lst = await (await client.get("/api/admin/orders?status=payreview", headers=hdr)).json()
    assert [x["code"] for x in lst["orders"]] == [o["code"]]

    r = await client.post(f"/api/admin/orders/{o['id']}/payment", headers=hdr, json={"action": "approve"})
    d = await r.json()
    assert r.status == 200 and d["order"]["pay_status"] == "paid" and d["order"]["pay_label"] == "✅ To'landi"
    # ikki marta qaror qabul qilinmaydi
    r = await client.post(f"/api/admin/orders/{o['id']}/payment", headers=hdr, json={"action": "reject", "note": "xato"})
    assert r.status == 409


async def test_receipt_reject_then_resend(client):
    hdr = await admin_headers(client)
    await enable_card(client, hdr)
    o = await card_order(client, 72)
    await client.post(f"/api/orders/{o['code']}/receipt", headers=H(72), data=receipt_form())
    r = await client.post(f"/api/admin/orders/{o['id']}/payment", headers=hdr, json={"action": "reject", "note": ""})
    assert r.status == 409  # sababsiz rad etib bo'lmaydi
    r = await client.post(f"/api/admin/orders/{o['id']}/payment", headers=hdr,
                          json={"action": "reject", "note": "Summa hisobga tushmadi"})
    assert (await r.json())["order"]["pay_status"] == "rejected"
    o2 = (await (await client.get(f"/api/orders/{o['code']}", headers=H(72))).json())["order"]
    assert o2["pay_status"] == "rejected" and o2["pay_note"] == "Summa hisobga tushmadi" and o2["can_upload_receipt"]
    r = await client.post(f"/api/orders/{o['code']}/receipt", headers=H(72), data=receipt_form())
    d = (await r.json())["order"]
    assert d["pay_status"] == "review" and d["pay_note"] == ""


async def test_bot_card_checkout_receipt_and_manager_reject(env):
    bot, dp, s = env
    await setup_people(bot, dp)
    await db.set_setting("card_enabled", "1")
    await db.set_setting("card_number", "8600 1234 5678 9012")
    v = await variant_of("AirPods Pro 2")
    oid = await place_order(CUSTOMER, {"name": "Ali", "phone": "+998901234567", "order_type": "pickup",
                                       "payment_method": "card"}, [{"variant_id": v["id"], "qty": 1}])
    order = await db.get_order(oid)
    from app.notify import notify_new_order
    s.calls.clear()
    await notify_new_order(bot, oid)
    info = " ".join(s.texts(CUSTOMER))
    assert "8600 1234 5678 9012" in info and "3 190 000" in info
    assert "copy_text" in s.markups(CUSTOMER) and f"sh:rc:{order['code']}" in s.markups(CUSTOMER)

    # mijoz chekni botda yuboradi
    await click(bot, dp, CUSTOMER, f"sh:rc:{order['code']}")
    await send(bot, dp, CUSTOMER, "salom")  # rasm emas
    assert "rasm" in s.texts(CUSTOMER)[-1]
    s.calls.clear()
    await send(bot, dp, CUSTOMER, photo=photo())
    order = await db.get_order(oid)
    assert order["pay_status"] == "review" and order["pay_receipt"].startswith("uploads/receipt_")
    assert any("TO'LOV CHEKI" in x for x in s.texts(ADMIN))
    assert f"py:ok:{oid}" in s.markups(ADMIN)

    # menejer sabab bilan rad etadi -> mijozga sabab va qayta yuborish tugmasi
    s.calls.clear()
    await click(bot, dp, ADMIN, f"py:no:{oid}")
    await send(bot, dp, ADMIN, "Summa to'liq emas")
    order = await db.get_order(oid)
    assert order["pay_status"] == "rejected" and order["pay_note"] == "Summa to'liq emas"
    assert any("Summa to'liq emas" in x for x in s.texts(CUSTOMER))
    assert f"sh:rc:{order['code']}" in s.markups(CUSTOMER)

    # qayta yuborish va tasdiqlash
    await click(bot, dp, CUSTOMER, f"sh:rc:{order['code']}")
    await send(bot, dp, CUSTOMER, photo=photo())
    s.calls.clear()
    await click(bot, dp, ADMIN, f"py:ok:{oid}")
    assert (await db.get_order(oid))["pay_status"] == "paid"
    assert any("tasdiqlandi" in x for x in s.texts(CUSTOMER))
