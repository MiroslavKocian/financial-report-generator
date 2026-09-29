"""Sales checks, summary totals, and grouped totals using Decimal."""

import logging
from decimal import Decimal

import pandas as pd

from financial_report_generator.money import (
    AMOUNT_COLUMN,
    format_amount,
    parse_amount,
)

logger = logging.getLogger(__name__)

# Prefer these headers when the caller does not pass group_by.
DEFAULT_GROUP_COLUMNS: tuple[str, ...] = ("region", "product")


def _fail(message: str) -> None:
    """Log a summary error, then raise it for the API to return."""
    logger.error("Sales summary failed: %s", message)
    raise ValueError(message)


def _amounts(dataframe: pd.DataFrame) -> list[Decimal]:
    """Return every amount as Decimal, or fail if any cell is not."""
    if dataframe.empty:
        _fail("Excel data has no rows.")
    if AMOUNT_COLUMN not in dataframe.columns:
        _fail("Excel data must include an 'amount' column.")

    amounts: list[Decimal] = []
    for value in dataframe[AMOUNT_COLUMN].tolist():
        if pd.isna(value):
            _fail("Column 'amount' must contain only numbers.")
        try:
            amounts.append(parse_amount(value))
        except ValueError:
            _fail("Column 'amount' must contain only numbers.")
    return amounts


def validate_sales_dataframe(dataframe: pd.DataFrame) -> None:
    """Ensure a workbook is ready for storage and summary."""
    _amounts(dataframe)


def summarize_sales(dataframe: pd.DataFrame) -> dict[str, int | str]:
    """Build the summary dict for one sales DataFrame."""
    amounts: list[Decimal] = _amounts(dataframe)
    total: Decimal = sum(amounts, start=Decimal(0))
    return {
        "row_count": len(dataframe),
        "total_amount": format_amount(total),
        "min_amount": format_amount(min(amounts)),
        "max_amount": format_amount(max(amounts)),
    }


def resolve_group_column(
    columns: list[str],
    requested: str | None,
) -> str:
    """Pick the grouping column: explicit name, else region, else product."""
    if requested:
        if requested == AMOUNT_COLUMN:
            raise ValueError("Cannot group a report by the amount column.")
        if requested not in columns:
            raise ValueError(f"Column {requested!r} is not in the stored data.")
        return requested

    for candidate in DEFAULT_GROUP_COLUMNS:
        if candidate in columns:
            return candidate
    raise ValueError(
        "Grouped report needs a region or product column, "
        "or pass group_by for another stored column."
    )


def grouped_sales(
    dataframe: pd.DataFrame,
    group_by: str | None = None,
) -> dict[str, object]:
    """Sum amount within each group. Group order follows the first row seen."""
    column: str = resolve_group_column(
        [str(name) for name in dataframe.columns],
        group_by,
    )
    _amounts(dataframe)

    buckets: dict[str, list[Decimal]] = {}
    order: list[str] = []
    for _, row in dataframe.iterrows():
        raw_key: object = row[column]
        label: str = "" if pd.isna(raw_key) else str(raw_key)
        if label not in buckets:
            buckets[label] = []
            order.append(label)
        buckets[label].append(parse_amount(row[AMOUNT_COLUMN]))

    groups: list[dict[str, int | str]] = []
    for label in order:
        values: list[Decimal] = buckets[label]
        groups.append(
            {
                "group": label,
                "row_count": len(values),
                "total_amount": format_amount(sum(values, start=Decimal(0))),
                "min_amount": format_amount(min(values)),
                "max_amount": format_amount(max(values)),
            }
        )

    overall: dict[str, int | str] = summarize_sales(dataframe)
    return {
        "group_by": column,
        "row_count": overall["row_count"],
        "total_amount": overall["total_amount"],
        "groups": groups,
    }
