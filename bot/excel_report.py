from __future__ import annotations

from datetime import date
from io import BytesIO
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from bot.db import DIRECTION_IN, EXPENSE, INCOME, Debt, Operation, Payment
from bot.texts import direction_title, pocket_label, wallet_kop
from bot.timeutils import format_local, parse_iso

HEADER_FILL = PatternFill("solid", fgColor="2F75B6")
HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
INCOME_FILL = PatternFill("solid", fgColor="C6EFCE")
EXPENSE_FILL = PatternFill("solid", fgColor="FFC7CE")
INCOME_FONT = Font(name="Calibri", bold=True, color="006100", size=11)
EXPENSE_FONT = Font(name="Calibri", bold=True, color="9C0006", size=11)
POSITIVE_FILL = PatternFill("solid", fgColor="C6EFCE")
NEGATIVE_FILL = PatternFill("solid", fgColor="FFC7CE")
CLOSED_FILL = PatternFill("solid", fgColor="F2F2F2")
TOTAL_FILL = PatternFill("solid", fgColor="D6DCE4")
NORMAL_FONT = Font(name="Calibri", size=11)
BOLD_FONT = Font(name="Calibri", bold=True, size=11)
MUTED_FONT = Font(name="Calibri", size=11, color="666666")
THIN = Border(
    left=Side(style="thin", color="B0B0B0"),
    right=Side(style="thin", color="B0B0B0"),
    top=Side(style="thin", color="B0B0B0"),
    bottom=Side(style="thin", color="B0B0B0"),
)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
RIGHT = Alignment(horizontal="right", vertical="center")
AMOUNT_FORMAT = "#,##0.00"
BALANCE_FORMAT = "+#,##0.00;-#,##0.00;0.00"

INCOME_LABEL = "+ Доход"
EXPENSE_LABEL = "− Расход"


def build_report_workbook(
    operations: list[Operation],
    debts: list[Debt],
    tz: ZoneInfo,
) -> bytes:
    workbook = Workbook()
    operations_sheet = workbook.active
    operations_sheet.title = "Операции"
    _write_operations(operations_sheet, operations, tz)
    debts_sheet = workbook.create_sheet("Должники")
    _write_debts(debts_sheet, debts, tz)
    operations_sheet.sheet_properties.tabColor = "2F75B6"
    debts_sheet.sheet_properties.tabColor = "C65911"
    workbook.properties.creator = "Мой Помощник"
    workbook.properties.title = "Финансовый отчёт"
    return _save(workbook)


def build_debts_workbook(
    debts: list[Debt],
    payments: list[Payment],
    tz: ZoneInfo,
) -> bytes:
    workbook = Workbook()
    debts_sheet = workbook.active
    debts_sheet.title = "Должники"
    _write_debts(debts_sheet, debts, tz)
    payments_sheet = workbook.create_sheet("Платежи")
    _write_payments(payments_sheet, payments, tz)
    debts_sheet.sheet_properties.tabColor = "C65911"
    payments_sheet.sheet_properties.tabColor = "2F75B6"
    workbook.properties.creator = "Мой Помощник"
    workbook.properties.title = "Книга должников"
    return _save(workbook)


