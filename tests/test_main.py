"""Tests for FastAPI upload and home routes."""

import gc
import io
import logging
import os
import shutil
import sqlite3
import time
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from database import DB_NAME, DYNAMIC_SALES_TABLE, init_db
from file_manager import UPLOAD_DIR
from main import app

client: TestClient = TestClient(app)


def _remove_db_file() -> None:
    """Delete the SQLite file; retry briefly on Windows file locks."""
    if not os.path.exists(DB_NAME):
        return
    gc.collect()
    for _ in range(10):
        try:
            os.remove(DB_NAME)
            return
        except PermissionError:
            time.sleep(0.05)


def _excel_bytes(dataframe: pd.DataFrame) -> bytes:
    buffer: io.BytesIO = io.BytesIO()
    dataframe.to_excel(buffer, index=False, engine="openpyxl")
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def clean_environment():
    """Clean database and upload folder for each test."""
    _remove_db_file()
    init_db()
    if os.path.exists(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)
    yield
    _remove_db_file()
    if os.path.exists(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)


def test_read_root_endpoint() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Upload and Store" in response.text
    assert 'href="/summary"' in response.text


_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _post_excel(filename: str, dataframe: pd.DataFrame):
    return client.post(
        "/uploadfile/",
        files={"file": (filename, _excel_bytes(dataframe), _MIME)},
    )


def test_summary_without_data_returns_400(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR):
        response = client.get("/summary")
    assert response.status_code == 400
    assert "No sales data" in response.json()["detail"]
    assert "Summary request failed" in caplog.text


