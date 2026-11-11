import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo
from aiohttp import web

from app import db
from app.backup import daily_backup_loop
from app.botapi import API_VERSION, ShopDispatcher, allowed_updates
from app.config import config
from app.handlers import setup_routers
from app.keyboards import webapp_ready, webapp_url
from app.rich import RichSessionMiddleware
from app.webapp import create_app

log = logging.getLogger("shop")


async def setup_bot_ui(bot: Bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="catalog", description="Katalog"),
        BotCommand(command="search", description="Qidiruv"),
        BotCommand(command="cart", description="Savat"),
        BotCommand(command="orders", description="Buyurtmalarim"),
        BotCommand(command="lang", description="Til / Язык"),
        BotCommand(command="help", description="Yordam"),
    ])
    await bot.set_my_commands([
        BotCommand(command="start", description="Перезапустить бота"),
        BotCommand(command="catalog", description="Каталог"),
        BotCommand(command="search", description="Поиск"),
        BotCommand(command="cart", description="Корзина"),
        BotCommand(command="orders", description="Мои заказы"),
        BotCommand(command="lang", description="Til / Язык"),
        BotCommand(command="help", description="Помощь"),
    ], language_code="ru")
    # Bot profili (chat ochilganda ko'rinadigan tavsif) brend sozlamalaridan — white-label uchun
    try:
        s = await db.get_settings()
        for lang, code in (("uz", None), ("ru", "ru")):
            about = (s.get(f"about_{lang}") or "").strip()
            short = (s.get("shop_tagline") or "").strip()
            if about and (await bot.get_my_description(language_code=code)).description != about[:512]:
                await bot.set_my_description(description=about[:512], language_code=code)
            if short and (await bot.get_my_short_description(language_code=code)).short_description != short[:120]:
                await bot.set_my_short_description(short_description=short[:120], language_code=code)
    except Exception as e:  # noqa: BLE001
        log.warning("Bot tavsifini o'rnatib bo'lmadi: %s", e)
    if webapp_ready():
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="🛍 Do'kon", web_app=WebAppInfo(url=webapp_url()))
        )
    else:
        log.warning("WEBAPP_URL https emas — mini app tugmasi o'rnatilmadi")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not config.bot_token:
        raise SystemExit("BOT_TOKEN topilmadi. .env faylini to'ldiring (.env.example ga qarang).")

    await db.init_db(config.db_path, seed_demo=config.demo_data)
    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # barcha oddiy matnli xabarlar Telegram rich message formatida yuboriladi (rad etilsa — oddiy matn)
    bot.session.middleware(RichSessionMiddleware())
    dp = ShopDispatcher()
    dp.include_router(setup_routers())

    runner = web.AppRunner(create_app(bot))
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", config.port).start()
    log.info("Bot API %s qatlami yoqilgan (aiogram %s)", API_VERSION, __import__("aiogram").__version__)
    log.info("Mini app server: http://0.0.0.0:%s  (WEBAPP_URL=%s)", config.port, config.webapp_url or "-")

    try:
        await setup_bot_ui(bot)
        await bot.delete_webhook(drop_pending_updates=False)
        tasks = [asyncio.create_task(daily_backup_loop(bot))]
        await dp.start_polling(bot, allowed_updates=allowed_updates(dp))
        for task in tasks:
            task.cancel()
    finally:
        await runner.cleanup()
        await db.close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
