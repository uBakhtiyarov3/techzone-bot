#!/usr/bin/env bash
# Kodni yangilash: GitHub dan oxirgi o'zgarishlarni olib, botni qayta quradi (baza va rasmlar saqlanadi).
# Rejim (.env dagi COMPOSE_FILE) avtomatik hisobga olinadi.
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
sudo docker compose up -d --build
sudo docker image prune -f >/dev/null
sudo docker compose ps
# bot ishga tushishini (baza migratsiyasi bilan) 30 soniyagacha kutamiz
for i in $(seq 1 15); do
  if sudo docker compose exec -T shop python -c \
      "import urllib.request as u; u.urlopen('http://127.0.0.1:8080/health', timeout=3)" >/dev/null 2>&1; then
    echo "✅ Bot ishlayapti"
    exit 0
  fi
  sleep 2
done
echo "⚠️  Bot 30 soniyada javob bermadi — loglar: sudo docker compose logs --tail 50 shop"
exit 1
