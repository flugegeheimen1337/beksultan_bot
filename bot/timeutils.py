from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def to_utc_iso(moment: datetime | None = None) -> str:
    current = moment or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc).replace(microsecond=0)
    return current.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def parse_iso(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S+00:00").replace(tzinfo=timezone.utc)


def today_local(tz: ZoneInfo, moment: datetime | None = None) -> date:
    current = moment or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(tz).date()


def format_local(value: str, tz: ZoneInfo, *, with_time: bool = True) -> str:
    local = parse_iso(value).astimezone(tz)
    if with_time:
        return local.strftime("%d.%m.%Y %H:%M")
    return local.strftime("%d.%m.%Y")


def local_day_bounds(day: date, tz: ZoneInfo) -> tuple[str, str]:
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = start + timedelta(days=1)
    return to_utc_iso(start), to_utc_iso(end)


def parse_date(text: str) -> date | None:
    raw = text.strip().rstrip(".")
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
        if 2000 <= parsed.year <= 2100:
            return parsed
    return None


def format_day(day: date) -> str:
    return day.strftime("%d.%m.%Y")
