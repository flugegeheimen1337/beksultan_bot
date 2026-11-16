from __future__ import annotations

import logging
from datetime import date

from aiogram import BaseMiddleware, F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import ErrorEvent, Message, TelegramObject

from bot.config import Settings
from bot.db import (
    DIRECTION_IN,
    DIRECTION_OUT,
    EXPENSE,
    INCOME,
    STATUS_OPEN,
    Database,
)
from bot.keyboards import (
    BTN_ALL,
    BTN_BACK,
    BTN_CANCEL,
    BTN_CLOSE_FULL,
    BTN_CONFIRM_DELETE,
    BTN_DAY,
    BTN_DEBT_EXCEL,
    BTN_DEBTS,
    BTN_DELETE,
    BTN_EXPENSE,
    BTN_I_OWE,
    BTN_INCOME,
    BTN_NEW_DEBT,
    BTN_OPEN_DEBTS,
    BTN_OWED,
    BTN_PAY,
    BTN_PERIOD,
    BTN_REPORT,
    cancel_kb,
    confirm_delete_kb,
    day_kb,
    debts_kb,
    direction_kb,
    main_kb,
    pay_amount_kb,
    report_type_kb,
)
from bot.money import format_amount, from_kopecks, parse_amount, to_kopecks
from bot.reporting import deliver_report, send_debts_book
from bot.states import DEBT_STATES, Flow
from bot.texts import (
    AMOUNT_ERROR,
    DATE_ERROR,
    clean_comment,
    clean_person,
    comment_too_long,
    debt_block,
    debts_home,
    display_name,
    greeting,
    help_text,
    parse_user_date,
    payment_saved,
    saved_debt,
    saved_operation,
)
from bot.timeutils import format_day

router = Router()
log = logging.getLogger(__name__)


class AllowChatsMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        if isinstance(event, Message):
            if event.chat.type not in {"private", "group", "supergroup"}:
                return None
            if event.from_user is None or event.from_user.is_bot:
                return None
        return await handler(event, data)


router.message.middleware(AllowChatsMiddleware())


def register(dispatcher) -> None:
    dispatcher.include_router(router)


def _name(message: Message) -> str:
    user = message.from_user
    return display_name(user.first_name, user.last_name, user.username)


def _take_comment(text: str) -> tuple[str | None, str | None]:
    if comment_too_long(text):
        return None, "Комментарий слишком длинный. Введите короче:"
    cleaned = clean_comment(text)
    if cleaned is None:
        return None, "Введите комментарий:"
    return cleaned, None


def _parse_id(text: str) -> int | None:
    raw = text.strip().lstrip("#")
    if not raw.isdigit():
        return None
    return int(raw)


async def _show_debts(message: Message, state: FSMContext, db: Database, prefix: str = "") -> None:
    await state.set_state(Flow.debts_menu)
    await state.set_data({"section": "debts"})
    open_debts = db.list_debts(message.chat.id, STATUS_OPEN)
    await message.answer(prefix + debts_home(open_debts), reply_markup=debts_kb())


async def _send_report(message: Message, state: FSMContext, db: Database, settings: Settings, start, end) -> None:
    await state.clear()
    try:
        await deliver_report(
            bot=message.bot,
            chat_id=message.chat.id,
            db=db,
            settings=settings,
            start=start,
            end=end,
            message=message,
            reply_markup=main_kb(),
        )
    except Exception:
        log.exception("report failed chat=%s", message.chat.id)
        await message.answer(
            "Не получилось собрать отчёт. Попробуйте ещё раз.",
            reply_markup=main_kb(),
        )


def _pack(header: str, blocks: list[str]) -> list[str]:
    messages: list[str] = []
    current = header
    for block in blocks:
        piece = block if current == header else f"\n\n{block}"
        if len(current) + len(piece) > 3500 and current != header:
            messages.append(current)
            current = block
        else:
            current += piece
    if current:
        messages.append(current)
    return messages


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(greeting(_name(message)), reply_markup=main_kb())
    if message.chat.type != "private":
        await message.answer(
            "В группе бот видит суммы и кнопки, если он администратор. "
            "Либо в @BotFather отключите Privacy Mode командой /setprivacy "
            "и добавьте бота в группу заново."
        )


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(help_text(), reply_markup=main_kb())


@router.message(Command("cancel"))
@router.message(F.text == BTN_CANCEL)
async def cmd_cancel(message: Message, state: FSMContext, db: Database) -> None:
    current = await state.get_state()
    data = await state.get_data()
    if current in DEBT_STATES or data.get("section") == "debts":
        await _show_debts(message, state, db, prefix="Действие отменено.\n\n")
        return
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_kb())


