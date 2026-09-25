"""SQLite access with hand-written SQL and validated identifiers."""

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

DB_NAME: str = "sales_data.db"
DYNAMIC_SALES_TABLE: str = "dynamic_sales_data"
_RESERVED_COLUMNS: frozenset[str] = frozenset({"id", "upload_id"})

_IDENTIFIER_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class StoredUpload:
    """Result of replacing the active sales dataset."""

    upload_id: int
    rows_stored: int


def validate_sql_identifier(name: str) -> str:
    """Reject names that are unsafe to embed as SQL identifiers."""
    if not _IDENTIFIER_PATTERN.fullmatch(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


def get_db_connection() -> sqlite3.Connection:
    """Open a SQLite connection with dict-like row access."""
    conn: sqlite3.Connection = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the uploads metadata table if it does not exist."""
    conn: sqlite3.Connection = get_db_connection()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS uploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
    finally:
        conn.close()


def _validate_data_columns(column_names: list[str]) -> list[str]:
    """Ensure Excel headers are safe SQL column names."""
    safe_columns: list[str] = [validate_sql_identifier(name) for name in column_names]
    reserved: set[str] = set(safe_columns) & _RESERVED_COLUMNS
    if reserved:
        raise ValueError(f"Excel column names {sorted(reserved)} are reserved.")
    return safe_columns


def _cell_value(value: object) -> str | None:
    """Store cell values as TEXT; missing cells become SQL NULL."""
    if pd.isna(value):
        return None
    return str(value)


def replace_sales_dataset(filename: str, dataframe: pd.DataFrame) -> StoredUpload:
    """
    Replace the active dataset inside one SQLite transaction.

    On failure the previous dataset is left unchanged.
    """
    if not filename:
        raise ValueError("filename is required.")

    safe_columns: list[str] = _validate_data_columns(
        [str(column) for column in dataframe.columns]
    )
    table_name: str = validate_sql_identifier(DYNAMIC_SALES_TABLE)

    conn: sqlite3.Connection = get_db_connection()
    try:
        conn.execute("BEGIN")
        conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        conn.execute("DELETE FROM uploads")
        cursor: sqlite3.Cursor = conn.execute(
            "INSERT INTO uploads (filename) VALUES (?)",
            (filename,),
        )
        upload_id: int | None = cursor.lastrowid
        if upload_id is None:
            raise RuntimeError("SQLite did not return an upload id.")

        col_defs: str = ", ".join(f"{column} TEXT" for column in safe_columns)
        conn.execute(
            f"""
            CREATE TABLE {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                upload_id INTEGER,
                {col_defs},
                FOREIGN KEY (upload_id) REFERENCES uploads (id)
            )
            """
        )

        if not dataframe.empty:
            insert_columns: list[str] = ["upload_id", *safe_columns]
            placeholders: str = ", ".join("?" for _ in insert_columns)
            columns_sql: str = ", ".join(insert_columns)
            row_values: list[tuple[Any, ...]] = [
                (
                    upload_id,
                    *(_cell_value(row[column]) for column in safe_columns),
                )
                for _, row in dataframe.iterrows()
            ]
            conn.executemany(
                f"""
                INSERT INTO {table_name} ({columns_sql})
                VALUES ({placeholders})
                """,
                row_values,
            )

        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        logger.error("Failed to replace sales dataset: %s", exc)
        raise RuntimeError(f"Failed to replace sales dataset: {exc}") from exc
    finally:
        conn.close()

    return StoredUpload(upload_id=upload_id, rows_stored=len(dataframe))


def clear_stored_upload_data() -> None:
    """Drop sales rows and the uploads catalog."""
    table_name: str = validate_sql_identifier(DYNAMIC_SALES_TABLE)
    conn: sqlite3.Connection = get_db_connection()
    try:
        with conn:
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.execute("DELETE FROM uploads")
    finally:
        conn.close()


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """True when sqlite_master lists the table."""
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
    cursor: sqlite3.Cursor = conn.execute(f"PRAGMA table_info({table_name})")
    columns: list[str] = [
        row["name"] for row in cursor.fetchall() if row["name"] not in _RESERVED_COLUMNS
    ]
    return columns


def save_upload_metadata(filename: str) -> int:
    """Insert an uploads row and return its primary key (upload_id)."""
    if not filename:
        raise ValueError("filename is required.")

    conn: sqlite3.Connection = get_db_connection()
    try:
        with conn:
            cursor: sqlite3.Cursor = conn.cursor()
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


def ensure_dynamic_sales_table(column_names: list[str]) -> None:
    """Create dynamic_sales_data for the given columns."""
    safe_columns: list[str] = _validate_data_columns(column_names)
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

        col_defs: str = ", ".join(f"{column} TEXT" for column in safe_columns)
        with conn:
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
    """Insert one row with a dynamic raw SQL INSERT."""
    safe_table: str = validate_sql_identifier(table_name)
    if not row_data:
        raise ValueError("row_data must not be empty.")

    safe_columns: list[str] = [validate_sql_identifier(column) for column in row_data]
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
    """Ensure the dynamic table matches the DataFrame, then insert all rows."""
    column_names: list[str] = [str(col) for col in dataframe.columns]
    ensure_dynamic_sales_table(column_names)

    inserted_count: int = 0
    for _, series in dataframe.iterrows():
        row_dict: dict[str, Any] = series.to_dict()
        row_payload: dict[str, Any] = {
            **row_dict,
            "upload_id": upload_id,
        }
        insert_generic_row(DYNAMIC_SALES_TABLE, row_payload)
        inserted_count += 1
    return inserted_count


def load_sales_dataframe() -> pd.DataFrame:
    """Read the active sales table into a DataFrame."""
    table_name: str = validate_sql_identifier(DYNAMIC_SALES_TABLE)
    conn: sqlite3.Connection = get_db_connection()
    try:
        if not _table_exists(conn, table_name):
            raise ValueError("No sales data is stored.")

        columns: list[str] = [
            validate_sql_identifier(name)
            for name in _existing_data_columns(conn, table_name)
        ]
        if not columns:
            raise ValueError("No sales data is stored.")

        columns_sql: str = ", ".join(columns)
        try:
            cursor: sqlite3.Cursor = conn.execute(
                f"SELECT {columns_sql} FROM {table_name} ORDER BY id"
            )
            rows: list[dict[str, Any]] = [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as exc:
            logger.error("Failed to load sales data: %s", exc)
            raise RuntimeError(f"Failed to load sales data: {exc}") from exc
    finally:
        conn.close()

    if not rows:
        raise ValueError("No sales data is stored.")
    return pd.DataFrame(rows, columns=columns)
