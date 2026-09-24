"""Read and normalize Excel sales files with pandas.

openpyxl reads .xlsx; column names are normalized so they can become
SQLite identifiers in the next pipeline step.
"""

import zipfile
from pathlib import Path

import pandas as pd


def normalize_column_name(name: object) -> str:
    """
    Turn a raw Excel header into a SQL-friendly identifier.

    Example: " Region Name " -> "region_name"
    """
    return str(name).strip().lower().replace(" ", "_")


def load_excel_dataframe(file_path: str | Path) -> pd.DataFrame:
    """
    Load an Excel file and return a DataFrame with normalized columns.

    Raises:
        ValueError: Unreadable workbook, no columns, or duplicate headers
        after normalization (e.g. "Amount" and "amount" both become amount).
    """
    try:
        dataframe: pd.DataFrame = pd.read_excel(
            file_path,
            engine="openpyxl",
        )
    except (
        ValueError,
        OSError,
        KeyError,
        AttributeError,
        TypeError,
        zipfile.BadZipFile,
    ) as exc:
        # Narrow catch: map library noise into one clear API error.
        raise ValueError(f"Invalid Excel file format: {exc}") from exc

    normalized_columns: list[str] = [
        normalize_column_name(column) for column in dataframe.columns
    ]
    if not normalized_columns:
        raise ValueError("Excel file has no columns.")
    if len(normalized_columns) != len(set(normalized_columns)):
        raise ValueError("Excel file has duplicate column names.")

    # Copy so callers get a new frame instead of a mutated original.
    result: pd.DataFrame = dataframe.copy()
    result.columns = normalized_columns
    return result
