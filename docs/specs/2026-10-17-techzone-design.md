# Tech.Zone — dizayn hujjati

Sana: 2026-10-17. Asos: Yaproq go'sht boti (kod tarixsiz ko'chirilgan).

## Maqsad

Tech.Zone elektronika do'koni uchun Telegram savdo boti, Mini App va to'liq onlayn do'kon paneli.
Loyiha **white-label**: boshqa do'konga sotilganda brend (nom, logo, ranglar, shior, buyurtma prefiksi,
kontaktlar) admin paneldan o'zgartiriladi, kodga tegish shart emas. `docs/REBRAND.md` — bitta prompt bilan
yangi do'konga moslash yo'riqnomasi.

## Qarorlar (foydalanuvchi bilan kelishilgan)

| Mavzu | Qaror |
|---|---|
| Ranglar | Oq / qora / qizil (`#E0382B`). Mini App doim to'q (qora) mavzuda, "liquid glass" uslubi |
| Navigatsiya | Pastda macOS Dock'ga o'xshash panel: faol bo'lim kattalashib ajralib turadi |
| Nasiya | Kerak emas |
| To'lov | Naqd (faol), Karta — "tez kunda" (Click/Payme keyin) |
| Holatlar | Buyurtma berildi → Qabul qilindi → Yig'ilmoqda → Yo'lda → Yetkazildi. Olib ketishda: … → Yig'ilmoqda → Tayyor — olib ketishingiz mumkin → Topshirildi |
| Holat rasmi | Xodim har bir holatda ixtiyoriy rasm yuborishi mumkin (masalan, yig'ilayotgan buyurtma). Mijozga bot va Mini App'da ko'rinadi |
| Buyurtma chati | Har buyurtma ichida mijoz ↔ do'kon yozishmasi (bot va Mini App) |
| Menejer paneli | To'laqonli onlayn do'kon paneli: sotuvlar, xaridlar (kirim), ombor, foyda, mijozlar, hisobotlar |

## Javob berilmagan savollar — qabul qilingan standartlar (admin paneldan o'zgaradi)

- Valyuta: faqat so'm.
- Yetkazish: 14 hudud. Toshkent sh. 30 000 (0–1 kun), Toshkent vil. 50 000 (1–2 kun), boshqalar 70 000 (2–5 kun),
  5 000 000 so'mdan bepul. Olib ketish — do'kondan (manzil va xarita sozlamalarda).
- Qoldiq buyurtma berilganda band qilinadi (ayiriladi), bekor qilinsa qaytariladi.
- Buyurtma 24/7 qabul qilinadi; ish vaqti — operator javob beradigan vaqt. "Yopiq" rejimi buyurtmani to'xtatadi.
- Demo katalog: 14 ta namunaviy mahsulot (generatsiya qilingan rasmlar bilan), admin paneldan bitta tugma bilan o'chiriladi.
- Ixtiyoriy funksiyalar: sevimlilar, solishtirish, "kelganda xabar berish", IMEI/seriya va kafolat kartasi — barchasi kiritiladi.
- Bot ichidagi menejer paneli soddalashtiriladi (statistika, buyurtmalar, rassilka, xodimlar, holat, CSV, zaxira, web panel havolasi).
  Mahsulot/variant/xarakteristika tahriri faqat web panelda (botda bunday murakkab formani yuritish noqulay).

## Ma'lumotlar modeli (SQLite, yangi baza)

- `categories` — nom uz/ru, emoji, `spec_template` (xarakteristika kalitlari shabloni), tartib, faol.
- `brands` — nom, logo, tartib, faol.
- `products` — kategoriya, brend, nom/tavsif uz/ru, `options` (JSON: `[{name, name_ru, values:[…]}]`, masalan Rang, Xotira),
  `specs` (JSON: `[{k, k_ru, v, v_ru}]`), `warranty_months`, badge'lar, chegirma % va muddati, faol, demo belgisi.
- `product_images` — galereya: yo'l, tartib, ixtiyoriy `color` (variant rangiga bog'langan rasm).
- `variants` — mahsulotning har bir kombinatsiyasi: `values` (JSON, options tartibida), SKU, narx, tannarx (o'rtacha), qoldiq, faol.
- `stock_moves` — ombor harakatlari: kirim, sotuv, bekor (qaytish), tuzatish; kim, qachon, izoh.
- `suppliers`, `purchases`, `purchase_items` — xaridlar (kirim): qoldiqni oshiradi, tannarxni o'rtacha hisoblaydi.
- `regions` — hudud: nom uz/ru, narx, bepul chegarasi, muddat (kun dan–gacha), faol, tartib.
- `orders` — + `region_id`, `region_name`, `delivery_eta`; `order_items` — + `variant_id`, `cost`, `serial` (IMEI), `warranty_months`.
- `order_media` — holat rasmlari; `order_chat` — buyurtma yozishmasi.
- `favorites`, `stock_alerts` (kelganda xabar berish), `promo_codes`, `reviews`, `texts`, `settings`, `admin_sessions`.

Brend sozlamalari (`settings`): `shop_name`, `shop_tagline`, `shop_logo`, `brand_color`, `order_prefix`,
`shop_phone`, `shop_address`, `shop_map_url`, `instagram`, `telegram_channel`, `website`, `about_uz/ru`.
Barcha bot matnlarida `{shop}` o'zgaruvchisi do'kon nomiga almashtiriladi.

## Modullar

- `app/brand.py` — brend sozlamalari (bot matnlari, Mini App, admin uchun).
- `app/catalog.py` — mahsulot ko'rinishi, narx/chegirma, variant tanlash, mavjudlik.
- `app/products.py` — katalog so'rovlari (kategoriya, brend, mahsulot, variant, rasm).
- `app/inventory.py` — qoldiq band qilish/qaytarish, kirim, harakatlar, kam qolganlar, "kelganda xabar".
- `app/regions.py` — hududlar va yetkazish narxi.
- `app/chat.py` — buyurtma chati va holat rasmlari.
- `app/orders.py` — narx hisoblash, promo, tekshiruvlar, buyurtma yaratish (qoldiq band qilinadi).
- `app/webapp.py`, `app/admin_api.py` — Mini App va admin API.
- `webapp/` — Mini App (vanilla JS, build bosqichisiz), `webapp/admin/` — do'kon paneli.

## Bosqichlar

1. Backend asos: brend, yangi sxema, katalog, ombor, hududlar, holatlar, chat, bot oqimlari, testlar.
2. Mini App: liquid glass, Dock, bosh sahifa, katalog/filtr/saralash, mahsulot sahifasi, sevimlilar, solishtirish, savat, buyurtma, kuzatish+chat.
3. Admin panel: dashboard (sotuv, foyda), buyurtmalar (holat, rasm, chat), mahsulotlar (variantlar, galereya, xarakteristikalar),
   ombor, xaridlar, mijozlar, promo, baholar, hududlar, rassilka, matnlar, brend sozlamalari.
4. Deploy: o'sha serverda ikkinchi bot (umumiy Caddy), yo'riqnoma, `REBRAND.md`.

Har bosqich: `pytest`, Playwright skrinshotlar, commit va push.
