#!/usr/bin/env bash
# Kodni yangilash: GitHub dan oxirgi o'zgarishlarni olib, botni qayta quradi (baza va rasmlar saqlanadi).
# Rejim (.env dagi COMPOSE_FILE) avtomatik hisobga olinadi.
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
sudo docker compose up -d --build
sudo docker image prune -f >/dev/null
sleep 3
sudo docker compose ps
sudo docker compose exec -T shop python -c \
  "import urllib.request as u; print('health:', u.urlopen('http://127.0.0.1:8080/health', timeout=5).status)" \
  || echo "⚠️  Bot hali javob bermadi — loglar: sudo docker compose logs --tail 50 shop"
