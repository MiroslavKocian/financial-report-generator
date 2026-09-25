"""SQLite access with hand-written raw SQL (no ORM).

Educational choice: every query is visible SQL so interviewers can see
parameter binding (?) for values and identifier validation for names.
"""

import re
import sqlite3
from typing import Any

import pandas as pd

DB_NAME: str = "sales_data.db"
DYNAMIC_SALES_TABLE: str = "dynamic_sales_data"

# Values can use ? placeholders; table/column names cannot — validate them.
_IDENTIFIER_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_sql_identifier(name: str) -> str:
    """Reject names that are unsafe to embed as SQL identifiers."""
    if not _IDENTIFIER_PATTERN.fullmatch(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


def get_db_connection() -> sqlite3.Connection:
    """Open a SQLite connection with dict-like row access."""
    conn: sqlite3.Connection = sqlite3.connect(DB_NAME)
    # Row lets callers use row["column"] instead of opaque tuples.
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the uploads metadata table if it does not exist."""
    conn: sqlite3.Connection = get_db_connection()
    try:
        with conn:
            # uploads is the stable catalog of every Excel received.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS uploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
    finally:
        conn.close()


def save_upload_metadata(filename: str) -> int:
    """Insert an uploads row and return its primary key (upload_id)."""
    if not filename:
        raise ValueError("filename is required.")

    conn: sqlite3.Connection = get_db_connection()
    try:
        with conn:
            cursor: sqlite3.Cursor = conn.cursor()
            # Parameterized value — never concatenate user text into SQL.
            cursor.execute(
                "INSERT INTO uploads (filename) VALUES (?)",
                (filename,),
            )
            new_id: int | None = cursor.lastrowid
    finally:
        conn.close()

    if new_id is None:
        raise RuntimeError("SQLite did not return an upload id.")
    return new_id


def clear_stored_upload_data() -> None:
    """
    Drop sales rows and the uploads catalog.

    The app keeps one active dataset: a successful new upload replaces
    whatever was stored before (possibly with different Excel columns).
    """
    table_name: str = validate_sql_identifier(DYNAMIC_SALES_TABLE)
    conn: sqlite3.Connection = get_db_connection()
    try:
        with conn:
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.execute("DELETE FROM uploads")
    finally:
        conn.close()


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """True when sqlite_master lists the table (raw SQL introspection)."""
    cursor: sqlite3.Cursor = conn.execute(
        """
        SELECT 1 FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    )
    return cursor.fetchone() is not None


def _existing_data_columns(
    conn: sqlite3.Connection,
    table_name: str,
) -> list[str]:
    """Return user data columns (exclude id and upload_id)."""
    # PRAGMA cannot take ? placeholders for the table name; name is validated.
    cursor: sqlite3.Cursor = conn.execute(f"PRAGMA table_info({table_name})")
    columns: list[str] = [
        row["name"]
        for row in cursor.fetchall()
        if row["name"] not in {"id", "upload_id"}
    ]
    return columns


def ensure_dynamic_sales_table(column_names: list[str]) -> None:
    """
    Create dynamic_sales_data for the given columns, or fail if an
    existing table has a different schema.

    Normal flow clears the table before each successful upload, so a
    new workbook may introduce different columns. This check remains a
    safety net if clear was skipped.
    """
    safe_columns: list[str] = [
        validate_sql_identifier(name) for name in column_names
    ]
    table_name: str = validate_sql_identifier(DYNAMIC_SALES_TABLE)

    conn: sqlite3.Connection = get_db_connection()
    try:
        if _table_exists(conn, table_name):
            existing: list[str] = _existing_data_columns(conn, table_name)
            if existing != safe_columns:
                raise ValueError(
                    "Existing dynamic_sales_data columns "
                    f"{existing} do not match upload columns "
                    f"{safe_columns}."
                )
            return

        col_defs: str = ", ".join(
            f"{column} TEXT" for column in safe_columns
        )
        with conn:
            # Identifiers above were validated; values stay parameterized.
            conn.execute(f"""
                CREATE TABLE {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    upload_id INTEGER,
                    {col_defs},
                    FOREIGN KEY (upload_id) REFERENCES uploads (id)
                )
            """)
    finally:
        conn.close()


def insert_generic_row(table_name: str, row_data: dict[str, Any]) -> int:
    """
    Insert one row with a dynamic raw SQL INSERT.

    Column names come from Excel headers (validated). Cell values always
    bind through ? placeholders to avoid SQL injection.
    """
    safe_table: str = validate_sql_identifier(table_name)
    if not row_data:
        raise ValueError("row_data must not be empty.")

    safe_columns: list[str] = [
        validate_sql_identifier(column) for column in row_data
    ]
    placeholders: str = ", ".join("?" for _ in safe_columns)
    columns_sql: str = ", ".join(safe_columns)
    values: tuple[Any, ...] = tuple(row_data[col] for col in safe_columns)

    conn: sqlite3.Connection = get_db_connection()
    try:
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute(
            f"""
            INSERT INTO {safe_table}
            ({columns_sql})
            VALUES ({placeholders})
            """,
            values,
        )
        conn.commit()
        new_row_id: int | None = cursor.lastrowid
    except sqlite3.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Failed to insert into {safe_table}: {exc}") from exc
    finally:
        conn.close()

    if new_row_id is None:
        raise RuntimeError("SQLite did not return a row id.")
    return new_row_id


def store_dataframe_rows(upload_id: int, dataframe: pd.DataFrame) -> int:
    """
    Ensure the dynamic table matches the DataFrame, then insert all rows.

    Returns the number of rows stored (useful for the API response).
    """
    column_names: list[str] = [str(col) for col in dataframe.columns]
    ensure_dynamic_sales_table(column_names)

    inserted_count: int = 0
    for _, series in dataframe.iterrows():
        row_dict: dict[str, Any] = series.to_dict()
        # upload_id links each sales row back to the uploads catalog.
        row_payload: dict[str, Any] = {
            **row_dict,
            "upload_id": upload_id,
        }
        insert_generic_row(DYNAMIC_SALES_TABLE, row_payload)
        inserted_count += 1
    return inserted_count
