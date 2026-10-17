"""Boshlang'ich ma'lumotlar: O'zbekiston hududlari va demo katalog (faqat baza bo'sh bo'lsa).

Demo mahsulotlar `is_demo = 1` belgisi bilan yoziladi va admin paneldan bitta tugma bilan o'chiriladi.
"""
import json

from . import db
from .utils import now_str

REGIONS = [
    # (uz, ru, narx, muddat dan, gacha)
    ("Toshkent shahri", "г. Ташкент", 30_000, 0, 1),
    ("Toshkent viloyati", "Ташкентская обл.", 50_000, 1, 2),
    ("Andijon", "Андижан", 70_000, 2, 4),
    ("Buxoro", "Бухара", 70_000, 2, 4),
    ("Farg'ona", "Фергана", 70_000, 2, 4),
    ("Jizzax", "Джизак", 70_000, 2, 3),
    ("Namangan", "Наманган", 70_000, 2, 4),
    ("Navoiy", "Навои", 70_000, 2, 4),
    ("Qashqadaryo", "Кашкадарья", 70_000, 2, 4),
    ("Qoraqalpog'iston", "Каракалпакстан", 70_000, 3, 5),
    ("Samarqand", "Самарканд", 70_000, 2, 3),
    ("Sirdaryo", "Сырдарья", 70_000, 2, 3),
    ("Surxondaryo", "Сурхандарья", 70_000, 3, 5),
    ("Xorazm", "Хорезм", 70_000, 3, 5),
]
FREE_FROM = 5_000_000

PHONE_SPECS = [("Ekran", "Экран"), ("Protsessor", "Процессор"), ("Operativ xotira", "Оперативная память"),
               ("Asosiy kamera", "Основная камера"), ("Batareya", "Аккумулятор"), ("SIM", "SIM")]
LAPTOP_SPECS = [("Ekran", "Экран"), ("Protsessor", "Процессор"), ("Operativ xotira", "Оперативная память"),
                ("Xotira (SSD)", "Накопитель (SSD)"), ("Videokarta", "Видеокарта"), ("Og'irligi", "Вес")]
TABLET_SPECS = [("Ekran", "Экран"), ("Protsessor", "Процессор"), ("Batareya", "Аккумулятор"),
                ("Aloqa", "Связь")]
AUDIO_SPECS = [("Turi", "Тип"), ("Shovqinni bostirish", "Шумоподавление"), ("Ishlash vaqti", "Время работы"),
               ("Ulanish", "Подключение")]
WATCH_SPECS = [("Ekran", "Экран"), ("Korpus", "Корпус"), ("Batareya", "Аккумулятор"), ("Himoya", "Защита")]
ACC_SPECS = [("Quvvat", "Мощность"), ("Sig'im", "Ёмкость"), ("Portlar", "Порты")]

CATEGORIES = [
    ("Smartfonlar", "Смартфоны", "📱", PHONE_SPECS),
    ("Noutbuklar", "Ноутбуки", "💻", LAPTOP_SPECS),
    ("Planshetlar", "Планшеты", "📲", TABLET_SPECS),
    ("Quloqchinlar", "Наушники", "🎧", AUDIO_SPECS),
    ("Smart soatlar", "Смарт-часы", "⌚", WATCH_SPECS),
    ("Aksessuarlar", "Аксессуары", "🔌", ACC_SPECS),
]

BRANDS = ["Apple", "Samsung", "Xiaomi", "Lenovo", "ASUS", "JBL", "Anker"]

COLOR_RU = {
    "Qora": "Чёрный", "Ko'k": "Голубой", "Pushti": "Розовый", "Tabiiy titan": "Натуральный титан",
    "Qora titan": "Чёрный титан", "Kulrang titan": "Серый титан", "To'q ko'k": "Тёмно-синий",
    "Siren": "Сиреневый", "Binafsha": "Фиолетовый", "Kulrang": "Серый", "Tun moviy": "Полночь",
    "Kumush": "Серебристый", "Oq": "Белый",
}

