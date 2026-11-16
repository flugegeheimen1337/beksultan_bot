from datetime import date
from zoneinfo import ZoneInfo

from bot.db import DIRECTION_IN, DIRECTION_OUT, EXPENSE, INCOME, Database
from bot.money import from_kopecks
from bot.timeutils import local_day_bounds


def test_day_bounds_follow_dubai_midnight():
    tz = ZoneInfo("Asia/Dubai")
    start, end = local_day_bounds(date(2026, 8, 31), tz)
    assert start == "2026-08-30T20:00:00+00:00"
    assert end == "2026-08-31T20:00:00+00:00"


def test_operations_stay_inside_local_day(tmp_path):
    db = Database(str(tmp_path / "finance.db"))
    tz = ZoneInfo("Asia/Dubai")
    db.add_operation(
        chat_id=1,
        user_id=2,
        user_name="Пока Так",
        kind=INCOME,
        amount_kop=50000,
        comment="Нашел у подъезда",
        created_at="2026-08-31T10:51:00+00:00",
    )
    db.add_operation(
        chat_id=1,
        user_id=2,
        user_name="Пока Так",
        kind=EXPENSE,
        amount_kop=15000,
        comment="Выбил кофе",
        created_at="2026-08-31T10:51:00+00:00",
    )
    db.add_operation(
        chat_id=1,
        user_id=2,
        user_name="Пока Так",
        kind=EXPENSE,
        amount_kop=100000,
        comment="Перевёл другу за чипсы и сок",
        created_at="2026-08-31T10:51:00+00:00",
    )
    db.add_operation(
        chat_id=1,
        user_id=2,
        user_name="Пока Так",
        kind=EXPENSE,
        amount_kop=100,
        comment="после полуночи",
        created_at="2026-08-31T21:30:00+00:00",
    )
    start, end = local_day_bounds(date(2026, 8, 31), tz)
    day = db.operations_between(1, start, end)
    assert [item.comment for item in day] == [
        "Нашел у подъезда",
        "Выбил кофе",
        "Перевёл другу за чипсы и сок",
    ]
    income = sum(item.amount_kop for item in day if item.kind == INCOME)
    expense = sum(item.amount_kop for item in day if item.kind == EXPENSE)
    assert from_kopecks(income - expense) == from_kopecks(-65000)

    next_start, next_end = local_day_bounds(date(2026, 9, 1), tz)
    nxt = db.operations_between(1, next_start, next_end)
    assert [item.comment for item in nxt] == ["после полуночи"]


def test_debt_payments_close_and_reject_overpay(tmp_path):
    db = Database(str(tmp_path / "finance.db"))
    debt = db.add_debt(
        chat_id=7,
        user_id=1,
        user_name="Аня",
        person="Иван",
        direction=DIRECTION_IN,
        amount_kop=500000,
        comment="Займ",
    )
    partial = db.add_payment(7, debt.id, 200000)
    assert partial.ok
    assert partial.debt is not None
    assert partial.debt.status == "open"
    assert partial.debt.rest_kop == 300000

    too_much = db.add_payment(7, debt.id, 300001)
    assert not too_much.ok
    assert too_much.reason == "too_much"

    closed = db.add_payment(7, debt.id, 300000)
    assert closed.ok
    assert closed.debt is not None
    assert closed.debt.status == "closed"
    assert closed.debt.rest_kop == 0
    assert db.list_debts(7, "open") == []

    other = db.add_debt(
        chat_id=7,
        user_id=1,
        user_name="Аня",
        person="Марина",
        direction=DIRECTION_OUT,
        amount_kop=120000,
        comment="Такси",
    )
    assert db.delete_debt(7, other.id)
    assert db.get_debt(7, other.id) is None
    assert db.list_payments(7)


def test_edit_keeps_the_original_day_and_delete_removes_it(tmp_path):
    db = Database(str(tmp_path / "finance.db"))
    moment = "2026-08-31T10:51:00+00:00"
    operation = db.add_operation(
        chat_id=1,
        user_id=2,
        user_name="Пока Так",
        kind=INCOME,
        amount_kop=50000,
        comment="Нашел у подъезда",
        created_at=moment,
    )
    updated = db.update_operation(1, operation.id, amount_kop=30000, comment="Исправил", kind=EXPENSE)
    assert updated is not None
    assert updated.amount_kop == 30000
    assert updated.comment == "Исправил"
    assert updated.kind == EXPENSE
    assert updated.created_at == moment
    assert db.delete_operation(1, operation.id) is True
    assert db.get_operation(1, operation.id) is None
    assert db.delete_operation(1, operation.id) is False


def test_recent_operations_are_newest_first(tmp_path):
    db = Database(str(tmp_path / "finance.db"))
    first = db.add_operation(
        chat_id=1, user_id=1, user_name="А", kind=INCOME, amount_kop=100,
        comment="старая", created_at="2026-08-01T10:00:00+00:00",
    )
    second = db.add_operation(
        chat_id=1, user_id=1, user_name="А", kind=EXPENSE, amount_kop=200,
        comment="новая", created_at="2026-08-02T10:00:00+00:00",
    )
    recent = db.recent_operations(1, 10)
    assert [item.id for item in recent] == [second.id, first.id]


def test_auto_report_flag(tmp_path):
    db = Database(str(tmp_path / "finance.db"))
    assert db.auto_enabled(3) is False
    db.set_auto(3, True)
    assert db.auto_chats() == [(3, None)]
    db.mark_auto_sent(3, "2026-11-16")
    assert db.auto_enabled(3) is True
    assert db.auto_chats() == [(3, "2026-11-16")]
    db.set_auto(3, False)
    assert db.auto_chats() == []
