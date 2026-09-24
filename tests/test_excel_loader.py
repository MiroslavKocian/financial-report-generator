"""Tests for Excel loading and column normalization."""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from excel_loader import load_excel_dataframe, normalize_column_name


def test_normalize_column_name() -> None:
    assert normalize_column_name(" Region Name ") == "region_name"


def test_load_excel_dataframe(tmp_path: Path) -> None:
    source: Path = tmp_path / "sales.xlsx"
    pd.DataFrame(
        {"Region": ["North"], "Amount": [100]}
    ).to_excel(source, index=False, engine="openpyxl")

    dataframe: pd.DataFrame = load_excel_dataframe(source)

    assert list(dataframe.columns) == ["region", "amount"]
    assert dataframe.iloc[0]["region"] == "North"


def test_load_excel_dataframe_rejects_non_excel(tmp_path: Path) -> None:
    bad_file: Path = tmp_path / "not_excel.txt"
    bad_file.write_text("plain text", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid Excel file format"):
        load_excel_dataframe(bad_file)


def test_load_excel_dataframe_rejects_empty_columns() -> None:
    empty_frame: pd.DataFrame = pd.DataFrame()
    with patch(
        "excel_loader.pd.read_excel",
        return_value=empty_frame,
    ):
        with pytest.raises(ValueError, match="no columns"):
            load_excel_dataframe("ignored.xlsx")


def test_load_excel_dataframe_rejects_duplicate_columns() -> None:
    duplicate_frame: pd.DataFrame = pd.DataFrame(
        [[1, 2]],
        columns=["Amount", "amount"],
    )
    with patch(
        "excel_loader.pd.read_excel",
        return_value=duplicate_frame,
    ):
        with pytest.raises(ValueError, match="duplicate column"):
            load_excel_dataframe("ignored.xlsx")
