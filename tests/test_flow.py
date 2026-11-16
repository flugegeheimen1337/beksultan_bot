import asyncio
from datetime import date

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from openpyxl import load_workbook
from io import BytesIO

from bot.config import Settings
from bot.db import Database
from bot.handlers import (
    choose_pocket,
    cmd_balance,
    cmd_expense,
    cmd_fix,
    cmd_income,
    cmd_start,
    edit_amount,
    edit_amount_prompt,
    edit_day,
    edit_delete_confirm,
    edit_pocket_prompt,
    edit_pick,
    expense_amount,
    expense_comment,
    income_amount,
    income_comment,
    period_end,
    period_start,
    report_day,
    report_day_prompt,
    cmd_report,
)
from bot.keyboards import BTN_BALANCE, BTN_CARD, BTN_CASH, BTN_CONFIRM_DELETE, BTN_EDIT_POCKET, BTN_TODAY
from bot.states import Flow
from bot.texts import AMOUNT_ERROR


class FakeUser:
    id = 5
    first_name = "Пока"
    last_name = "Так"
    username = None
    is_bot = False


class FakeChat:
    id = 10
    type = "private"


class FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.chat = FakeChat()
        self.from_user = FakeUser()
        self.bot = None
        self.answers: list[str] = []
        self.documents: list[dict] = []

    async def answer(self, text, reply_markup=None):
        self.answers.append(text)

    async def answer_document(self, document, caption=None, reply_markup=None):
        self.documents.append(
            {"caption": caption, "filename": document.filename, "data": document.data}
        )


def _state() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=10, user_id=5)
    return FSMContext(storage=storage, key=key)


def _settings(path) -> Settings:
    return Settings("test-token", "Asia/Dubai", 21, str(path))


def test_screenshot_dialog_builds_day_report(tmp_path):
    async def run():
        db = Database(str(tmp_path / "finance.db"))
        settings = _settings(tmp_path / "finance.db")
        state = _state()

        start = FakeMessage("/start")
        await cmd_start(start, state)
        assert "Привет, Пока Так! 👋" in start.answers[0]
        assert await state.get_state() is None

        await cmd_income(FakeMessage("+ Доход"), state)
        bad = FakeMessage("-")
        await income_amount(bad, state)
        assert bad.answers == [AMOUNT_ERROR]
        assert await state.get_state() == Flow.income_amount.state

        amount = FakeMessage("500")
        await income_amount(amount, state)
        assert amount.answers == ["Введите комментарий:"]
        comment = FakeMessage("Нашел у подъезда")
        await income_comment(comment, state)
        assert comment.answers == ["Где деньги?"]
        cash = FakeMessage(BTN_CASH)
        await choose_pocket(cash, state, db, settings)
        assert "Доход записан" in cash.answers[0]
        assert "500.00 ₽" in cash.answers[0]
        assert "💵 Наличные" in cash.answers[0]

        await cmd_expense(FakeMessage("− Расход"), state)
        await expense_amount(FakeMessage("150"), state)
        coffee = FakeMessage("Выбил кофе")
        await expense_comment(coffee, state)
        coffee_place = FakeMessage(BTN_CASH)
        await choose_pocket(coffee_place, state, db, settings)
        assert "Расход записан" in coffee_place.answers[0]

        await cmd_expense(FakeMessage("− Расход"), state)
        rejected = FakeMessage("-")
        await expense_amount(rejected, state)
        assert rejected.answers == [AMOUNT_ERROR]
        await expense_amount(FakeMessage("1000"), state)
        transfer = FakeMessage("Перевёл другу за чипсы и сок")
        await expense_comment(transfer, state)
        card = FakeMessage(BTN_CARD)
        await choose_pocket(card, state, db, settings)
        assert "1 000.00 ₽" in card.answers[0]
        assert "💳 Карта" in card.answers[0]

        await cmd_report(FakeMessage("📊 Отчёт"), state, db)
        assert (await state.get_state()) == Flow.report_type.state
        prompt = FakeMessage("📅 За день")
        await report_day_prompt(prompt, state)
        assert prompt.answers == ["За какой день?"]

        today = date.today()
        # Operations above were stored at the real current time, so "today"
        # in Asia/Dubai includes them.
        from zoneinfo import ZoneInfo
        from bot.timeutils import today_local

        day = today_local(ZoneInfo("Asia/Dubai"))
        report = FakeMessage(BTN_TODAY)
        await report_day(report, state, db, settings)
        assert report.documents, report.answers
        document = report.documents[0]
        assert document["filename"] == f"report_{day.strftime('%d.%m.%Y')}.xlsx"
        assert "➕ Доходы: 500.00 ₽" in document["caption"]
        assert "➖ Расходы: 1 150.00 ₽" in document["caption"]
        assert "💰 Баланс: -650.00 ₽" in document["caption"]
        assert "💵 Наличные: +350.00 ₽" in document["caption"]
        assert "💳 Карта: -1 000.00 ₽" in document["caption"]
        assert "Операций: 3" in document["caption"]
        balance = FakeMessage(BTN_BALANCE)
        await cmd_balance(balance, state, db)
        assert "💵 Наличные: +350.00 ₽" in balance.answers[0]
        assert "💳 Карта: -1 000.00 ₽" in balance.answers[0]
        workbook = load_workbook(BytesIO(document["data"]))
        assert workbook.sheetnames[1] == "Должники"
        assert workbook["Операции"]["C9"].value == -650

        await cmd_report(FakeMessage("/report"), state, db)
        await period_start(FakeMessage("01.08.2026"), state, settings)
        early = FakeMessage("01.01.2026")
        await period_end(early, state, db, settings)
        assert "раньше начала" in early.answers[0]
        assert today >= date(2026, 8, 1)

    asyncio.run(run())


