import os
import sqlite3
from typing import Any

import pytest

from database import (
    DB_NAME,
    get_db_connection,
    init_db,
    insert_generic_row,
    save_upload_metadata,
)


@pytest.fixture(autouse=True)
def clean_database():
    """Fixture to ensure a clean database before and after each test."""
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    init_db()
    yield
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)


def test_save_upload_metadata() -> None:
    file_id: int = save_upload_metadata("test_file.xlsx")
    assert isinstance(file_id, int)
    assert file_id > 0


def test_save_upload_metadata_persists_in_db() -> None:
    filename: str = "persisted_test.xlsx"
    file_id: int = save_upload_metadata(filename)

    conn: sqlite3.Connection = get_db_connection()
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute("SELECT filename FROM uploads WHERE id = ?", (file_id,))
    row: sqlite3.Row | None = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row["filename"] == filename


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
