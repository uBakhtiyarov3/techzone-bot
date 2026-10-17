import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOT_TOKEN", "123456:TEST-token")
os.environ.setdefault("ADMIN_IDS", "1")

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _no_network_maps(monkeypatch):
    """Testlarda Google Maps havolasini internet orqali ochmaslik."""
    from app import geo

    async def fake_resolve(url):
        return geo.parse_coords(url)

    monkeypatch.setattr(geo, "resolve_map_url", fake_resolve)
    monkeypatch.setattr(geo, "_last_fail", 0.0)


def make_init_data(user_id: int, token: str | None = None, auth_date: int | None = None) -> str:
    from app.config import config

    token = token or config.bot_token
    fields = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "AAE",
        "user": json.dumps({"id": user_id, "first_name": "Ali", "username": "ali"}),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def H(uid: int = 100) -> dict:
    """Mini App so'rovi sarlavhasi (haqiqiy imzolangan Telegram initData)."""
    return {"X-Telegram-Init-Data": make_init_data(uid)}


@pytest.fixture
async def client(aiohttp_client, tmp_path):
    from app import db
    from app.config import config
    from app.webapp import create_app

    old_dir = config.uploads_dir
    config.uploads_dir = tmp_path / "uploads"
    await db.init_db(str(tmp_path / "test.db"))
    await db.set_setting("mode", "open")  # testlar soatga bog'liq bo'lmasin
    c = await aiohttp_client(create_app(None))
    yield c
    config.uploads_dir = old_dir
    await db.close_db()


async def admin_headers(client, uid: int = 1) -> dict:
    from app import db
    from app.admin_api import make_login_link

    await db.upsert_user(uid, "Boss", None, None)
    code = (await make_login_link(uid)).split("#code=")[1]
    r = await client.post("/api/admin/login", json={"code": code})
    assert r.status == 200, await r.text()
    return {"X-Admin-Token": (await r.json())["token"]}


async def variant_of(product_name: str, *vals: str) -> dict:
    """Demo katalogdan variant: variant_of("iPhone 15", "Qora", "128 GB")."""
    from app import db, products

    pid = await db.scalar("SELECT id FROM products WHERE name = ?", product_name)
    p = await products.get_product(pid)
    return next(v for v in p["variants"] if v["vals"] == list(vals))
