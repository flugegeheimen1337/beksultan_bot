from decimal import Decimal

from bot.money import format_amount, format_balance, parse_amount, to_kopecks


def test_parse_amount_accepts_plain_and_spaced_numbers():
    assert parse_amount("500") == Decimal("500.00")
    assert parse_amount("150.00") == Decimal("150.00")
    assert parse_amount("1 000") == Decimal("1000.00")
    assert parse_amount("1 000,50") == Decimal("1000.50")
    assert parse_amount("1000.5") == Decimal("1000.50")
    assert parse_amount("500 ₽") == Decimal("500.00")
    assert parse_amount("1,000.50") == Decimal("1000.50")
    assert parse_amount("1.000,50") == Decimal("1000.50")


def test_parse_amount_rejects_zero_and_junk():
    for raw in ("-", "0", "0.00", "-5", "−5", "abc", "", "   ", "0.004", None):
        assert parse_amount(raw) is None


def test_format_matches_screenshot_totals():
    assert format_amount(Decimal("500")) == "500.00"
    assert format_amount(Decimal("1150")) == "1 150.00"
    assert format_amount(Decimal("1000")) == "1 000.00"
    assert format_balance(Decimal("-650")) == "-650.00"
    assert format_amount(Decimal("1379994.49")) == "1 379 994.49"
    assert format_amount(Decimal("180744.63")) == "180 744.63"
    assert format_balance(Decimal("1199249.86")) == "+1 199 249.86"
    assert to_kopecks(Decimal("150.5")) == 15050
