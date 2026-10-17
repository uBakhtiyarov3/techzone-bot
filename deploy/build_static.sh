#!/usr/bin/env bash
# (Ixtiyoriy) Mini App + do'kon paneli fayllarini oddiy shared hostingga (cPanel) tayyorlaydi.
# Odatda kerak emas — bot serveri ularni o'zi https://DOMEN/ va /admin da beradi.
#
#   bash deploy/build_static.sh https://techzone.duckdns.org [nom]
#
# 1-argument — bot ishlayotgan server manzili (API shu yerda). Natija: dist/<nom>-web.zip
# ZIP ichidagi fayllarni hostingdagi papkaga yuklang va serverdagi .env ga
# CORS_ORIGINS=https://hosting-domeni qo'shing.
set -euo pipefail
cd "$(dirname "$0")/.."

API="${1:-}"
if [[ ! "$API" =~ ^https:// ]]; then
  echo "Foydalanish: bash deploy/build_static.sh https://SERVER-DOMEN" >&2
  echo "(bot va API ishlayotgan server manzili, https bilan)" >&2
  exit 1
fi
API="${API%/}"
NAME="${2:-techzone}"
V="$(date +%s)"
OUT="dist/$NAME"
rm -rf dist && mkdir -p "$OUT/admin"

sed "s/{{v}}/$V/g" webapp/index.html > "$OUT/index.html"
cp webapp/app.js webapp/style.css "$OUT/"
sed "s/{{v}}/$V/g" webapp/admin/index.html > "$OUT/admin/index.html"
cp webapp/admin/admin.js webapp/admin/admin.css "$OUT/admin/"
cp -r webapp/brand "$OUT/brand"
printf 'window.SHOP_CONFIG = { api: "%s" };\n' "$API" > "$OUT/config.js"

cat > "$OUT/.htaccess" <<'HT'
Options -Indexes
DirectoryIndex index.html
<IfModule mod_headers.c>
  <FilesMatch "\.(html|js|css)$">
    Header set Cache-Control "no-cache"
  </FilesMatch>
  Header always set X-Content-Type-Options "nosniff"
  Header always set Referrer-Policy "no-referrer"
</IfModule>
HT
cat > "$OUT/admin/.htaccess" <<'HT'
<IfModule mod_headers.c>
  Header always set X-Robots-Tag "noindex, nofollow"
</IfModule>
HT

python3 - <<PY
import pathlib, zipfile
root = pathlib.Path("$OUT")
with zipfile.ZipFile("dist/$NAME-web.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(root.rglob("*")):
        if f.is_file():
            z.write(f, f.relative_to(root))
PY
echo "✅ Tayyor: dist/$NAME-web.zip  (API: $API)"
echo "   Hostingdagi papkaga yuklab, Extract qiling. Serverda CORS_ORIGINS ni unutmang."