def test_edit_moves_cash_operation_onto_the_card(tmp_path):
    async def run():
        db = Database(str(tmp_path / "finance.db"))
        settings = _settings(tmp_path / "finance.db")
        state = _state()
        await cmd_income(FakeMessage("+ Доход"), state)
        await income_amount(FakeMessage("500"), state)
        await income_comment(FakeMessage("зарплата"), state)
        await choose_pocket(FakeMessage(BTN_CASH), state, db, settings)
        operation = db.operations_between(10, None, None)[0]
        assert operation.pocket == "cash"

        await cmd_fix(FakeMessage("✏️ Правка"), state)
        await edit_day(FakeMessage(BTN_TODAY), state, db, settings)
        await edit_pick(FakeMessage(str(operation.id)), state, db, settings)
        await edit_pocket_prompt(FakeMessage(BTN_EDIT_POCKET), state)
        moved = FakeMessage(BTN_CARD)
        await choose_pocket(moved, state, db, settings)
        assert "Место изменено" in moved.answers[-1]
        assert db.get_operation(10, operation.id).pocket == "card"

    asyncio.run(run())


def test_zero_amount_deletes_a_past_operation(tmp_path):
    async def run():
        db = Database(str(tmp_path / "finance.db"))
        settings = _settings(tmp_path / "finance.db")
        state = _state()
        await cmd_income(FakeMessage("+ Доход"), state)
        await income_amount(FakeMessage("500"), state)
        await income_comment(FakeMessage("ошибся"), state)
        await choose_pocket(FakeMessage(BTN_CASH), state, db, settings)
        operation = db.operations_between(10, None, None)[0]

        await cmd_fix(FakeMessage("✏️ Правка"), state)
        listed = FakeMessage(BTN_TODAY)
        await edit_day(listed, state, db, settings)
        assert f"#{operation.id}" in listed.answers[-1]

        picked = FakeMessage(str(operation.id))
        await edit_pick(picked, state, db, settings)
        assert "Что исправить?" in picked.answers[-1]

        await edit_amount_prompt(FakeMessage("✏️ Сумма"), state)
        zero = FakeMessage("0")
        await edit_amount(zero, state, db, settings)
        assert "удалить" in zero.answers[-1].lower()

        await edit_delete_confirm(FakeMessage(BTN_CONFIRM_DELETE), state, db, settings)
        assert db.get_operation(10, operation.id) is None

    asyncio.run(run())
