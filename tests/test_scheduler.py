from bot.scheduler import is_auto_due


def test_auto_report_is_due_once_after_the_hour():
    assert is_auto_due(None, "2026-11-16", 21, 20) is False
    assert is_auto_due(None, "2026-11-16", 21, 21) is True
    assert is_auto_due("2026-11-16", "2026-11-16", 21, 22) is False
    assert is_auto_due("2026-11-15", "2026-11-16", 21, 21) is True
