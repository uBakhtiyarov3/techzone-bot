from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Router
from aiogram.types import CallbackQuery, Message, TelegramObject

from . import admin, common, shop, staff


class BanMiddleware(BaseMiddleware):
    """Admin bloklagan foydalanuvchining xabar va tugmalari qayta ishlanmaydi."""

    async def __call__(self, handler: Callable[[TelegramObject, dict], Awaitable[Any]], event: TelegramObject,
                       data: dict) -> Any:
        from .. import db
        from ..config import config
        from ..i18n import t
        from ..roles import lang_of

        user = getattr(event, "from_user", None)
        if not user or user.id in config.admin_ids:
            return await handler(event, data)
        reason = await db.is_banned(user.id)
        if reason is None:
            return await handler(event, data)
        text = t("banned", await lang_of(user.id), reason=f"\n\n{reason}" if reason else "")
        if isinstance(event, CallbackQuery):
            await event.answer(text[:190], show_alert=True)
        elif isinstance(event, Message) and event.chat.type == "private":
            await event.answer(text)
        return None


def setup_routers() -> Router:
    root = Router()
    root.message.outer_middleware(BanMiddleware())
    root.callback_query.outer_middleware(BanMiddleware())
    # tartib muhim: buyurtma va menejer FSM holatlari umumiy tugmalardan oldin tekshiriladi
    root.include_routers(shop.router, admin.router, staff.router, common.router, common.fallback_router)
    return root