def _write_operations(sheet: Worksheet, operations: list[Operation], tz: ZoneInfo) -> None:
    headers = ["№", "Тип", "Сумма, ₽", "Комментарий", "Дата и время", "Где"]
    _header(sheet, headers)
    for index, operation in enumerate(operations, start=1):
        income = operation.kind == INCOME
        label = INCOME_LABEL if income else EXPENSE_LABEL
        fill = INCOME_FILL if income else EXPENSE_FILL
        kind_font = INCOME_FONT if income else EXPENSE_FONT
        values = [
            index,
            label,
            round(operation.amount_kop / 100, 2),
            operation.comment or "—",
            format_local(operation.created_at, tz),
            pocket_label(operation.pocket),
        ]
        for column, value in enumerate(values, start=1):
            cell = sheet.cell(index + 1, column, value)
            cell.fill = fill
            cell.font = kind_font if column == 2 else NORMAL_FONT
            cell.border = THIN
            cell.alignment = CENTER if column in {1, 5, 6} else RIGHT if column == 3 else LEFT
            if column == 3:
                cell.number_format = AMOUNT_FORMAT
    last_data = max(len(operations) + 1, 1)
    sheet.auto_filter.ref = f"A1:F{max(last_data, 1)}"
    sheet.freeze_panes = "A2"
    _size(sheet, [6, 16, 16, 42, 20, 16])
    _page(sheet)

    income_kop = sum(item.amount_kop for item in operations if item.kind == INCOME)
    expense_kop = sum(item.amount_kop for item in operations if item.kind == EXPENSE)
    balance_kop = income_kop - expense_kop
    cash_kop, card_kop, _other_kop = wallet_kop(operations)
    total_row = len(operations) + 3
    label_cell = sheet.cell(total_row, 1, "Итого:")
    label_cell.font = BOLD_FONT
    summary = [
        (INCOME, "+ Доходы", income_kop),
        (EXPENSE, "− Расходы", expense_kop),
        ("balance", "💰 Баланс", balance_kop),
        ("cash", "💵 Наличные", cash_kop),
        ("card", "💳 Карта", card_kop),
    ]
    for offset, (kind, title, kop) in enumerate(summary, start=1):
        row = total_row + offset
        title_cell = sheet.cell(row, 2, title)
        amount_cell = sheet.cell(row, 3, round(kop / 100, 2))
        signed = kind in {"balance", "cash", "card"}
        positive = kind == INCOME or (signed and kop >= 0)
        fill = POSITIVE_FILL if positive and kind != EXPENSE else NEGATIVE_FILL
        if kind == EXPENSE:
            fill = EXPENSE_FILL
        font = INCOME_FONT if positive and kind != EXPENSE else EXPENSE_FONT
        if signed and kop >= 0:
            font = INCOME_FONT
            fill = POSITIVE_FILL
        title_cell.font = font
        amount_cell.font = font
        title_cell.fill = fill
        amount_cell.fill = fill
        title_cell.alignment = LEFT
        amount_cell.alignment = RIGHT
        title_cell.border = THIN
        amount_cell.border = THIN
        amount_cell.number_format = BALANCE_FORMAT if signed else AMOUNT_FORMAT


