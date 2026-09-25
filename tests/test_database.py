"""Tests for raw SQL database helpers."""

import os
import sqlite3
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from database import (
    DYNAMIC_SALES_TABLE,
    clear_stored_upload_data,
    ensure_dynamic_sales_table,
    get_db_connection,
    insert_generic_row,
    load_sales_dataframe,
    replace_sales_dataset,
    save_upload_metadata,
    store_dataframe_rows,
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
    assert rows[0]["amount"] == "1.0"
    assert rows[1]["amount"] is None


def test_replace_sales_dataset_raises_when_upload_id_missing() -> None:
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = None
    mock_conn = MagicMock()
    mock_conn.execute.return_value = mock_cursor

    with patch("database.get_db_connection", return_value=mock_conn):
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
        "database.get_db_connection",
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
    assert loaded.iloc[0]["amount"] in {"1.0", "1"}


def test_save_upload_metadata() -> None:
    file_id: int = save_upload_metadata("test_file.xlsx")
    assert isinstance(file_id, int)
    assert file_id > 0


def test_save_upload_metadata_persists_in_db() -> None:
    filename: str = "persisted_test.xlsx"
    file_id: int = save_upload_metadata(filename)

    conn: sqlite3.Connection = get_db_connection()
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute(
        "SELECT filename FROM uploads WHERE id = ?",
        (file_id,),
    )
    row: sqlite3.Row | None = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row["filename"] == filename


def test_save_upload_metadata_rejects_empty_filename() -> None:
    with pytest.raises(ValueError, match="filename"):
        save_upload_metadata("")


def test_insert_generic_row() -> None:
    conn: sqlite3.Connection = get_db_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                price REAL NOT NULL,
                in_stock INTEGER NOT NULL
            )
        """)
    conn.close()

    sample_data: dict[str, Any] = {
        "product_name": "Laptop Pro",
        "price": 1299.99,
        "in_stock": 15,
    }

    row_id: int = insert_generic_row("test_products", sample_data)

    assert isinstance(row_id, int)
    assert row_id > 0

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT product_name, price, in_stock FROM test_products WHERE id = ?",
        (row_id,),
    )
    row: sqlite3.Row | None = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row["product_name"] == "Laptop Pro"
    assert row["price"] == 1299.99
    assert row["in_stock"] == 15


def test_validate_sql_identifier_rejects_injection() -> None:
    with pytest.raises(ValueError, match="Invalid SQL identifier"):
        validate_sql_identifier("users; DROP TABLE uploads--")


def test_ensure_dynamic_sales_table_schema_mismatch() -> None:
    ensure_dynamic_sales_table(["region", "amount"])
    with pytest.raises(ValueError, match="do not match"):
        ensure_dynamic_sales_table(["region", "amount", "extra"])


def test_store_dataframe_rows() -> None:
    upload_id: int = save_upload_metadata("rows.xlsx")
    dataframe: pd.DataFrame = pd.DataFrame({"region": ["North"], "amount": [10.5]})

    count: int = store_dataframe_rows(upload_id, dataframe)
    assert count == 1

    conn: sqlite3.Connection = get_db_connection()
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute(f"SELECT region, amount, upload_id FROM {DYNAMIC_SALES_TABLE}")
    row: sqlite3.Row | None = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row["region"] == "North"
    assert row["amount"] == "10.5" or row["amount"] == 10.5
    assert row["upload_id"] == upload_id


def test_ensure_dynamic_sales_table_accepts_matching_schema() -> None:
    ensure_dynamic_sales_table(["region", "amount"])
    # Second call with the same columns should succeed (early return).
    ensure_dynamic_sales_table(["region", "amount"])


def test_clear_stored_upload_data_drops_sales_and_uploads() -> None:
    upload_id: int = save_upload_metadata("first.xlsx")
    store_dataframe_rows(
        upload_id,
        pd.DataFrame({"region": ["North"], "amount": [1.0]}),
    )

    clear_stored_upload_data()

    conn: sqlite3.Connection = get_db_connection()
    uploads_count: int = conn.execute("SELECT COUNT(*) FROM uploads").fetchone()[0]
    table_row = conn.execute(
        """
        SELECT 1 FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (DYNAMIC_SALES_TABLE,),
    ).fetchone()
    conn.close()

    assert uploads_count == 0
    assert table_row is None


def test_clear_stored_upload_data_allows_new_schema() -> None:
    upload_id: int = save_upload_metadata("first.xlsx")
    store_dataframe_rows(
        upload_id,
        pd.DataFrame({"region": ["North"], "amount": [1.0]}),
    )
    clear_stored_upload_data()

    # After clear, a workbook with different columns may be stored.
    new_id: int = save_upload_metadata("second.xlsx")
    count: int = store_dataframe_rows(
        new_id,
        pd.DataFrame({"product": ["A"], "price": [9.5]}),
    )
    assert count == 1


def test_insert_generic_row_rejects_empty_data() -> None:
    with pytest.raises(ValueError, match="row_data must not be empty"):
        insert_generic_row("uploads", {})


def test_insert_generic_row_wraps_sqlite_error() -> None:
    with pytest.raises(RuntimeError, match="Failed to insert"):
        insert_generic_row(
            "uploads",
            {"missing_column": "value"},
        )


def test_save_upload_metadata_raises_when_lastrowid_missing() -> None:
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = None
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.__exit__.return_value = False

    with patch(
        "database.get_db_connection",
        return_value=mock_conn,
    ):
        with pytest.raises(RuntimeError, match="upload id"):
            save_upload_metadata("orphan.xlsx")


def test_insert_generic_row_raises_when_lastrowid_missing() -> None:
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = None
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch(
        "database.get_db_connection",
        return_value=mock_conn,
    ):
        with pytest.raises(RuntimeError, match="row id"):
            insert_generic_row(
                "uploads",
                {"filename": "x.xlsx"},
            )


def test_load_sales_dataframe_reads_stored_rows() -> None:
    upload_id: int = save_upload_metadata("rows.xlsx")
    store_dataframe_rows(
        upload_id,
        pd.DataFrame({"amount": [10.5, 2]}),
    )

    loaded: pd.DataFrame = load_sales_dataframe()

    assert list(loaded.columns) == ["amount"]
    assert len(loaded) == 2
    assert str(loaded.iloc[0]["amount"]) in {"10.5", "10.50"}


def test_load_sales_dataframe_requires_stored_data() -> None:
    with pytest.raises(ValueError, match="No sales data"):
        load_sales_dataframe()


def test_load_sales_dataframe_rejects_empty_table() -> None:
    ensure_dynamic_sales_table(["amount"])
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
    upload_id: int = save_upload_metadata("rows.xlsx")
    store_dataframe_rows(upload_id, pd.DataFrame({"amount": [1]}))
    real_conn: sqlite3.Connection = get_db_connection()

    class _FailingSelect:
        """Real connection, except the sales SELECT raises."""

        def execute(self, sql: str, *params: Any) -> sqlite3.Cursor:
            if sql.startswith("SELECT amount"):
                raise sqlite3.Error("disk")
            return real_conn.execute(sql, *params)

        def close(self) -> None:
            real_conn.close()

    with patch("database.get_db_connection", return_value=_FailingSelect()):
        with caplog.at_level("ERROR"):
            with pytest.raises(RuntimeError, match="Failed to load sales data"):
                load_sales_dataframe()

    assert "disk" in caplog.text
