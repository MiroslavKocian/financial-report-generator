"""Pandas summary of stored sales: total, minimum, and maximum amount."""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

AMOUNT_COLUMN: str = "amount"


def _fail(message: str) -> None:
    """Log a summary error, then raise it for the API to return."""
    logger.error("Sales summary failed: %s", message)
    raise ValueError(message)


def _money(value: float) -> float:
    """Round a monetary value to cents so JSON stays stable."""
    return round(float(value), 2)


def _numeric_amounts(dataframe: pd.DataFrame) -> pd.Series:
    """Return the amount column as numbers, or fail if any cell is not."""
    if dataframe.empty:
        _fail("Excel data has no rows.")
    if AMOUNT_COLUMN not in dataframe.columns:
        _fail("Excel data must include an 'amount' column.")

    try:
        amounts: pd.Series = pd.to_numeric(
            dataframe[AMOUNT_COLUMN],
            errors="raise",
        )
    except (ValueError, TypeError):
        _fail("Column 'amount' must contain only numbers.")

    if amounts.isna().any():
        _fail("Column 'amount' must contain only numbers.")
    return amounts


def validate_sales_dataframe(dataframe: pd.DataFrame) -> None:
    """Ensure a workbook is ready for storage and summary."""
    _numeric_amounts(dataframe)


def summarize_sales(dataframe: pd.DataFrame) -> dict:
    """Build the summary dict for one sales DataFrame."""
    amounts: pd.Series = _numeric_amounts(dataframe)
    return {
        "row_count": int(len(dataframe)),
        "total_amount": _money(amounts.sum()),
        "min_amount": _money(amounts.min()),
        "max_amount": _money(amounts.max()),
    }
