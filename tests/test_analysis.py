"""Tests for the small sales summary."""

import pandas as pd
import pytest

from analysis import summarize_sales, validate_sales_dataframe


def test_validate_sales_dataframe_accepts_valid_amount() -> None:
    validate_sales_dataframe(pd.DataFrame({"amount": [1.0]}))


def test_summarize_sales_totals_min_and_max() -> None:
    summary = summarize_sales(pd.DataFrame({"amount": [10, 2.5, 7]}))

    assert summary["row_count"] == 3
    assert summary["total_amount"] == 19.5
    assert summary["min_amount"] == 2.5
    assert summary["max_amount"] == 10.0


def test_summarize_sales_single_row_min_equals_max() -> None:
    summary = summarize_sales(pd.DataFrame({"amount": [42]}))

    assert summary["total_amount"] == 42.0
    assert summary["min_amount"] == 42.0
    assert summary["max_amount"] == 42.0


def test_summarize_sales_rejects_missing_amount(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("ERROR"):
        with pytest.raises(ValueError, match="amount"):
            summarize_sales(pd.DataFrame({"region": ["North"]}))
    assert "Sales summary failed" in caplog.text


def test_summarize_sales_rejects_empty_frame() -> None:
    with pytest.raises(ValueError, match="no rows"):
        summarize_sales(pd.DataFrame({"amount": []}))


def test_summarize_sales_rejects_non_numeric_amount() -> None:
    with pytest.raises(ValueError, match="only numbers"):
        summarize_sales(pd.DataFrame({"amount": ["n/a"]}))


def test_summarize_sales_rejects_missing_amount_value() -> None:
    with pytest.raises(ValueError, match="only numbers"):
        summarize_sales(pd.DataFrame({"amount": [1.0, None]}))
