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
    cmd_expense,
    cmd_income,
    cmd_start,
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
from bot.keyboards import BTN_TODAY
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
        await income_comment(comment, state, db)
        assert "Доход записан" in comment.answers[0]
        assert "500.00 ₽" in comment.answers[0]

        await cmd_expense(FakeMessage("− Расход"), state)
        await expense_amount(FakeMessage("150"), state)
        coffee = FakeMessage("Выбил кофе")
        await expense_comment(coffee, state, db)
        assert "Расход записан" in coffee.answers[0]

        await cmd_expense(FakeMessage("− Расход"), state)
        rejected = FakeMessage("-")
        await expense_amount(rejected, state)
        assert rejected.answers == [AMOUNT_ERROR]
        await expense_amount(FakeMessage("1000"), state)
        transfer = FakeMessage("Перевёл другу за чипсы и сок")
        await expense_comment(transfer, state, db)
        assert "1 000.00 ₽" in transfer.answers[0]

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
        assert "Операций: 3" in document["caption"]
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
