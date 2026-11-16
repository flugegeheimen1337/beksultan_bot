from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP

MAX_AMOUNT = Decimal("999999999.99")
_KOPECK = Decimal("0.01")
_WORD = re.compile(r"(?i)\b(руб(?:лей|ля)?|rub)\b")


def parse_amount(text: str | None) -> Decimal | None:
    """Parse a ruble amount. Rejects zero, negatives and anything that is not money."""
    if text is None:
        return None
    raw = text.strip().lower().replace("\u00a0", " ").replace("₽", " ")
    raw = _WORD.sub(" ", raw).replace(" ", "")
    if not raw:
        return None
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(",", ".")
    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", raw):
        return None
    value = Decimal(raw).quantize(_KOPECK, rounding=ROUND_HALF_UP)
    if value <= 0 or value > MAX_AMOUNT:
        return None
    return value


def to_kopecks(value: Decimal) -> int:
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_kopecks(value: int) -> Decimal:
    return (Decimal(value) / Decimal(100)).quantize(_KOPECK)


def format_amount(value: Decimal) -> str:
    """`1150` -> `1 150.00`, negatives keep the minus sign."""
    quantized = Decimal(value).quantize(_KOPECK, rounding=ROUND_HALF_UP)
    sign = "-" if quantized < 0 else ""
    whole, frac = f"{abs(quantized):.2f}".split(".")
    groups: list[str] = []
    while whole:
        groups.append(whole[-3:])
        whole = whole[:-3]
    return f"{sign}{' '.join(reversed(groups))}.{frac}"


def format_balance(value: Decimal) -> str:
    quantized = Decimal(value).quantize(_KOPECK, rounding=ROUND_HALF_UP)
    if quantized > 0:
        return f"+{format_amount(quantized)}"
    return format_amount(quantized)
