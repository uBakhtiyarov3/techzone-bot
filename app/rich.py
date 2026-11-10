"""Telegram Rich Messages (Bot API 10.x): barcha bot xabarlari rich formatda.

`Rich` — rich HTML quruvchi (sarlavha, jadval, ro'yxat, details, rasm/slaydshou).
`send` / `edit` / `answer` — yuborish; Telegram rad etsa oddiy HTML xabarga avtomatik qaytadi.
`RichSessionMiddleware` — kodning qolgan joylaridagi oddiy `sendMessage`/`editMessageText` larni ham
rich xabarga aylantiradi (bitta joydan boshqariladi).

Rasmlar: WEBAPP_URL (https) bo'lsa — URL orqali (Telegram o'zi keshlaydi), aks holda fayl yuklanadi va
olingan file_id keshlanadi.
"""
import html as _html
import logging
import re
from contextvars import ContextVar

from aiogram import Bot
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import EditMessageText, SendMessage, SendRichMessage, TelegramMethod
from aiogram.types import FSInputFile, InputMediaPhoto, InputRichMessage, InputRichMessageMedia, Message

from .config import config

log = logging.getLogger(__name__)

# fallback yuborilayotganda middleware xabarni qayta rich ga aylantirmasligi uchun
_SKIP_RICH: ContextVar[bool] = ContextVar("skip_rich", default=False)

# rasm yo'li -> Telegram file_id (bir marta yuklangan rasmni qayta yuklamaslik uchun)
PHOTO_CACHE: dict[str, str] = {}


def esc(text) -> str:
    return _html.escape(str(text if text is not None else ""), quote=True)


def _public_url(path: str) -> str | None:
    if path.startswith(("http://", "https://")):
        return path
    if config.webapp_url.startswith("https://"):
        return f"{config.webapp_url}/{path.lstrip('/')}"
    return None


def _local_file(path: str):
    if path.startswith("uploads/"):
        f = config.uploads_dir / path.removeprefix("uploads/")
    else:
        f = config.webapp_dir / path
    return f if f.exists() else None


