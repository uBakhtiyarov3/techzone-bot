# 🏷 Loyihani boshqa do'konga moslash (white-label)

Loyiha boshidan white-label qilib qurilgan. Brend ikki qatlamda turadi.

1. **Admin panel (kod o'zgarmaydi).**
   *⚙️ Do'kon va brend* bo'limida quyidagilar o'zgaradi:
   - nom, shior, logo, kichik belgi, asosiy rang, buyurtma prefiksi;
   - "Do'kon haqida" (uz/ru), Instagram, Telegram kanal, sayt;
   - telefon va manzil.

   Saqlangan zahoti bot xabarlari, Mini App va panel yangi brendda ishlaydi.
   Bot matnlari, hududlar, kategoriyalar, mahsulotlar va promo-kodlar ham paneldan o'zgaradi.
2. **Kod (yangi o'rnatish uchun boshlang'ich qiymatlar).**
   Yangi do'kon toza bazadan boshlanganda u yangi brendda chiqishi uchun quyidagilar o'zgartiriladi:
   standart sozlamalar, logo fayllari, demo katalog, repo manzili.

Odatda yangi mijoz uchun 2-qatlamni **bitta prompt** bilan Claude Code ga topshirasiz.
Qolganini mijozning o'zi paneldan to'ldiradi.

---

## Tayyor prompt (nusxa oling va `< >` larni to'ldiring)

```text
Bu repo — white-label elektronika do'koni boti (docs/REBRAND.md ga qara).
Uni yangi do'konga moslab ber:

- Do'kon nomi: <Gadget House>
- Shior: <Texnika — ishonch bilan>
- Asosiy rang: <#1E6BFF>
- Buyurtma prefiksi: <GH>   (2–4 lotin harf)
- Do'kon haqida (uz): <...>
- Do'kon haqida (ru): <...>
- Instagram / Telegram kanal / sayt: <@gadgethouse> / <@gadgethouse_uz> / <https://...>
- Logo: <logo.png ilova qilindi / URL>   (shaffof fon bo'lsa yaxshi)
- Domen: <gadgethouse.duckdns.org>
- Yangi GitHub repo: <owner/gadgethouse-bot>
- Demo katalog: <saqlansin | olib tashlansin | o'z ro'yxatim: ...>
- Mahsulot turlari: <elektronika (o'zgarishsiz) | boshqa: ...>

docs/REBRAND.md dagi ro'yxat bo'yicha hamma joyni yangila,
testlarni ishga tushir, Mini App va panel skrinshotlarini ko'rsat va yangi repoga push qil.
Tokenni kodga yozma.
```

---

## Claude uchun: o'zgartiriladigan joylar ro'yxati

| # | Fayl | Nima o'zgaradi |
|---|---|---|
| 1 | `app/db.py` → `DEFAULT_SETTINGS` | `shop_name`, `shop_tagline`, `brand_color`, `order_prefix`, `about_uz`, `about_ru`, `instagram`, `telegram_channel`, `website` |
| 2 | `app/brand.py` | `SHOP["name"]` va zaxira (fallback) nom/rang. Ular `DEFAULT_SETTINGS` bilan bir xil bo'lsin. |
| 3 | `webapp/brand/` | Logo fayllarini qayta yaratish (pastda). Fayl nomlari o'zgarmaydi. |
| 4 | `webapp/style.css`, `webapp/admin/admin.css` | `--brand` / `--brand-rgb` — sahifa yuklanguncha ko'rinadigan rang |
| 5 | `webapp/app.js`, `webapp/admin/admin.js` | zaxira rang `#e0382b`, sarlavha izohlari, `@techzone` placeholderlari |
| 6 | `webapp/index.html` | `<title>` (yuklangach brend nomi bilan almashadi) |
| 7 | `.env.example`, `webapp/config.js` | namunaviy domen |
| 8 | `deploy/get.sh` | `REPO` va `DIR` standart qiymatlari |
| 9 | `deploy/build_static.sh`, `deploy/install.sh` | namunaviy domen va nom (`techzone`) |
| 10 | `app/admin_api.py`, `app/handlers/admin.py` | xato xabaridagi rang namunasi, rassilka misolidagi havolalar |
| 11 | `app/seed.py` | Demo katalog. Elektronika bo'lsa qoladi. Boshqa yo'nalish bo'lsa: kategoriyalar va ularning `spec_template` lari, brendlar, mahsulotlar. Rasmlar `tools/gen_demo_images.py` da. |
| 12 | `README.md`, `DEPLOY.md` | Nom, domen, repo manzili. Yaproq go'shtga oid "shared" bo'limi yangi serverga mos kelmasa qisqartiriladi. |
| 13 | `tests/` | Prefiks yoki nomga bog'liq assertlar (`TZ-` va h.k.) |

Brendga bog'liq qolgan joylarni topish:

```bash
grep -rn -i "tech\.\?zone\|techzone\|e0382b\|\"TZ\"" --include=*.{py,js,html,css,sh,yml,md,example} .
```

### Logo fayllari (`webapp/brand/`)

| Fayl | Qayerda | O'lcham |
|---|---|---|
| `logo.png` | Mini App bosh sahifa, panel, botdagi salomlashuv | ~1200 px eni, shaffof fon |
| `wordmark.png` | faqat yozuv qismi (zaxira, hozircha ishlatilmaydi) | shaffof |
| `mark.png` | kichik belgi (`shop_mark` sozlamasi) | kvadrat, ~512 px |
| `icon.png` | BotFather avatar (`/setuserpic`) | 640×640, to'liq fonli |
| `favicon.png` | brauzer yorlig'i | 64×64 |
| `logo-original.jpg` | mijoz yuborgan asl fayl | — |

Pillow bilan yaratiladi: fonni olib tashlash (oq yoki qora fon bo'lsa threshold bilan), kesish (`getbbox`), kvadratga joylash.

### O'zgarmaydigan narsalar
- Bazadagi jadval va ustun nomlari, API yo'llari, `localStorage` kalitlari (`shop_` prefiksi). Ular brenddan mustaqil.
- `{shop}` o'zgaruvchisi: barcha bot matnlarida do'kon nomi shu orqali qo'yiladi. Matnlarga nom qo'lda yozilmaydi.
- Valyuta — so'm (`app/utils.py` → `money`, `app/i18n.py`). Boshqa davlat uchun alohida vazifa.
- Hududlar — O'zbekiston viloyatlari (`app/seed.py` → `REGIONS`). Paneldan tahrirlanadi.

### Mavjud (ishlab turgan) do'konni rebrend qilish
Kod o'zgarishi shart emas: panel → *⚙️ Do'kon va brend* → yangi nom, logo, rang, prefiks → **Saqlash**.

`DEFAULT_SETTINGS` faqat bazada qiymat yo'q bo'lganda ishlatiladi, shuning uchun ishlab turgan do'konga kod orqali o'zgarish ta'sir qilmaydi.

Eski buyurtmalar eski prefiks bilan qoladi, yangilari yangi prefiks bilan beriladi.

### Tekshiruv ro'yxati
- [ ] `pytest` — hammasi yashil
- [ ] `python tools/dev_server.py 8090`: Mini App va panel yangi nom, logo va rangda (skrinshot)
- [ ] `grep` brendning eski nomini topmaydi (`docs/specs` va tarixiy hujjatlardan tashqari)
- [ ] BotFather: yangi bot, avatar `icon.png`, tavsif
- [ ] Yangi repoga push. Token faqat serverdagi `.env` da
