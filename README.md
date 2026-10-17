# Tech.Zone — elektronika do'koni uchun Telegram bot, Mini App va do'kon paneli

Smartfon, noutbuk, planshet va aksessuarlar sotadigan onlayn do'kon uchun yechim.
Mijoz Telegram Mini App yoki botning o'zida buyurtma beradi. Xodimlar buyurtmani bot ichida yuritadi.
Menejer esa butun do'konni brauzerdagi panelda boshqaradi: savdo, ombor, xaridlar, kontent.

**White-label:** loyiha boshqa do'konga bitta prompt bilan moslashadi (nom, logo, rang, prefiks).
Qolgan hamma narsa admin paneldan o'zgartiriladi. Batafsil: [`docs/REBRAND.md`](docs/REBRAND.md).

## Imkoniyatlar

### 🙋 Mijoz — Mini App (liquid glass, macOS-dock uslubidagi pastki panel)

**Katalog va mahsulot**
- Bosh sahifa: chegirmalar, xitlar, yangi mahsulotlar, brendlar.
- Katalog: kategoriya, brend filtri, narx oralig'i va saralash (arzon/qimmat/ommabop/yangi).
- Mahsulot sahifasi:
  - rasm galereyasi; rang tanlanganda shu rangdagi rasm ko'rsatiladi;
  - variantlar (rang, xotira va h.k.), har birining o'z narxi va qoldig'i bor;
  - xususiyatlar jadvali va kafolat muddati;
  - "Sotuvda yo'q" holatida "kelganda xabar berish" tugmasi.

**Saralash va savat**
- ❤️ Saralanganlar va ⚖️ taqqoslash jadvali (4 tagacha mahsulot).
- Savat, promo-kod, viloyat bo'yicha yetkazish narxi va muddati (masalan "2–4 kun"), ma'lum summadan bepul.
- Olib ketish ham bor.

**To'lov:** naqd. Karta — "tez kunda".

**Buyurtmalarim**
- Holat chizig'i: Qabul qilindi → Yig'ilmoqda → Yo'lda → Yetkazildi.
- Olib ketishda: "Tayyor — olib ketishingiz mumkin".
- Har bosqichda do'kon yuborgan rasmlar.
- Kafolat kartasi (IMEI yoki seriya raqami bilan).
- **Buyurtma chati.** Buyurtma yakunlangach yopiladi.
- **↩️ Qaytarish** — admin belgilagan muddat ichida: sabab va rasm bilan forma, panelga boradi, xodim qo'ng'iroq qiladi, keyin tasdiqlanadi yoki rad etiladi.
- **⚠️ Muammo haqida xabar** — har bir buyurtmada, yopilganlarida ham: savol va rasm.

**Til:** o'zbek va rus.

### 🤖 Bot (Telegram rich messages — Bot API 10)
- Botdagi barcha xabarlar Telegramning yangi **rich** formatida keladi: sarlavha, jadval, galereya, belgilar ro'yxati, yig'iladigan bloklar, xarita.
- Eski Telegram ilovalari uchun oddiy HTML ga avtomatik o'tadi.
- Mini App siz to'liq xarid qilish mumkin:
  - katalog, brend bo'yicha filtr, qidiruv;
  - mahsulot kartasi (galereya, variant tugmalari, xususiyatlar jadvali);
  - savat va rasmiylashtirish: ism, telefon, viloyat, manzil, izoh, promo;
  - buyurtmalarim, chat, qaytarish va muammo xabari.

### 👷 Xodim kabineti (bot ichida)
- Yangi buyurtma barcha xodimlarga keladi. Holat tugmalari bor; bir xodim bossa, xabar hammada yangilanadi.
- Har bosqichda **rasm** (ixtiyoriy) yuborish, buyurtma chatiga javob berish, **IMEI/seriya** kiritish.
- Murojaatlar: qaytarishni tasdiqlash (omborga qaytarib yoki qaytarmasdan), rad etish (sabab bilan), muammoni hal qilingan deb belgilash.
- Bekor qilinganda yoki qaytarilganda mahsulot omborga avtomatik qaytadi.

### 🖥 Do'kon paneli (`/admin`) — to'liq onlayn do'kon boshqaruvi

**Savdo**
- **Dashboard:** tushum, yalpi foyda va marja, o'rtacha chek, jarayondagi summa, xaridlar; kunlik tushum va foyda grafigi; top mahsulot va brendlar; kam qolganlar; javobsiz chatlar; ochiq murojaatlar.
- **Buyurtmalar:** holat bo'yicha tablar, qidiruv, buyurtma kartasi (tannarx, IMEI, chat va rasm, holat rasmlari, bekor qilish, o'chirish).
- **Murojaatlar:** qaytarish va muammo xabarlari.
- **Mijozlar va baholar.**

