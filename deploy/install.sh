#!/usr/bin/env bash
# Do'kon botini (Tech.Zone yoki boshqa brend) Ubuntu serverga bir buyruq bilan o'rnatish.
#   bash deploy/install.sh
#
# Ikki rejim avtomatik tanlanadi:
#   • alohida — serverda 443-port bo'sh: bot + o'z Caddy si (HTTPS) ishga tushadi;
#   • shared  — 443-portni boshqa botning Caddy si band qilgan (masalan Yaproq go'sht):
#               bot o'sha Caddy ning docker tarmog'iga ulanadi va Caddyfile ga yangi domen bloki qo'shiladi.
#               Boshqa botning kodi, bazasi va tokeni o'zgarmaydi.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
DOCKER="sudo docker"

say()  { printf "\n\033[1;33m==> %s\033[0m\n" "$1"; }
warn() { printf "\033[1;31m%s\033[0m\n" "$1"; }

# 1) Kam xotirali serverlar (1 GB) uchun swap
if [ "$(free -m | awk '/^Mem:/{print $2}')" -lt 2000 ] && ! swapon --show | grep -q .; then
  say "2 GB swap yaratilmoqda"
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
  sudo mkswap /swapfile >/dev/null && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

# 2) Docker
if ! command -v docker >/dev/null; then
  say "Docker o'rnatilmoqda"
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER" || true
fi

# 3) Rejimni aniqlash: 443-portda boshqa konteyner (Caddy) bormi?
PROXY=""
if [ -f .env ] && grep -q '^COMPOSE_FILE=docker-compose.shared.yml' .env; then
  PROXY="$(grep '^PROXY_CONTAINER=' .env | cut -d= -f2- || true)"
fi
if [ -z "$PROXY" ]; then
  PROXY="$($DOCKER ps --filter publish=443 --format '{{.Names}}' | grep -v "^$(basename "$ROOT")-" | head -1 || true)"
fi
MODE="alohida"
if [ -n "$PROXY" ]; then
  if ! $DOCKER inspect -f '{{.Config.Image}}' "$PROXY" | grep -qi caddy; then
    warn "443-portni '$PROXY' konteyneri band qilgan, lekin u Caddy emas."
    warn "Uni to'xtating yoki domenni qo'lda yo'naltiring (DEPLOY.md → 'Qo'lda sozlash')."
    exit 1
  fi
  MODE="shared"
  EDGE_NETWORK="$($DOCKER inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}' "$PROXY" | head -1)"
  CADDYFILE="$($DOCKER inspect -f '{{range .Mounts}}{{if eq .Destination "/etc/caddy/Caddyfile"}}{{.Source}}{{end}}{{end}}' "$PROXY")"
  if [ -z "$EDGE_NETWORK" ] || [ -z "$CADDYFILE" ] || [ ! -f "$CADDYFILE" ]; then
    warn "Caddy ($PROXY) tarmog'i yoki Caddyfile topilmadi. DEPLOY.md → 'Qo'lda sozlash' bo'limiga qarang."
    exit 1
  fi
  say "Shared rejim: mavjud Caddy ($PROXY, tarmoq: $EDGE_NETWORK) ortida ishlaydi"
else
  say "Alohida rejim: o'z Caddy si bilan (80/443)"
fi

# 4) Firewall (faqat alohida rejimda — shared rejimda portlar allaqachon ochiq)
if [ "$MODE" = "alohida" ]; then
  if command -v ufw >/dev/null && sudo ufw status | grep -q "Status: active"; then
    sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
  fi
  if sudo iptables -L INPUT -n 2>/dev/null | grep -q "REJECT"; then
    for p in 80 443; do
      sudo iptables -C INPUT -p tcp --dport $p -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 5 -p tcp --dport $p -j ACCEPT
    done
    if command -v netfilter-persistent >/dev/null; then sudo netfilter-persistent save; fi
  fi
fi

