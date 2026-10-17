# 🚀 Tech.Zone botini serverga o'rnatish va hostingga chiqarish

Bot **24/7 ishlab turishi** kerak: Telegramdan xabarlarni kutadi, xodimlarga buyurtma yuboradi, har kuni zaxira nusxa oladi.
Shuning uchun unga doim yoqilgan server kerak ("uxlab qoladigan" bepul xostinglar mos emas).

Ikki yo'l bor — o'rnatish skripti qaysi birida ekanini **o'zi aniqlaydi**:

| Holat | Rejim | Nima bo'ladi |
|---|---|---|
| **Yaproq go'sht ishlayotgan Google Cloud VM** (tavsiya, qo'shimcha xarajat yo'q) | `shared` | Tech.Zone alohida konteynerda, alohida token/baza/`.env` bilan ishlaydi. Mavjud Caddy ga faqat yangi domen bloki qo'shiladi. Yaproq go'sht kodi, bazasi, tokeni o'zgarmaydi. |
| Yangi, bo'sh server | `alohida` | Bot + o'z Caddy si (80/443, avtomatik SSL). |

> **Resurs:** e2-micro (1 GB RAM) ikki bot uchun yetarli — har bir bot ~100–150 MB ishlatadi, skript 2 GB swap ham qo'shadi.
> Har bir konteynerga 400 MB limit qo'yilgan, shuning uchun biri ikkinchisini "bo'g'ib" qo'ymaydi.

---

## 1-qadam. Tayyorgarlik (5 daqiqa)

1. **Bot token:** @BotFather → `/newbot` → nom: `Tech.Zone`, username: masalan `techzone_uz_bot`. Tokenni hech kimga yubormang — u faqat serverdagi `.env` faylga yoziladi.
2. **Bot ko'rinishi (BotFather'da):**
   - `/setuserpic` → `webapp/brand/icon.png` (logo)
   - `/setdescription` → "Smartfonlar, noutbuklar va aksessuarlar — rasmiy kafolat bilan. Buyurtma 24/7."
   - `/setabouttext` → "Tech.Zone — smart choices, better tomorrow."
   - Menyu tugmasi va buyruqlar ro'yxatini bot **o'zi** o'rnatadi.
3. **Telegram ID ingiz** (bosh menejer): `2076925033`. Boshqa menejer va xodimlar keyin paneldan qo'shiladi.

## 2-qadam. Domen (Mini App uchun HTTPS majburiy)

Telegram Mini App faqat `https://` manzilda ochiladi. SSL ni Caddy o'zi oladi — sizdan faqat domen kerak.

**a) Bepul DuckDNS (eng oson):** https://www.duckdns.org → Google bilan kiring → subdomen yarating: `techzone` →
**current ip** ga VM ning tashqi IP sini yozing (Yaproq go'sht bilan **bir xil IP**) → sahifadagi **token** ni saqlang.
Natija: `techzone.duckdns.org`.

**b) O'z domeningiz bo'lsa** (masalan `techzone.uz`): DNS → **A** yozuv: `@` yoki `shop` → VM IP si.

> Ikkala bot bitta IP da, lekin **har biri o'z domenida** ishlaydi — Caddy so'rovni domen nomiga qarab to'g'ri botga yo'naltiradi.

## 3-qadam. O'rnatish (bitta buyruq)

Google Cloud konsol → *Compute Engine → VM instances* → Yaproq go'sht VM → **SSH** tugmasi. Ochilgan oynada:

```bash
curl -fsSL https://raw.githubusercontent.com/uBakhtiyarov3/techzone-bot/HEAD/deploy/get.sh | bash
```

> Repo **private** bo'lsa `git clone` GitHub login va **Personal Access Token** so'raydi
> (GitHub → Settings → Developer settings → Fine-grained tokens → faqat `techzone-bot` repo, *Contents: Read*).

Skript so'raydi:

| Savol | Javob |
|---|---|
| `BOT_TOKEN` | BotFather bergan token (yozilganda ko'rinmaydi) |
| `ADMIN_IDS` | `2076925033` |
| `DOMAIN` | `techzone.duckdns.org` |
| `DUCKDNS_TOKEN` | DuckDNS sahifasidagi token |
| Demo katalog | `Y` — sinab ko'rish uchun 16 ta namunaviy mahsulot (keyin paneldan bitta tugma bilan o'chadi) |

