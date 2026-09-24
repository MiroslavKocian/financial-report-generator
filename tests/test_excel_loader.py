"""Tests for Excel loading and column normalization."""

from pathlib import Path

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
