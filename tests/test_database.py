"""Tests for raw SQL database helpers."""

import sqlite3
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from financial_report_generator.database import (
    DYNAMIC_SALES_TABLE,
    get_db_connection,
    load_sales_dataframe,
    replace_sales_dataset,
    validate_sql_identifier,
)


def test_replace_sales_dataset_stores_rows() -> None:
    stored = replace_sales_dataset(
        "sales.xlsx",
        pd.DataFrame({"region": ["North"], "amount": [10.5]}),
    )
    assert stored.upload_id > 0
    assert stored.rows_stored == 1

    loaded = load_sales_dataframe()
    assert list(loaded.columns) == ["region", "amount"]
    assert loaded.iloc[0]["region"] == "North"


def test_replace_sales_dataset_rejects_empty_filename() -> None:
    with pytest.raises(ValueError, match="filename"):
        replace_sales_dataset("", pd.DataFrame({"amount": [1.0]}))


def test_replace_sales_dataset_rejects_reserved_column() -> None:
    with pytest.raises(ValueError, match="reserved"):
        replace_sales_dataset(
            "bad.xlsx",
            pd.DataFrame({"id": [1], "amount": [1.0]}),
        )


def test_replace_sales_dataset_stores_sql_null_for_missing_cells() -> None:
    replace_sales_dataset(
        "na.xlsx",
        pd.DataFrame({"amount": [1.0, pd.NA]}),
    )
    conn = get_db_connection()
    rows = conn.execute(
        f"SELECT amount FROM {DYNAMIC_SALES_TABLE} ORDER BY id"
    ).fetchall()
    conn.close()
    assert rows[0]["amount"] == "1.00"
    assert rows[1]["amount"] is None


def test_replace_sales_dataset_raises_when_upload_id_missing() -> None:
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = None
    mock_conn = MagicMock()
    mock_conn.execute.return_value = mock_cursor

    with patch(
        "financial_report_generator.database.get_db_connection", return_value=mock_conn
    ):
        with pytest.raises(RuntimeError, match="upload id"):
            replace_sales_dataset("orphan.xlsx", pd.DataFrame({"amount": [1.0]}))


def test_replace_sales_dataset_rolls_back_on_sqlite_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    replace_sales_dataset(
        "first.xlsx",
        pd.DataFrame({"amount": [1.0]}),
    )
    inner: sqlite3.Connection = get_db_connection()

    class _FailingConnection:
        """Delegate to SQLite except executemany, which fails."""

        def executemany(self, *args: Any, **kwargs: Any) -> None:
            raise sqlite3.OperationalError("disk")

        def __getattr__(self, name: str) -> Any:
            return getattr(inner, name)

    with patch(
        "financial_report_generator.database.get_db_connection",
        return_value=_FailingConnection(),
    ):
        with caplog.at_level("ERROR"):
            with pytest.raises(RuntimeError, match="Failed to replace sales dataset"):
                replace_sales_dataset(
                    "second.xlsx",
                    pd.DataFrame({"amount": [2.0, 3.0]}),
                )

    assert "disk" in caplog.text
    loaded = load_sales_dataframe()
    assert loaded.iloc[0]["amount"] == "1.00"


def test_validate_sql_identifier_rejects_injection() -> None:
    with pytest.raises(ValueError, match="Invalid SQL identifier"):
        validate_sql_identifier("users; DROP TABLE uploads--")


def test_load_sales_dataframe_reads_stored_rows() -> None:
    replace_sales_dataset(
        "rows.xlsx",
        pd.DataFrame({"amount": [10.5, 2]}),
    )

    loaded: pd.DataFrame = load_sales_dataframe()

    assert list(loaded.columns) == ["amount"]
    assert len(loaded) == 2
    assert loaded.iloc[0]["amount"] == "10.50"


def test_load_sales_dataframe_requires_stored_data() -> None:
    with pytest.raises(ValueError, match="No sales data"):
        load_sales_dataframe()


def test_load_sales_dataframe_rejects_empty_table() -> None:
    conn: sqlite3.Connection = get_db_connection()
    conn.execute(
        """
        CREATE TABLE dynamic_sales_data (
            id INTEGER PRIMARY KEY,
            upload_id INTEGER,
            amount TEXT
        )
        """
    )
    conn.commit()
    conn.close()
    with pytest.raises(ValueError, match="No sales data"):
        load_sales_dataframe()


def test_load_sales_dataframe_rejects_unsafe_column() -> None:
    conn: sqlite3.Connection = get_db_connection()
    conn.execute(
        """
        CREATE TABLE dynamic_sales_data (
            id INTEGER PRIMARY KEY,
            "bad-col" TEXT
        )
        """
    )
    conn.execute("INSERT INTO dynamic_sales_data (\"bad-col\") VALUES ('1')")
    conn.commit()
    conn.close()

    with pytest.raises(ValueError, match="Invalid SQL identifier"):
        load_sales_dataframe()


def test_load_sales_dataframe_rejects_table_without_data_columns() -> None:
    conn: sqlite3.Connection = get_db_connection()
    conn.execute(
        """
        CREATE TABLE dynamic_sales_data (
            id INTEGER PRIMARY KEY,
            upload_id INTEGER
        )
        """
    )
    conn.commit()
    conn.close()

    with pytest.raises(ValueError, match="No sales data"):
        load_sales_dataframe()


def test_load_sales_dataframe_wraps_sqlite_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    replace_sales_dataset("rows.xlsx", pd.DataFrame({"amount": [1]}))
    real_conn: sqlite3.Connection = get_db_connection()

    class _FailingSelect:
        """Real connection, except the sales SELECT raises."""

        def execute(self, sql: str, *params: Any) -> sqlite3.Cursor:
            if sql.startswith("SELECT amount"):
                raise sqlite3.Error("disk")
            return real_conn.execute(sql, *params)

        def close(self) -> None:
            real_conn.close()

    with patch(
        "financial_report_generator.database.get_db_connection",
        return_value=_FailingSelect(),
    ):
        with caplog.at_level("ERROR"):
            with pytest.raises(RuntimeError, match="Failed to load sales data"):
                load_sales_dataframe()

    assert "disk" in caplog.text