def test_summary_returns_total_min_and_max() -> None:
    uploaded = _post_excel(
        "sales.xlsx",
        pd.DataFrame({"Amount": [10, 25, 5]}),
    )
    assert uploaded.status_code == 200

    response = client.get("/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 3
    assert body["total_amount"] == 40.0
    assert body["min_amount"] == 5.0
    assert body["max_amount"] == 25.0


def test_summary_runtime_error_returns_500(caplog: pytest.LogCaptureFixture) -> None:
    with patch("main.load_sales_dataframe", side_effect=RuntimeError("db down")):
        with caplog.at_level(logging.ERROR):
            response = client.get("/summary")
    assert response.status_code == 500
    assert "db down" in response.json()["detail"]
    assert "Summary request failed" in caplog.text


def test_upload_file_endpoint() -> None:
    """Happy path: disk file + uploads row + dynamic_sales_data rows."""
    excel_bytes: bytes = _excel_bytes(
        pd.DataFrame(
            {
                "Region": ["North", "South"],
                "Amount": [100.50, 250.75],
            }
        )
    )
    filename: str = "test_report.xlsx"

    response = client.post(
        "/uploadfile/",
        files={
            "file": (
                filename,
                excel_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200
    json_response: dict = response.json()
    assert json_response["filename"] == filename
    assert json_response["status"] == ("File uploaded and raw data stored via raw SQL")
    assert isinstance(json_response["file_id"], int)
    assert json_response["rows_stored"] == 2
    assert os.path.exists(os.path.join(UPLOAD_DIR, filename))

    # End-to-end proof that raw SQL storage wrote the Excel rows.
    conn: sqlite3.Connection = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT filename FROM uploads WHERE id = ?",
        (json_response["file_id"],),
    )
    upload_row = cursor.fetchone()
    cursor.execute(
        f"SELECT region, amount, upload_id FROM {DYNAMIC_SALES_TABLE} ORDER BY id"
    )
    data_rows = cursor.fetchall()
    conn.close()

    assert upload_row is not None
    assert upload_row["filename"] == filename
    assert len(data_rows) == 2
    assert data_rows[0]["region"] == "North"
    assert data_rows[0]["upload_id"] == json_response["file_id"]


def test_upload_invalid_file_format() -> None:
    bad_bytes: bytes = b"This is just a plain text file, not Excel!"
    response = client.post(
        "/uploadfile/",
        files={"file": ("invalid.txt", bad_bytes, "text/plain")},
    )
    assert response.status_code == 400
    assert "Invalid Excel file format" in response.json()["detail"]
    # Failed parse must not leave an orphaned file in uploads/.
    assert not os.path.exists(os.path.join(UPLOAD_DIR, "invalid.txt"))


def test_upload_same_filename_replaces_dataset() -> None:
    first_bytes: bytes = _excel_bytes(
        pd.DataFrame({"Region": ["North"], "Amount": [1.0]})
    )
    second_bytes: bytes = _excel_bytes(
        pd.DataFrame({"Region": ["South", "East"], "Amount": [2.0, 3.0]})
    )
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert (
        client.post(
            "/uploadfile/",
            files={"file": ("same.xlsx", first_bytes, mime)},
        ).status_code
        == 200
    )
    second = client.post(
        "/uploadfile/",
        files={"file": ("same.xlsx", second_bytes, mime)},
    )
    assert second.status_code == 200
    assert second.json()["rows_stored"] == 2
    assert os.path.exists(os.path.join(UPLOAD_DIR, "same.xlsx"))

    conn: sqlite3.Connection = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    upload_count = conn.execute("SELECT COUNT(*) FROM uploads").fetchone()[0]
    data_count = conn.execute(f"SELECT COUNT(*) FROM {DYNAMIC_SALES_TABLE}").fetchone()[
        0
    ]
    conn.close()

    assert upload_count == 1
    assert data_count == 2


def test_upload_save_value_error_returns_400() -> None:
    with patch(
        "main.save_uploaded_file",
        side_effect=ValueError("Uploaded file must have a filename."),
    ):
        response = client.post(
            "/uploadfile/",
            files={"file": ("x.xlsx", b"data", "text/plain")},
        )
    assert response.status_code == 400
    assert "filename" in response.json()["detail"]


def test_upload_save_oserror_returns_500() -> None:
    with patch(
        "main.save_uploaded_file",
        side_effect=OSError("disk full"),
    ):
        response = client.post(
            "/uploadfile/",
            files={"file": ("x.xlsx", b"data", "text/plain")},
        )
    assert response.status_code == 500
    assert "disk full" in response.json()["detail"]


def test_upload_store_value_error_cleans_metadata() -> None:
    """ValueError after metadata INSERT must delete the uploads row."""
    excel_bytes: bytes = _excel_bytes(
        pd.DataFrame({"Region": ["North"], "Amount": [1.0]})
    )

    with patch(
        "main.store_dataframe_rows",
        side_effect=ValueError("storage rejected"),
    ):
        response = client.post(
            "/uploadfile/",
            files={
                "file": (
                    "ok.xlsx",
                    excel_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert response.status_code == 400
    assert "storage rejected" in response.json()["detail"]
    assert not os.path.exists(os.path.join(UPLOAD_DIR, "ok.xlsx"))

    conn: sqlite3.Connection = sqlite3.connect(DB_NAME)
    count = conn.execute("SELECT COUNT(*) FROM uploads").fetchone()[0]
    conn.close()
    assert count == 0


def test_upload_store_runtime_error_returns_500() -> None:
    excel_bytes: bytes = _excel_bytes(
        pd.DataFrame({"Region": ["North"], "Amount": [1.0]})
    )

    with patch(
        "main.store_dataframe_rows",
        side_effect=RuntimeError("insert failed"),
    ):
        response = client.post(
            "/uploadfile/",
            files={
                "file": (
                    "ok.xlsx",
                    excel_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert response.status_code == 500
    assert "insert failed" in response.json()["detail"]
    assert not os.path.exists(os.path.join(UPLOAD_DIR, "ok.xlsx"))


def test_upload_replaces_previous_dataset() -> None:
    """A second valid file wipes prior disk file and DB rows."""
    first = _excel_bytes(pd.DataFrame({"Region": ["North"], "Amount": [1.0]}))
    second = _excel_bytes(
        pd.DataFrame({"Region": ["South", "East"], "Amount": [2.0, 3.0]})
    )
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert (
        client.post(
            "/uploadfile/",
            files={"file": ("a.xlsx", first, mime)},
        ).status_code
        == 200
    )

    response = client.post(
        "/uploadfile/",
        files={"file": ("b.xlsx", second, mime)},
    )
    assert response.status_code == 200
    assert response.json()["rows_stored"] == 2
    assert response.json()["filename"] == "b.xlsx"

    assert not os.path.exists(os.path.join(UPLOAD_DIR, "a.xlsx"))
    assert os.path.exists(os.path.join(UPLOAD_DIR, "b.xlsx"))

    conn: sqlite3.Connection = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    upload_rows = conn.execute("SELECT filename FROM uploads ORDER BY id").fetchall()
    data_rows = conn.execute(
        f"SELECT region, amount FROM {DYNAMIC_SALES_TABLE} ORDER BY id"
    ).fetchall()
    conn.close()

    assert len(upload_rows) == 1
    assert upload_rows[0]["filename"] == "b.xlsx"
    assert len(data_rows) == 2
    assert data_rows[0]["region"] == "South"
    assert data_rows[1]["region"] == "East"


def test_upload_replaces_with_different_schema() -> None:
    """Replace also allows a new workbook with different columns."""
    first = _excel_bytes(pd.DataFrame({"Region": ["North"], "Amount": [1.0]}))
    second = _excel_bytes(pd.DataFrame({"Product": ["Widget"], "Price": [9.5]}))
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert (
        client.post(
            "/uploadfile/",
            files={"file": ("a.xlsx", first, mime)},
        ).status_code
        == 200
    )
    response = client.post(
        "/uploadfile/",
        files={"file": ("b.xlsx", second, mime)},
    )
    assert response.status_code == 200
    assert response.json()["rows_stored"] == 1

    conn: sqlite3.Connection = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    row = conn.execute(f"SELECT product, price FROM {DYNAMIC_SALES_TABLE}").fetchone()
    uploads_count = conn.execute("SELECT COUNT(*) FROM uploads").fetchone()[0]
    conn.close()

    assert uploads_count == 1
    assert row is not None
    assert row["product"] == "Widget"


def test_upload_invalid_second_file_keeps_previous_data() -> None:
    """A bad second upload must not wipe the first successful dataset."""
    first = _excel_bytes(pd.DataFrame({"Region": ["North"], "Amount": [1.0]}))
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert (
        client.post(
            "/uploadfile/",
            files={"file": ("a.xlsx", first, mime)},
        ).status_code
        == 200
    )

    response = client.post(
        "/uploadfile/",
        files={"file": ("bad.txt", b"not-excel", "text/plain")},
    )
    assert response.status_code == 400
    assert not os.path.exists(os.path.join(UPLOAD_DIR, "bad.txt"))
    assert os.path.exists(os.path.join(UPLOAD_DIR, "a.xlsx"))

    conn: sqlite3.Connection = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    uploads_count = conn.execute("SELECT COUNT(*) FROM uploads").fetchone()[0]
    data_count = conn.execute(f"SELECT COUNT(*) FROM {DYNAMIC_SALES_TABLE}").fetchone()[
        0
    ]
    conn.close()

    assert uploads_count == 1
    assert data_count == 1