# (kategoriya, brend, nom, tavsif uz, tavsif ru, kafolat oy, badge, chegirma %,
#  ranglar [(nom, rasm)], ikkinchi opsiya (nom, nom_ru, qiymatlar) yoki None,
#  narxlar {ikkinchi opsiya qiymati: narx}, qoldiq, xarakteristikalar [(uz, ru)])
PRODUCTS = [
    ("Smartfonlar", "Apple", "iPhone 15",
     "Dynamic Island, 48 MP kamera va USB-C. Kundalik foydalanish uchun eng muvozanatli iPhone.",
     "Dynamic Island, камера 48 Мп и USB-C. Самый сбалансированный iPhone на каждый день.",
     12, "hit", 0, [("Qora", "iphone15-black"), ("Ko'k", "iphone15-blue"), ("Pushti", "iphone15-pink")],
     ("Xotira", "Память", ["128 GB", "256 GB"]), {"128 GB": 10_990_000, "256 GB": 12_490_000}, 6,
     ["6.1\" Super Retina XDR OLED", "A16 Bionic", "6 GB", "48 MP + 12 MP", "3349 mAh, 20 W", "nanoSIM + eSIM"]),
    ("Smartfonlar", "Apple", "iPhone 15 Pro Max",
     "Titan korpus, A17 Pro chip va 5x optik zum. Eng kuchli iPhone.",
     "Титановый корпус, чип A17 Pro и 5-кратный оптический зум. Самый мощный iPhone.",
     12, "top", 0, [("Tabiiy titan", "iphone15pm-natural"), ("Qora titan", "iphone15pm-black")],
     ("Xotira", "Память", ["256 GB", "512 GB"]), {"256 GB": 17_490_000, "512 GB": 20_490_000}, 4,
     ["6.7\" ProMotion OLED 120 Hz", "A17 Pro", "8 GB", "48 + 12 + 12 MP (5x)", "4441 mAh", "nanoSIM + eSIM"]),
    ("Smartfonlar", "Samsung", "Galaxy S24 Ultra",
     "Galaxy AI, S Pen va 200 MP kamera. Titan korpusdagi flagman.",
     "Galaxy AI, S Pen и камера 200 Мп. Флагман в титановом корпусе.",
     12, "top", 10, [("Kulrang titan", "s24u-gray"), ("Qora titan", "s24u-black")],
     ("Xotira", "Память", ["256 GB", "512 GB"]), {"256 GB": 15_990_000, "512 GB": 17_990_000}, 5,
     ["6.8\" Dynamic AMOLED 2X 120 Hz", "Snapdragon 8 Gen 3", "12 GB", "200 + 50 + 12 + 10 MP",
      "5000 mAh, 45 W", "2 × nanoSIM + eSIM"]),
    ("Smartfonlar", "Samsung", "Galaxy A55",
     "Metall ramka, IP67 himoya va yorqin Super AMOLED ekran.",
     "Металлическая рамка, защита IP67 и яркий Super AMOLED экран.",
     12, "", 0, [("To'q ko'k", "a55-navy"), ("Siren", "a55-lilac")],
     ("Xotira", "Память", ["128 GB", "256 GB"]), {"128 GB": 4_990_000, "256 GB": 5_590_000}, 9,
     ["6.6\" Super AMOLED 120 Hz", "Exynos 1480", "8 GB", "50 + 12 + 5 MP", "5000 mAh, 25 W", "2 × nanoSIM"]),
    ("Smartfonlar", "Xiaomi", "Redmi Note 13 Pro",
     "200 MP kamera va 67 W tezkor quvvatlash — narxiga ko'ra eng yaxshi tanlov.",
     "Камера 200 Мп и быстрая зарядка 67 Вт — лучший выбор за свои деньги.",
     12, "hit", 0, [("Qora", "rn13-black"), ("Binafsha", "rn13-purple")],
     ("Xotira", "Память", ["256 GB"]), {"256 GB": 3_990_000}, 12,
     ["6.67\" AMOLED 120 Hz", "Snapdragon 7s Gen 2", "8 GB", "200 + 8 + 2 MP", "5100 mAh, 67 W", "2 × nanoSIM"]),
    ("Smartfonlar", "Xiaomi", "Xiaomi 14T",
     "Leica optikasi bilan yangi avlod kamera va 144 Hz ekran.",
     "Камера нового поколения с оптикой Leica и экран 144 Гц.",
     12, "new", 0, [("Qora", "x14t-black"), ("Kulrang", "x14t-gray")],
     ("Xotira", "Память", ["512 GB"]), {"512 GB": 7_490_000}, 3,
     ["6.67\" AMOLED 144 Hz", "Dimensity 8300-Ultra", "12 GB", "50 + 50 + 12 MP Leica", "5000 mAh, 67 W",
      "2 × nanoSIM + eSIM"]),
    ("Noutbuklar", "Apple", "MacBook Air 13 M3",
     "Yupqa, yengil va jim — 18 soatgacha ishlaydi.",
     "Тонкий, лёгкий и бесшумный — до 18 часов работы.",
     12, "hit", 0, [("Tun moviy", "mba-midnight"), ("Kumush", "mba-silver")],
     ("Konfiguratsiya", "Конфигурация", ["8/256 GB", "16/512 GB"]), {"8/256 GB": 14_490_000, "16/512 GB": 19_990_000},
     3, ["13.6\" Liquid Retina", "Apple M3 (8 yadro)", "8–16 GB", "256–512 GB", "Apple 10-core GPU", "1.24 kg"]),
    ("Noutbuklar", "Lenovo", "IdeaPad Slim 5",
     "Ish va o'qish uchun ishonchli noutbuk: OLED ekran va uzoq batareya.",
     "Надёжный ноутбук для работы и учёбы: OLED-экран и долгая автономность.",
     12, "", 0, [], None, {"": 8_990_000}, 5,
     ["14\" 2.8K OLED", "Ryzen 7 8845HS", "16 GB", "1 TB", "Radeon 780M", "1.46 kg"]),
    ("Noutbuklar", "ASUS", "TUF Gaming F15",
     "O'yinlar uchun: RTX 4060 va 144 Hz ekran.",
     "Для игр: RTX 4060 и экран 144 Гц.",
     24, "", 7, [], None, {"": 11_490_000}, 2,
     ["15.6\" FHD 144 Hz", "Core i7-13620H", "16 GB", "512 GB", "RTX 4060 8 GB", "2.2 kg"]),
    ("Planshetlar", "Apple", "iPad Air 11 M2",
     "M2 chip, Apple Pencil Pro va Magic Keyboard bilan ishlaydi.",
     "Чип M2, поддержка Apple Pencil Pro и Magic Keyboard.",
     12, "new", 0, [("Kulrang", "ipadair-gray"), ("Ko'k", "ipadair-blue")],
     ("Xotira", "Память", ["128 GB", "256 GB"]), {"128 GB": 8_490_000, "256 GB": 9_990_000}, 4,
     ["11\" Liquid Retina", "Apple M2", "28.6 Wh", "Wi-Fi 6E"]),
    ("Planshetlar", "Samsung", "Galaxy Tab S9 FE",
     "S Pen to'plamda, IP68 himoya — o'qish va ijod uchun.",
     "S Pen в комплекте, защита IP68 — для учёбы и творчества.",
     12, "", 0, [], None, {"": 5_290_000}, 6,
     ["10.9\" TFT 90 Hz", "Exynos 1380", "8000 mAh", "Wi-Fi 6"]),
    ("Quloqchinlar", "Apple", "AirPods Pro 2",
     "Faol shovqin bostirish, shaffof rejim va USB-C quti.",
     "Активное шумоподавление, режим прозрачности и кейс USB-C.",
     12, "hit", 0, [], None, {"": 3_190_000}, 15,
     ["TWS", "Ha (ANC)", "6 soat / 30 soat quti bilan", "Bluetooth 5.3"]),
    ("Quloqchinlar", "JBL", "JBL Tune 770NC",
     "70 soatgacha musiqa va adaptiv shovqin bostirish.",
     "До 70 часов музыки и адаптивное шумоподавление.",
     12, "", 15, [("Qora", "jbl-black"), ("Oq", "jbl-white")], None, {"": 1_190_000}, 8,
     ["To'liq o'lchamli", "Ha (Adaptive ANC)", "70 soat", "Bluetooth 5.3, 3.5 mm"]),
    ("Smart soatlar", "Apple", "Apple Watch Series 9",
     "Yorqinroq ekran, ikki marta bosish imo-ishorasi va sog'liq kuzatuvi.",
     "Более яркий экран, жест двойного касания и мониторинг здоровья.",
     12, "", 0, [("Tun moviy", "watch9-midnight"), ("Kumush", "watch9-silver")],
     ("O'lcham", "Размер", ["41 mm", "45 mm"]), {"41 mm": 5_490_000, "45 mm": 5_990_000}, 4,
     ["Always-On Retina", "Alyuminiy", "18 soat", "WR50, IP6X"]),
    ("Aksessuarlar", "Anker", "Anker PowerCore 20000",
     "20 000 mAh, ikkita qurilmani bir vaqtda quvvatlaydi.",
     "20 000 мАч, заряжает два устройства одновременно.",
     18, "", 0, [], None, {"": 590_000}, 0,
     ["22.5 W", "20 000 mAh", "USB-C, 2 × USB-A"]),
    ("Aksessuarlar", "Samsung", "Samsung 25W quvvatlagich",
     "Super Fast Charging, USB-C — barcha zamonaviy smartfonlar uchun.",
     "Super Fast Charging, USB-C — для всех современных смартфонов.",
     12, "", 0, [], None, {"": 249_000}, 20,
     ["25 W", "—", "USB-C"]),
]
# rangsiz mahsulotlarning rasmi
SINGLE_IMAGES = {"IdeaPad Slim 5": "ideapad", "TUF Gaming F15": "tuf", "Galaxy Tab S9 FE": "tabs9fe",
                 "AirPods Pro 2": "airpods", "Anker PowerCore 20000": "anker", "Samsung 25W quvvatlagich": "charger"}