Keyin o'zi:
1. Serverda Yaproq go'sht Caddy si 443-portda ishlayotganini ko'radi → **shared rejim**;
2. Tech.Zone ni `~/techzone-bot` papkasida alohida konteynerda ishga tushiradi;
3. Yaproq go'sht `Caddyfile` iga `techzone.duckdns.org` blokini qo'shadi (oldin nusxasini `~/techzone-bot/data/Caddyfile.backup` ga oladi, xato bo'lsa qaytaradi) va Caddy ni **to'xtatmasdan** qayta yuklaydi;
4. DuckDNS uchun faqat `techzone` subdomeni cron qatorini qo'shadi (Yaproq go'shtning DuckDNS qatoriga tegmaydi).

## 4-qadam. Tekshirish

1. Brauzerda `https://techzone.duckdns.org/health` → `{"ok": true, ...}`. (SSL 1–2 daqiqada olinadi.)
2. Yaproq go'sht ham ishlayotganini tekshiring: uning domeni `/health`.
3. Botga `/start` → logo bilan salomlashuv xabari, pastda **🛍 Do'kon** tugmasi (Mini App).
4. **👑 Menejer paneli → 🖥 Do'kon paneli** → kelgan havola orqali brauzerda to'liq panel ochiladi (havola 15 daqiqa amal qiladi).
5. Panelda birinchi navbatda:
   - **⚙️ Do'kon va brend** — telefon, manzil, Google Maps havolasi, Instagram/kanal, qaytarish muddati (kun);
   - **🗺 Yetkazish hududlari** — har viloyat narxi, muddati, "bepul yetkazish ... dan";
   - **👥 Xodimlar** — buyurtmalarni qabul qiladigan xodimlar;
   - **📱 Mahsulotlar** — o'z mahsulotlaringizni qo'shing, keyin *Demo mahsulotlarni o'chirish*.
6. Test buyurtma bering (Mini App va bot ichidagi katalog orqali) → xodimga keladi → holatlarni o'tkazing (Qabul qilindi → Yig'ilmoqda → Yo'lda → Yetkazildi), har bosqichda ixtiyoriy rasm yuboring.

## Kundalik ishlatish

Barcha buyruqlar serverda, `~/techzone-bot` papkasida (`cd ~/techzone-bot`):

| Vazifa | Buyruq |
|---|---|
| Loglar | `sudo docker compose logs -f shop` |
| Qayta ishga tushirish | `sudo docker compose restart shop` |
| Kodni yangilash | `bash deploy/update.sh` |
| To'xtatish | `sudo docker compose stop` |
| Holat | `sudo docker compose ps` |

- Server qayta yuklansa bot **o'zi** ishga tushadi (`restart: unless-stopped`).
- Konteyner xizmati nomi — `shop` (Yaproq go'shtniki `bot`; bir xil nom bo'lsa Caddy ularni adashtirib yuborardi).
- Rejim `.env` dagi `COMPOSE_FILE` da saqlanadi — `docker compose` buyruqlari ikkala rejimda bir xil.
- `.env` ni o'zgartirgandan keyin: `sudo docker compose up -d` (masalan yangi token, `ADMIN_IDS`).

### Zaxira nusxa va tiklash

- Har kuni soat **04:00** da bosh menejerga `techzone_backup_....zip` keladi (baza + yuklangan rasmlar).
  Qo'lda: *Menejer paneli → 💾 Zaxira nusxa* yoki panel → *Hisobot va zaxira*.
- **Tiklash:** `sudo docker compose stop` → zip ichidagi `data/` ni `~/techzone-bot/data/` ga ko'chiring → `sudo docker compose up -d`.

### Token o'g'irlangan / almashtirish kerak bo'lsa

@BotFather → `/mybots` → bot → *API Token* → **Revoke** → yangi tokenni `~/techzone-bot/.env` dagi `BOT_TOKEN=` ga yozing → `sudo docker compose up -d`.

---

## Yaproq go'sht bilan birga ishlash — nimalarni bilish kerak

