"""Bot API 10.4 (9-noyabr 2026) qo'llab-quvvatlash qatlami.

aiogram ning eng yangi versiyasi (3.31) Bot API 10.3 gacha. 10.4 dagi yangi metod va turlar shu yerda
e'lon qilingan; aiogram yangilanganda bu fayldagi narsalar uning o'z klasslariga almashtiriladi.

Qo'shilganlar:
- metodlar: sendWidget, sendSharedWidget, editMessageWidgetData, editSharedWidgetData, answerWidgetQuery;
- turlar: Widget, WidgetQuery, SharedWidgetQuery, WidgetQueryType;
- `ShopDispatcher` — aiogram tanimaydigan `widget_query` / `shared_widget_query` yangilanishlarini qabul
  qilib, ro'yxatdan o'tgan ishlovchiga beradi (aks holda aiogram ularni xato deb tashlab yuborardi).
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Literal

from aiogram import Bot, Dispatcher
from aiogram.methods import TelegramMethod
from aiogram.types import (
    Chat, InlineKeyboardMarkup, Message, MessageEntity, ReplyParameters, TelegramObject, Update, User,
)

log = logging.getLogger(__name__)

API_VERSION = "10.4"
WIDGET_HTML_MAX = 32768        # bayt (UTF-8)
WIDGET_ZLIB_MAX = 4096         # zlib -9 bilan siqilgandan keyin
WIDGET_DATA_MAX = 1024         # public_data / chat_data / javob
WIDGET_QUERY_TIMEOUT = 15      # soniya — answerWidgetQuery shu vaqt ichida


# ---------------- turlar ----------------

class Widget(TelegramObject):
    html: str
    id: str | None = None
    width: int | None = None
    height: int | None = None
    public_data: str | None = None
    chat_data: str | None = None


class WidgetQueryWallet(TelegramObject):
    address: str
    amount: str
    public_key: str | None = None
    state_init: str | None = None


class WidgetQueryType(TelegramObject):
    type: Literal["data", "sign_data", "sent_transaction"]
    wallet: WidgetQueryWallet | None = None
    sign_data: str | None = None
    msg_hash: str | None = None


class WidgetQuery(TelegramObject):
    id: str
    from_user: User
    chat_instance: str
    type: WidgetQueryType
    data: str
    chat: Chat | None = None
    message_id: int | None = None
    inline_message_id: str | None = None
    chat_type: str | None = None
    widget_id: str | None = None

    def __init__(self, **data: Any):
        if "from" in data:
            data["from_user"] = data.pop("from")
        super().__init__(**data)


class SharedWidgetQuery(TelegramObject):
    id: str
    from_user: User
    type: WidgetQueryType
    data: str
    widget_id: str

    def __init__(self, **data: Any):
        if "from" in data:
            data["from_user"] = data.pop("from")
        super().__init__(**data)


def message_widget(message: Message) -> Widget | None:
    """Xabardagi widget (aiogram uni hali bilmaydi — qo'shimcha maydondan o'qiladi)."""
    raw = (message.model_extra or {}).get("widget")
    return Widget.model_validate(raw) if isinstance(raw, dict) else None


# ---------------- metodlar ----------------

class SendWidget(TelegramMethod[Message]):
    __returning__ = Message
    __api_method__ = "sendWidget"

    chat_id: int | str
    html: str
    width: int | None = None
    height: int | None = None
    public_data: str | None = None
    chat_data: str | None = None
    caption: str | None = None
    parse_mode: str | None = None
    caption_entities: list[MessageEntity] | None = None
    show_caption_above_media: bool | None = None
    allow_queries: bool | None = None
    is_shared: bool | None = None
    message_thread_id: int | None = None
    disable_notification: bool | None = None
    protect_content: bool | None = None
    allow_paid_broadcast: bool | None = None
    message_effect_id: str | None = None
    reply_parameters: ReplyParameters | None = None
    reply_markup: InlineKeyboardMarkup | None = None


class SendSharedWidget(TelegramMethod[Message]):
    __returning__ = Message
    __api_method__ = "sendSharedWidget"

    chat_id: int | str
    widget_id: str
    chat_data: str | None = None
    caption: str | None = None
    parse_mode: str | None = None
    caption_entities: list[MessageEntity] | None = None
    show_caption_above_media: bool | None = None
    message_thread_id: int | None = None
    disable_notification: bool | None = None
    protect_content: bool | None = None
    allow_paid_broadcast: bool | None = None
    message_effect_id: str | None = None
    reply_parameters: ReplyParameters | None = None
    reply_markup: InlineKeyboardMarkup | None = None


class EditMessageWidgetData(TelegramMethod[bool]):
    __returning__ = bool
    __api_method__ = "editMessageWidgetData"

    chat_id: int | str | None = None
    message_id: int | None = None
    inline_message_id: str | None = None
    public_data: str | None = None
    chat_data: str | None = None


class EditSharedWidgetData(TelegramMethod[bool]):
    __returning__ = bool
    __api_method__ = "editSharedWidgetData"

    widget_id: str
    public_data: str
    cache_time: int | None = None


class AnswerWidgetQuery(TelegramMethod[bool]):
    __returning__ = bool
    __api_method__ = "answerWidgetQuery"

    widget_query_id: str
    data: str | None = None


# ---------------- yangilanishlarni qabul qilish ----------------

WidgetHandler = Callable[[Bot, "WidgetQuery | SharedWidgetQuery"], Awaitable[str | None]]


class ShopDispatcher(Dispatcher):
    """aiogram Dispatcher + Bot API 10.4 widget so'rovlari.

    `widget_handler` javob matnini (≤ 1024 bayt) qaytaradi; dispetcher uni answerWidgetQuery bilan yuboradi.
    Ishlovchi bo'lmasa yoki xato bersa ham so'rovga bo'sh javob beriladi (widget 15 s kutib qolmasin).
    """

    widget_handler: WidgetHandler | None = None

    async def feed_update(self, bot: Bot, update: Update, **kwargs: Any) -> Any:
        extra = update.model_extra or {}
        for key, cls in (("widget_query", WidgetQuery), ("shared_widget_query", SharedWidgetQuery)):
            if key in extra:
                return await self._widget_query(bot, cls.model_validate(extra[key]))
        return await super().feed_update(bot, update, **kwargs)

    async def _widget_query(self, bot: Bot, query: WidgetQuery | SharedWidgetQuery) -> None:
        answer: str | None = None
        try:
            if self.widget_handler:
                answer = await self.widget_handler(bot, query)
        except Exception:  # noqa: BLE001
            log.exception("Widget so'rovini qayta ishlab bo'lmadi")
        if answer is not None and len(answer.encode()) > WIDGET_DATA_MAX:
            log.warning("Widget javobi 1024 baytdan uzun — qisqartirilmaydi, bo'sh javob yuboriladi")
            answer = None
        try:
            await bot(AnswerWidgetQuery(widget_query_id=query.id, data=answer))
        except Exception as e:  # noqa: BLE001
            log.warning("answerWidgetQuery bo'lmadi: %s", e)


def allowed_updates(dp: Dispatcher) -> list[str]:
    """Polling uchun: aiogram ishlatayotgan turlar + widget so'rovlari."""
    return sorted(set(dp.resolve_used_update_types()) | {"widget_query", "shared_widget_query"})