@router.message(Command("report"))
@router.message(F.text == BTN_REPORT)
async def cmd_report(message: Message, state: FSMContext, db: Database) -> None:
    enabled = db.auto_enabled(message.chat.id)
    await state.set_state(Flow.report_type)
    await state.set_data({})
    await message.answer("Тип отчёта:", reply_markup=report_type_kb(enabled))


@router.message(Command("debts"))
@router.message(F.text == BTN_DEBTS)
async def cmd_debts(message: Message, state: FSMContext, db: Database) -> None:
    await _show_debts(message, state, db)


@router.message(F.text == BTN_INCOME)
async def cmd_income(message: Message, state: FSMContext) -> None:
    await state.set_state(Flow.income_amount)
    await state.set_data({})
    await message.answer("Введите сумму дохода (₽):", reply_markup=cancel_kb())


@router.message(F.text == BTN_EXPENSE)
async def cmd_expense(message: Message, state: FSMContext) -> None:
    await state.set_state(Flow.expense_amount)
    await state.set_data({})
    await message.answer("Введите сумму расхода (₽):", reply_markup=cancel_kb())


@router.message(F.text == BTN_BACK)
async def cmd_back(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Главное меню.", reply_markup=main_kb())


@router.message(F.text == BTN_NEW_DEBT)
async def cmd_new_debt(message: Message, state: FSMContext) -> None:
    await state.set_state(Flow.debt_name)
    await state.set_data({"section": "debts"})
    await message.answer("Введите имя:", reply_markup=cancel_kb())


@router.message(F.text == BTN_OPEN_DEBTS)
async def cmd_open_debts(message: Message, state: FSMContext, db: Database, settings: Settings) -> None:
    await state.set_state(Flow.debts_menu)
    await state.set_data({"section": "debts"})
    debts = db.list_debts(message.chat.id, STATUS_OPEN)
    if not debts:
        await message.answer("Открытых долгов нет.", reply_markup=debts_kb())
        return
    zone = settings.zone()
    blocks = [debt_block(debt, zone) for debt in debts]
    parts = _pack("📋 Открытые долги\n\n", blocks)
    for index, part in enumerate(parts):
        markup = debts_kb() if index == len(parts) - 1 else None
        await message.answer(part, reply_markup=markup)


@router.message(F.text == BTN_PAY)
async def cmd_pay(message: Message, state: FSMContext, db: Database, settings: Settings) -> None:
    debts = db.list_debts(message.chat.id, STATUS_OPEN)
    await state.set_state(Flow.debts_menu)
    await state.set_data({"section": "debts"})
    if not debts:
        await message.answer("Открытых долгов нет.", reply_markup=debts_kb())
        return
    await state.set_state(Flow.debt_pay_pick)
    zone = settings.zone()
    shown = debts[:20]
    blocks = [debt_block(debt, zone) for debt in shown]
    extra = ""
    if len(debts) > 20:
        extra = "\n\nПоказаны первые 20. Номер можно ввести и для остальных."
    parts = _pack("💳 Погашение\n\n", blocks)
    parts[-1] += f"{extra}\n\nВведите номер долга:"
    for index, part in enumerate(parts):
        markup = cancel_kb() if index == len(parts) - 1 else None
        await message.answer(part, reply_markup=markup)


@router.message(F.text == BTN_DEBT_EXCEL)
async def cmd_debt_excel(message: Message, state: FSMContext, db: Database, settings: Settings) -> None:
    await state.set_state(Flow.debts_menu)
    await state.set_data({"section": "debts"})
    try:
        await send_debts_book(message=message, db=db, settings=settings)
    except Exception:
        log.exception("debts excel failed chat=%s", message.chat.id)
        await message.answer("Не получилось собрать книгу. Попробуйте ещё раз.", reply_markup=debts_kb())


@router.message(F.text == BTN_DELETE)
async def cmd_delete(message: Message, state: FSMContext, db: Database, settings: Settings) -> None:
    debts = db.list_debts(message.chat.id)
    await state.set_state(Flow.debts_menu)
    await state.set_data({"section": "debts"})
    if not debts:
        await message.answer("Книга должников пуста.", reply_markup=debts_kb())
        return
    await state.set_state(Flow.debt_delete_pick)
    zone = settings.zone()
    blocks = [debt_block(debt, zone) for debt in debts[:30]]
    extra = ""
    if len(debts) > 30:
        extra = "\n\nПоказаны первые 30."
    parts = _pack("🗑 Удаление\n\n", blocks)
    parts[-1] += f"{extra}\n\nВведите номер долга:"
    for index, part in enumerate(parts):
        markup = cancel_kb() if index == len(parts) - 1 else None
        await message.answer(part, reply_markup=markup)


@router.message(Flow.income_amount, F.text)
async def income_amount(message: Message, state: FSMContext) -> None:
    amount = parse_amount(message.text)
    if amount is None:
        await message.answer(AMOUNT_ERROR)
        return
    await state.update_data(amount_kop=to_kopecks(amount))
    await state.set_state(Flow.income_comment)
    await message.answer("Введите комментарий:", reply_markup=cancel_kb())


@router.message(Flow.expense_amount, F.text)
async def expense_amount(message: Message, state: FSMContext) -> None:
    amount = parse_amount(message.text)
    if amount is None:
        await message.answer(AMOUNT_ERROR)
        return
    await state.update_data(amount_kop=to_kopecks(amount))
    await state.set_state(Flow.expense_comment)
    await message.answer("Введите комментарий:", reply_markup=cancel_kb())


@router.message(Flow.income_comment, F.text)
async def income_comment(message: Message, state: FSMContext, db: Database) -> None:
    await _save_operation(message, state, db, INCOME, "Доход")


@router.message(Flow.expense_comment, F.text)
async def expense_comment(message: Message, state: FSMContext, db: Database) -> None:
    await _save_operation(message, state, db, EXPENSE, "Расход")


async def _save_operation(message: Message, state: FSMContext, db: Database, kind: str, label: str) -> None:
    comment, error = _take_comment(message.text or "")
    if error:
        await message.answer(error)
        return
    data = await state.get_data()
    amount_kop = int(data["amount_kop"])
    await state.clear()
    db.add_operation(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        user_name=_name(message),
        kind=kind,
        amount_kop=amount_kop,
        comment=comment or "",
    )
    await message.answer(
        saved_operation(label, from_kopecks(amount_kop), comment or ""),
        reply_markup=main_kb(),
    )


@router.message(Flow.report_type, F.text == BTN_DAY)
async def report_day_prompt(message: Message, state: FSMContext) -> None:
    await state.set_state(Flow.report_day)
    await message.answer("За какой день?", reply_markup=day_kb())


@router.message(Flow.report_type, F.text == BTN_PERIOD)
async def report_period_prompt(message: Message, state: FSMContext) -> None:
    await state.set_state(Flow.period_start)
    await message.answer("Введите начало периода\n(ДД.ММ.ГГГГ):", reply_markup=cancel_kb())


@router.message(Flow.report_type, F.text == BTN_ALL)
async def report_all(message: Message, state: FSMContext, db: Database, settings: Settings) -> None:
    await _send_report(message, state, db, settings, None, None)


@router.message(Flow.report_type, F.text.startswith("🔔 Автоотчёт"))
async def toggle_auto(message: Message, state: FSMContext, db: Database, settings: Settings) -> None:
    enabled = not db.auto_enabled(message.chat.id)
    db.set_auto(message.chat.id, enabled)
    hour = settings.auto_report_hour
    if enabled:
        text = (
            f"🔔 Автоотчёт включён. Каждый день в {hour:02d}:00 "
            "пришлю итог за день, если были операции."
        )
    else:
        text = "🔔 Автоотчёт выключен."
    await state.set_state(Flow.report_type)
    await message.answer(text, reply_markup=report_type_kb(enabled))


@router.message(Flow.report_day, F.text)
async def report_day(message: Message, state: FSMContext, db: Database, settings: Settings) -> None:
    day = parse_user_date(message.text or "", settings.zone())
    if day is None:
        await message.answer(DATE_ERROR, reply_markup=day_kb())
        return
    await _send_report(message, state, db, settings, day, day)


@router.message(Flow.period_start, F.text)
async def period_start(message: Message, state: FSMContext, settings: Settings) -> None:
    day = parse_user_date(message.text or "", settings.zone())
    if day is None:
        await message.answer(DATE_ERROR)
        return
    await state.update_data(period_start=day.isoformat())
    await state.set_state(Flow.period_end)
    await message.answer(
        f"Начало: {format_day(day)}\n\n"
        "Конец периода — кнопкой или введите дату (ДД.ММ.ГГГГ):",
        reply_markup=day_kb(),
    )


@router.message(Flow.period_end, F.text)
async def period_end(message: Message, state: FSMContext, db: Database, settings: Settings) -> None:
    end = parse_user_date(message.text or "", settings.zone())
    if end is None:
        await message.answer(DATE_ERROR, reply_markup=day_kb())
        return
    data = await state.get_data()
    start = date.fromisoformat(data["period_start"])
    if end < start:
        await message.answer(
            "❌ Конец периода раньше начала. Введите другую дату:",
            reply_markup=day_kb(),
        )
        return
    await _send_report(message, state, db, settings, start, end)


@router.message(Flow.debt_name, F.text)
async def debt_name(message: Message, state: FSMContext) -> None:
    person = clean_person(message.text or "")
    if person is None:
        await message.answer("Введите имя (до 80 символов):")
        return
    await state.update_data(person=person)
    await state.set_state(Flow.debt_amount)
    await message.answer("Введите сумму долга (₽):", reply_markup=cancel_kb())


@router.message(Flow.debt_amount, F.text)
async def debt_amount(message: Message, state: FSMContext) -> None:
    amount = parse_amount(message.text)
    if amount is None:
        await message.answer(AMOUNT_ERROR)
        return
    await state.update_data(amount_kop=to_kopecks(amount))
    await state.set_state(Flow.debt_comment)
    await message.answer("Введите комментарий:", reply_markup=cancel_kb())


@router.message(Flow.debt_comment, F.text)
async def debt_comment(message: Message, state: FSMContext) -> None:
    comment, error = _take_comment(message.text or "")
    if error:
        await message.answer(error)
        return
    await state.update_data(comment=comment)
    await state.set_state(Flow.debt_direction)
    await message.answer("Кто кому должен?", reply_markup=direction_kb())


@router.message(Flow.debt_direction, F.text.in_({BTN_OWED, BTN_I_OWE}))
async def debt_direction(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    direction = DIRECTION_IN if message.text == BTN_OWED else DIRECTION_OUT
    await state.set_state(Flow.debts_menu)
    await state.set_data({"section": "debts"})
    debt = db.add_debt(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        user_name=_name(message),
        person=data["person"],
        direction=direction,
        amount_kop=int(data["amount_kop"]),
        comment=data.get("comment") or "",
    )
    await message.answer(saved_debt(debt), reply_markup=debts_kb())


@router.message(Flow.debt_direction, F.text)
async def debt_direction_unknown(message: Message) -> None:
    await message.answer("Выберите кнопку: кому должен.", reply_markup=direction_kb())


@router.message(Flow.debt_pay_pick, F.text)
async def debt_pay_pick(message: Message, state: FSMContext, db: Database) -> None:
    debt_id = _parse_id(message.text or "")
    debt = db.get_debt(message.chat.id, debt_id) if debt_id is not None else None
    if debt is None or debt.status != STATUS_OPEN:
        await message.answer("❌ Этот долг не найден среди открытых. Введите номер:")
        return
    await state.set_state(Flow.debt_pay_amount)
    await state.update_data(debt_id=debt.id, section="debts")
    rest = format_amount(from_kopecks(debt.rest_kop))
    await message.answer(
        f"#{debt.id} {debt.person}\n"
        f"Остаток: {rest} ₽\n"
        "\n"
        "Введите сумму погашения или закройте долг целиком:",
        reply_markup=pay_amount_kb(),
    )


@router.message(Flow.debt_pay_amount, F.text == BTN_CLOSE_FULL)
async def debt_pay_full(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    debt = db.get_debt(message.chat.id, int(data["debt_id"]))
    await state.set_state(Flow.debts_menu)
    await state.set_data({"section": "debts"})
    if debt is None or debt.status != STATUS_OPEN:
        await message.answer("Этот долг уже закрыт.", reply_markup=debts_kb())
        return
    result = db.add_payment(message.chat.id, debt.id, debt.rest_kop)
    if not result.ok or result.debt is None:
        await message.answer("Не получилось закрыть долг.", reply_markup=debts_kb())
        return
    await message.answer(
        payment_saved(result.debt, from_kopecks(debt.rest_kop)),
        reply_markup=debts_kb(),
    )


@router.message(Flow.debt_pay_amount, F.text)
async def debt_pay_amount(message: Message, state: FSMContext, db: Database) -> None:
    amount = parse_amount(message.text)
    if amount is None:
        await message.answer(AMOUNT_ERROR, reply_markup=pay_amount_kb())
        return
    data = await state.get_data()
    debt = db.get_debt(message.chat.id, int(data["debt_id"]))
    if debt is None or debt.status != STATUS_OPEN:
        await state.set_state(Flow.debts_menu)
        await state.set_data({"section": "debts"})
        await message.answer("Этот долг уже закрыт.", reply_markup=debts_kb())
        return
    paid_kop = to_kopecks(amount)
    if paid_kop > debt.rest_kop:
        rest = format_amount(from_kopecks(debt.rest_kop))
        await message.answer(
            f"❌ Сумма больше остатка ({rest} ₽). Введите меньшую сумму:",
            reply_markup=pay_amount_kb(),
        )
        return
    result = db.add_payment(message.chat.id, debt.id, paid_kop)
    await state.set_state(Flow.debts_menu)
    await state.set_data({"section": "debts"})
    if not result.ok or result.debt is None:
        await message.answer("Не получилось записать платёж.", reply_markup=debts_kb())
        return
    await message.answer(payment_saved(result.debt, amount), reply_markup=debts_kb())


@router.message(Flow.debt_delete_pick, F.text)
async def debt_delete_pick(message: Message, state: FSMContext, db: Database) -> None:
    debt_id = _parse_id(message.text or "")
    debt = db.get_debt(message.chat.id, debt_id) if debt_id is not None else None
    if debt is None:
        await message.answer("❌ Долг с таким номером не найден. Введите номер:")
        return
    await state.set_state(Flow.debt_delete_confirm)
    await state.update_data(debt_id=debt.id, section="debts")
    rest = format_amount(from_kopecks(debt.rest_kop))
    await message.answer(
        f"Удалить долг #{debt.id} ({debt.person}, остаток {rest} ₽)?",
        reply_markup=confirm_delete_kb(),
    )


@router.message(Flow.debt_delete_confirm, F.text == BTN_CONFIRM_DELETE)
async def debt_delete_confirm(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    deleted = db.delete_debt(message.chat.id, int(data["debt_id"]))
    await state.set_state(Flow.debts_menu)
    await state.set_data({"section": "debts"})
    text = "🗑 Долг удалён." if deleted else "Долг уже удалён."
    await message.answer(text, reply_markup=debts_kb())


@router.message(Flow.debt_delete_confirm, F.text)
async def debt_delete_unknown(message: Message) -> None:
    await message.answer("Подтвердите удаление или нажмите отмену.", reply_markup=confirm_delete_kb())


@router.message(Flow.income_amount)
@router.message(Flow.expense_amount)
@router.message(Flow.debt_amount)
@router.message(Flow.debt_pay_amount)
async def amount_other(message: Message) -> None:
    await message.answer(AMOUNT_ERROR)


@router.message(Flow.income_comment)
@router.message(Flow.expense_comment)
@router.message(Flow.debt_comment)
async def comment_other(message: Message) -> None:
    await message.answer("Введите комментарий текстом:")


@router.message(Flow.report_day)
@router.message(Flow.period_start)
@router.message(Flow.period_end)
async def date_other(message: Message) -> None:
    await message.answer(DATE_ERROR)


@router.message(Flow.debt_name)
async def name_other(message: Message) -> None:
    await message.answer("Введите имя текстом:")


@router.message(Flow.debt_direction)
async def direction_other(message: Message) -> None:
    await message.answer("Выберите кнопку: кому должен.", reply_markup=direction_kb())


@router.message(Flow.debt_pay_pick)
@router.message(Flow.debt_delete_pick)
async def pick_other(message: Message) -> None:
    await message.answer("❌ Введите номер долга из списка:")


@router.message(Flow.debts_menu)
async def debts_menu_other(message: Message) -> None:
    await message.answer("Выберите действие на клавиатуре.", reply_markup=debts_kb())


@router.message(Flow.report_type)
async def report_type_other(message: Message, db: Database) -> None:
    enabled = db.auto_enabled(message.chat.id)
    await message.answer("Выберите тип отчёта:", reply_markup=report_type_kb(enabled))


@router.message(StateFilter(None))
async def idle(message: Message) -> None:
    if message.text and message.text.startswith("/"):
        await message.answer("Неизвестная команда. Нажмите /help.", reply_markup=main_kb())
        return
    await message.answer("Выберите действие на клавиатуре.", reply_markup=main_kb())


@router.error()
async def on_error(event: ErrorEvent) -> None:
    log.exception("update failed", exc_info=event.exception)
    message = event.update.message if event.update else None
    if message is None:
        return
    try:
        await message.answer("Не получилось выполнить действие. Попробуйте ещё раз.")
    except Exception:
        log.debug("failed to notify chat about an error")