def _write_debts(sheet: Worksheet, debts: list[Debt], tz: ZoneInfo) -> None:
    headers = [
        "№",
        "Имя",
        "Тип",
        "Сумма, ₽",
        "Погашено, ₽",
        "Остаток, ₽",
        "Комментарий",
        "Дата",
        "Статус",
    ]
    _header(sheet, headers)
    if not debts:
        note = sheet.cell(2, 1, "Пока нет записей")
        note.font = MUTED_FONT
        sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(headers))
        data_rows = 1
    else:
        for index, debt in enumerate(debts, start=1):
            owed = debt.direction == DIRECTION_IN
            fill = CLOSED_FILL if debt.status != "open" else INCOME_FILL if owed else EXPENSE_FILL
            kind_font = MUTED_FONT if debt.status != "open" else INCOME_FONT if owed else EXPENSE_FONT
            values = [
                index,
                debt.person,
                direction_title(debt.direction),
                round(debt.amount_kop / 100, 2),
                round(debt.paid_kop / 100, 2),
                round(debt.rest_kop / 100, 2),
                debt.comment or "—",
                format_local(debt.created_at, tz, with_time=False),
                "Открыт" if debt.status == "open" else "Закрыт",
            ]
            for column, value in enumerate(values, start=1):
                cell = sheet.cell(index + 1, column, value)
                cell.fill = fill
                cell.font = kind_font if column == 3 else (MUTED_FONT if debt.status != "open" else NORMAL_FONT)
                cell.border = THIN
                cell.alignment = RIGHT if column in {4, 5, 6} else CENTER if column in {1, 8, 9} else LEFT
                if column in {4, 5, 6}:
                    cell.number_format = AMOUNT_FORMAT
        data_rows = len(debts)
    last_data = data_rows + 1
    if debts:
        sheet.auto_filter.ref = f"A1:I{last_data}"
    sheet.freeze_panes = "A2"
    _size(sheet, [6, 22, 16, 14, 14, 14, 36, 14, 12])
    _page(sheet)

    open_debts = [debt for debt in debts if debt.status == "open"]
    owed_kop = sum(debt.rest_kop for debt in open_debts if debt.direction == DIRECTION_IN)
    owe_kop = sum(debt.rest_kop for debt in open_debts if debt.direction != DIRECTION_IN)
    balance_kop = owed_kop - owe_kop
    total_row = last_data + 2
    label = sheet.cell(total_row, 1, "Итого:")
    label.font = BOLD_FONT
    rows = [
        ("Мне должны", owed_kop, True),
        ("Я должен", owe_kop, False),
        ("💰 Сальдо", balance_kop, balance_kop >= 0),
    ]
    for offset, (title, kop, positive) in enumerate(rows, start=1):
        row = total_row + offset
        title_cell = sheet.cell(row, 2, title)
        amount_cell = sheet.cell(row, 6, round(kop / 100, 2))
        fill = POSITIVE_FILL if positive else NEGATIVE_FILL
        font = INCOME_FONT if positive else EXPENSE_FONT
        if title == "Я должен":
            fill = EXPENSE_FILL
            font = EXPENSE_FONT
        title_cell.fill = fill
        amount_cell.fill = fill
        title_cell.font = font
        amount_cell.font = font
        title_cell.border = THIN
        amount_cell.border = THIN
        title_cell.alignment = LEFT
        amount_cell.alignment = RIGHT
        amount_cell.number_format = BALANCE_FORMAT if title.startswith("💰") else AMOUNT_FORMAT


def _write_payments(sheet: Worksheet, payments: list[Payment], tz: ZoneInfo) -> None:
    headers = ["№", "Долг", "Имя", "Сумма, ₽", "Дата и время"]
    _header(sheet, headers)
    if not payments:
        note = sheet.cell(2, 1, "Платежей пока нет")
        note.font = MUTED_FONT
        sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(headers))
    else:
        for index, payment in enumerate(payments, start=1):
            values = [
                index,
                f"#{payment.debt_id}",
                payment.person,
                round(payment.amount_kop / 100, 2),
                format_local(payment.created_at, tz),
            ]
            for column, value in enumerate(values, start=1):
                cell = sheet.cell(index + 1, column, value)
                cell.font = NORMAL_FONT
                cell.border = THIN
                cell.alignment = RIGHT if column == 4 else CENTER if column in {1, 2, 5} else LEFT
                if column == 4:
                    cell.number_format = AMOUNT_FORMAT
                    cell.font = EXPENSE_FONT
                    cell.fill = EXPENSE_FILL
        sheet.auto_filter.ref = f"A1:E{len(payments) + 1}"
    sheet.freeze_panes = "A2"
    _size(sheet, [6, 12, 22, 16, 20])
    _page(sheet)


def _header(sheet: Worksheet, headers: list[str]) -> None:
    for column, title in enumerate(headers, start=1):
        cell = sheet.cell(1, column, title)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER
        cell.border = THIN
    sheet.row_dimensions[1].height = 24
    sheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"


def _size(sheet: Worksheet, widths: list[int]) -> None:
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width


def _page(sheet: Worksheet) -> None:
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToPage = True
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.horizontalCentered = True
    sheet.print_title_rows = "1:1"
    sheet.page_margins.left = 0.4
    sheet.page_margins.right = 0.4
    sheet.sheet_view.showGridLines = False


def _save(workbook: Workbook) -> bytes:
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def span_dates(operations: list[Operation], tz: ZoneInfo) -> tuple[date | None, date | None]:
    if not operations:
        return None, None
    days = [parse_iso(item.created_at).astimezone(tz).date() for item in operations]
    return min(days), max(days)
