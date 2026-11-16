from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from bot.db import CARD, CASH, DIRECTION_IN, INCOME, Debt, Operation
from bot.keyboards import BTN_TODAY, BTN_YESTERDAY
from bot.money import format_amount, format_balance, from_kopecks
from bot.timeutils import format_day, format_local, parse_date, today_local


DESCRIPTION = (
    "Личный финансовый учёт. Записывай доходы и расходы, получай отчёты "
    "за день, период или автоматически. Книга должников — отдельной вкладкой."
)
SHORT_DESCRIPTION = "Доходы, расходы, отчёты и должники"

AMOUNT_ERROR = "❌ Введите корректную сумму (число больше 0):"
DATE_ERROR = "❌ Введите дату в формате ДД.ММ.ГГГГ:"


def display_name(first_name: str | None, last_name: str | None, username: str | None) -> str:
    parts = [part.strip() for part in (first_name or "", last_name or "") if part and part.strip()]
    if parts:
        return " ".join(parts)
    if username:
        return username
    return "друг"


def greeting(name: str) -> str:
    return (
        f"Привет, {name}! 👋\n"
        "\n"
        "💼 Личный финансовый учёт\n"
        "\n"
        "Записывай доходы и расходы, получай "
        "отчёты за день, период или автоматически."
    )


def help_text() -> str:
    return (
        "💼 Личный финансовый учёт\n"
        "\n"
        "+ Доход — записать поступление\n"
        "− Расход — записать трату\n"
        "📊 Отчёт — Excel за день, период или всё время\n"
        "📒 Должники — книга должников. В файле отчёта это вкладка «Должники».\n"
        "✏️ Правка — изменить сумму, комментарий, тип, место или удалить запись.\n"
        "💰 Баланс — сколько сейчас наличными и на карте.\n"
        "\n"
        "🔔 Автоотчёт включается в меню отчёта: бот сам пришлёт итог дня.\n"
        "\n"
        "В группе бот читает суммы и кнопки, если он администратор. "
        "Иначе в @BotFather отключите Privacy Mode командой /setprivacy "
        "и добавьте бота в группу заново."
    )


def kind_label(kind: str) -> str:
    if kind == INCOME:
        return "+ Доход"
    return "− Расход"


def pocket_label(pocket: str | None) -> str:
    if pocket == CASH:
        return "💵 Наличные"
    if pocket == CARD:
        return "💳 Карта"
    return "—"


def operation_line(operation: Operation, tz: ZoneInfo) -> str:
    amount = format_amount(from_kopecks(operation.amount_kop))
    comment = operation.comment or "—"
    when = format_local(operation.created_at, tz)
    place = pocket_label(operation.pocket)
    return f"#{operation.id} {kind_label(operation.kind)} · {place}\n{amount} ₽ · {comment}\n{when}"


def operation_card(operation: Operation, tz: ZoneInfo) -> str:
    amount = format_amount(from_kopecks(operation.amount_kop))
    comment = operation.comment or "—"
    when = format_local(operation.created_at, tz)
    return (
        f"#{operation.id} {kind_label(operation.kind)}\n"
        f"Сумма: {amount} ₽\n"
        f"Комментарий: {comment}\n"
        f"Где: {pocket_label(operation.pocket)}\n"
        f"Дата: {when}"
    )


def saved_operation(kind_label: str, amount: Decimal, comment: str, pocket: str | None) -> str:
    shown = comment or "—"
    return (
        f"✅ {kind_label} записан!\n"
        f"Сумма: {format_amount(amount)} ₽\n"
        f"Комментарий: {shown}\n"
        f"{pocket_label(pocket)}"
    )


def wallet_kop(operations: list[Operation]) -> tuple[int, int, int]:
    cash = card = other = 0
    for operation in operations:
        signed = operation.amount_kop if operation.kind == INCOME else -operation.amount_kop
        if operation.pocket == CASH:
            cash += signed
        elif operation.pocket == CARD:
            card += signed
        else:
            other += signed
    return cash, card, other


def wallet_text(cash_kop: int, card_kop: int, other_kop: int = 0) -> str:
    lines = [
        "💰 Сейчас",
        "",
        f"💵 Наличные: {format_balance(from_kopecks(cash_kop))} ₽",
        f"💳 Карта: {format_balance(from_kopecks(card_kop))} ₽",
    ]
    if other_kop:
        lines.append(f"❔ Без места: {format_balance(from_kopecks(other_kop))} ₽")
    total = cash_kop + card_kop + other_kop
    lines.append(f"Баланс: {format_balance(from_kopecks(total))} ₽")
    return "\n".join(lines)


def report_caption(
    title: str,
    income: Decimal,
    expense: Decimal,
    balance: Decimal,
    count: int,
    cash: Decimal | None = None,
    card: Decimal | None = None,
    unassigned: Decimal | None = None,
) -> str:
    lines = [
        f"📊 Отчёт: {title}",
        f"➕ Доходы: {format_amount(income)} ₽",
        f"➖ Расходы: {format_amount(expense)} ₽",
        f"💰 Баланс: {format_balance(balance)} ₽",
    ]
    if cash is not None and card is not None:
        lines.append(f"💵 Наличные: {format_balance(cash)} ₽")
        lines.append(f"💳 Карта: {format_balance(card)} ₽")
    if unassigned is not None and unassigned != 0:
        lines.append(f"❔ Без места: {format_balance(unassigned)} ₽")
    lines.append("")
    lines.append(f"Операций: {count}")
    return "\n".join(lines)