# 5) .env (token faqat shu faylda saqlanadi)
PUBLIC_IP="$(curl -fsS https://api.ipify.org || true)"
if [ ! -f .env ]; then
  say ".env sozlamalari"
  read -rsp "BOT_TOKEN (@BotFather, yozilganda ko'rinmaydi): " BOT_TOKEN; echo
  read -rp "ADMIN_IDS (bosh menejer Telegram ID, vergul bilan): " ADMIN_IDS
  echo "Domen: masalan techzone.duckdns.org (A-yozuv shu server IP siga: ${PUBLIC_IP:-?})."
  echo "Bo'sh qoldirsangiz vaqtinchalik ${PUBLIC_IP//./-}.sslip.io ishlatiladi."
  read -rp "DOMAIN: " DOMAIN
  DOMAIN="${DOMAIN:-${PUBLIC_IP//./-}.sslip.io}"
  read -rp "DUCKDNS_TOKEN (DuckDNS ishlatmasangiz bo'sh qoldiring): " DUCKDNS_TOKEN
  read -rp "Demo katalog qo'shilsinmi? (keyin paneldan bitta tugma bilan o'chiriladi) [Y/n]: " DEMO
  [[ "${DEMO:-y}" =~ ^[Nn] ]] && DEMO_DATA=0 || DEMO_DATA=1
  APP_SLUG="$(printf '%s' "${DOMAIN%%.*}" | tr 'A-Z' 'a-z' | tr -cd 'a-z0-9-')"
  {
    echo "BOT_TOKEN=$BOT_TOKEN"
    echo "ADMIN_IDS=$ADMIN_IDS"
    echo "DOMAIN=$DOMAIN"
    echo "WEBAPP_URL=https://$DOMAIN"
    echo "PORT=8080"
    echo "DB_PATH=data/bot.db"
    echo "DEMO_DATA=$DEMO_DATA"
    echo "DEBUG=0"
    echo "DUCKDNS_TOKEN=$DUCKDNS_TOKEN"
    echo "APP_SLUG=${APP_SLUG:-shop}"
    if [ "$MODE" = "shared" ]; then
      echo "COMPOSE_FILE=docker-compose.shared.yml"
      echo "EDGE_NETWORK=$EDGE_NETWORK"
      echo "PROXY_CONTAINER=$PROXY"
    fi
  } > .env
  chmod 600 .env
fi
set -a; . ./.env; set +a
APP_SLUG="${APP_SLUG:-techzone}"

# 6) DuckDNS: IP o'zgarsa domen avtomatik yangilanadi (har 5 daqiqada).
#    Faqat SHU subdomen qatori almashtiriladi — boshqa botlarning DuckDNS yozuvlari qoladi.
if [ -n "${DUCKDNS_TOKEN:-}" ] && [[ "$DOMAIN" == *.duckdns.org ]]; then
  say "DuckDNS yangilagich o'rnatilmoqda"
  SUB="${DOMAIN%.duckdns.org}"
  URL="https://www.duckdns.org/update?domains=${SUB}&token=${DUCKDNS_TOKEN}&ip="
  curl -fsS "$URL" && echo
  ( crontab -l 2>/dev/null | grep -vF "domains=${SUB}&" || true; echo "*/5 * * * * curl -fsS '$URL' >/dev/null 2>&1" ) | crontab -
fi

# 7) Ishga tushirish
say "Bot ishga tushirilmoqda"
mkdir -p data
$DOCKER compose up -d --build
sleep 5
$DOCKER compose ps

# 8) Shared rejim: mavjud Caddy ga domen bloki
if [ "$MODE" = "shared" ]; then
  CADDYFILE="$($DOCKER inspect -f '{{range .Mounts}}{{if eq .Destination "/etc/caddy/Caddyfile"}}{{.Source}}{{end}}{{end}}' "$PROXY")"
  if grep -qF "$DOMAIN {" "$CADDYFILE"; then
    echo "Caddyfile da $DOMAIN bloki allaqachon bor."
  else
    say "Caddy ga $DOMAIN qo'shilmoqda ($CADDYFILE)"
    cp "$CADDYFILE" data/Caddyfile.backup
    # tee -a — faylning o'zi (inode) saqlanadi, konteyner o'zgarishni darhol ko'radi
    printf '\n# %s — %s/deploy/install.sh qo'"'"'shdi\n%s {\n\tencode gzip\n\treverse_proxy %s-bot:8080\n}\n' \
      "$APP_SLUG" "$ROOT" "$DOMAIN" "$APP_SLUG" | sudo tee -a "$CADDYFILE" >/dev/null
    if ! $DOCKER exec "$PROXY" caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null 2>&1; then
      warn "Yangi Caddyfile xato — eski holatiga qaytarildi. DEPLOY.md → 'Qo'lda sozlash'."
      sudo sh -c "cat '$ROOT/data/Caddyfile.backup' > '$CADDYFILE'"
      exit 1
    fi
    # Caddyfile boshqa bot reposida bo'lsa, uning `git pull` i bu qatorlarga xalaqit bermasin
    REPO_DIR="$(git -C "$(dirname "$CADDYFILE")" rev-parse --show-toplevel 2>/dev/null || true)"
    if [ -n "$REPO_DIR" ]; then
      git -C "$REPO_DIR" update-index --skip-worktree "$(realpath --relative-to="$REPO_DIR" "$CADDYFILE")" 2>/dev/null || true
    fi
  fi
  $DOCKER exec "$PROXY" caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
fi

cat <<DONE

✅ Tayyor! ($MODE rejim)
   Mini App:    https://$DOMAIN        (SSL sertifikat 1–2 daqiqada olinadi)
   Do'kon paneli: https://$DOMAIN/admin  (kirish — botdagi 🖥 Do'kon paneli tugmasi orqali)
   Tekshirish:  https://$DOMAIN/health
   Loglar:      sudo docker compose logs -f shop
   Yangilash:   bash deploy/update.sh

Botga /start bosing.
DONE