**Katalog va ombor**
- **Mahsulot muharriri:**
  - variant turlari, ulardan avtomatik narx-qoldiq matritsasi;
  - galereya (drag-and-drop, rangga biriktirish, tartib);
  - xususiyatlar, kategoriya shabloni bilan;
  - belgilar (Hit/Yangi/Top), chegirma va uning muddati, kafolat.
- **Kategoriya va brendlar:** xususiyat shablonlari, brend logolari, tartib.
- **Ombor:**
  - qoldiqlar va inventarizatsiya;
  - har bir variant harakatlari tarixi;
  - ombor qiymati: tannarxda va sotuv narxida;
  - CSV eksport.
- **Xaridlar (kirim):**
  - yetkazib beruvchilar;
  - kirim hujjatlari;
  - tannarx o'rtacha og'irlik usulida hisoblanadi;
  - mahsulot sotuvga qaytganda obuna bo'lgan mijozlarga xabar boradi.

**Marketing:** promo-kodlar; rassilka (rasm va "Katalog" tugmasi bilan).

**Sozlamalar**
- Do'kon holati.
- Brend: nom, shior, logo, rang, buyurtma prefiksi.
- Aloqa va olib ketish manzili.
- Qaytarish muddati.
- Operatorlar ish vaqti.
- Yetkazish hududlari.
- Bot matnlari (uz/ru).
- Xodimlar.
- CSV hisobot va zaxira nusxa.

### 👑 Menejer paneli (bot ichida)
- Tezkor statistika, buyurtmalar, kam qolgan mahsulotlar, xabar yuborish, xodimlar, mijozlar.
- Do'kon holati: qabul qilish rejimi, yetkazish va olib ketishni yoqish/o'chirish.
- CSV hisobot, zaxira nusxa.
- **🖥 Do'kon paneli** — panelga bir martalik kirish havolasi.

### Ishonchlilik
- **Ombor rezervi:** buyurtma berilganda qoldiq darhol band qilinadi. Bu blokirovka ostida bajariladi, shuning uchun ikki mijoz oxirgi donani bir vaqtda ololmaydi.
- Har bir harakat `stock_moves` jurnaliga yoziladi.
- Har kuni soat 04:00 da zaxira nusxa (baza va rasmlar) bosh menejerga yuboriladi.

## Texnologiyalar

Python 3.11+, aiogram 3, aiohttp, SQLite (aiosqlite), Pillow. Frontend — framework siz (vanilla JS, CSS).
Docker va Caddy (avtomatik HTTPS).

```
main.py               bot + web server
app/
  db.py               sxema, buyurtma va savat yordamchilari
  products.py         katalog CRUD
  catalog.py          narx, chegirma, variant, qoldiq holati
  inventory.py        rezerv, kirim, harakatlar, "kelganda xabar"
  regions.py          yetkazish hududlari
  orders.py           hisob-kitob, buyurtma berish va bekor qilish, qaytarish
  tickets.py          qaytarish va muammo xabarlari
  chat.py             buyurtma chati
  rich.py             Telegram rich message builder va fallback
  notify.py           xodim va mijozga bildirishnomalar
  i18n.py             uz/ru matnlar
  texts_admin.py      paneldan tahrirlanadigan matnlar
  brand.py            white-label sozlamalari
  webapp.py           Mini App API
  admin_api.py        panel API
  handlers/           bot handlerlari (shop, staff, admin, common)
webapp/               Mini App (index.html, app.js, style.css)
  admin/              do'kon paneli
  brand/              logo fayllari
  img/demo/           demo mahsulot rasmlari
deploy/               o'rnatish va yangilash skriptlari, Caddyfile
tools/                dev_server.py, gen_demo_images.py
tests/                pytest
```

## Lokal ishga tushirish

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest                                   # testlar

# Botsiz brauzerda ko'rish (demo katalog bilan):
python tools/dev_server.py 8090
#   Mini App:  http://localhost:8090/?dev_user=1
#   Panel:     http://localhost:8090/admin/?dev_user=1

# Haqiqiy bot bilan:
cp .env.example .env                     # BOT_TOKEN, ADMIN_IDS, WEBAPP_URL ni to'ldiring
python main.py
```

Mini App Telegramda faqat `https://` manzilda ochiladi. Serverga o'rnatish: [`DEPLOY.md`](DEPLOY.md).

## Xavfsizlik
- Bot tokeni faqat `.env` da turadi. U repoga kirmaydi (`.gitignore`, `.dockerignore`).
- Mini App so'rovlari Telegram `initData` imzosi bilan tekshiriladi.
- Panelga faqat menejer kira oladi: botdan olingan bir martalik havola (15 daqiqa), sessiya tokeni.
- `DEBUG=1` (initData siz kirish) faqat lokal test uchun. Production'da doim `DEBUG=0`.
