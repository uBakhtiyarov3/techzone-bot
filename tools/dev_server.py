"""Mini App va do'kon panelini Telegram'siz brauzerda ko'rish uchun lokal server (faqat ishlab chiqish uchun).

    python tools/dev_server.py [port]

Ochish: http://localhost:8090/?dev_user=1  (Mini App, 1 — ADMIN_IDS dagi menejer)
        http://localhost:8090/admin/?dev_user=1  (do'kon paneli)
Baza: data/dev.db (demo katalog bilan). Bot ulanmaydi — bildirishnomalar yuborilmaydi.
"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["DEBUG"] = "1"
os.environ.setdefault("BOT_TOKEN", "1:dev")
os.environ.setdefault("ADMIN_IDS", "1")

from aiohttp import web  # noqa: E402

from app import db  # noqa: E402
from app.config import config  # noqa: E402
from app.webapp import create_app  # noqa: E402


async def main(port: int) -> None:
    config.debug = True
    await db.init_db(os.getenv("DEV_DB", str(ROOT / "data" / "dev.db")))
    runner = web.AppRunner(create_app(None))
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", port).start()
    print(f"Mini App:  http://localhost:{port}/?dev_user=1")
    print(f"Panel:     http://localhost:{port}/admin/?dev_user=1")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 8090))
