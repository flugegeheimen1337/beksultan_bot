from __future__ import annotations

from aiogram import Bot
from aiogram.types import BufferedInputFile, Message, ReplyKeyboardMarkup

from bot.config import Settings
from bot.db import INCOME, Database
from bot.excel_report import build_debts_workbook, build_report_workbook, span_dates
from bot.keyboards import debts_kb
from bot.money import from_kopecks
from bot.texts import (
    debts_book_caption,
    empty_report_text,
    report_caption,
    report_filename,
    report_title,
    wallet_kop,
)
from bot.timeutils import local_day_bounds


async def deliver_report(
    *,
    bot: Bot,
    chat_id: int,
    db: Database,
    settings: Settings,
    start,
    end,
    message: Message | None,
    reply_markup: ReplyKeyboardMarkup | None,
) -> bool:
    """Send a finance workbook. Returns True when a file was sent."""
    zone = settings.zone()
    if start is None or end is None:
        operations = db.operations_between(chat_id, None, None)
        span_start, span_end = span_dates(operations, zone)
        title = report_title(span_start, span_end, all_time=True)
        filename = report_filename(span_start, span_end)
    else:
        start_iso, _ = local_day_bounds(start, zone)
        _, end_iso = local_day_bounds(end, zone)
        operations = db.operations_between(chat_id, start_iso, end_iso)
        title = report_title(start, end, all_time=False)
        filename = report_filename(start, end)

    if not operations:
        if message is not None:
            await message.answer(empty_report_text(title), reply_markup=reply_markup)
        return False

    income_kop = sum(item.amount_kop for item in operations if item.kind == INCOME)
    expense_kop = sum(item.amount_kop for item in operations if item.kind != INCOME)
    balance_kop = income_kop - expense_kop
    cash_kop, card_kop, other_kop = wallet_kop(operations)
    caption = report_caption(
        title,
        from_kopecks(income_kop),
        from_kopecks(expense_kop),
        from_kopecks(balance_kop),
        len(operations),
        cash=from_kopecks(cash_kop),
        card=from_kopecks(card_kop),
        unassigned=from_kopecks(other_kop),
    )
    payload = build_report_workbook(operations, db.list_debts(chat_id), zone)
    await _send_file(bot, chat_id, message, payload, filename, caption, reply_markup)
    return True


async def send_debts_book(
    *,
    message: Message,
    db: Database,
    settings: Settings,
) -> None:
    zone = settings.zone()
    debts = db.list_debts(message.chat.id)
    payments = db.list_payments(message.chat.id)
    payload = build_debts_workbook(debts, payments, zone)
    open_debts = [debt for debt in debts if debt.status == "open"]
    await message.answer_document(
        BufferedInputFile(payload, filename="debtors.xlsx"),
        caption=debts_book_caption(open_debts),
        reply_markup=debts_kb(),
    )


async def _send_file(bot, chat_id, message, payload, filename, caption, reply_markup) -> None:
    document = BufferedInputFile(payload, filename=filename)
    if message is not None:
        await message.answer_document(document, caption=caption, reply_markup=reply_markup)
        return
    await bot.send_document(chat_id, document, caption=caption)
