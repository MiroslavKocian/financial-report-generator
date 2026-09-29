"""Tests for Decimal parsing at the money boundary."""

from decimal import Decimal

import pytest

from financial_report_generator.money import format_amount, parse_amount


def test_parse_amount_quantizes_decimal_half_up() -> None:
    assert parse_amount(Decimal("1.005")) == Decimal("1.01")
    assert parse_amount(2) == Decimal("2.00")
    assert parse_amount(0.1) == Decimal("0.10")
    assert parse_amount(" 1.20 ") == Decimal("1.20")
    assert format_amount(parse_amount("1.2")) == "1.20"


def test_parse_amount_rejects_non_numbers() -> None:
    for value in (None, True, "", "n/a", "nan", float("inf")):
        with pytest.raises(ValueError, match="only numbers"):
            parse_amount(value)
