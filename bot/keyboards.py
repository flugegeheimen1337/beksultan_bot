from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

# U+2212 MINUS SIGN, same glyph as on the client screenshots.
BTN_INCOME = "+ Доход"
BTN_EXPENSE = "− Расход"
BTN_REPORT = "📊 Отчёт"
BTN_DEBTS = "📒 Должники"
BTN_CANCEL = "❌ Отмена"
BTN_TODAY = "📅 Сегодня"
BTN_YESTERDAY = "📅 Вчера"
BTN_DAY = "📅 За день"
BTN_PERIOD = "📅 За период"
BTN_ALL = "📅 За всё время"
BTN_BACK = "⬅️ Назад"
BTN_NEW_DEBT = "➕ Новый долг"
BTN_OPEN_DEBTS = "📋 Открытые"
BTN_PAY = "💳 Погашение"
BTN_DEBT_EXCEL = "📥 Excel"
BTN_DELETE = "🗑 Удалить"
BTN_OWED = "👤 Мне должны"
BTN_I_OWE = "🙋 Я должен"
BTN_CLOSE_FULL = "✅ Закрыть полностью"
BTN_CONFIRM_DELETE = "✅ Да, удалить"
BTN_FIX = "✏️ Правка"
BTN_RECENT = "📋 Последние"
BTN_EDIT_AMOUNT = "✏️ Сумма"
BTN_EDIT_COMMENT = "✏️ Комментарий"
BTN_EDIT_TYPE = "🔁 Тип"
BTN_DELETE_OP = "🗑 Удалить операцию"
BTN_BACK_LIST = "⬅️ К списку"


def _kb(rows: list[list[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=item) for item in row] for row in rows],
        resize_keyboard=True,
        is_persistent=True,
    )


def main_kb() -> ReplyKeyboardMarkup:
    return _kb(
        [
            [BTN_INCOME, BTN_EXPENSE],
            [BTN_REPORT, BTN_DEBTS],
            [BTN_FIX],
        ]
    )


def cancel_kb() -> ReplyKeyboardMarkup:
    return _kb([[BTN_CANCEL]])


def report_type_kb(auto_enabled: bool) -> ReplyKeyboardMarkup:
    auto = "🔔 Автоотчёт: вкл" if auto_enabled else "🔔 Автоотчёт: выкл"
    return _kb(
        [
            [BTN_DAY, BTN_PERIOD],
            [BTN_ALL],
            [auto],
            [BTN_CANCEL],
        ]
    )


def day_kb() -> ReplyKeyboardMarkup:
    return _kb(
        [
            [BTN_TODAY, BTN_YESTERDAY],
            [BTN_CANCEL],
        ]
    )


def debts_kb() -> ReplyKeyboardMarkup:
    return _kb(
        [
            [BTN_NEW_DEBT],
            [BTN_OPEN_DEBTS, BTN_PAY],
            [BTN_DEBT_EXCEL, BTN_DELETE],
            [BTN_BACK],
        ]
    )


def direction_kb() -> ReplyKeyboardMarkup:
    return _kb(
        [
            [BTN_OWED, BTN_I_OWE],
            [BTN_CANCEL],
        ]
    )


def pay_amount_kb() -> ReplyKeyboardMarkup:
    return _kb(
        [
            [BTN_CLOSE_FULL],
            [BTN_CANCEL],
        ]
    )


def confirm_delete_kb() -> ReplyKeyboardMarkup:
    return _kb(
        [
            [BTN_CONFIRM_DELETE],
            [BTN_CANCEL],
        ]
    )


def edit_day_kb() -> ReplyKeyboardMarkup:
    return _kb(
        [
            [BTN_TODAY, BTN_YESTERDAY],
            [BTN_RECENT],
            [BTN_CANCEL],
        ]
    )


def edit_action_kb() -> ReplyKeyboardMarkup:
    return _kb(
        [
            [BTN_EDIT_AMOUNT, BTN_EDIT_COMMENT],
            [BTN_EDIT_TYPE, BTN_DELETE_OP],
            [BTN_BACK_LIST],
            [BTN_CANCEL],
        ]
    )
