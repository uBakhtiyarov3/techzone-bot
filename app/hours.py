"""Ish jadvali: operatorlar ishlaydigan vaqt. Buyurtma 24/7 qabul qilinadi, faqat "closed" rejimi to'xtatadi."""
import json
from datetime import date, datetime, timedelta

from .utils import TZ, now

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_NAMES = {
    "uz": ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"],
    "ru": ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"],
}
DEFAULT_SCHEDULE = {d: ["09:00", "21:00"] for d in DAYS}


def load_schedule(settings: dict) -> dict:
    try:
        data = json.loads(settings.get("schedule") or "")
        return {d: data.get(d) for d in DAYS}
    except (ValueError, AttributeError):
        return dict(DEFAULT_SCHEDULE)


def parse_hhmm(text: str) -> tuple[int, int] | None:
    try:
        hh, mm = text.strip().replace(".", ":").split(":")
        hh, mm = int(hh), int(mm)
    except ValueError:
        return None
    if 0 <= hh <= 24 and 0 <= mm < 60 and not (hh == 24 and mm):
        return hh, mm
    return None


def day_window(schedule: dict, day: date) -> tuple[datetime, datetime] | None:
    """Shu kunning ish oynasi. Yopilish ochilishdan oldin bo'lsa — keyingi kunga o'tadi (masalan 10:00–02:00)."""
    hours = schedule.get(DAYS[day.weekday()])
    if not hours:
        return None
    o, c = parse_hhmm(hours[0]), parse_hhmm(hours[1])
    if not o or not c:
        return None
    start = datetime(day.year, day.month, day.day, tzinfo=TZ) + timedelta(hours=o[0], minutes=o[1])
    end = datetime(day.year, day.month, day.day, tzinfo=TZ) + timedelta(hours=c[0], minutes=c[1])
    if end <= start:
        end += timedelta(days=1)
    return start, end


def is_open_at(settings: dict, dt: datetime | None = None) -> bool:
    mode = settings.get("mode") or "auto"
    if mode == "open":
        return True
    if mode == "closed":
        return False
    dt = dt or now()
    schedule = load_schedule(settings)
    for d in (dt.date() - timedelta(days=1), dt.date()):
        w = day_window(schedule, d)
        if w and w[0] <= dt < w[1]:
            return True
    return False


def next_opening(settings: dict, dt: datetime | None = None) -> datetime | None:
    if (settings.get("mode") or "auto") != "auto":
        return None
    dt = dt or now()
    schedule = load_schedule(settings)
    for i in range(8):
        w = day_window(schedule, dt.date() + timedelta(days=i))
        if w and w[0] > dt:
            return w[0]
    return None


def today_hours(settings: dict) -> str | None:
    """Bugungi ish vaqti "10:00–23:00" yoki None (dam olish)."""
    hours = load_schedule(settings).get(DAYS[now().weekday()])
    return f"{hours[0]}–{hours[1]}" if hours else None


def schedule_lines(settings: dict, lang: str = "uz") -> list[str]:
    schedule = load_schedule(settings)
    off = "dam olish" if lang == "uz" else "выходной"
    return [
        f"{DAY_NAMES[lang][i]}: {schedule[d][0]}–{schedule[d][1]}" if schedule.get(d) else f"{DAY_NAMES[lang][i]}: {off}"
        for i, d in enumerate(DAYS)
    ]


def schedule_summary(settings: dict, lang: str = "uz") -> str:
    """Qisqa ko'rinish: barcha kunlar bir xil bo'lsa "Har kuni 10:00–23:00"."""
    schedule = load_schedule(settings)
    values = {tuple(v) if v else None for v in schedule.values()}
    if len(values) == 1 and None not in values:
        o, c = next(iter(values))
        return f"{'Har kuni' if lang == 'uz' else 'Ежедневно'} {o}–{c}"
    return "; ".join(schedule_lines(settings, lang))
