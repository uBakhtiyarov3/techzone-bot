"""Serverda bot dizaynini tekshirish: har bir qadamni haqiqiy Telegram bilan sinaydi va natijani yozadi.

    sudo docker compose exec shop python tools/doctor.py [telegram_id]

Bosh menejerga (ADMIN_IDS dagi birinchi ID) 4 ta sinov xabari yuboriladi. Bot ishlayotgan paytda ham
ishlatish mumkin — faqat xabar yuboradi, hech narsani o'zgartirmaydi.
"""
import asyncio
import sys
import traceback
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OK, BAD = "✅", "❌"


def line(mark: str, text: str) -> None:
    print(f"{mark} {text}", flush=True)


async def main() -> None:
    import aiogram
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputRichMessage

    from app import bot_ui, cards, db, rich
    from app.config import config

    print(f"aiogram {aiogram.__version__} · Bot API {aiogram.__api_version__}")
    print(f"WEBAPP_URL = {config.webapp_url or '(bo`sh)'}")
    if not config.admin_ids:
        line(BAD, "ADMIN_IDS bo'sh — sinov xabarini kimga yuborishni bilmayman")
        return
    # kimga yuborish: buyruqdagi ID (python tools/doctor.py 123456789) yoki ADMIN_IDS dagi birinchisi
    admin = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else sorted(config.admin_ids)[0]
    await db.init_db(config.db_path, seed_demo=False)

    # 1. shriftlar va karta chizish
    fonts = list((ROOT / "app" / "assets" / "fonts").glob("*.otf"))
    line(OK if fonts else BAD, f"shriftlar: {len(fonts)} ta")
    card_path = ""
    try:
        card_path = cards.render_sync("cover", {"brand": await bot_ui.brand_info(), "caption": "Tekshiruv",
                                                "title": "Doctor", "subtitle": "karta chizildi", "images": []})
        line(OK, f"karta chizildi: {card_path}")
    except Exception:  # noqa: BLE001
        line(BAD, "karta chizilmadi:\n" + traceback.format_exc())

    # 2. rasm internetdan ochiladimi (Telegram rasmni shu manzildan oladi)
    if card_path and config.webapp_url.startswith("https://"):
        url = f"{config.webapp_url.rstrip('/')}/{card_path}"
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                line(OK if r.status == 200 else BAD, f"rasm manzili ochildi ({r.status}): {url}")
        except Exception as e:  # noqa: BLE001
            line(BAD, f"rasm manzili ochilmadi: {url} — {e}")

    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    try:
        me = await bot.get_me()
        line(OK, f"bot: @{me.username}")
        try:
            chat = await bot.get_chat(admin)
            who = " ".join(x for x in (chat.first_name, chat.last_name) if x) + (f" (@{chat.username})" if chat.username else "")
            line(OK, f"sinov xabarlari kimga: ID {admin} — {who}")
        except Exception as e:  # noqa: BLE001
            line(BAD, f"ID {admin} ga yozib bo'lmaydi: {e}")

        # 3. rich xabar (oddiy) — middleware siz, to'g'ridan-to'g'ri
        try:
            await bot.send_rich_message(admin, InputRichMessage(html="<h3>Doctor 1/4</h3><p>Rich xabar ishlaydi.</p>"))
            line(OK, "1/4 rich xabar yuborildi")
        except Exception as e:  # noqa: BLE001
            line(BAD, f"1/4 rich xabar rad etildi: {e}")

        # 4. rasm-karta bilan rich xabar
        if card_path:
            try:
                await bot.send_rich_message(admin, rich.Rich().img(card_path).p("Doctor 2/4: karta rasmi").build())
                line(OK, "2/4 karta rasmi bilan xabar yuborildi")
            except Exception as e:  # noqa: BLE001
                line(BAD, f"2/4 karta rasmi rad etildi: {e}")

        # 5. rangli tugmalar
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Yashil", callback_data="sh:noop", style="success"),
            InlineKeyboardButton(text="Ko'k", callback_data="sh:noop", style="primary"),
            InlineKeyboardButton(text="Qizil", callback_data="sh:noop", style="danger")]])
        try:
            await bot.send_message(admin, "Doctor 3/4: rangli tugmalar", reply_markup=kb)
            line(OK, "3/4 rangli tugmalar yuborildi")
        except Exception as e:  # noqa: BLE001
            line(BAD, f"3/4 rangli tugmalar rad etildi: {e}")

        # 6. effekt
        try:
            await bot.send_rich_message(admin, InputRichMessage(html="<p>Doctor 4/4: 🎉 effekt</p>"),
                                        message_effect_id=bot_ui.FX_PARTY)
            line(OK, "4/4 effekt bilan xabar yuborildi")
        except Exception as e:  # noqa: BLE001
            line(BAD, f"4/4 effekt rad etildi: {e}")
    finally:
        await bot.session.close()
        await db.close_db()
    print("\nTelegram'da 4 ta xabarni ko'ring. Yuqoridagi natijani menga yuboring.")


if __name__ == "__main__":
    asyncio.run(main())