class Rich:
    """Rich HTML quruvchi. Har bir metod self qaytaradi (zanjir bilan yozish uchun)."""

    def __init__(self):
        self.parts: list[str] = []
        self.media: list[InputRichMessageMedia] = []
        self.photo_paths: list[str] = []      # yuklangan rasmlar tartibi (file_id keshlash uchun)

    # ---------- matn ----------
    def h(self, text_html: str, level: int = 2) -> "Rich":
        self.parts.append(f"<h{level}>{text_html}</h{level}>")
        return self

    def p(self, text_html: str) -> "Rich":
        """Paragraf. Ichidagi \\n qatorlar <br> ga aylanadi."""
        if text_html:
            self.parts.append(f"<p>{nl2br(text_html)}</p>")
        return self

    def lines(self, lines: list[str]) -> "Rich":
        return self.p("\n".join(x for x in lines if x is not None))

    def quote(self, text_html: str, expandable: bool = False) -> "Rich":
        if text_html:
            self.parts.append(f"<blockquote{' expandable' if expandable else ''}>{nl2br(text_html)}</blockquote>")
        return self

    def aside(self, text_html: str) -> "Rich":
        self.parts.append(f"<aside>{text_html}</aside>")
        return self

    def hr(self) -> "Rich":
        self.parts.append("<hr/>")
        return self

    def footer(self, text_html: str) -> "Rich":
        self.parts.append(f"<footer>{text_html}</footer>")
        return self

    def ul(self, items: list[str], checks: list[bool] | None = None) -> "Rich":
        if not items:
            return self
        lis = []
        for i, it in enumerate(items):
            box = ""
            if checks is not None:
                box = f'<input type="checkbox"{" checked" if checks[i] else ""}>'
            lis.append(f"<li>{box}{it}</li>")
        self.parts.append("<ul>" + "".join(lis) + "</ul>")
        return self

    def table(self, rows: list[list[str]], header: list[str] | None = None, align: list[str] | None = None,
              caption: str = "", striped: bool = True) -> "Rich":
        """rows — HTML katakchalar. align — ustunlar bo'yicha 'left'/'center'/'right'."""
        if not rows:
            return self
        out = [f"<table bordered{' striped' if striped else ''} compact>"]
        if caption:
            out.append(f"<caption>{caption}</caption>")
        if header:
            out.append("<tr>" + "".join(f"<th{_al(align, i)}>{c}</th>" for i, c in enumerate(header)) + "</tr>")
        for row in rows:
            cells = []
            for i, c in enumerate(row):
                if isinstance(c, tuple):  # (matn, colspan)
                    cells.append(f'<td colspan="{c[1]}"{_al(align, i)}>{c[0]}</td>')
                else:
                    cells.append(f"<td{_al(align, i)}>{c}</td>")
            out.append("<tr>" + "".join(cells) + "</tr>")
        out.append("</table>")
        self.parts.append("".join(out))
        return self

    def details(self, summary_html: str, inner: "Rich", open_: bool = False) -> "Rich":
        self.parts.append(f"<details{' open' if open_ else ''}><summary>{summary_html}</summary>{inner.body()}</details>")
        self.media += inner.media
        self.photo_paths += inner.photo_paths
        return self

    # ---------- media ----------
    def _src(self, path: str) -> str | None:
        if path in PHOTO_CACHE:
            mid = f"m{len(self.media)}"
            self.media.append(InputRichMessageMedia(id=mid, media=InputMediaPhoto(media=PHOTO_CACHE[path])))
            return f"tg://photo?id={mid}"
        url = _public_url(path)
        if url:
            return url
        file = _local_file(path)
        if not file:
            return None
        mid = f"m{len(self.media)}"
        self.media.append(InputRichMessageMedia(id=mid, media=InputMediaPhoto(media=FSInputFile(file))))
        self.photo_paths.append(path)
        return f"tg://photo?id={mid}"

    def img(self, path: str, caption_html: str = "") -> "Rich":
        src = self._src(path) if path else None
        if src:
            if caption_html:
                self.parts.append(f'<figure><img src="{esc(src)}"/><figcaption>{caption_html}</figcaption></figure>')
            else:
                self.parts.append(f'<img src="{esc(src)}"/>')
        return self

    def gallery(self, paths: list[str], caption_html: str = "") -> "Rich":
        """Bitta rasm — oddiy rasm, bir nechta — slaydshou (varaqlab ko'riladi)."""
        srcs = [s for s in (self._src(p) for p in paths[:10]) if s]
        if len(srcs) == 1:
            self.parts.append(f'<figure><img src="{esc(srcs[0])}"/>'
                              + (f"<figcaption>{caption_html}</figcaption>" if caption_html else "") + "</figure>")
        elif srcs:
            imgs = "".join(f'<img src="{esc(s)}"/>' for s in srcs)
            cap = f"<figcaption>{caption_html}</figcaption>" if caption_html else ""
            self.parts.append(f"<tg-slideshow>{imgs}{cap}</tg-slideshow>")
        return self

    def map(self, lat: float, lng: float, caption_html: str = "") -> "Rich":
        tag = f'<tg-map lat="{lat:.6f}" long="{lng:.6f}" zoom="16"/>'
        self.parts.append(f"<figure>{tag}<figcaption>{caption_html}</figcaption></figure>" if caption_html else tag)
        return self

    # ---------- natija ----------
    def body(self) -> str:
        return "".join(self.parts)

    def build(self) -> InputRichMessage:
        return InputRichMessage(html=self.body() or "<p>…</p>", media=self.media or None)

    def plain(self) -> str:
        """Telegram rich xabarni qabul qilmasa — oddiy HTML matn."""
        return to_plain(self.body())


def _al(align: list[str] | None, i: int) -> str:
    if align and i < len(align) and align[i] and align[i] != "left":
        return f' align="{align[i]}"'
    return ""


def nl2br(text: str) -> str:
    return text.replace("\r", "").replace("\n", "<br>")


# ---------- rich HTML -> oddiy Telegram HTML (fallback) ----------

_BLOCK_BREAK = re.compile(r"</(p|h\d|li|tr|blockquote|aside|footer|figcaption|caption|table|ul|ol|details|summary)>"
                          r"|<br\s*/?>|<hr\s*/?>", re.I)
_DROP = re.compile(r"<(/?)(p|h\d|li|ul|ol|tr|td|th|table|caption|aside|footer|figure|figcaption|details|summary|"
                   r"input|tg-slideshow|tg-collage|img|tg-map|tg-button-row|cite|mark|sub|sup|br|hr)\b[^>]*>", re.I)


def to_plain(rich_html: str) -> str:
    text = re.sub(r"<h\d>(.*?)</h\d>", r"<b>\1</b>\n", rich_html, flags=re.S | re.I)
    text = re.sub(r'<input type="checkbox" checked>', "✅ ", text)
    text = re.sub(r'<input type="checkbox">', "▫️ ", text)
    text = re.sub(r"<li>", "• ", text)
    text = re.sub(r"</t[dh]>", "  ", text)
    text = re.sub(r"<blockquote[^>]*>", "<blockquote>", text)
    text = _BLOCK_BREAK.sub(lambda m: "\n" if not m.group(0).lower().startswith("</blockquote") else
                            "</blockquote>\n", text)
    text = _DROP.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text or "…"


