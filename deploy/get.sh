#!/usr/bin/env bash
# Bir qatorli o'rnatish (Ubuntu server):
#   curl -fsSL https://raw.githubusercontent.com/uBakhtiyarov3/techzone-bot/HEAD/deploy/get.sh | bash
# Boshqa repo/branch/papka: SHOP_REPO=... SHOP_BRANCH=... SHOP_DIR=... bilan.
set -euo pipefail
REPO="${SHOP_REPO:-https://github.com/uBakhtiyarov3/techzone-bot.git}"
BRANCH="${SHOP_BRANCH:-}"
DIR="${SHOP_DIR:-$HOME/techzone-bot}"

if ! command -v git >/dev/null; then
  sudo apt-get update -y && sudo apt-get install -y git curl
fi
if [ -d "$DIR/.git" ]; then
  [ -n "$BRANCH" ] && git -C "$DIR" fetch origin "$BRANCH" && git -C "$DIR" checkout "$BRANCH"
  git -C "$DIR" pull --ff-only
else
  git clone ${BRANCH:+-b "$BRANCH"} "$REPO" "$DIR"
fi
# savollarga klaviaturadan javob berish uchun stdin ni terminalga ulaymiz
bash "$DIR/deploy/install.sh" </dev/tty