- **Ikkala bot mustaqil:** alohida papka, `.env`, baza (`data/`), token, konteyner. Birini yangilash/to'xtatish ikkinchisiga ta'sir qilmaydi.
- **Yagona umumiy narsa — Yaproq go'sht Caddy si** (80/443 portlar). U to'xtasa Tech.Zone Mini App ham ochilmaydi (bot xabarlari esa ishlayveradi).
- Yaproq go'sht `deploy/update.sh` ni odatdagidek ishlatavering. Caddyfile ga qo'shilgan blok `git pull` ga xalaqit bermasligi uchun `skip-worktree` qilib belgilangan.
  Agar Yaproq go'shtning yangi versiyasida `deploy/Caddyfile` o'zgargan bo'lsa, `git pull` "local changes would be overwritten" deydi — u holda:
  ```bash
  cd ~/yaproqgosht
  git update-index --no-skip-worktree deploy/Caddyfile && git checkout deploy/Caddyfile && git pull
  cd ~/techzone-bot && bash deploy/install.sh   # blokni qayta qo'shadi
  ```
- Yaproq go'sht `docker compose down` qilinsa, uning tarmog'i ham o'chadi. Keyin `up` qilingach Tech.Zone ni qayta ulang:
  `cd ~/techzone-bot && sudo docker compose up -d --force-recreate`.

### Qo'lda sozlash (skript Caddy ni topa olmasa)

1. `~/techzone-bot/.env` ga qo'shing:
   ```
   COMPOSE_FILE=docker-compose.shared.yml
   EDGE_NETWORK=yaproqgosht_default
   PROXY_CONTAINER=yaproqgosht-caddy-1
   APP_SLUG=techzone
   ```
   (Nomlarni `sudo docker ps` va `sudo docker network ls` dan tekshiring.)
2. `sudo docker compose up -d --build`
3. Yaproq go'sht `deploy/Caddyfile` oxiriga:
   ```
   techzone.duckdns.org {
   	encode gzip
   	reverse_proxy techzone-bot:8080
   }
   ```
4. `sudo docker exec yaproqgosht-caddy-1 caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile`

### Keyinroq alohida serverga ko'chirish

Yangi serverda `get.sh` ni ishga tushiring (u `alohida` rejimni tanlaydi) → eski serverdan `~/techzone-bot/data/` ni ko'chiring →
domen A-yozuvini yangi IP ga o'zgartiring → eski serverda `cd ~/techzone-bot && sudo docker compose down` va Yaproq go'sht Caddyfile idan Tech.Zone blokini o'chirib, Caddy ni reload qiling.

---

## (Ixtiyoriy) Mini App ni shared hostingda (cPanel) joylash

Odatda kerak emas — server Mini App ni `https://DOMEN/`, panelni `https://DOMEN/admin` da o'zi beradi.
Agar Mini App boshqa domenda (masalan `techzone.uz/shop/`) ochilishi kerak bo'lsa:

```bash
cd ~/techzone-bot && bash deploy/build_static.sh https://techzone.duckdns.org techzone
```
`dist/techzone-web.zip` ni hosting papkasiga yuklab Extract qiling, serverdagi `.env` ga
`CORS_ORIGINS=https://techzone.uz` qo'shing va `sudo docker compose up -d`. BotFather'da Mini App manzilini va `.env` dagi `WEBAPP_URL` ni yangi manzilga o'zgartiring.

## Muammolar

| Belgi | Sabab va yechim |
|---|---|
| `/health` ochilmaydi, SSL xatosi | Domen A-yozuvi VM IP siga qaramayapti yoki 1–2 daqiqa kuting. `sudo docker logs yaproqgosht-caddy-1 --tail 50` (shared) / `sudo docker compose logs caddy` (alohida). |
| Bot javob bermayapti | `sudo docker compose logs --tail 100 shop`. "Unauthorized" — token xato. "Conflict: terminated by other getUpdates" — shu token bilan boshqa joyda ham bot ishlayapti. |
| Mini App bo'sh oq ekran | `.env` da `WEBAPP_URL=https://...` to'g'rimi? O'zgartirgach `sudo docker compose up -d`. |
| Panelga kira olmayapman | Havola 15 daqiqa amal qiladi — botdan yangisini oling. ID ingiz `ADMIN_IDS` da bo'lishi kerak. |
| Xotira yetmayapti | `free -m` — swap bormi? `sudo docker stats` bilan ikkala botni kuzating. |