# ---------- oddiy Telegram HTML -> rich HTML (middleware uchun) ----------

def legacy_to_rich(text: str) -> str:
    """Eski uslubdagi (parse_mode=HTML) matnni rich HTML ga: bo'sh qatorlar — paragraflar."""
    text = re.sub(r'<span class="tg-spoiler">(.*?)</span>', r"<tg-spoiler>\1</tg-spoiler>", text, flags=re.S)
    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        block = block.strip("\n")
        if not block:
            continue
        if block.startswith("<blockquote") and block.endswith("</blockquote>"):
            out.append(nl2br(block))
        elif block.startswith("<pre>"):
            out.append(block)
        else:
            out.append(f"<p>{nl2br(block)}</p>")
    return "".join(out) or "<p>…</p>"


def _remember(rich: Rich, msg) -> None:
    """Yuklangan rasmlarning file_id sini keshlaydi (javobdagi rasm bloklari tartibi bo'yicha)."""
    if not rich.photo_paths or not isinstance(msg, Message) or not msg.rich_message:
        return
    photos = []

    def walk(blocks):
        for b in blocks or []:
            if getattr(b, "type", "") == "photo" and getattr(b, "photo", None):
                photos.append(b.photo[-1].file_id)
            walk(getattr(b, "blocks", None))

    walk(msg.rich_message.blocks)
    for path, fid in zip(rich.photo_paths, photos):
        PHOTO_CACHE[path] = fid


# ---------- yuborish ----------

async def send(bot: Bot, chat_id: int, rich: Rich, reply_markup=None, **kw) -> Message:
    try:
        msg = await bot.send_rich_message(chat_id, rich.build(), reply_markup=reply_markup, **kw)
        _remember(rich, msg)
        return msg
    except TelegramBadRequest as e:
        if kw.pop("message_effect_id", None):  # effekt qo'llab-quvvatlanmasa — effektsiz qayta urinamiz
            return await send(bot, chat_id, rich, reply_markup, **kw)
        log.warning("Rich xabar qabul qilinmadi, oddiy matn: %s", e)
        token = _SKIP_RICH.set(True)
        try:
            return await bot.send_message(chat_id, rich.plain(), reply_markup=reply_markup,
                                          disable_web_page_preview=True, **kw)
        finally:
            _SKIP_RICH.reset(token)


async def answer(message: Message, rich: Rich, reply_markup=None) -> Message:
    return await send(message.bot, message.chat.id, rich, reply_markup)


async def edit(message: Message, rich: Rich, reply_markup=None) -> None:
    """Xabarni rich ko'rinishda tahrirlaydi; bo'lmasa o'chirib, yangisini yuboradi."""
    try:
        res = await message.bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id,
                                                  rich_message=rich.build(), reply_markup=reply_markup)
        _remember(rich, res)
        return
    except TelegramBadRequest as e:
        if "not modified" in str(e):
            return
        log.debug("Rich edit bo'lmadi: %s", e)
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    await send(message.bot, message.chat.id, rich, reply_markup)


class RichSessionMiddleware(BaseRequestMiddleware):
    """Oddiy matnli sendMessage / editMessageText so'rovlarini rich xabarga aylantiradi.

    Telegram rad etsa (masalan juda eski klient yoki noto'g'ri teg), asl so'rov o'zgarishsiz yuboriladi.
    """

    async def __call__(self, make_request, bot: Bot, method: TelegramMethod):
        rich_method = None
        from .bot_ui import style_markup

        style_markup(getattr(method, "reply_markup", None))  # tugma ranglari — bitta joyda
        if _SKIP_RICH.get():
            return await make_request(bot, method)
        if isinstance(method, SendMessage) and method.text and not getattr(method, "entities", None):
            rich_method = SendRichMessage(
                chat_id=method.chat_id, rich_message=InputRichMessage(html=legacy_to_rich(method.text)),
                reply_markup=method.reply_markup, disable_notification=method.disable_notification,
                reply_parameters=method.reply_parameters, message_thread_id=method.message_thread_id,
            )
        elif isinstance(method, EditMessageText) and method.text and method.rich_message is None \
                and not method.inline_message_id:
            rich_method = EditMessageText(
                chat_id=method.chat_id, message_id=method.message_id,
                rich_message=InputRichMessage(html=legacy_to_rich(method.text)), reply_markup=method.reply_markup,
            )
        if rich_method is None:
            return await make_request(bot, method)
        try:
            return await make_request(bot, rich_method)
        except TelegramBadRequest as e:
            if "not modified" in str(e):
                raise
            log.debug("Rich ga aylantirib bo'lmadi, asl so'rov: %s", e)
            return await make_request(bot, method)
