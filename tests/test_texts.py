from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo

from bot.keyboards import BTN_EXPENSE, BTN_INCOME, BTN_REPORT
from bot.texts import (
    empty_report_text,
    greeting,
    parse_user_date,
    report_caption,
    report_filename,
    saved_operation,
)


def test_greeting_uses_telegram_name():
    assert greeting("Пока Так") == (
        "Привет, Пока Так! 👋\n"
        "\n"
        "💼 Личный финансовый учёт\n"
        "\n"
        "Записывай доходы и расходы, получай "
        "отчёты за день, период или автоматически."
    )


def test_saved_operation_matches_screenshots():
    assert saved_operation("Доход", Decimal("500"), "Нашел у подъезда") == (
        "✅ Доход записан!\nСумма: 500.00 ₽\nКомментарий: Нашел у подъезда"
    )
    assert saved_operation("Расход", Decimal("1000"), "Перевёл другу за чипсы и сок") == (
        "✅ Расход записан!\nСумма: 1 000.00 ₽\nКомментарий: Перевёл другу за чипсы и сок"
    )


def test_day_report_caption():
    assert report_caption("31.08.2026", Decimal("500"), Decimal("1150"), Decimal("-650"), 3) == (
        "📊 Отчёт: 31.08.2026\n"
        "➕ Доходы: 500.00 ₽\n"
        "➖ Расходы: 1 150.00 ₽\n"
        "💰 Баланс: -650.00 ₽\n"
        "\n"
        "Операций: 3"
    )


def test_period_report_caption():
    assert report_caption(
        "01.08.2026 — 31.08.2026",
        Decimal("1379994.49"),
        Decimal("180744.63"),
        Decimal("1199249.86"),
        82,
    ) == (
        "📊 Отчёт: 01.08.2026 — 31.08.2026\n"
        "➕ Доходы: 1 379 994.49 ₽\n"
        "➖ Расходы: 180 744.63 ₽\n"
        "💰 Баланс: +1 199 249.86 ₽\n"
        "\n"
        "Операций: 82"
    )


def test_empty_report_and_filenames():
    assert empty_report_text("16.11.2026") == "📊 Отчёт: 16.11.2026\n\nОпераций нет."
    assert report_filename(date(2026, 8, 31), date(2026, 8, 31)) == "report_31.08.2026.xlsx"
    assert (
        report_filename(date(2026, 8, 1), date(2026, 8, 31))
        == "report_01.08.2026 31.08.2026.xlsx"
    )


def test_parse_user_date_buttons_and_text():
    tz = ZoneInfo("Asia/Dubai")
    today = date(2026, 8, 31)
    assert parse_user_date("📅 Сегодня", tz, today) == today
    assert parse_user_date("📅 Вчера", tz, today) == date(2026, 8, 30)
    assert parse_user_date("01.08.2026", tz, today) == date(2026, 8, 1)
    assert parse_user_date("31.02.2026", tz, today) is None
    assert parse_user_date("-", tz, today) is None


def test_menu_labels_match_screenshots():
    assert BTN_INCOME == "+ Доход"
    assert BTN_EXPENSE == "− Расход"
    assert BTN_REPORT == "📊 Отчёт"