def empty_report_text(title: str) -> str:
    return f"📊 Отчёт: {title}\n\nОпераций нет."


def report_title(start: date | None, end: date | None, *, all_time: bool) -> str:
    if start is None or end is None:
        return "за всё время"
    if start == end and not all_time:
        return format_day(start)
    if start == end:
        return format_day(start)
    return f"{format_day(start)} — {format_day(end)}"


def report_filename(start: date | None, end: date | None) -> str:
    if start is None or end is None:
        return "report.xlsx"
    if start == end:
        return f"report_{format_day(start)}.xlsx"
    return f"report_{format_day(start)} {format_day(end)}.xlsx"


def parse_user_date(text: str, tz: ZoneInfo, today: date | None = None) -> date | None:
    raw = text.strip()
    current = today or today_local(tz)
    lowered = raw.lower()
    if raw == BTN_TODAY or lowered == "сегодня":
        return current
    if raw == BTN_YESTERDAY or lowered == "вчера":
        return current - timedelta(days=1)
    return parse_date(raw)


def direction_label(direction: str) -> str:
    if direction == DIRECTION_IN:
        return "мне должны"
    return "я должен"


def direction_title(direction: str) -> str:
    if direction == DIRECTION_IN:
        return "Мне должны"
    return "Я должен"


def debt_block(debt: Debt, tz: ZoneInfo) -> str:
    rest = format_amount(from_kopecks(debt.rest_kop))
    total = format_amount(from_kopecks(debt.amount_kop))
    comment = debt.comment or "—"
    when = format_local(debt.created_at, tz, with_time=False)
    status = "" if debt.status == "open" else "\nСтатус: закрыт"
    return (
        f"#{debt.id} {debt.person} — {direction_label(debt.direction)}\n"
        f"Остаток: {rest} ₽ из {total} ₽\n"
        f"Комментарий: {comment}\n"
        f"Дата: {when}{status}"
    )


def debts_home(open_debts: list[Debt]) -> str:
    owed = sum(debt.rest_kop for debt in open_debts if debt.direction == DIRECTION_IN)
    owe = sum(debt.rest_kop for debt in open_debts if debt.direction != DIRECTION_IN)
    balance = owed - owe
    if not open_debts:
        body = "Пока пусто. Нажмите «➕ Новый долг», чтобы записать, кто кому должен."
    else:
        body = (
            f"Открытых: {len(open_debts)}\n"
            f"👤 Мне должны: {format_amount(from_kopecks(owed))} ₽\n"
            f"🙋 Я должен: {format_amount(from_kopecks(owe))} ₽\n"
            f"💰 Сальдо: {format_balance(from_kopecks(balance))} ₽"
        )
    return (
        "📒 Книга должников\n"
        "\n"
        f"{body}\n"
        "\n"
        "Долги не смешиваются с доходами и расходами. "
        "В Excel-отчёте они на вкладке «Должники»."
    )


def saved_debt(debt: Debt) -> str:
    comment = debt.comment or "—"
    amount = format_amount(from_kopecks(debt.amount_kop))
    return (
        "✅ Долг записан!\n"
        f"#{debt.id} {debt.person} — {direction_label(debt.direction)}\n"
        f"Сумма: {amount} ₽\n"
        f"Комментарий: {comment}"
    )


def payment_saved(debt: Debt, paid: Decimal) -> str:
    rest = format_amount(from_kopecks(debt.rest_kop))
    if debt.status != "open":
        return (
            "✅ Долг закрыт!\n"
            f"#{debt.id} {debt.person}\n"
            f"Сумма: {format_amount(from_kopecks(debt.amount_kop))} ₽"
        )
    return (
        "✅ Платёж записан!\n"
        f"#{debt.id} {debt.person}\n"
        f"Погашено: {format_amount(paid)} ₽\n"
        f"Остаток: {rest} ₽"
    )


def debts_book_caption(open_debts: list[Debt]) -> str:
    owed = sum(debt.rest_kop for debt in open_debts if debt.direction == DIRECTION_IN)
    owe = sum(debt.rest_kop for debt in open_debts if debt.direction != DIRECTION_IN)
    balance = owed - owe
    return (
        "📒 Книга должников\n"
        f"👤 Мне должны: {format_amount(from_kopecks(owed))} ₽\n"
        f"🙋 Я должен: {format_amount(from_kopecks(owe))} ₽\n"
        f"💰 Сальдо: {format_balance(from_kopecks(balance))} ₽\n"
        "\n"
        f"Открытых: {len(open_debts)}"
    )


def clean_person(text: str) -> str | None:
    name = " ".join(text.split())
    if not name or name.startswith("/") or len(name) > 80:
        return None
    return name


def clean_comment(text: str) -> str | None:
    value = text.strip()
    if not value:
        return None
    if value in {"-", "—", "нет", "Нет", "НЕТ"}:
        return ""
    if len(value) > 500:
        return None
    return value


def comment_too_long(text: str) -> bool:
    return len(text.strip()) > 500
