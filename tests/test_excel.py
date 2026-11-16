from io import BytesIO
from zoneinfo import ZoneInfo

from openpyxl import load_workbook

from bot.db import DIRECTION_IN, EXPENSE, INCOME, Database
from bot.excel_report import EXPENSE_LABEL, INCOME_LABEL, build_report_workbook


def test_report_workbook_matches_screenshot_rows(tmp_path):
    db = Database(str(tmp_path / "finance.db"))
    moment = "2026-08-31T10:51:00+00:00"
    db.add_operation(
        chat_id=1,
        user_id=1,
        user_name="Пока Так",
        kind=INCOME,
        amount_kop=50000,
        comment="Нашел у подъезда",
        created_at=moment,
    )
    db.add_operation(
        chat_id=1,
        user_id=1,
        user_name="Пока Так",
        kind=EXPENSE,
        amount_kop=15000,
        comment="Выбил кофе",
        created_at=moment,
    )
    db.add_operation(
        chat_id=1,
        user_id=1,
        user_name="Пока Так",
        kind=EXPENSE,
        amount_kop=100000,
        comment="Перевёл другу за чипсы и сок",
        created_at=moment,
    )
    db.add_debt(
        chat_id=1,
        user_id=1,
        user_name="Пока Так",
        person="Иван",
        direction=DIRECTION_IN,
        amount_kop=250000,
        comment="Займ",
        created_at=moment,
    )
    tz = ZoneInfo("Asia/Dubai")
    payload = build_report_workbook(db.operations_between(1, None, None), db.list_debts(1), tz)
    workbook = load_workbook(BytesIO(payload))
    assert workbook.sheetnames == ["Операции", "Должники"]

    sheet = workbook["Операции"]
    assert [cell.value for cell in sheet[1]] == [
        "№",
        "Тип",
        "Сумма, ₽",
        "Комментарий",
        "Дата и время",
        "Где",
    ]
    assert sheet["F2"].value == "—"
    assert sheet["B2"].value == INCOME_LABEL
    assert sheet["C2"].value == 500
    assert sheet["D2"].value == "Нашел у подъезда"
    assert sheet["E2"].value == "31.08.2026 14:51"
    assert sheet["B3"].value == EXPENSE_LABEL
    assert sheet["C3"].value == 150
    assert sheet["D4"].value == "Перевёл другу за чипсы и сок"
    assert sheet["C4"].value == 1000
    assert sheet["A6"].value == "Итого:"
    assert sheet["B7"].value == "+ Доходы"
    assert sheet["C7"].value == 500
    assert sheet["B8"].value == "− Расходы"
    assert sheet["C8"].value == 1150
    assert sheet["B9"].value == "💰 Баланс"
    assert sheet["C9"].value == -650
    assert sheet["B10"].value == "💵 Наличные"
    assert sheet["C10"].value == 0
    assert sheet["B11"].value == "💳 Карта"
    assert sheet["C11"].value == 0
    assert sheet["B2"].font.color.rgb == "00006100"
    assert sheet["A1"].font.color.rgb == "00FFFFFF"

    debts = workbook["Должники"]
    assert debts["B2"].value == "Иван"
    assert debts["C2"].value == "Мне должны"
    assert debts["D2"].value == 2500
    assert debts["F2"].value == 2500
    assert debts["I2"].value == "Открыт"
