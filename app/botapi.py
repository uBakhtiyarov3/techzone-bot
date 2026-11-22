"""Bot API 10.4 (9-noyabr 2026): widgetlar bilan bog'liq umumiy narsalar.

Metod va turlar aiogram 3.33 dan (rasmiy). Bu yerda — chegaralar va widget so'rovlariga javob beruvchi router.
"""
from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.types import SharedWidgetQuery, WidgetQuery

log = logging.getLogger(__name__)

API_VERSION = "10.4"
WIDGET_HTML_MAX = 32768        # bayt (UTF-8)
WIDGET_ZLIB_MAX = 4096         # zlib -9 bilan siqilgandan keyin
WIDGET_DATA_MAX = 1024         # public_data / chat_data / javob

router = Router(name="widgets")


@router.widget_query()
@router.shared_widget_query()
async def on_widget_query(query: WidgetQuery | SharedWidgetQuery, bot: Bot) -> None:
    """Widget so'rovlari. Hozirgi widgetlar so'rov yubormaydi (allow_queries o'chiq), lakin kelib qolsa —
    widget 15 soniya kutib qolmasligi uchun darhol bo'sh javob beramiz."""
    log.info("Widget so'rovi %s: %s", query.from_user.id, query.data[:64])
    try:
        await bot.answer_widget_query(widget_query_id=query.id)
    except Exception as e:  # noqa: BLE001
        log.warning("answerWidgetQuery bo'lmadi: %s", e)
