"""Excel fayldan mahsulot yaratish: shablon, guruhlash, xatolarda hech narsa yaratilmasligi, Uzum shabloni."""
import io

from aiohttp import FormData
from openpyxl import Workbook, load_workbook

from app import db, product_import, products
from tests.conftest import H, admin_headers
from tests.test_tickets import png


def xlsx(headers: list[str], rows: list[list], pad_rows: int = 0) -> FormData:
    wb = Workbook()
    ws = wb.active
    for _ in range(pad_rows):
        ws.append(["Atributlar"])
    ws.append(headers)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    form = FormData()
    form.add_field("file", buf.getvalue(), filename="t.xlsx",
                   content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    return form


HEAD = ["Guruh (SKU birlashtirish)", "Nomi UZ*", "Kategoriya*", "Brend", "Rang", "O'lcham / xotira", "2-variant nomi",
        "Sotuv narxi (so'm)*", "Chegirmadan oldingi narx (so'm)", "Qoldiq (dona)", "Tannarx (so'm)", "Kafolat (oy)",
        "Rasm havolalari", "Xarakteristikalar", "Xar: Ekran"]


async def test_template_download(client):
    hdr = await admin_headers(client)
    r = await client.get("/api/admin/products/template.xlsx?category_id=1", headers=hdr)
    assert r.status == 200
    wb = load_workbook(io.BytesIO(await r.read()))
    ws = wb["Tovarlar"]
    heads = [c.value for c in ws[1]]
    assert "Nomi UZ*" in heads and "Sotuv narxi (so'm)*" in heads and "Xar: Ekran" in heads
    assert str(ws.cell(2, 2).value).startswith("✅") and ws.cell(3, heads.index("Kategoriya*") + 1).value == "Smartfonlar"
    assert wb["Ro'yxatlar"]["A2"].value == "Smartfonlar" and "Ko'rsatma" in wb.sheetnames
    # shablonning o'zi (namuna satri bilan) qayta yuklansa — o'qiladi
    rows = product_import.read_rows(await (await client.get("/api/admin/products/template.xlsx", headers=hdr)).read())
    assert len(rows) == 1 and rows[0][1]["name"] == "iPhone 15"


async def test_import_groups_variants_and_images(client, monkeypatch):
    hdr = await admin_headers(client)

    async def fake_fetch(url):
        if "bad" in url:
            raise ValueError("HTTP 404")
        return png()

    monkeypatch.setattr(product_import, "fetch_image", fake_fetch)
    form = xlsx(HEAD, [
        ["px9", "Pixel 9", "Smartfonlar", "Google", "Qora", "128 GB", "Xotira", 9_000_000, 10_000_000, 4, 7_500_000, 12,
         "https://img.test/black.jpg, https://img.test/bad.jpg", "Batareya: 4700 mA/s", "6.3\" OLED"],
        ["px9", "Pixel 9", "Smartfonlar", "Google", "Oq", "128 GB", None, 9_000_000, 10_000_000, 2, 7_500_000, None,
         "https://img.test/white.jpg", None, None],
        [None, "USB-C kabel 1m", "Kabellar", None, None, None, None, 49_000, None, None, None, None, None, None, None],
    ])
    r = await client.post("/api/admin/products/import", headers=hdr, data=form)
    d = await r.json()
    assert r.status == 200 and d["products"] == 2 and d["skus"] == 3, d
    assert any("rasm yuklab olinmadi" in w for w in d["warnings"]) and any("Kabellar" in w for w in d["warnings"])
    p = next(x for x in await products.get_products() if x["name"] == "Pixel 9")
    assert [o["name"] for o in p["options"]] == ["Rang", "Xotira"] and p["options"][0]["values"] == ["Qora", "Oq"]
    assert p["discount_percent"] == 10 and p["warranty_months"] == 12 and p["brand"]["name"] == "Google"
    assert {s["k"]: s["v"] for s in p["specs"]} == {"Ekran": '6.3" OLED', "Batareya": "4700 mA/s"}
    assert [(v["vals"], v["price"], v["stock"], v["cost"]) for v in p["variants"]] == [
        (["Qora", "128 GB"], 10_000_000, 4, 7_500_000), (["Oq", "128 GB"], 10_000_000, 2, 7_500_000)]
    assert [i["color"] for i in p["images"]] == ["Qora", "Oq"]
    boot = await (await client.get("/api/bootstrap", headers=H(5))).json()
    card = next(x for x in boot["products"] if x["name"] == "Pixel 9")
    assert card["price"] == 9_000_000  # chegirma bilan sotuv narxi
    cable = next(x for x in await products.get_products() if x["name"] == "USB-C kabel 1m")
    assert cable["options"] == [] and cable["variants"][0]["price"] == 49_000


async def test_import_errors_create_nothing(client):
    hdr = await admin_headers(client)
    before = await db.scalar("SELECT COUNT(*) FROM products")
    form = xlsx(HEAD, [
        [None, "Yaxshi tovar", "Aksessuarlar", None, None, None, None, 50_000] + [None] * 7,
        [None, "iPhone 15", "Smartfonlar", None, None, None, None, 1_000_000] + [None] * 7,   # allaqachon bor
        [None, "Narxsiz", "Aksessuarlar", None, None, None, None, None] + [None] * 7,
        ["g", "Juft", "Aksessuarlar", None, "Qora", None, None, 10_000] + [None] * 7,
        ["g", "Juft", "Aksessuarlar", None, None, None, None, "abc", None, None, None, None, "ftp://x"] + [None] * 2,
    ])
    r = await client.post("/api/admin/products/import", headers=hdr, data=form)
    d = await r.json()
    assert r.status == 400 and len(d["errors"]) == 5, d
    text = " | ".join(d["errors"])
    assert "allaqachon bor" in text and "4-satr: sotuv narxi" in text and "«Rang» to'ldirilmagan" in text
    assert "son bo'lishi kerak" in text and "rasm havolasi noto'g'ri" in text
    assert await db.scalar("SELECT COUNT(*) FROM products") == before
    r = await client.post("/api/admin/products/import", headers=hdr, data=xlsx(["A", "B"], [[1, 2]]))
    assert r.status == 400 and "sarlavhalari topilmadi" in (await r.json())["error"]


async def test_import_uzum_template(client):
    """Uzum shabloni: sarlavha 2-satrda, 3-satr — izohlar, kategoriya — to'liq yo'l."""
    hdr = await admin_headers(client)
    head = ["Название товара RU*", "Идентификатор от продавца", "Название товара UZ*",
            "Группировка SKU (до 100 символов)*", "Название категории*", "Бренд*", "Описание товара UZ*",
            "Ссылки на фото*", "Цвет", "Размер", "Цена продажи (som)*", "Цена до скидки (som)*"]
    form = xlsx(head, [
        ["✅ Обязательно\n\nУкажите название"] + [None] * 11,
        ["Наушники X", "NX-1", "Quloqchin X", "nx", "Электроника > Аудио > Наушники", "Отсутствует бренд", "Zo'r ovoz",
         None, "Чёрный", None, 99_000, 120_000],
        ["Наушники X", "NX-2", "Quloqchin X", "nx", "Электроника > Аудио > Наушники", "Отсутствует бренд", None,
         None, "Белый", None, 99_000, 120_000],
    ], pad_rows=1)
    d = await (await client.post("/api/admin/products/import", headers=hdr, data=form)).json()
    assert d.get("products") == 1 and d["skus"] == 2, d
    p = next(x for x in await products.get_products() if x["name"] == "Quloqchin X")
    cat = await products.get_category(p["category_id"])
    assert p["name_ru"] == "Наушники X" and cat["name"] == "Quloqchinlar" and not p["brand"]  # ruscha nomi bo'yicha topildi
    assert [v["sku"] for v in p["variants"]] == ["NX-1", "NX-2"] and p["discount_percent"] == 18
