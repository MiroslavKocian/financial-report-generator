"""Tests for the small sales summary."""

import pandas as pd
import pytest

from financial_report_generator.analysis import (
    grouped_sales,
    summarize_sales,
    validate_sales_dataframe,
)


def test_validate_sales_dataframe_accepts_valid_amount() -> None:
    validate_sales_dataframe(pd.DataFrame({"amount": [1.0]}))


def test_summarize_sales_totals_min_and_max() -> None:
    summary = summarize_sales(pd.DataFrame({"amount": [10, 2.5, 7]}))

    assert summary["row_count"] == 3
    assert summary["total_amount"] == "19.50"
    assert summary["min_amount"] == "2.50"
    assert summary["max_amount"] == "10.00"


def test_summarize_sales_single_row_min_equals_max() -> None:
    summary = summarize_sales(pd.DataFrame({"amount": [42]}))

    assert summary["total_amount"] == "42.00"
    assert summary["min_amount"] == "42.00"
    assert summary["max_amount"] == "42.00"


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


def test_summarize_sales_quantizes_binary_fractions() -> None:
    """0.1 + 0.2 must be 0.30, not a binary float artifact."""
    summary = summarize_sales(pd.DataFrame({"amount": [0.1, 0.2]}))
    assert summary["total_amount"] == "0.30"


def test_grouped_sales_defaults_to_region_in_first_seen_order() -> None:
    frame = pd.DataFrame(
        {
            "region": ["South", "North", "South"],
            "product": ["A", "B", "C"],
            "amount": [0.1, 0.2, 0.2],
        }
    )
    report = grouped_sales(frame)

    assert report["group_by"] == "region"
    assert report["total_amount"] == "0.50"
    groups = report["groups"]
    assert [row["group"] for row in groups] == ["South", "North"]
    assert groups[0]["total_amount"] == "0.30"
    assert groups[0]["row_count"] == 2
    assert groups[1]["total_amount"] == "0.20"


def test_grouped_sales_uses_product_when_region_missing() -> None:
    frame = pd.DataFrame({"product": ["A", "A"], "amount": ["1.10", "2.20"]})
    report = grouped_sales(frame)
    assert report["group_by"] == "product"
    assert report["groups"][0]["total_amount"] == "3.30"


def test_grouped_sales_honors_explicit_group_by() -> None:
    frame = pd.DataFrame(
        {
            "region": ["North", "North"],
            "product": ["A", "B"],
            "amount": [1, 2],
        }
    )
    report = grouped_sales(frame, group_by="product")
    assert report["group_by"] == "product"
    assert len(report["groups"]) == 2


def test_grouped_sales_rejects_amount_and_unknown_column() -> None:
    frame = pd.DataFrame({"region": ["North"], "amount": [1]})
    with pytest.raises(ValueError, match="amount column"):
        grouped_sales(frame, group_by="amount")
    with pytest.raises(ValueError, match="not in the stored data"):
        grouped_sales(frame, group_by="missing")


def test_grouped_sales_requires_a_category_column() -> None:
    with pytest.raises(ValueError, match="region or product"):
        grouped_sales(pd.DataFrame({"amount": [1, 2]}))


def test_grouped_sales_treats_missing_group_key_as_empty_string() -> None:
    frame = pd.DataFrame({"region": ["North", None], "amount": [1, 2]})
    report = grouped_sales(frame)
    assert report["groups"][1]["group"] == ""
    assert report["groups"][1]["total_amount"] == "2.00"
