"""Tests for FastAPI upload and home routes."""

import gc
import io
import os
import shutil
import time
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from database import DB_NAME, init_db
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


def test_upload_file_endpoint() -> None:
    df_test: pd.DataFrame = pd.DataFrame(
        {"Region": ["North", "South"], "Amount": [100.50, 250.75]}
    )
    excel_buffer: io.BytesIO = io.BytesIO()
    df_test.to_excel(excel_buffer, index=False, engine="openpyxl")
    excel_bytes: bytes = excel_buffer.getvalue()

    filename: str = "test_report.xlsx"

    response = client.post(
        "/uploadfile/",
        files={
            "file": (
                filename,
                excel_bytes,
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200

    json_response: dict = response.json()
    assert json_response["filename"] == filename
    assert json_response["status"] == (
        "File uploaded and raw data stored via raw SQL"
    )
    assert isinstance(json_response["file_id"], int)
    assert json_response["rows_stored"] == 2
    assert os.path.exists(os.path.join(UPLOAD_DIR, filename))


def test_upload_invalid_file_format() -> None:
    bad_bytes: bytes = b"This is just a plain text file, not Excel!"
    response = client.post(
        "/uploadfile/",
        files={"file": ("invalid.txt", bad_bytes, "text/plain")},
    )
    assert response.status_code == 400
    assert "Invalid Excel file format" in response.json()["detail"]


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


def test_upload_store_runtime_error_returns_500() -> None:
    df_test: pd.DataFrame = pd.DataFrame(
        {"Region": ["North"], "Amount": [1.0]}
    )
    excel_buffer: io.BytesIO = io.BytesIO()
    df_test.to_excel(excel_buffer, index=False, engine="openpyxl")
    excel_bytes: bytes = excel_buffer.getvalue()

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
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet",
                )
            },
        )
    assert response.status_code == 500
    assert "insert failed" in response.json()["detail"]