async def seed_regions() -> None:
    if await db.scalar("SELECT COUNT(*) FROM regions"):
        return
    for pos, (name, name_ru, fee, lo, hi) in enumerate(REGIONS):
        await db.db().execute(
            "INSERT INTO regions(name, name_ru, fee, free_from, days_min, days_max, sort) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, name_ru, fee, FREE_FROM, lo, hi, pos),
        )
    await db.db().commit()


async def seed_demo_catalog() -> None:
    if await db.scalar("SELECT COUNT(*) FROM categories"):
        return
    conn = db.db()
    cat_ids, brand_ids = {}, {}
    for pos, (name, name_ru, emoji, specs) in enumerate(CATEGORIES):
        cur = await conn.execute(
            "INSERT INTO categories(name, name_ru, emoji, spec_template, sort) VALUES (?, ?, ?, ?, ?)",
            (name, name_ru, emoji, json.dumps([{"k": k, "k_ru": r} for k, r in specs], ensure_ascii=False), pos))
        cat_ids[name] = (cur.lastrowid, specs)
    for pos, name in enumerate(BRANDS):
        cur = await conn.execute("INSERT INTO brands(name, sort) VALUES (?, ?)", (name, pos))
        brand_ids[name] = cur.lastrowid

    ts = now_str()
    for pos, (cat, brand, name, desc, desc_ru, warranty, badge, discount, colors, second, prices, stock,
              spec_values) in enumerate(PRODUCTS):
        cat_id, spec_keys = cat_ids[cat]
        options = []
        if colors:
            options.append({"name": "Rang", "name_ru": "Цвет", "values": [c for c, _ in colors],
                            "values_ru": [COLOR_RU.get(c, c) for c, _ in colors]})
        if second:
            options.append({"name": second[0], "name_ru": second[1], "values": second[2]})
        specs = [{"k": k, "k_ru": kr, "v": v, "v_ru": ""} for (k, kr), v in zip(spec_keys, spec_values)]
        cur = await conn.execute(
            "INSERT INTO products(category_id, brand_id, name, name_ru, description, description_ru, options, specs,"
            " warranty_months, badges, discount_percent, is_demo, sort, created_at)"
            " VALUES (?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
            (cat_id, brand_ids[brand], name, desc, desc_ru, json.dumps(options, ensure_ascii=False),
             json.dumps(specs, ensure_ascii=False), warranty, badge, discount, pos, ts))
        pid = cur.lastrowid
        images = [(f"img/demo/{img}.jpg", c) for c, img in colors] or [(f"img/demo/{SINGLE_IMAGES[name]}.jpg", "")]
        for ipos, (path, color) in enumerate(images):
            await conn.execute("INSERT INTO product_images(product_id, path, color, sort) VALUES (?, ?, ?, ?)",
                               (pid, path, color, ipos))
        # variantlar: rang × ikkinchi opsiya
        color_vals = [c for c, _ in colors] or [None]
        second_vals = second[2] if second else [None]
        vpos = 0
        for ci, c in enumerate(color_vals):
            for s in second_vals:
                vals = [x for x in (c, s) if x is not None]
                price = prices[s or ""]
                # demo: qoldiq variantlar bo'yicha har xil, ba'zilari tugagan
                qty = max(0, stock - ci * 2 - vpos % 2) if stock else 0
                cur = await conn.execute(
                    "INSERT INTO variants(product_id, vals, sku, price, cost, stock, sort) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (pid, json.dumps(vals, ensure_ascii=False), f"TZ-{pid:03d}-{vpos + 1:02d}", price,
                     int(price * 0.82) // 1000 * 1000, qty, vpos))
                if qty:
                    await conn.execute(
                        "INSERT INTO stock_moves(variant_id, delta, reason, note, at) VALUES (?, ?, 'adjust', ?, ?)",
                        (cur.lastrowid, qty, "Demo qoldiq", ts))
                vpos += 1
    await conn.commit()
